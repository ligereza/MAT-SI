import unittest

from matsi.order_dimensions import run_order_dimension_audit


class OrderDimensionsAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_order_dimension_audit()

    def test_affine_lift_requires_negative_controls_and_preserves_semantics(self):
        summary = self.result["families"]["A_affine_lift"]["summary"]
        self.assertTrue(summary["positive_detected"])
        self.assertTrue(summary["positive_semantics_preserved"])
        self.assertTrue(summary["positive_solver_work_reduced"])
        self.assertTrue(summary["negative_rejected"])

    def test_future_quotient_rejects_coarse_residue(self):
        summary = self.result["families"]["B_future_quotient"]["summary"]
        self.assertTrue(summary["dense_has_exact_compression"])
        self.assertTrue(summary["dense_full_residual_is_exact"])
        self.assertTrue(summary["dense_coarse_projection_rejected"])
        self.assertTrue(summary["superincreasing_has_no_collapse"])

    def test_pi_is_a_negative_local_predictor_control(self):
        summary = self.result["families"]["C_pi_local_negative"]["summary"]
        self.assertTrue(summary["pi_is_not_stronger_than_random"])
        self.assertTrue(summary["pi_is_not_stronger_than_shuffled"])
        self.assertTrue(summary["planted_rule_detected"])

    def test_record_contract_and_phase_boundary_are_explicit(self):
        contract = self.result["observability_contract"]
        self.assertEqual(contract["mandatory_fields"], ["before", "intervention", "after", "provenance"])
        for record in contract["records"]:
            self.assertEqual(set(record), {"before", "intervention", "after", "provenance", "resources", "residue"})
            self.assertFalse(record["resources"]["scalar_collapsed"])
        gate = self.result["gate"]
        self.assertEqual(gate["decision"], "KEEP-SPECULATIVE")
        self.assertFalse(gate["phase5_started"])
        self.assertFalse(gate["accepted_frontier_modified"])
        self.assertFalse(gate["main_modified"])


if __name__ == "__main__":
    unittest.main()
