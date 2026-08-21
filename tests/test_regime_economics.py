import unittest
from fractions import Fraction

from matsi.regime_economics import (
    evaluate_identification_economics,
    identification_adjusted_break_even_count,
    run_regime_economics_suite,
)
from matsi.regime_identification import AffineRoute, MetaProblemObservation


class RegimeEconomicsTests(unittest.TestCase):
    def setUp(self):
        self.observation = MetaProblemObservation(
            horizon="KNOWN",
            horizon_value=1,
            routes=(AffineRoute("direct", 0, 10), AffineRoute("compiled", 3, 2)),
            candidate_values_known=True,
        )

    def test_identification_is_selected_only_when_net_gain_is_strictly_positive(self):
        result = evaluate_identification_economics(self.observation, 10, 1)
        self.assertEqual(result["decision"], "IDENTIFY_AND_SOLVE")
        self.assertEqual(result["costs"]["identify_total"], "6")
        self.assertEqual(result["costs"]["net_gain_after_identification"], "4")

    def test_correct_classification_can_be_globally_worse(self):
        result = evaluate_identification_economics(self.observation, 10, 6)
        self.assertEqual(result["classification"]["status"], "CLASSIFIED")
        self.assertEqual(result["decision"], "SOLVE_DIRECT")
        self.assertEqual(result["costs"]["identify_total"], "11")

    def test_equality_is_not_called_a_gain(self):
        result = evaluate_identification_economics(self.observation, 10, 5)
        self.assertEqual(result["decision"], "SOLVE_DIRECT")
        self.assertEqual(result["costs"]["net_gain_after_identification"], "0")

    def test_adjusted_break_even_is_strict_and_exact(self):
        self.assertEqual(identification_adjusted_break_even_count(3, 10, 2, 0), 1)
        self.assertEqual(identification_adjusted_break_even_count(3, 10, 2, 2), 1)
        self.assertEqual(identification_adjusted_break_even_count(3, 10, 2, 6), 2)
        self.assertIsNone(identification_adjusted_break_even_count(3, 2, 2, 0))

    def test_unsupported_downstream_regime_abstains_even_at_zero_meta_cost(self):
        observation = MetaProblemObservation(
            horizon="UNKNOWN",
            routes=(AffineRoute("a", 1, 2), AffineRoute("b", 4, 1)),
            direct_rate=5,
            candidate_values_known=True,
        )
        result = evaluate_identification_economics(observation, 10, 0)
        self.assertEqual(result["status"], "ABSTAIN")

    def test_condition_matches_exhaustive_scalar_comparison(self):
        for direct in range(1, 8):
            for setup in range(0, 7):
                for transformed_rate in range(0, direct + 1):
                    for meta_cost in range(0, 7):
                        observation = MetaProblemObservation(
                            horizon="KNOWN",
                            horizon_value=1,
                            routes=(
                                AffineRoute("direct", 0, direct),
                                AffineRoute("candidate", setup, transformed_rate),
                            ),
                            candidate_values_known=True,
                        )
                        result = evaluate_identification_economics(observation, direct, meta_cost)
                        best = min(direct, setup + transformed_rate)
                        expected = "IDENTIFY_AND_SOLVE" if meta_cost + best < direct else "SOLVE_DIRECT"
                        self.assertEqual(result["decision"], expected)

    def test_suite_reports_proved_disproved_and_unknown(self):
        result = run_regime_economics_suite()
        statuses = {claim["status"] for claim in result["claims"]}
        self.assertTrue({"PROVED", "DISPROVED", "KNOWN_RESULT", "UNKNOWN"} <= statuses)
        self.assertEqual(result["identification_cost_exceeds_gain"]["decision"], "SOLVE_DIRECT")


if __name__ == "__main__":
    unittest.main()

