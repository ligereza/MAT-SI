import unittest

from matsi.meta_lift import PARENT_COMMIT, candidate_library, run_meta_lift_audit, select_representation


class MetaLiftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_meta_lift_audit()
        cls.cases = {case["case"]: case for case in cls.result["cases"]}

    def test_parent_and_candidate_contract_are_explicit(self):
        self.assertEqual(PARENT_COMMIT, "4325a71")
        self.assertEqual(self.result["parent_commit"], "4325a71")
        expected = {
            "RAW_SEARCH", "GF2_LIFT", "HORN", "DUAL_HORN", "2SAT",
            "VARIABLE_ELIMINATION", "FUTURE_EQUIVALENCE_REFINEMENT",
            "SUBSET_SUM_DP", "MITM", "CARDINALITY_LIFT", "CLUSTER/LATTICE",
        }
        self.assertEqual(set(self.result["candidate_library"]), expected)
        for candidate in candidate_library():
            self.assertTrue(candidate.name)
            self.assertTrue(candidate.representation)
            self.assertTrue(candidate.solver_name)

    def test_selector_receives_blind_raw_input_only(self):
        forbidden = {"family", "difficulty", "expected_candidate", "audit_case_name", "easy", "hard"}
        for case in self.result["cases"]:
            self.assertTrue(forbidden.isdisjoint(case["raw_input"]), case["case"])
            self.assertFalse(case["selection"]["oracle_used_for_selection"])
            self.assertTrue(case["decision_boundary"]["selection_frozen_before_posthoc"])

    def test_specialized_selection_and_exact_count_are_observed(self):
        self.assertEqual(self.cases["blind_affine"]["selected"]["candidate"], "GF2_LIFT")
        self.assertEqual(self.cases["blind_horn"]["selected"]["candidate"], "HORN")
        self.assertEqual(self.cases["blind_dual_horn"]["selected"]["candidate"], "DUAL_HORN")
        self.assertEqual(self.cases["blind_2sat"]["selected"]["candidate"], "2SAT")
        self.assertIn(self.cases["blind_subset_sum"]["selected"]["candidate"], {"SUBSET_SUM_DP", "MITM"})
        self.assertEqual(self.cases["blind_cardinality"]["selected"]["candidate"], "CARDINALITY_LIFT")
        self.assertEqual(self.cases["blind_future_queries"]["selected"]["candidate"], "FUTURE_EQUIVALENCE_REFINEMENT")
        for case in self.result["cases"]:
            self.assertTrue(case["selected"]["exact_count_match_raw"], case["case"])

    def test_surface_variants_are_checked_and_robust_here(self):
        for case in self.result["cases"]:
            self.assertEqual(len(case["surface_variants"]), 2)
            self.assertTrue(case["surface_robust"], case["case"])
            self.assertTrue(all(not variant["selection_oracle_used"] for variant in case["surface_variants"]))
        self.assertEqual(self.result["summary"]["surface_robust_cases"], len(self.result["cases"]))

    def test_adversarial_false_lift_and_missed_lift_are_preserved(self):
        graph = self.cases["adversarial_low_width_graph"]
        self.assertTrue(graph["adversarial_audit"]["false_lift"])
        self.assertTrue(graph["adversarial_audit"]["missed_lift"])
        perturbed = self.cases["adversarial_perturbed_affine"]
        self.assertEqual(perturbed["selected"]["candidate"], "RAW_SEARCH")
        tight = self.cases["tight_budget_subset"]
        self.assertEqual(tight["selected"]["candidate"], "RAW_SEARCH")
        self.assertTrue(tight["adversarial_audit"]["missed_lift"])
        self.assertLessEqual(tight["selection"]["discovery_cost_total"], tight["discovery_budget"])

    def test_posthoc_oracle_is_reference_only_and_pareto_vectors_remain(self):
        for case in self.result["cases"]:
            oracle = case["posthoc_oracle"]
            self.assertFalse(oracle["oracle_used_for_selection"])
            self.assertTrue(oracle["pareto_frontier"])
            self.assertEqual(
                set(case["regret"]["comparable_vector_fields"]),
                {"discovery_ops", "transform_ops", "solve_ops", "memory_proxy"},
            )
            self.assertTrue(case["regret"]["scalar_is_only_posthoc_policy"])
            for method in oracle["all_methods"]:
                self.assertIn("certificate", method)
                self.assertIn("resource_vector", method)

    def test_selection_is_independent_of_external_case_labels(self):
        raw = self.cases["blind_affine"]["raw_input"]
        first = select_representation(raw, budget=60)
        altered = dict(raw)
        altered["metadata"] = {"external_label": "looks_like_subset_sum"}
        second = select_representation(altered, budget=60)
        self.assertEqual(first["selected_candidate"], second["selected_candidate"])
        self.assertFalse(first["oracle_used_for_selection"])

    def test_resource_and_scope_boundaries_are_explicit(self):
        self.assertTrue(self.result["selection_policy"]["budgeted"])
        self.assertTrue(self.result["selection_policy"]["oracle_used_for_selection"] is False)
        self.assertTrue(self.result["gate"]["false_lifts_preserved"])
        self.assertTrue(self.result["gate"]["negative_result"])
        self.assertFalse(self.result["scope_declarations"]["pipi_44_modified"])
        self.assertFalse(self.result["scope_declarations"]["codeine_modified"])


if __name__ == "__main__":
    unittest.main()
