"""Exact economics of paying to identify a supported meta-problem regime.

``regime_identification`` answers whether the observed structure is sufficient
to select a solver family.  This module asks the next question: can that
observation cost more than the best downstream advantage it exposes?

For a known finite horizon and an exact affine solver, let ``C0`` be the
direct-solve cost, ``C*`` the exact best supplied route cost, and ``I`` the
cost of observing/classifying the regime.  The end-to-end comparison is

    direct:       C0
    identify:     I + C*

The decision is strict: identification is selected iff ``I < C0 - C*``.
This is intentionally a cost inequality, not a weighted score.
"""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from .decision_calculus import Number, frac
from .regime_identification import (
    AffineRoute,
    MetaProblemObservation,
    classify_meta_problem,
    solve_known_horizon_affine,
)


def _validate_cost(value: Number, name: str) -> Fraction:
    result = frac(value)
    if result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


def evaluate_identification_economics(
    observation: MetaProblemObservation,
    direct_cost: Number,
    identification_cost: Number,
) -> dict[str, Any]:
    """Make an exact direct-vs-identify decision for the affine regime.

    Other classified regimes are deliberately not silently approximated.  If
    the current module has no exact downstream solver for the observation, the
    result is ``ABSTAIN``.
    """

    direct = _validate_cost(direct_cost, "direct_cost")
    identify_cost = _validate_cost(identification_cost, "identification_cost")
    classification = classify_meta_problem(observation)
    if classification.status == "ABSTAIN":
        return {
            "status": "ABSTAIN",
            "reason": "regime was not identified with a supported certificate",
            "classification": classification.as_dict(),
        }
    if classification.regime != "KNOWN_HORIZON_AFFINE":
        return {
            "status": "ABSTAIN",
            "reason": "no exact downstream solver is implemented for this regime",
            "classification": classification.as_dict(),
        }

    solved = solve_known_horizon_affine(observation.routes, int(observation.horizon_value))
    best = frac(solved["optimal_cost"])
    total_identify = identify_cost + best
    gross_gain = direct - best
    net_gain = direct - total_identify
    if net_gain > 0:
        decision = "IDENTIFY_AND_SOLVE"
        certificate = "identification_cost < direct_cost - exact_downstream_cost"
    else:
        decision = "SOLVE_DIRECT"
        certificate = "identification_cost >= direct_cost - exact_downstream_cost"
    return {
        "status": "EXACT_META_DECISION",
        "decision": decision,
        "classification": classification.as_dict(),
        "downstream_solution": solved,
        "costs": {
            "direct": str(direct),
            "identification": str(identify_cost),
            "downstream_exact": str(best),
            "identify_total": str(total_identify),
            "gross_gain_before_identification": str(gross_gain),
            "net_gain_after_identification": str(net_gain),
            "strictly_allowed_identification_cost": str(gross_gain) if gross_gain > 0 else "0",
        },
        "certificate": certificate,
    }


def identification_adjusted_break_even_count(
    setup_cost: Number,
    direct_rate: Number,
    transformed_rate: Number,
    identification_cost: Number,
) -> int | None:
    """Least ``n`` with ``I + D + nA < nB`` under a scalar resource.

    The strict inequality matters: equality is not an end-to-end advantage.
    """

    setup = _validate_cost(setup_cost, "setup_cost")
    direct = _validate_cost(direct_rate, "direct_rate")
    transformed = _validate_cost(transformed_rate, "transformed_rate")
    identify = _validate_cost(identification_cost, "identification_cost")
    gain = direct - transformed
    if gain <= 0:
        return None
    quotient = (setup + identify) / gain
    return quotient.numerator // quotient.denominator + 1


def run_regime_economics_suite() -> dict[str, Any]:
    """Run the smallest exact counterexample suite for identification cost."""

    direct = AffineRoute("direct", 0, 10)
    transformed = AffineRoute("compiled", 3, 2)
    observation = MetaProblemObservation(
        horizon="KNOWN",
        horizon_value=1,
        routes=(direct, transformed),
        candidate_values_known=True,
    )
    useful = evaluate_identification_economics(observation, direct_cost=10, identification_cost=1)
    too_expensive = evaluate_identification_economics(observation, direct_cost=10, identification_cost=6)
    equality = evaluate_identification_economics(observation, direct_cost=10, identification_cost=5)

    unsupported = evaluate_identification_economics(
        MetaProblemObservation(
            horizon="UNKNOWN",
            routes=(AffineRoute("a", 1, 2), AffineRoute("b", 4, 1)),
            direct_rate=5,
            candidate_values_known=True,
        ),
        direct_cost=10,
        identification_cost=0,
    )

    return {
        "question": "When does regime identification pay for itself?",
        "model": {
            "direct": "C0",
            "identify_and_solve": "I + C*",
            "strict_condition": "I < C0 - C*",
        },
        "useful_identification": useful,
        "identification_cost_exceeds_gain": too_expensive,
        "equality_is_not_strict_improvement": equality,
        "unsupported_regime_stays_abstain": unsupported,
        "break_even": {
            "setup": "3",
            "direct_rate": "10",
            "transformed_rate": "2",
            "without_identification_cost": identification_adjusted_break_even_count(3, 10, 2, 0),
            "with_identification_cost_2": identification_adjusted_break_even_count(3, 10, 2, 2),
            "with_identification_cost_6": identification_adjusted_break_even_count(3, 10, 2, 6),
        },
        "claims": [
            {
                "status": "PROVED",
                "claim": "for an exact known-horizon downstream solver, identify iff I < C0 - C*",
            },
            {
                "status": "PROVED",
                "claim": "adding identification cost shifts affine break-even from D/g to (D+I)/g",
            },
            {
                "status": "DISPROVED",
                "claim": "a sound regime classification is automatically worth executing",
            },
            {
                "status": "KNOWN_RESULT",
                "claim": "this is an exact finite metareasoning cost comparison, not a novelty claim by itself",
            },
            {
                "status": "UNKNOWN",
                "claim": "a learned/partial classifier can estimate I tightly enough without hiding its own cost",
            },
        ],
        "phase_boundary": "No new corpus; no new product; no merge to main.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    result = run_regime_economics_suite()
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

