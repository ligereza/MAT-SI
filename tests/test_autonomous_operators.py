"""The four operators, their anti-worlds, and the structural selection layer.

Every test names the kind of claim it establishes:

    PROVED_BY_ARGUMENT   true by the construction of the world
    VERIFIED_FINITE_CASE checked exhaustively on a finite instance
    COUNTEREXAMPLE       the intuitive strategy provably fails here
    KNOWN_RESULT         imported from the literature, verified locally
"""

from __future__ import annotations

from fractions import Fraction
import unittest

from matsi.operators.admissibility import admissible_operators, select_operation
from matsi.operators.codeine import CodeineConfig, decide, run_operator, v0_product_rule
from matsi.operators.ketamine import KetamineConfig, explore_branches
from matsi.operators.vizz import Vizz, VizzConfig, greedy_versus_optimal
from matsi.operators.xanax import Xanax, XanaxConfig, explore
from matsi.substrate import Budget, Decision, State, run_loop
from matsi.worlds import branch_world as bw
from matsi.worlds import expression_world as ew
from matsi.worlds import hypothesis_world as hw
from matsi.worlds import trajectory_world as tw
from matsi.worlds.cross_operator import CrossOperatorWorld, stage_state

XANAX = dict(max_iterations=3, node_limit=700, enumeration_depth=4, enumeration_limit=300)


def _belief_state(world, budget=6):
    return State(
        representation={"belief": {t: Fraction(world.prior[t]) for t in world.hypotheses}},
        budget=Budget(total=budget),
    )


class VizzOperator(unittest.TestCase):
    def test_rarity_surprise_and_target_information_are_three_quantities(self):
        """VERIFIED_FINITE_CASE: the three are not proportional and can disagree."""
        from matsi.operators.vizz import (
            expected_bayesian_surprise,
            expected_information_gain,
            expected_rarity,
        )

        world = hw.rare_but_uninformative_world()
        belief = {t: Fraction(world.prior[t]) for t in world.hypotheses}
        rare_rarity = expected_rarity(belief, world, "rare_nuisance")
        rare_target = expected_information_gain(belief, world, "rare_nuisance", "target")
        rare_surprise = expected_bayesian_surprise(belief, world, "rare_nuisance")
        self.assertGreater(rare_rarity, 0.0)
        self.assertGreater(rare_surprise, 0.0)
        self.assertEqual(rare_target, 0.0)

    def test_nuisance_experiment_is_surprising_and_decision_useless(self):
        """VERIFIED_FINITE_CASE: I(Theta;Y) > 0 while I(T;Y) = 0."""
        from matsi.operators.vizz import expected_information_gain

        world = hw.nuisance_surprise_world()
        belief = {t: Fraction(world.prior[t]) for t in world.hypotheses}
        self.assertGreater(expected_information_gain(belief, world, "nuisance", "hypothesis"), 0.0)
        self.assertEqual(expected_information_gain(belief, world, "nuisance", "target"), 0.0)

    def test_greedy_has_its_guarantee_when_the_objective_is_submodular(self):
        """KNOWN_RESULT verified locally: Krause & Guestrin 2005 + NWF 1978."""
        result = greedy_versus_optimal(hw.conditionally_independent_world(), 2)
        self.assertEqual(result["submodularity_status"], "VERIFIED_FINITE_CASE")
        self.assertTrue(result["greedy_guarantee_applies"])
        self.assertTrue(result["guarantee_respected"])

    def test_greedy_information_gain_anti_world(self):
        """COUNTEREXAMPLE: the approximation ratio is driven below any constant."""
        ratios = []
        for bits in (Fraction(1, 8), Fraction(1, 32), Fraction(1, 128)):
            result = greedy_versus_optimal(hw.decoy_parity_world(bits), 2)
            self.assertEqual(result["submodularity_status"], "COUNTEREXAMPLE")
            self.assertFalse(result["greedy_guarantee_applies"])
            ratios.append(result["approximation_ratio"])
        self.assertTrue(all(later < earlier for earlier, later in zip(ratios, ratios[1:])))
        self.assertLess(ratios[-1], 1.0 - 1.0 / 2.718281828459045)

    def test_unaffordable_information_is_refused(self):
        """VERIFIED_FINITE_CASE: highest information gain is not selected when priced out."""
        world = hw.expensive_information_world()
        operator = Vizz(world, VizzConfig(bits_per_cost_unit=None))
        _final, turns = run_loop(operator, _belief_state(world, budget=3), max_turns=4)
        self.assertNotIn("decisive", [turn.selected.name for turn in turns if turn.selected])
        self.assertIn("ABSTAIN", str(operator.certificates[-1]["decision"]))

    def test_incomparable_without_an_exchange_rate(self):
        """PROVED_BY_ARGUMENT: a Pareto frontier with no preference is not orderable."""
        world = hw.conditionally_independent_world()
        operator = Vizz(world, VizzConfig(bits_per_cost_unit=None))
        run_loop(operator, _belief_state(world), max_turns=1)
        self.assertTrue(operator.certificates[-1].get("incomparable"))
        with_rate = Vizz(world, VizzConfig(bits_per_cost_unit=0.01))
        final, turns = run_loop(with_rate, _belief_state(world), max_turns=6)
        self.assertIs(turns[-1].decision, Decision.STOP)
        self.assertEqual(final.representation["target_entropy"], 0.0)


