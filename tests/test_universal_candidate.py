import unittest

from matsi.regime_economics import JointCostScenario
from matsi.universal_candidate import (
    exact_closure_check,
    exact_universal_trichotomy,
    partial_observation_impossibility,
    run_universal_candidate_attempt,
)


class UniversalCandidateTests(unittest.TestCase):
    def test_exact_trichotomy_identifies_all_positive_universe(self):
        result = exact_universal_trichotomy(
            (
                JointCostScenario("a", 10, 6, 0),
                JointCostScenario("b", 10, 0, 9),
            )
        )
        self.assertEqual(result["decision"], "ROBUST_IDENTIFY_AND_SOLVE")
        self.assertEqual(result["inf_net_gain_finite"], "1")

    def test_exact_trichotomy_abstains_on_mixed_universe(self):
        result = exact_universal_trichotomy(
            (
                JointCostScenario("positive", 10, 6, 0),
                JointCostScenario("negative", 10, 9, 2),
            )
        )
        self.assertEqual(result["decision"], "ABSTAIN_JOINT_UNCERTAIN")

    def test_partial_observation_cannot_support_both_possible_worlds(self):
        result = partial_observation_impossibility(
            (JointCostScenario("observed", 10, 6, 0),),
            JointCostScenario("omitted", 10, 9, 2),
        )
        self.assertEqual(result["status"], "IMPOSSIBILITY_WITNESS")
        self.assertNotEqual(
            result["possible_world_observed_only"]["decision"],
            result["possible_world_with_omitted"]["result"]["decision"],
        )
        self.assertFalse(result["universal_observation_only_rule_possible"])

    def test_exact_closure_is_relative_to_explicit_universe(self):
        universe = (
            JointCostScenario("a", 10, 6, 0),
            JointCostScenario("b", 10, 0, 9),
        )
        self.assertTrue(exact_closure_check(universe, universe)["exact_closure"])
        self.assertFalse(exact_closure_check(universe[:1], universe)["exact_closure"])

    def test_attempt_reports_required_gate(self):
        result = run_universal_candidate_attempt()
        self.assertEqual(result["gate"], "UNIVERSALITY_REQUIRES_VERIFIABLE_CLOSURE")
        self.assertEqual(result["partial_observation_attack"]["status"], "IMPOSSIBILITY_WITNESS")


if __name__ == "__main__":
    unittest.main()

