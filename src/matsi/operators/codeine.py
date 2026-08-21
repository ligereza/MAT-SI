"""CODEINE: continue, switch, stop, or abstain on a running process.

FORMAL OBJECT.  Sequential decision on a trajectory.  At step ``t`` the operator
has observed a sequence of ``(procedure, utility gain, state digest)`` triples, a
per-step cost, and the set of available procedures.  It chooses one of
``CONTINUE`` (apply the current procedure again), ``SWITCH`` (apply another),
``STOP``, or ``ABSTAIN``.

ACTION SPACE.  A control decision about a *trajectory*.  Unlike VIZZ it buys no
observation, unlike X-ANA-X it changes no representation, and unlike KETAMINE it
opens no branch: the object it acts on is a history.

LITERATURE AUDIT.
* Optimal stopping by backward induction -- ESTABLISHED (Chow, Robbins & Siegmund,
  *Great Expectations*, 1971).  Requires a known value distribution, which most of
  these worlds do not supply, so the exact rule is only used where it applies.
* Regret-minimising arm choice -- IMPORTED (Auer, Cesa-Bianchi & Fischer 2002 for
  UCB1; Garivier & Moulines 2011 for the non-stationary case).
* Change-point detection -- IMPORTED (Page, Biometrika 1954).
* Diminishing returns as a stopping signal -- ANALOGY, not a theorem: concavity of
  the observed cumulative-value curve is evidence about the past, and extrapolating
  it is an assumption.  Labelled as such in every certificate.

WHAT REMAINS SPECIFIC TO MAT-SI.  Two things, both negative and both about
observability rather than about algorithms:

1. The operator separates *progress* (a utility gain supplied by the world) from
   *state change* (a digest difference).  The CODEINE v0 product rule in
   ``src/codeine/core.py`` reads only digests, so it is the special case
   ``patience = 2, no utility signal``.  On
   ``worlds.productive_repetition_world`` that special case is wrong: the digest
   never changes while every step pays.
2. ``worlds.indistinguishable_prefix_pair`` shows a pair of worlds with identical
   observable prefixes and opposite optimal actions, so no policy that is a
   function of the prefix is optimal in both.  This bounds every rule in this
   module, including the ones that work.

FAILURE REGIME.  Any fixed ``patience`` is wrong on one member of the
indistinguishable pair.  The operator therefore reports its patience and the
regret it incurs, and does not claim optimality.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Hashable, Sequence

from ..sequential.changepoint import page_hinkley
from ..sequential.cycles import cycle_report
from ..sequential.returns import diminishing_returns, marginal_gains
from ..substrate import Candidate, Declaration, Decision, Observation, State
from ..worlds.trajectory_world import TrajectoryWorld

REASONS = (
    "insufficient_measurement",
    "productive_repetition",
    "plateau_within_patience",
    "cycle_without_progress",
    "regime_change_alternative_better",
    "diminishing_returns_exhausted",
    "detected_collapse",
)


@dataclass
class CodeineConfig:
    """Every threshold is explicit and reported; none is claimed optimal."""

    patience: int = 2
    """Plateau length tolerated before stopping or switching."""

    window: int = 2
    """How many recent gains the myopic estimator averages."""

    change_threshold: float = 1.0
    change_delta: float = 0.005


@dataclass(frozen=True)
class Verdict:
    """A reason-typed decision, with the observables that produced it."""

    action: str
    reason: str
    evidence: dict[str, object]

    def as_measurement(self) -> dict[str, object]:
        return {"action": self.action, "reason": self.reason, **self.evidence}


def decide(
    gains: Sequence[float],
    digests: Sequence[Hashable],
    step_cost: float,
    alternatives: Sequence[str],
    config: CodeineConfig,
    alternative_estimate: float | None = None,
) -> Verdict:
    """The sequential rule, as a pure function of the observed trajectory.

    Each branch has its own mathematical justification, and they are *not*
    comparable on a common scale: this is a classification of the trajectory, not
    an argmax over a score.
    """
    cycles = cycle_report(list(digests))
    returns = diminishing_returns(_cumulative(gains), window=config.window)
    alarms = page_hinkley(
        list(gains), delta=config.change_delta, threshold=config.change_threshold, direction="decrease"
    )
    recent = list(gains)[-config.window :]
    recent_mean = fmean(recent) if recent else 0.0
    evidence: dict[str, object] = {
        "steps": len(gains),
        "recent_mean_gain": recent_mean,
        "step_cost": step_cost,
        "plateau": returns["plateau"],
        "patience": config.patience,
        "cycle_found": cycles["cycle_found"],
        "cycle_period": cycles.get("period"),
        "longest_constant_run": cycles["longest_run"],
        "recurrence_rate": cycles["recurrence_rate"],
        "distinct_states": cycles["distinct_states"],
        "change_alarms": list(alarms.alarms),
        "state_changed_last": bool(len(digests) < 2 or digests[-1] != digests[-2]),
        "progress_last": bool(gains and gains[-1] > 0.0),
        "extrapolation_status": "ANALOGY: past concavity is not a theorem about the future",
    }

    if len(gains) < 2:
        # Not a conclusion about the world: a statement that the trajectory is
        # too short to classify.  The caller should measure once more.
        return Verdict("ABSTAIN", "insufficient_measurement", evidence)

    # 1. Productive repetition.  The utility signal decides, never the digest, so
    #    a frozen state with paying steps is correctly continued.
    if recent_mean > step_cost + 1e-12:
        return Verdict("CONTINUE", "productive_repetition", evidence)

    # 2. A closed cycle with no gain around the loop: the procedure has returned
    #    to a state it already visited without buying anything.
    if cycles["cycle_found"] and abs(sum(gains[-(cycles["period"] or 1) :])) <= 1e-12:
        if alternatives:
            return Verdict("SWITCH", "cycle_without_progress", evidence)
        return Verdict("STOP", "cycle_without_progress", evidence)

    # 3. A flat stretch shorter than the declared patience is not evidence of
    #    exhaustion (worlds.delayed_payoff_world is the witness).
    plateau = int(returns["plateau"])
    if 1 <= plateau < config.patience:
        return Verdict("CONTINUE", "plateau_within_patience", evidence)

    # 4. An alternative whose one-step estimate beats both the step cost and the
    #    current recent mean: a regime change worth paying for.
    if (
        alternatives
        and alternative_estimate is not None
        and alternative_estimate > step_cost + 1e-12
        and alternative_estimate > recent_mean + 1e-12
    ):
        evidence["alternative_estimate"] = alternative_estimate
        return Verdict("SWITCH", "regime_change_alternative_better", evidence)

    # 5. The marginal return has fallen to or below the price of a step.  Which
    #    of the two stopping reasons applies is decided by the change detector,
    #    not by the same quantity twice.
    if alarms.alarms:
        return Verdict("STOP", "detected_collapse", evidence)
    return Verdict("STOP", "diminishing_returns_exhausted", evidence)


def _cumulative(values: Sequence[float]) -> list[float]:
    total = 0.0
    out: list[float] = []
    for value in values:
        total += value
        out.append(total)
    return out


def v0_product_rule(digests: Sequence[Hashable]) -> str:
    """The CODEINE v0 rule from ``src/codeine/core.py``, restated for comparison.

    It counts the trailing run of boundaries whose observed state did not change:
    one is CONTINUE, two is SWITCH, three or more is STOP.  It never reads a
    utility, which is exactly why it is a special case rather than a rival.
    """
    trailing = 0
    for index in range(len(digests) - 1, 0, -1):
        if digests[index] == digests[index - 1]:
            trailing += 1
        else:
            break
    if trailing >= 3:
        return "STOP"
    if trailing >= 2:
        return "SWITCH"
    return "CONTINUE"


class Codeine:
    """The continuation operator over the shared substrate."""

    name = "CODEINE"

    def __init__(
        self,
        world: TrajectoryWorld,
        start: str,
        config: CodeineConfig | None = None,
    ) -> None:
        self.world = world
        self.start = start
        self.config = config or CodeineConfig()
        self.verdicts: list[Verdict] = []

    # --- substrate contract ----------------------------------------------
    def observe(self, state: State) -> State:
        representation = dict(state.representation)
        representation.setdefault("current", self.start)
        representation.setdefault("gains", ())
        representation.setdefault("digests", ())
        representation.setdefault("counters", {})
        return state.with_representation(representation)

    def _alternative_estimate(self, state: State) -> float | None:
        """A one-step optimistic estimate for the untried alternatives.

        Deliberately optimistic and deliberately labelled: it is the first-step
        gain the world would give, which the operator may only use because these
        worlds are inspectable.  In an opaque setting this term is ``None`` and the
        SWITCH-on-regime-change branch cannot fire.
        """
        current = state.representation["current"]
        others = [name for name in sorted(self.world.procedures) if name != current]
        if not others:
            return None
        counters = dict(state.representation["counters"])
        estimates = [self.world.step(name, counters.get(name, 0))[0] for name in others]
        return max(estimates) if estimates else None

    def propose(self, state: State) -> list[Candidate]:
        current = state.representation["current"]
        counters = dict(state.representation["counters"])
        candidates: list[Candidate] = []
        for name in sorted(self.world.procedures):
            kind = "continue" if name == current else "switch"
            candidates.append(
                Candidate(
                    name=f"{kind}:{name}",
                    operator=self.name,
                    declared=Declaration(
                        cost=self.world.step_cost,
                        evidence=(f"steps={len(state.representation['gains'])}",),
                        uncertainty=None,
                        information_gain=None,
                        residue={"procedure": name, "kind": kind, "uses": counters.get(name, 0)},
                        invariants=("the trajectory is append-only",),
                    ),
                    payload={"procedure": name, "kind": kind},
                )
            )
        return candidates

    def select(self, state: State, candidates: Sequence[Candidate]) -> Candidate | None:
        gains = list(state.representation["gains"])
        digests = list(state.representation["digests"])
        current = state.representation["current"]
        alternatives = [name for name in sorted(self.world.procedures) if name != current]
        verdict = decide(
            gains,
            digests,
            self.world.step_cost,
            alternatives,
            self.config,
            self._alternative_estimate(state),
        )
        verdict.evidence["v0_product_rule_would_say"] = v0_product_rule(digests)
        verdict.evidence["current_procedure"] = current
        self.verdicts.append(verdict)
        if verdict.action in ("STOP", "ABSTAIN") and len(gains) >= 2:
            return None
        if verdict.action == "ABSTAIN" and len(gains) < 2:
            # Not enough measurement to classify: take one more measured step of
            # the current procedure rather than concluding anything.
            target = current
        elif verdict.action == "SWITCH" and alternatives:
            target = max(
                alternatives,
                key=lambda name: self.world.step(
                    name, dict(state.representation["counters"]).get(name, 0)
                )[0],
            )
        else:
            target = current
        for candidate in candidates:
            if candidate.payload["procedure"] == target:
                return candidate
        return None

    def apply(self, state: State, candidate: Candidate) -> State:
        procedure = candidate.payload["procedure"]
        counters = dict(state.representation["counters"])
        index = counters.get(procedure, 0)
        gain, digest = self.world.step(procedure, index)
        counters[procedure] = index + 1
        representation = dict(state.representation)
        representation["current"] = procedure
        representation["counters"] = counters
        representation["gains"] = tuple(state.representation["gains"]) + (gain,)
        representation["digests"] = tuple(state.representation["digests"]) + (digest,)
        after = state.with_representation(representation).with_observations(
            [Observation(key=f"{procedure}#{index}", value=(gain, digest), source="trajectory")]
        )
        return after.charge(1)

    def validate(self, state: State, candidate: Candidate, after: State) -> bool | None:
        """The trajectory must only grow, and by exactly one step."""
        return len(after.representation["gains"]) == len(state.representation["gains"]) + 1

    def conclude(self, state: State, turn_index: int, validated: bool | None) -> tuple[Decision, str]:
        verdict = self.verdicts[-1]
        if verdict.action == "ABSTAIN":
            # ``insufficient_measurement`` is resolved by measuring, not by
            # concluding.  Abstention only terminates when no step was taken.
            if validated:
                return Decision.CONTINUE, verdict.reason
            return Decision.ABSTAIN, verdict.reason
        if verdict.action == "STOP":
            return Decision.STOP, verdict.reason
        # CONTINUE and SWITCH both applied a step, so the loop keeps running; the
        # distinction between them is recorded in the verdict reason.
        return Decision.CONTINUE, verdict.reason


def payoff_of_run(world: TrajectoryWorld, gains: Sequence[float]) -> float:
    return sum(gains) - world.step_cost * len(gains)


def run_operator(
    world: TrajectoryWorld, start: str, config: CodeineConfig | None = None, max_turns: int = 12
) -> dict[str, object]:
    """Run CODEINE on a world and compare with the exhaustive policy oracle."""
    from ..substrate import Budget, State as SubstrateState, run_loop

    state = SubstrateState(
        representation={"current": start, "gains": (), "digests": (), "counters": {}},
        budget=Budget(total=world.horizon),
    )
    operator = Codeine(world, start, config)
    final, turns = run_loop(operator, state, max_turns=max_turns)
    gains = list(final.representation["gains"])
    oracle = world.best_plan()
    achieved = payoff_of_run(world, gains)
    return {
        "world": world.name,
        "note": world.note,
        "patience": operator.config.patience,
        "actions": [turn.selected.name if turn.selected else "-" for turn in turns],
        "reasons": [turn.reason for turn in turns],
        "final_decision": turns[-1].decision.value if turns else None,
        "steps_taken": len(gains),
        "gains": gains,
        "digests": [str(item) for item in final.representation["digests"]],
        "payoff": achieved,
        "oracle_payoff": oracle["payoff"],
        "oracle_plan": list(oracle["actions"]),
        "regret": float(oracle["payoff"]) - achieved,
        "v0_rule_on_same_digests": v0_product_rule(list(final.representation["digests"])),
        "verdicts": [verdict.as_measurement() for verdict in operator.verdicts],
    }