class CodeineOperator(unittest.TestCase):
    def test_progress_is_not_state_change(self):
        """COUNTEREXAMPLE: the digest-only v0 rule is wrong where utility is positive."""
        world = tw.productive_repetition_world()
        result = run_operator(world, "grind", CodeineConfig(patience=2))
        self.assertEqual(len(set(result["digests"])), 1)
        self.assertEqual(result["v0_rule_on_same_digests"], "STOP")
        self.assertIn("productive_repetition", result["reasons"])
        self.assertAlmostEqual(result["regret"], 0.0, places=9)

    def test_state_change_is_not_progress(self):
        """VERIFIED_FINITE_CASE: a cycle with changing digests and zero gain switches."""
        world = tw.cycling_world()
        result = run_operator(world, "spin", CodeineConfig(patience=2))
        self.assertGreater(len(set(result["digests"])), 1)
        self.assertIn("regime_change_alternative_better", result["reasons"])
        self.assertLess(result["regret"], world.best_plan()["payoff"])

    def test_the_four_actions_arise_for_different_reasons(self):
        """VERIFIED_FINITE_CASE: the decision is reason-typed, not an argmax."""
        short = decide([1.0], ["a"], 0.25, [], CodeineConfig())
        self.assertEqual((short.action, short.reason), ("ABSTAIN", "insufficient_measurement"))
        productive = decide([1.0, 1.0], ["a", "a"], 0.25, [], CodeineConfig())
        self.assertEqual(productive.reason, "productive_repetition")
        cycled = decide([0.0, 0.0, 0.0], ["a", "b", "a"], 0.25, ["other"], CodeineConfig())
        self.assertEqual((cycled.action, cycled.reason), ("SWITCH", "cycle_without_progress"))
        exhausted = decide([1.0, 0.0, 0.0, 0.0], ["a", "b", "c", "d"], 0.25, [], CodeineConfig())
        self.assertEqual(exhausted.action, "STOP")
        self.assertIn(exhausted.reason, ("diminishing_returns_exhausted", "detected_collapse"))
        self.assertEqual(len({productive.reason, cycled.reason, exhausted.reason}), 3)

    def test_plateau_alone_does_not_license_stopping(self):
        """VERIFIED_FINITE_CASE: patience must exceed the plateau to reach the payoff."""
        world = tw.delayed_payoff_world()
        impatient = run_operator(world, "dig", CodeineConfig(patience=2))
        patient = run_operator(world, "dig", CodeineConfig(patience=4))
        self.assertGreater(patient["payoff"], impatient["payoff"])
        self.assertIn("plateau_within_patience", patient["reasons"])

    def test_indistinguishable_prefix_pair_admits_no_dominant_patience(self):
        """PROVED_BY_ARGUMENT: identical prefixes, opposite optimal actions."""
        barren, fertile = tw.indistinguishable_prefix_pair()
        self.assertEqual(barren.procedures["task"][:4], fertile.procedures["task"][:4])
        sweep = []
        for patience in (1, 2, 3, 4, 6):
            left = run_operator(barren, "task", CodeineConfig(patience=patience))
            right = run_operator(fertile, "task", CodeineConfig(patience=patience))
            sweep.append((patience, left["regret"], right["regret"]))
        best_barren = min(sweep, key=lambda item: item[1])[0]
        best_fertile = min(sweep, key=lambda item: item[2])[0]
        self.assertNotEqual(best_barren, best_fertile)
        # No setting achieves zero regret on both.
        self.assertFalse(any(abs(a) < 1e-9 and abs(b) < 1e-9 for _p, a, b in sweep))

    def test_v0_rule_is_the_special_case_that_reads_only_digests(self):
        """VERIFIED_FINITE_CASE: the v0 rule ignores utility by construction."""
        self.assertEqual(v0_product_rule(["a", "a", "a"]), "SWITCH")
        self.assertEqual(v0_product_rule(["a", "a", "a", "a"]), "STOP")
        self.assertEqual(v0_product_rule(["a", "b", "a"]), "CONTINUE")


