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
        self.assertTrue(summary["negative_rejected"])
        comparison = self.result["families"]["A_affine_lift"]["resource_comparison"]
        self.assertEqual(comparison["status"], "NOT_CLAIMED")
        self.assertIn("dpll_nodes", comparison["vector_fields"])
        self.assertIn("gf2_row_xor_ops", comparison["vector_fields"])
        self.assertNotIn("positive_solver_work_reduced", summary)

    def test_future_quotient_rejects_coarse_residue(self):
        summary = self.result["families"]["B_future_quotient"]["summary"]
        self.assertTrue(summary["dense_has_exact_compression"])
        self.assertTrue(summary["dense_full_residual_is_exact"])
        self.assertTrue(summary["dense_coarse_projection_rejected"])
        self.assertTrue(summary["superincreasing_has_no_residual_collision"])
        self.assertTrue(summary["superincreasing_has_dead_future_collapse"])
        self.assertTrue(summary["approximate_discovery_without_oracle"])
        for case in self.result["families"]["B_future_quotient"]["cases"]:
            self.assertEqual(case["oracle"]["label"], "GROUND_TRUTH/ORACLE")
            self.assertFalse(case["approximate_discovery"]["oracle_used_for_discovery"])
            self.assertGreater(case["approximate_discovery"]["discovery_cost"]["sampled_future_queries"], 0)

    def test_pi_is_a_negative_local_predictor_control(self):
        family = self.result["families"]["C_pi_local_negative"]
        summary = family["summary"]
        self.assertEqual(summary["comparison_status"], "DESCRIPTIVE_ONLY_UNTIL_PREREGISTERED_TEST")
        self.assertTrue(family["parameter_freeze"]["frozen_before_heldout"])
        self.assertEqual(len(family["null_replicates"]["random"]), 5)
        self.assertEqual(len(family["null_replicates"]["shuffled_pi"]), 5)
        self.assertTrue(summary["planted_rule_detected"])

    def test_record_contract_and_phase_boundary_are_explicit(self):
        contract = self.result["observability_contract"]
        self.assertEqual(contract["record_kind"], "derived_audit_record")
        self.assertEqual(contract["mandatory_fields"], ["before", "intervention", "after", "provenance"])
        for record in contract["records"]:
            self.assertEqual(set(record), {"kind", "before", "intervention", "after", "provenance", "resources", "residue"})
            self.assertEqual(record["kind"], "derived_audit_record")
            self.assertEqual(record["provenance"]["record_kind"], "derived_audit_record")
            self.assertNotEqual(record["before"]["state_digest"], record["after"]["state_digest"])
            self.assertFalse(record["resources"]["scalar_collapsed"])
        gate = self.result["gate"]
        self.assertEqual(gate["decision"], "KEEP-SPECULATIVE")


if __name__ == "__main__":
    unittest.main()
