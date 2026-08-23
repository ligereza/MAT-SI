"""Speculative PiPi-inspired representation-lift audit.

This module is deliberately outside the accepted MAT-SI phase history.  It tests
one narrow question from the PiPi handoff:

    can a representation be discovered, paid for, and then used without losing
    the future behaviour of the original problem?

The audit has three small families:

* A: affine CNF/Tseitin-like instances, with a blind affine detector and a
  GF(2) solver, plus perturbed and random negative controls;
* B: subset-sum histories, where a full residual is compared with coarse
  projections under an explicit future-query class;
* C: a local next-digit predictor on generated pi digits, random digits, a
  shuffled-pi control, and a planted local process.

The result keeps discovery, transformation, solver, state, and fidelity
measurements separate.  It does not add a MAT-SI primitive, start Phase 5, or
claim that a toy speedup is a general theorem.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, localcontext
from itertools import combinations
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
PARENT_COMMIT = "059574f"
PROTOCOL = "speculative-order-dimensions-lift-audit-v0"


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AffineInstance:
    name: str
    n_vars: int
    equations: tuple[tuple[tuple[int, ...], int], ...]
    clauses: tuple[tuple[int, ...], ...]


def _encode_xor(variables: tuple[int, ...], rhs: int) -> list[tuple[int, ...]]:
    """Encode xor(variables) == rhs as CNF clauses.

    Variables are zero-based internally; literals are one-based, as in DIMACS.
    Each clause forbids one assignment whose parity disagrees with ``rhs``.
    """

    clauses: list[tuple[int, ...]] = []
    for assignment in range(1 << len(variables)):
        bits = [(assignment >> offset) & 1 for offset in range(len(variables))]
        if sum(bits) % 2 == rhs:
            continue
        clause = tuple(
            -(variable + 1) if bit else variable + 1
            for variable, bit in zip(variables, bits)
        )
        clauses.append(clause)
    return clauses


def _tseitin_instance(vertices: int) -> AffineInstance:
    """Make a small 3-regular graph with one inconsistent charge.

    Every edge is a Boolean variable and every vertex contributes an odd-width
    xor equation.  The xor of all equations is inconsistent because every edge
    occurs twice while the charges sum to one.
    """

    if vertices < 6 or vertices % 2:
        raise ValueError("vertices must be an even integer >= 6")
    edges: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    def add_edge(left: int, right: int) -> None:
        edge = tuple(sorted((left, right)))
        if edge not in seen:
            seen.add(edge)
            edges.append(edge)

    for vertex in range(vertices):
        add_edge(vertex, (vertex + 1) % vertices)
    for vertex in range(vertices // 2):
        add_edge(vertex, vertex + vertices // 2)

    incident: list[list[int]] = [[] for _ in range(vertices)]
    for edge_index, (left, right) in enumerate(edges):
        incident[left].append(edge_index)
        incident[right].append(edge_index)

    equations = tuple(
        (tuple(incident[vertex]), 1 if vertex == 0 else 0)
        for vertex in range(vertices)
    )
    clauses = tuple(
        clause
        for variables, rhs in equations
        for clause in _encode_xor(variables, rhs)
    )
    return AffineInstance(
        name=f"tseitin_{vertices}",
        n_vars=len(edges),
        equations=equations,
        clauses=clauses,
    )


def _perturb(instance: AffineInstance) -> AffineInstance:
    clauses = list(instance.clauses)
    first = list(clauses[0])
    first[0] *= -1
    clauses[0] = tuple(first)
    return AffineInstance(
        name=f"{instance.name}_perturbed",
        n_vars=instance.n_vars,
        equations=(),
        clauses=tuple(clauses),
    )


def _random_3sat(instance: AffineInstance, seed: int) -> AffineInstance:
    rng = random.Random(seed)
    clauses: list[tuple[int, ...]] = []
    for _ in range(len(instance.clauses)):
        variables = sorted(rng.sample(range(instance.n_vars), 3))
        clauses.append(
            tuple(
                variable + 1 if rng.randrange(2) else -(variable + 1)
                for variable in variables
            )
        )
    return AffineInstance(
        name=f"{instance.name}_random3sat",
        n_vars=instance.n_vars,
        equations=(),
        clauses=tuple(clauses),
    )


def discover_affine(
    clauses: Iterable[tuple[int, ...]], n_vars: int
) -> dict[str, Any]:
    """Blindly detect exact xor clause blocks from raw CNF."""

    grouped: dict[tuple[int, ...], list[tuple[int, ...]]] = defaultdict(list)
    clause_count = 0
    for clause in clauses:
        clause_count += 1
        support = tuple(sorted(abs(literal) - 1 for literal in clause))
        if len(set(support)) != len(support):
            return {
                "detected": False,
                "equations": [],
                "discovery_steps": clause_count,
                "reason": "repeated_variable_in_clause",
            }
        grouped[support].append(tuple(clause))

    equations: list[tuple[tuple[int, ...], int]] = []
    for support, block in sorted(grouped.items()):
        expected = 1 << (len(support) - 1)
        if len(block) != expected:
            return {
                "detected": False,
                "equations": [],
                "discovery_steps": clause_count + len(grouped),
                "reason": f"support_{support}_has_{len(block)}_clauses_expected_{expected}",
            }
        forbidden_assignments: set[int] = set()
        parity: set[int] = set()
        for clause in block:
            assignment = 0
            for offset, literal in enumerate(clause):
                if literal < 0:
                    assignment |= 1 << offset
            if assignment in forbidden_assignments:
                return {
                    "detected": False,
                    "equations": [],
                    "discovery_steps": clause_count + len(grouped),
                    "reason": "duplicate_forbidden_assignment",
                }
            forbidden_assignments.add(assignment)
            parity.add(assignment.bit_count() % 2)
        if len(forbidden_assignments) != expected or len(parity) != 1:
            return {
                "detected": False,
                "equations": [],
                "discovery_steps": clause_count + len(grouped),
                "reason": "forbidden_assignments_are_not_one_parity_class",
            }
        equations.append((support, 1 - next(iter(parity))))

    covered = {variable for support in grouped for variable in support}
    if not equations or covered != set(range(n_vars)):
        return {
            "detected": False,
            "equations": [],
            "discovery_steps": clause_count + len(grouped),
            "reason": "not_all_variables_covered",
        }
    return {
        "detected": True,
        "equations": equations,
        "discovery_steps": clause_count + len(grouped),
        "reason": "exact_affine_clause_blocks",
    }


def solve_gf2(
    equations: Iterable[tuple[tuple[int, ...], int]], n_vars: int
) -> dict[str, Any]:
    rows = []
    for variables, rhs in equations:
        mask = 0
        for variable in variables:
            mask ^= 1 << variable
        rows.append([mask, rhs & 1])

    pivot_row = 0
    row_xor_ops = 0
    rank = 0
    for column in range(n_vars):
        pivot = next(
            (index for index in range(pivot_row, len(rows)) if rows[index][0] & (1 << column)),
            None,
        )
        if pivot is None:
            continue
        rows[pivot_row], rows[pivot] = rows[pivot], rows[pivot_row]
        for index in range(len(rows)):
            if index != pivot_row and rows[index][0] & (1 << column):
                rows[index][0] ^= rows[pivot_row][0]
                rows[index][1] ^= rows[pivot_row][1]
                row_xor_ops += 1
        pivot_row += 1
        rank += 1
    inconsistent = any(mask == 0 and rhs for mask, rhs in rows)
    return {
        "sat": not inconsistent,
        "rank": rank,
        "row_xor_ops": row_xor_ops,
        "equation_count": len(rows),
    }


def solve_dpll(
    clauses: tuple[tuple[int, ...], ...], n_vars: int, node_cap: int = 250_000
) -> dict[str, Any]:
    assignment: list[bool | None] = [None] * n_vars
    nodes = 0

    def propagate() -> bool | None:
        changed = True
        while changed:
            changed = False
            for clause in clauses:
                undecided: list[int] = []
                satisfied = False
                for literal in clause:
                    value = assignment[abs(literal) - 1]
                    if value is None:
                        undecided.append(literal)
                    elif (literal > 0 and value) or (literal < 0 and not value):
                        satisfied = True
                        break
                if satisfied:
                    continue
                if not undecided:
                    return False
                if len(undecided) == 1:
                    literal = undecided[0]
                    variable = abs(literal) - 1
                    desired = literal > 0
                    if assignment[variable] is not None and assignment[variable] != desired:
                        return False
                    if assignment[variable] is None:
                        assignment[variable] = desired
                        changed = True
        return None

    def search() -> bool | None:
        nonlocal nodes
        nodes += 1
        if nodes > node_cap:
            return None
        marker = assignment[:]
        contradiction = propagate()
        if contradiction is False:
            assignment[:] = marker
            return False
        if all(value is not None for value in assignment):
            assignment[:] = marker
            return True
        variable = next(index for index, value in enumerate(assignment) if value is None)
        for value in (False, True):
            assignment[variable] = value
            result = search()
            if result is True:
                assignment[:] = marker
                return True
            if result is None:
                assignment[:] = marker
                return None
            assignment[variable] = None
        assignment[:] = marker
        return False

    started = perf_counter()
    solved = search()
    return {
        "sat": solved if solved is not None else None,
        "status": "TIMEOUT" if solved is None else "SOLVED",
        "nodes": nodes,
        "node_cap": node_cap,
        "wall_ms": round((perf_counter() - started) * 1000, 4),
    }


def _affine_row(instance: AffineInstance) -> dict[str, Any]:
    discovery = discover_affine(instance.clauses, instance.n_vars)
    dpll = solve_dpll(instance.clauses, instance.n_vars)
    gf2 = (
        solve_gf2(discovery["equations"], instance.n_vars)
        if discovery["detected"]
        else None
    )
    semantics_preserved = (
        gf2 is not None and dpll["sat"] is not None and gf2["sat"] == dpll["sat"]
    )
    return {
        "instance": instance.name,
        "n_vars": instance.n_vars,
        "cnf_clauses": len(instance.clauses),
        "affine_detected": discovery["detected"],
        "discovery_reason": discovery["reason"],
        "semantics_preserved": semantics_preserved,
        "dpll": dpll,
        "gf2": gf2,
        "resources": {
            "discovery_steps": discovery["discovery_steps"],
            "transform_clauses": len(instance.clauses),
            "dpll_nodes": dpll["nodes"],
            "gf2_row_xor_ops": gf2["row_xor_ops"] if gf2 else None,
        },
    }


def run_affine_audit() -> dict[str, Any]:
    positive = [_tseitin_instance(vertices) for vertices in (6, 8, 10, 12, 14)]
    perturbed = [_perturb(instance) for instance in positive]
    random_controls = [_random_3sat(instance, seed=900 + index) for index, instance in enumerate(positive)]
    positive_rows = [_affine_row(instance) for instance in positive]
    negative_rows = [_affine_row(instance) for instance in perturbed + random_controls]
    return {
        "question": "can a raw CNF be lifted to affine structure without losing semantics?",
        "positive_family": positive_rows,
        "negative_controls": negative_rows,
        "summary": {
            "positive_count": len(positive_rows),
            "positive_detected": all(row["affine_detected"] for row in positive_rows),
            "positive_semantics_preserved": all(row["semantics_preserved"] for row in positive_rows),
            "positive_solver_work_reduced": all(
                row["gf2"] is not None
                and row["gf2"]["row_xor_ops"] < row["dpll"]["nodes"]
                for row in positive_rows
            ),
            "negative_count": len(negative_rows),
            "negative_rejected": all(not row["affine_detected"] for row in negative_rows),
        },
        "interpretation": "candidate representation only; solver-work vectors are not collapsed into one cost scalar",
    }


def _subset_sums(weights: tuple[int, ...]) -> set[int]:
    sums = {0}
    for weight in weights:
        sums |= {value + weight for value in tuple(sums)}
    return sums


def _future_class(residual: int, suffix_sums: set[int]) -> tuple[str, int | None]:
    """Future query class for exact suffix completion.

    The query class is the complete suffix decision tree for the fixed target:
    a live residual is keyed by its exact value, while all impossible residuals
    share the same all-false (dead) future.
    """

    return ("live", residual) if residual in suffix_sums else ("dead", None)


def _projection_value(projection: str, residual: int) -> Any:
    if projection == "full_residual":
        return residual
    if projection == "sign":
        return -1 if residual < 0 else 0 if residual == 0 else 1
    if projection == "parity":
        return residual % 2
    if projection.startswith("mod"):
        return residual % int(projection[3:])
    raise ValueError(f"unknown projection: {projection}")


def _subset_case(
    kind: str, weights: tuple[int, ...], split: int, target: int
) -> dict[str, Any]:
    prefix = weights[:split]
    suffix = weights[split:]
    suffix_sums = _subset_sums(suffix)
    prefix_residuals = [target - sum(prefix[index] for index in range(split) if mask & (1 << index)) for mask in range(1 << split)]
    future_classes = {_future_class(residual, suffix_sums) for residual in prefix_residuals}
    live = [value for value in future_classes if value[0] == "live"]
    dead_histories = sum(1 for residual in prefix_residuals if residual not in suffix_sums)
    projections: dict[str, dict[str, Any]] = {}
    for projection in ("full_residual", "sign", "parity", "mod3", "mod5", "mod16"):
        groups: dict[Any, set[tuple[str, int | None]]] = defaultdict(set)
        for residual in prefix_residuals:
            groups[_projection_value(projection, residual)].add(_future_class(residual, suffix_sums))
        ambiguous = sum(1 for futures in groups.values() if len(futures) > 1)
        projections[projection] = {
            "projected_states": len(groups),
            "ambiguous_groups": ambiguous,
            "exact_for_future": ambiguous == 0,
        }
    exact_classes = len(future_classes)
    return {
        "kind": kind,
        "n_weights": len(weights),
        "split": split,
        "target": target,
        "prefix_histories": len(prefix_residuals),
        "unique_full_residuals": len(set(prefix_residuals)),
        "live_future_classes": len(live),
        "dead_histories": dead_histories,
        "dead_future_class_present": dead_histories > 0,
        "exact_future_classes": exact_classes,
        "history_to_future_class_ratio": round(len(prefix_residuals) / exact_classes, 6),
        "projections": projections,
        "resources": {
            "prefix_histories": len(prefix_residuals),
            "suffix_distinct_sums": len(suffix_sums),
            "full_state_count": len(set(prefix_residuals)),
        },
    }


def run_future_quotient_audit() -> dict[str, Any]:
    dense = tuple(1 << (index // 2) for index in range(16))
    superincreasing = tuple(1 << index for index in range(16))
    cases = [
        _subset_case("dense_redundant", dense, split=8, target=sum(dense) // 2),
        _subset_case("superincreasing", superincreasing, split=8, target=sum(superincreasing) // 2),
    ]
    dense_case, super_case = cases
    return {
        "question": "does a compressed state preserve the future query class?",
        "cases": cases,
        "summary": {
            "dense_has_exact_compression": dense_case["exact_future_classes"] < dense_case["prefix_histories"],
            "dense_full_residual_is_exact": dense_case["projections"]["full_residual"]["exact_for_future"],
            "dense_coarse_projection_rejected": any(
                not value["exact_for_future"]
                for key, value in dense_case["projections"].items()
                if key != "full_residual"
            ),
            "superincreasing_has_no_collapse": super_case["unique_full_residuals"] == super_case["prefix_histories"],
        },
        "interpretation": "full residual is a candidate future-sufficient state only for the stated suffix query class",
    }


def _pi_digits(count: int) -> str:
    with localcontext() as context:
        context.prec = count + 12

        def arctan_inverse(inverse: int) -> Decimal:
            x = Decimal(1) / Decimal(inverse)
            x_squared = x * x
            term = x
            total = term
            denominator = 1
            while abs(term) > Decimal(10) ** (-(count + 8)):
                term *= -x_squared
                denominator += 2
                total += term / Decimal(denominator)
            return +total

        pi = 16 * arctan_inverse(5) - 4 * arctan_inverse(239)
        rendered = format(+pi, "f")
    digits = "".join(character for character in rendered if character.isdigit())
    return digits[:count]


def _random_digits(count: int, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(str(rng.randrange(10)) for _ in range(count))


def _shuffled_digits(digits: str, seed: int) -> str:
    values = list(digits)
    random.Random(seed).shuffle(values)
    return "".join(values)


def _planted_digits(count: int) -> str:
    return "".join(str((index + 3) % 10) for index in range(count))


def _mode(counts: Counter[str], fallback: str = "0") -> str:
    return min(counts, key=lambda digit: (-counts[digit], digit)) if counts else fallback


def _local_prediction(digits: str, train_fraction: float = 0.6, context_size: int = 2) -> dict[str, Any]:
    split = int(len(digits) * train_fraction)
    train = digits[:split]
    test = digits[split:]
    baseline = _mode(Counter(train))
    contexts: dict[str, Counter[str]] = defaultdict(Counter)
    for index in range(context_size, len(train)):
        contexts[train[index - context_size : index]][train[index]] += 1
    baseline_correct = 0
    local_correct = 0
    for offset, digit in enumerate(test):
        position = split + offset
        context = digits[position - context_size : position]
        baseline_correct += digit == baseline
        local_correct += digit == _mode(contexts.get(context, Counter()), baseline)
    return {
        "digits": len(digits),
        "train_digits": len(train),
        "test_digits": len(test),
        "context_size": context_size,
        "baseline_accuracy": round(baseline_correct / len(test), 6),
        "local_accuracy": round(local_correct / len(test), 6),
        "heldout_gain": round((local_correct - baseline_correct) / len(test), 6),
        "contexts_seen": len(contexts),
    }


def run_digit_negative_control() -> dict[str, Any]:
    count = 1200
    pi = _pi_digits(count)
    random_digits = _random_digits(count, seed=20260823)
    shuffled_pi = _shuffled_digits(pi, seed=20260823)
    planted = _planted_digits(count)
    rows = {
        "pi": _local_prediction(pi),
        "random": _local_prediction(random_digits),
        "shuffled_pi": _local_prediction(shuffled_pi),
        "planted_local": _local_prediction(planted),
    }
    return {
        "question": "does pi expose a useful held-out local digit rule?",
        "rows": rows,
        "summary": {
            "pi_is_not_stronger_than_random": rows["pi"]["heldout_gain"] <= rows["random"]["heldout_gain"] + 0.02,
            "pi_is_not_stronger_than_shuffled": rows["pi"]["heldout_gain"] <= rows["shuffled_pi"]["heldout_gain"] + 0.02,
            "planted_rule_detected": rows["planted_local"]["heldout_gain"] > rows["pi"]["heldout_gain"] + 0.2,
        },
        "interpretation": "a negative result for pi is a control, not evidence that pi has no nonlocal structure",
    }


def _observability_record(family: str, payload: dict[str, Any]) -> dict[str, Any]:
    digest = _digest(payload)
    return {
        "before": {"state_digest": _digest({"family": family, "phase": "raw"}), "scope": "raw_instance"},
        "intervention": {"event_digest": digest[:16], "kind": "opaque_representation_lift"},
        "after": {"state_digest": _digest({"family": family, "phase": "candidate", "payload": payload}), "scope": "candidate_representation"},
        "provenance": {
            "source_system": "MAT-SI-PiPi-independent-audit",
            "source_ref": f"generated://{family}",
            "field_audit": {
                "before": {"RAW_SOURCE": "deterministic_generator", "DERIVATION": "canonical raw instance", "LOSS": "none", "RESIDUE": {"payload_digest": digest}, "PROVENANCE": "module"},
                "intervention": {"RAW_SOURCE": "audit protocol", "DERIVATION": "opaque lift token", "LOSS": "semantic label withheld", "RESIDUE": {"payload_digest": digest}, "PROVENANCE": "module"},
                "after": {"RAW_SOURCE": "candidate result", "DERIVATION": "candidate solver/state summary", "LOSS": "full payload remains recoverable from generator", "RESIDUE": {"payload_digest": digest}, "PROVENANCE": "module"},
                "provenance": {"RAW_SOURCE": "repository-owned generator", "DERIVATION": "deterministic run", "LOSS": "wall-clock is machine-dependent", "RESIDUE": {"protocol": PROTOCOL}, "PROVENANCE": "parent commit " + PARENT_COMMIT},
            },
        },
        "resources": {
            "dimensions": {"discovery_steps": {"status": "MEASURED"}, "transform_units": {"status": "MEASURED"}, "solver_units": {"status": "MEASURED"}},
            "scalar_collapsed": False,
        },
        "residue": {"candidate": True, "certificate": "see family result", "evidence_for": [], "evidence_against": [], "fallback": "retain raw representation"},
    }


def run_order_dimension_audit() -> dict[str, Any]:
    affine = run_affine_audit()
    quotient = run_future_quotient_audit()
    digits = run_digit_negative_control()
    return {
        "protocol": PROTOCOL,
        "parent_commit": PARENT_COMMIT,
        "scope": "speculative evidence; does not modify accepted MAT-SI phase state",
        "families": {"A_affine_lift": affine, "B_future_quotient": quotient, "C_pi_local_negative": digits},
        "observability_contract": {
            "mandatory_fields": ["before", "intervention", "after", "provenance"],
            "optional_fields": ["resources"],
            "records": [
                _observability_record("A_affine_lift", affine["summary"]),
                _observability_record("B_future_quotient", quotient["summary"]),
                _observability_record("C_pi_local_negative", digits["summary"]),
            ],
        },
        "gate": {
            "decision": "KEEP-SPECULATIVE",
            "phase5_started": False,
            "accepted_frontier_modified": False,
            "main_modified": False,
            "next": "freeze parameters, add held-out instances, and rerun from a clean checkout before any promotion",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the speculative PiPi-inspired MAT-SI audit")
    parser.add_argument("--json-out", type=Path, default=ROOT / "results" / "order-dimensions-lift-audit.json")
    args = parser.parse_args(argv)
    result = run_order_dimension_audit()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("A positive detected:", result["families"]["A_affine_lift"]["summary"]["positive_detected"])
    print("B dense exact compression:", result["families"]["B_future_quotient"]["summary"]["dense_has_exact_compression"])
    print("C planted rule detected:", result["families"]["C_pi_local_negative"]["summary"]["planted_rule_detected"])
    print("gate:", result["gate"]["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
