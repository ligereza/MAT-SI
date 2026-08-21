"""The new mathematical primitives, checked against ground truth.

Each test states what kind of claim it establishes.  Finite verification is never
promoted to a universal theorem.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import product
import unittest

from matsi.information.divergence import jensen_shannon_divergence, kl_divergence
from matsi.information.entropy import (
    conditional_entropy,
    conditional_mutual_information,
    entropy,
    joint_entropy,
    mutual_information,
)
from matsi.information.surprise import bayesian_surprise
from matsi.search.exact import astar, branch_and_bound, breadth_first, uniform_cost
from matsi.search.heuristic import beam_search
from matsi.search.problem import SearchProblem
from matsi.sequential.changepoint import page_hinkley
from matsi.sequential.cycles import cycle_report
from matsi.sequential.stopping import (
    exhaustive_best_stopping,
    optimal_stopping_threshold,
    run_stopping_policy,
)
from matsi.symbolic.canonical_graph import is_isomorphic, normalise_graph, refine
from matsi.symbolic.egraph import EGraph
from matsi.symbolic.rules import ARITHMETIC_RULES, rule_soundness_report
from matsi.symbolic.terms import DEFAULT_COSTS, size as term_size
from matsi.verification.equivalence import equivalent_by_exhaustion, equivalent_by_sat
from matsi.verification.formula import AND, NOT, OR, VAR, XOR, evaluate, variables_of


class InformationIdentities(unittest.TestCase):
    """PROVED_BY_ARGUMENT (standard identities); here VERIFIED_FINITE_CASE."""

    def test_chain_rule_and_nonnegativity_on_all_small_joints(self):
        # Every joint on a 2x2 support with denominator 4.
        for weights in product(range(5), repeat=4):
            if sum(weights) != 4:
                continue
            joint = {
                (a, b): Fraction(weights[index], 4)
                for index, (a, b) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1)])
            }
            joint = {key: value for key, value in joint.items() if value > 0}
            marginal_x = {}
            for (x, _y), p in joint.items():
                marginal_x[x] = marginal_x.get(x, Fraction(0)) + p
            self.assertAlmostEqual(
                joint_entropy(joint), entropy(marginal_x) + conditional_entropy(joint), places=9
            )
            self.assertGreaterEqual(mutual_information(joint) + 1e-12, 0.0)

    def test_independence_gives_exactly_zero_mutual_information(self):
        independent = {(a, b): Fraction(1, 4) for a in (0, 1) for b in (0, 1)}
        self.assertEqual(mutual_information(independent), 0.0)

    def test_parity_makes_conditional_information_exceed_marginal(self):
        # I(X1;Y) = 0 but I(X1;Y|X2) = 1: the standard non-submodularity witness.
        triple = {(x1, x1 ^ x2, x2): Fraction(1, 4) for x1 in (0, 1) for x2 in (0, 1)}
        pair = {(x1, x1 ^ x2): Fraction(1, 4) for x1 in (0, 1) for x2 in (0, 1)}
        self.assertEqual(mutual_information(pair), 0.0)
        self.assertAlmostEqual(conditional_mutual_information(triple), 1.0, places=9)

    def test_divergences_respect_their_bounds(self):
        self.assertEqual(kl_divergence({0: Fraction(1, 2), 1: Fraction(1, 2)}, {0: Fraction(1, 2), 1: Fraction(1, 2)}), 0.0)
        self.assertEqual(kl_divergence({0: Fraction(1)}, {1: Fraction(1)}), float("inf"))
        self.assertAlmostEqual(jensen_shannon_divergence({0: Fraction(1)}, {1: Fraction(1)}), 1.0, places=9)

    def test_bayesian_surprise_is_zero_when_the_posterior_does_not_move(self):
        prior = {"a": Fraction(1, 3), "b": Fraction(2, 3)}
        surprise, posterior = bayesian_surprise(prior, lambda _h: Fraction(1, 5))
        self.assertEqual(surprise, 0.0)
        self.assertEqual(posterior, prior)


class SearchAgreement(unittest.TestCase):
    """VERIFIED_FINITE_CASE: the exact algorithms agree; beam is incomplete."""

    def _grid(self, wall):
        def successors(state):
            x, y = state
            for dx, dy, name in ((1, 0, "R"), (-1, 0, "L"), (0, 1, "U"), (0, -1, "D")):
                nxt = (x + dx, y + dy)
                if 0 <= nxt[0] <= 3 and 0 <= nxt[1] <= 3 and nxt not in wall:
                    yield name, nxt, 1.0

        return SearchProblem(
            start=(0, 0),
            successors=successors,
            is_goal=lambda s: s == (3, 3),
            heuristic=lambda s: abs(s[0] - 3) + abs(s[1] - 3),
        )

    def test_bfs_ucs_astar_and_branch_and_bound_agree_on_cost(self):
        problem = self._grid({(1, 1), (1, 2)})
        costs = {
            "bfs": breadth_first(problem).cost,
            "ucs": uniform_cost(problem).cost,
            "astar": astar(problem).cost,
            "bnb": branch_and_bound(problem).cost,
        }
        self.assertEqual(len(set(costs.values())), 1, costs)

    def test_beam_search_is_incomplete(self):
        # A corridor where the greedy heuristic prefers a dead end.
        def successors(state):
            mapping = {
                "s": (("bait", "b1", 1.0), ("long", "l1", 1.0)),
                "b1": (("stuck", "b2", 1.0),),
                "l1": (("on", "l2", 1.0),),
                "l2": (("on", "goal", 1.0),),
            }
            return mapping.get(state, ())

        problem = SearchProblem(
            start="s",
            successors=successors,
            is_goal=lambda s: s == "goal",
            heuristic=lambda s: {"s": 3.0, "b1": 0.0, "b2": 0.0, "l1": 2.0, "l2": 1.0, "goal": 0.0}[s],
        )
        self.assertTrue(breadth_first(problem).found)
        self.assertFalse(beam_search(problem, width=1).found)


class VerificationCapability(unittest.TestCase):
    """VERIFIED_FINITE_CASE: the SAT solver agrees with exhaustive truth tables."""

    def _formulas(self):
        a, b, c = VAR("a"), VAR("b"), VAR("c")
        return [
            NOT(AND(a, b)),
            OR(NOT(a), NOT(b)),
            XOR(a, b),
            AND(a, OR(b, c)),
            OR(AND(a, b), AND(a, c)),
            AND(OR(a, b), NOT(AND(a, b))),
            OR(a, NOT(a)),
            AND(a, NOT(a)),
        ]

    def test_sat_equivalence_matches_exhaustive_equivalence_on_every_pair(self):
        formulas = self._formulas()
        for left in formulas:
            for right in formulas:
                exhaustive, _cex, _m = equivalent_by_exhaustion(left, right)
                by_sat, counterexample, _measurement = equivalent_by_sat(left, right)
                self.assertEqual(exhaustive, by_sat, (left, right))
                if not by_sat:
                    names = set(variables_of(left)) | set(variables_of(right))
                    assignment = {name: counterexample.get(name, False) for name in names}
                    self.assertNotEqual(
                        evaluate(left, assignment), evaluate(right, assignment), assignment
                    )

    def test_de_morgan_holds_and_distribution_is_not_an_identity(self):
        a, b, c = VAR("a"), VAR("b"), VAR("c")
        self.assertTrue(equivalent_by_sat(NOT(AND(a, b)), OR(NOT(a), NOT(b)))[0])
        self.assertTrue(equivalent_by_sat(AND(a, OR(b, c)), OR(AND(a, b), AND(a, c)))[0])
        self.assertFalse(equivalent_by_sat(AND(a, b), OR(a, b))[0])


class EGraphCapability(unittest.TestCase):
    """VERIFIED_FINITE_CASE: extraction attains the enumerated minimum."""

    def test_rules_are_valid_on_the_declared_finite_domain(self):
        report = rule_soundness_report()
        self.assertEqual(report["invalid_on_domain"], [])
        self.assertIn("scope", report)

    def test_saturation_proves_a_nontrivial_equality_and_refuses_a_false_one(self):
        graph = EGraph()
        left = ("*", ("var", "x"), ("const", 4))
        right = ("<<", ("var", "x"), ("const", 2))
        graph.add_term(left)
        graph.add_term(right)
        graph.saturate(ARITHMETIC_RULES, max_iterations=4, node_limit=800)
        self.assertTrue(graph.equivalent(left, right))
        self.assertFalse(graph.equivalent(left, ("+", ("var", "x"), ("const", 3))))

    def test_extraction_matches_brute_force_minimum(self):
        graph = EGraph()
        root = graph.add_term(("*", ("+", ("var", "x"), ("const", 0)), ("const", 2)))
        graph.saturate(ARITHMETIC_RULES, max_iterations=3, node_limit=700)
        enumerated = graph.enumerate_terms(root, max_depth=4, limit=1500)
        self.assertTrue(enumerated)
        best = min(term_size(term) for term in enumerated)
        _term, value = graph.extract(DEFAULT_COSTS["tree_size"], root)
        self.assertEqual(int(value), best)

    def test_identity_introduction_directions_are_dropped_and_reported(self):
        graph = EGraph()
        graph.add_term(("+", ("var", "x"), ("const", 0)))
        report = graph.saturate(ARITHMETIC_RULES, max_iterations=2, node_limit=400)
        self.assertIn("add_zero:reverse", report.dropped_directions)


class CanonicalLabelling(unittest.TestCase):
    """KNOWN_RESULT: 1-WL cannot separate C6 from 2*C3; the search stage can."""

    def test_refinement_fails_but_canonical_form_separates(self):
        c6 = normalise_graph([(i, (i + 1) % 6) for i in range(6)])
        two_c3 = normalise_graph([(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)])
        self.assertEqual(set(refine(c6).values()), set(refine(two_c3).values()))
        same, meta = is_isomorphic(c6, two_c3)
        self.assertFalse(same)
        self.assertTrue(meta["exact"])
        self.assertFalse(meta["refinement_separated"])

    def test_relabelling_does_not_change_the_canonical_form(self):
        left = normalise_graph([(0, 1), (1, 2), (2, 3)])
        right = normalise_graph([("d", "c"), ("c", "b"), ("b", "a")])
        same, meta = is_isomorphic(left, right)
        self.assertTrue(same)
        self.assertTrue(meta["exact"])


class SequentialCapability(unittest.TestCase):
    """VERIFIED_FINITE_CASE for stopping; EMPIRICAL for the detector trade-off."""

    def test_backward_induction_beats_a_naive_rule_in_expectation(self):
        distribution = {0.0: 0.5, 1.0: 0.5}
        policy = optimal_stopping_threshold(distribution, horizon=4, continuation_cost=0.05)
        sequences = list(product([0.0, 1.0], repeat=4))
        policy_total = sum(
            float(run_stopping_policy(policy, list(values))["payoff"]) for values in sequences
        )
        first_total = sum(values[0] for values in sequences)
        oracle_total = sum(
            float(exhaustive_best_stopping(list(values), 0.05)["payoff"]) for values in sequences
        )
        self.assertGreater(policy_total, first_total)
        self.assertLessEqual(policy_total, oracle_total + 1e-9)

    def test_page_hinkley_trades_delay_against_false_alarms(self):
        stream = [1.0] * 20 + [0.0] * 20
        sensitive = page_hinkley(stream, threshold=0.5, direction="decrease")
        blunt = page_hinkley(stream, threshold=5.0, direction="decrease")
        self.assertIsNotNone(sensitive.first_alarm)
        sensitive_delay = sensitive.delay_from(20)
        blunt_delay = blunt.delay_from(20)
        if blunt_delay is None:
            self.assertIsNotNone(sensitive_delay)
        else:
            self.assertLessEqual(sensitive_delay, blunt_delay)

    def test_cycle_report_separates_returning_from_standing_still(self):
        returning = cycle_report(["a", "b", "c", "a", "b"])
        still = cycle_report(["a", "a", "a", "a"])
        self.assertTrue(returning["cycle_found"])
        self.assertEqual(returning["period"], 3)
        self.assertEqual(returning["longest_run"], 1)
        self.assertTrue(still["cycle_found"])
        self.assertEqual(still["longest_run"], 4)


if __name__ == "__main__":
    unittest.main()
