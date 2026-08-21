"""Trajectory worlds for CODEINE, with an exhaustive policy oracle.

A world offers several *procedures*.  Running a procedure for the k-th time yields
a utility gain and lands on an observable state digest, both supplied by the world
-- CODEINE never invents a utility.  Switching procedure restarts that
procedure's own step counter; stopping ends the run.

Payoff of a run is ``sum of gains - step_cost * steps``.  The oracle enumerates
every action sequence, so the operator's decisions are compared with the exact
best policy rather than with intuition.

Two observables are deliberately decoupled:

    progress      = the utility gain supplied by the world
    state change  = whether the digest differs from the previous one

``productive_repetition_world`` has positive gains with a *constant* digest, and
``cycling_world`` has changing digests with zero gains.  Any rule that reads only
one of the two is wrong on one of these worlds.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Hashable, Sequence

Step = tuple[float, Hashable]


@dataclass(frozen=True)
class TrajectoryWorld:
    """Finite, deterministic, fully enumerable."""

    name: str
    procedures: dict[str, tuple[Step, ...]]
    step_cost: float
    horizon: int
    note: str = ""

    def step(self, procedure: str, index: int) -> Step:
        """Gain and digest for the ``index``-th use of ``procedure`` (0-based).

        Past the supplied length the procedure is exhausted: zero gain and a
        terminal digest.  That is a modelling choice of the world, stated here.
        """
        table = self.procedures[procedure]
        if index < len(table):
            return table[index]
        return (0.0, (procedure, "exhausted"))

    def run(self, actions: Sequence[str]) -> dict[str, object]:
        """Execute a plan of procedure names and report the realised payoff."""
        counters: dict[str, int] = {}
        gains: list[float] = []
        digests: list[Hashable] = []
        for procedure in actions:
            index = counters.get(procedure, 0)
            gain, digest = self.step(procedure, index)
            counters[procedure] = index + 1
            gains.append(gain)
            digests.append(digest)
        return {
            "actions": tuple(actions),
            "gains": tuple(gains),
            "digests": tuple(digests),
            "cumulative": tuple(_cumulative(gains)),
            "steps": len(actions),
            "payoff": sum(gains) - self.step_cost * len(actions),
        }

    def best_plan(self) -> dict[str, object]:
        """Exhaustive optimum over all plans of length 0..horizon."""
        names = sorted(self.procedures)
        best: dict[str, object] | None = None
        evaluated = 0
        for length in range(self.horizon + 1):
            for plan in product(names, repeat=length):
                evaluated += 1
                outcome = self.run(plan)
                if best is None or outcome["payoff"] > float(best["payoff"]) + 1e-12:
                    best = outcome
        assert best is not None
        return {**best, "plans_evaluated": evaluated, "oracle": "exhaustive"}

    def best_single_procedure(self, procedure: str) -> dict[str, object]:
        """Best stopping point when never switching: the pure-continuation oracle."""
        best: dict[str, object] | None = None
        for length in range(self.horizon + 1):
            outcome = self.run([procedure] * length)
            if best is None or outcome["payoff"] > float(best["payoff"]) + 1e-12:
                best = outcome
        assert best is not None
        return best


def _cumulative(values: Sequence[float]) -> list[float]:
    total = 0.0
    out: list[float] = []
    for value in values:
        total += value
        out.append(total)
    return out


# --- A. repetition that is productive even with a frozen digest -----------
def productive_repetition_world() -> TrajectoryWorld:
    """Constant observable state, steady positive gain.

    The digest never changes, so a detector that equates "no state change" with
    "stuck" says STOP.  The utility supplied by the world says CONTINUE, and the
    oracle agrees.  This world exists to break that equation.
    """
    frozen = ("compile", "same-artifact")
    return TrajectoryWorld(
        name="productive_repetition",
        procedures={"grind": tuple((1.0, frozen) for _ in range(10))},
        step_cost=0.25,
        horizon=8,
        note="progress without state change: repetition pays while the digest is constant",
    )


# --- B. diminishing returns ----------------------------------------------
def diminishing_world() -> TrajectoryWorld:
    """Geometric decay: there is an exact optimal stopping point."""
    gains = tuple((2.0 * (0.5 ** index), ("refine", index)) for index in range(10))
    return TrajectoryWorld(
        name="diminishing",
        procedures={"refine": gains},
        step_cost=0.25,
        horizon=8,
        note="marginal gain decays below the step cost; stopping becomes optimal",
    )


# --- C. plateau then renewed gain ---------------------------------------
def delayed_payoff_world() -> TrajectoryWorld:
    """A flat stretch followed by a large payoff.

    Stopping on the plateau is strictly worse than continuing, so a plateau alone
    is not evidence for stopping.
    """
    table: tuple[Step, ...] = (
        (1.0, ("dig", 0)),
        (0.0, ("dig", 1)),
        (0.0, ("dig", 2)),
        (0.0, ("dig", 3)),
        (6.0, ("dig", 4)),
        (0.0, ("dig", 5)),
    )
    return TrajectoryWorld(
        name="delayed_payoff",
        procedures={"dig": table},
        step_cost=0.25,
        horizon=6,
        note="a plateau is not evidence of exhaustion",
    )


# --- D. a cycle that should trigger SWITCH -------------------------------
def cycling_world() -> TrajectoryWorld:
    """Digests cycle with period 3 and zero gain, while an alternative pays.

    State keeps changing, so a stagnation detector reading only the digest sees
    activity.  The gains are zero, and another procedure is available: SWITCH.
    """
    loop: tuple[Step, ...] = tuple(
        (0.0, ("spin", index % 3)) for index in range(10)
    )
    other: tuple[Step, ...] = tuple((1.5, ("other", index)) for index in range(10))
    return TrajectoryWorld(
        name="cycling",
        procedures={"spin": loop, "alternative": other},
        step_cost=0.25,
        horizon=6,
        note="state change without progress: a cycle with an available alternative",
    )


# --- E. switching early is worse than continuing -------------------------
def late_reward_versus_switch_world() -> TrajectoryWorld:
    """The current procedure pays late; the alternative pays a little, forever.

    An impatient SWITCH after the flat prefix forfeits the large late gain.
    """
    current: tuple[Step, ...] = (
        (0.5, ("deep", 0)),
        (0.0, ("deep", 1)),
        (0.0, ("deep", 2)),
        (8.0, ("deep", 3)),
    )
    alternative: tuple[Step, ...] = tuple((0.6, ("shallow", index)) for index in range(8))
    return TrajectoryWorld(
        name="late_reward_versus_switch",
        procedures={"deep": current, "shallow": alternative},
        step_cost=0.25,
        horizon=6,
        note="switching on a flat prefix forfeits a late payoff",
    )


# --- F. sunk cost: continuing is worse than stopping ---------------------
def deceptive_prefix_world() -> TrajectoryWorld:
    """A promising prefix followed by a permanent collapse.

    Continuing after the collapse only pays the step cost, so STOP is optimal even
    though the trajectory started well.
    """
    table: tuple[Step, ...] = (
        (3.0, ("hope", 0)),
        (2.0, ("hope", 1)),
        (0.0, ("hope", 2)),
        (0.0, ("hope", 3)),
        (0.0, ("hope", 4)),
        (0.0, ("hope", 5)),
    )
    return TrajectoryWorld(
        name="deceptive_prefix",
        procedures={"hope": table},
        step_cost=0.5,
        horizon=6,
        note="a good prefix does not license continuation",
    )


# --- the CODEINE anti-world: an information-theoretic impossibility -------
def indistinguishable_prefix_pair() -> tuple[TrajectoryWorld, TrajectoryWorld]:
    """Two worlds with identical observable prefixes and opposite correct actions.

    Both emit gains ``(1, 1, 0, 0)`` with identical digests for the first four
    steps.  Afterwards ``barren`` yields nothing while ``fertile`` yields 5.

    COUNTEREXAMPLE.  Any policy whose decision at step 4 is a function of the
    observed prefix must take the same action in both worlds, so it is suboptimal
    in at least one.  No amount of change-point detection, plateau measurement or
    cycle analysis removes this: the prefixes are equal as observations.  The
    bound is on *observability*, not on the algorithm.
    """
    shared: tuple[Step, ...] = (
        (1.0, ("t", 0)),
        (1.0, ("t", 1)),
        (0.0, ("t", 2)),
        (0.0, ("t", 3)),
    )
    barren = TrajectoryWorld(
        name="barren_tail",
        procedures={"task": shared + ((0.0, ("t", 4)), (0.0, ("t", 5)))},
        step_cost=0.5,
        horizon=6,
        note="identical prefix, empty tail: stopping at step 4 is optimal",
    )
    fertile = TrajectoryWorld(
        name="fertile_tail",
        procedures={"task": shared + ((5.0, ("t", 4)), (0.0, ("t", 5)))},
        step_cost=0.5,
        horizon=6,
        note="identical prefix, rich tail: continuing past step 4 is optimal",
    )
    return barren, fertile
