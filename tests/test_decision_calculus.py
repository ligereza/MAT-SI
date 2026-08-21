import unittest
from fractions import Fraction

from matsi.decision_calculus import (
    bayes_decision_engine,
    compare_blackwell,
    compose_garblings,
    directed_deficiency,
    epsilon_sufficient_compression,
    identify_decision,
    le_cam_distance,
    multi_task_sufficient_quotient,
    representation_compiler,
    representation_path,
    task_sufficient_quotient,
)


class DecisionCalculusTests(unittest.TestCase):
    def setUp(self):
        self.prior = [Fraction(1, 2), Fraction(1, 2)]
        self.identity = [[1, 0], [0, 1]]
        self.strict = [[Fraction(3, 4), Fraction(1, 4)], [Fraction(1, 4), Fraction(3, 4)]]
        self.useless = [[Fraction(1, 2), Fraction(1, 2)], [Fraction(1, 2), Fraction(1, 2)]]
        self.loss = [[0, 1], [1, 0]]

    def test_bayes_engine_supports_arbitrary_loss_and_ties(self):
        engine = bayes_decision_engine(
            self.prior,
            self.identity,
            [[0, 2], [1, 0]],
            actions=["safe", "risky"],
        )
        self.assertEqual(engine["bayes_risk"], "0")
        self.assertEqual(engine["policy"], [["safe"], ["risky"]])

        tied = bayes_decision_engine(self.prior, self.useless, self.loss)
        self.assertEqual(tied["bayes_risk"], "1/2")
        self.assertEqual(tied["policy"], [[0, 1], [0, 1]])

    def test_blackwell_classifies_standard_cases_and_returns_witness(self):
        dominant = compare_blackwell(self.identity, self.strict)
        self.assertEqual(dominant["classification"], "DOMINATES")
        self.assertTrue(dominant["first_to_second"]["exists"])
        self.assertEqual(dominant["first_to_second"]["residual_linf"], "0")

        self.assertEqual(compare_blackwell(self.identity, [[0, 1], [1, 0]])["classification"], "EQUIVALENT")
        self.assertEqual(compare_blackwell(self.identity, self.useless)["classification"], "DOMINATES")

        left = [[1, 0], [1, 0], [0, 1]]
        right = [[1, 0], [0, 1], [0, 1]]
        self.assertEqual(compare_blackwell(left, right)["classification"], "INCOMPARABLE")
        self.assertEqual(compare_blackwell([[1, 0], [0, 1]], [[1, 0], [0, 1], [1, 0]])["classification"], "INVALID")

    def test_deficiency_has_zero_certificate_and_nonzero_reverse(self):
        zero = directed_deficiency(self.identity, self.strict)
        self.assertEqual(zero["status"], "EXACT")
        self.assertEqual(zero["deficiency"], "0")

        reverse = directed_deficiency(self.strict, self.identity)
        self.assertEqual(reverse["status"], "EXACT")
        self.assertEqual(reverse["deficiency"], "1/4")
        distance = le_cam_distance(self.identity, self.strict)
        self.assertEqual(distance["le_cam_distance"], "1/4")

    def test_task_quotient_is_verified_by_common_optimal_action(self):
        experiment = [[Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)], [0, Fraction(1, 2), Fraction(1, 2)]]
        result = task_sufficient_quotient(experiment, self.prior, self.loss)
        self.assertEqual(result["minimum_quotient_states"], 2)
        self.assertTrue(result["verification"]["preserved"])
        self.assertEqual(result["verification"]["risk_delta"], "0")
        self.assertTrue(all(witness["common_optimal_actions"] for witness in result["verification"]["witnesses"]))

    def test_multi_task_quotient_is_monotone_and_epsilon_can_compress_more(self):
        experiment = [[Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)], [0, Fraction(1, 2), Fraction(1, 2)]]
        tasks = [
            {"id": "classification", "losses": self.loss, "actions": [0, 1]},
            {"id": "asymmetric", "losses": [[0, 2], [1, 0]], "actions": [0, 1]},
        ]
        single = task_sufficient_quotient(experiment, self.prior, self.loss)
        multi = multi_task_sufficient_quotient(experiment, self.prior, tasks)
        self.assertGreaterEqual(multi["minimum_quotient_states"], single["minimum_quotient_states"])
        self.assertTrue(all(item["preserved"] for item in multi["verification"]))

        epsilon = epsilon_sufficient_compression(experiment, self.prior, tasks, [Fraction(1, 4), Fraction(1, 4)])
        self.assertEqual(epsilon["status"], "EXACT")
        self.assertLessEqual(epsilon["minimum"]["state_count"], multi["minimum_quotient_states"])
        self.assertTrue(all(delta <= Fraction(1, 4) for delta in map(Fraction, epsilon["minimum"]["risk_deltas"])))

    def test_compiler_and_path_keep_decisions_explicit(self):
        experiment = [[Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)], [0, Fraction(1, 2), Fraction(1, 2)]]
        tasks = [{"id": "classification", "losses": self.loss, "actions": [0, 1]}]
        compiled = representation_compiler(experiment, self.prior, tasks, [0])
        self.assertEqual(compiled["status"], "COMPILED")
        self.assertIn("classification", compiled["preserved_tasks"])
        self.assertTrue(compiled["blackwell_original_to_compressed"]["exists"])

        path = representation_path([self.identity, self.strict, self.useless], self.prior, tasks)
        self.assertTrue(path["all_steps_exact_blackwell"])
        self.assertEqual(path["deficiency_upper_bound_by_triangle"], "0")

    def test_identification_is_an_explicit_interface(self):
        identified = identify_decision(["labels", "symmetry"], ["labels", "symmetry"])
        missing = identify_decision(["labels"], ["labels", "calibration"])
        self.assertEqual(identified["status"], "IDENTIFIED")
        self.assertEqual(missing["status"], "NOT_IDENTIFIED")
        self.assertEqual(missing["missing"], ["calibration"])

    def test_channel_composition_preserves_stochastic_rows(self):
        first = [[1, 0], [0, 1]]
        second = [[Fraction(3, 4), Fraction(1, 4)], [Fraction(1, 4), Fraction(3, 4)]]
        composed = compose_garblings(first, second)
        self.assertEqual(composed, second)
        self.assertTrue(all(sum(row) == 1 for row in composed))


if __name__ == "__main__":
    unittest.main()