class XanaxOperator(unittest.TestCase):
    def test_representation_is_chosen_by_what_it_enables(self):
        """VERIFIED_FINITE_CASE: equal-size forms separated by an enabling predicate."""
        report = explore(ew.shift_only_task(), XanaxConfig(**XANAX))
        admissible = [item["term"] for item in report["admissible"]]
        self.assertEqual(admissible, ["(x << 2)"])
        self.assertTrue(all(item["equivalent"] for item in report["admissible"]))

    def test_cheapest_equivalent_form_is_rejected_for_breaking_an_invariant(self):
        """COUNTEREXAMPLE: the anti-world where cost and size cannot decide."""
        task = ew.linear_read_task()
        operator = Xanax(task, XanaxConfig(objective="execution", **XANAX))
        state = State(representation={"term": task.start}, budget=Budget(total=4))
        _final, turns = run_loop(operator, state, max_turns=3)
        certificate = operator.certificates[-1]
        self.assertEqual(certificate["cost_driven_choice"], "(x + x)")
        self.assertFalse(certificate["cost_driven_choice_is_admissible"])
        self.assertEqual(certificate["decision"], "SELECT (x << 1)")
        self.assertIn("(x + x)", certificate["rejected_for_invariant"])
        # The two forms are indistinguishable by cost: only the invariant separates them.
        report = explore(task, XanaxConfig(**XANAX))
        costs = {
            item["term"]: item["costs"]
            for item in report["candidates"]
            if item["term"] in ("(x + x)", "(x << 1)")
        }
        self.assertEqual(costs["(x + x)"]["execution"], costs["(x << 1)"]["execution"])
        self.assertEqual(costs["(x + x)"]["tree_size"], costs["(x << 1)"]["tree_size"])

    def test_rewriting_exposes_a_hidden_decomposition(self):
        """VERIFIED_FINITE_CASE: factorisation becomes visible after saturation."""
        report = explore(ew.hidden_decomposition_task(), XanaxConfig(**XANAX))
        admissible = {item["term"] for item in report["admissible"]}
        self.assertTrue(any("+" in term and term.startswith("(x *") for term in admissible))

    def test_selection_depends_on_the_downstream_objective(self):
        """VERIFIED_FINITE_CASE: one class, several objectives, different winners."""
        task = ew.parallel_depth_task()
        choices = set()
        for objective in ("tree_size", "execution", "depth"):
            operator = Xanax(task, XanaxConfig(objective=objective, **XANAX))
            state = State(representation={"term": task.start}, budget=Budget(total=4))
            run_loop(operator, state, max_turns=2)
            choices.add(operator.certificates[-1]["decision"])
        self.assertGreater(len(choices), 1)

    def test_incomparable_without_a_downstream_objective(self):
        """PROVED_BY_ARGUMENT: several admissible forms and no supplied preference."""
        task = ew.parallel_depth_task()
        operator = Xanax(task, XanaxConfig(objective=None, **XANAX))
        state = State(representation={"term": task.start}, budget=Budget(total=4))
        run_loop(operator, state, max_turns=2)
        self.assertIn("INCOMPARABLE", str(operator.certificates[-1]["decision"]))

    def test_equivalence_is_verified_not_assumed(self):
        """VERIFIED_FINITE_CASE: every accepted form is re-checked on the domain."""
        report = explore(ew.shift_only_task(), XanaxConfig(**XANAX))
        for item in report["admissible"]:
            self.assertEqual(item["checker"], "finite_domain")
            self.assertGreater(item["points_checked"], 0)
        self.assertIn("not a proof over Z", report["equivalence_scope"])


