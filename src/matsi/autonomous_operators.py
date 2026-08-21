"""Run every autonomous-operator experiment and emit one reproducible result.

    python -m matsi.autonomous_operators --json-out results/autonomous-operators-results.json

Nothing here is hardcoded: every number is computed from the synthetic worlds at
run time, and every claim carries a status label from

    PROVED_BY_ARGUMENT  VERIFIED_FINITE_CASE  COUNTEREXAMPLE
    KNOWN_RESULT        EMPIRICAL             UNKNOWN
"""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from .operators.admissibility import admissible_operators, select_operation
from .operators.codeine import CodeineConfig, run_operator as run_codeine, v0_product_rule
from .operators.ketamine import KetamineConfig, explore_branches
from .operators.vizz import Vizz, VizzConfig, greedy_versus_optimal
from .operators.xanax import Xanax, XanaxConfig, explore as explore_representations
from .substrate import Budget, State, run_loop
from .worlds import branch_world as bw
from .worlds import expression_world as ew
from .worlds import hypothesis_world as hw
from .worlds import trajectory_world as tw
from .worlds.cross_operator import CrossOperatorWorld, stage_state

ROOT = Path(__file__).resolve().parents[2]

XANAX_CONFIG = dict(max_iterations=3, node_limit=900, enumeration_depth=4, enumeration_limit=400)


# --- VIZZ ----------------------------------------------------------------
def vizz_experiments() -> dict[str, Any]:
    def snapshot(world: hw.HypothesisWorld) -> dict[str, Any]:
        from .operators.vizz import (
            expected_bayesian_surprise,
            expected_information_gain,
            expected_rarity,
        )

        belief = {theta: Fraction(world.prior[theta]) for theta in world.hypotheses}
        return {
            "world": world.name,
            "note": world.note,
            "experiments": [
                {
                    "key": item.key,
                    "cost": item.cost,
                    "expected_rarity_bits": expected_rarity(belief, world, item.key),
                    "information_about_theta_bits": expected_information_gain(
                        belief, world, item.key, "hypothesis"
                    ),
                    "expected_surprise_bits": expected_bayesian_surprise(belief, world, item.key),
                    "information_about_target_bits": expected_information_gain(
                        belief, world, item.key, "target"
                    ),
                }
                for item in world.experiments
            ],
        }

    rarity = snapshot(hw.rare_but_uninformative_world())
    nuisance = snapshot(hw.nuisance_surprise_world())
    good = greedy_versus_optimal(hw.conditionally_independent_world(), 2)
    bad = greedy_versus_optimal(hw.decoy_parity_world(), 2)
    shrink = [
        {
            "decoy_bits": str(bits),
            **{
                key: greedy_versus_optimal(hw.decoy_parity_world(bits), 2)[key]
                for key in ("greedy_value_bits", "optimal_value_bits", "approximation_ratio")
            },
        }
        for bits in (Fraction(1, 4), Fraction(1, 8), Fraction(1, 32), Fraction(1, 128))
    ]

    expensive = hw.expensive_information_world()
    state = State(
        representation={"belief": {t: Fraction(expensive.prior[t]) for t in expensive.hypotheses}},
        budget=Budget(total=3),
    )
    operator = Vizz(expensive, VizzConfig(bits_per_cost_unit=None))
    _final, turns = run_loop(operator, state, max_turns=4)
    unaffordable = {
        "world": expensive.name,
        "decisions": [turn.decision.value for turn in turns],
        "final_certificate": operator.certificates[-1]["decision"],
    }

    independent = hw.conditionally_independent_world()
    state = State(
        representation={
            "belief": {t: Fraction(independent.prior[t]) for t in independent.hypotheses}
        },
        budget=Budget(total=5),
    )
    no_rate = Vizz(independent, VizzConfig(bits_per_cost_unit=None))
    run_loop(no_rate, state, max_turns=1)
    with_rate = Vizz(independent, VizzConfig(bits_per_cost_unit=0.01))
    final, turns = run_loop(with_rate, state, max_turns=6)

    return {
        "A_rarity_is_not_information": {
            **rarity,
            "claim": "an outcome can be rare and carry zero information about the target",
            "status": "VERIFIED_FINITE_CASE",
        },
        "B_surprise_is_not_decision_value": {
            **nuisance,
            "claim": "an experiment can be maximally surprising about Theta and useless for T",
            "status": "VERIFIED_FINITE_CASE",
        },
        "C_unaffordable_information": {
            **unaffordable,
            "claim": "the highest-information experiment is refused when unaffordable",
            "status": "VERIFIED_FINITE_CASE",
        },
        "D_greedy_with_its_guarantee": {
            **good,
            "claim": "conditionally independent observations make the objective submodular",
            "status": "KNOWN_RESULT",
            "reference": "Krause & Guestrin 2005; Nemhauser, Wolsey & Fisher 1978",
        },
        "E_greedy_counterexample": {
            **bad,
            "ratio_shrinks_with_decoy": shrink,
            "claim": (
                "greedy expected-information-gain has no constant-factor guarantee: "
                "the ratio to the optimum tends to 0 as the decoy weakens"
            ),
            "status": "COUNTEREXAMPLE",
        },
        "incomparability": {
            "no_exchange_rate": no_rate.certificates[-1]["decision"],
            "with_exchange_rate_0_01": [
                turn.selected.name for turn in turns if turn.selected is not None
            ],
            "final_decision": turns[-1].decision.value,
            "claim": "with several Pareto-optimal experiments and no supplied exchange rate the operator refuses to choose",
            "status": "PROVED_BY_ARGUMENT",
        },
    }


