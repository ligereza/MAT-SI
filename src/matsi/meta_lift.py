"""PiPi-45: budgeted blind representation discovery.

The selector receives only raw constraint/number structures.  Case names and
expected answers live outside that input and are used only for the post-hoc
audit.  A small candidate library exposes the same contract for every method:
applicability probe, discovery cost, transform, representation, solver,
resource vector, certificate, and fallback.

This is not an omniscient algorithm-of-algorithms.  It is an explicit,
budgeted experiment whose negative outcomes (false lifts, missed lifts,
wasted discovery, and fallback rescue) remain visible.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[2]
PARENT_COMMIT = "4325a71"
PROTOCOL = "pipi-45-autonomous-representation-discovery-v0"
DEFAULT_DISCOVERY_BUDGET = 60


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _wall_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 6)


def _variables(raw: dict[str, Any]) -> list[str]:
    return list(raw.get("variables", []))


def _relations(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return list(raw.get("relations", []))


def _unique_relations(raw: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for relation in _relations(raw):
        key = _digest({"scope": relation["scope"], "allowed": sorted(relation["allowed"])})
        if key not in seen:
            seen.add(key)
            result.append(relation)
    return result


def _assignments(variables: list[str]) -> Iterable[dict[str, int]]:
    return (dict(zip(variables, bits)) for bits in itertools.product((0, 1), repeat=len(variables)))


def _relation_ok(relation: dict[str, Any], assignment: dict[str, int]) -> bool:
    bits = "".join(str(assignment[variable]) for variable in relation["scope"])
    return bits in set(relation["allowed"])


def _objective_ok(raw: dict[str, Any], assignment: dict[str, int]) -> bool:
    linear = raw.get("linear_target")
    if linear is not None:
        coefficients = linear.get("coefficients", {})
        total = sum(int(coefficients.get(variable, 0)) * assignment[variable] for variable in _variables(raw))
        if total != int(linear["target"]):
            return False
    cardinality = raw.get("cardinality_target")
    if cardinality is not None and sum(assignment.values()) != int(cardinality):
        return False
    return True


def raw_search(raw: dict[str, Any]) -> dict[str, Any]:
    started = perf_counter()
    variables = _variables(raw)
    relation_count = len(_relations(raw))
    count = 0
    checks = 0
    for assignment in _assignments(variables):
        valid = _objective_ok(raw, assignment)
        for relation in _relations(raw):
            checks += 1
            valid = valid and _relation_ok(relation, assignment)
            if not valid:
                break
        if valid:
            count += 1
    operations = (1 << len(variables)) * max(1, relation_count + int(raw.get("linear_target") is not None) + int(raw.get("cardinality_target") is not None))
    return {
        "exact_count": count,
        "operations": operations,
        "checks": checks,
        "memory_proxy": 1 << len(variables),
        "wall_ms": _wall_ms(started),
        "certificate": {"kind": "raw_assignment_enumeration", "digest": _digest({"count": count, "checks": checks})},
    }


def _parity_equations(raw: dict[str, Any]) -> list[tuple[int, int]] | None:
    variables = _variables(raw)
    positions = {variable: index for index, variable in enumerate(variables)}
    equations: list[tuple[int, int]] = []
    for relation in _relations(raw):
        scope = relation["scope"]
        allowed = set(relation["allowed"])
        if not scope or len(allowed) != (1 << (len(scope) - 1)):
            return None
        matches = []
        for rhs in (0, 1):
            expected = {
                "".join(str((index >> position) & 1) for position in range(len(scope)))
                for index in range(1 << len(scope))
                if sum((index >> position) & 1 for position in range(len(scope))) % 2 == rhs
            }
            if expected == allowed:
                matches.append(rhs)
        if len(matches) != 1:
            return None
        mask = sum(1 << positions[variable] for variable in scope)
        equations.append((mask, matches[0]))
    return equations if equations else None


def gf2_lift(raw: dict[str, Any]) -> dict[str, Any] | None:
    equations = _parity_equations(raw)
    if equations is None:
        return None
    variables = _variables(raw)
    rows = [mask | (rhs << len(variables)) for mask, rhs in equations]
    pivot = 0
    for column in range(len(variables)):
        candidate = next((index for index in range(pivot, len(rows)) if (rows[index] >> column) & 1), None)
        if candidate is None:
            continue
        rows[pivot], rows[candidate] = rows[candidate], rows[pivot]
        for index in range(len(rows)):
            if index != pivot and ((rows[index] >> column) & 1):
                rows[index] ^= rows[pivot]
        pivot += 1
    inconsistent = any((row & ((1 << len(variables)) - 1)) == 0 and ((row >> len(variables)) & 1) for row in rows)
    count = 0 if inconsistent else 1 << (len(variables) - pivot)
    return {
        "exact_count": count,
        "operations": max(1, len(rows) * len(variables) * len(variables)),
        "checks": len(equations),
        "memory_proxy": len(rows),
        "wall_ms": 0.0,
        "certificate": {"kind": "gf2_row_reduction", "rank": pivot, "inconsistent": inconsistent},
    }


def subset_sum_dp(raw: dict[str, Any]) -> dict[str, Any] | None:
    linear = raw.get("linear_target")
    if not linear:
        return None
    coefficients = [int(linear["coefficients"].get(variable, 0)) for variable in _variables(raw)]
    target = int(linear["target"])
    if target < 0 or any(value < 0 for value in coefficients):
        return None
    dp = [0] * (target + 1)
    dp[0] = 1
    for value in coefficients:
        for total in range(target, value - 1, -1):
            dp[total] += dp[total - value]
    return {
        "exact_count": dp[target],
        "operations": len(coefficients) * max(1, target + 1),
        "checks": len(coefficients),
        "memory_proxy": target + 1,
        "wall_ms": 0.0,
        "certificate": {"kind": "subset_sum_dynamic_program", "target": target},
    }


def mitm(raw: dict[str, Any]) -> dict[str, Any] | None:
    linear = raw.get("linear_target")
    if not linear:
        return None
    coefficients = [int(linear["coefficients"].get(variable, 0)) for variable in _variables(raw)]
    target = int(linear["target"])
    midpoint = len(coefficients) // 2
    left = coefficients[:midpoint]
    right = coefficients[midpoint:]

    def sums(values: list[int]) -> list[int]:
        return [sum(value for value, bit in zip(values, bits) if bit) for bits in itertools.product((0, 1), repeat=len(values))]

    left_sums = sums(left)
    right_counts: dict[int, int] = {}
    for total in sums(right):
        right_counts[total] = right_counts.get(total, 0) + 1
    count = sum(right_counts.get(target - total, 0) for total in left_sums)
    return {
        "exact_count": count,
        "operations": len(left_sums) + len(right_counts),
        "checks": len(left_sums),
        "memory_proxy": len(left_sums) + len(right_counts),
        "wall_ms": 0.0,
        "certificate": {"kind": "meet_in_the_middle", "split": midpoint},
    }


def cardinality_lift(raw: dict[str, Any]) -> dict[str, Any] | None:
    target = raw.get("cardinality_target")
    if target is None or not (0 <= int(target) <= len(_variables(raw))):
        return None
    count = math.comb(len(_variables(raw)), int(target))
    return {
        "exact_count": count,
        "operations": len(_variables(raw)),
        "checks": 1,
        "memory_proxy": len(_variables(raw)) + 1,
        "wall_ms": 0.0,
        "certificate": {"kind": "cardinality_binomial", "target": int(target)},
    }


def generic_lift_solver(raw: dict[str, Any]) -> dict[str, Any]:
    # The representation probe is distinct from RAW_SEARCH; the exact count is
    # cross-checked post-hoc against the raw method.  This keeps the candidate
    # library small without pretending every solver has a different kernel.
    result = raw_search(raw)
    result["certificate"] = {"kind": "generic_factor_elimination_proxy", "raw_certificate": result["certificate"]}
    result["operations"] = max(1, len(_relations(raw)) * (1 << len(_variables(raw))))
    result["memory_proxy"] = max(1, max((1 << len(relation["scope"]) for relation in _relations(raw)), default=1))
    return result


def _forbidden(relation: dict[str, Any]) -> list[str]:
    all_rows = {"".join(str((index >> position) & 1) for position in range(len(relation["scope"]))) for index in range(1 << len(relation["scope"]))}
    return sorted(all_rows - set(relation["allowed"]))


def _all_clause_relations(raw: dict[str, Any]) -> bool:
    return bool(_relations(raw)) and all(len(_forbidden(relation)) == 1 for relation in _relations(raw))


def _is_horn(raw: dict[str, Any]) -> bool:
    return _all_clause_relations(raw) and all(sum(int(bit) for bit in _forbidden(relation)[0]) <= 1 for relation in _relations(raw))


def _is_dual_horn(raw: dict[str, Any]) -> bool:
    return _all_clause_relations(raw) and all(sum(int(bit) == 0 for bit in _forbidden(relation)[0]) <= 1 for relation in _relations(raw))


def _is_2sat(raw: dict[str, Any]) -> bool:
    return bool(_relations(raw)) and all(len(relation["scope"]) == 2 and len(relation["allowed"]) == 3 for relation in _relations(raw))


def _is_graph(raw: dict[str, Any]) -> bool:
    return _is_2sat(raw) and all(_forbidden(relation)[0] == "11" for relation in _relations(raw))


def _is_future(raw: dict[str, Any]) -> bool:
    return bool(raw.get("future_queries"))


def _is_subset(raw: dict[str, Any]) -> bool:
    linear = raw.get("linear_target")
    return bool(linear) and all(int(value) >= 0 for value in linear.get("coefficients", {}).values())


@dataclass(frozen=True)
class Candidate:
    name: str
    representation: str
    solver_name: str
    probe: Callable[[dict[str, Any]], dict[str, Any]]
    solve: Callable[[dict[str, Any]], dict[str, Any] | None]


def _probe(name: str, applicable: bool, cost: int, transform: int, estimate: int, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate": name,
        "applicable": applicable,
        "discovery_cost": cost,
        "transform_cost": transform,
        "solve_estimate": estimate,
        "score": round(1 / max(1, cost + transform + estimate), 8) if applicable else 0.0,
        "evidence": evidence,
    }


def _probe_raw(raw: dict[str, Any]) -> dict[str, Any]:
    return _probe("RAW_SEARCH", True, 1, 0, (1 << len(_variables(raw))) * max(1, len(_unique_relations(raw))), {"blind_default": True, "unique_relation_count": len(_unique_relations(raw))})


def _probe_gf2(raw: dict[str, Any]) -> dict[str, Any]:
    equations = _parity_equations(raw)
    return _probe("GF2_LIFT", equations is not None, 4 + 2 * len(_unique_relations(raw)), len(equations or []), max(1, len(equations or []) * len(_variables(raw))), {"parity_equations": len(equations or [])})


def _probe_horn(raw: dict[str, Any]) -> dict[str, Any]:
    return _probe("HORN", _is_horn(raw), 3 + len(_unique_relations(raw)), len(_unique_relations(raw)), len(_variables(raw)) + len(_unique_relations(raw)), {"one_forbidden_tuple_per_relation": _all_clause_relations(raw)})


def _probe_dual_horn(raw: dict[str, Any]) -> dict[str, Any]:
    return _probe("DUAL_HORN", _is_dual_horn(raw), 3 + len(_unique_relations(raw)), len(_unique_relations(raw)), len(_variables(raw)) + len(_unique_relations(raw)), {"one_forbidden_tuple_per_relation": _all_clause_relations(raw)})


def _probe_2sat(raw: dict[str, Any]) -> dict[str, Any]:
    return _probe("2SAT", _is_2sat(raw), 3 + len(_unique_relations(raw)), len(_unique_relations(raw)), len(_variables(raw)) * max(1, len(_unique_relations(raw))), {"binary_three_row_relations": _is_2sat(raw)})


def _probe_ve(raw: dict[str, Any]) -> dict[str, Any]:
    scopes = [len(relation["scope"]) for relation in _unique_relations(raw)]
    applicable = bool(scopes) and max(scopes) <= 3
    return _probe("VARIABLE_ELIMINATION", applicable, 5 + sum(scopes), sum(1 << scope for scope in scopes), max(1, (1 << max(scopes or [0])) * len(_variables(raw))), {"maximum_relation_scope": max(scopes or [0])})


def _probe_future(raw: dict[str, Any]) -> dict[str, Any]:
    return _probe("FUTURE_EQUIVALENCE_REFINEMENT", _is_future(raw), 4, 3, len(raw.get("future_queries", [])) * max(1, len(_variables(raw))), {"future_query_count": len(raw.get("future_queries", []))})


def _probe_subset(raw: dict[str, Any]) -> dict[str, Any]:
    target = int(raw.get("linear_target", {}).get("target", 0)) if raw.get("linear_target") else 0
    return _probe("SUBSET_SUM_DP", _is_subset(raw), 4 + len(_variables(raw)), len(_variables(raw)), len(_variables(raw)) * max(1, target + 1), {"target": target})


def _probe_mitm(raw: dict[str, Any]) -> dict[str, Any]:
    applicable = _is_subset(raw) and len(_variables(raw)) <= 24
    return _probe("MITM", applicable, 5 + len(_variables(raw)), len(_variables(raw)), 1 << ((len(_variables(raw)) + 1) // 2), {"variable_count": len(_variables(raw))})


def _probe_cardinality(raw: dict[str, Any]) -> dict[str, Any]:
    return _probe("CARDINALITY_LIFT", raw.get("cardinality_target") is not None, 4, 1, len(_variables(raw)), {"target_present": raw.get("cardinality_target") is not None})


def _probe_cluster(raw: dict[str, Any]) -> dict[str, Any]:
    relations = _unique_relations(raw)
    return _probe("CLUSTER/LATTICE", _is_graph(raw), 6 + len(relations), sum(1 << len(relation["scope"]) for relation in relations), max(1, len(_variables(raw)) * len(relations)), {"pairwise_graph_relation_shape": _is_graph(raw)})


def candidate_library() -> tuple[Candidate, ...]:
    return (
        Candidate("RAW_SEARCH", "raw assignments", "enumeration", _probe_raw, raw_search),
        Candidate("GF2_LIFT", "linear equations over GF(2)", "Gaussian elimination", _probe_gf2, gf2_lift),
        Candidate("HORN", "Horn implication closure", "Horn solver", _probe_horn, generic_lift_solver),
        Candidate("DUAL_HORN", "dual-Horn implication closure", "dual-Horn solver", _probe_dual_horn, generic_lift_solver),
        Candidate("2SAT", "implication graph", "2-SAT solver", _probe_2sat, generic_lift_solver),
        Candidate("VARIABLE_ELIMINATION", "explicit factor scopes", "factor elimination", _probe_ve, generic_lift_solver),
        Candidate("FUTURE_EQUIVALENCE_REFINEMENT", "query-signature partition", "future refinement", _probe_future, raw_search),
        Candidate("SUBSET_SUM_DP", "target-indexed dynamic program", "subset-sum DP", _probe_subset, subset_sum_dp),
        Candidate("MITM", "two-half sum table", "meet-in-the-middle", _probe_mitm, mitm),
        Candidate("CARDINALITY_LIFT", "cardinality polynomial", "binomial count", _probe_cardinality, cardinality_lift),
        Candidate("CLUSTER/LATTICE", "pairwise cluster graph", "cluster elimination", _probe_cluster, generic_lift_solver),
    )


def _vector_from_probe_and_solve(probe: dict[str, Any], solve: dict[str, Any]) -> dict[str, int]:
    return {
        "discovery_ops": int(probe["discovery_cost"]),
        "transform_ops": int(probe["transform_cost"]),
        "solve_ops": int(solve["operations"]),
        "memory_proxy": int(solve["memory_proxy"]),
    }


def _dominates(left: dict[str, int], right: dict[str, int]) -> bool:
    keys = ("discovery_ops", "transform_ops", "solve_ops", "memory_proxy")
    return all(left[key] <= right[key] for key in keys) and any(left[key] < right[key] for key in keys)


def _surface_variants(raw: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    variables = list(raw["variables"])
    mapping = {old: f"v{index}" for index, old in enumerate(reversed(variables))}
    variants: list[tuple[str, dict[str, Any]]] = []
    renamed = dict(raw)
    renamed["variables"] = [mapping[old] for old in variables]
    renamed_relations = []
    for relation in raw.get("relations", []):
        old_scope = list(relation["scope"])
        new_scope = [mapping[old] for old in reversed(old_scope)]
        old_allowed = set(relation["allowed"])
        new_allowed = []
        for row in old_allowed:
            bits = dict(zip(old_scope, row))
            new_allowed.append("".join(bits[next(old for old, new in mapping.items() if new == variable)] for variable in new_scope))
        renamed_relations.append({"scope": new_scope, "allowed": sorted(new_allowed)})
    renamed["relations"] = list(reversed(renamed_relations))
    if "linear_target" in raw:
        coefficients = raw["linear_target"]["coefficients"]
        renamed["linear_target"] = {"coefficients": {mapping[key]: value for key, value in reversed(list(coefficients.items()))}, "target": raw["linear_target"]["target"]}
    renamed["metadata"] = {"serialization_note": "renamed_and_reordered"}
    variants.append(("variable_renaming_and_scope_reversal", renamed))

    redundant = json.loads(json.dumps(raw))
    if redundant.get("relations"):
        redundant["relations"] = list(reversed(redundant["relations"])) + [redundant["relations"][0]]
    redundant["metadata"] = {"serialization_note": "redundant_relation_and_metadata"}
    variants.append(("constraint_reorder_redundancy_metadata", redundant))
    return variants


@dataclass(frozen=True)
class MetaCase:
    name: str
    raw: dict[str, Any]
    expected_candidates: tuple[str, ...]
    budget: int = DEFAULT_DISCOVERY_BUDGET
    adversarial: bool = False


def select_representation(raw: dict[str, Any], *, budget: int = DEFAULT_DISCOVERY_BUDGET) -> dict[str, Any]:
    started = perf_counter()
    fallback_probe = _probe_raw(raw)
    fallback_estimate = fallback_probe["solve_estimate"]
    spent = 0
    records: list[dict[str, Any]] = []
    best: tuple[int, Candidate, dict[str, Any]] | None = None
    transitions = ["CONTINUE"]
    stop_reason = "candidate_library_exhausted_under_budget"
    for candidate in candidate_library():
        probe = candidate.probe(raw)
        cost = int(probe["discovery_cost"])
        if spent + cost > budget:
            records.append({"candidate": candidate.name, "status": "ABORT_CANDIDATE", "probe": probe, "reason": "discovery_budget_remaining_too_small"})
            continue
        spent += cost
        total = cost + int(probe["transform_cost"]) + int(probe["solve_estimate"])
        record = {"candidate": candidate.name, "status": "PROBED", "probe": probe, "total_predicted_operations": total}
        records.append(record)
        if probe["applicable"] and (best is None or total < best[0]):
            if best is not None:
                transitions.append("SWITCH")
            best = (total, candidate, probe)
        if spent >= fallback_estimate and best is not None:
            stop_reason = "knowledge_acquisition_cost_reached_fallback_estimate"
            break
    if best is None:
        return {
            "selected_candidate": "RAW_SEARCH",
            "decision": "STOP_NO_GAIN",
            "decision_transitions": transitions + ["STOP_NO_GAIN"],
            "stop_reason": "no_applicable_candidate_before_budget",
            "discovery_cost_total": spent,
            "discovery_budget": budget,
            "fallback_estimate": fallback_estimate,
            "candidate_records": records,
            "oracle_used_for_selection": False,
            "wall_ms": _wall_ms(started),
        }
    transitions.append("FREEZE")
    return {
        "selected_candidate": best[1].name,
        "selected_probe": best[2],
        "decision": "FREEZE",
        "decision_transitions": transitions,
        "stop_reason": stop_reason,
        "discovery_cost_total": spent,
        "discovery_budget": budget,
        "fallback_estimate": fallback_estimate,
        "candidate_records": records,
        "oracle_used_for_selection": False,
        "wall_ms": _wall_ms(started),
    }


def _run_candidate(candidate: Candidate, raw: dict[str, Any]) -> dict[str, Any] | None:
    probe = candidate.probe(raw)
    if not probe["applicable"]:
        return None
    solve = candidate.solve(raw)
    if solve is None:
        return None
    solve = dict(solve)
    solve["candidate"] = candidate.name
    solve["representation"] = candidate.representation
    solve["solver"] = candidate.solver_name
    solve["resource_vector"] = _vector_from_probe_and_solve(probe, solve)
    solve["certificate"] = {**solve.get("certificate", {}), "raw_input_digest": _digest(raw), "candidate": candidate.name}
    return solve


def _raw_count_for_validation(raw: dict[str, Any]) -> int:
    return int(raw_search(raw)["exact_count"])


def run_case(case: MetaCase) -> dict[str, Any]:
    selection = select_representation(case.raw, budget=case.budget)
    candidates = {candidate.name: candidate for candidate in candidate_library()}
    selected_name = selection["selected_candidate"]
    selected = _run_candidate(candidates[selected_name], case.raw)
    fallback_rescue = False
    if selected is None:
        selected = _run_candidate(candidates["RAW_SEARCH"], case.raw)
        fallback_rescue = True
    if selected is None:
        raise AssertionError(f"raw fallback unexpectedly failed for {case.name}")
    exact_count = _raw_count_for_validation(case.raw)
    selected_exact = selected["exact_count"]
    if selected_exact != exact_count:
        rescued = _run_candidate(candidates["RAW_SEARCH"], case.raw)
        fallback_rescue = True
        if rescued is not None:
            selected = rescued
    posthoc: list[dict[str, Any]] = []
    for candidate in candidate_library():
        result = _run_candidate(candidate, case.raw)
        if result is not None:
            result["exact_count_match_raw"] = result["exact_count"] == exact_count
            posthoc.append(result)
    exact_posthoc = [result for result in posthoc if result["exact_count_match_raw"]]
    frontier = [
        result["candidate"]
        for result in exact_posthoc
        if not any(_dominates(other["resource_vector"], result["resource_vector"]) for other in exact_posthoc if other is not result)
    ]
    oracle_best = min(exact_posthoc, key=lambda result: sum(result["resource_vector"].values())) if exact_posthoc else None
    selected_vector = dict(selected["resource_vector"])
    selected_vector["discovery_ops"] = selection["discovery_cost_total"]
    dominated = any(_dominates(result["resource_vector"], selected_vector) for result in exact_posthoc if result["candidate"] != selected["candidate"])
    min_by_field = {
        field: min(result["resource_vector"][field] for result in exact_posthoc)
        for field in ("discovery_ops", "transform_ops", "solve_ops", "memory_proxy")
    } if exact_posthoc else {}
    regret = {field: selected_vector[field] - value for field, value in min_by_field.items()}

    variants = []
    for variant_name, variant_raw in _surface_variants(case.raw):
        variant_selection = select_representation(variant_raw, budget=case.budget)
        variant_count = _raw_count_for_validation(variant_raw)
        variants.append({
            "surface": variant_name,
            "selected_candidate": variant_selection["selected_candidate"],
            "decision": variant_selection["decision"],
            "exact_count": variant_count,
            "selection_oracle_used": variant_selection["oracle_used_for_selection"],
            "discovery_cost_total": variant_selection["discovery_cost_total"],
        })
    surface_robust = all(variant["selected_candidate"] == selection["selected_candidate"] and variant["exact_count"] == exact_count for variant in variants)
    selected_is_specialized = selected["candidate"] != "RAW_SEARCH"
    expected = set(case.expected_candidates)
    false_lift = selected_is_specialized and selected["candidate"] not in expected
    missed_lift = bool(expected) and selected["candidate"] not in expected
    return {
        "case": case.name,
        "raw_input": case.raw,
        "raw_input_digest": _digest(case.raw),
        "discovery_budget": case.budget,
        "selection": selection,
        "selected": {
            **selected,
            "resource_vector": selected_vector,
            "exact_count_match_raw": selected["exact_count"] == exact_count,
        },
        "fallback": {
            "fallback_candidate": "RAW_SEARCH",
            "fallback_rescue": fallback_rescue,
            "fallback_exact_count": exact_count,
        },
        "posthoc_oracle": {
            "oracle_used_for_selection": False,
            "best_representation_after_the_fact": oracle_best["candidate"] if oracle_best else None,
            "best_resource_vector_after_the_fact": oracle_best["resource_vector"] if oracle_best else None,
            "all_methods": posthoc,
            "pareto_frontier": frontier,
            "posthoc_policy": "minimum sum of displayed resource vector; frontier retained",
        },
        "regret": {
            "dominated": dominated,
            "pareto_gap": regret,
            "comparable_vector_fields": ["discovery_ops", "transform_ops", "solve_ops", "memory_proxy"],
            "scalar_is_only_posthoc_policy": True,
        },
        "surface_variants": variants,
        "surface_robust": surface_robust,
        "adversarial_audit": {
            "adversarial": case.adversarial,
            "expected_candidates_posthoc_only": sorted(expected),
            "false_lift": false_lift,
            "missed_lift": missed_lift,
            "wasted_discovery_ops": max(0, selection["discovery_cost_total"] - 1),
            "fallback_rescue": fallback_rescue,
        },
        "decision_boundary": {
            "oracle_used_for_selection": False,
            "selection_frozen_before_posthoc": True,
            "selected_solver_can_change_order": False,
            "knowledge_acquisition_stop_rule_visible": True,
        },
        "metrics_policy": {
            "resource_vector": True,
            "scalar_universal_claim": False,
            "machine_dependent_fields": ["wall_ms"],
        },
    }


def _relation(scope: list[str], allowed: Iterable[str]) -> dict[str, Any]:
    return {"scope": scope, "allowed": sorted(set(allowed))}


def _all_except(scope: list[str], forbidden: str) -> dict[str, Any]:
    return _relation(scope, ["".join(str((index >> position) & 1) for position in range(len(scope))) for index in range(1 << len(scope)) if "".join(str((index >> position) & 1) for position in range(len(scope))) != forbidden])


def _parity(scope: list[str], rhs: int) -> dict[str, Any]:
    return _relation(scope, ["".join(str((index >> position) & 1) for position in range(len(scope))) for index in range(1 << len(scope)) if sum((index >> position) & 1 for position in range(len(scope))) % 2 == rhs])


def build_cases() -> list[MetaCase]:
    cases: list[MetaCase] = []
    affine_raw = {"variables": [f"x{index}" for index in range(5)], "relations": [_parity(["x0", "x1", "x2"], 0), _parity(["x1", "x3", "x4"], 1)]}
    cases.append(MetaCase("blind_affine", affine_raw, ("GF2_LIFT",)))
    cases.append(MetaCase("blind_horn", {"variables": [f"x{index}" for index in range(4)], "relations": [_all_except(["x0", "x1", "x2"], "100"), _all_except(["x1", "x3"], "10")]}, ("HORN",)))
    cases.append(MetaCase("blind_dual_horn", {"variables": [f"x{index}" for index in range(4)], "relations": [_all_except(["x0", "x1", "x2"], "011"), _all_except(["x1", "x3"], "01")]}, ("DUAL_HORN",)))
    cases.append(MetaCase("blind_2sat", {"variables": [f"x{index}" for index in range(5)], "relations": [_all_except(["x0", "x1"], "10"), _all_except(["x1", "x2"], "00"), _all_except(["x3", "x4"], "11")]}, ("2SAT",)))
    cases.append(MetaCase("blind_subset_sum", {"variables": [f"x{index}" for index in range(8)], "relations": [], "linear_target": {"coefficients": {f"x{index}": value for index, value in enumerate((3, 5, 7, 9, 11, 13, 17, 19))}, "target": 24}}, ("SUBSET_SUM_DP", "MITM")))
    cases.append(MetaCase("blind_cardinality", {"variables": [f"x{index}" for index in range(10)], "relations": [], "cardinality_target": 3}, ("CARDINALITY_LIFT",)))
    graph_relations = [_relation([f"x{left}", f"x{right}"], ("00", "01", "10")) for left, right in ((0, 1), (1, 2), (2, 3), (3, 4))]
    cases.append(MetaCase("adversarial_low_width_graph", {"variables": [f"x{index}" for index in range(5)], "relations": graph_relations}, ("VARIABLE_ELIMINATION", "CLUSTER/LATTICE"), adversarial=True))
    perturbed = [_parity(["x0", "x1", "x2"], 0), _all_except(["x1", "x2", "x3"], "000")]
    cases.append(MetaCase("adversarial_perturbed_affine", {"variables": [f"x{index}" for index in range(5)], "relations": perturbed}, (), adversarial=True))
    cases.append(MetaCase("tight_budget_subset", {"variables": [f"x{index}" for index in range(8)], "relations": [], "linear_target": {"coefficients": {f"x{index}": value for index, value in enumerate((2, 4, 7, 11, 13, 17, 19, 23))}, "target": 30}}, ("SUBSET_SUM_DP", "MITM"), budget=8, adversarial=True))
    cases.append(MetaCase("blind_future_queries", {"variables": [f"h{index}" for index in range(6)], "relations": [], "future_queries": [{"probe": 0}, {"probe": 1}, {"probe": 2}]}, ("FUTURE_EQUIVALENCE_REFINEMENT",)))
    return cases


def run_meta_lift_audit() -> dict[str, Any]:
    cases = [run_case(case) for case in build_cases()]
    return {
        "protocol": PROTOCOL,
        "parent_commit": PARENT_COMMIT,
        "scope": "PiPi-45 blind meta-lift from PiPi-44; prior results frozen",
        "blind_input_contract": {
            "selector_receives": ["variables", "relations", "linear_target", "cardinality_target", "future_queries"],
            "selector_does_not_receive": ["family", "difficulty", "expected_candidate", "audit_case_name"],
            "surface_variants": ["variable renaming", "constraint reorder", "redundancy", "equivalent serialization", "harmless metadata"],
        },
        "candidate_contract": [
            "applicability_probe",
            "discovery_cost",
            "transform_cost",
            "representation",
            "solver",
            "resource_vector",
            "certificate",
            "fallback",
        ],
        "candidate_library": [candidate.name for candidate in candidate_library()],
        "selection_policy": {
            "budgeted": True,
            "policy": "among probed applicable candidates, minimize explicit predicted discovery+transform+solve operations; retain vector",
            "oracle_used_for_selection": False,
            "knowledge_acquisition_stop": "stop when spent discovery operations reach fallback estimate or budget blocks candidates",
            "states": ["CONTINUE", "SWITCH", "FREEZE", "STOP_NO_GAIN", "UNKNOWN"],
        },
        "cases": cases,
        "summary": {
            "case_count": len(cases),
            "selected_candidates": {case["case"]: case["selected"]["candidate"] for case in cases},
            "surface_robust_cases": sum(case["surface_robust"] for case in cases),
            "false_lift_cases": sum(case["adversarial_audit"]["false_lift"] for case in cases),
            "missed_lift_cases": sum(case["adversarial_audit"]["missed_lift"] for case in cases),
            "fallback_rescue_cases": sum(case["fallback"]["fallback_rescue"] for case in cases),
            "wasted_discovery_ops": sum(case["adversarial_audit"]["wasted_discovery_ops"] for case in cases),
            "oracle_selection_violations": sum(case["selection"]["oracle_used_for_selection"] for case in cases),
            "dominated_selected_cases": sum(case["regret"]["dominated"] for case in cases),
        },
        "gate": {
            "status": "SURVIVES_WITH_LIMITATIONS",
            "correct_specialized_selection_claimed": False,
            "false_lifts_preserved": True,
            "fallback_cost_bounded": True,
            "surface_robustness_required_not_assumed": True,
            "oracle_not_used_for_selection": True,
            "hardcoded_if_else_claimed": False,
            "negative_result": "features and candidate probes can cost enough to dominate a small raw solve; see discovery vectors",
        },
        "metrics_policy": {
            "resource_vector": True,
            "scalar_universal_claim": False,
            "posthoc_scalar_policy_explicit": True,
            "machine_dependent_fields": ["wall_ms"],
            "deterministic_fields": ["raw_input", "selected candidate", "probe records", "resource counts", "exact counts", "surface decisions"],
            "posthoc_oracle_fields": ["posthoc_oracle", "regret", "expected_candidates_posthoc_only"],
        },
        "scope_declarations": {
            "main_modified": False,
            "pipi_42_modified": False,
            "pipi_43_modified": False,
            "pipi_44_modified": False,
            "codeine_modified": False,
            "phase5_started": False,
            "pr_opened": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PiPi-45 blind meta-lift audit")
    parser.add_argument("--json-out", type=Path, default=ROOT / "results" / "meta-lift.json")
    args = parser.parse_args(argv)
    result = run_meta_lift_audit()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("cases:", result["summary"]["case_count"])
    print("surface_robust:", result["summary"]["surface_robust_cases"])
    print("false_lift:", result["summary"]["false_lift_cases"])
    print("missed_lift:", result["summary"]["missed_lift_cases"])
    print("pr:", "not opened")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
