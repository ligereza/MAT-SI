"""PiPi-46: quantum query/order stress tests with idealized small models.

No quantum hardware or gate simulator is used.  The controls model oracle
queries and post-query information exactly for small spaces, while explicitly
marking full gate/circuit cost as ``NOT_MEASURED``.  Query count, classical
postprocessing, repetitions, oracle construction, candidate-space evolution,
and state dimension are separate resource fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
from time import perf_counter
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PARENT_COMMIT = "81be791"
PROTOCOL = "pipi-46-quantum-order-stress-v0"

PREDICTION_RULE = {
    "status": "PREREGISTERED_BEFORE_HELDOUT_LABELS",
    "if": "first_observation_candidate_ratio <= 0.5 and independent_constraints_gained >= 1",
    "then": "EXPONENTIAL/STRUCTURAL QUERY SPEEDUP",
    "elif": "quantum_query_ratio_to_classical <= 0.5",
    "then_else": "QUADRATIC-LIKE",
    "otherwise": "NO_SIGNIFICANT_STRUCTURAL SPEEDUP",
    "heldout": ["simon_n4", "period_finding_n16"],
}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _rank(rows: list[int], n: int) -> int:
    rows = list(rows)
    pivot = 0
    for column in range(n):
        candidate = next((index for index in range(pivot, len(rows)) if (rows[index] >> column) & 1), None)
        if candidate is None:
            continue
        rows[pivot], rows[candidate] = rows[candidate], rows[pivot]
        for index in range(len(rows)):
            if index != pivot and ((rows[index] >> column) & 1):
                rows[index] ^= rows[pivot]
        pivot += 1
    return pivot


def _dot_mod2(left: int, right: int) -> int:
    return (left & right).bit_count() % 2


def _oracle_cost(n: int) -> dict[str, Any]:
    return {
        "model": "enumerated ideal oracle truth-table entries",
        "entries": 1 << n,
        "used_as_query_count": False,
        "gate_circuit_proxy": "NOT_MEASURED",
    }


def _profile(
    *,
    raw_candidate_space: int,
    first_after: int,
    width: int,
    message_bytes: int,
    discovery_ops: int,
    transform_ops: int,
    solve_ops: int,
    independent_constraints: list[int],
    quantum_queries: int,
    classical_queries: int,
) -> dict[str, Any]:
    return {
        "H_raw_candidate_space": raw_candidate_space,
        "Q_after_first_observation": first_after,
        "W_observation_structure_width": width,
        "M_observation_description_bytes": message_bytes,
        "D_discovery_operations": discovery_ops,
        "X_transform_operations": transform_ops,
        "S_postprocessing_operations": solve_ops,
        "I_independent_constraints_per_query": independent_constraints,
        "K_profitable_refinement_depth": len(independent_constraints),
        "first_observation_candidate_ratio": first_after / raw_candidate_space if raw_candidate_space else 1.0,
        "quantum_query_ratio_to_classical": quantum_queries / classical_queries if classical_queries else None,
    }


def _base_record(
    name: str,
    family: str,
    raw_candidate_space: int,
    classical: dict[str, Any],
    quantum: dict[str, Any],
    profile: dict[str, Any],
    actual_category: str,
) -> dict[str, Any]:
    return {
        "case": name,
        "family": family,
        "raw_candidate_space": raw_candidate_space,
        "classical": classical,
        "quantum": quantum,
        "order_profile": profile,
        "actual_category_posthoc": actual_category,
        "oracle_construction_cost": quantum["oracle_construction_cost"],
        "machine_dependent_fields": ["wall_ms"],
        "wall_ms": 0.0,
    }


def grover_control() -> dict[str, Any]:
    n = 16
    target = 9
    remaining = list(range(n))
    classical_after: list[int] = []
    classical_queries = 0
    for query in range(n):
        classical_queries += 1
        if query == target:
            remaining = [target]
        else:
            remaining.remove(query)
        classical_after.append(len(remaining))
        if len(remaining) == 1:
            break
    quantum_queries = max(1, math.floor(math.pi * math.sqrt(n) / 4))
    theta = math.asin(1 / math.sqrt(n))
    success_probability = math.sin((2 * quantum_queries + 1) * theta) ** 2
    quantum_after = [n] * quantum_queries
    profile = _profile(
        raw_candidate_space=n,
        first_after=n,
        width=0,
        message_bytes=1,
        discovery_ops=1,
        transform_ops=0,
        solve_ops=1,
        independent_constraints=[0] * quantum_queries,
        quantum_queries=quantum_queries,
        classical_queries=classical_queries,
    )
    return _base_record(
        "grover_n16",
        "UNSTRUCTURED_SEARCH",
        n,
        {
            "query_complexity_worst_case": n,
            "query_complexity_observed_target": classical_queries,
            "candidate_secret_space_after_each_observation": classical_after,
            "structure_known_before_query": "only black-box marked predicate",
            "structure_revealed_per_query": "one candidate tested; no global relation",
            "independent_constraints_gained": [1] * classical_queries,
            "representation_postprocessing": "candidate list",
            "postprocessing_operations": classical_queries,
            "memory_proxy": n,
            "success_probability": 1.0,
            "repetitions": 1,
        },
        {
            "query_complexity_ideal": quantum_queries,
            "candidate_secret_space_after_each_observation": quantum_after,
            "structure_known_before_query": "black-box phase/oracle marking one target",
            "structure_revealed_per_query": "amplitude amplification; no classical candidate constraint",
            "independent_constraints_gained": [0] * quantum_queries,
            "representation_postprocessing": "amplitude vector; measurement at end",
            "postprocessing_operations": 1,
            "memory_proxy": n,
            "state_dimension": n,
            "success_probability": success_probability,
            "repetitions": 1,
            "success_amplification_queries": quantum_queries,
            "oracle_construction_cost": _oracle_cost(4),
        },
        profile,
        "QUADRATIC-LIKE",
    )


def simon_control() -> dict[str, Any]:
    n = 4
    secret = 0b0101
    space = 1 << n
    secrets = list(range(1, space))

    def oracle(x: int) -> int:
        return min(x, x ^ secret)

    observations: dict[int, int] = {}
    classical_after: list[int] = []
    classical_queries = 0
    for x in range(space):
        observations[x] = oracle(x)
        classical_queries += 1
        candidates = [candidate for candidate in secrets if all(min(query, query ^ candidate) == value for query, value in observations.items())]
        classical_after.append(len(candidates))
        if len(candidates) == 1:
            break
    measurements: list[int] = []
    ranks: list[int] = []
    quantum_after: list[int] = []
    independent_gains: list[int] = []
    previous_rank = 0
    for y in range(1, space):
        if _dot_mod2(y, secret) != 0:
            continue
        next_rank = _rank(measurements + [y], n)
        if next_rank == previous_rank:
            continue
        measurements.append(y)
        ranks.append(next_rank)
        independent_gains.append(next_rank - previous_rank)
        previous_rank = next_rank
        quantum_after.append(sum(1 for candidate in secrets if all(_dot_mod2(y0, candidate) == 0 for y0 in measurements)))
        if next_rank == n - 1:
            break
    quantum_queries = len(measurements)
    profile = _profile(
        raw_candidate_space=len(secrets),
        first_after=quantum_after[0],
        width=n,
        message_bytes=n,
        discovery_ops=1,
        transform_ops=n,
        solve_ops=n**3,
        independent_constraints=independent_gains,
        quantum_queries=quantum_queries,
        classical_queries=classical_queries,
    )
    return _base_record(
        "simon_n4",
        "SIMON_HIDDEN_XOR",
        len(secrets),
        {
            "query_complexity_worst_case": space,
            "query_complexity_observed_collision": classical_queries,
            "candidate_secret_space_after_each_observation": classical_after,
            "structure_known_before_query": "hidden XOR period promised but secret unknown",
            "structure_revealed_per_query": "function value; collision needed for direct secret recovery",
            "independent_constraints_gained": [0] * classical_queries,
            "representation_postprocessing": "collision table and secret consistency set",
            "postprocessing_operations": classical_queries * len(secrets),
            "memory_proxy": len(observations) + len(secrets),
            "success_probability": 1.0,
            "repetitions": 1,
        },
        {
            "query_complexity_ideal": quantum_queries,
            "measurements": measurements,
            "constraint_equations": [f"dot({y}, secret)=0 mod 2" for y in measurements],
            "candidate_secret_space_after_each_observation": quantum_after,
            "structure_known_before_query": "hidden XOR structure promised",
            "structure_revealed_per_query": "one homogeneous GF2 constraint y·s=0",
            "independent_constraints_gained": independent_gains,
            "postprocessing_representation": "GF2 row reduction",
            "postprocessing_operations": n**3,
            "memory_proxy": n,
            "state_dimension": space,
            "success_probability": 1.0 if previous_rank == n - 1 else None,
            "repetitions": quantum_queries,
            "success_amplification_queries": quantum_queries,
            "oracle_construction_cost": _oracle_cost(n),
        },
        profile,
        "EXPONENTIAL/STRUCTURAL QUERY SPEEDUP",
    )


def period_finding_control() -> dict[str, Any]:
    N = 16
    periods = (2, 4, 8)
    hidden_period = 4

    def oracle(x: int, period: int) -> int:
        return x % period

    observations: dict[int, int] = {}
    classical_after: list[int] = []
    classical_queries = 0
    for x in range(N):
        observations[x] = oracle(x, hidden_period)
        classical_queries += 1
        candidates = [period for period in periods if all(oracle(query, period) == value for query, value in observations.items())]
        classical_after.append(len(candidates))
        if len(candidates) == 1:
            break
    sample = N // hidden_period
    reconstructed_denominator = Fraction(sample, N).limit_denominator(N).denominator
    quantum_candidates = [period for period in periods if period == reconstructed_denominator]
    quantum_after = [len(quantum_candidates)]
    quantum_queries = 1
    profile = _profile(
        raw_candidate_space=len(periods),
        first_after=len(quantum_candidates),
        width=int(math.log2(N)),
        message_bytes=len(str(sample)),
        discovery_ops=1,
        transform_ops=1,
        solve_ops=math.ceil(math.log2(N)) ** 2,
        independent_constraints=[1 if len(quantum_candidates) == 1 else 0],
        quantum_queries=quantum_queries,
        classical_queries=classical_queries,
    )
    return _base_record(
        "period_finding_n16",
        "TOY_PERIOD_FINDING",
        len(periods),
        {
            "query_complexity_worst_case": N,
            "query_complexity_observed_period_identification": classical_queries,
            "candidate_secret_space_after_each_observation": classical_after,
            "structure_known_before_query": "periodic function promise; period unknown",
            "structure_revealed_per_query": "function value; short prefix may leave periods tied",
            "independent_constraints_gained": [0] * classical_queries,
            "representation_postprocessing": "period consistency table",
            "postprocessing_operations": classical_queries * len(periods),
            "memory_proxy": len(periods),
            "success_probability": 1.0,
            "repetitions": 1,
        },
        {
            "query_complexity_ideal": quantum_queries,
            "fourier_sample": sample,
            "candidate_secret_space_after_each_observation": quantum_after,
            "structure_known_before_query": "periodic oracle promise",
            "structure_revealed_per_query": "ideal Fourier sample and rational denominator",
            "independent_constraints_gained": [1 if len(quantum_candidates) == 1 else 0],
            "postprocessing_representation": "continued-fraction/rational reconstruction proxy",
            "postprocessing_operations": math.ceil(math.log2(N)) ** 2,
            "memory_proxy": N,
            "state_dimension": N,
            "success_probability": 1.0 if len(quantum_candidates) == 1 else None,
            "repetitions": 1,
            "success_amplification_queries": 1,
            "oracle_construction_cost": _oracle_cost(int(math.log2(N))),
        },
        profile,
        "NO_SIGNIFICANT_STRUCTURAL SPEEDUP",
    )


def bernstein_vazirani_control() -> dict[str, Any]:
    n = 4
    secret = 0b1001
    raw_space = 1 << n
    classical_after = [1 << (n - index) for index in range(1, n + 1)]
    quantum_after = [1]
    profile = _profile(
        raw_candidate_space=raw_space,
        first_after=1,
        width=n,
        message_bytes=n,
        discovery_ops=1,
        transform_ops=n,
        solve_ops=n,
        independent_constraints=[n],
        quantum_queries=1,
        classical_queries=n,
    )
    return _base_record(
        "bernstein_vazirani_n4",
        "BERNSTEIN_VAZIRANI_CALIBRATION",
        raw_space,
        {
            "query_complexity_worst_case": n,
            "query_complexity_observed": n,
            "candidate_secret_space_after_each_observation": classical_after,
            "structure_known_before_query": "linear Boolean phase promised",
            "structure_revealed_per_query": "one basis-bit parity observation",
            "independent_constraints_gained": [1] * n,
            "representation_postprocessing": "bit vector",
            "postprocessing_operations": n,
            "memory_proxy": n,
            "success_probability": 1.0,
            "repetitions": 1,
        },
        {
            "query_complexity_ideal": 1,
            "measurement": format(secret, f"0{n}b"),
            "candidate_secret_space_after_each_observation": quantum_after,
            "structure_known_before_query": "linear Boolean phase promised",
            "structure_revealed_per_query": "n-bit global parity vector",
            "independent_constraints_gained": [n],
            "postprocessing_representation": "direct bit vector",
            "postprocessing_operations": n,
            "memory_proxy": raw_space,
            "state_dimension": raw_space,
            "success_probability": 1.0,
            "repetitions": 1,
            "success_amplification_queries": 1,
            "oracle_construction_cost": _oracle_cost(n),
        },
        profile,
        "LINEAR_GLOBAL_CALIBRATION",
    )


def _predict(profile: dict[str, Any]) -> str:
    first_ratio = profile["first_observation_candidate_ratio"]
    independent = max(profile["I_independent_constraints_per_query"] or [0])
    query_ratio = profile["quantum_query_ratio_to_classical"]
    if first_ratio <= 0.5 and independent >= 1:
        return "EXPONENTIAL/STRUCTURAL QUERY SPEEDUP"
    if query_ratio is not None and query_ratio <= 0.5:
        return "QUADRATIC-LIKE"
    return "NO_SIGNIFICANT STRUCTURAL SPEEDUP"


def run_quantum_order_stress() -> dict[str, Any]:
    controls = [grover_control(), bernstein_vazirani_control(), simon_control(), period_finding_control()]
    heldout = {"simon_n4", "period_finding_n16"}
    training = {"grover_n16", "bernstein_vazirani_n4"}
    predictions = {control["case"]: _predict(control["order_profile"]) for control in controls}
    for control in controls:
        control["prediction"] = {
            "category": predictions[control["case"]],
            "computed_before_actual_category_reveal": True,
            "rule_digest": _digest(PREDICTION_RULE),
        }
        control["prediction"]["heldout"] = control["case"] in heldout
        control["prediction"]["actual_category_posthoc"] = control["actual_category_posthoc"]
        control["prediction"]["correct"] = predictions[control["case"]] == control["actual_category_posthoc"]
    heldout_results = [control for control in controls if control["case"] in heldout]
    return {
        "protocol": PROTOCOL,
        "parent_commit": PARENT_COMMIT,
        "scope": "PiPi-46 idealized quantum query stress; no hardware, no full gate simulator",
        "model_boundary": {
            "quantum_hardware": False,
            "idealized_oracle_model": True,
            "full_gate_circuit_cost": "NOT_MEASURED",
            "oracle_construction_is_reported": True,
            "scalar_speedup_claim": False,
        },
        "common_metrics": [
            "raw candidate space",
            "classical query complexity",
            "quantum query complexity",
            "structure known before query",
            "structure revealed per query",
            "independent constraints gained",
            "remaining candidate classes after each observation",
            "representation/postprocessing resources",
            "memory/state resources",
            "success probability",
            "repetitions and amplification",
            "oracle construction cost",
        ],
        "controls": controls,
        "prediction_protocol": {
            "training_controls": sorted(training),
            "heldout_controls": sorted(heldout),
            "labels_revealed_after_prediction": True,
            "rule": PREDICTION_RULE,
            "predictions": {name: predictions[name] for name in sorted(predictions)},
            "heldout_accuracy": sum(control["prediction"]["correct"] for control in heldout_results) / len(heldout_results),
            "heldout_results": [
                {"case": control["case"], "prediction": control["prediction"]["category"], "actual": control["actual_category_posthoc"], "correct": control["prediction"]["correct"]}
                for control in heldout_results
            ],
            "interpretation": "one held-out structural prediction succeeds and the toy period control exposes a mismatch; no general predictor is claimed",
        },
        "order_profile_mapping": {
            "H": "raw candidate/secret space",
            "Q": "candidate classes after an observation",
            "W": "observation/global-constraint width proxy",
            "M": "exact observation description bytes",
            "D": "pre-query discovery operations",
            "X": "transform operations",
            "S": "classical postprocessing operations",
            "I": "independent constraints gained per query",
            "K": "refinement depth until useful candidate restriction",
            "not_a_final_definition": True,
        },
        "optional_tensor_bridge": {
            "status": "NOT_RUN",
            "reason": "full gate/interactions were not measured; no tensor conclusion is licensed",
        },
        "negative_controls": {
            "grover_has_no_global_candidate_constraint": True,
            "simon_collision_vs_global_constraint_is_separate": True,
            "period_postprocessing_mismatch_preserved": True,
            "bv_is_calibration_not_heldout_evidence": True,
        },
        "metrics_policy": {
            "resource_vector": True,
            "scalar_universal_claim": False,
            "machine_dependent_fields": ["wall_ms"],
            "deterministic_fields": ["candidate traces", "constraint ranks", "query counts", "state dimensions", "oracle table entries"],
            "posthoc_fields": ["actual_category_posthoc", "prediction.correct", "prediction_protocol.heldout_accuracy"],
            "not_measured_fields": ["full gate/circuit proxy", "hardware runtime"],
        },
        "scope_declarations": {
            "main_modified": False,
            "pipi_42_modified": False,
            "pipi_43_modified": False,
            "pipi_44_modified": False,
            "pipi_45_modified": False,
            "phase5_started": False,
            "pr_opened": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PiPi-46 quantum query/order stress tests")
    parser.add_argument("--json-out", type=Path, default=ROOT / "results" / "quantum-order-stress.json")
    args = parser.parse_args(argv)
    result = run_quantum_order_stress()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("controls:", len(result["controls"]))
    print("heldout_accuracy:", result["prediction_protocol"]["heldout_accuracy"])
    print("tensor_bridge:", result["optional_tensor_bridge"]["status"])
    print("pr:", "not opened")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