class KetamineOperator(unittest.TestCase):
    def test_admissible_bound_makes_pruning_safe(self):
        """VERIFIED_FINITE_CASE: pruning never loses the optimum when the bound holds."""
        world = bw.bounded_world()
        self.assertTrue(world.bound_is_admissible()["admissible"])
        oracle = world.best_leaf()["value"]
        report = explore_branches(world, KetamineConfig(node_budget=24))
        self.assertTrue(report.optimal)
        self.assertEqual(report.best_value, oracle)
        self.assertGreater(len(report.pruned), 0)

    def test_beam_width_loses_the_optimum(self):
        """COUNTEREXAMPLE: the optimal prefix has the worst immediate score."""
        world = bw.trap_world()
        self.assertFalse(world.bound_is_admissible()["admissible"])
        narrow = explore_branches(world, KetamineConfig(node_budget=24, beam_width=1))
        wide = explore_branches(world, KetamineConfig(node_budget=24, beam_width=2))
        self.assertFalse(narrow.optimal)
        self.assertTrue(wide.optimal)
        self.assertLess(narrow.best_value, wide.best_value)

    def test_counterfactual_contradicting_evidence_is_rejected(self):
        """VERIFIED_FINITE_CASE: consistency is checked before value."""
        world = bw.contradictory_evidence_world()
        report = explore_branches(world, KetamineConfig(node_budget=24))
        self.assertTrue(report.rejected)
        self.assertEqual(report.rejected[0]["status"], "REJECTED")
        self.assertLess(report.best_value, 50.0)
        self.assertEqual(report.best_value, 8.0)

    def test_novelty_is_not_value(self):
        """COUNTEREXAMPLE: diversity-driven expansion spends the budget badly."""
        world = bw.novelty_trap_world()
        guided = explore_branches(world, KetamineConfig(node_budget=5))
        diverse = explore_branches(world, KetamineConfig(node_budget=5, diversity_first=True))
        self.assertTrue(guided.optimal)
        self.assertFalse(diverse.optimal)
        self.assertLess(diverse.best_value, guided.best_value)

    def test_simulated_is_never_reported_as_observed(self):
        """PROVED_BY_ARGUMENT: the status field is set at generation."""
        report = explore_branches(bw.bounded_world(), KetamineConfig(node_budget=24))
        modality = report.as_measurement()["modality"]
        self.assertEqual(modality["observed_states"], 1)
        self.assertGreater(modality["simulated_states"], 1)


