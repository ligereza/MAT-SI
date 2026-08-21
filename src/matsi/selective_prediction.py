"""Formal finite theory for selectors, predictors, and abstention.

This module starts from the Phase 4A observation that ``G`` selected three
windows but emitted one repeated label.  It does not add a corpus.  Instead it
defines the smallest objects needed to tell selection, prediction, and
rejection apart, and exhaustively solves the resulting finite policy problem.

The solver is intentionally a small-instance instrument.  It enumerates
accept/reject masks for a fixed total predictor, reports coverage and risks as
separate coordinates, and never chooses a policy with an invented weighted
score.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Iterable

from .coverage_prediction import evaluate, phase4_partial_predictor
from .cross_domain import run_phase4


ROOT = Path(__file__).resolve().parents[2]
Label = bool
Prediction = bool | None


def _bools(values: Iterable[bool], name: str) -> list[bool]:
    result = list(values)
    if any(not isinstance(value, bool) for value in result):
        raise ValueError(f"{name} must contain only booleans")
    return result


def _predictions(values: Iterable[Prediction], expected_length: int | None = None) -> list[Prediction]:
    result = list(values)
    if expected_length is not None and len(result) != expected_length:
        raise ValueError("outcomes and predictions must have equal length")
    if any(value is not None and not isinstance(value, bool) for value in result):
        raise ValueError("predictions must contain booleans or None")
    return result


def selector_signature(selected: Iterable[bool]) -> dict[str, Any]:
    """Describe a selector ``s: X -> {0,1}`` without assigning labels."""
    values = _bools(selected, "selected")
    return {
        "kind": "selector",
        "domain_size": len(values),
        "covered": sum(values),
        "coverage": sum(values) / len(values) if values else None,
        "prediction_image_size": 0,
    }


def predictor_signature(predicted: Iterable[bool]) -> dict[str, Any]:
    """Describe a total predictor ``f: X -> Y``."""
    values = _bools(predicted, "predicted")
    image = sorted(set(values))
    return {
        "kind": "predictor",
        "domain_size": len(values),
        "covered": len(values),
        "coverage": 1.0 if values else None,
        "prediction_image": image,
        "prediction_image_size": len(image),
        "prediction_varies": len(image) > 1,
    }


def selective_predictor_signature(predicted: Iterable[Prediction]) -> dict[str, Any]:
    """Describe a partial map ``g: X -> Y union {bottom}``."""
    values = _predictions(predicted)
    image = sorted({value for value in values if value is not None})
    covered = sum(value is not None for value in values)
    return {
        "kind": "selective_predictor",
        "domain_size": len(values),
        "covered": covered,
        "coverage": covered / len(values) if values else None,
        "abstained": len(values) - covered,
        "prediction_image": image,
        "prediction_image_size": len(image),
        "prediction_varies": len(image) > 1,
    }


def induced_prediction_image(
    representations: Iterable[Any], decoder: Callable[[Any], bool]
) -> dict[str, Any]:
    """Apply a decoder to represented states and count its prediction image.

    ``None`` is the represented abstention state.  The decoder is required to
    depend on the representation only; the observed outcome is never passed
    to it.  This is an executable form of the image condition:

        variable predictions iff |decoder(R(X_selected))| >= 2.
    """
    states = list(representations)
    predictions = [None if state is None else decoder(state) for state in states]
    signature = selective_predictor_signature(predictions)
    return {
        "representations": states,
        "predictions": predictions,
        "prediction_image": signature["prediction_image"],
        "prediction_image_size": signature["prediction_image_size"],
        "prediction_varies": signature["prediction_varies"],
        "decoder_uses_outcome": False,
    }


def _validate_total_problem(
    outcomes: Iterable[bool], predictions: Iterable[bool]
) -> tuple[list[bool], list[bool]]:
    y = _bools(outcomes, "outcomes")
    f = _bools(predictions, "predictions")
    if len(y) != len(f):
        raise ValueError("outcomes and predictions must have equal length")
    if not y:
        raise ValueError("exact solver requires at least one row")
    return y, f


def _mask_indices(mask: int, n: int) -> list[int]:
    return [index for index in range(n) if mask & (1 << index)]


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def policy_metrics(
    outcomes: Iterable[bool], predictions: Iterable[bool], accepted_mask: int
) -> dict[str, Any]:
    """Measure one accept/reject policy with integer counts preserved."""
    y, f = _validate_total_problem(outcomes, predictions)
    n = len(y)
    accepted = _mask_indices(accepted_mask, n)
    accepted_set = set(accepted)
    rejected = [index for index in range(n) if index not in accepted_set]
    accepted_errors = sum(f[index] != y[index] for index in accepted)
    rejected_errors = sum(f[index] != y[index] for index in rejected)
    total_errors = accepted_errors + rejected_errors
    return {
        "mask": format(accepted_mask, f"0{n}b"),
        "accepted_indices": accepted,
        "rejected_indices": rejected,
        "total": n,
        "accepted": len(accepted),
        "rejected": len(rejected),
        "coverage": len(accepted) / n,
        "abstention_rate": len(rejected) / n,
        "accepted_errors": accepted_errors,
        "rejected_errors": rejected_errors,
        "total_errors": total_errors,
        "full_risk": total_errors / n,
        "selective_risk": _ratio(accepted_errors, len(accepted)),
        "rejected_risk": _ratio(rejected_errors, len(rejected)),
        "accepted_correct": len(accepted) - accepted_errors,
        "rejected_correct": len(rejected) - rejected_errors,
        "rejected_error_mass": rejected_errors / n,
    }


def action_risk(policy: dict[str, Any], abstention_cost: float) -> float:
    """Expected 0-1 action loss when abstention has an external cost ``c``."""
    if abstention_cost < 0:
        raise ValueError("abstention_cost must be non-negative")
    return (policy["accepted_errors"] + abstention_cost * policy["rejected"]) / policy["total"]


def policy_dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Dominance on the explicit coverage/risk axes; no scalarization."""
    if left["selective_risk"] is None or right["selective_risk"] is None:
        return False
    no_worse = (
        left["coverage"] >= right["coverage"]
        and left["selective_risk"] <= right["selective_risk"]
    )
    strict = (
        left["coverage"] > right["coverage"]
        or left["selective_risk"] < right["selective_risk"]
    )
    return no_worse and strict


