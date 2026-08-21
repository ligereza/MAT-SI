"""Partial identification of representation-conditioned meta-problem regimes.

This module is deliberately narrower than a universal meta-planner.  It asks
whether a small set of observable invariants is sufficient to select a known
mathematical regime.  The classifier is partial: when its premises are not
visible, it returns ``ABSTAIN`` instead of guessing.

The implemented regimes are:

``KNOWN_HORIZON_AFFINE``
    A finite explicit portfolio of reusable routes with costs
    ``C_i(n) = D_i + n A_i`` and a known integer horizon.  The solver is the
    exact lower-envelope evaluation at that horizon.

``UNKNOWN_HORIZON_TWO_SLOPE``
    One direct rate ``B`` and one reusable transformed route with setup cost
    ``D`` and rate ``A < B``.  The horizon is unknown.  The returned policy
    rents for ``floor(D / (B-A))`` uses and then buys.  It is certified
    2-competitive against the offline optimum for this model.

``COSTLY_OPTION_INSPECTION`` and ``EXPLICIT_ROUTE_GRAPH``
    These are identified as known families, but this module does not pretend
    to solve them.  The result names the appropriate solver family and keeps
    the decision at the meta-level.

No domain name is used by the classifier.  A regime is accepted only when the
corresponding structural facts are explicitly observed.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, Sequence

from .decision_calculus import Number, frac


HorizonStatus = Literal["KNOWN", "UNKNOWN", "UNOBSERVED"]
DecisionStatus = Literal["CLASSIFIED", "ABSTAIN"]


def _fraction_tuple(values: Sequence[Number]) -> tuple[Fraction, ...]:
    result = tuple(frac(value) for value in values)
    if any(value < 0 for value in result):
        raise ValueError("costs must be non-negative")
    return result


@dataclass(frozen=True)
class AffineRoute:
    """A reusable setup/rate option ``D + n A``."""

    id: str
    setup_cost: Number
    per_use_cost: Number

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("route id must be non-empty")
        setup = frac(self.setup_cost)
        rate = frac(self.per_use_cost)
        if setup < 0 or rate < 0:
            raise ValueError("route costs must be non-negative")
        object.__setattr__(self, "setup_cost", setup)
        object.__setattr__(self, "per_use_cost", rate)

    def total(self, horizon: int) -> Fraction:
        if horizon < 1:
            raise ValueError("horizon must be positive")
        return self.setup_cost + horizon * self.per_use_cost

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "setup_cost": str(self.setup_cost),
            "per_use_cost": str(self.per_use_cost),
        }


@dataclass(frozen=True)
class MetaProblemObservation:
    """Neutral structural evidence supplied to the partial classifier.

    The fields intentionally describe observability, not a domain ontology.
    ``candidate_values_known`` means that the relevant setup/rate values are
    available to the classifier; it does not assert that a route is useful.
    """

    horizon: HorizonStatus = "UNOBSERVED"
    horizon_value: int | None = None
    routes: tuple[AffineRoute, ...] = ()
    direct_rate: Number | None = None
    candidate_values_known: bool | None = None
    inspection_costs: tuple[Number, ...] = ()
    route_graph_complete: bool = False
    transition_generators_complete: bool = False
    objective_dimensions: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.horizon not in {"KNOWN", "UNKNOWN", "UNOBSERVED"}:
            raise ValueError("horizon must be KNOWN, UNKNOWN, or UNOBSERVED")
        if self.horizon == "KNOWN" and (self.horizon_value is None or self.horizon_value < 1):
            raise ValueError("a known horizon must be a positive integer")
        if self.horizon != "KNOWN" and self.horizon_value is not None:
            raise ValueError("horizon_value is only valid when horizon is KNOWN")
        if self.objective_dimensions < 1:
            raise ValueError("objective_dimensions must be positive")
        routes = tuple(self.routes)
        if len({route.id for route in routes}) != len(routes):
            raise ValueError("route ids must be unique")
        object.__setattr__(self, "routes", routes)
        if self.direct_rate is not None:
            direct = frac(self.direct_rate)
            if direct < 0:
                raise ValueError("direct_rate must be non-negative")
            object.__setattr__(self, "direct_rate", direct)
        object.__setattr__(self, "inspection_costs", _fraction_tuple(self.inspection_costs))


@dataclass(frozen=True)
class RegimeDecision:
    """The classifier output, including a soundness certificate or abstention."""

    status: DecisionStatus
    regime: str
    solver_family: str | None
    reasons: tuple[str, ...]
    observed: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "regime": self.regime,
            "solver_family": self.solver_family,
            "reasons": list(self.reasons),
            "observed": self.observed,
        }


def _observed_summary(observation: MetaProblemObservation) -> dict[str, Any]:
    return {
        "horizon": observation.horizon,
        "horizon_value": observation.horizon_value,
        "route_count": len(observation.routes),
        "route_ids": [route.id for route in observation.routes],
        "direct_rate_known": observation.direct_rate is not None,
        "candidate_values_known": observation.candidate_values_known,
        "inspection_cost_count": len(observation.inspection_costs),
        "route_graph_complete": observation.route_graph_complete,
        "transition_generators_complete": observation.transition_generators_complete,
        "objective_dimensions": observation.objective_dimensions,
    }


def _abstain(observation: MetaProblemObservation, *reasons: str) -> RegimeDecision:
    return RegimeDecision(
        status="ABSTAIN",
        regime="UNSUPPORTED_OR_UNOBSERVED",
        solver_family=None,
        reasons=tuple(reasons),
        observed=_observed_summary(observation),
    )


def classify_meta_problem(observation: MetaProblemObservation) -> RegimeDecision:
    """Classify only regimes whose structural premises are visible.

    This function is intentionally conservative.  In particular, it does not
    infer a two-slope problem from an arbitrary collection of routes and does
    not call an unknown generator space a shortest-path instance.
    """

    if observation.objective_dimensions != 1:
        return _abstain(
            observation,
            "scalar solver families are not sound for multiple incomparable objectives",
        )

    if observation.route_graph_complete and observation.transition_generators_complete:
        return RegimeDecision(
            status="CLASSIFIED",
            regime="EXPLICIT_ROUTE_GRAPH",
            solver_family="SHORTEST_PATH_OR_ASTAR",
            reasons=("route states and transitions are explicitly complete",),
            observed=_observed_summary(observation),
        )

    if (
        observation.horizon == "KNOWN"
        and observation.routes
        and observation.candidate_values_known is True
    ):
        return RegimeDecision(
            status="CLASSIFIED",
            regime="KNOWN_HORIZON_AFFINE",
            solver_family="EXACT_LOWER_ENVELOPE",
            reasons=(
                "finite reusable routes expose setup and per-use costs",
                "the reuse horizon is observed",
            ),
            observed=_observed_summary(observation),
        )

    if observation.horizon == "UNKNOWN":
        if observation.candidate_values_known is False and observation.inspection_costs:
            return RegimeDecision(
                status="CLASSIFIED",
                regime="COSTLY_OPTION_INSPECTION",
                solver_family="COSTLY_INFORMATION_OR_PANDORA_LIKE",
                reasons=(
                    "option values are not observed",
                    "inspection costs are observed",
                ),
                observed=_observed_summary(observation),
            )

        if (
            observation.candidate_values_known is True
            and observation.direct_rate is not None
            and len(observation.routes) == 1
            and observation.routes[0].per_use_cost < observation.direct_rate
        ):
            return RegimeDecision(
                status="CLASSIFIED",
                regime="UNKNOWN_HORIZON_TWO_SLOPE",
                solver_family="DETERMINISTIC_SKI_RENTAL_THRESHOLD",
                reasons=(
                    "one direct rate and one reusable transformed rate are observed",
                    "the transformed rate is strictly lower",
                    "the reuse horizon is explicitly unknown",
                ),
                observed=_observed_summary(observation),
            )

    return _abstain(
        observation,
        "the observed invariants do not identify a supported regime",
        "no solver guarantee is exported for this case",
    )


def solve_known_horizon_affine(
    routes: Sequence[AffineRoute],
    horizon: int,
) -> dict[str, Any]:
    """Evaluate the exact lower envelope at a known positive horizon."""

    options = tuple(routes)
    if not options:
        raise ValueError("at least one route is required")
    if horizon < 1:
        raise ValueError("horizon must be positive")
    totals = [(route, route.total(horizon)) for route in options]
    optimum = min(value for _route, value in totals)
    ties = sorted(route.id for route, value in totals if value == optimum)
    winner = ties[0]
    return {
        "status": "EXACT",
        "winner": winner,
        "ties": ties,
        "optimal_cost": str(optimum),
        "costs": {route.id: str(value) for route, value in sorted(totals, key=lambda item: item[0].id)},
        "complexity": {"time": "O(m)", "space": "O(m)"},
        "certificate": "minimum over all explicitly supplied affine route costs",
    }


def two_slope_threshold_policy(
    transformed: AffineRoute,
    direct_rate: Number,
) -> dict[str, Any]:
    """Return the deterministic unknown-horizon policy for two slopes.

    The policy rents for ``k = floor(D/(B-A))`` uses and buys before use
    ``k+1``.  If ``A >= B`` there is no strict rate improvement and no buying
    guarantee is returned.
    """

    direct = frac(direct_rate)
    gain = direct - transformed.per_use_cost
    if direct < 0:
        raise ValueError("direct_rate must be non-negative")
    if gain <= 0:
        return {
            "status": "NO_STRICT_RATE_IMPROVEMENT",
            "route": transformed.id,
            "rent_uses_before_buy": None,
            "competitive_ratio_bound": None,
            "certificate": "A >= B, so setup cannot be amortized by a lower rate",
        }
    threshold = transformed.setup_cost / gain
    rent_uses = threshold.numerator // threshold.denominator
    return {
        "status": "CERTIFIED_ONLINE_POLICY",
        "route": transformed.id,
        "rent_uses_before_buy": rent_uses,
        "buy_before_use": rent_uses + 1,
        "direct_rate": str(direct),
        "transformed_setup": str(transformed.setup_cost),
        "transformed_rate": str(transformed.per_use_cost),
        "saving_per_use": str(gain),
        "competitive_ratio_bound": "2",
        "certificate": "deterministic two-slope threshold against offline optimum",
    }


def simulate_two_slope_policy(
    transformed: AffineRoute,
    direct_rate: Number,
    horizon: int,
) -> dict[str, Any]:
    """Compare the threshold policy with the offline exact optimum."""

    if horizon < 1:
        raise ValueError("horizon must be positive")
    policy = two_slope_threshold_policy(transformed, direct_rate)
    direct = frac(direct_rate)
    offline = min(horizon * direct, transformed.total(horizon))
    if policy["rent_uses_before_buy"] is None:
        policy_cost = horizon * direct
        action = "RENT"
    else:
        rent_uses = int(policy["rent_uses_before_buy"])
        if horizon <= rent_uses:
            policy_cost = horizon * direct
            action = "RENT_THROUGHOUT"
        else:
            policy_cost = rent_uses * direct + transformed.setup_cost
            policy_cost += (horizon - rent_uses) * transformed.per_use_cost
            action = "RENT_THEN_BUY"
    if offline == 0:
        ratio: Fraction | None = Fraction(1) if policy_cost == 0 else None
    else:
        ratio = policy_cost / offline
    return {
        "horizon": horizon,
        "action": action,
        "policy_cost": str(policy_cost),
        "offline_optimum": str(offline),
        "competitive_ratio": None if ratio is None else str(ratio),
        "within_two": ratio is not None and ratio <= 2,
    }


def audit_two_slope_policy(
    transformed: AffineRoute,
    direct_rate: Number,
    max_horizon: int,
) -> dict[str, Any]:
    """Finite exact audit; the theorem itself is independent of the cutoff."""

    if max_horizon < 1:
        raise ValueError("max_horizon must be positive")
    rows = [simulate_two_slope_policy(transformed, direct_rate, horizon) for horizon in range(1, max_horizon + 1)]
    finite_ratios = [frac(row["competitive_ratio"]) for row in rows if row["competitive_ratio"] is not None]
    worst = max(finite_ratios, default=Fraction(1))
    worst_row = next(row for row in rows if row["competitive_ratio"] == str(worst))
    return {
        "status": "FINITE_AUDIT",
        "max_horizon": max_horizon,
        "rows": rows,
        "worst_horizon": worst_row["horizon"],
        "worst_ratio": str(worst),
        "within_certified_bound": worst <= 2,
    }


def solve_observed_problem(observation: MetaProblemObservation) -> dict[str, Any]:
    """Classify and execute only the solver whose premises were certified."""

    decision = classify_meta_problem(observation)
    result: dict[str, Any] = {"classification": decision.as_dict()}
    if decision.status == "ABSTAIN":
        result["status"] = "ABSTAIN"
        return result
    if decision.regime == "KNOWN_HORIZON_AFFINE":
        result["solution"] = solve_known_horizon_affine(observation.routes, int(observation.horizon_value))
        result["status"] = "SOLVED"
        return result
    if decision.regime == "UNKNOWN_HORIZON_TWO_SLOPE":
        result["solution"] = two_slope_threshold_policy(observation.routes[0], observation.direct_rate)
        result["status"] = "POLICY"
        return result
    result["status"] = "CLASSIFIED_BUT_SOLVER_DEFERRED"
    return result


def run_regime_identification_suite() -> dict[str, Any]:
    """Run the smallest falsification suite for the chosen research direction."""

    direct = AffineRoute("direct", 0, 10)
    compiled = AffineRoute("compiled", 3, 2)
    known = MetaProblemObservation(
        horizon="KNOWN",
        horizon_value=4,
        routes=(direct, compiled),
        candidate_values_known=True,
    )
    known_solution = solve_observed_problem(known)

    two_slope = AffineRoute("compiled", Fraction(51, 10), 0)
    unknown = MetaProblemObservation(
        horizon="UNKNOWN",
        routes=(two_slope,),
        direct_rate=5,
        candidate_values_known=True,
    )
    policy = solve_observed_problem(unknown)
    policy_audit = audit_two_slope_policy(two_slope, 5, 8)

    costly_inspection = MetaProblemObservation(
        horizon="UNKNOWN",
        candidate_values_known=False,
        inspection_costs=(2,),
    )
    costly = solve_observed_problem(costly_inspection)

    unsupported = MetaProblemObservation(
        horizon="UNKNOWN",
        routes=(AffineRoute("a", 1, 2), AffineRoute("b", 4, 1)),
        direct_rate=5,
        candidate_values_known=True,
    )
    ambiguous = solve_observed_problem(unsupported)

    short_horizon_no_gain = solve_observed_problem(
        MetaProblemObservation(
            horizon="KNOWN",
            horizon_value=1,
            routes=(AffineRoute("direct", 0, 10), AffineRoute("expensive_transform", 4, 9)),
            candidate_values_known=True,
        )
    )

    return {
        "question": "Can observable invariants identify a meta-problem regime before selecting a solver?",
        "direction": "representation-conditioned regime identification with abstention",
        "known_horizon": known_solution,
        "unknown_horizon": {"policy": policy, "audit": policy_audit},
        "costly_inspection": costly,
        "unsupported_negative_control": ambiguous,
        "regime_without_speedup_negative_control": short_horizon_no_gain,
        "claims": [
            {
                "status": "PROVED",
                "claim": "the known-horizon affine solver returns the exact minimum over supplied routes",
            },
            {
                "status": "PROVED",
                "claim": "the two-slope threshold policy is at most 2-competitive in its stated model",
            },
            {
                "status": "KNOWN_RESULT",
                "claim": "these two solver families are standard mathematical regimes, not a novelty claim",
            },
            {
                "status": "DISPROVED",
                "claim": "identifying a favorable regime implies that transformation is worthwhile",
            },
            {
                "status": "UNKNOWN",
                "claim": "regime identification lowers end-to-end cost after charging its own observation cost",
            },
        ],
        "phase_boundary": "No new corpus; no product; no merge to main.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    result = run_regime_identification_suite()
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

