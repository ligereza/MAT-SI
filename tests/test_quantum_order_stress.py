import unittest

from matsi.quantum_order_stress import PARENT_COMMIT, run_quantum_order_stress


class QuantumOrderStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_quantum_order_stress()
        cls.controls = {control["case"]: control for control in cls.result["controls"]}

    def test_parent_and_model_boundary(self):
        self.assertEqual(PARENT_COMMIT, "81be791")
        self.assertEqual(self.result["parent_commit"], "81be791")
        self.assertTrue(self.result["model_boundary"]["idealized_oracle_model"])
        self.assertEqual(self.result["model_boundary"]["full_gate_circuit_cost"], "NOT_MEASURED")
        self.assertFalse(self.result["model_boundary"]["scalar_speedup_claim"])

    def test_all_controls_report_the_same_resource_questions(self):
        self.assertEqual(
            {"grover_n16", "simon_n4", "period_finding_n16", "bernstein_vazirani_n4"},
            set(self.controls),
        )
        for control in self.controls.values():
            self.assertIn("raw_candidate_space", control)
            self.assertIn("classical", control)
            self.assertIn("quantum", control)
            self.assertIn("order_profile", control)
            self.assertIn("oracle_construction_cost", control)
            self.assertEqual(control["oracle_construction_cost"]["used_as_query_count"], False)
            self.assertEqual(control["quantum"]["oracle_construction_cost"]["gate_circuit_proxy"], "NOT_MEASURED")

    def test_grover_preserves_no_global_constraint_counterexample(self):
        grover = self.controls["grover_n16"]
        self.assertTrue(all(value == 0 for value in grover["quantum"]["independent_constraints_gained"]))
        self.assertTrue(all(value == 16 for value in grover["quantum"]["candidate_secret_space_after_each_observation"]))
        self.assertLess(grover["quantum"]["query_complexity_ideal"], grover["classical"]["query_complexity_worst_case"])
        self.assertGreater(grover["quantum"]["success_probability"], 0.9)

    def test_simon_tracks_global_constraints_and_secret_recovery(self):
        simon = self.controls["simon_n4"]
        self.assertEqual(simon["quantum"]["candidate_secret_space_after_each_observation"][-1], 1)
        self.assertEqual(sum(simon["quantum"]["independent_constraints_gained"]), 3)
        self.assertEqual(len(simon["quantum"]["measurements"]), 3)
        self.assertEqual(simon["prediction"]["actual_category_posthoc"], "EXPONENTIAL/STRUCTURAL QUERY SPEEDUP")
        self.assertEqual(simon["prediction"]["correct"], True)

    def test_period_control_keeps_toy_postprocessing_mismatch(self):
        period = self.controls["period_finding_n16"]
        self.assertEqual(period["quantum"]["query_complexity_ideal"], 1)
        self.assertEqual(period["quantum"]["candidate_secret_space_after_each_observation"], [1])
        self.assertEqual(period["actual_category_posthoc"], "NO_SIGNIFICANT_STRUCTURAL SPEEDUP")
        self.assertFalse(period["prediction"]["correct"])
        self.assertIn("continued-fraction", period["quantum"]["postprocessing_representation"])

    def test_prediction_is_frozen_before_heldout_actual_labels(self):
        protocol = self.result["prediction_protocol"]
        self.assertTrue(protocol["labels_revealed_after_prediction"])
        self.assertEqual(set(protocol["heldout_controls"]), {"simon_n4", "period_finding_n16"})
        self.assertEqual(protocol["heldout_accuracy"], 0.5)
        for control in self.controls.values():
            self.assertTrue(control["prediction"]["computed_before_actual_category_reveal"])

    def test_bv_is_calibration_and_tensor_bridge_is_not_claimed(self):
        bv = self.controls["bernstein_vazirani_n4"]
        self.assertEqual(bv["quantum"]["query_complexity_ideal"], 1)
        self.assertEqual(bv["quantum"]["candidate_secret_space_after_each_observation"], [1])
        self.assertEqual(bv["actual_category_posthoc"], "LINEAR_GLOBAL_CALIBRATION")
        self.assertEqual(self.result["optional_tensor_bridge"]["status"], "NOT_RUN")

    def test_profile_axes_and_negative_boundaries_are_visible(self):
        for control in self.controls.values():
            profile = control["order_profile"]
            for key in ("H_raw_candidate_space", "Q_after_first_observation", "W_observation_structure_width", "M_observation_description_bytes", "D_discovery_operations", "X_transform_operations", "S_postprocessing_operations", "I_independent_constraints_per_query", "K_profitable_refinement_depth"):
                self.assertIn(key, profile)
        self.assertTrue(self.result["negative_controls"]["period_postprocessing_mismatch_preserved"])
        self.assertFalse(self.result["metrics_policy"]["scalar_universal_claim"])
        self.assertTrue(self.result["metrics_policy"]["not_measured_fields"])
        self.assertFalse(self.result["scope_declarations"]["pipi_45_modified"])


if __name__ == "__main__":
    unittest.main()
