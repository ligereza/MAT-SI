import unittest

from matsi.symbolic_overapprox import (
    AffineDelta,
    BooleanBox,
    ConcreteWitness,
    affine_box_bounds,
    audit_box_relation,
    certify_box_decision,
    refine_fixed_bit,
    run_symbolic_overapprox_suite,
    underapproximation_witnesses,
)


class SymbolicOverapproxTests(unittest.TestCase):
    def test_strict_overapprox_can_certify_identify_without_enumeration(self):
        dimension = 32
        omega = BooleanBox(dimension, {0: 1})
        abstract = BooleanBox(dimension)
        delta = AffineDelta(1, (1,) + (0,) * (dimension - 1))
        self.assertEqual(audit_box_relation(omega, abstract)["status"], "SOUND_STRICT_OVERAPPROXIMATION")
        result = certify_box_decision(abstract, delta)
        self.assertEqual(result["decision"], "CERTIFIED_IDENTIFY")
        self.assertEqual(result["bounds"]["enumerated_worlds"], 0)
        self.assertEqual(abstract.world_count, 2**32)

    def test_strict_overapprox_can_certify_direct(self):
        omega = BooleanBox(8, {0: 1})
        abstract = BooleanBox(8)
        delta = AffineDelta(-2, (-1,) + (0,) * 7)
        self.assertEqual(audit_box_relation(omega, abstract)["status"], "SOUND_STRICT_OVERAPPROXIMATION")
        self.assertEqual(certify_box_decision(abstract, delta)["decision"], "CERTIFIED_DIRECT")

    def test_coarse_box_abstains_and_certified_refinement_separates(self):
        dimension = 16
        delta = AffineDelta(3, (2, -5) + (0,) * (dimension - 2))
        coarse = BooleanBox(dimension)
        self.assertEqual(certify_box_decision(coarse, delta)["decision"], "ABSTAIN_COARSE_ABSTRACTION")
        refined = refine_fixed_bit(coarse, delta, 1, 0, True)
        self.assertEqual(refined["status"], "REFINED_BY_CERTIFIED_PREDICATE")
        self.assertEqual(refined["after"]["decision"], "CERTIFIED_IDENTIFY")

    def test_real_negative_world_survives_without_spurious_certificate(self):
        dimension = 16
        delta = AffineDelta(3, (2, -5) + (0,) * (dimension - 2))
        coarse = BooleanBox(dimension)
        refinement = refine_fixed_bit(coarse, delta, 1, 0, False)
        self.assertEqual(refinement["status"], "REFINEMENT_REJECTED_REAL_OR_UNKNOWN")
        self.assertEqual(refinement["after"]["decision"], "ABSTAIN_COARSE_ABSTRACTION")
        witness = underapproximation_witnesses(
            (ConcreteWitness((0, 1) + (0,) * (dimension - 2), "real"),),
            delta,
        )
        self.assertEqual(witness["refutes"], "UNIVERSAL_IDENTIFY")

    def test_irreducible_ambiguity_has_both_sign_witnesses(self):
        delta = AffineDelta(1, (-2,))
        box = BooleanBox(1)
        self.assertEqual(certify_box_decision(box, delta)["decision"], "ABSTAIN_COARSE_ABSTRACTION")
        witnesses = underapproximation_witnesses(
            (ConcreteWitness((0,), "positive"), ConcreteWitness((1,), "negative")),
            delta,
        )
        self.assertEqual(witnesses["refutes"], "UNIVERSAL_IDENTIFY")

    def test_previous_plus_four_minus_one_regression(self):
        delta = AffineDelta(4, (-5,))
        box = BooleanBox(1)
        result = certify_box_decision(box, delta)
        self.assertEqual(result["decision"], "ABSTAIN_COARSE_ABSTRACTION")
        self.assertEqual(result["bounds"]["lower"], "-1")
        observed = underapproximation_witnesses((ConcreteWitness((0,), "observed"),), delta)
        self.assertEqual(observed["L_witnesses"][0]["delta"], "4")

    def test_unsound_box_relation_is_rejected_as_universal_basis(self):
        omega = BooleanBox(2)
        wrong = BooleanBox(2, {1: 0})
        relation = audit_box_relation(omega, wrong)
        self.assertEqual(relation["status"], "UNSOUND_ABSTRACTION")

    def test_affine_bounds_are_exact_on_a_small_box(self):
        box = BooleanBox(3, {0: 1})
        delta = AffineDelta(2, (-3, 4, -1))
        bounds = affine_box_bounds(box, delta)
        self.assertEqual(bounds["lower"], "-2")
        self.assertEqual(bounds["upper"], "3")

    def test_suite_exposes_required_statuses(self):
        result = run_symbolic_overapprox_suite()
        statuses = {claim["status"] for claim in result["claims"]}
        self.assertTrue({"PROVED", "KNOWN_RESULT", "DISPROVED", "UNKNOWN"} <= statuses)
        self.assertEqual(result["gate"], "SOUND_ENVELOPE_CAN_REPLACE_EXACT_CLOSURE_FOR_SIGN_SEPARATION")


if __name__ == "__main__":
    unittest.main()
