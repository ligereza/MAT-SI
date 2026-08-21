import unittest

from matsi.selective_prediction import (
    action_risk,
    exact_selective_solver,
    induced_prediction_image,
    policy_metrics,
    predictor_signature,
    selector_signature,
    selective_predictor_signature,
)


class SelectivePredictionTests(unittest.TestCase):
    def test_formal_types_are_distinct(self):
        self.assertEqual(selector_signature([True, False])["kind"], "selector")
        self.assertEqual(predictor_signature([True, False])["kind"], "predictor")
        self.assertEqual(
            selective_predictor_signature([True, None])["kind"],
            "selective_predictor",
        )

    def test_nonconstant_condition_is_image_cardinality(self):
        constant = induced_prediction_image(["a", "b", None], lambda _: True)
        varying = induced_prediction_image(["a", "b", None], lambda value: value == "b")
        self.assertFalse(constant["prediction_varies"])
        self.assertEqual(constant["prediction_image_size"], 1)
        self.assertTrue(varying["prediction_varies"])
        self.assertEqual(varying["prediction_image_size"], 2)

    def test_risk_decomposition_and_abstention_cost(self):
        outcomes = [True, False, True, False]
        predictions = [True, True, True, True]
        full = policy_metrics(outcomes, predictions, 0b1111)
        selective = policy_metrics(outcomes, predictions, 0b0111)
        self.assertAlmostEqual(full["full_risk"], 0.5)
        self.assertAlmostEqual(selective["selective_risk"], 1 / 3)
        self.assertAlmostEqual(selective["rejected_risk"], 1.0)
        self.assertAlmostEqual(action_risk(selective, 1.0), 0.5)

    def test_exact_solver_enumerates_all_masks_and_applies_constraints(self):
        outcomes = [True, False, True, False]
        predictions = [True, False, True, True]
        result = exact_selective_solver(
            outcomes,
            predictions,
            min_coverage=0.5,
            max_rejected_risk=0.5,
        )
        self.assertEqual(result["enumerated_policy_count"], 16)
        self.assertGreater(result["feasible_policy_count"], 0)
        self.assertTrue(all(p["coverage"] >= 0.5 for p in result["policies"]))
        self.assertTrue(all(
            p["rejected_risk"] is None or p["rejected_risk"] <= 0.5
            for p in result["policies"]
        ))

    def test_sparse_precision_is_not_global_superiority(self):
        outcomes = [True, False, True, False]
        predictions = [True, True, True, True]
        full = policy_metrics(outcomes, predictions, 0b1111)
        sparse = policy_metrics(outcomes, predictions, 0b0001)
        self.assertLess(sparse["selective_risk"], full["full_risk"])
        self.assertLess(sparse["accepted"] - sparse["accepted_errors"], 2)
        self.assertGreater(action_risk(sparse, 1.0), action_risk(full, 1.0))


if __name__ == "__main__":
    unittest.main()
