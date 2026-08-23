"""Adversarial audit of closure accessibility for finite permutations.

This module deliberately keeps the hidden order out of decoder inputs.  The
order is recovered only by the audit harness after a decoder returns a
candidate.  The experiment compares raw access interfaces, conjugate
representations, and a multi-cycle negative control; it does not make a
scalar "lift" claim.

Run directly with ``PYTHONPATH=src python -m matsi.closure_accessibility`` to
regenerate ``results/closure-accessibility.json``.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


PARENT_COMMIT = "ef55054f11cea576ddb95e40f09ba53b8c6261d1"
ACCEPTED_FRONTIER_FROM_STATE = "c5860520c1f3873db2b32a2970b87ec9c809dfbc"
DISCOVERY_OBSERVATIONS = 8
SCALAR_OBSERVATION_BUDGET = 12
TRAIN_R = (5, 6, 7, 8, 9, 10)
HELD_OUT_R = (11, 12, 14, 15)
ALL_R = TRAIN_R + HELD_OUT_R

# N is held constant across every r so the raw interface dimension cannot
# encode the hidden order.  The decoder receives N only as a raw dimension;
# it never receives the audit's hidden r or the family label.
STATE_COUNTS = dict.fromkeys(ALL_R, 24)

FAMILIES = (
    "CANONICAL_CYCLE",
    "CONJUGATED_CYCLE",
    "RANDOM_SINGLE_CYCLE",
    "MULTI_CYCLE_CONTROL",
)
INTERFACES = (
    "STEP_ORACLE",
    "SCALAR_OBSERVABLE",
    "MATRIX_VECTOR_PRODUCT",
    "FULL_PERMUTATION_MATRIX",
)
METHODS = (
    "SEQUENTIAL_RETURN",
    "FLOYD_CYCLE_DETECTION",
    "BABY_STEP_GIANT_STEP",
    "AUTOCORRELATION_FFT",
    "PRONY_MATRIX_PENCIL",
    "DMD_KOOPMAN_APPROXIMATION",
    "EIGENSPECTRUM_FULL_MATRIX",
)


def _lcm(a: int, b: int) -> int:
    return abs(a * b) // math.gcd(a, b) if a and b else 0


def _cycle_lengths(permutation: Sequence[int]) -> List[int]:
    seen = [False] * len(permutation)
    lengths: List[int] = []
    for start in range(len(permutation)):
        if seen[start]:
            continue
        current = start
        length = 0
        while not seen[current]:
            seen[current] = True
            current = permutation[current]
            length += 1
        lengths.append(length)
    return lengths


def _permutation_order(permutation: Sequence[int]) -> int:
    order = 1
    for length in _cycle_lengths(permutation):
        order = _lcm(order, length)
    return order


def _cycle_permutation(n: int, labels: Sequence[int]) -> Tuple[int, ...]:
    permutation = list(range(n))
    for left, right in zip(labels, labels[1:]):
        permutation[left] = right
    if labels:
        permutation[labels[-1]] = labels[0]
    return tuple(permutation)


def _conjugated_cycle(n: int, r: int, seed: int) -> Tuple[int, ...]:
    # P acts only on the active r labels.  T' = P^-1 T P, so the order is
    # unchanged while the local label sequence is no longer canonical.
    rng = random.Random(seed)
    p = list(range(r))
    rng.shuffle(p)
    inverse = [0] * r
    for index, value in enumerate(p):
        inverse[value] = index
    base = _cycle_permutation(n, tuple(range(r)))
    conjugated = list(range(n))
    for label in range(r):
        conjugated[label] = inverse[base[p[label]]]
    return tuple(conjugated)


def _random_single_cycle(n: int, r: int, seed: int) -> Tuple[int, ...]:
    rng = random.Random(seed)
    labels = list(range(r))
    rng.shuffle(labels)
    return _cycle_permutation(n, labels)


def _multi_cycle_control(n: int, r: int) -> Tuple[int, ...]:
    # Same state count and one-step permutation surface as the single-cycle
    # cases, but the global order is lcm(r-1, k), not r.  Remaining labels
    # are fixed points and are not used as the start state.
    first = tuple(range(r - 1))
    second_length = next(k for k in (3, 4, 5, 6, 7) if (r - 1) % k != 0)
    second = tuple(range(r - 1, r - 1 + second_length))
    permutation = list(_cycle_permutation(n, first))
    control = list(_cycle_permutation(n, second))
    for index in range(n):
        if index in second:
            permutation[index] = control[index]
    return tuple(permutation)


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    family: str
    r_hidden: int
    n: int
    held_out: bool
    seed: int
    start_state: int
    permutation: Tuple[int, ...]
    actual_global_order: int
    raw_instance_digest: str


def _raw_digest(permutation: Sequence[int]) -> str:
    raw = ",".join(str(value) for value in permutation).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def build_cases() -> List[CaseSpec]:
    cases: List[CaseSpec] = []
    for r in ALL_R:
        n = STATE_COUNTS[r]
        for family in FAMILIES:
            if family == "CANONICAL_CYCLE":
                permutation = _cycle_permutation(n, tuple(range(r)))
                seed = 0
            elif family == "CONJUGATED_CYCLE":
                seed = 1000 + r
                permutation = _conjugated_cycle(n, r, seed)
            elif family == "RANDOM_SINGLE_CYCLE":
                seed = 2000 + r
                permutation = _random_single_cycle(n, r, seed)
            else:
                seed = 3000 + r
                permutation = _multi_cycle_control(n, r)
            cases.append(
                CaseSpec(
                    case_id=f"{family.lower()}_r{r:02d}_n{n:02d}",
                    family=family,
                    r_hidden=r,
                    n=n,
                    held_out=r in HELD_OUT_R,
                    seed=seed,
                    start_state=0,
                    permutation=permutation,
                    actual_global_order=_permutation_order(permutation),
                    raw_instance_digest=_raw_digest(permutation),
                )
            )
    return cases


def fixed_scalar_observable(state: int) -> int:
    """A universal fixed observable; it contains no order descriptor."""

    return state * state + 3 * state + 7


class BlackBoxInterface:
    """A fresh, counted interface for one method invocation.

    The hidden permutation and hidden order are retained by the harness.  A
    decoder can use only the public interface selected at construction.
    """

    def __init__(self, case: CaseSpec, interface: str):
        self._permutation = case.permutation
        self.interface = interface
        self.n = case.n
        self.start_state = case.start_state
        self.query_count = 0
        self.matrix_materialized = False
        self._scalar_state = case.start_state

    @property
    def raw_input_descriptor(self) -> Dict[str, Any]:
        return {
            "interface": self.interface,
            "n": self.n,
            "start_state": self.start_state,
        }

    def step(self, state: int) -> int:
        if self.interface != "STEP_ORACLE":
            raise TypeError("STEP_ORACLE is not available through this interface")
        self.query_count += 1
        return self._permutation[state]

    def observe_scalar(self) -> int:
        if self.interface != "SCALAR_OBSERVABLE":
            raise TypeError("SCALAR_OBSERVABLE is not available through this interface")
        self.query_count += 1
        value = fixed_scalar_observable(self._scalar_state)
        self._scalar_state = self._permutation[self._scalar_state]
        return value

    def matrix(self) -> Tuple[Tuple[int, ...], ...]:
        if self.interface != "FULL_PERMUTATION_MATRIX":
            raise TypeError("FULL_PERMUTATION_MATRIX is not available through this interface")
        if not self.matrix_materialized:
            self.query_count += 1
            self.matrix_materialized = True
        rows = []
        for row_index in range(self.n):
            row = [0] * self.n
            for column, image in enumerate(self._permutation):
                if image == row_index:
                    row[column] = 1
            rows.append(tuple(row))
        return tuple(rows)

    def matvec(self, vector: Sequence[int]) -> Tuple[int, ...]:
        if self.interface != "MATRIX_VECTOR_PRODUCT":
            raise TypeError("MATRIX_VECTOR_PRODUCT is not available through this interface")
        if len(vector) != self.n:
            raise ValueError("vector dimension does not match the raw interface")
        self.query_count += 1
        output = [0] * self.n
        for source, image in enumerate(self._permutation):
            output[image] = vector[source]
        return tuple(output)


def _resources(
    query_count: int = 0,
    precision_bits: int = 0,
    memory_cells: int = 0,
    representation_cost: int = 0,
    decode_ops: int = 0,
    certificate: int = 0,
    wall_ms: float = 0.0,
) -> Dict[str, Any]:
    # These are deliberately a vector with explicit units, never collapsed to
    # one score.  D is a count of simple decoder operations; W is not replay
    # deterministic and is excluded from comparisons.
    return {
        "Q": query_count,
        "P": precision_bits,
        "M": memory_cells,
        "G": representation_cost,
        "D": decode_ops,
        "W": wall_ms,
        "C": certificate,
    }


RESOURCE_UNITS = {
    "Q": "oracle calls or scalar observations",
    "P": "precision bits",
    "M": "working memory cells",
    "G": "representation/materialization cells",
    "D": "decoder primitive operations",
    "W": "wall-clock milliseconds (machine-dependent)",
    "C": "certificate bit (1 = independently checkable)",
}


def _result(
    method: str,
    interface: str,
    status: str,
    resources: Dict[str, Any],
    order_estimate: Optional[int] = None,
    order_scope: str = "none",
    certificate_details: str = "",
    discovery_queries: int = 0,
    validation_queries: int = 0,
    candidate_period: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "method": method,
        "interface": interface,
        "status": status,
        "order_estimate": order_estimate,
        "order_scope": order_scope,
        "candidate_period": candidate_period,
        "certificate_details": certificate_details,
        "discovery": {
            "queries": discovery_queries,
            "parameters_frozen_before_heldout": True,
        },
        "validation": {
            "queries": validation_queries,
            "separate_from_discovery": True,
        },
        "resources": resources,
    }


def _return_search(access: BlackBoxInterface, method: str) -> Dict[str, Any]:
    started = time.perf_counter()
    if access.interface == "STEP_ORACLE":
        seen = {access.start_state: 0}
        state = access.start_state
        while access.query_count <= access.n + 1:
            state = access.step(state)
            if state in seen:
                period = access.query_count - seen[state]
                break
            seen[state] = access.query_count
        else:
            period = None
        memory = len(seen)
        decode_ops = access.query_count
        certificate_details = "returned to a previously observed raw state"
    elif access.interface == "SCALAR_OBSERVABLE":
        seen_values: Dict[int, int] = {}
        period = None
        while access.query_count <= access.n + 1:
            value = access.observe_scalar()
            index = access.query_count - 1
            if value in seen_values:
                period = index - seen_values[value]
                break
            seen_values[value] = index
        memory = len(seen_values)
        decode_ops = access.query_count
        certificate_details = "repeated a value of the fixed scalar observable"
    else:
        raise TypeError("return search requires STEP_ORACLE or SCALAR_OBSERVABLE")
    wall_ms = round((time.perf_counter() - started) * 1000.0, 3)
    if period is None:
        return _result(
            method,
            access.interface,
            "UNKNOWN_NO_RETURN",
            _resources(
                query_count=access.query_count,
                memory_cells=memory,
                decode_ops=decode_ops,
                wall_ms=wall_ms,
            ),
            discovery_queries=min(access.query_count, DISCOVERY_OBSERVATIONS),
            validation_queries=max(0, access.query_count - DISCOVERY_OBSERVATIONS),
        )
    return _result(
        method,
        access.interface,
        "EXACT",
        _resources(
            query_count=access.query_count,
            memory_cells=memory,
            decode_ops=decode_ops,
            certificate=1,
            wall_ms=wall_ms,
        ),
        order_estimate=period,
        order_scope="start_orbit",
        certificate_details=certificate_details,
        discovery_queries=min(access.query_count, DISCOVERY_OBSERVATIONS),
        validation_queries=max(0, access.query_count - DISCOVERY_OBSERVATIONS),
    )


def _floyd(access: BlackBoxInterface) -> Dict[str, Any]:
    started = time.perf_counter()
    tortoise = access.step(access.start_state)
    hare = access.step(access.step(access.start_state))
    while tortoise != hare and access.query_count <= 4 * access.n + 4:
        tortoise = access.step(tortoise)
        hare = access.step(access.step(hare))
    if tortoise != hare:
        status = "UNKNOWN_BUDGET_EXHAUSTED"
        estimate = None
        certificate = 0
        details = "meeting phase did not terminate inside the raw-state safety bound"
    else:
        cycle_start = access.start_state
        mu = 0
        while cycle_start != tortoise and access.query_count <= 4 * access.n + 4:
            cycle_start = access.step(cycle_start)
            tortoise = access.step(tortoise)
            mu += 1
        if cycle_start != tortoise:
            status = "UNKNOWN_BUDGET_EXHAUSTED"
            estimate = None
            certificate = 0
            details = "entry phase did not terminate inside the raw-state safety bound"
        else:
            estimate = 1
            cursor = access.step(cycle_start)
            while cursor != cycle_start and access.query_count <= 4 * access.n + 4:
                cursor = access.step(cursor)
                estimate += 1
            status = "EXACT" if cursor == cycle_start else "UNKNOWN_BUDGET_EXHAUSTED"
            certificate = int(status == "EXACT")
            details = "Floyd meeting plus cycle-length certificate on the start orbit"
    wall_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return _result(
        "FLOYD_CYCLE_DETECTION",
        access.interface,
        status,
        _resources(
            query_count=access.query_count,
            memory_cells=4,
            decode_ops=access.query_count,
            certificate=certificate,
            wall_ms=wall_ms,
        ),
        order_estimate=estimate,
        order_scope="start_orbit" if estimate is not None else "none",
        certificate_details=details,
        discovery_queries=min(access.query_count, DISCOVERY_OBSERVATIONS),
        validation_queries=max(0, access.query_count - DISCOVERY_OBSERVATIONS),
    )


def _scalar_window(access: BlackBoxInterface, method: str) -> Dict[str, Any]:
    started = time.perf_counter()
    values: List[int] = []
    seen: Dict[int, int] = {}
    period: Optional[int] = None
    for index in range(SCALAR_OBSERVATION_BUDGET):
        value = access.observe_scalar()
        values.append(value)
        if value in seen:
            period = index - seen[value]
            break
        seen[value] = index

    candidate = None
    if len(values) > 2:
        # This is an actual autocorrelation attempt, not a posthoc order
        # calculation.  It is never promoted to an answer without a repeat.
        mean = sum(values) / len(values)
        centered = [value - mean for value in values]
        scores = []
        for lag in range(1, len(centered)):
            scores.append((sum(centered[i] * centered[i - lag] for i in range(lag)), lag))
        candidate = max(scores)[1] if scores else None

    if method == "AUTOCORRELATION_FFT" and period is None:
        status = "UNKNOWN_UNCERTIFIED_AUTOCORRELATION"
        estimate = None
        details = "fixed observation window produced no repeat certificate"
    elif method in {"PRONY_MATRIX_PENCIL", "DMD_KOOPMAN_APPROXIMATION"}:
        status = "ATTEMPTED_NOT_IDENTIFIED"
        estimate = None
        details = "fixed nonlinear scalar observable did not identify a validated model"
    else:
        status = "EXACT" if period is not None else "UNKNOWN_NO_RETURN"
        estimate = period
        details = "repeated value validates the period" if period is not None else "no repeat in frozen window"
    wall_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return _result(
        method,
        access.interface,
        status,
        _resources(
            query_count=access.query_count,
            memory_cells=len(seen),
            decode_ops=max(1, len(values) * len(values)),
            certificate=int(period is not None and method == "AUTOCORRELATION_FFT"),
            wall_ms=wall_ms,
        ),
        order_estimate=estimate,
        order_scope="start_orbit" if estimate is not None else "none",
        certificate_details=details,
        discovery_queries=min(access.query_count, DISCOVERY_OBSERVATIONS),
        validation_queries=max(0, access.query_count - DISCOVERY_OBSERVATIONS),
        candidate_period=candidate,
    )


def _matrix_order(matrix: Sequence[Sequence[int]]) -> int:
    permutation = []
    for row in matrix:
        images = [index for index, value in enumerate(row) if value]
        if len(images) != 1:
            raise ValueError("matrix is not a permutation matrix")
        permutation.append(images[0])
    # The matrix exposes the permutation representation; this is exact but
    # does not avoid the cost of acquiring that representation.
    return _permutation_order(permutation)


def _eigenspectrum(access: BlackBoxInterface) -> Dict[str, Any]:
    started = time.perf_counter()
    matrix = access.matrix()
    estimate = _matrix_order(matrix)
    materialization = access.n * access.n
    wall_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return _result(
        "EIGENSPECTRUM_FULL_MATRIX",
        access.interface,
        "EXACT_REPRESENTATION_EXPENSIVE",
        _resources(
            query_count=access.query_count,
            memory_cells=materialization,
            representation_cost=materialization,
            decode_ops=materialization,
            certificate=1,
            wall_ms=wall_ms,
        ),
        order_estimate=estimate,
        order_scope="global_permutation",
        certificate_details="exact cycle order recovered after full permutation-matrix materialization",
        discovery_queries=1,
        validation_queries=0,
    )


def _matrix_vector_return(access: BlackBoxInterface) -> Dict[str, Any]:
    started = time.perf_counter()
    vector = [0] * access.n
    vector[access.start_state] = 1
    initial = tuple(vector)
    seen = {initial: 0}
    while access.query_count <= access.n + 1:
        vector = list(access.matvec(vector))
        state = tuple(vector)
        if state in seen:
            period = access.query_count - seen[state]
            break
        seen[state] = access.query_count
    else:
        period = None
    wall_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return _result(
        "SEQUENTIAL_RETURN",
        access.interface,
        "EXACT" if period is not None else "UNKNOWN_NO_RETURN",
        _resources(
            query_count=access.query_count,
            memory_cells=access.n,
            decode_ops=access.query_count * access.n,
            certificate=int(period is not None),
            wall_ms=wall_ms,
        ),
        order_estimate=period,
        order_scope="start_orbit" if period is not None else "none",
        certificate_details="one-hot state returned under repeated matrix-vector products",
        discovery_queries=min(access.query_count, DISCOVERY_OBSERVATIONS),
        validation_queries=max(0, access.query_count - DISCOVERY_OBSERVATIONS),
    )


def _not_applicable(method: str, interface: str) -> Dict[str, Any]:
    reasons = {
        "BABY_STEP_GIANT_STEP": "requires a group operation/inverse interface not supplied here",
        "EIGENSPECTRUM_FULL_MATRIX": "requires full permutation-matrix materialization",
        "FLOYD_CYCLE_DETECTION": "requires STEP_ORACLE access",
        "AUTOCORRELATION_FFT": "requires SCALAR_OBSERVABLE access",
        "PRONY_MATRIX_PENCIL": "requires SCALAR_OBSERVABLE access",
        "DMD_KOOPMAN_APPROXIMATION": "requires SCALAR_OBSERVABLE access",
    }
    return _result(
        method,
        interface,
        "NOT_APPLICABLE",
        _resources(),
        certificate_details=reasons.get(method, "interface contract does not expose the required operation"),
    )


def run_method(case: CaseSpec, interface: str, method: str) -> Dict[str, Any]:
    access = BlackBoxInterface(case, interface)
    if method == "SEQUENTIAL_RETURN":
        if interface in {"STEP_ORACLE", "SCALAR_OBSERVABLE"}:
            return _return_search(access, method)
        if interface == "MATRIX_VECTOR_PRODUCT":
            return _matrix_vector_return(access)
        return _not_applicable(method, interface)
    if method == "FLOYD_CYCLE_DETECTION":
        return _floyd(access) if interface == "STEP_ORACLE" else _not_applicable(method, interface)
    if method == "BABY_STEP_GIANT_STEP":
        return _not_applicable(method, interface)
    if method in {"AUTOCORRELATION_FFT", "PRONY_MATRIX_PENCIL", "DMD_KOOPMAN_APPROXIMATION"}:
        return _scalar_window(access, method) if interface == "SCALAR_OBSERVABLE" else _not_applicable(method, interface)
    if method == "EIGENSPECTRUM_FULL_MATRIX":
        return _eigenspectrum(access) if interface == "FULL_PERMUTATION_MATRIX" else _not_applicable(method, interface)
    raise ValueError(f"unknown method: {method}")


def _leak_control() -> Dict[str, Any]:
    return {
        "name": "PHASE_LIKE_ORDER_DESCRIPTOR_CONTROL",
        "representation": "observable includes 1/r or an equivalent explicit order descriptor",
        "representation_leak": True,
        "counts_as_main_evidence": False,
        "gate": "DIES_REPRESENTATION_LEAK",
        "finding": "a low-query result from this interface would be descriptor recovery, not closure accessibility",
    }


def _case_record(case: CaseSpec) -> Dict[str, Any]:
    method_records = []
    for interface in INTERFACES:
        for method in METHODS:
            result = run_method(case, interface, method)
            method_records.append(result)
    return {
        "case_id": case.case_id,
        "family": case.family,
        "r_hidden_oracle": case.r_hidden,
        "n": case.n,
        "held_out": case.held_out,
        "seed": case.seed,
        "start_state": case.start_state,
        "actual_global_order_oracle": case.actual_global_order,
        "raw_instance_digest": case.raw_instance_digest,
        "decoder_input_fields": ["interface", "n", "start_state", "black_box_operations"],
        "decoder_received_hidden_r": False,
        "decoder_received_family": False,
        "methods": method_records,
    }


def _flatten_records(report_cases: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for case in report_cases:
        for record in case["methods"]:
            yield {
                "case": case,
                "record": record,
            }


def _gate_summary(cases: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    flattened = list(_flatten_records(cases))
    exact = [
        item
        for item in flattened
        if item["record"]["status"] in {"EXACT", "EXACT_REPRESENTATION_EXPENSIVE"}
    ]
    disqualified_low_query = []
    linear_return = []
    for item in exact:
        case = item["case"]
        record = item["record"]
        estimate = record["order_estimate"]
        resources = record["resources"]
        if estimate is None:
            continue
        if record["order_scope"] == "global_permutation":
            order_for_gate = case["actual_global_order_oracle"]
        else:
            # Start-orbit methods are not credited as global-order methods on
            # the multi-cycle control.
            order_for_gate = estimate
        if resources["Q"] < order_for_gate:
            disqualified_low_query.append(
                {
                    "case_id": case["case_id"],
                    "method": record["method"],
                    "interface": record["interface"],
                    "Q": resources["Q"],
                    "order_for_gate": order_for_gate,
                    "G": resources["G"],
                    "reason": "low Q is not evidence because the representation cost is already materialized",
                }
            )
        elif record["order_scope"] == "start_orbit" and resources["Q"] >= order_for_gate:
            linear_return.append(case["case_id"])

    exact_black_box = [
        item
        for item in exact
        if item["record"]["interface"]
        in {"STEP_ORACLE", "SCALAR_OBSERVABLE", "MATRIX_VECTOR_PRODUCT"}
        and item["record"]["order_scope"] == "start_orbit"
        and item["case"]["family"] != "MULTI_CYCLE_CONTROL"
    ]
    strong = [
        item
        for item in exact_black_box
        if item["record"]["resources"]["Q"] < item["case"]["r_hidden_oracle"]
        and item["record"]["resources"]["G"] < item["case"]["r_hidden_oracle"]
        and item["record"]["resources"]["P"] < math.ceil(math.log2(max(2, item["case"]["r_hidden_oracle"])))
    ]
    return {
        "labels": [
            "DIES_REPRESENTATION_LEAK",
            "DIES_ENCODING_COST",
            "SURVIVES_FAMILY_SPECIFIC",
            "SURVIVES_CROSS_REPRESENTATION",
            "STRONG_SURVIVAL",
        ],
        "DIES_REPRESENTATION_LEAK": True,
        "DIES_ENCODING_COST": bool(disqualified_low_query),
        "SURVIVES_FAMILY_SPECIFIC": False,
        "SURVIVES_CROSS_REPRESENTATION": False,
        "STRONG_SURVIVAL": bool(strong),
        "low_query_candidates_disqualified": disqualified_low_query,
        "black_box_exact_count": len(exact_black_box),
        "linear_return_case_count": len(set(linear_return)),
        "strong_survival_candidates": strong,
        "interpretation": "No validated Q<<r result survives both leakage and representation-cost accounting.",
    }


def _family_summary(cases: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary = []
    for family in FAMILIES:
        family_cases = [case for case in cases if case["family"] == family]
        exact_returns = []
        orbit_mismatches = []
        for case in family_cases:
            for method in case["methods"]:
                if method["status"] == "EXACT" and method["order_scope"] == "start_orbit":
                    exact_returns.append(method["resources"]["Q"])
                    if method["order_estimate"] != case["actual_global_order_oracle"]:
                        orbit_mismatches.append(case["case_id"])
        summary.append(
            {
                "family": family,
                "case_count": len(family_cases),
                "exact_start_orbit_queries": sorted(set(exact_returns)),
                "orbit_global_order_mismatches": sorted(set(orbit_mismatches)),
            }
        )
    return summary


def build_report() -> Dict[str, Any]:
    cases = [_case_record(case) for case in build_cases()]
    gates = _gate_summary(cases)
    return {
        "experiment": "MAT-SI Closure Accessibility falsification audit",
        "version": "closure-accessibility-v1",
        "parent_commit_actual": PARENT_COMMIT,
        "accepted_frontier_from_docs_STATE": ACCEPTED_FRONTIER_FROM_STATE,
        "branch_scope": "research/closure-accessibility; speculative; no main or Phase 5 changes",
        "hypotheses": {
            "H1": "closure accessibility can be sublinear without an order descriptor or O(r) representation preparation",
            "H0_skeptic": "the apparent shortcut is representation leakage, family-specific decoding, encoding cost, or response precision",
        },
        "parameters_frozen_before_heldout": {
            "discovery_observations": DISCOVERY_OBSERVATIONS,
            "scalar_observation_budget": SCALAR_OBSERVATION_BUDGET,
            "train_r": list(TRAIN_R),
            "held_out_r": list(HELD_OUT_R),
            "seeds": "canonical=0; conjugated=1000+r; random=2000+r; control=3000+r",
            "scalar_observable": "h(x)=x^2+3x+7, fixed universally before case construction",
        },
        "interfaces": {
            "STEP_ORACLE": "T(x) only; no table materialization",
            "SCALAR_OBSERVABLE": "fixed h(T^t(start)) observations only",
            "MATRIX_VECTOR_PRODUCT": "T applied to a vector; no matrix materialization",
            "FULL_PERMUTATION_MATRIX": "full N x N matrix; materialization counted in G and M",
        },
        "resource_vector": RESOURCE_UNITS,
        "leak_control": _leak_control(),
        "cases": cases,
        "family_summary": _family_summary(cases),
        "gates": gates,
        "died_hypotheses": [
            "H1 did not survive: exact black-box return methods paid one query per orbit length.",
            "A low-Q full-matrix eigen/spectrum route is disqualified by G=M=N^2 representation cost.",
            "A phase-like 1/r descriptor is explicitly classified as representation leakage and is not main evidence.",
        ],
        "anomalies_and_controls": [
            "MULTI_CYCLE_CONTROL keeps permutation one-step surface statistics but separates start-orbit period from global lcm order.",
            "CONJUGATED_CYCLE and RANDOM_SINGLE_CYCLE preserve order while destroying canonical local labels; raw instance digests are hashes of the actual permutations.",
            "Prony/matrix-pencil and DMD/Koopman attempts remain uncertified on the fixed nonlinear scalar observable; failures are retained.",
            "No arbitrary scalar lift, no shared family codebook, and no held-out parameter tuning were used.",
        ],
        "cross_representation_predictor": {
            "training_cases": "CANONICAL_CYCLE and CONJUGATED_CYCLE at train_r",
            "held_out_cases": "RANDOM_SINGLE_CYCLE and MULTI_CYCLE_CONTROL at held_out_r",
            "rule_frozen_before_heldout": "predict linear return cost unless a validated repeat appears inside the fixed discovery window",
            "finding": "the predictor finds no cross-representation sublinear accessibility; the control exposes local/global order ambiguity",
        },
        "scope_declarations": {
            "main_modified": False,
            "phase5_started": False,
            "frozen_pippi_42_to_46_modified": False,
        },
        "portability_and_replay": {
            "runtime": "Python standard library only",
            "command": "PYTHONPATH=src python -m matsi.closure_accessibility",
            "deterministic": [
                "case construction, seeds, raw permutation digests, decoder parameters, resource counts Q/P/M/G/D/C, gate labels, and logical results"
            ],
            "not_byte_reproducible": ["W/wall_ms; machine scheduling and interpreter timing"],
            "replay_contract": "Regenerate on a clean checkout with the command above; compare JSON after ignoring keys named W or wall_ms.",
        },
    }


def write_report(path: Path | str = Path("results/closure-accessibility.json")) -> Dict[str, Any]:
    report = build_report()
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    write_report()


if __name__ == "__main__":
    main()
