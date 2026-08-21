import unittest
from fractions import Fraction

from matsi.decision_calculus import evaluate_representation_transformation, quotient_experiment, task_sufficient_quotient
from matsi.representation_economics import (
    TransformationCandidate,
    candidate_from_transformation_analysis,
    choose_transformation_discovery_action,
    evaluate_connected_component_transformation,
    exact_break_even_count,
    run_representation_economics_suite,
    select_representation_route,
    solve_transformation_discovery_sequence,
)


class RepresentationEconomicsTests(unittest.TestCase):
    def test_break_even_is_exact_and_strict(self):
        self.assertEqual(exact_break_even_count(8, 10, 4), 2)
        self.assertEqual(exact_break_even_count(0, 10, 4), 1)
        self.assertIsNone(exact_break_even_count(8, 4, 4))
        self.assertIsNone(exact_break_even_count(8, 4, 5))

    def test_negative_case_prefers_direct_even_when_after_regime_is_easy(self):
        candidate = TransformationCandidate(
            id="expensive",
            structural_property="decomposition",
            discovery_cost={"time": 8},
            apply_cost={"time": 3},
            solve_cost_after={"time": 1},
            resulting_regime="EASY",
        )
        result = select_representation_route({"time": 10}, [candidate], policy={"resource": "time"})
        self.assertEqual(result["decision"], "SOLVE_DIRECT")
        self.assertEqual(result["routes"][0]["selected_resource_total"], "12")
        self.assertTrue(result["routes"][0]["amortized_advantage"])

    def test_positive_case_uses_exact_transform_analysis(self):
        source = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        prior = [Fraction(1, 4)] * 4
        losses = [[0, 0, 0], [0, 0, 0], [0, 1, 1], [1, 0, 1]]
        quotient = task_sufficient_quotient(source, prior, losses)
        target = quotient_experiment(source, quotient["blocks"])
        analysis = evaluate_representation_transformation(source, target, prior, losses)
        candidate = candidate_from_transformation_analysis(
            analysis,
            discovery_cost={"time": 2},
            apply_cost={"time": 1},
            solve_cost_after={"time": 3},
        )
        result = select_representation_route({"time": 10}, [candidate], policy={"resource": "time"})
        self.assertEqual(result["decision"], candidate.id)
        self.assertTrue(analysis["decision_preserved"])
        self.assertEqual(result["selected_route"]["structural_regime_after"], "UNIQUE_OPTIMUM")

    def test_amortization_changes_route_at_exact_threshold(self):
        candidate = TransformationCandidate(
            id="compiled",
            structural_property="reusable_structure",
            discovery_cost={"time": 5},
            apply_cost={"time": 3},
            solve_cost_after={"time": 4},
            resulting_regime="COMPILED",
        )
        one = select_representation_route({"time": 10}, [candidate], policy={"resource": "time"})
        two = select_representation_route({"time": 10}, [candidate], reuse_count=2, policy={"resource": "time"})
        self.assertEqual(one["decision"], "SOLVE_DIRECT")
        self.assertEqual(two["decision"], "compiled")
        self.assertEqual(two["selected_route"]["break_even_count"], 2)

    def test_non_reusable_transform_pays_acquisition_on_each_use(self):
        candidate = TransformationCandidate(
            id="one_shot_compile",
            structural_property="instance_specific_structure",
            discovery_cost={"time": 2},
            apply_cost={"time": 1},
            solve_cost_after={"time": 1},
            resulting_regime="FAST",
            reusable=False,
        )
        result = select_representation_route(
            {"time": 10}, [candidate], reuse_count=2, policy={"resource": "time"}
        )
        route = result["routes"][0]
        self.assertEqual(route["selected_resource_total"], "8")
        self.assertIsNone(route["break_even_count"])

    def test_known_transform_does_not_charge_discovery(self):
        candidate = TransformationCandidate(
            id="already_compiled",
            structural_property="stored_index",
            discovery_cost={"time": 100},
            apply_cost={"time": 2},
            solve_cost_after={"time": 1},
            resulting_regime="INDEXED",
            discovery_status="KNOWN",
        )
        result = select_representation_route({"time": 10}, [candidate], policy={"resource": "time"})
        self.assertEqual(result["routes"][0]["acquisition_cost"], {"time": "2"})
        self.assertEqual(result["decision"], "already_compiled")

    def test_lossy_transform_is_pruned_without_an_exchange_rate(self):
        candidate = TransformationCandidate(
            id="lossy",
            structural_property="coarse_graining",
            discovery_cost={"time": 0},
            apply_cost={"time": 1},
            solve_cost_after={"time": 1},
            resulting_regime="FAST",
            task_preserved=False,
            decision_preserved=False,
            risk_preserved=False,
            risk_degradation=Fraction(1, 10),
        )
        result = select_representation_route(
            {"time": 10}, [candidate], policy={"resource": "time", "allowed_risk_degradation": 0}
        )
        self.assertEqual(result["decision"], "SOLVE_DIRECT")
        self.assertEqual(result["pruned"][0]["rule"], "TASK_NOT_PRESERVED")

    def test_discovery_is_an_existing_meta_action(self):
        candidate = TransformationCandidate(
            id="state_reveal",
            structural_property="state_partition",
            discovery_cost={"time": 1},
            apply_cost={"time": 1},
            solve_cost_after={"time": 1},
            resulting_regime="KNOWN_STATE",
        )
        result = choose_transformation_discovery_action(
            [Fraction(1, 2), Fraction(1, 2)],
            [candidate],
            {candidate.id: [[1, 0], [0, 1]]},
            [[0, 1], [1, 0]],
            policy={"max_cost": {"time": 1}},
        )
        self.assertEqual(result["chosen_meta_action"], "DISCOVER:state_reveal")
        sequential = solve_transformation_discovery_sequence(
            [Fraction(1, 2), Fraction(1, 2)],
            [candidate],
            {candidate.id: [[1, 0], [0, 1]]},
            [[0, 1], [1, 0]],
            time_cost_weight=Fraction(1, 10),
        )
        self.assertEqual(sequential["status"], "EXACT")

    def test_graph_component_transform_is_outside_opt_r_and_reusable(self):
        result = evaluate_connected_component_transformation(
            [[1], [0, 2], [1], [4], [3]],
            [(0, 2), (0, 4), (3, 4)],
        )
        self.assertTrue(result["task_preserved"])
        self.assertTrue(result["different_algorithm_family"])
        self.assertTrue(result["not_defined_by_opt_r"])
        self.assertEqual(result["query_results"], [True, False, True])
        self.assertEqual(result["amortized_break_even_queries"], 2)

    def test_suite_contains_required_counterexamples(self):
        result = run_representation_economics_suite()
        self.assertEqual(result["negative_case"]["decision"], "SOLVE_DIRECT")
        self.assertEqual(result["positive_case"]["route_selection"]["decision"], "cheap_task_sufficient_quotient")
        self.assertEqual(result["amortized_case"]["exact_break_even_count"], 2)
        self.assertEqual(result["generality_verdict"], "GENERALIZES_WITH_NEW_OBJECT")


if __name__ == "__main__":
    unittest.main()