# --- CODEINE -------------------------------------------------------------
def codeine_experiments() -> dict[str, Any]:
    worlds = [
        ("A_productive_repetition", tw.productive_repetition_world(), "grind"),
        ("B_diminishing_returns", tw.diminishing_world(), "refine"),
        ("C_plateau_then_payoff", tw.delayed_payoff_world(), "dig"),
        ("D_cycle_triggers_switch", tw.cycling_world(), "spin"),
        ("E_late_reward_vs_switch", tw.late_reward_versus_switch_world(), "deep"),
        ("F_sunk_cost_stop", tw.deceptive_prefix_world(), "hope"),
    ]
    runs = {}
    for label, world, start in worlds:
        result = run_codeine(world, start, CodeineConfig(patience=2))
        runs[label] = {
            key: result[key]
            for key in (
                "world",
                "note",
                "patience",
                "reasons",
                "steps_taken",
                "payoff",
                "oracle_payoff",
                "regret",
                "v0_rule_on_same_digests",
            )
        }

    frozen = tw.productive_repetition_world()
    frozen_run = run_codeine(frozen, "grind", CodeineConfig(patience=2))

    barren, fertile = tw.indistinguishable_prefix_pair()
    sweep = []
    for patience in (1, 2, 3, 4, 6):
        left = run_codeine(barren, "task", CodeineConfig(patience=patience))
        right = run_codeine(fertile, "task", CodeineConfig(patience=patience))
        sweep.append(
            {
                "patience": patience,
                "barren_regret": left["regret"],
                "fertile_regret": right["regret"],
                "total_regret": left["regret"] + right["regret"],
            }
        )
    best_for_barren = min(sweep, key=lambda item: item["barren_regret"])["patience"]
    best_for_fertile = min(sweep, key=lambda item: item["fertile_regret"])["patience"]

    return {
        "worlds": runs,
        "progress_is_not_state_change": {
            "digests_distinct": len(set(frozen_run["digests"])),
            "steps": frozen_run["steps_taken"],
            "regret": frozen_run["regret"],
            "v0_digest_only_rule": frozen_run["v0_rule_on_same_digests"],
            "operator_reasons": frozen_run["reasons"],
            "claim": (
                "on a trajectory with a constant state digest and positive utility, the "
                "digest-only v0 rule says STOP while the utility-aware operator reaches "
                "the oracle payoff"
            ),
            "status": "COUNTEREXAMPLE",
        },
        "indistinguishable_prefix_pair": {
            "prefix_identical": barren.procedures["task"][:4] == fertile.procedures["task"][:4],
            "barren_oracle": barren.best_plan()["payoff"],
            "fertile_oracle": fertile.best_plan()["payoff"],
            "patience_sweep": sweep,
            "best_patience_for_barren": best_for_barren,
            "best_patience_for_fertile": best_for_fertile,
            "single_patience_optimal_for_both": best_for_barren == best_for_fertile,
            "claim": (
                "two worlds share an observable prefix and have opposite optimal actions, "
                "so no prefix-measurable policy is optimal in both"
            ),
            "status": "PROVED_BY_ARGUMENT",
        },
    }


