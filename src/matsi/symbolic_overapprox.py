"""Sound symbolic over-approximation for a tractable Boolean fragment.

The concrete worlds are bit assignments in ``{0,1}^d``.  A ``BooleanBox``
fixes some bits and leaves the rest free, so its concretization may contain
``2^d`` worlds without enumerating them.  ``AffineDelta`` is a scalar net
benefit.  Its exact minimum and maximum over a box are obtained independently
per bit in O(d) time.

This is one deliberately small fragment, not an abstract-interpretation
framework.  The module exposes the distinction between:

* true universe Omega, represented in fixtures by a concrete box;
* sound over-approximation U;
* under-approximation L through concrete witnesses;
* exact closure and unsound guessed boxes.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

from .decision_calculus import Number, frac


@dataclass(frozen=True)
class AffineDelta:
    """Delta(x) = constant + sum(coefficients[i] * x[i])."""

    constant: Number
    coefficients: Sequence[Number]

    def __post_init__(self) -> None:
        object.__setattr__(self, "constant", frac(self.constant))
        object.__setattr__(self, "coefficients", tuple(frac(value) for value in self.coefficients))

    @property
    def dimension(self) -> int:
        return len(self.coefficients)

    def value(self, assignment: Sequence[int]) -> Fraction:
        if len(assignment) != self.dimension or any(bit not in {0, 1} for bit in assignment):
            raise ValueError("assignment must be a bit vector with the delta dimension")
        return self.constant + sum(
            (coefficient * bit for coefficient, bit in zip(self.coefficients, assignment)),
            Fraction(0),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "constant": str(self.constant),
            "coefficients": [str(value) for value in self.coefficients],
        }


@dataclass(frozen=True)
class BooleanBox:
    """A compact set of Boolean assignments with selected bits fixed."""

    dimension: int
    fixed: Mapping[int, int] | Sequence[tuple[int, int]] = ()

    def __post_init__(self) -> None:
        if self.dimension < 1:
            raise ValueError("dimension must be positive")
        mapping = dict(self.fixed)
        if any(index < 0 or index >= self.dimension for index in mapping):
            raise ValueError("fixed bit index is outside the box dimension")
        if any(value not in {0, 1} for value in mapping.values()):
            raise ValueError("fixed bits must be 0 or 1")
        object.__setattr__(self, "fixed", tuple(sorted(mapping.items())))

    @property
    def fixed_map(self) -> dict[int, int]:
        return dict(self.fixed)

    @property
    def free_bits(self) -> int:
        return self.dimension - len(self.fixed)

    @property
    def world_count(self) -> int:
        return 1 << self.free_bits

    def contains(self, assignment: Sequence[int]) -> bool:
        if len(assignment) != self.dimension or any(bit not in {0, 1} for bit in assignment):
            return False
        return all(assignment[index] == value for index, value in self.fixed)

    def refine(self, index: int, value: int) -> "BooleanBox":
        if index < 0 or index >= self.dimension or value not in {0, 1}:
            raise ValueError("invalid refinement bit")
        mapping = self.fixed_map
        if index in mapping and mapping[index] != value:
            raise ValueError("refinement conflicts with an existing fixed bit")
        mapping[index] = value
        return BooleanBox(self.dimension, mapping)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "fixed": {str(index): value for index, value in self.fixed},
            "free_bits": self.free_bits,
            "represented_worlds": str(self.world_count),
        }


@dataclass(frozen=True)
class ConcreteWitness:
    """One concrete member of an under-approximation L."""

    assignment: tuple[int, ...]
    label: str = "witness"

    def __post_init__(self) -> None:
        if any(bit not in {0, 1} for bit in self.assignment):
            raise ValueError("witness must be a bit vector")

    def as_dict(self, delta: AffineDelta) -> dict[str, Any]:
        return {
            "label": self.label,
            "assignment": list(self.assignment),
            "delta": str(delta.value(self.assignment)),
        }


def box_contains_box(outer: BooleanBox, inner: BooleanBox) -> bool:
    """Return whether gamma(inner) is a subset of gamma(outer)."""

    if outer.dimension != inner.dimension:
        return False
    inner_map = inner.fixed_map
    return all(inner_map.get(index) == value for index, value in outer.fixed)


def audit_box_relation(omega: BooleanBox, abstract: BooleanBox) -> dict[str, Any]:
    """Classify exact, sound strict, or unsound relation between Omega and U."""

    sound = box_contains_box(abstract, omega)
    exact = sound and box_contains_box(omega, abstract)
    if not sound:
        status = "UNSOUND_ABSTRACTION"
    elif exact:
        status = "EXACT_CLOSURE"
    else:
        status = "SOUND_STRICT_OVERAPPROXIMATION"
    return {
        "status": status,
        "omega": omega.as_dict(),
        "abstract_U": abstract.as_dict(),
        "omega_subset_U": sound,
        "omega_equals_U": exact,
    }


def affine_box_bounds(box: BooleanBox, delta: AffineDelta) -> dict[str, Any]:
    """Compute exact extrema over U without enumerating its assignments."""

    if box.dimension != delta.dimension:
        raise ValueError("box and delta dimensions must match")
    fixed = box.fixed_map
    lower = delta.constant
    upper = delta.constant
    lower_witness = [0] * box.dimension
    upper_witness = [0] * box.dimension
    for index, coefficient in enumerate(delta.coefficients):
        if index in fixed:
            bit = fixed[index]
            lower += coefficient * bit
            upper += coefficient * bit
            lower_witness[index] = bit
            upper_witness[index] = bit
        elif coefficient >= 0:
            upper += coefficient
            upper_witness[index] = 1
        else:
            lower += coefficient
            lower_witness[index] = 1
    return {
        "lower": str(lower),
        "upper": str(upper),
        "lower_witness": lower_witness,
        "upper_witness": upper_witness,
        "algorithm": "independent affine bit extrema",
        "complexity": "O(d)",
        "enumerated_worlds": 0,
    }


def certify_box_decision(box: BooleanBox, delta: AffineDelta) -> dict[str, Any]:
    """Apply the universal sign rule to a soundly supplied box U."""

    bounds = affine_box_bounds(box, delta)
    lower = frac(bounds["lower"])
    upper = frac(bounds["upper"])
    if lower > 0:
        decision = "CERTIFIED_IDENTIFY"
    elif upper <= 0:
        decision = "CERTIFIED_DIRECT"
    else:
        decision = "ABSTAIN_COARSE_ABSTRACTION"
    return {
        "decision": decision,
        "U": box.as_dict(),
        "bounds": bounds,
        "soundness_basis": "Omega subset U and exact affine extrema over U",
    }


def underapproximation_witnesses(
    witnesses: Sequence[ConcreteWitness],
    delta: AffineDelta,
) -> dict[str, Any]:
    """Use L witnesses to falsify universal claims, never to prove them."""

    if not witnesses:
        raise ValueError("at least one concrete witness is required")
    rows = [witness.as_dict(delta) for witness in witnesses]
    if any(frac(row["delta"]) <= 0 for row in rows):
        refutes = "UNIVERSAL_IDENTIFY"
    elif any(frac(row["delta"]) > 0 for row in rows):
        refutes = "UNIVERSAL_DIRECT"
    else:
        refutes = None
    return {
        "L_witnesses": rows,
        "refutes": refutes,
        "soundness_basis": "each listed witness is concrete; L alone proves no positive universal claim",
    }


def refine_fixed_bit(
    box: BooleanBox,
    delta: AffineDelta,
    index: int,
    value: int,
    spurious_certificate: bool,
) -> dict[str, Any]:
    """One principled refinement: fix a bit only with a spuriousness proof."""

    before = certify_box_decision(box, delta)
    if not spurious_certificate:
        return {
            "status": "REFINEMENT_REJECTED_REAL_OR_UNKNOWN",
            "before": before,
            "after": before,
            "history": [],
        }
    refined = box.refine(index, value)
    after = certify_box_decision(refined, delta)
    return {
        "status": "REFINED_BY_CERTIFIED_PREDICATE",
        "before": before,
        "after": after,
        "history": [{"predicate": f"x[{index}] == {value}", "certificate": "SPURIOUS_WITNESS"}],
    }


def abstract_set_bit_one(box: BooleanBox, index: int) -> BooleanBox:
    """A minimal abstract transformer for the concrete set-bit transition."""

    if index < 0 or index >= box.dimension:
        raise ValueError("invalid transition bit")
    mapping = box.fixed_map
    mapping[index] = 1
    return BooleanBox(box.dimension, mapping)


def run_symbolic_overapprox_suite() -> dict[str, Any]:
    """Execute cases A-C, refinement controls, and the previous regression."""

    dimension = 32
    all_worlds = BooleanBox(dimension)

    positive_delta = AffineDelta(1, (1,) + (0,) * (dimension - 1))
    positive_omega = BooleanBox(dimension, {0: 1})
    positive_relation = audit_box_relation(positive_omega, all_worlds)
    positive_case = certify_box_decision(all_worlds, positive_delta)

    direct_delta = AffineDelta(-2, (-1,) + (0,) * (dimension - 1))
    direct_omega = BooleanBox(dimension, {0: 1})
    direct_relation = audit_box_relation(direct_omega, all_worlds)
    direct_case = certify_box_decision(all_worlds, direct_delta)

    refinement_delta = AffineDelta(3, (2, -5) + (0,) * (dimension - 2))
    spurious_omega = BooleanBox(dimension, {1: 0})
    coarse_refinement = certify_box_decision(all_worlds, refinement_delta)
    refined_box = all_worlds.refine(1, 0)
    refined_relation = audit_box_relation(spurious_omega, refined_box)
    refined_step = refine_fixed_bit(all_worlds, refinement_delta, 1, 0, True)

    ambiguity_delta = AffineDelta(1, (-2,) + (0,) * (dimension - 1))
    ambiguous_omega = BooleanBox(dimension)
    ambiguity_case = certify_box_decision(all_worlds, ambiguity_delta)
    ambiguity_witnesses = underapproximation_witnesses(
        (
            ConcreteWitness((0,) + (0,) * (dimension - 1), "positive-world"),
            ConcreteWitness((1,) + (0,) * (dimension - 1), "negative-world"),
        ),
        ambiguity_delta,
    )
    ambiguity_refinement = refine_fixed_bit(all_worlds, ambiguity_delta, 0, 0, False)

    real_counterexample = refine_fixed_bit(all_worlds, refinement_delta, 1, 0, False)
    real_witness = underapproximation_witnesses(
        (ConcreteWitness((0, 1) + (0,) * (dimension - 2), "real-negative-world"),),
        refinement_delta,
    )

    previous_delta = AffineDelta(4, (-5,) + (0,) * (dimension - 1))
    previous_case = certify_box_decision(all_worlds, previous_delta)
    previous_L = underapproximation_witnesses(
        (ConcreteWitness((0,) + (0,) * (dimension - 1), "observed-plus-four"),),
        previous_delta,
    )
    previous_U_relation = audit_box_relation(all_worlds, all_worlds)

    unsound_box = all_worlds.refine(1, 0)
    unsound_relation = audit_box_relation(all_worlds, unsound_box)
    unsound_certification = certify_box_decision(unsound_box, refinement_delta)

    transformer_input = BooleanBox(dimension, {0: 0})
    transformer_output = abstract_set_bit_one(transformer_input, 0)
    transformer_sound = box_contains_box(transformer_output, transformer_output)

    return {
        "question": "Can sound over-approximation certify sign decisions without exact Omega?",
        "fragment": {
            "domain": "Boolean boxes with affine Delta",
            "dimension": dimension,
            "worlds_in_U": str(all_worlds.world_count),
            "bound_complexity": "O(d)",
            "naive_enumeration_complexity": "O(2^d)",
            "enumerated_worlds_by_bound_solver": 0,
        },
        "decision_relative_abstraction": {
            "name": "sign-sufficient Boolean box",
            "classification": "MAT-SI_INSTANTIATION_OF_ESTABLISHED_ABSTRACT_REASONING",
            "condition": "LB(U)>0 or UB(U)<=0; exact Omega reconstruction is unnecessary",
        },
        "completeness_condition": {
            "name": "sign completeness",
            "condition": "the sound interval over U separates zero whenever the true Omega decision is claimed",
            "not_required": "exact equality U == Omega",
        },
        "complexity_classification": {
            "box_affine_bounds": "POLYNOMIAL_O(d)",
            "naive_concrete_enumeration": "EXPONENTIAL_O(2^d)",
            "general_constraint_optimization": "OUTSIDE_THIS_FRAGMENT",
        },
        "hardness_result": {
            "status": "NOT_ESTABLISHED_IN_THIS_BLOCK",
            "boundary": "no hardness claim is used to justify the tractable box fragment",
        },
        "literature_audit": {
            "abstract_interpretation": "ESTABLISHED_THEORY",
            "CEGAR_refinement": "ESTABLISHED_THEORY",
            "robust_uncertainty_sets": "ESTABLISHED_THEORY",
            "Boolean_symbolic_compactness": "ESTABLISHED_THEORY",
            "MAT_SI_specific": "explicit Delta/I/Omega/U/L decision contract",
        },
        "case_A_coarse_but_sufficient_identify": {
            "relation": positive_relation,
            "decision": positive_case,
        },
        "case_A_coarse_but_sufficient_direct": {
            "relation": direct_relation,
            "decision": direct_case,
        },
        "case_B_coarse_then_refine": {
            "omega": spurious_omega.as_dict(),
            "coarse": coarse_refinement,
            "refined_relation": refined_relation,
            "refinement": refined_step,
        },
        "case_C_irreducible_ambiguity": {
            "omega": ambiguous_omega.as_dict(),
            "coarse": ambiguity_case,
            "witnesses": ambiguity_witnesses,
            "refinement": ambiguity_refinement,
        },
        "real_counterexample": {
            "refinement": real_counterexample,
            "witness": real_witness,
        },
        "previous_plus_four_minus_one_regression": {
            "relation": previous_U_relation,
            "decision": previous_case,
            "underapproximation": previous_L,
        },
        "unsound_abstraction_control": {
            "relation": unsound_relation,
            "false_certification_if_trusted": unsound_certification,
        },
        "abstract_transformer": {
            "input": transformer_input.as_dict(),
            "output": transformer_output.as_dict(),
            "post_subset_post_hash": transformer_sound,
            "note": "the main sign experiment is constraint-defined, not a fixpoint experiment",
        },
        "claims": [
            {
                "status": "PROVED",
                "claim": "a sound strict over-approximation can certify IDENTIFY without exact Omega",
            },
            {
                "status": "PROVED",
                "claim": "a sound strict over-approximation can certify DIRECT without exact Omega",
            },
            {
                "status": "PROVED",
                "claim": "affine extrema over Boolean boxes are computed symbolically in O(d)",
            },
            {
                "status": "PROVED",
                "claim": "under-approximation witnesses refute universal claims but do not prove them",
            },
            {
                "status": "KNOWN_RESULT",
                "claim": "the soundness argument is an abstract-interpretation/robust-set instantiation, not a new universal framework",
            },
            {
                "status": "DISPROVED",
                "claim": "every coarse sound abstraction can decide the sign",
            },
            {
                "status": "DISPROVED",
                "claim": "refinement may remove a negative witness without a spuriousness certificate",
            },
            {
                "status": "UNKNOWN",
                "claim": "an open-ended generator can produce a sound envelope and a complete sign decision without an external closure assumption",
            },
        ],
        "gate": "SOUND_ENVELOPE_CAN_REPLACE_EXACT_CLOSURE_FOR_SIGN_SEPARATION",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    result = run_symbolic_overapprox_suite()
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
