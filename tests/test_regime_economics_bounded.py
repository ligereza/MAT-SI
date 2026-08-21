import unittest

from matsi.regime_economics import (
    CostInterval,
    evaluate_bounded_identification_economics,
)
from matsi.regime_identification import AffineRoute, MetaProblemObservation


class BoundedRegimeEconomicsTests(unittest.TestCase):
    def setUp(self):
        self.observation = MetaProblemObservation(
            horizon="KNOWN",
            horizon_value=1,
            routes=(AffineRoute("direct", 0, 10), AffineRoute("compiled", 3, 2)),
            candidate_values_known=True,
        )

    def test_upper_bound_below_gain_certifies_identification(self):
        result = evaluate_bounded_identification_economics(self.observation, 10, 0, 4)
        self.assertEqual(result["status"], "ROBUST_DECISION")
        self.assertEqual(result["decision"], "ROBUST_IDENTIFY_AND_SOLVE")

    def test_lower_bound_at_gain_certifies_direct(self):
        result = evaluate_bounded_identification_economics(self.observation, 10, 5, 8)
        self.assertEqual(result["decision"], "DIRECT_CERTIFIED")

    def test_crossing_interval_abstains_with_safe_fallback(self):
        result = evaluate_bounded_identification_economics(self.observation, 10, 4, 6)
        self.assertEqual(result["status"], "ABSTAIN")
        self.assertEqual(result["decision"], "ABSTAIN_COST_UNCERTAIN")
        self.assertEqual(result["safe_fallback"], "SOLVE_DIRECT")

    def test_unbounded_upper_cost_cannot_certify_identification(self):
        result = evaluate_bounded_identification_economics(self.observation, 10, 0, None)
        self.assertEqual(result["decision"], "ABSTAIN_COST_UNCERTAIN")

    def test_nonpositive_gain_certifies_direct_even_with_zero_cost(self):
        observation = MetaProblemObservation(
            horizon="KNOWN",
            horizon_value=1,
            routes=(AffineRoute("direct", 0, 10), AffineRoute("worse", 4, 9)),
            candidate_values_known=True,
        )
        result = evaluate_bounded_identification_economics(observation, 10, 0, 0)
        self.assertEqual(result["decision"], "DIRECT_CERTIFIED")

    def test_interval_validation_is_not_a_probability_model(self):
        with self.assertRaises(ValueError):
            CostInterval(5, 4)
        interval = CostInterval(0, None)
        self.assertEqual(interval.as_dict(), {"lower": "0", "upper": None})

    def test_small_integer_intervals_match_trichotomy(self):
        for direct in range(1, 7):
            for setup in range(0, 6):
                for transformed in range(0, direct + 1):
                    observation = MetaProblemObservation(
                        horizon="KNOWN",
                        horizon_value=1,
                        routes=(
                            AffineRoute("direct", 0, direct),
                            AffineRoute("candidate", setup, transformed),
                        ),
                        candidate_values_known=True,
                    )
                    gain = direct - min(direct, setup + transformed)
                    for lower in range(0, 6):
                        for upper in range(lower, 6):
                            result = evaluate_bounded_identification_economics(
                                observation, direct, lower, upper
                            )
                            if gain <= 0 or lower >= gain:
                                expected = "DIRECT_CERTIFIED"
                            elif upper < gain:
                                expected = "ROBUST_IDENTIFY_AND_SOLVE"
                            else:
                                expected = "ABSTAIN_COST_UNCERTAIN"
                            self.assertEqual(result["decision"], expected)


if __name__ == "__main__":
    unittest.main()