def _frontier(policies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        policy
        for policy in policies
        if not any(
            other["mask"] != policy["mask"] and policy_dominates(other, policy)
            for other in policies
        )
    ]


def exact_selective_solver(
    outcomes: Iterable[bool],
    predictions: Iterable[bool],
    *,
    min_coverage: float = 0.0,
    max_rejected_risk: float | None = None,
    abstention_costs: Iterable[float] = (),
) -> dict[str, Any]:
    """Enumerate all selective policies for a small total predictor.

    Constraints are filters, not weights.  The returned frontier preserves
    every policy not dominated on coverage and selective risk.  ``outcomes``
    are used only for finite evaluation; a real policy must be frozen before
    those outcomes are observed.
    """
    y, f = _validate_total_problem(outcomes, predictions)
    if not 0 <= min_coverage <= 1:
        raise ValueError("min_coverage must be in [0, 1]")
    if max_rejected_risk is not None and not 0 <= max_rejected_risk <= 1:
        raise ValueError("max_rejected_risk must be in [0, 1]")
    costs = list(abstention_costs)
    if any(cost < 0 for cost in costs):
        raise ValueError("abstention costs must be non-negative")

    all_policies = []
    for mask in range(1 << len(y)):
        policy = policy_metrics(y, f, mask)
        if policy["coverage"] < min_coverage:
            continue
        if (
            max_rejected_risk is not None
            and policy["rejected_risk"] is not None
            and policy["rejected_risk"] > max_rejected_risk
        ):
            continue
        policy["improves_selective_risk_over_full"] = (
            policy["selective_risk"] is not None
            and policy["selective_risk"] < policy["full_risk"]
        )
        policy["action_risk"] = {
            str(cost): action_risk(policy, cost) for cost in costs
        }
        all_policies.append(policy)

    frontier = _frontier(all_policies)
    return {
        "n": len(y),
        "enumerated_policy_count": 1 << len(y),
        "feasible_policy_count": len(all_policies),
        "constraints": {
            "min_coverage": min_coverage,
            "max_rejected_risk": max_rejected_risk,
        },
        "policies": all_policies,
        "pareto_frontier": frontier,
        "complexity": "O(2^n * n) time and O(2^n) policy output space",
        "abstention_costs_are_external": True,
    }