class StructuralSelection(unittest.TestCase):
    def setUp(self):
        self.world = CrossOperatorWorld()

    def test_each_stage_admits_exactly_one_useful_operator(self):
        """VERIFIED_FINITE_CASE: the trigger is structural, not a name."""
        expected = {
            "belief": "RUN_VIZZ",
            "term": "RUN_XANAX",
            "branches": "RUN_KETAMINE",
        }
        for stage, decision in expected.items():
            state = stage_state(self.world, stage, budget=8)
            verdict = select_operation(state)
            self.assertEqual(verdict.decision, decision, stage)
            self.assertEqual(len(verdict.useful), 1, (stage, verdict.useful))

    def test_codeine_becomes_admissible_only_with_a_measured_trajectory(self):
        """VERIFIED_FINITE_CASE: its precondition is about history, not the object."""
        results = []
        for steps in (0, 1, 2):
            state = stage_state(
                self.world,
                "belief",
                budget=8,
                gains=tuple(1.0 for _ in range(steps)),
                digests=tuple(range(steps)),
            )
            results.append(admissible_operators(state)["CODEINE"].admissible)
        self.assertEqual(results, [False, False, True])

    def test_representation_decides_which_operator_may_act(self):
        """VERIFIED_FINITE_CASE: same object, same task, different R."""
        belief_state = stage_state(self.world, "belief", budget=8)
        term_state = stage_state(self.world, "term", budget=8)
        self.assertEqual(belief_state.representation["task"], term_state.representation["task"])
        belief_triggers = admissible_operators(belief_state)
        term_triggers = admissible_operators(term_state)
        self.assertTrue(belief_triggers["VIZZ"].admissible)
        self.assertFalse(belief_triggers["X-ANA-X"].admissible)
        self.assertFalse(term_triggers["VIZZ"].admissible)
        self.assertTrue(term_triggers["X-ANA-X"].admissible)

    def test_two_useful_operators_are_incomparable_without_a_preference(self):
        """PROVED_BY_ARGUMENT: bits and utility-per-step have no common unit."""
        state = stage_state(self.world, "term", budget=8, gains=(1.0, 0.9), digests=("a", "b"))
        verdict = select_operation(state)
        self.assertEqual(verdict.decision, "INCOMPARABLE")
        self.assertEqual(set(verdict.useful), {"CODEINE", "X-ANA-X"})
        with_preference = select_operation(state, preference=("X-ANA-X", "CODEINE"))
        self.assertEqual(with_preference.decision, "RUN_XANAX")
        self.assertIn("externally supplied", with_preference.reason)

    def test_abstain_when_no_precondition_holds(self):
        """VERIFIED_FINITE_CASE: an empty state licenses no operation."""
        verdict = select_operation(State(representation={}, budget=Budget(total=4)))
        self.assertEqual(verdict.decision, "ABSTAIN")
        self.assertEqual(verdict.admissible, ())

    def test_emergent_sequence_is_not_scripted(self):
        """VERIFIED_FINITE_CASE: the order follows from the structural facts."""
        sequence = [
            select_operation(stage_state(self.world, stage, budget=8)).decision
            for stage in ("belief", "term", "branches")
        ]
        self.assertEqual(sequence, ["RUN_VIZZ", "RUN_XANAX", "RUN_KETAMINE"])


class OperatorComposition(unittest.TestCase):
    def test_vizz_output_becomes_the_object_xanax_can_rewrite(self):
        """VERIFIED_FINITE_CASE: closed composition VIZZ -> X-ANA-X."""
        world = CrossOperatorWorld()
        hypothesis_world = world.hypothesis_world()
        operator = Vizz(hypothesis_world, VizzConfig(bits_per_cost_unit=0.01))
        final, turns = run_loop(operator, _belief_state(hypothesis_world, budget=6), max_turns=5)
        self.assertIs(turns[-1].decision, Decision.STOP)
        identified = [theta for theta, weight in final.representation["belief"].items() if weight > 0]
        self.assertEqual(identified, [world.truth])
        task = world.representation_task(identified[0])
        report = explore(task, XanaxConfig(**XANAX))
        self.assertTrue(report["admissible"])

    def test_ketamine_cannot_act_before_a_branch_structure_exists(self):
        """VERIFIED_FINITE_CASE: invalid composition, reported as inadmissible."""
        world = CrossOperatorWorld()
        state = stage_state(world, "belief", budget=8)
        self.assertFalse(admissible_operators(state)["KETAMINE"].admissible)
        self.assertIn("no branch structure", admissible_operators(state)["KETAMINE"].reason)


if __name__ == "__main__":
    unittest.main()
