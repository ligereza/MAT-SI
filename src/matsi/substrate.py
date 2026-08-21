"""The shared MAT-SI research substrate.

A research state is provisionally

    S = (R, O, H, M, B)

with ``R`` a representation, ``O`` observations, ``H`` candidate transformations,
``M`` memory and ``B`` a computational budget.  An operation is a partial map
``T : S -> S'`` that must declare, for every candidate it proposes,

    cost, evidence, uncertainty, information_gain, residue, invariants

The declarations are *claims by the proposing operator*, not measurements of the
world.  ``Candidate.declared`` therefore carries them separately from anything a
validator later confirms, so an unverified estimate can never be mistaken for an
observation.  This mirrors the Phase 4C separation between a raw record and a
derived hypothesis.

Nothing here interprets a domain.  Representations, observation payloads and
residues stay opaque; only their identity, cost and declared quantities are
substrate-level notions.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Callable, Iterable, Protocol, Sequence


class Decision(str, Enum):
    """What an autonomous operator may conclude after one loop turn."""

    CONTINUE = "CONTINUE"
    SWITCH = "SWITCH"
    ABSTAIN = "ABSTAIN"
    STOP = "STOP"


@dataclass(frozen=True)
class Budget:
    """A computational budget in abstract units of work."""

    total: int
    spent: int = 0

    def remaining(self) -> int:
        return max(0, self.total - self.spent)

    def exhausted(self) -> bool:
        return self.remaining() <= 0

    def charge(self, units: int) -> "Budget":
        if units < 0:
            raise ValueError("budget charge must be non-negative")
        return replace(self, spent=self.spent + units)


@dataclass(frozen=True)
class Observation:
    """One observation with an opaque payload and an explicit source."""

    key: str
    value: Any
    source: str = "world"

    def identity(self) -> str:
        return self.key


@dataclass(frozen=True)
class Declaration:
    """The quantities an operation must declare about itself.

    ``information_gain`` is in bits when the operator can compute one, otherwise
    ``None``.  ``None`` means *not declared*; it never means zero.
    """

    cost: float
    evidence: tuple[str, ...] = ()
    uncertainty: float | None = None
    information_gain: float | None = None
    residue: Any = None
    invariants: tuple[str, ...] = ()

    def value_per_cost(self) -> float | None:
        if self.information_gain is None or self.cost <= 0:
            return None
        return self.information_gain / self.cost


@dataclass(frozen=True)
class Candidate:
    """A proposed transformation together with its declarations."""

    name: str
    operator: str
    declared: Declaration
    payload: Any = None

    def identity(self) -> str:
        return f"{self.operator}:{self.name}"


@dataclass(frozen=True)
class Memory:
    """Append-only research memory.

    ``seen`` holds observation identities, ``records`` holds one entry per
    applied transformation and ``notes`` holds operator-private state keyed by
    operator name.  Memory never stores a semantic verdict such as progress or
    success; it stores what happened.
    """

    seen: frozenset[str] = frozenset()
    records: tuple[dict[str, Any], ...] = ()
    notes: dict[str, Any] = field(default_factory=dict)

    def with_seen(self, keys: Iterable[str]) -> "Memory":
        return replace(self, seen=self.seen | frozenset(keys))

    def with_record(self, record: dict[str, Any]) -> "Memory":
        return replace(self, records=self.records + (dict(record),))

    def with_note(self, operator: str, note: Any) -> "Memory":
        notes = dict(self.notes)
        notes[operator] = note
        return replace(self, notes=notes)


@dataclass(frozen=True)
class State:
    """S = (R, O, H, M, B)."""

    representation: Any
    observations: tuple[Observation, ...] = ()
    hypotheses: tuple[Candidate, ...] = ()
    memory: Memory = field(default_factory=Memory)
    budget: Budget = field(default_factory=lambda: Budget(total=0))

    def with_observations(self, new: Sequence[Observation]) -> "State":
        return replace(
            self,
            observations=self.observations + tuple(new),
            memory=self.memory.with_seen(item.identity() for item in new),
        )

    def with_representation(self, representation: Any) -> "State":
        return replace(self, representation=representation)

    def with_hypotheses(self, hypotheses: Sequence[Candidate]) -> "State":
        return replace(self, hypotheses=tuple(hypotheses))

    def charge(self, units: int) -> "State":
        return replace(self, budget=self.budget.charge(units))


@dataclass(frozen=True)
class Turn:
    """One completed pass of the autonomy loop."""

    index: int
    proposed: tuple[Candidate, ...]
    selected: Candidate | None
    validated: bool | None
    decision: Decision
    reason: str
    cost_charged: int
    measurements: dict[str, Any] = field(default_factory=dict)


class Operator(Protocol):
    """An autonomous operator over the shared substrate.

    The loop is fixed; the mathematics lives in ``propose``, ``estimate``,
    ``select``, ``validate`` and ``conclude``.  An operator that cannot justify
    any candidate must return ``ABSTAIN`` rather than a default action.
    """

    name: str

    def observe(self, state: State) -> State: ...

    def propose(self, state: State) -> Sequence[Candidate]: ...

    def select(self, state: State, candidates: Sequence[Candidate]) -> Candidate | None: ...

    def apply(self, state: State, candidate: Candidate) -> State: ...

    def validate(self, state: State, candidate: Candidate, after: State) -> bool | None: ...

    def conclude(self, state: State, turn_index: int, validated: bool | None) -> tuple[Decision, str]: ...


def run_loop(
    operator: Operator,
    state: State,
    max_turns: int = 64,
    on_turn: Callable[[Turn, State], None] | None = None,
) -> tuple[State, list[Turn]]:
    """Run OBSERVE -> PROPOSE -> ESTIMATE -> SELECT -> APPLY -> VALIDATE -> UPDATE.

    The loop itself decides nothing about the domain.  It stops when the operator
    concludes ``STOP``, when the budget is exhausted, or after ``max_turns``.
    ``ABSTAIN`` ends the loop without claiming a conclusion about the world.
    """
    turns: list[Turn] = []
    for index in range(max_turns):
        if state.budget.exhausted():
            turns.append(
                Turn(
                    index=index,
                    proposed=(),
                    selected=None,
                    validated=None,
                    decision=Decision.STOP,
                    reason="budget exhausted",
                    cost_charged=0,
                )
            )
            break
        before_spent = state.budget.spent
        state = operator.observe(state)
        candidates = tuple(operator.propose(state))
        state = state.with_hypotheses(candidates)
        chosen = operator.select(state, candidates)
        if chosen is None:
            decision, reason = operator.conclude(state, index, None)
            if decision is Decision.CONTINUE:
                decision, reason = Decision.ABSTAIN, "no candidate could be justified"
            turns.append(
                Turn(
                    index=index,
                    proposed=candidates,
                    selected=None,
                    validated=None,
                    decision=decision,
                    reason=reason,
                    cost_charged=state.budget.spent - before_spent,
                )
            )
            break
        after = operator.apply(state, chosen)
        validated = operator.validate(state, chosen, after)
        state = after if validated is not False else state
        state = replace(
            state,
            memory=state.memory.with_record(
                {
                    "turn": index,
                    "candidate": chosen.identity(),
                    "declared_cost": chosen.declared.cost,
                    "declared_information_gain": chosen.declared.information_gain,
                    "validated": validated,
                }
            ),
        )
        decision, reason = operator.conclude(state, index, validated)
        turn = Turn(
            index=index,
            proposed=candidates,
            selected=chosen,
            validated=validated,
            decision=decision,
            reason=reason,
            cost_charged=state.budget.spent - before_spent,
        )
        turns.append(turn)
        if on_turn is not None:
            on_turn(turn, state)
        if decision in (Decision.STOP, Decision.ABSTAIN):
            break
    return state, turns