# --- X-ANA-X -------------------------------------------------------------
def xanax_experiments() -> dict[str, Any]:
    config = XanaxConfig(**XANAX_CONFIG)
    tasks = {
        "A_canonicalisation": ew.shift_only_task(),
        "C_exposed_decomposition": ew.hidden_decomposition_task(),
        "D_invariant_violation": ew.linear_read_task(),
        "E_objective_dependent": ew.parallel_depth_task(),
    }
    explored = {}
    for label, task in tasks.items():
        report = explore_representations(task, config)
        explored[label] = {
            key: report[key]
            for key in (
                "task",
                "note",
                "start",
                "enables_description",
                "declared_invariants",
                "saturation",
                "class_size_explored",
                "equivalence_scope",
            )
        }
        explored[label]["admissible"] = report["admissible"]
        explored[label]["rejected_for_invariant"] = report["rejected_for_invariant"]

    # The anti-world: what a cost-driven selector would have chosen.
    task = ew.linear_read_task()
    operator = Xanax(task, XanaxConfig(objective="execution", **XANAX_CONFIG))
    state = State(representation={"term": task.start}, budget=Budget(total=4))
    _final, turns = run_loop(operator, state, max_turns=3)
    certificate = operator.certificates[-1]

    # Objective dependence on a class with many admissible members.
    depth_task = ew.parallel_depth_task()
    by_objective = {}
    for objective in ("tree_size", "execution", "depth", "interpretability_proxy"):
        operator2 = Xanax(depth_task, XanaxConfig(objective=objective, **XANAX_CONFIG))
        state2 = State(representation={"term": depth_task.start}, budget=Budget(total=4))
        run_loop(operator2, state2, max_turns=2)
        by_objective[objective] = operator2.certificates[-1]["decision"]
    operator3 = Xanax(depth_task, XanaxConfig(objective=None, **XANAX_CONFIG))
    state3 = State(representation={"term": depth_task.start}, budget=Budget(total=4))
    run_loop(operator3, state3, max_turns=2)

    return {
        "tasks": explored,
        "invariant_beats_cost": {
            "decision": certificate["decision"],
            "cost_driven_choice": certificate.get("cost_driven_choice"),
            "cost_driven_choice_is_admissible": certificate.get("cost_driven_choice_is_admissible"),
            "rejected_for_invariant": certificate["rejected_for_invariant"],
            "preserved": certificate.get("preserved"),
            "claim": (
                "the cheapest equivalent representation destroys a declared invariant and is "
                "rejected; cost and size cannot distinguish the two forms because they tie"
            ),
            "status": "COUNTEREXAMPLE",
        },
        "objective_dependence": {
            "selection_by_objective": by_objective,
            "distinct_selections": len(set(by_objective.values())),
            "no_objective": operator3.certificates[-1]["decision"],
            "claim": "the extracted representation depends on the downstream objective",
            "status": "VERIFIED_FINITE_CASE",
        },
    }


