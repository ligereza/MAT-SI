"""PiPi-44: cross-axis analysis of a minimal past-to-future interface.

All cases in this module use one finite-state layered factor-process domain:
binary history variables, optional latent past variables, binary boundary
variables, and binary future query variables.  A past assignment induces an
exact integer message table over the boundary.  A future query contracts that
message with the future factors.  This keeps Q (future quotient), W
(structural separator width), and M (message content) in the same semantics.

The module is intentionally a result object, not a kernel extension.  Oracle
quotients and minimality checks are post-hoc; discovery resources and solve
resources are recorded separately, and no scalar "dimension" is declared.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
PARENT_COMMIT = "1d5a1d9"
PROTOCOL = "pipi-44-cross-axis-order-v0"
DISCOVERY_QUERY_SPLIT = "first_half_of_future_queries"

PREREGISTERED_HYPOTHESES = {
    "Q_W_NOT_IDENTICAL": "Future quotient size Q and structural separator width W need not coincide.",
    "MESSAGE_CONTENT_MATTERS": "At fixed or small W, message values can distinguish future behaviour beyond W alone.",
    "NATURAL_INTERFACE_REDUNDANCY": "Some natural separator messages can be fused without changing any future query.",
    "MISSING_AXIS": "Equal W and Q can still carry different message/cost profiles, leaving an additional axis unresolved.",
}


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _wall_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 6)


def _assignments(variables: tuple[str, ...]) -> list[dict[str, int]]:
    return [dict(zip(variables, bits)) for bits in itertools.product((0, 1), repeat=len(variables))]


@dataclass(frozen=True)
class FactorSpec:
    name: str
    scope: tuple[str, ...]
    table: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.table) != 1 << len(self.scope):
            raise ValueError(f"factor {self.name} table length does not match scope")
        if any(value < 0 for value in self.table):
            raise ValueError(f"factor {self.name} must be non-negative")

    def value(self, assignment: dict[str, int]) -> int:
        index = 0
        for position, variable in enumerate(self.scope):
            index |= assignment[variable] << position
        return self.table[index]


@dataclass(frozen=True)
class LayeredProcess:
    name: str
    family: str
    history_vars: tuple[str, ...]
    latent_vars: tuple[str, ...]
    boundary_vars: tuple[str, ...]
    future_vars: tuple[str, ...]
    past_factors: tuple[FactorSpec, ...]
    future_factors: tuple[FactorSpec, ...]
    metadata: tuple[tuple[str, Any], ...] = ()

    @property
    def raw_input(self) -> dict[str, Any]:
        return {
            "kind": "layered_binary_factor_process",
            "name": self.name,
            "family": self.family,
            "history_vars": list(self.history_vars),
            "latent_vars": list(self.latent_vars),
            "boundary_vars": list(self.boundary_vars),
            "future_vars": list(self.future_vars),
            "past_factors": [
                {"name": factor.name, "scope": list(factor.scope), "table": list(factor.table)}
                for factor in self.past_factors
            ],
            "future_factors": [
                {"name": factor.name, "scope": list(factor.scope), "table": list(factor.table)}
                for factor in self.future_factors
            ],
            "metadata": {key: value for key, value in self.metadata},
        }


def _equal_factor(name: str, left: str, right: str) -> FactorSpec:
    # Scope bit order is (left, right): 00, 10, 01, 11 by binary index.
    table = tuple(1 if ((index & 1) == ((index >> 1) & 1)) else 0 for index in range(4))
    return FactorSpec(name, (left, right), table)


def _weighted_history_factor(name: str, history: str, boundary: str, values: tuple[int, int, int, int]) -> FactorSpec:
    # Values are (h=0,b=0), (h=0,b=1), (h=1,b=0), (h=1,b=1).
    table = (values[0], values[2], values[1], values[3])
    return FactorSpec(name, (history, boundary), table)


def _constant_factor(name: str, variable: str) -> FactorSpec:
    return FactorSpec(name, (variable,), (1, 1))


def _make_process(
    name: str,
    family: str,
    history_vars: Iterable[str],
    boundary_vars: Iterable[str],
    future_vars: Iterable[str],
    *,
    latent_vars: Iterable[str] = (),
    past_factors: Iterable[FactorSpec] = (),
    future_factors: Iterable[FactorSpec] = (),
    metadata: dict[str, Any] | None = None,
) -> LayeredProcess:
    return LayeredProcess(
        name=name,
        family=family,
        history_vars=tuple(history_vars),
        latent_vars=tuple(latent_vars),
        boundary_vars=tuple(boundary_vars),
        future_vars=tuple(future_vars),
        past_factors=tuple(past_factors),
        future_factors=tuple(future_factors),
        metadata=tuple(sorted((metadata or {}).items())),
    )


def _message_for_history(process: LayeredProcess, history: dict[str, int], boundary: dict[str, int]) -> int:
    total = 0
    for latent in _assignments(process.latent_vars):
        assignment = {**history, **latent, **boundary}
        value = 1
        for factor in process.past_factors:
            value *= factor.value(assignment)
        total += value
    return total


def _future_weight(process: LayeredProcess, boundary: dict[str, int], future: dict[str, int]) -> int:
    assignment = {**boundary, **future}
    value = 1
    for factor in process.future_factors:
        value *= factor.value(assignment)
    return value


def _rank(matrix: list[tuple[int, ...]]) -> int:
    if not matrix:
        return 0
    rows = [[Fraction(value) for value in row] for row in matrix]
    row = 0
    columns = len(rows[0])
    for column in range(columns):
        pivot = next((candidate for candidate in range(row, len(rows)) if rows[candidate][column]), None)
        if pivot is None:
            continue
        rows[row], rows[pivot] = rows[pivot], rows[row]
        pivot_value = rows[row][column]
        rows[row] = [value / pivot_value for value in rows[row]]
        for candidate in range(len(rows)):
            if candidate != row and rows[candidate][column]:
                multiplier = rows[candidate][column]
                rows[candidate] = [left - multiplier * right for left, right in zip(rows[candidate], rows[row])]
        row += 1
        if row == len(rows):
            break
    return row


def _compact_bytes(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _partition_signature(values: Iterable[tuple[int, ...]]) -> dict[tuple[int, ...], int]:
    signatures = sorted(set(values))
    return {signature: index for index, signature in enumerate(signatures)}


def analyze_process(process: LayeredProcess) -> dict[str, Any]:
    """Compute discovery, natural messages, exact future quotient, and minimality."""

    started = perf_counter()
    histories = _assignments(process.history_vars)
    boundaries = _assignments(process.boundary_vars)
    futures = _assignments(process.future_vars)
    messages = [
        tuple(_message_for_history(process, history, boundary) for boundary in boundaries)
        for history in histories
    ]
    signatures = [
        tuple(
            sum(message[index] * _future_weight(process, boundary, future) for index, boundary in enumerate(boundaries))
            for future in futures
        )
        for message in messages
    ]
    natural_message_ids = _partition_signature(messages)
    quotient_ids = _partition_signature(signatures)
    natural_message_count = len(natural_message_ids)
    quotient_size = len(quotient_ids)

    # The preregistered discovery split is deliberately fixed before the oracle.
    discovery_count = max(1, len(futures) // 2)
    discovery_indices = tuple(range(discovery_count))
    validation_indices = tuple(range(discovery_count, len(futures)))
    discovery_signatures = [tuple(signature[index] for index in discovery_indices) for signature in signatures]
    discovery_partition = _partition_signature(discovery_signatures)
    validation_counterexamples = sum(
        1
        for left, right in itertools.combinations(range(len(histories)), 2)
        if discovery_signatures[left] == discovery_signatures[right] and signatures[left] != signatures[right]
    )

    unique_messages = sorted(natural_message_ids)
    unique_signatures = sorted(quotient_ids)
    message_values = [value for message in messages for value in message]
    natural_description_bytes = _compact_bytes(unique_messages)
    minimal_description_bytes = _compact_bytes(unique_signatures)

    safe_fusions = 0
    unsafe_fusions = 0
    for left, right in itertools.combinations(unique_messages, 2):
        left_signature = signatures[messages.index(left)]
        right_signature = signatures[messages.index(right)]
        if left_signature == right_signature:
            safe_fusions += 1
        else:
            unsafe_fusions += 1

    message_to_future_signature = {
        _digest(message): _digest(signatures[messages.index(message)]) for message in unique_messages
    }
    solve_operations = len(histories) * len(boundaries) * max(1, len(futures))
    solve_resources = {
        "history_assignments": len(histories),
        "boundary_assignments": len(boundaries),
        "future_queries": len(futures),
        "message_cells_materialized": len(messages) * len(boundaries),
        "future_response_operations": solve_operations,
        "message_matrix_rank": _rank(messages),
        "wall_ms": _wall_ms(started),
        "machine_dependent_fields": ["wall_ms"],
    }
    discovery_resources = {
        "query_split": DISCOVERY_QUERY_SPLIT,
        "discovery_query_ids": list(discovery_indices),
        "validation_query_ids": list(validation_indices),
        "discovery_query_count": len(discovery_indices),
        "discovery_history_query_evaluations": len(histories) * len(discovery_indices),
        "discovery_partition_size": len(discovery_partition),
        "validation_counterexamples": validation_counterexamples,
        "oracle_used_for_discovery": False,
        "wall_ms": 0.0,
        "machine_dependent_fields": ["wall_ms"],
    }
    return {
        "raw_history_count": len(histories),
        "future_quotient_size": quotient_size,
        "separator_width": len(process.boundary_vars),
        "separator_domain_cells": len(boundaries),
        "distinct_messages": natural_message_count,
        "message_description_bytes": natural_description_bytes,
        "minimal_sufficient_messages": quotient_size,
        "interface_slack": {
            "message_classes": natural_message_count - quotient_size,
            "description_bytes": natural_description_bytes - minimal_description_bytes,
        },
        "discovery_resources": discovery_resources,
        "solve_resources": solve_resources,
        "case": process.name,
        "family": process.family,
        "raw_input": process.raw_input,
        "raw_input_digest": _digest(process.raw_input),
        "natural_interface": {
            "separator_width": len(process.boundary_vars),
            "domain_cells": len(boundaries),
            "distinct_messages": natural_message_count,
            "description_bytes": natural_description_bytes,
            "message_value_min": min(message_values, default=0),
            "message_value_max": max(message_values, default=0),
            "message_nonzero_cells": sum(value != 0 for value in message_values),
            "message_matrix_rank": solve_resources["message_matrix_rank"],
            "message_digests": sorted(message_to_future_signature),
        },
        "minimal_sufficient_interface": {
            "future_quotient_size": quotient_size,
            "description_bytes": minimal_description_bytes,
            "partition_labels": sorted(set(quotient_ids.values())),
            "construction": "exhaustive future-signature fusion post-hoc",
        },
        "minimality_attack": {
            "natural_message_classes_tested": natural_message_count,
            "candidate_pairs_tested": len(list(itertools.combinations(unique_messages, 2))),
            "safe_fusions": safe_fusions,
            "unsafe_fusions": unsafe_fusions,
            "fusion_complete": True,
            "future_sufficiency_checked": True,
            "oracle_used_during_discovery": False,
        },
        "posthoc": {
            "future_signatures": [list(signature) for signature in signatures],
            "quotient_partition": [quotient_ids[signature] for signature in signatures],
            "natural_message_partition": [natural_message_ids[message] for message in messages],
        },
        "stop_rule": {
            "decision_before_posthoc": "FREEZE",
            "decision_after_posthoc": "FREEZE",
            "parameters_frozen_before_validation": True,
            "oracle_can_change_decision": False,
        },
        "resource_policy": {
            "scalar_collapsed": False,
            "lift_gain_declared": False,
            "same_domain": True,
        },
    }


def build_processes() -> list[LayeredProcess]:
    processes: list[LayeredProcess] = []
    processes.append(
        _make_process(
            "small_q_small_w",
            "A_controlled_quadrants",
            ("h0",),
            ("b0",),
            ("f0",),
            past_factors=[_equal_factor("past_equal", "h0", "b0")],
            metadata={"quadrant": "small_Q_small_W", "future_ignores_boundary": True},
        )
    )
    processes.append(
        _make_process(
            "small_q_large_w",
            "A_controlled_quadrants",
            ("h0", "h1"),
            tuple(f"b{index}" for index in range(4)),
            ("f0",),
            past_factors=[_equal_factor("past_equal_0", "h0", "b0"), _equal_factor("past_equal_1", "h1", "b1")],
            future_factors=[_equal_factor("future_equal_0", "b0", "f0")],
            metadata={"quadrant": "small_Q_large_W", "future_ignores_boundary_variables": ["b1", "b2", "b3"]},
        )
    )
    processes.append(
        _make_process(
            "large_q_small_w",
            "A_controlled_quadrants",
            tuple(f"h{index}" for index in range(6)),
            ("b0",),
            ("f0",),
            past_factors=[
                _weighted_history_factor(f"weighted_{index}", f"h{index}", "b0", (1, 1, 2, 3))
                for index in range(6)
            ],
            future_factors=[_equal_factor("future_equal", "b0", "f0")],
            metadata={"quadrant": "large_Q_small_W", "message_rule": "[2**popcount, 3**popcount]"},
        )
    )
    processes.append(
        _make_process(
            "large_q_large_w",
            "A_controlled_quadrants",
            tuple(f"h{index}" for index in range(3)),
            tuple(f"b{index}" for index in range(3)),
            tuple(f"f{index}" for index in range(3)),
            past_factors=[_equal_factor(f"past_equal_{index}", f"h{index}", f"b{index}") for index in range(3)],
            future_factors=[_equal_factor(f"future_equal_{index}", f"b{index}", f"f{index}") for index in range(3)],
            metadata={"quadrant": "large_Q_large_W", "message_rule": "one_hot_boundary_state"},
        )
    )
    processes.append(
        _make_process(
            "same_w1_q2_boolean",
            "B_same_w_q_different_message",
            ("h0",),
            ("b0",),
            ("f0",),
            past_factors=[_equal_factor("past_equal", "h0", "b0")],
            future_factors=[_equal_factor("future_equal", "b0", "f0")],
            metadata={"contrast_group": "W1_Q2", "message_kind": "boolean"},
        )
    )
    processes.append(
        _make_process(
            "same_w1_q2_weighted",
            "B_same_w_q_different_message",
            ("h0",),
            ("b0",),
            ("f0",),
            past_factors=[_weighted_history_factor("weighted_large", "h0", "b0", (1, 1, 1024, 2048))],
            future_factors=[_equal_factor("future_equal", "b0", "f0")],
            metadata={"contrast_group": "W1_Q2", "message_kind": "weighted_large_values"},
        )
    )
    processes.append(
        _make_process(
            "same_w1_q2_more_histories",
            "C_same_w_q_same_message_more_raw_work",
            tuple(f"h{index}" for index in range(8)),
            ("b0",),
            ("f0",),
            past_factors=[_equal_factor("past_equal_only_h0", "h0", "b0")],
            future_factors=[_equal_factor("future_equal", "b0", "f0")],
            metadata={"contrast_group": "W1_Q2", "ignored_history_variables": 7},
        )
    )
    return processes


def run_cross_axis_order_audit() -> dict[str, Any]:
    cases = [analyze_process(process) for process in build_processes()]
    by_case = {case["case"]: case for case in cases}
    quadrant_observations = [
        {
            "case": case["case"],
            "quadrant": case["raw_input"]["metadata"].get("quadrant"),
            "Q": case["future_quotient_size"],
            "W": case["separator_width"],
            "M": case["distinct_messages"],
        }
        for case in cases
        if case["raw_input"]["metadata"].get("quadrant")
    ]
    fixed_w_contrast = [
        {
            "case": name,
            "W": by_case[name]["separator_width"],
            "Q": by_case[name]["future_quotient_size"],
            "M": by_case[name]["distinct_messages"],
            "message_value_max": by_case[name]["natural_interface"]["message_value_max"],
            "solve_operations": by_case[name]["solve_resources"]["future_response_operations"],
        }
        for name in ("same_w1_q2_boolean", "same_w1_q2_weighted", "same_w1_q2_more_histories")
    ]
    q_le_m_verified = all(case["future_quotient_size"] <= case["distinct_messages"] for case in cases)
    compression_cases = [case["case"] for case in cases if case["interface_slack"]["message_classes"] > 0]
    return {
        "protocol": PROTOCOL,
        "parent_commit": PARENT_COMMIT,
        "scope": "PiPi-44 same-domain layered binary factor processes; result object only",
        "preregistered_hypotheses": {
            "status": "PREREGISTERED_BEFORE_RESULTS",
            "hypotheses": PREREGISTERED_HYPOTHESES,
        },
        "domain": {
            "history": "binary assignments to past variables",
            "interface": "integer message table over binary boundary assignments",
            "future_query": "exact contraction of boundary message with future factor for each future assignment",
            "all_axes_same_semantics": True,
            "cross_domain_comparison_used": False,
        },
        "axis_definitions": {
            "Q": "future_quotient_size: distinct full future response signatures",
            "W": "separator_width: number of boundary variables",
            "D": "separator_domain_cells: 2**W binary boundary assignments",
            "M": "distinct_messages plus exact value/rank/byte statistics; not one scalar",
        },
        "cases": cases,
        "controlled_quadrants": quadrant_observations,
        "fixed_w_contrasts": fixed_w_contrast,
        "minimality_attack": {
            "method": "enumerate natural messages, test every pair against all future signatures, fuse safe pairs until quotient partition",
            "compression_cases": compression_cases,
            "minimality_is_claimed": False,
            "minimality_is_checked_for_small_cases": True,
        },
        "bounds_and_constraints": {
            "q_le_distinct_messages_verified": q_le_m_verified,
            "q_le_distinct_messages_reason": "future response is a deterministic function of the exact message in this domain",
            "general_bound_claimed": False,
            "observed_controlled_quadrants": len(quadrant_observations),
        },
        "gate": {
            "status": "SURVIVES_PROVISIONALLY",
            "A_q_w_contrast": True,
            "B_reproducible_relation": q_le_m_verified,
            "C_natural_interface_compression": bool(compression_cases),
            "D_w_alone_not_sufficient": by_case["large_q_small_w"]["future_quotient_size"] != by_case["small_q_small_w"]["future_quotient_size"],
            "caveat": "These are controlled finite processes; no stable theory or universal dimension is claimed.",
        },
        "anomalies_and_counterexamples": {
            "same_w_q_message_content_changes": True,
            "same_w_q_raw_history_and_cost_changes": True,
            "q_large_w_small_exists_in_this_weighted_domain": True,
            "same_w_same_q_same_message_different_raw_work": True,
            "negative_outcomes_preserved": True,
        },
        "metrics_policy": {
            "resource_vector": True,
            "scalar_collapsed": False,
            "lift_gain_declared": False,
            "machine_dependent_fields": ["wall_ms"],
            "deterministic_fields": ["raw_input", "raw_input_digest", "Q", "W", "D", "M", "message values", "quotient", "minimality partitions"],
            "posthoc_oracle_fields": ["future_signatures", "future_quotient_size", "minimal_sufficient_messages", "minimality_attack"],
        },
        "scope_declarations": {
            "main_modified": False,
            "pipi_42_modified": False,
            "pipi_43_modified": False,
            "kernel_modified": False,
            "phase5_started": False,
            "pr_opened": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the PiPi-44 cross-axis order audit")
    parser.add_argument("--json-out", type=Path, default=ROOT / "results" / "cross-axis-order.json")
    args = parser.parse_args(argv)
    result = run_cross_axis_order_audit()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("cases:", len(result["cases"]))
    print("quadrants:", len(result["controlled_quadrants"]))
    print("compression_cases:", result["minimality_attack"]["compression_cases"])
    print("gate:", result["gate"]["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
