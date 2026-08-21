import unittest

from matsi.regime_economics import JointCostScenario, evaluate_joint_cost_scenarios


class JointRegimeEconomicsTests(unittest.TestCase):
    def test_joint_correlation_recovers_identification_certificate(self):
        result = evaluate_joint_cost_scenarios(
            (
                JointCostScenario("low_meta_low_gain", 10, 6, 0),
                JointCostScenario("high_meta_high_gain", 10, 0, 9),
            )
        )
        self.assertEqual(result["decision"], "ROBUST_IDENTIFY_AND_SOLVE")
        self.assertEqual(result["independent_interval_hull"]["decision"], "ABSTAIN_INDEPENDENT_HULL")

    def test_joint_disagreement_still_abstains(self):
        result = evaluate_joint_cost_scenarios(
            (
                JointCostScenario("positive", 10, 6, 0),
                JointCostScenario("negative", 10, 5, 6),
            )
        )
        self.assertEqual(result["status"], "ABSTAIN")
        self.assertEqual(result["decision"], "ABSTAIN_JOINT_UNCERTAIN")
        self.assertEqual(result["safe_fallback"], "SOLVE_DIRECT")

    def test_joint_direct_certificate_survives_all_scenarios(self):
        result = evaluate_joint_cost_scenarios(
            (
                JointCostScenario("tie", 10, 5, 5),
                JointCostScenario("loss", 10, 8, 3),
            )
        )
        self.assertEqual(result["decision"], "DIRECT_CERTIFIED")

    def test_scenario_costs_are_nonnegative_and_ids_unique(self):
        with self.assertRaises(ValueError):
            JointCostScenario("bad", -1, 1, 1)
        with self.assertRaises(ValueError):
            evaluate_joint_cost_scenarios(
                (
                    JointCostScenario("same", 1, 1, 1),
                    JointCostScenario("same", 1, 1, 1),
                )
            )


if __name__ == "__main__":
    unittest.main()