# --- KETAMINE ------------------------------------------------------------
def ketamine_experiments() -> dict[str, Any]:
    bounded = bw.bounded_world()
    admissibility = bounded.bound_is_admissible()
    oracle = bounded.best_leaf()
    budget_curve = []
    for budget in (4, 6, 8, 24):
        report = explore_branches(bounded, KetamineConfig(node_budget=budget))
        budget_curve.append(
            {
                "node_budget": budget,
                "expanded": report.expanded,
                "best_value": report.best_value,
                "optimal": report.optimal,
                "pruned": len(report.pruned),
                "budget_exhausted": report.budget_exhausted,
            }
        )

    trap = bw.trap_world()
    beams = []
    for width in (1, 2):
        report = explore_branches(trap, KetamineConfig(node_budget=24, beam_width=width))
        beams.append(
            {
                "beam_width": width,
                "best_value": report.best_value,
                "optimal": report.optimal,
                "expanded": report.expanded,
            }
        )
    unbounded = explore_branches(trap, KetamineConfig(node_budget=24))

    contradictory = bw.contradictory_evidence_world()
    rejected = explore_branches(contradictory, KetamineConfig(node_budget=24))

    novelty = bw.novelty_trap_world()
    novelty_runs = {}
    for label, config in (
        ("bound_guided", KetamineConfig(node_budget=5)),
        ("diversity_first", KetamineConfig(node_budget=5, diversity_first=True)),
        ("beam_width_3", KetamineConfig(node_budget=5, beam_width=3)),
    ):
        report = explore_branches(novelty, config)
        novelty_runs[label] = {
            "best_value": report.best_value,
            "optimal": report.optimal,
            "expanded": report.expanded,
        }

    return {
        "A_C_admissible_bound_makes_pruning_safe": {
            "bound_admissibility": admissibility,
            "oracle_value": oracle["value"],
            "budget_curve": budget_curve,
            "claim": "with a verified admissible bound, pruning never loses the optimum",
            "status": "VERIFIED_FINITE_CASE",
            "reference": "Land & Doig 1960; Hart, Nilsson & Raphael 1968",
        },
        "B_beam_loses_the_optimum": {
            "oracle_value": trap.best_leaf()["value"],
            "bound_claimed_admissible": trap.admissible_bound,
            "bound_verified_admissible": trap.bound_is_admissible()["admissible"],
            "beams": beams,
            "best_first_without_valid_bound": {
                "best_value": unbounded.best_value,
                "optimal": unbounded.optimal,
            },
            "claim": "a beam narrower than the branching factor discards the unique optimal prefix when that prefix scores worst immediately",
            "status": "COUNTEREXAMPLE",
        },
        "D_counterfactual_rejected": {
            "evidence": sorted(contradictory.evidence),
            "rejected": rejected.rejected,
            "best_consistent_value": rejected.best_value,
            "inconsistent_branch_value": 50.0,
            "claim": "a branch whose assumption contradicts the record is rejected before exploration, even though it has the highest nominal value",
            "status": "VERIFIED_FINITE_CASE",
            "reference": "Pearl 2009, ch. 7 (finite syntactic special case)",
        },
        "E_F_novelty_is_not_value": {
            "oracle_value": novelty.best_leaf()["value"],
            "runs": novelty_runs,
            "claim": "novelty-driven expansion spends the whole budget on mutually dissimilar worthless branches",
            "status": "COUNTEREXAMPLE",
        },
        "mcts_decision": {
            "used": False,
            "reason": (
                "the worlds are finite, deterministic and equipped with an admissible bound, "
                "so branch and bound is exact and cheaper; UCT's guarantee is asymptotic and "
                "would add no capability here"
            ),
            "status": "KNOWN_RESULT",
            "reference": "Kocsis & Szepesvari 2006",
        },
    }


