"""Direct attempt at a universal robust-decision theorem.

The candidate theorem is parameterized by a non-empty feasible scenario set
``Omega``.  For each scenario the net gain of identifying is

    Delta(omega) = direct(omega) - downstream(omega) - identification(omega)

The theorem classifies an exact ``Omega`` by the sign of ``Delta``.  The
important companion result is an impossibility witness: an observed subset
cannot justify a universal decision when two feasible supersets of that same
observation induce different outcomes.

This module therefore tests the universal claim directly instead of adding
more domain examples.  It does not claim that an open-ended representation
generator can produce a complete ``Omega``.
"""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from .regime_economics import JointCostScenario


def exact_universal_trichotomy(scenarios: Sequence[JointCostScenario]) -> dict[str, Any]:
    """Evaluate the candidate theorem on an explicitly supplied finite Omega."""

    items = tuple(scenarios)
    if not items:
        raise ValueError("Omega must be non-empty")
    gains = [item.net_gain for item in items]
    if all(gain > 0 for gain in gains):
        decision = "ROBUST_IDENTIFY_AND_SOLVE"
    elif all(gain <= 0 for gain in gains):
        decision = "DIRECT_CERTIFIED"
    else:
        decision = "ABSTAIN_JOINT_UNCERTAIN"
    return {
        "decision": decision,
        "inf_net_gain_finite": str(min(gains)),
        "sup_net_gain_finite": str(max(gains)),
        "scenario_count": len(items),
        "certificate": "exact finite instance of the universal trichotomy",
    }


def _signature(item: JointCostScenario) -> tuple[Fraction, Fraction, Fraction]:
    return item.direct_cost, item.downstream_cost, item.identification_cost


def exact_closure_check(
    declared: Sequence[JointCostScenario],
    universe: Sequence[JointCostScenario],
) -> dict[str, Any]:
    """Check exact equality of a declaration and an explicit finite universe."""

    declared_signatures = {_signature(item) for item in declared}
    universe_signatures = {_signature(item) for item in universe}
    missing = universe_signatures - declared_signatures
    extra = declared_signatures - universe_signatures
    return {
        "exact_closure": not missing and not extra,
        "missing_count": len(missing),
        "extra_count": len(extra),
        "universe_decision": exact_universal_trichotomy(universe)["decision"],
        "certificate": "exact only relative to the explicitly supplied finite universe",
    }


def partial_observation_impossibility(
    observed: Sequence[JointCostScenario],
    omitted: JointCostScenario,
) -> dict[str, Any]:
    """Show that the same partial observation cannot decide both possible worlds."""

    observed_items = tuple(observed)
    if not observed_items:
        raise ValueError("observed subset must be non-empty")
    if any(_signature(item) == _signature(omitted) for item in observed_items):
        raise ValueError("omitted scenario must be distinct from observed scenarios")
    observed_result = exact_universal_trichotomy(observed_items)
    extended_result = exact_universal_trichotomy(observed_items + (omitted,))
    differs = observed_result["decision"] != extended_result["decision"]
    return {
        "status": "IMPOSSIBILITY_WITNESS" if differs else "NO_DIFFERENCE_IN_THIS_WITNESS",
        "same_observation": [item.as_dict() for item in observed_items],
        "possible_world_observed_only": observed_result,
        "possible_world_with_omitted": {
            "omitted": omitted.as_dict(),
            "result": extended_result,
        },
        "universal_observation_only_rule_possible": not differs,
        "certificate": "any rule seeing only the observed subset returns the same output in both worlds",
    }


def run_universal_candidate_attempt() -> dict[str, Any]:
    """Run the direct theorem attempt and its closure counterexample."""

    observed = (JointCostScenario("observed", 10, 6, 0),)
    positive_extension = JointCostScenario("positive-extension", 10, 0, 9)
    omitted_counterexample = JointCostScenario("omitted-counterexample", 10, 9, 2)
    exact_universe = observed + (positive_extension,)
    partial = partial_observation_impossibility(observed, omitted_counterexample)
    exact = exact_universal_trichotomy(exact_universe)
    closure = exact_closure_check(exact_universe, exact_universe)
    incomplete_closure = exact_closure_check(observed, exact_universe)
    return {
        "question": "Can a universal robust-decision theorem avoid an exact closure assumption?",
        "candidate_theorem": {
            "for_nonempty_Omega": "identify iff inf Delta > 0; direct iff sup Delta <= 0; otherwise abstain",
            "finite_implementation": exact,
        },
        "exact_closure": closure,
        "incomplete_closure": incomplete_closure,
        "partial_observation_attack": partial,
        "claims": [
            {
                "status": "PROVED",
                "claim": "the trichotomy is sound and complete once the exact feasible set Omega is supplied",
            },
            {
                "status": "PROVED",
                "claim": "exact closure makes the finite instance an instance of the universal theorem",
            },
            {
                "status": "DISPROVED",
                "claim": "a partial observed subset alone can support a universal decision for all compatible supersets",
            },
            {
                "status": "KNOWN_RESULT",
                "claim": "the theorem is a general robust-set decision rule, not evidence of a new universal solver",
            },
            {
                "status": "UNKNOWN",
                "claim": "an open-ended representation generator can provide exact closure without an external completeness axiom",
            },
        ],
        "gate": "UNIVERSALITY_REQUIRES_VERIFIABLE_CLOSURE",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    result = run_universal_candidate_attempt()
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

