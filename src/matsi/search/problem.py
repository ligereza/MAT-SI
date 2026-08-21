"""The one search interface every MAT-SI search algorithm consumes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Hashable, Iterable, Sequence


@dataclass(frozen=True)
class SearchProblem:
    """A deterministic state-space search problem.

    ``successors(state)`` yields ``(action, next_state, step_cost)``.  States must
    be hashable so closed sets and canonical labelling work.  ``heuristic`` must
    return a non-negative estimate; admissibility is the caller's claim and is
    checked empirically in the tests, never assumed by the algorithms.
    """

    start: Hashable
    successors: Callable[[Hashable], Iterable[tuple[Any, Hashable, float]]]
    is_goal: Callable[[Hashable], bool]
    heuristic: Callable[[Hashable], float] = lambda _state: 0.0
    upper_bound: float | None = None


@dataclass
class SearchResult:
    """Outcome plus the effort it took, so cost can be measured not asserted."""

    found: bool
    goal: Hashable | None = None
    path: tuple[Any, ...] = ()
    cost: float | None = None
    expanded: int = 0
    generated: int = 0
    max_frontier: int = 0
    iterations: int = 0
    exhausted: bool = False
    truncated: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def as_measurement(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "cost": self.cost,
            "expanded": self.expanded,
            "generated": self.generated,
            "max_frontier": self.max_frontier,
            "iterations": self.iterations,
            "exhausted": self.exhausted,
            "truncated": self.truncated,
            **self.extra,
        }


def reconstruct(parents: dict[Hashable, tuple[Hashable, Any] | None], goal: Hashable) -> tuple[Any, ...]:
    """Walk a parent map back to the start and return the action sequence."""
    actions: list[Any] = []
    cursor: Hashable | None = goal
    while cursor is not None:
        entry = parents.get(cursor)
        if entry is None:
            break
        parent, action = entry
        actions.append(action)
        cursor = parent
    return tuple(reversed(actions))


def path_cost(problem: SearchProblem, actions: Sequence[Any]) -> float:
    """Replay an action sequence from the start and total its step costs."""
    state = problem.start
    total = 0.0
    for action in actions:
        for candidate_action, next_state, step in problem.successors(state):
            if candidate_action == action:
                total += step
                state = next_state
                break
        else:
            raise ValueError(f"action {action!r} is not available from {state!r}")
    return total