# --- cross-operator ------------------------------------------------------
def cross_operator_experiment() -> dict[str, Any]:
    world = CrossOperatorWorld()
    stages = {}
    sequence = []
    for stage in ("belief", "term", "branches"):
        state = stage_state(world, stage, budget=8)
        verdict = select_operation(state)
        stages[stage] = verdict.as_measurement()
        sequence.append(verdict.decision)

    trajectory_admissibility = []
    for steps in (0, 1, 2):
        state = stage_state(
            world,
            "belief",
            budget=8,
            gains=tuple(1.0 for _ in range(steps)),
            digests=tuple(range(steps)),
        )
        trigger = admissible_operators(state)["CODEINE"]
        trajectory_admissibility.append(
            {"measured_steps": steps, "admissible": trigger.admissible, "reason": trigger.reason}
        )

    belief_state = stage_state(world, "belief", budget=8)
    term_state = stage_state(world, "term", budget=8)
    representation_sensitivity = {
        "task_identical": belief_state.representation["task"] == term_state.representation["task"],
        "R_belief": {
            "VIZZ": admissible_operators(belief_state)["VIZZ"].admissible,
            "X-ANA-X": admissible_operators(belief_state)["X-ANA-X"].admissible,
            "decision": select_operation(belief_state).decision,
        },
        "R_term": {
            "VIZZ": admissible_operators(term_state)["VIZZ"].admissible,
            "X-ANA-X": admissible_operators(term_state)["X-ANA-X"].admissible,
            "decision": select_operation(term_state).decision,
        },
        "claim": "the same object and the same task admit different operators under different representations",
        "status": "VERIFIED_FINITE_CASE",
    }

    tie_state = stage_state(world, "term", budget=8, gains=(1.0, 0.9), digests=("a", "b"))
    tie = select_operation(tie_state)
    tie_broken = select_operation(tie_state, preference=("X-ANA-X", "CODEINE"))

    return {
        "stages": stages,
        "emergent_sequence": sequence,
        "sequence_is_scripted": False,
        "codeine_admissibility_by_trajectory_length": trajectory_admissibility,
        "representation_sensitivity": representation_sensitivity,
        "incomparability": {
            "useful": list(tie.useful),
            "decision": tie.decision,
            "reason": tie.reason,
            "with_external_preference": tie_broken.decision,
            "claim": "with two useful operators and no commensurable unit the selector abstains from ordering them",
            "status": "PROVED_BY_ARGUMENT",
        },
    }


def run_all() -> dict[str, Any]:
    return {
        "protocol": "autonomous-operators-foundation",
        "parent_commit": "c91efd8",
        "determinism": {
            "external_dependencies": [],
            "network_used": False,
            "llm_used": False,
            "random_seeds": "all worlds are deterministic; no sampling is performed",
        },
        "vizz": vizz_experiments(),
        "codeine": codeine_experiments(),
        "xanax": xanax_experiments(),
        "ketamine": ketamine_experiments(),
        "cross_operator": cross_operator_experiment(),
        "meta_selector": {
            "status": "DEFERRED",
            "implemented": "structural admissibility plus a partial order with explicit INCOMPARABLE",
            "not_implemented": "a scalar meta-utility over operators",
            "reason": (
                "value-of-computation requires a common utility (Russell & Wefald 1991); the "
                "four operators produce bits, utility-per-step, invariant preservation and "
                "simulated branch value, which are not commensurable without an external "
                "preference this milestone declines to invent"
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the autonomous-operator experiments")
    parser.add_argument(
        "--json-out", type=Path, default=ROOT / "results" / "autonomous-operators-results.json"
    )
    args = parser.parse_args(argv)
    result = run_all()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print("vizz greedy ratio on the anti-world:", result["vizz"]["E_greedy_counterexample"]["approximation_ratio"])
    print("codeine single patience optimal for both:", result["codeine"]["indistinguishable_prefix_pair"]["single_patience_optimal_for_both"])
    print("xanax cost-driven choice admissible:", result["xanax"]["invariant_beats_cost"]["cost_driven_choice_is_admissible"])
    print("ketamine beam widths:", [item["optimal"] for item in result["ketamine"]["B_beam_loses_the_optimum"]["beams"]])
    print("emergent sequence:", result["cross_operator"]["emergent_sequence"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
