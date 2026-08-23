import unittest

from matsi.future_equivalence import PARENT_COMMIT, run_future_equivalence_audit


class FutureEquivalenceDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_future_equivalence_audit()
        cls.cases = {case["case"]: case for case in cls.result["cases"]}

    def test_branch_parent_and_preregistered_prediction_are_explicit(self):
        self.assertEqual(PARENT_COMMIT, "c99cfd1")
        self.assertEqual(
            self.result["preregistered_prediction"]["status"],
            "PREREGISTERED_BEFORE_RESULTS",
        )
        self.assertGreater(len(self.result["preregistered_prediction"]["text"]), 20)

    def test_oracle_is_posthoc_and_sealed_holdout_is_after_freeze(self):
        for case in self.result["cases"]:
            self.assertFalse(case["oracle_used_during_discovery"])
            self.assertFalse(case["sealed_holdout_touched_before_freeze"])
            sequence = case["phase_sequence"]
            self.assertLess(sequence.index("SEALED_HOLDOUT"), sequence.index("GROUND_TRUTH/ORACLE"))
            self.assertFalse(case["ground_truth_used_for_decision"])
            self.assertEqual(case["decision_before_oracle"], case["decision_after_oracle"])

    def test_sealed_false_merge_is_not_ignored(self):
        deceptive = self.cases["cheap_probes_hide_later_difference"]
        self.assertGreater(deceptive["false_merge_pairs"], 0)
        self.assertEqual(deceptive["outcome_label"], "DECEPTIVE_FALSE_MERGE_REMAINS")
        self.assertGreater(deceptive["posthoc_oracle_comparison"]["false_merge_pairs"], 0)

    def test_subset_baseline_false_merge_and_refinement_contrast(self):
        dense = self.cases["dense_redundant"]
        superincreasing = self.cases["superincreasing"]

        self.assertGreater(dense["baseline_sampled_future_queries"]["false_merge_pairs"], 0)
        self.assertEqual(dense["false_merge_pairs"], 0)
        self.assertEqual(dense["outcome_label"], "RECOVERED_QUOTIENT")
        self.assertGreater(dense["discovery_queries"], dense["baseline_sampled_future_queries"]["discovery_queries"])
        self.assertLess(dense["discovery_queries"], dense["oracle_query_count"])

        self.assertGreater(superincreasing["baseline_sampled_future_queries"]["false_merge_pairs"], 0)
        self.assertGreater(superincreasing["false_merge_pairs"], 0)
        self.assertEqual(superincreasing["outcome_label"], "PARTIAL_OR_UNRESOLVED_RECOVERY")

    def test_near_maximal_control_stops_without_successful_compression(self):
        control = self.cases["almost_every_history_distinct"]
        self.assertEqual(control["ground_truth_class_count"], control["raw_history_count"])
        self.assertEqual(control["outcome_label"], "NO_USEFUL_COMPRESSION")
        self.assertEqual(control["stop_state"], "STOP_NO_GAIN")

    def test_fallback_budget_cannot_be_exceeded_silently(self):
        for case in self.result["cases"]:
            discovery_validation_queries = case["discovery_queries"] + case["validation_queries"]
            fallback_budget = case["fallback"]["query_budget"]
            self.assertLessEqual(discovery_validation_queries, fallback_budget)
            if discovery_validation_queries >= fallback_budget:
                self.assertEqual(case["stop_state"], "STOP_NO_GAIN")

    def test_parameters_are_frozen_before_holdout_and_not_changed_after(self):
        for case in self.result["cases"]:
            self.assertEqual(
                case["frozen_parameters_digest_before_sealed_holdout"],
                case["parameters_digest_after_sealed_holdout"],
            )
            self.assertEqual(case["frozen_parameters_digest"], case["parameters_digest_after_sealed_holdout"])

    def test_heterogeneous_resources_are_not_collapsed(self):
        for case in self.result["cases"]:
            self.assertTrue(case["resource_policy"]["heterogeneous_units_kept_separate"])
            self.assertFalse(case["resource_policy"]["scalar_collapsed"])
            self.assertFalse(case["resource_policy"]["lift_gain_declared"])
        self.assertTrue(self.result["metrics_policy"]["resource_vector"])

    def test_all_cases_and_posthoc_metrics_are_reported(self):
        self.assertEqual(len(self.result["cases"]), 10)
        for case in self.result["cases"]:
            for field in (
                "raw_history_count",
                "discovered_class_count",
                "ground_truth_class_count",
                "discovery_queries",
                "validation_queries",
                "sealed_holdout_queries",
                "refinement_rounds",
                "counterexamples_found",
                "splits_per_round",
                "false_merge_groups",
                "false_merge_pairs",
                "false_split_groups",
                "false_split_pairs",
                "sealed_holdout_error",
                "representation_bytes",
                "class_assignment_bytes",
                "query_runtime",
                "discovery_runtime",
                "peak_candidate_class_count",
                "peak_state_count",
                "oracle_query_count",
                "oracle_construction_cost",
                "baseline_raw_cost",
                "valid_history_merges",
                "discovery_queries_per_valid_history_merge",
            ):
                self.assertIn(field, case)


if __name__ == "__main__":
    unittest.main()
