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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class CostInterval:
    """A non-negative interval for an identification cost.

    ``upper=None`` means that no finite upper bound is certified.  The
    interval is evidence about cost, not a probability distribution, so no
    expected value is inferred from it.
    """

    lower: Number
    upper: Number | None = None

    def __post_init__(self) -> None:
        low = _validate_cost(self.lower, "identification_cost_lower")
        high = None if self.upper is None else _validate_cost(self.upper, "identification_cost_upper")
        if high is not None and high < low:
            raise ValueError("identification cost upper bound must be >= lower bound")
        object.__setattr__(self, "lower", low)
        object.__setattr__(self, "upper", high)

    def as_dict(self) -> dict[str, str | None]:
        return {"lower": str(self.lower), "upper": None if self.upper is None else str(self.upper)}


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


def evaluate_bounded_identification_economics(
    observation: MetaProblemObservation,
    direct_cost: Number,
    identification_cost_lower: Number,
    identification_cost_upper: Number | None,
) -> dict[str, Any]:
    """Make a robust decision when identification cost is interval-valued.

    For an exact downstream gain ``G = C0-C*``:

    * ``I_max < G`` certifies identification for every admissible cost;
    * ``I_min >= G`` certifies direct solving;
    * otherwise the evidence cannot certify either strict comparison.

    The last case returns ``ABSTAIN_COST_UNCERTAIN`` and names direct solving
    as a safe fallback without silently treating it as a proven optimum.
    """

    direct = _validate_cost(direct_cost, "direct_cost")
    interval = CostInterval(identification_cost_lower, identification_cost_upper)
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
    gain = direct - best
    if gain <= 0:
        decision = "DIRECT_CERTIFIED"
        reason = "the exact downstream route has no strict gross advantage"
        status = "ROBUST_DECISION"
        fallback = None
    elif interval.upper is not None and interval.upper < gain:
        decision = "ROBUST_IDENTIFY_AND_SOLVE"
        reason = "the certified upper cost remains below the gross advantage"
        status = "ROBUST_DECISION"
        fallback = None
    elif interval.lower >= gain:
        decision = "DIRECT_CERTIFIED"
        reason = "even the certified lower cost consumes the gross advantage"
        status = "ROBUST_DECISION"
        fallback = None
    else:
        decision = "ABSTAIN_COST_UNCERTAIN"
        reason = "the cost interval crosses the strict break-even boundary"
        status = "ABSTAIN"
        fallback = "SOLVE_DIRECT"
    return {
        "status": status,
        "decision": decision,
        "classification": classification.as_dict(),
        "downstream_solution": solved,
        "costs": {
            "direct": str(direct),
            "downstream_exact": str(best),
            "gross_gain": str(gain),
            "identification_interval": interval.as_dict(),
        },
        "reason": reason,
        "safe_fallback": fallback,
        "certificate": "robust interval comparison without an expected-cost assumption",
    }


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

    bounded_identify = evaluate_bounded_identification_economics(observation, 10, 0, 4)
    bounded_direct = evaluate_bounded_identification_economics(observation, 10, 5, 8)
    bounded_abstain = evaluate_bounded_identification_economics(observation, 10, 4, 6)
    unbounded = evaluate_bounded_identification_economics(observation, 10, 0, None)

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
        "bounded_cost": {
            "robust_identify": bounded_identify,
            "robust_direct": bounded_direct,
            "crossing_interval_abstains": bounded_abstain,
            "unbounded_interval_abstains": unbounded,
        },
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
            {
                "status": "PROVED",
                "claim": "for an exact downstream gain, interval bounds yield a robust identify/direct/abstain trichotomy",
            },
            {
                "status": "DISPROVED",
                "claim": "an interval crossing the break-even boundary can certify a strict choice without extra evidence",
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