def calibration_profile(
    outcomes: Iterable[bool], predictions: Iterable[bool], confidence: Iterable[float]
) -> list[dict[str, Any]]:
    """Report exact-confidence calibration groups for a total predictor."""
    y, f = _validate_total_problem(outcomes, predictions)
    q = list(confidence)
    if len(q) != len(y) or any(not 0 <= value <= 1 for value in q):
        raise ValueError("confidence values must have the same length and lie in [0, 1]")
    groups = []
    for level in sorted(set(q)):
        indices = [index for index, value in enumerate(q) if value == level]
        correct = sum(f[index] == y[index] for index in indices)
        groups.append({
            "confidence": level,
            "count": len(indices),
            "empirical_accuracy": correct / len(indices),
            "calibration_gap": correct / len(indices) - level,
            "indices": indices,
        })
    return groups


def threshold_curve(
    outcomes: Iterable[bool],
    predictions: Iterable[bool],
    confidence: Iterable[float],
    thresholds: Iterable[float],
) -> list[dict[str, Any]]:
    """Construct a risk/coverage curve from a confidence threshold."""
    y, f = _validate_total_problem(outcomes, predictions)
    q = list(confidence)
    if len(q) != len(y):
        raise ValueError("confidence must have the same length as outcomes")
    curve = []
    for threshold in thresholds:
        mask = sum((1 << index) for index, value in enumerate(q) if value >= threshold)
        policy = policy_metrics(y, f, mask)
        policy["threshold"] = threshold
        policy["mean_confidence_accepted"] = (
            sum(q[index] for index in policy["accepted_indices"]) / policy["accepted"]
            if policy["accepted"] else None
        )
        curve.append(policy)
    return curve


