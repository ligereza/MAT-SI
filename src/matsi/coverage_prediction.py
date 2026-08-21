"""Coverage-aware tests for relational prediction.

Phase 4A treated a relation that *selects* windows as if it predicted a
continuation on those windows.  This module isolates the distinction.

The experiment is deliberately binary and small.  A row contains an observed
outcome and either a represented prediction or an abstention.  Coverage and
conditional accuracy are kept as separate coordinates; no weighted score is
introduced.
"""

from __future__ import annotations

import argparse
from itertools import combinations
import json
from pathlib import Path
from typing import Any, Iterable

from .cross_domain import run_phase4


ROOT = Path(__file__).resolve().parents[2]


def _rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for index, row in enumerate(rows):
        outcome = row["outcome"]
        prediction = row.get("prediction")
        if not isinstance(outcome, bool):
            raise ValueError(f"row {index} has a non-boolean outcome")
        if prediction is not None and not isinstance(prediction, bool):
            raise ValueError(f"row {index} has a non-boolean prediction")
        result.append({"outcome": outcome, "prediction": prediction})
    return result


def _gain_counts(rows: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    covered = [row for row in rows if row["prediction"] is not None]
    correct = sum(row["prediction"] == row["outcome"] for row in covered)
    true_count = sum(row["outcome"] for row in covered)
    false_count = len(covered) - true_count
    modal_correct = max(true_count, false_count)
    return len(covered), correct, modal_correct, correct - modal_correct


def evaluate(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate one partial predictor without collapsing coverage into accuracy."""
    normalized = _rows(rows)
    covered_count, correct, modal_correct, gain_numerator = _gain_counts(normalized)
    total = len(normalized)
    covered_predictions = [row["prediction"] for row in normalized if row["prediction"] is not None]
    selection_only = bool(covered_predictions) and len(set(covered_predictions)) == 1
    return {
        "total": total,
        "covered": covered_count,
        "coverage": covered_count / total if total else None,
        "abstained": total - covered_count,
        "correct": correct,
        "wrong": covered_count - correct,
        "conditional_accuracy": correct / covered_count if covered_count else None,
        "same_opportunity_baseline_correct": modal_correct if covered_count else None,
        "same_opportunity_baseline_accuracy": (
            modal_correct / covered_count if covered_count else None
        ),
        "same_opportunity_gain_numerator": gain_numerator if covered_count else None,
        "same_opportunity_gain_denominator": covered_count if covered_count else None,
        "same_opportunity_gain": gain_numerator / covered_count if covered_count else None,
        "selection_only": selection_only,
        "prediction_varies": bool(covered_predictions) and len(set(covered_predictions)) > 1,
    }


def dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return whether left is at least as good on both explicit axes."""
    axes = ("coverage", "conditional_accuracy")
    if any(left[axis] is None or right[axis] is None for axis in axes):
        return False
    no_worse = all(left[axis] >= right[axis] for axis in axes)
    strictly_better = any(left[axis] > right[axis] for axis in axes)
    return no_worse and strictly_better


def pareto_frontier(candidates: dict[str, dict[str, Any]]) -> list[str]:
    """Return non-dominated candidate ids using coverage/accuracy only."""
    return [
        candidate_id
        for candidate_id, candidate in candidates.items()
        if not any(
            other_id != candidate_id and dominates(other, candidate)
            for other_id, other in candidates.items()
        )
    ]


def exact_binary_null(rows: Iterable[dict[str, Any]], max_cases: int = 100_000) -> dict[str, Any]:
    """Enumerate outcome arrangements while fixing the represented predictor.

    This is an exact exchangeability check, not a causal test.  Predictions and
    abstentions stay fixed; only the observed boolean outcomes are rearranged.
    The number of distinct arrangements is C(n, number_of_true_outcomes).
    """
    normalized = _rows(rows)
    n = len(normalized)
    true_count = sum(row["outcome"] for row in normalized)
    case_count = 1
    for index in range(1, min(true_count, n - true_count) + 1):
        case_count = case_count * (n - index + 1) // index
    if case_count > max_cases:
        raise ValueError(f"exact null has {case_count} cases; max_cases={max_cases}")

    observed = evaluate(normalized)
    observed_numerator = observed["same_opportunity_gain_numerator"]
    gains: dict[str, int] = {}
    at_least_observed = 0
    for true_positions in combinations(range(n), true_count):
        true_positions = set(true_positions)
        permuted = [
            {"outcome": index in true_positions, "prediction": row["prediction"]}
            for index, row in enumerate(normalized)
        ]
        metrics = evaluate(permuted)
        numerator = metrics["same_opportunity_gain_numerator"]
        key = (
            "undefined"
            if numerator is None
            else f"{numerator}/{metrics['same_opportunity_gain_denominator']}"
        )
        gains[key] = gains.get(key, 0) + 1
        if observed_numerator is not None and numerator >= observed_numerator:
            at_least_observed += 1

    return {
        "null": "outcomes exchangeable across fixed prediction/abstention positions",
        "total_rows": n,
        "total_true_outcomes": true_count,
        "distinct_cases": case_count,
        "observed_gain": observed["same_opportunity_gain"],
        "observed_gain_numerator": observed_numerator,
        "p_value_gain_at_least_observed": (
            at_least_observed / case_count if observed_numerator is not None else None
        ),
        "gain_distribution": dict(sorted(gains.items())),
        "interpretation": "descriptive finite-sample null; no causal conclusion",
    }


def phase4_partial_predictor(evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert the old G evaluation into the neutral partial-predictor form.

    A matched window receives the represented prediction ``True`` because the
    historical target was ``prediction_holds``.  An unmatched window abstains.
    This exposes that G's prediction is constant wherever it predicts.
    """
    return [
        {
            "outcome": bool(item["prediction_holds"]),
            "prediction": True if item["prefix_match"] else None,
        }
        for item in evaluations
    ]


def _fixture_rows() -> dict[str, list[dict[str, Any]]]:
    outcomes = [True, False, True, False]
    return {
        "selection_only": [
            {"outcome": outcome, "prediction": True if index < 3 else None}
            for index, outcome in enumerate(outcomes)
        ],
        "varying_prediction": [
            {"outcome": outcome, "prediction": [True, False, True, None][index]}
            for index, outcome in enumerate(outcomes)
        ],
        "full_constant": [
            {"outcome": outcome, "prediction": True}
            for outcome in outcomes
        ],
        "sparse_perfect": [
            {"outcome": outcome, "prediction": True if index == 0 else None}
            for index, outcome in enumerate(outcomes)
        ],
    }


def run_experiment() -> dict[str, Any]:
    fixtures = _fixture_rows()
    evaluated = {name: evaluate(rows) for name, rows in fixtures.items()}
    nulls = {name: exact_binary_null(rows) for name, rows in fixtures.items()}
    frontier = pareto_frontier(evaluated)

    phase4 = run_phase4()
    phase4_rows = phase4_partial_predictor(phase4["held_out_C"]["evaluations"])
    phase4_metrics = evaluate(phase4_rows)
    phase4_null = exact_binary_null(phase4_rows)

    return {
        "protocol": "agent1-continuation-coverage-prediction-v1",
        "question": (
            "When a relation selects only some observations, what evidence separates "
            "coverage from predictive content?"
        ),
        "formalization": {
            "row": "(observed outcome, represented prediction or abstention)",
            "coverage": "covered / total",
            "conditional_accuracy": "correct / covered",
            "same_opportunity_gain": "correct - modal correct on the identical covered set",
            "comparison": "Pareto dominance over coverage and conditional accuracy; no weighted score",
        },
        "proposition": {
            "statement": (
                "If every covered row receives the same prediction, its accuracy cannot "
                "exceed the modal constant predictor on that covered population."
            ),
            "proof": (
                "The predictor's correct count is the count of its one label. The modal "
                "constant chooses the larger of that count and its complement, so the "
                "difference is non-positive."
            ),
            "testable_consequence": "selection_only => same_opportunity_gain <= 0",
        },
        "counterexamples": {
            "selection_is_not_prediction": {
                "rows": fixtures["selection_only"],
                "metrics": evaluated["selection_only"],
                "exact_null": nulls["selection_only"],
                "finding": (
                    "75% coverage and 66.7% conditional accuracy, but zero gain: the "
                    "apparent relation only selects windows and repeats True."
                ),
            },
            "varying_prediction_can_add_information": {
                "rows": fixtures["varying_prediction"],
                "metrics": evaluated["varying_prediction"],
                "exact_null": nulls["varying_prediction"],
                "finding": (
                    "The same covered population with represented True/False predictions "
                    "reaches 100% conditional accuracy and gain 1/3; exact null p=1/6."
                ),
            },
            "accuracy_without_coverage_is_not_a_winner": {
                "metrics": {
                    "sparse_perfect": evaluated["sparse_perfect"],
                    "full_constant": evaluated["full_constant"],
                },
                "finding": (
                    "A perfect one-row predictor has no positive same-opportunity gain and "
                    "is dominated by the three-row varying predictor."
                ),
            },
        },
        "pareto": {
            "candidates": evaluated,
            "frontier": frontier,
            "dominated": [name for name in evaluated if name not in frontier],
            "meaning": "both high coverage/lower accuracy and lower coverage/higher accuracy survive without weights",
        },
        "phase4a_reanalysis": {
            "source": "existing held-out C evaluations; no Phase 4 source was changed",
            "rows": phase4_rows,
            "metrics": phase4_metrics,
            "exact_null": phase4_null,
            "finding": (
                "The corrected Phase 4A result is reproduced: G is selection-only, its "
                "same-opportunity gain is 0, and coverage remains a separate descriptive axis."
            ),
        },
        "complexity": {
            "evaluate": "O(n) time and O(n) space for normalized rows",
            "pareto_frontier": "O(k^2) comparisons for k candidates",
            "exact_binary_null": "O(C(n,t) * n) time and O(C(n,t)) output space",
            "limit": "exact null is intentionally finite-sample and not scalable without approximation",
        },
        "host_represented_derived": {
            "HOST": ["boolean arithmetic", "combination enumeration", "JSON serialization"],
            "REPRESENTED": ["outcomes", "predictions", "abstentions", "fixed covered set"],
            "DERIVED": ["coverage", "conditional accuracy", "same-opportunity gain", "Pareto frontier", "null distribution"],
        },
        "conclusion": {
            "answer": "The Phase 4A relation did not establish predictive transfer; it established a selection pattern with no same-opportunity gain.",
            "minimum_missing_relation": "A relation must emit varying represented predictions, or define a precommitted abstention utility; selection alone is insufficient.",
            "causal_status": "No causation claim: the exact null only tests outcome rearrangement under fixed predictions.",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MAT-SI coverage/prediction falsification")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    result = run_experiment()
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "protocol": result["protocol"],
        "frontier": result["pareto"]["frontier"],
        "phase4a_gain": result["phase4a_reanalysis"]["metrics"]["same_opportunity_gain"],
        "phase4a_coverage": result["phase4a_reanalysis"]["metrics"]["coverage"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
