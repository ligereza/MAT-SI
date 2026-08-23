import unittest

from matsi.order_width import (
    FACTOR_STATE_BUDGET,
    PARENT_COMMIT,
    build_cases,
    discover_order,
    run_order_width_audit,
)


class OrderWidthAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_order_width_audit()
        cls.cases = {case["case"]: case for case in cls.result["cases"]}

    def test_exact_parent_and_preregistered_boundaries(self):
        self.assertEqual(PARENT_COMMIT, "f17d1ff")
        self.assertEqual(self.result["parent_commit"], "f17d1ff")
        self.assertEqual(
            self.result["preregistered_predictions"]["status"],
            "PREREGISTERED_BEFORE_RESULTS",
        )
        self.assertFalse(self.result["method_boundaries"]["oracle_used_for_discovery"])
        self.assertFalse(self.result["method_boundaries"]["solve_result_can_change_frozen_order"])

    def test_all_small_orders_agree_with_brute_force(self):
        for case in self.result["cases"]:
            brute_force = case["resources"]["brute_force"]
            if brute_force is None:
                continue
            exact_counts = {
                order["exact_count"]
                for order in case["orders"]
                if order["status"] == "FREEZE"
            }
            if not exact_counts:
                self.assertTrue(all(order["status"] == "STOP_NO_GAIN" for order in case["orders"]))
                continue
            self.assertEqual(exact_counts, {brute_force["exact_count"]}, case["case"])
            self.assertNotIn(False, [
                order["exact_count_match_brute_force"]
                for order in case["orders"]
                if order["exact_count_match_brute_force"] is not None
            ])

    def test_discovery_does_not_consult_exact_width_and_reference_cannot_retrofit_decisions(self):
        for case in self.result["cases"]:
            self.assertTrue(all(not order["order_discovery_oracle_used"] for order in case["orders"]))
            self.assertTrue(case["decision_stability"]["all_orders_decided_before_posthoc_reference"])
            self.assertTrue(case["decision_stability"]["decision_fields_equal_before_after_reference"])
            for order in case["orders"]:
                if order["status"] == "STOP_NO_GAIN":
                    self.assertIsNone(order["exact_count"])

    def test_random_seed_is_frozen_and_discovery_has_no_width_oracle_input(self):
        case = next(case for case in build_cases() if case.name == "deceptive_random_sparse_seed_97")
        first = discover_order(case, "RANDOM", seed=430042)
        second = discover_order(case, "RANDOM", seed=430042)
        self.assertEqual(first["order"], second["order"])
        self.assertEqual(first["operations"], second["operations"])
        self.assertFalse(first["oracle_used_for_discovery"])
        self.assertEqual(first["seed"], 430042)

    def test_star_good_and_bad_are_same_instance_and_width_separates(self):
        star = self.cases["star_12_same_instance"]
        self.assertEqual(star["raw_input"]["edges"], [[0, leaf] for leaf in range(1, 12)])
        orders = {order["order_strategy"]: order for order in star["orders"]}
        self.assertEqual(orders["BAD_ORDER_CENTER_FIRST"]["order"], list(range(12)))
        self.assertEqual(orders["GOOD_ORDER_LEAVES_FIRST"]["order"], list(range(1, 12)) + [0])
        self.assertGreater(
            orders["BAD_ORDER_CENTER_FIRST"]["induced_width"],
            orders["GOOD_ORDER_LEAVES_FIRST"]["induced_width"],
        )
        self.assertEqual(
            orders["BAD_ORDER_CENTER_FIRST"]["exact_count"],
            orders["GOOD_ORDER_LEAVES_FIRST"]["exact_count"],
        )

    def test_factor_budget_stops_high_width_without_success_claim(self):
        high_width = self.cases["clique_16_scaling"]
        self.assertTrue(any(order["status"] == "STOP_NO_GAIN" for order in high_width["orders"]))
        for order in high_width["orders"]:
            if order["status"] == "STOP_NO_GAIN":
                self.assertGreater(order["peak_factor_states"], FACTOR_STATE_BUDGET)
                self.assertIsNone(order["exact_count"])
        self.assertIn("clique_16_scaling", self.result["summary"]["high_width_controls"])

    def test_separator_sufficiency_is_exhaustive_but_not_minimality(self):
        separator = self.cases["path_8"]["separator_sufficiency"]
        self.assertEqual(separator["status"], "CHECKED")
        self.assertTrue(separator["separator_sufficiency_exact"])
        self.assertGreater(separator["histories_collapsed_by_separator"], 0)
        self.assertEqual(
            separator["raw_past_assignment_count"] - separator["separator_state_count"],
            separator["histories_collapsed_by_separator"],
        )
        self.assertFalse(separator["minimality_claimed"])

    def test_resource_vector_keeps_units_and_does_not_declare_lift_gain(self):
        self.assertTrue(self.result["metrics_policy"]["resource_vector"])
        self.assertFalse(self.result["metrics_policy"]["scalar_collapsed"])
        self.assertFalse(self.result["metrics_policy"]["lift_gain_declared"])
        self.assertFalse(self.result["metrics_policy"]["brute_force_and_ve_units_compared_directly"])
        for case in self.result["cases"]:
            self.assertTrue(case["resources"]["variable_elimination"]["resource_vector_per_order"])
            self.assertIsInstance(case["order_discovery_cost"]["per_order"], list)

    def test_report_contains_same_n_families_gaps_and_machine_time_classification(self):
        self.assertGreaterEqual(len(self.result["cases"]), 20)
        self.assertEqual(len(self.result["summary"]["same_n_structures"]), 8)
        self.assertIn("runtime_ms", self.result["metrics_policy"]["machine_dependent_fields"])
        self.assertIn("raw_input_digest", self.result["metrics_policy"]["deterministic_fields"])
        self.assertIn("posthoc_reference", self.result["metrics_policy"]["posthoc_reference_fields"])
        self.assertTrue(any(case["width_gap_of_best_discovery"] is not None for case in self.result["cases"]))


if __name__ == "__main__":
    unittest.main()
