import unittest
from fractions import Fraction

from matsi.representation_search import (
    RepresentationState,
    RepresentationTransition,
    TransformationGenerator,
    build_directed_reachability_search,
    build_quotient_merge_search,
    greedy_one_step_choice,
    route_economics_frontier,
    run_representation_search_suite,
    search_explicit_route_graph,
    search_representation_routes,
)


class RepresentationSearchTests(unittest.TestCase):
    def test_explicit_graph_reduces_to_shortest_path_with_goal_cost(self):
        r0 = RepresentationState("r0", "RAW", 10, "DIRECT", terminal_lower_bound=1)
        r1 = RepresentationState("r1", "INDEX", 2, "INDEX", terminal_lower_bound=1)
        r2 = RepresentationState("r2", "CLOSURE", 1, "LOOKUP", terminal_lower_bound=1)
        result = search_explicit_route_graph(
            r0,
            {
                "r0": [
                    RepresentationTransition("to_r1", "r0", r1, 5),
                    RepresentationTransition("to_r2", "r0", r2, 20),
                ],
                "r1": [RepresentationTransition("to_r2", "r1", r2, 1)],
            },
            direct_solve_cost=10,
            reuse_horizon=2,
        )
        self.assertEqual(result["status"], "EXACT_OPTIMUM")
        self.assertEqual(result["best_route"]["representation_sequence"], ["r0", "r1", "r2"])
        self.assertEqual(result["best_route_cost"], "8")
        self.assertEqual(result["optimality_gap"], "0")

    def test_greedy_local_choice_fails_compositionally(self):
        r0 = RepresentationState("r0", "RAW", 100, "DIRECT", terminal_lower_bound=1)
        a = RepresentationState("a", "SLOW_INTERMEDIATE", 90, "A", terminal_lower_bound=1)
        a2 = RepresentationState("a2", "COMPILED", 1, "LOOKUP", terminal_lower_bound=1)
        b = RepresentationState("b", "FAST_LOCAL", 10, "B", terminal_lower_bound=1)

        def first(state):
            if state.id == "r0":
                yield RepresentationTransition("cheap_enabler", "r0", a, 1)
                yield RepresentationTransition("fast_local", "r0", b, 5)

        def second(state):
            if state.id == "a":
                yield RepresentationTransition("compose", "a", a2, 1)

        generators = [TransformationGenerator("first", first), TransformationGenerator("second", second)]
        greedy = greedy_one_step_choice(r0, generators)
        exact = search_representation_routes(r0, generators, direct_solve_cost=100)
        self.assertEqual(greedy["choice"], "b")
        self.assertEqual(exact["best_route"]["representation_sequence"], ["r0", "a", "a2"])
        self.assertEqual(exact["best_route_cost"], "3")

    def test_budget_returns_incumbent_and_sound_gap(self):
        r0 = RepresentationState("r0", "RAW", 100, "DIRECT", terminal_lower_bound=1)
        a = RepresentationState("a", "INTERMEDIATE", 90, "A", terminal_lower_bound=1)
        a2 = RepresentationState("a2", "COMPILED", 1, "LOOKUP", terminal_lower_bound=1)

        def generate(state):
            if state.id == "r0":
                yield RepresentationTransition("to_a", "r0", a, 1)
            elif state.id == "a":
                yield RepresentationTransition("to_a2", "a", a2, 1)

        result = search_representation_routes(
            r0,
            [TransformationGenerator("generated", generate)],
            direct_solve_cost=100,
            max_expansions=1,
        )
        self.assertEqual(result["status"], "BOUNDED_INCUMBENT")
        self.assertEqual(result["best_route_cost"], "100")
        self.assertGreater(Fraction(result["optimality_gap"]), 0)
        self.assertFalse(result["optimality_certificate"]["exact"])

    def test_lower_bound_prunes_many_bad_states_without_changing_optimum(self):
        root = RepresentationState("root", "RAW", 5, "DIRECT", terminal_lower_bound=1)
        states = {
            "root": root,
        }
        for depth in range(3):
            for index in range(3 ** (depth + 1)):
                state_id = f"n{depth}-{index}"
                states[state_id] = RepresentationState(
                    state_id,
                    "BAD_STRUCTURE",
                    100,
                    "BAD_SOLVER",
                    terminal_lower_bound=100,
                )

        def generate(state):
            if state.id == "root":
                children = [f"n0-{index}" for index in range(3)]
            elif state.id.startswith("n"):
                depth, index = state.id[1:].split("-")
                if int(depth) >= 2:
                    return
                children = [f"n{int(depth) + 1}-{int(index) * 3 + offset}" for offset in range(3)]
            else:
                return
            for child in children:
                yield RepresentationTransition("expand_bad", state.id, states[child], 0)

        generator = TransformationGenerator("expand_bad", generate)
        uninformed = search_representation_routes(root, [generator], direct_solve_cost=5, use_lower_bound=False)
        bounded = search_representation_routes(root, [generator], direct_solve_cost=5, use_lower_bound=True)
        self.assertEqual(uninformed["status"], "NO_BETTER_ROUTE")
        self.assertEqual(bounded["status"], "NO_BETTER_ROUTE")
        self.assertGreater(uninformed["search_cost"]["states_expanded"], bounded["search_cost"]["states_expanded"])
        self.assertEqual(bounded["search_cost"]["states_expanded"], 1)

    def test_duplicate_canonical_state_is_removed(self):
        r0 = RepresentationState("r0", "RAW", 10, "DIRECT", terminal_lower_bound=1)
        target = RepresentationState("same", "INDEX", 1, "LOOKUP", terminal_lower_bound=1)

        def first(state):
            if state.id == "r0":
                yield RepresentationTransition("path_a", "r0", target, 1)

        def second(state):
            if state.id == "r0":
                yield RepresentationTransition("path_b", "r0", target, 2)

        result = search_representation_routes(
            r0,
            [TransformationGenerator("a", first), TransformationGenerator("b", second)],
            direct_solve_cost=10,
        )
        self.assertGreaterEqual(result["search_cost"]["duplicate_states_removed"], 1)
        self.assertEqual(result["best_route"]["representation_sequence"], ["r0", "same"])

    def test_preservation_failure_never_becomes_exact_route(self):
        r0 = RepresentationState("r0", "RAW", 10, "DIRECT", terminal_lower_bound=1)
        bad = RepresentationTransition(
            "bad", "r0", None, 0, preservation_status="INVALID_FOR_TASK"
        )

        def generate(state):
            if state.id == "r0":
                yield bad

        result = search_representation_routes(
            r0,
            [TransformationGenerator("bad", generate)],
            direct_solve_cost=10,
        )
        self.assertEqual(result["status"], "NO_BETTER_ROUTE")
        self.assertEqual(result["search_cost"]["preservation_failures"], 1)

    def test_quotient_bridge_generates_merges_and_matches_exact_optimum(self):
        source = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        prior = [Fraction(1, 4)] * 4
        losses = [[0, 0, 0], [0, 0, 0], [0, 1, 1], [1, 0, 1]]
        initial, generators, expected = build_quotient_merge_search(source, prior, losses)
        result = search_representation_routes(
            initial,
            generators,
            direct_solve_cost=initial.terminal_solve_cost,
        )
        self.assertEqual(result["status"], "EXACT_OPTIMUM")
        self.assertEqual(result["best_route"]["representation_sequence"][-1], "partition:((0, 1, 2), (3,))")
        self.assertEqual(expected["expected_minimum_blocks"], 2)

    def test_directed_reachability_has_direct_small_and_composed_reused_routes(self):
        graph = [[1], [2], [0, 3], [4], [5], [3]]
        small_queries = [(0, 5)]
        many_queries = [(0, 5)] * 10
        initial_small, generators_small, meta_small = build_directed_reachability_search(graph, small_queries)
        initial_many, generators_many, meta_many = build_directed_reachability_search(graph, many_queries)
        small = search_representation_routes(
            initial_small,
            generators_small,
            direct_solve_cost=meta_small["direct_per_query"],
            reuse_horizon=1,
        )
        many = search_representation_routes(
            initial_many,
            generators_many,
            direct_solve_cost=meta_many["direct_per_query"],
            reuse_horizon=10,
        )
        self.assertEqual(small["best_route"]["kind"], "SOLVE_DIRECT")
        self.assertEqual(many["best_route"]["representation_sequence"][1].split(":", 2)[1], "SCC")
        self.assertEqual(many["best_route"]["representation_sequence"][2].split(":", 2)[1], "SCC_CLOSURE")
        self.assertEqual(many["best_route"]["total_route_cost"], "69")
        self.assertTrue(meta_many["expected_answers"] == [True] * 10)

    def test_frontier_keeps_non_dominated_routes_that_never_win_integer_horizon(self):
        result = route_economics_frontier([
            {"id": "direct", "D": 0, "A": 10},
            {"id": "middle", "D": 3, "A": 8},
            {"id": "fast", "D": 6, "A": 0},
        ])
        self.assertEqual(result["dominated"], [])
        self.assertIn("middle", result["non_dominated_never_optimal"])
        self.assertIn("fast", [item["route"] for item in result["optimal_integer_intervals"]])

    def test_suite_has_required_statuses(self):
        result = run_representation_search_suite()
        self.assertEqual(result["explicit_graph"]["status"], "EXACT_OPTIMUM")
        self.assertEqual(result["bounded_search"]["status"], "BOUNDED_INCUMBENT")
        self.assertEqual(result["no_better_route"]["status"], "NO_BETTER_ROUTE")
        self.assertTrue(result["quotient_regression"]["matches_minimum"])
        self.assertTrue(result["directed_reachability"]["answers_preserved"])


if __name__ == "__main__":
    unittest.main()
