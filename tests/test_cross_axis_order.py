import unittest

from matsi.cross_axis_order import PARENT_COMMIT, run_cross_axis_order_audit


class CrossAxisOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_cross_axis_order_audit()
        cls.cases = {case["case"]: case for case in cls.result["cases"]}

    def test_parent_domain_and_scope_are_explicit(self):
        self.assertEqual(PARENT_COMMIT, "1d5a1d9")
        self.assertEqual(self.result["parent_commit"], "1d5a1d9")
        self.assertTrue(self.result["domain"]["all_axes_same_semantics"])
        self.assertFalse(self.result["domain"]["cross_domain_comparison_used"])
        self.assertFalse(self.result["scope_declarations"]["kernel_modified"])

    def test_all_requested_order_interface_fields_exist(self):
        fields = {
            "raw_history_count",
            "future_quotient_size",
            "separator_width",
            "separator_domain_cells",
            "distinct_messages",
            "message_description_bytes",
            "minimal_sufficient_messages",
            "interface_slack",
            "discovery_resources",
            "solve_resources",
        }
        for case in self.result["cases"]:
            self.assertTrue(fields.issubset(case), case["case"])
            self.assertEqual(case["separator_domain_cells"], 2 ** case["separator_width"])
            self.assertIn("wall_ms", case["solve_resources"])

    def test_controlled_quadrants_and_w_not_sufficient(self):
        quadrants = {(item["quadrant"], item["case"]) for item in self.result["controlled_quadrants"]}
        self.assertEqual(len(quadrants), 4)
        self.assertEqual(self.cases["small_q_small_w"]["future_quotient_size"], 1)
        self.assertEqual(self.cases["small_q_small_w"]["separator_width"], 1)
        self.assertEqual(self.cases["small_q_large_w"]["future_quotient_size"], 2)
        self.assertEqual(self.cases["small_q_large_w"]["separator_width"], 4)
        self.assertGreater(self.cases["large_q_small_w"]["future_quotient_size"], 2)
        self.assertEqual(self.cases["large_q_small_w"]["separator_width"], 1)
        self.assertTrue(self.result["gate"]["D_w_alone_not_sufficient"])

    def test_future_quotient_is_bounded_by_message_partition_and_compression_is_visible(self):
        self.assertTrue(self.result["bounds_and_constraints"]["q_le_distinct_messages_verified"])
        for case in self.result["cases"]:
            self.assertLessEqual(case["future_quotient_size"], case["distinct_messages"])
            self.assertEqual(
                case["minimal_sufficient_messages"],
                case["future_quotient_size"],
            )
        self.assertIn("small_q_large_w", self.result["minimality_attack"]["compression_cases"])
        self.assertGreater(self.cases["small_q_large_w"]["interface_slack"]["message_classes"], 0)

    def test_same_w_same_q_can_have_different_message_content_or_raw_cost(self):
        boolean = self.cases["same_w1_q2_boolean"]
        weighted = self.cases["same_w1_q2_weighted"]
        more_histories = self.cases["same_w1_q2_more_histories"]
        self.assertEqual((boolean["separator_width"], boolean["future_quotient_size"]), (1, 2))
        self.assertEqual((weighted["separator_width"], weighted["future_quotient_size"]), (1, 2))
        self.assertEqual((more_histories["separator_width"], more_histories["future_quotient_size"]), (1, 2))
        self.assertGreater(weighted["natural_interface"]["message_value_max"], boolean["natural_interface"]["message_value_max"])
        self.assertGreater(
            more_histories["solve_resources"]["future_response_operations"],
            boolean["solve_resources"]["future_response_operations"],
        )

    def test_minimality_attack_is_exhaustive_posthoc_and_decision_is_stable(self):
        for case in self.result["cases"]:
            attack = case["minimality_attack"]
            self.assertTrue(attack["fusion_complete"])
            self.assertTrue(attack["future_sufficiency_checked"])
            self.assertFalse(attack["oracle_used_during_discovery"])
            self.assertTrue(case["stop_rule"]["parameters_frozen_before_validation"])
            self.assertEqual(case["stop_rule"]["decision_before_posthoc"], case["stop_rule"]["decision_after_posthoc"])

    def test_negative_and_resource_boundaries_remain_explicit(self):
        self.assertFalse(self.result["metrics_policy"]["scalar_collapsed"])
        self.assertFalse(self.result["metrics_policy"]["lift_gain_declared"])
        self.assertFalse(self.result["scope_declarations"]["pipi_42_modified"])
        self.assertFalse(self.result["scope_declarations"]["pipi_43_modified"])
        self.assertTrue(self.result["anomalies_and_counterexamples"]["same_w_q_message_content_changes"])
        self.assertTrue(self.result["anomalies_and_counterexamples"]["same_w_q_raw_history_and_cost_changes"])


if __name__ == "__main__":
    unittest.main()
