import unittest
from fractions import Fraction

from matsi.regime_identification import (
    AffineRoute,
    MetaProblemObservation,
    audit_two_slope_policy,
    classify_meta_problem,
    run_regime_identification_suite,
    simulate_two_slope_policy,
    solve_known_horizon_affine,
    solve_observed_problem,
    two_slope_threshold_policy,
)


class RegimeIdentificationTests(unittest.TestCase):
    def test_known_horizon_affine_is_exact(self):
        routes = (AffineRoute("direct", 0, 10), AffineRoute("compiled", 3, 2))
        decision = classify_meta_problem(
            MetaProblemObservation(
                horizon="KNOWN",
                horizon_value=4,
                routes=routes,
                candidate_values_known=True,
            )
        )
        self.assertEqual(decision.status, "CLASSIFIED")
        self.assertEqual(decision.regime, "KNOWN_HORIZON_AFFINE")
        solved = solve_known_horizon_affine(routes, 4)
        self.assertEqual(solved["winner"], "compiled")
        self.assertEqual(solved["optimal_cost"], "11")

    def test_classification_does_not_claim_transformation_benefit(self):
        result = solve_observed_problem(
            MetaProblemObservation(
                horizon="KNOWN",
                horizon_value=1,
                routes=(AffineRoute("direct", 0, 10), AffineRoute("expensive", 4, 9)),
                candidate_values_known=True,
            )
        )
        self.assertEqual(result["classification"]["regime"], "KNOWN_HORIZON_AFFINE")
        self.assertEqual(result["solution"]["winner"], "direct")

    def test_unknown_horizon_two_slope_gets_certified_policy(self):
        route = AffineRoute("compiled", Fraction(51, 10), 0)
        observation = MetaProblemObservation(
            horizon="UNKNOWN",
            routes=(route,),
            direct_rate=5,
            candidate_values_known=True,
        )
        result = solve_observed_problem(observation)
        self.assertEqual(result["classification"]["regime"], "UNKNOWN_HORIZON_TWO_SLOPE")
        self.assertEqual(result["solution"]["rent_uses_before_buy"], 1)
        self.assertEqual(result["solution"]["competitive_ratio_bound"], "2")

    def test_two_slope_policy_is_within_two_on_finite_audit(self):
        route = AffineRoute("compiled", Fraction(51, 10), 0)
        audit = audit_two_slope_policy(route, 5, 20)
        self.assertTrue(audit["within_certified_bound"])
        self.assertLessEqual(Fraction(audit["worst_ratio"]), 2)
        self.assertEqual(simulate_two_slope_policy(route, 5, 2)["action"], "RENT_THEN_BUY")

    def test_two_slope_bound_survives_small_integer_exhaustion(self):
        for setup in range(0, 9):
            for direct in range(1, 7):
                for transformed_rate in range(direct):
                    route = AffineRoute("compiled", setup, transformed_rate)
                    audit = audit_two_slope_policy(route, direct, 20)
                    self.assertTrue(audit["within_certified_bound"])

    def test_complete_route_graph_is_classified_without_affine_assumptions(self):
        decision = classify_meta_problem(
            MetaProblemObservation(
                route_graph_complete=True,
                transition_generators_complete=True,
            )
        )
        self.assertEqual(decision.regime, "EXPLICIT_ROUTE_GRAPH")
        self.assertEqual(decision.solver_family, "SHORTEST_PATH_OR_ASTAR")

    def test_no_rate_improvement_is_not_classified_as_two_slope(self):
        observation = MetaProblemObservation(
            horizon="UNKNOWN",
            routes=(AffineRoute("same_rate", 5, 10),),
            direct_rate=10,
            candidate_values_known=True,
        )
        self.assertEqual(classify_meta_problem(observation).status, "ABSTAIN")
        self.assertEqual(solve_observed_problem(observation)["status"], "ABSTAIN")

    def test_multiple_unknown_options_are_a_negative_control(self):
        observation = MetaProblemObservation(
            horizon="UNKNOWN",
            routes=(AffineRoute("a", 1, 2), AffineRoute("b", 4, 1)),
            direct_rate=5,
            candidate_values_known=True,
        )
        decision = classify_meta_problem(observation)
        self.assertEqual(decision.status, "ABSTAIN")
        self.assertIn("no solver guarantee", " ".join(decision.reasons))

    def test_costly_inspection_is_named_but_not_solved_by_fiat(self):
        observation = MetaProblemObservation(
            horizon="UNKNOWN",
            candidate_values_known=False,
            inspection_costs=(2,),
        )
        result = solve_observed_problem(observation)
        self.assertEqual(result["classification"]["regime"], "COSTLY_OPTION_INSPECTION")
        self.assertEqual(result["status"], "CLASSIFIED_BUT_SOLVER_DEFERRED")

    def test_incomparable_objectives_force_abstention(self):
        observation = MetaProblemObservation(
            horizon="KNOWN",
            horizon_value=3,
            routes=(AffineRoute("a", 1, 1),),
            candidate_values_known=True,
            objective_dimensions=2,
        )
        decision = classify_meta_problem(observation)
        self.assertEqual(decision.status, "ABSTAIN")

    def test_suite_exposes_required_negative_and_unknown_results(self):
        result = run_regime_identification_suite()
        statuses = {claim["status"] for claim in result["claims"]}
        self.assertTrue({"PROVED", "KNOWN_RESULT", "DISPROVED", "UNKNOWN"} <= statuses)
        self.assertEqual(result["unsupported_negative_control"]["status"], "ABSTAIN")
        self.assertEqual(
            result["regime_without_speedup_negative_control"]["solution"]["winner"],
            "direct",
        )


if __name__ == "__main__":
    unittest.main()
