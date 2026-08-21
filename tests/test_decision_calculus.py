import unittest
from fractions import Fraction

from matsi.decision_calculus import (
    adaptive_task_quotient,
    analyze_decision_ambiguity,
    bayes_decision_engine,
    compare_blackwell,
    complexity_experiment_suite,
    compose_garblings,
    directed_deficiency,
    epsilon_sufficient_compression,
    find_separation_witnesses,
    identify_decision,
    le_cam_distance,
    mutual_information,
    multi_task_sufficient_quotient,
    representation_compiler,
    representation_path,
    set_cover_reduction_instance,
    stochastic_compression_search,
    task_sufficient_quotient,
    verify_set_cover_reduction,
    vertex_cover_reduction_certificate,
    vertex_cover_reduction_instance,
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
        self.assertEqual(compare_blackwell(self.strict, self.identity)["classification"], "DOMINATED_BY")

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

    def test_compiler_distinguishes_forward_loss_from_reverse_deficiency(self):
        experiment = [[Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)], [0, Fraction(1, 3), Fraction(2, 3)]]
        compiled = representation_compiler(
            experiment,
            self.prior,
            [{"id": "classification", "losses": self.loss, "actions": [0, 1]}],
            [0],
        )
        self.assertEqual(compiled["forward_simulation_loss"]["deficiency"], "0")
        self.assertGreater(Fraction(compiled["reverse_reconstruction_deficiency"]["deficiency"]), 0)
        self.assertEqual(compiled["symmetric_decision_distance"]["value"], "1/18")

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

    def test_mutual_information_and_task_risk_can_order_experiments_differently(self):
        prior = [Fraction(1, 3)] * 3
        irrelevant = [[1, 0], [0, 1], [1, 0]]
        targeted = [
            [Fraction(9, 10), Fraction(1, 10)],
            [Fraction(1, 10), Fraction(9, 10)],
            [Fraction(1, 10), Fraction(9, 10)],
        ]
        loss = [[0, 1], [1, 0], [1, 0]]
        irrelevant_engine = bayes_decision_engine(prior, irrelevant, loss)
        targeted_engine = bayes_decision_engine(prior, targeted, loss)
        self.assertGreater(mutual_information(prior, irrelevant), mutual_information(prior, targeted))
        self.assertGreater(Fraction(irrelevant_engine["bayes_risk"]), Fraction(targeted_engine["bayes_risk"]))

    def test_set_cover_and_degree_two_reductions_are_executable(self):
        instance = set_cover_reduction_instance(
            ["u1", "u2", "u3"], [["u1", "u2"], ["u2", "u3"], ["u3"]], 2
        )
        certificate = verify_set_cover_reduction(instance)
        self.assertTrue(certificate["quotient_yes"])
        vertex_instance = vertex_cover_reduction_instance(
            ["a", "b", "c"], [("a", "b"), ("b", "c")], 1
        )
        vertex_certificate = vertex_cover_reduction_certificate(vertex_instance)
        self.assertEqual(vertex_certificate["chosen_vertices"], ["b"])
        self.assertTrue(vertex_certificate["quotient_yes"])

    def test_ambiguity_profile_selects_degree_two_solver(self):
        instance = vertex_cover_reduction_instance(
            ["a", "b", "c"], [("a", "b"), ("b", "c")], 1
        )
        profile = analyze_decision_ambiguity(
            instance["experiment"], instance["prior"], instance["losses"], instance["actions"]
        )
        self.assertEqual(profile["regime"], "DEGREE_2_AMBIGUITY")
        solved = adaptive_task_quotient(instance["experiment"], instance["prior"], instance["losses"])
        self.assertIn("Vertex-Cover", solved["algorithm"])
        self.assertEqual(solved["bounds"]["optimality_gap"], 0)

    def test_incomparable_pair_has_bounded_decision_witnesses(self):
        witnesses = find_separation_witnesses(
            [[1, 0], [1, 0], [0, 1]], [[1, 0], [0, 1], [0, 1]], prior_denominator=4
        )
        self.assertEqual(witnesses["status"], "SEPARATED")
        self.assertIsNotNone(witnesses["first_better"])
        self.assertIsNotNone(witnesses["second_better"])

    def test_stochastic_compression_zero_tolerance_has_no_grid_advantage(self):
        result = stochastic_compression_search(
            self.identity,
            self.prior,
            [{"losses": self.loss}],
            [0],
            target_symbols=1,
            denominator=2,
        )
        self.assertFalse(result["strict_stochastic_advantage_found"])
        self.assertEqual(result["general_epsilon_status"], "PROVED_NO_ADVANTAGE")

    def test_controlled_complexity_suite_changes_algorithm_by_structure(self):
        rows = {row["case"]: row for row in complexity_experiment_suite()}
        self.assertEqual(rows["unique_optimum"]["algorithm"], "direct grouping by unique optimal action")
        self.assertIn("Vertex-Cover", rows["degree_2_cycle"]["algorithm"])
        self.assertIn("component-wise", rows["decomposable"]["algorithm"])
        self.assertEqual(rows["large_general_bounded"]["status"], "BOUNDED_APPROXIMATION")
        self.assertGreater(rows["large_general_bounded"]["optimality_gap"], 0)


if __name__ == "__main__":
    unittest.main()
