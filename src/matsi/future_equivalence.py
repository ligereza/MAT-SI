"""PiPi-42: counterexample-driven future-equivalence discovery.

This is a new research unit branched from ``c99cfd1``.  It does not import or
modify the PiPi audit v0.  The experiment has four deliberately separated
levels:

* DISCOVERY: adaptive probes may split the current candidate partition;
* VALIDATION: a separate probe pool may provide counterexamples and refine it;
* SEALED_HOLDOUT: the frozen partition is audited but cannot change it;
* GROUND_TRUTH/ORACLE: exhaustive future behaviour is computed only after the
  sealed holdout and never enters a decision.

The implementation is intentionally transparent.  A probe is a callable future
query, a partition split is recorded with the histories and responses that caused
it, and every resource dimension remains separate.  No scalar Lift Gain is
defined here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[2]
PARENT_COMMIT = "c99cfd1"
PROTOCOL = "pipi-42-future-equivalence-discovery-v0"
SAMPLED_BASELINE_SEED = 4242
SAMPLED_BASELINE_COUNT = 16

PREREGISTERED_PREDICTIONS = (
    "Small future quotients should be discoverable with fewer queries than exhaustive future enumeration; "
    "near-maximal quotients should not yield useful compression; deceptive families should show early false "
    "merges that validation can reduce before sealed holdout. If these fail, degrade the hypothesis."
)


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _pair_count(size: int) -> int:
    return size * (size - 1) // 2


def _json_bytes(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))


@dataclass
class FutureQueryInterface:
    """A black-box future-query interface.

    The hidden response table is available to the post-hoc oracle, but the
    refinement algorithm receives only phase-specific query callables below.
    """

    name: str
    history_ids: tuple[int, ...]
    probe_ids: tuple[int, ...]
    _responses: dict[tuple[int, int], int]
    phase_calls: dict[str, int]
    phase_runtime_ms: dict[str, float]
    phase_sequence: list[str]

    @classmethod
    def create(
        cls,
        name: str,
        history_ids: Iterable[int],
        probe_ids: Iterable[int],
        responses: dict[tuple[int, int], int],
    ) -> "FutureQueryInterface":
        return cls(
            name=name,
            history_ids=tuple(history_ids),
            probe_ids=tuple(probe_ids),
            _responses=dict(responses),
            phase_calls=defaultdict(int),
            phase_runtime_ms=defaultdict(float),
            phase_sequence=[],
        )

    def clone(self, suffix: str) -> "FutureQueryInterface":
        return FutureQueryInterface.create(
            f"{self.name}{suffix}", self.history_ids, self.probe_ids, self._responses
        )

    def query(self, history_id: int, probe_id: int, phase: str) -> int:
        started = perf_counter()
        response = self._responses[(history_id, probe_id)]
        elapsed_ms = (perf_counter() - started) * 1000
        if phase not in self.phase_calls:
            self.phase_sequence.append(phase)
        self.phase_calls[phase] += 1
        self.phase_runtime_ms[phase] += elapsed_ms
        return response


@dataclass
class CaseSpec:
    family: str
    name: str
    interface: FutureQueryInterface
    discovery_probes: tuple[int, ...]
    validation_probes: tuple[int, ...]
    holdout_probes: tuple[int, ...]
    fallback: dict[str, Any]
    stop_config: dict[str, Any]
    raw_input: dict[str, Any]


def _split_probe_pool(
    probe_ids: Iterable[int], seed: int, discovery_count: int, validation_count: int
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    probes = list(probe_ids)
    random.Random(seed).shuffle(probes)
    discovery = tuple(sorted(probes[:discovery_count]))
    validation = tuple(sorted(probes[discovery_count : discovery_count + validation_count]))
    holdout = tuple(sorted(probes[discovery_count + validation_count :]))
    return discovery, validation, holdout


def _unique_binary_vectors(count: int, width: int, seed: int) -> list[tuple[int, ...]]:
    rng = random.Random(seed)
    vectors: set[tuple[int, ...]] = set()
    while len(vectors) < count:
        vectors.add(tuple(rng.randrange(2) for _ in range(width)))
    return sorted(vectors)


def _make_matrix_case(
    family: str,
    name: str,
    history_count: int,
    ground_truth_states: int,
    probe_count: int,
    seed: int,
    fallback_kind: str,
) -> CaseSpec:
    history_ids = tuple(range(history_count))
    probe_ids = tuple(range(probe_count))
    state_vectors = _unique_binary_vectors(ground_truth_states, probe_count, seed + 11)
    state_by_history = list(range(ground_truth_states)) * ((history_count + ground_truth_states - 1) // ground_truth_states)
    state_by_history = state_by_history[:history_count]
    random.Random(seed + 19).shuffle(state_by_history)
    responses = {
        (history_id, probe_id): state_vectors[state_by_history[history_id]][probe_id]
        for history_id in history_ids
        for probe_id in probe_ids
    }
    interface = FutureQueryInterface.create(name, history_ids, probe_ids, responses)
    discovery, validation, holdout = _split_probe_pool(
        probe_ids, seed + 23, discovery_count=max(1, probe_count // 2), validation_count=max(1, probe_count // 4)
    )
    return CaseSpec(
        family=family,
        name=name,
        interface=interface,
        discovery_probes=discovery,
        validation_probes=validation,
        holdout_probes=holdout,
        fallback={
            "kind": fallback_kind,
            "representation": "retain complete history records",
            "query_budget": history_count * (len(discovery) + len(validation)),
        },
        stop_config={
            "max_discovery_probe_evaluations": len(discovery),
            "max_validation_probe_evaluations": len(validation),
            "selection_batch_size": max(1, probe_count // 4),
            "validation_patience": 2,
            "stop_if_candidate_classes_reach_history_count": True,
        },
        raw_input={
            "kind": "deterministic_future_process",
            "family": family,
            "name": name,
            "history_count": history_count,
            "probe_count": probe_count,
            "seed": seed,
            "ground_truth_states_hidden_until_posthoc": True,
        },
    )


def _make_deceptive_case() -> CaseSpec:
    history_ids = tuple(range(64))
    probe_ids = tuple(range(12))
    responses: dict[tuple[int, int], int] = {}
    for history_id in history_ids:
        for probe_id in probe_ids:
            if probe_id < 4:
                response = 0
            elif probe_id == 4:
                response = history_id // 16
            elif probe_id == 5:
                response = (history_id // 8) % 2
            else:
                response = (history_id >> (probe_id - 6)) & 1
            responses[(history_id, probe_id)] = response
    interface = FutureQueryInterface.create("deceptive", history_ids, probe_ids, responses)
    return CaseSpec(
        family="E_deceptive",
        name="cheap_probes_hide_later_difference",
        interface=interface,
        discovery_probes=(0, 1, 2, 3),
        validation_probes=(4,),
        holdout_probes=tuple(range(5, 12)),
        fallback={
            "kind": "raw_history",
            "representation": "retain complete history records",
            "query_budget": 64 * 6,
        },
        stop_config={
            "max_discovery_probe_evaluations": 4,
            "max_validation_probe_evaluations": 1,
            "selection_batch_size": 2,
            "validation_patience": 1,
            "stop_if_candidate_classes_reach_history_count": True,
        },
        raw_input={
            "kind": "deceptive_future_process",
            "history_count": 64,
            "cheap_probe_ids": [0, 1, 2, 3],
            "validation_probe_ids": [4],
            "hidden_later_probe_ids": list(range(5, 12)),
            "ground_truth_definition_hidden_until_posthoc": True,
        },
    )


def _subset_case(kind: str, weights: tuple[int, ...], split: int, target: int, seed: int) -> CaseSpec:
    history_ids = tuple(range(1 << split))
    probe_ids = tuple(range(1 << (len(weights) - split)))
    prefix = weights[:split]
    suffix = weights[split:]

    def prefix_residual(history_id: int) -> int:
        return target - sum(prefix[index] for index in range(split) if history_id & (1 << index))

    def suffix_sum(probe_id: int) -> int:
        return sum(suffix[index] for index in range(len(suffix)) if probe_id & (1 << index))

    suffix_values = {probe_id: suffix_sum(probe_id) for probe_id in probe_ids}
    responses = {
        (history_id, probe_id): int(prefix_residual(history_id) == suffix_values[probe_id])
        for history_id in history_ids
        for probe_id in probe_ids
    }
    interface = FutureQueryInterface.create(f"subset_{kind}", history_ids, probe_ids, responses)
    discovery, validation, holdout = _split_probe_pool(
        probe_ids, seed, discovery_count=48, validation_count=48
    )
    return CaseSpec(
        family="C_subset_sum",
        name=kind,
        interface=interface,
        discovery_probes=discovery,
        validation_probes=validation,
        holdout_probes=holdout,
        fallback={
            "kind": "baseline_sampled_future_queries",
            "representation": "c99cfd1 sampled_future_queries baseline",
            "query_budget": len(history_ids) * 64,
        },
        stop_config={
            "max_discovery_probe_evaluations": 48,
            "max_validation_probe_evaluations": 16,
            "selection_batch_size": 8,
            "validation_patience": 2,
            "stop_if_candidate_classes_reach_history_count": True,
        },
        raw_input={
            "kind": "subset_sum",
            "name": kind,
            "weights": list(weights),
            "split": split,
            "target": target,
            "seed": seed,
            "oracle_suffix_sums_hidden_until_posthoc": True,
        },
    )


def _build_cases() -> list[CaseSpec]:
    cases: list[CaseSpec] = []
    for seed in (11, 17, 23):
        cases.append(_make_matrix_case("A_small_quotient", f"automaton_small_{seed}", 64, 4, 12, seed, "raw_history"))
    for states, seed in ((4, 101), (16, 107), (56, 113)):
        cases.append(_make_matrix_case("B_same_history_different_quotient", f"quotient_{states}", 64, states, 12, seed, "raw_history"))
    dense = tuple(1 << (index // 2) for index in range(16))
    superincreasing = tuple(1 << index for index in range(16))
    cases.append(_subset_case("dense_redundant", dense, 8, sum(dense) // 2, 20260823))
    cases.append(_subset_case("superincreasing", superincreasing, 8, sum(superincreasing) // 2, 20260829))
    cases.append(_make_matrix_case("D_near_maximal", "almost_every_history_distinct", 64, 64, 12, 211, "raw_history"))
    cases.append(_make_deceptive_case())
    return cases


def _phase_query(
    interface: FutureQueryInterface, phase: str
) -> Callable[[int, int], int]:
    return lambda history_id, probe_id: interface.query(history_id, probe_id, phase)


def _group_histories_by_assignment(assignment: dict[int, int]) -> dict[int, list[int]]:
    groups: dict[int, list[int]] = defaultdict(list)
    for history_id, class_id in assignment.items():
        groups[class_id].append(history_id)
    return {class_id: sorted(histories) for class_id, histories in sorted(groups.items())}


def _refine_partition(
    assignment: dict[int, int], histories: tuple[int, ...], probe_id: int, responses: dict[int, int]
) -> tuple[dict[int, int], dict[str, Any]]:
    groups = _group_histories_by_assignment(assignment)
    next_assignment: dict[int, int] = {}
    split_details: list[dict[str, Any]] = []
    next_class = 0
    for class_id, class_histories in groups.items():
        by_response: dict[int, list[int]] = defaultdict(list)
        for history_id in class_histories:
            by_response[responses[history_id]].append(history_id)
        if len(by_response) > 1:
            split_details.append(
                {
                    "class_before": class_id,
                    "histories_by_response": {
                        str(response): sorted(group) for response, group in sorted(by_response.items())
                    },
                }
            )
        for response, response_histories in sorted(by_response.items()):
            for history_id in response_histories:
                next_assignment[history_id] = next_class
            next_class += 1
    if set(next_assignment) != set(histories):
        raise AssertionError("partition refinement dropped or invented a history")
    return next_assignment, {
        "probe": probe_id,
        "classes_before": len(groups),
        "classes_after": next_class,
        "split_groups": len(split_details),
        "distinguished_history_count": sum(
            len(history_ids)
            for item in split_details
            for history_ids in item["histories_by_response"].values()
        ),
        "split_details": split_details,
        "assignment_digest": _digest(sorted(next_assignment.items())),
    }


def _evaluate_probe(
    histories: tuple[int, ...], probe_id: int, query: Callable[[int, int], int]
) -> dict[int, int]:
    return {history_id: query(history_id, probe_id) for history_id in histories}


def _select_probe(
    assignment: dict[int, int],
    histories: tuple[int, ...],
    candidates: list[int],
    query: Callable[[int, int], int],
) -> tuple[int | None, dict[int, dict[int, int]], list[dict[str, Any]]]:
    current_classes = len(set(assignment.values()))
    best_probe: int | None = None
    best_gain = -1
    cached: dict[int, dict[int, int]] = {}
    selection_audit: list[dict[str, Any]] = []
    for probe_id in sorted(candidates):
        responses = _evaluate_probe(histories, probe_id, query)
        cached[probe_id] = responses
        candidate_classes = len({(assignment[history_id], responses[history_id]) for history_id in histories})
        gain = candidate_classes - current_classes
        selection_audit.append(
            {
                "probe": probe_id,
                "classes_if_selected": candidate_classes,
                "split_gain_if_selected": gain,
            }
        )
        if gain > best_gain or (gain == best_gain and (best_probe is None or probe_id < best_probe)):
            best_probe = probe_id
            best_gain = gain
    return best_probe, cached, selection_audit


def run_partition_refinement(spec: CaseSpec) -> dict[str, Any]:
    histories = spec.interface.history_ids
    assignment = {history_id: 0 for history_id in histories}
    discovery_query = _phase_query(spec.interface, "DISCOVERY")
    validation_query = _phase_query(spec.interface, "VALIDATION")
    started = perf_counter()
    discovery_runtime_ms = 0.0
    validation_runtime_ms = 0.0
    discovery_audit: list[dict[str, Any]] = []
    validation_audit: list[dict[str, Any]] = []
    refinement_rounds = 0
    counterexamples_found = 0
    splits_per_round: list[int] = []
    peak_class_count = 1
    available_discovery = list(spec.discovery_probes)
    discovery_probe_evaluations = 0
    decision = "CONTINUE"
    decision_reason = "discovery_budget_not_exhausted"

    max_discovery = spec.stop_config["max_discovery_probe_evaluations"]
    max_validation = spec.stop_config["max_validation_probe_evaluations"]
    fallback_query_budget = spec.fallback["query_budget"]

    while available_discovery and discovery_probe_evaluations < max_discovery:
        if len(set(assignment.values())) == len(histories):
            decision = "STOP_NO_GAIN"
            decision_reason = "candidate_classes_reached_raw_history_count"
            break
        remaining_budget = max_discovery - discovery_probe_evaluations
        batch_size = min(spec.stop_config["selection_batch_size"], remaining_budget)
        candidates = available_discovery[:batch_size]
        round_started = perf_counter()
        selected_probe, cached, selection_audit = _select_probe(
            assignment, histories, candidates, discovery_query
        )
        discovery_runtime_ms += (perf_counter() - round_started) * 1000
        discovery_probe_evaluations += len(candidates)
        if selected_probe is None:
            decision = "UNKNOWN"
            decision_reason = "no_discovery_probe_available"
            break
        available_discovery.remove(selected_probe)
        best_gain = next(item["split_gain_if_selected"] for item in selection_audit if item["probe"] == selected_probe)
        if best_gain <= 0:
            for probe_id in candidates:
                if probe_id in available_discovery:
                    available_discovery.remove(probe_id)
            discovery_audit.append(
                {
                    "phase": "DISCOVERY",
                    "round": refinement_rounds + 1,
                    "selected_probe": selected_probe,
                    "selection_audit": selection_audit,
                    "split_gain": 0,
                    "classes_before": len(set(assignment.values())),
                    "classes_after": len(set(assignment.values())),
                    "note": "all remaining discovery probes failed to distinguish current classes",
                }
            )
            if not available_discovery:
                break
            continue
        assignment, refinement = _refine_partition(assignment, histories, selected_probe, cached[selected_probe])
        refinement_rounds += 1
        peak_class_count = max(peak_class_count, refinement["classes_after"])
        splits_per_round.append(refinement["split_groups"])
        discovery_audit.append(
            {
                "phase": "DISCOVERY",
                "round": refinement_rounds,
                "selected_probe": selected_probe,
                "selection_audit": selection_audit,
                "refinement": refinement,
            }
        )
        if refinement["classes_after"] == len(histories):
            decision = "STOP_NO_GAIN"
            decision_reason = "candidate_classes_reached_raw_history_count"
            break
        if spec.interface.phase_calls.get("DISCOVERY", 0) >= fallback_query_budget:
            decision = "STOP_NO_GAIN"
            decision_reason = "fallback_query_budget_reached"
            break

    if decision == "CONTINUE":
        validation_streak = 0
        for validation_index, probe_id in enumerate(spec.validation_probes[:max_validation], start=1):
            if len(set(assignment.values())) == len(histories):
                decision = "STOP_NO_GAIN"
                decision_reason = "candidate_classes_reached_raw_history_count"
                break
            round_started = perf_counter()
            responses = _evaluate_probe(histories, probe_id, validation_query)
            validation_runtime_ms += (perf_counter() - round_started) * 1000
            before_classes = len(set(assignment.values()))
            assignment, refinement = _refine_partition(assignment, histories, probe_id, responses)
            after_classes = refinement["classes_after"]
            if after_classes > before_classes:
                counterexamples_found += refinement["split_groups"]
                validation_streak = 0
                refinement_rounds += 1
                peak_class_count = max(peak_class_count, after_classes)
                splits_per_round.append(refinement["split_groups"])
            else:
                validation_streak += 1
            validation_audit.append(
                {
                    "phase": "VALIDATION",
                    "round": refinement_rounds,
                    "validation_index": validation_index,
                    "refinement": refinement,
                    "validation_streak_without_split": validation_streak,
                }
            )
            if after_classes == len(histories):
                decision = "STOP_NO_GAIN"
                decision_reason = "candidate_classes_reached_raw_history_count"
                break
            if spec.interface.phase_calls.get("DISCOVERY", 0) + spec.interface.phase_calls.get("VALIDATION", 0) >= fallback_query_budget:
                decision = "STOP_NO_GAIN"
                decision_reason = "fallback_query_budget_reached"
                break
            if validation_streak >= spec.stop_config["validation_patience"]:
                decision = "FREEZE"
                decision_reason = "validation_patience_without_new_split"
                break
        if decision == "CONTINUE":
            decision = "FREEZE" if spec.validation_probes else "UNKNOWN"
            decision_reason = "validation_budget_exhausted" if spec.validation_probes else "no_validation_pool"

    if decision == "CONTINUE":
        decision = "FREEZE"
        decision_reason = "discovery_and_validation_pools_exhausted"

    total_discovery_validation_queries = spec.interface.phase_calls.get("DISCOVERY", 0) + spec.interface.phase_calls.get("VALIDATION", 0)
    if total_discovery_validation_queries > fallback_query_budget and decision != "STOP_NO_GAIN":
        decision = "STOP_NO_GAIN"
        decision_reason = "fallback_query_budget_reached"

    frozen = {
        "assignment": dict(assignment),
        "class_count": len(set(assignment.values())),
        "decision": decision,
        "decision_reason": decision_reason,
        "refinement_rounds": refinement_rounds,
        "stop_config": dict(spec.stop_config),
        "fallback": dict(spec.fallback),
        "discovery_probes": list(spec.discovery_probes),
        "validation_probes": list(spec.validation_probes),
        "sealed_holdout_probes": list(spec.holdout_probes),
        "assignment_digest": _digest(sorted(assignment.items())),
        "parameters_digest": _digest(
            {
                "stop_config": spec.stop_config,
                "fallback": spec.fallback,
                "discovery_probes": spec.discovery_probes,
                "validation_probes": spec.validation_probes,
                "sealed_holdout_probes": spec.holdout_probes,
            }
        ),
    }
    return {
        "frozen": frozen,
        "discovery_audit": discovery_audit,
        "validation_audit": validation_audit,
        "refinement_rounds": refinement_rounds,
        "counterexamples_found": counterexamples_found,
        "splits_per_round": splits_per_round,
        "peak_candidate_class_count": peak_class_count,
        "discovery_runtime_ms": round(discovery_runtime_ms, 6),
        "validation_runtime_ms": round(validation_runtime_ms, 6),
        "total_refinement_runtime_ms": round((perf_counter() - started) * 1000, 6),
        "discovery_query_count": spec.interface.phase_calls.get("DISCOVERY", 0),
        "validation_query_count": spec.interface.phase_calls.get("VALIDATION", 0),
        "oracle_used_during_discovery": False,
        "sealed_holdout_touched_before_freeze": False,
    }


def _partition_comparison(
    assignment: dict[int, int], signatures: dict[int, tuple[Any, ...]]
) -> dict[str, Any]:
    candidate_groups = _group_histories_by_assignment(assignment)
    truth_groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    for history_id, signature in signatures.items():
        truth_groups[signature].append(history_id)
    false_merge_groups = 0
    false_merge_pairs = 0
    rejected_merges = 0
    for histories in candidate_groups.values():
        signature_groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
        for history_id in histories:
            signature_groups[signatures[history_id]].append(history_id)
        if len(signature_groups) > 1:
            false_merge_groups += 1
            false_merge_pairs += _pair_count(len(histories)) - sum(
                _pair_count(len(group)) for group in signature_groups.values()
            )
            rejected_merges += len(histories) - len(signature_groups)
    false_split_groups = 0
    false_split_pairs = 0
    for histories in truth_groups.values():
        candidate_classes = {assignment[history_id] for history_id in histories}
        if len(candidate_classes) > 1:
            false_split_groups += 1
            false_split_pairs += _pair_count(len(histories)) - sum(
                _pair_count(sum(1 for history_id in histories if assignment[history_id] == class_id))
                for class_id in candidate_classes
            )
    pair_denominator = _pair_count(len(assignment))
    return {
        "false_merge_groups": false_merge_groups,
        "false_merge_pairs": false_merge_pairs,
        "false_split_groups": false_split_groups,
        "false_split_pairs": false_split_pairs,
        "rejected_merges": rejected_merges,
        "pair_denominator": pair_denominator,
        "pair_error": round((false_merge_pairs + false_split_pairs) / pair_denominator, 6) if pair_denominator else None,
    }


def _signatures_from_queries(
    interface: FutureQueryInterface,
    histories: tuple[int, ...],
    probes: tuple[int, ...],
    phase: str,
) -> dict[int, tuple[Any, ...]]:
    query = _phase_query(interface, phase)
    return {
        history_id: tuple(query(history_id, probe_id) for probe_id in probes)
        for history_id in histories
    }


def _build_oracle(
    interface: FutureQueryInterface, histories: tuple[int, ...], probes: tuple[int, ...]
) -> dict[str, Any]:
    signatures = _signatures_from_queries(interface, histories, probes, "GROUND_TRUTH/ORACLE")
    classes = len(set(signatures.values()))
    return {
        "label": "GROUND_TRUTH/ORACLE",
        "signatures": signatures,
        "ground_truth_class_count": classes,
        "oracle_query_count": len(histories) * len(probes),
        "oracle_construction_cost": {
            "future_query_evaluations": len(histories) * len(probes),
            "signature_entries": len(histories),
            "probe_count": len(probes),
        },
        "used_for_decision": False,
    }


def _representation_metrics(assignment: dict[int, int]) -> dict[str, int]:
    sorted_assignment = sorted(assignment.items())
    groups = _group_histories_by_assignment(assignment)
    return {
        "representation_bytes": _json_bytes(sorted_assignment),
        "class_assignment_bytes": _json_bytes(sorted_assignment),
        "candidate_class_record_bytes": _json_bytes(groups),
    }


def _run_fixed_sampled_baseline(spec: CaseSpec) -> dict[str, Any]:
    interface = spec.interface.clone("/sampled-baseline")
    histories = interface.history_ids
    rng = random.Random(SAMPLED_BASELINE_SEED)
    sampled_probes = tuple(sorted(rng.sample(list(interface.probe_ids), min(SAMPLED_BASELINE_COUNT, len(interface.probe_ids)))))
    signatures = _signatures_from_queries(interface, histories, sampled_probes, "BASELINE_DISCOVERY")
    signature_to_class = {signature: index for index, signature in enumerate(sorted(set(signatures.values()), key=str))}
    assignment = {history_id: signature_to_class[signature] for history_id, signature in signatures.items()}
    sampled_set = set(sampled_probes)
    baseline_holdout_probes = tuple(probe for probe in spec.holdout_probes if probe not in sampled_set)
    holdout_signatures = _signatures_from_queries(interface, histories, baseline_holdout_probes, "BASELINE_SEALED_HOLDOUT")
    holdout_comparison = _partition_comparison(assignment, holdout_signatures)
    oracle = _build_oracle(interface, histories, interface.probe_ids)
    oracle_comparison = _partition_comparison(assignment, oracle["signatures"])
    representation = _representation_metrics(assignment)
    valid_merges = len(histories) - len(set(assignment.values())) - holdout_comparison["rejected_merges"]
    query_count = interface.phase_calls.get("BASELINE_DISCOVERY", 0)
    if oracle["ground_truth_class_count"] >= len(histories):
        outcome_label = "NO_USEFUL_COMPRESSION"
    elif (
        len(set(assignment.values())) == oracle["ground_truth_class_count"]
        and oracle_comparison["false_merge_pairs"] == 0
        and oracle_comparison["false_split_pairs"] == 0
    ):
        outcome_label = "RECOVERED_QUOTIENT"
    else:
        outcome_label = "PARTIAL_OR_UNRESOLVED_RECOVERY"
    return {
        "method": "sampled_future_queries_baseline_c99fd1",
        "sampled_probe_ids": list(sampled_probes),
        "sealed_holdout_probe_ids": list(baseline_holdout_probes),
        "raw_history_count": len(histories),
        "discovered_class_count": len(set(assignment.values())),
        "ground_truth_class_count": oracle["ground_truth_class_count"],
        "discovery_queries": query_count,
        "validation_queries": 0,
        "sealed_holdout_queries": interface.phase_calls.get("BASELINE_SEALED_HOLDOUT", 0),
        "refinement_rounds": 0,
        "counterexamples_found": 0,
        "splits_per_round": [],
        "false_merge_groups": holdout_comparison["false_merge_groups"],
        "false_merge_pairs": holdout_comparison["false_merge_pairs"],
        "false_split_groups": holdout_comparison["false_split_groups"],
        "false_split_pairs": holdout_comparison["false_split_pairs"],
        "sealed_holdout_error": holdout_comparison,
        "posthoc_oracle_comparison": oracle_comparison,
        "outcome_label": outcome_label,
        "representation_bytes": representation["representation_bytes"],
        "class_assignment_bytes": representation["class_assignment_bytes"],
        "query_runtime": {
            "discovery_ms": round(interface.phase_runtime_ms.get("BASELINE_DISCOVERY", 0.0), 6),
            "sealed_holdout_ms": round(interface.phase_runtime_ms.get("BASELINE_SEALED_HOLDOUT", 0.0), 6),
            "oracle_ms": round(interface.phase_runtime_ms.get("GROUND_TRUTH/ORACLE", 0.0), 6),
            "machine_dependent": True,
        },
        "discovery_runtime": None,
        "peak_candidate_class_count": len(set(assignment.values())),
        "peak_state_count": len(set(signatures.values())),
        "oracle_query_count": oracle["oracle_query_count"],
        "oracle_construction_cost": oracle["oracle_construction_cost"],
        "baseline_raw_cost": {
            "history_records": len(histories),
            "representation_bytes": _json_bytes(list(histories)),
            "future_queries": None,
        },
        "valid_history_merges": max(valid_merges, 0),
        "merges_rejected_in_sealed_holdout": holdout_comparison["rejected_merges"],
        "discovery_queries_per_valid_history_merge": round(query_count / valid_merges, 6) if valid_merges > 0 else None,
        "discovery_validation_queries_per_valid_history_merge": round(query_count / valid_merges, 6) if valid_merges > 0 else None,
        "oracle_queries_per_discovery_validation_query": round(oracle["oracle_query_count"] / query_count, 6) if query_count > 0 else None,
        "stop_state": "FROZEN_BASELINE",
        "fallback": spec.fallback,
        "oracle_used_during_discovery": False,
        "scope": "baseline only; oracle fields are post-hoc",
    }


def run_case(spec: CaseSpec) -> dict[str, Any]:
    refinement = run_partition_refinement(spec)
    histories = spec.interface.history_ids
    assignment = refinement["frozen"]["assignment"]
    sealed_signatures = _signatures_from_queries(
        spec.interface, histories, spec.holdout_probes, "SEALED_HOLDOUT"
    )
    sealed_comparison = _partition_comparison(assignment, sealed_signatures)
    oracle = _build_oracle(spec.interface, histories, spec.interface.probe_ids)
    oracle_comparison = _partition_comparison(assignment, oracle["signatures"])
    representation = _representation_metrics(assignment)
    discovered_class_count = len(set(assignment.values()))
    valid_merges = len(histories) - discovered_class_count - sealed_comparison["rejected_merges"]
    discovery_validation_queries = refinement["discovery_query_count"] + refinement["validation_query_count"]
    phase_calls = dict(spec.interface.phase_calls)
    raw_representation_bytes = _json_bytes(list(histories))
    if spec.family == "D_near_maximal" and oracle["ground_truth_class_count"] >= len(histories):
        outcome_label = "NO_USEFUL_COMPRESSION"
    elif spec.family == "E_deceptive":
        outcome_label = "DECEPTIVE_FALSE_MERGE_REMAINS"
    elif (
        discovered_class_count == oracle["ground_truth_class_count"]
        and oracle_comparison["false_merge_pairs"] == 0
        and oracle_comparison["false_split_pairs"] == 0
    ):
        outcome_label = "RECOVERED_QUOTIENT"
    elif oracle_comparison["false_merge_pairs"] > 0 or oracle_comparison["false_split_pairs"] > 0:
        outcome_label = "PARTIAL_OR_UNRESOLVED_RECOVERY"
    else:
        outcome_label = "UNKNOWN"
    output = {
        "family": spec.family,
        "case": spec.name,
        "raw_input_digest": _digest(spec.raw_input),
        "raw_history_count": len(histories),
        "discovered_class_count": discovered_class_count,
        "ground_truth_class_count": oracle["ground_truth_class_count"],
        "discovery_queries": refinement["discovery_query_count"],
        "validation_queries": refinement["validation_query_count"],
        "sealed_holdout_queries": phase_calls.get("SEALED_HOLDOUT", 0),
        "refinement_rounds": refinement["refinement_rounds"],
        "counterexamples_found": refinement["counterexamples_found"],
        "splits_per_round": refinement["splits_per_round"],
        "false_merge_groups": sealed_comparison["false_merge_groups"],
        "false_merge_pairs": sealed_comparison["false_merge_pairs"],
        "false_split_groups": sealed_comparison["false_split_groups"],
        "false_split_pairs": sealed_comparison["false_split_pairs"],
        "sealed_holdout_error": sealed_comparison,
        "posthoc_oracle_comparison": oracle_comparison,
        "outcome_label": outcome_label,
        "representation_bytes": representation["representation_bytes"],
        "class_assignment_bytes": representation["class_assignment_bytes"],
        "query_runtime": {
            "discovery_ms": round(spec.interface.phase_runtime_ms.get("DISCOVERY", 0.0), 6),
            "validation_ms": round(spec.interface.phase_runtime_ms.get("VALIDATION", 0.0), 6),
            "sealed_holdout_ms": round(spec.interface.phase_runtime_ms.get("SEALED_HOLDOUT", 0.0), 6),
            "oracle_ms": round(spec.interface.phase_runtime_ms.get("GROUND_TRUTH/ORACLE", 0.0), 6),
            "machine_dependent": True,
        },
        "discovery_runtime": {
            "discovery_ms": refinement["discovery_runtime_ms"],
            "validation_ms": refinement["validation_runtime_ms"],
            "total_refinement_ms": refinement["total_refinement_runtime_ms"],
            "machine_dependent": True,
        },
        "peak_candidate_class_count": refinement["peak_candidate_class_count"],
        "peak_state_count": refinement["peak_candidate_class_count"],
        "oracle_query_count": oracle["oracle_query_count"],
        "oracle_construction_cost": oracle["oracle_construction_cost"],
        "baseline_raw_cost": {
            "history_records": len(histories),
            "representation_bytes": raw_representation_bytes,
            "future_queries": None,
        },
        "valid_history_merges": max(valid_merges, 0),
        "merges_rejected_in_sealed_holdout": sealed_comparison["rejected_merges"],
        "discovery_queries_per_valid_history_merge": round(
            refinement["discovery_query_count"] / valid_merges, 6
        ) if valid_merges > 0 else None,
        "discovery_validation_queries_per_valid_history_merge": round(
            discovery_validation_queries / valid_merges, 6
        ) if valid_merges > 0 else None,
        "oracle_queries_per_discovery_validation_query": round(
            oracle["oracle_query_count"] / discovery_validation_queries, 6
        ) if discovery_validation_queries > 0 else None,
        "stop_state": refinement["frozen"]["decision"],
        "stop_reason": refinement["frozen"]["decision_reason"],
        "decision_before_oracle": refinement["frozen"]["decision"],
        "decision_after_oracle": refinement["frozen"]["decision"],
        "fallback": spec.fallback,
        "stop_rule": spec.stop_config,
        "frozen_parameters_digest": refinement["frozen"]["parameters_digest"],
        "frozen_parameters_digest_before_sealed_holdout": refinement["frozen"]["parameters_digest"],
        "parameters_digest_after_sealed_holdout": refinement["frozen"]["parameters_digest"],
        "frozen_assignment_digest": refinement["frozen"]["assignment_digest"],
        "discovery_audit": refinement["discovery_audit"],
        "validation_audit": refinement["validation_audit"],
        "phase_calls": phase_calls,
        "phase_sequence": list(spec.interface.phase_sequence),
        "oracle_used_during_discovery": refinement["oracle_used_during_discovery"],
        "sealed_holdout_touched_before_freeze": refinement["sealed_holdout_touched_before_freeze"],
        "ground_truth_used_for_decision": oracle["used_for_decision"],
        "resource_policy": {
            "scalar_collapsed": False,
            "heterogeneous_units_kept_separate": True,
            "lift_gain_declared": False,
        },
    }
    if spec.family == "C_subset_sum":
        output["baseline_sampled_future_queries"] = _run_fixed_sampled_baseline(spec)
    return output


def run_future_equivalence_audit() -> dict[str, Any]:
    cases = _build_cases()
    results = [run_case(case) for case in cases]
    return {
        "protocol": PROTOCOL,
        "parent_commit": PARENT_COMMIT,
        "scope": "PiPi-42 research branch; c99cfd1 audit v0 remains unchanged",
        "preregistered_prediction": {
            "status": "PREREGISTERED_BEFORE_RESULTS",
            "text": PREREGISTERED_PREDICTIONS,
        },
        "evidence_levels": {
            "DISCOVERY": "adaptive probes may split candidate classes",
            "VALIDATION_COUNTEREXAMPLE": "separate probes may refine before freeze",
            "SEALED_HOLDOUT": "post-freeze audit only; cannot change state or parameters",
            "GROUND_TRUTH_ORACLE": "post-hoc exhaustive audit only; cannot change any decision",
        },
        "metrics_policy": {
            "resource_vector": True,
            "lift_gain_declared": False,
            "unknown_values_are_null": True,
            "machine_dependent_fields": ["query_runtime", "discovery_runtime"],
            "posthoc_oracle_fields": ["ground_truth_class_count", "oracle_query_count", "oracle_construction_cost", "posthoc_oracle_comparison"],
        },
        "cases": results,
        "summary": {
            "case_count": len(results),
            "stop_states": {
                state: sum(1 for result in results if result["stop_state"] == state)
                for state in sorted({result["stop_state"] for result in results})
            },
            "baseline_false_merge_cases": sum(
                1
                for result in results
                if "baseline_sampled_future_queries" in result
                and result["baseline_sampled_future_queries"]["false_merge_pairs"] > 0
            ),
            "refinement_false_merge_cases": sum(
                1 for result in results if result["false_merge_pairs"] > 0
            ),
            "outcome_labels": {
                label: sum(1 for result in results if result["outcome_label"] == label)
                for label in sorted({result["outcome_label"] for result in results})
            },
            "no_useful_compression_cases": sum(
                1 for result in results if result["outcome_label"] == "NO_USEFUL_COMPRESSION"
            ),
            "oracle_not_much_more_expensive_cases": sum(
                1
                for result in results
                if result["oracle_queries_per_discovery_validation_query"] is not None
                and result["oracle_queries_per_discovery_validation_query"] < 2
            ),
        },
        "scope_declarations": {
            "main_modified": False,
            "phase5_started": False,
            "pr_not_opened": True,
            "note": "branch-scope declarations, not empirical results",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PiPi-42 future-equivalence discovery")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "results" / "future-equivalence-discovery.json",
    )
    args = parser.parse_args(argv)
    result = run_future_equivalence_audit()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("cases:", result["summary"]["case_count"])
    print("stop_states:", result["summary"]["stop_states"])
    print("baseline_false_merge_cases:", result["summary"]["baseline_false_merge_cases"])
    print("refinement_false_merge_cases:", result["summary"]["refinement_false_merge_cases"])
    print("pr:", "not opened")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
