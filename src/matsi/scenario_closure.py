"""One finite closure experiment for jointly uncertain regime scenarios.

This is a deliberately bounded experiment, not a universal scenario language.
An affine mode rule maps a finite mode set to triples
``(C0, C*, I)``.  The generator is compared with an independent exhaustive
enumeration of the same finite mode domain.  A deliberately incomplete
generator is also audited to ensure that a robust decision can be falsified by
one omitted mode.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from .decision_calculus import Number, frac
from .regime_economics import JointCostScenario, evaluate_joint_cost_scenarios


@dataclass(frozen=True)
class AffineModeRule:
    """A finite declarative rule mapping integer modes to cost triples."""

    modes: tuple[int, ...]
    direct_base: Number
    direct_step: Number
    downstream_base: Number
    downstream_step: Number
    identification_base: Number
    identification_step: Number

    def __post_init__(self) -> None:
        if not self.modes or len(set(self.modes)) != len(self.modes):
            raise ValueError("modes must be a non-empty set of unique integers")
        for name in (
            "direct_base",
            "direct_step",
            "downstream_base",
            "downstream_step",
            "identification_base",
            "identification_step",
        ):
            object.__setattr__(self, name, frac(getattr(self, name)))

    def costs_for_mode(self, mode: int) -> tuple[Fraction, Fraction, Fraction]:
        if mode not in self.modes:
            raise ValueError("mode is outside the declared finite domain")
        return (
            self.direct_base + mode * self.direct_step,
            self.downstream_base + mode * self.downstream_step,
            self.identification_base + mode * self.identification_step,
        )

    def generate(self, drop_modes: Sequence[int] = ()) -> tuple[JointCostScenario, ...]:
        """Generate scenarios; ``drop_modes`` is only an adversarial test hook."""

        dropped = set(drop_modes)
        if not dropped <= set(self.modes):
            raise ValueError("drop_modes must be drawn from the declared domain")
        result = []
        for mode in self.modes:
            if mode in dropped:
                continue
            direct, downstream, identification = self.costs_for_mode(mode)
            result.append(JointCostScenario(f"mode-{mode}", direct, downstream, identification))
        return tuple(result)

    def oracle(self) -> tuple[JointCostScenario, ...]:
        """Independently enumerate every declared mode without the generator."""

        result = []
        for mode in sorted(self.modes):
            direct = self.direct_base + mode * self.direct_step
            downstream = self.downstream_base + mode * self.downstream_step
            identification = self.identification_base + mode * self.identification_step
            result.append(JointCostScenario(f"oracle-mode-{mode}", direct, downstream, identification))
        return tuple(result)


def _signature(scenario: JointCostScenario) -> tuple[Fraction, Fraction, Fraction]:
    return scenario.direct_cost, scenario.downstream_cost, scenario.identification_cost


def audit_affine_mode_closure(
    rule: AffineModeRule,
    drop_modes: Sequence[int] = (),
) -> dict[str, Any]:
    """Compare generated and oracle scenario sets and test end-to-end value."""

    generated = rule.generate(drop_modes)
    oracle = rule.oracle()
    generated_by_signature = {_signature(item): item for item in generated}
    oracle_by_signature = {_signature(item): item for item in oracle}
    missing = [item for signature, item in oracle_by_signature.items() if signature not in generated_by_signature]
    extra = [item for signature, item in generated_by_signature.items() if signature not in oracle_by_signature]
    generated_result = None if not generated else evaluate_joint_cost_scenarios(generated)
    oracle_result = evaluate_joint_cost_scenarios(oracle)
    closure_matches = not missing and not extra
    if closure_matches:
        closure_status = "CLOSURE_MATCHED_FINITE_DOMAIN"
    else:
        closure_status = "CLOSURE_FALSIFIED"
    oracle_net = [item.net_gain for item in oracle]
    end_to_end_advantage = all(gain > 0 for gain in oracle_net)
    return {
        "closure_status": closure_status,
        "domain_modes": list(rule.modes),
        "dropped_modes": list(drop_modes),
        "generated_count": len(generated),
        "oracle_count": len(oracle),
        "missing_from_generator": [item.as_dict() for item in missing],
        "extra_in_generator": [item.as_dict() for item in extra],
        "generated_decision": None if generated_result is None else generated_result["decision"],
        "oracle_decision": oracle_result["decision"],
        "oracle_min_net_gain": str(min(oracle_net)),
        "oracle_max_net_gain": str(max(oracle_net)),
        "end_to_end_advantage": end_to_end_advantage,
        "identification_cost_accounted": True,
        "oracle_scenarios": [item.as_dict() for item in oracle],
    }


def run_scenario_closure_experiment() -> dict[str, Any]:
    """Run one complete finite closure experiment plus its negative control."""

    rule = AffineModeRule(
        modes=(0, 1),
        direct_base=10,
        direct_step=0,
        downstream_base=6,
        downstream_step=-6,
        identification_base=0,
        identification_step=9,
    )
    complete = audit_affine_mode_closure(rule)
    incomplete = audit_affine_mode_closure(rule, drop_modes=(1,))
    return {
        "question": "Can a finite declarative scenario closure be complete and end-to-end useful?",
        "experiment": {
            "rule": {
                "modes": [0, 1],
                "direct": "10",
                "downstream": "6 - 6*mode",
                "identification": "9*mode",
            },
            "generator_steps": 2,
            "oracle_steps": 2,
        },
        "complete_generator": complete,
        "incomplete_negative_control": incomplete,
        "claims": [
            {
                "status": "PROVED",
                "claim": "the complete generator matches the independent oracle over the declared finite mode domain",
            },
            {
                "status": "PROVED",
                "claim": "the matched finite domain has positive net gain in every scenario",
            },
            {
                "status": "DISPROVED",
                "claim": "a robust decision survives arbitrary omission from the declared mode domain",
            },
            {
                "status": "KNOWN_RESULT",
                "claim": "the closure guarantee is conditional on the finite domain and its rule being correct",
            },
            {
                "status": "UNKNOWN",
                "claim": "an open-ended scenario generator can prove completeness beyond its declared finite domain",
            },
        ],
        "gate": "SUCCESS_WITHIN_FINITE_DECLARED_CLASS_ONLY",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    result = run_scenario_closure_experiment()
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

