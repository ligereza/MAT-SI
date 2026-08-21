import unittest

from matsi.coverage_prediction import (
    exact_binary_null,
    evaluate,
    pareto_frontier,
    phase4_partial_predictor,
    run_experiment,
)
from matsi.cross_domain import run_phase4


class CoveragePredictionTests(unittest.TestCase):
    def test_selection_only_cannot_beat_same_opportunity_mode(self):
        rows = [
            {"outcome": True, "prediction": True},
            {"outcome": False, "prediction": True},
            {"outcome": True, "prediction": True},
            {"outcome": False, "prediction": None},
        ]
        metrics = evaluate(rows)
        self.assertTrue(metrics["selection_only"])
        self.assertEqual(metrics["same_opportunity_gain_numerator"], 0)
        self.assertLessEqual(metrics["same_opportunity_gain"], 0)

    def test_varying_represented_predictions_survive_exact_null(self):
        rows = [
            {"outcome": True, "prediction": True},
            {"outcome": False, "prediction": False},
            {"outcome": True, "prediction": True},
            {"outcome": False, "prediction": None},
        ]
        metrics = evaluate(rows)
        null = exact_binary_null(rows)
        self.assertTrue(metrics["prediction_varies"])
        self.assertEqual(metrics["same_opportunity_gain_numerator"], 1)
        self.assertEqual(null["distinct_cases"], 6)
        self.assertAlmostEqual(null["p_value_gain_at_least_observed"], 1 / 6)

    def test_pareto_frontier_keeps_tradeoff_and_removes_strictly_dominated(self):
        result = run_experiment()["pareto"]
        self.assertIn("full_constant", result["frontier"])
        self.assertIn("varying_prediction", result["frontier"])
        self.assertNotIn("selection_only", result["frontier"])
        self.assertNotIn("sparse_perfect", result["frontier"])

    def test_phase4_g_is_selection_only_and_corrected_gain_is_zero(self):
        phase4 = run_phase4()
        rows = phase4_partial_predictor(phase4["held_out_C"]["evaluations"])
        metrics = evaluate(rows)
        self.assertTrue(metrics["selection_only"])
        self.assertEqual(metrics["covered"], 3)
        self.assertAlmostEqual(metrics["coverage"], 0.75)
        self.assertEqual(metrics["same_opportunity_gain"], 0.0)

    def test_exact_null_preserves_fixed_predictions_and_abstentions(self):
        rows = [
            {"outcome": True, "prediction": True},
            {"outcome": False, "prediction": None},
            {"outcome": True, "prediction": False},
        ]
        null = exact_binary_null(rows)
        self.assertEqual(null["distinct_cases"], 3)
        self.assertEqual(null["total_true_outcomes"], 2)
        self.assertEqual(null["total_rows"], 3)

    def test_all_abstentions_are_unknown_not_a_zero_gain_claim(self):
        null = exact_binary_null([
            {"outcome": True, "prediction": None},
            {"outcome": False, "prediction": None},
        ])
        self.assertIsNone(null["observed_gain"])
        self.assertIsNone(null["p_value_gain_at_least_observed"])
        self.assertEqual(null["gain_distribution"], {"undefined": 2})


if __name__ == "__main__":
    unittest.main()