def run_theory() -> dict[str, Any]:
    """Run the finite derivations against the existing four-row observation."""
    phase4 = run_phase4()
    old_rows = phase4_partial_predictor(phase4["held_out_C"]["evaluations"])
    old_metrics = evaluate(old_rows)
    outcomes = [row["outcome"] for row in old_rows]

    selector = [True, True, True, False]
    constant_total = [True, True, True, True]
    varying_total = [True, False, True, True]
    sparse_mask = 1  # accept only the first row

    selector_only = {
        "signature": selector_signature(selector),
        "phase4_partial_signature": {
            "kind": "selective_predictor",
            "prediction_image": [True],
            "prediction_image_size": 1,
            "prediction_varies": False,
        },
        "interpretation": "G's prefix relation selects; its represented prediction is constant on selected rows.",
    }
    induced = induced_prediction_image(
        ["same", "different", None, "same"], lambda value: value == "different"
    )

    constant_solver = exact_selective_solver(
        outcomes,
        constant_total,
        min_coverage=0.25,
        abstention_costs=[0.0, 0.25, 0.5, 1.0],
    )
    varying_solver = exact_selective_solver(
        outcomes,
        varying_total,
        min_coverage=0.25,
        max_rejected_risk=0.5,
        abstention_costs=[0.0, 0.25, 0.5, 1.0],
    )
    sparse_constant = policy_metrics(outcomes, constant_total, sparse_mask)

    calibrated_outcomes = [True, True, False, False]
    calibrated_predictions = [True, True, True, True]
    calibrated_confidence = [1.0, 1.0, 0.0, 0.0]

    return {
        "protocol": "agent1-continuation-selective-prediction-v1",
        "corpus_policy": "no new corpus; only existing Phase 4A four-row observation plus finite controlled masks",
        "formal_definitions": {
            "selector": "s: X -> {0,1}; chooses a subset and emits no label",
            "predictor": "f: X -> Y; emits one label for every x",
            "selective_predictor": "(s,f), equivalently g: X -> Y union {bottom}; f is evaluated only where s=1",
            "nonconstant_condition": "|f({x: s(x)=1})| >= 2; necessary and sufficient",
            "representation_decoder_condition": "|d(R(X_selected))| >= 2; two decoder-distinguishable represented states are necessary and sufficient",
        },
        "theorems": {
            "selector_cannot_predict_alone": {
                "status": "PROVED",
                "statement": "A selector has no label-valued output; a label requires an additional decoder or predictor.",
            },
            "image_characterization": {
                "status": "PROVED",
                "statement": "A selective predictor is variable exactly when its represented prediction image on the covered set has cardinality at least two.",
            },
            "selection_only_bound": {
                "status": "PROVED",
                "statement": "A selective predictor with one covered label has non-positive gain against the covered-set modal constant.",
            },
            "risk_decomposition": {
                "status": "PROVED",
                "statement": "For coverage C, accepted risk R_A and rejected risk R_R, full predictor risk is C*R_A + (1-C)*R_R.",
            },
            "conditional_risk_improvement": {
                "status": "PROVED",
                "statement": "For 0<C<1, selective risk is below full risk iff R_A < R_R; this alone says nothing about coverage or global action cost.",
            },
            "abstention_cost_boundary": {
                "status": "PROVED",
                "statement": "With externally specified abstention cost a, selective action risk beats full prediction iff a < R_R, assuming the same predictor and nonzero rejection.",
            },
            "policy_dominance": {
                "status": "PROVED",
                "statement": "A policy with at least as much coverage and no greater selective risk dominates another; no weights are needed.",
            },
        },
        "conditions": {
            "selector_only": selector_only,
            "induced_nonconstant_prediction": induced,
            "same_decoder_constant": {
                "representations": ["a", "b", None],
                "decoder": "constant True",
                "prediction_image_size": 1,
                "prediction_varies": False,
            },
        },
        "phase4a_known_result": {
            "status": "KNOWN_RESULT",
            "metrics": old_metrics,
            "finding": "G has coverage 3/4 but emits one label on all selected rows; corrected same-opportunity gain remains zero.",
        },
        "exact_solver": {
            "constant_predictor_with_selector": constant_solver,
            "varying_predictor_with_rejection_constraint": varying_solver,
            "complexity": "O(2^n*n) exact enumeration; finite-instance solver only",
        },
        "counterexamples": {
            "precision_can_worsen_global_system": {
                "status": "DISPROVED",
                "full_constant": policy_metrics(outcomes, constant_total, (1 << len(outcomes)) - 1),
                "sparse_perfect_conditioned": sparse_constant,
                "finding": "The one-row policy has conditional risk 0 but coverage 1/4; counting abstention as failure gives global success 1/4 versus 1/2 for full constant prediction.",
                "action_risk_at_cost_1": {
                    "full_constant": action_risk(policy_metrics(outcomes, constant_total, 15), 1.0),
                    "sparse_policy": action_risk(sparse_constant, 1.0),
                },
            },
            "risk_improvement_can_hide_errors": {
                "status": "KNOWN_RESULT",
                "policy": policy_metrics(outcomes, constant_total, 7),
                "finding": "The selected risk is 1/3, below full risk 1/2, while rejected risk is 1; the improvement is entirely compatible with concentrating the error in abstentions.",
            },
        },
        "calibration": {
            "groups": calibration_profile(calibrated_outcomes, calibrated_predictions, calibrated_confidence),
            "risk_coverage_curve": threshold_curve(
                calibrated_outcomes,
                calibrated_predictions,
                calibrated_confidence,
                [0.0, 0.5, 1.0, 1.1],
            ),
            "result": "KNOWN_RESULT",
            "interpretation": "Perfect group calibration makes threshold risk equal the average of 1-confidence on accepted rows; calibration does not choose a coverage target.",
        },
        "connections_after_formulation": {
            "selective_classification": "same partial-map object, with coverage and conditional risk exposed separately",
            "reject_option": "the abstention action is represented by bottom and receives an externally specified loss",
            "conformal_prediction": "a conformal set can be treated as a coverage/abstention policy, but its coverage guarantee is not a proof that a discovered relation predicts; the relation still needs a decoder and held-out evaluation",
        },
        "status_summary": {
            "PROVED": [
                "formal type distinction",
                "image condition for variable predictions",
                "selection-only non-positive gain",
                "risk decomposition and abstention boundary",
                "Pareto policy dominance",
            ],
            "KNOWN_RESULT": [
                "Phase 4A G is selection-only",
                "calibration and risk-coverage are distinct objects",
            ],
            "DISPROVED": [
                "higher conditional precision implies better global system",
            ],
            "CONJECTURE": [],
            "UNKNOWN": [
                "whether a future MAT-SI-discovered decoder can produce calibrated variable predictions without label leakage",
                "whether the finite conditions survive a larger held-out domain",
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MAT-SI selective prediction theory")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    result = run_theory()
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "protocol": result["protocol"],
        "phase4a_selection_only": result["phase4a_known_result"]["metrics"]["selection_only"],
        "constant_frontier_count": len(result["exact_solver"]["constant_predictor_with_selector"]["pareto_frontier"]),
        "varying_feasible_count": result["exact_solver"]["varying_predictor_with_rejection_constraint"]["feasible_policy_count"],
        "status_summary": result["status_summary"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
