"""One world where several operators are admissible at different times.

THE TASK.  A hidden linear map ``f(x) = a*x`` with ``a`` unknown must be
*implemented on a machine without a multiply instruction*.  The task never
changes; what changes is the state.

    stage 1   R is a belief over candidate coefficients.
              There is no concrete term to rewrite, so X-ANA-X has nothing to act
              on; querying f reduces the uncertainty, so VIZZ is admissible.

    stage 2   R is a concrete term ``x * a``.
              The belief is a point mass, so VIZZ has nothing left to buy; the
              equivalence class has several members, so X-ANA-X is admissible.

    stage 3   R is an implementable term, and several consistent implementation
              orders remain under a node budget, so KETAMINE is admissible.

CODEINE becomes admissible as soon as two measured steps exist, and stays
admissible while budget remains -- it is the only operator whose precondition is
about the *history* rather than about the current object.

The sequence is not scripted anywhere.  ``operators.admissibility`` reads the
state and reports which preconditions hold; the stages differ because the
structure differs.  This is also the representation-sensitivity demonstration:
the same underlying object with representation ``belief`` admits VIZZ and refuses
X-ANA-X, and with representation ``term`` admits X-ANA-X and refuses VIZZ.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Hashable

from ..symbolic.terms import Term
from .branch_world import BranchWorld
from .expression_world import RepresentationTask, shift_only_task
from .hypothesis_world import Experiment, HypothesisWorld

COEFFICIENTS = (2, 4, 8)


@dataclass(frozen=True)
class CrossOperatorWorld:
    """The hidden-coefficient implementation task."""

    name: str = "hidden_coefficient_implementation"
    coefficients: tuple[int, ...] = COEFFICIENTS
    truth: int = 4
    query_points: tuple[int, ...] = (1, 3)
    query_cost: float = 1.0
    note: str = "implement an unknown linear map on a machine without multiply"

    # --- stage 1: uncertainty about the object -------------------------
    def hypothesis_world(self) -> HypothesisWorld:
        """Experiments are evaluations of ``f`` at a point.

        ``query@1`` returns ``a`` itself and so determines the coefficient
        outright; ``query@3`` returns ``3a``, which also determines it.  A third
        experiment ``parity@2`` returns ``(2a) mod 3``, which is informative but
        not decisive, so the three are not interchangeable.
        """
        hypotheses = tuple(self.coefficients)
        prior = {value: Fraction(1, len(hypotheses)) for value in hypotheses}
        experiments = tuple(
            Experiment(f"query@{point}", self.query_cost, lambda theta, p=point: theta * p)
            for point in self.query_points
        ) + (
            Experiment("parity@2", 0.5, lambda theta: (2 * theta) % 3),
        )
        return HypothesisWorld(
            name=f"{self.name}:identify",
            hypotheses=hypotheses,
            prior=prior,
            experiments=experiments,
            target=lambda theta: theta,
            truth=self.truth,
            note="identify the coefficient before it can be re-represented",
        )

    # --- stage 2: a concrete object to re-represent ---------------------
    def representation_task(self, coefficient: int) -> RepresentationTask:
        base = shift_only_task()
        return RepresentationTask(
            name=f"{self.name}:implement",
            start=("*", ("var", "x"), ("const", coefficient)),
            rules=base.rules,
            enables=base.enables,
            enables_description=base.enables_description,
            invariants=base.invariants,
            variables=("x",),
            domain=tuple(range(-8, 9)),
            note="the identified coefficient can now be rewritten for the target machine",
        )

    # --- stage 3: alternative implementations --------------------------
    def branch_world(self, shifts: int) -> BranchWorld:
        """Implementation orders for ``shifts`` successive shift-by-one steps.

        Each step may be emitted now (``emit``) or deferred (``defer``); deferring
        everything is recorded as contradicting the evidence that the program must
        terminate, so that branch is rejected rather than explored.
        """

        def children(state):
            emitted, deferred = state
            if emitted + deferred >= shifts:
                return ()
            return (
                ("emit", (emitted + 1, deferred), 1.0, frozenset()),
                ("defer", (emitted, deferred + 1), 1.0, frozenset({"defer_all"} if emitted == 0 and deferred + 1 == shifts else set())),
            )

        def value(state):
            emitted, deferred = state
            return float(emitted) - 0.5 * float(deferred)

        return BranchWorld(
            name=f"{self.name}:schedule",
            root=(0, 0),
            children=children,
            value=value,
            is_terminal=lambda state: state[0] + state[1] >= shifts,
            bound=lambda state: float(shifts) - 0.5 * float(state[1]),
            evidence=frozenset({"program_must_terminate"}),
            contradictions={"defer_all": "program_must_terminate"},
            note="several consistent schedules, one inconsistent with the evidence",
        )


def stage_state(
    world: CrossOperatorWorld,
    stage: str,
    budget: int = 8,
    gains: tuple[float, ...] = (),
    digests: tuple[Hashable, ...] = (),
) -> "State":
    """Build the substrate state for one stage, with the structural facts filled in.

    The facts written into ``representation`` are exactly what
    ``operators.admissibility`` reads.  They are computed here, from the world,
    rather than asserted.
    """
    from ..information.entropy import entropy
    from ..operators.vizz import expected_information_gain
    from ..operators.xanax import XanaxConfig, explore_objects
    from ..substrate import Budget, State

    representation: dict[str, object] = {"stage": stage, "task": world.note}
    if gains:
        representation["gains"] = gains
        representation["digests"] = digests

    if stage == "belief":
        hypothesis_world = world.hypothesis_world()
        belief = {theta: Fraction(hypothesis_world.prior[theta]) for theta in hypothesis_world.hypotheses}
        representation["belief"] = belief
        representation["target_entropy"] = entropy(belief)
        representation["informative_experiments"] = [
            {
                "key": item.key,
                "cost": item.cost,
                "bits": expected_information_gain(belief, hypothesis_world, item.key, "target"),
            }
            for item in hypothesis_world.experiments
        ]
    elif stage == "term":
        task = world.representation_task(world.truth)
        candidates, _report = explore_objects(
            task, XanaxConfig(max_iterations=3, node_limit=700, enumeration_depth=4, enumeration_limit=300)
        )
        representation["term"] = task.start
        representation["class_size"] = len(candidates)
        representation["enables_now"] = bool(task.enables(task.start))
        # The coefficient is known, so the belief is a point mass: no bits to buy.
        representation["belief"] = {world.truth: Fraction(1)}
        representation["target_entropy"] = 0.0
        representation["informative_experiments"] = []
    elif stage == "branches":
        branch_world = world.branch_world(shifts=2)
        leaves = branch_world.enumerate_leaves()
        representation["term"] = ("<<", ("var", "x"), ("const", 2))
        representation["class_size"] = 1
        representation["enables_now"] = True
        representation["belief"] = {world.truth: Fraction(1)}
        representation["target_entropy"] = 0.0
        representation["informative_experiments"] = []
        representation["consistent_branches"] = len(leaves)
        representation["exhaustive_nodes"] = sum(1 for _ in leaves) * 2
    else:
        raise ValueError(f"unknown stage {stage!r}")

    return State(representation=representation, budget=Budget(total=budget))
