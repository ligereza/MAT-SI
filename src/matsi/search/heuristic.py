"""Incomplete search: greedy best-first, beam, simulated annealing.

These trade completeness for effort, so they are only ever compared against the
exact algorithms in ``exact.py`` on instances small enough for an oracle.  Beam
search is the vehicle for the KETAMINE pruning counterexample: it is provably
incomplete, and ``docs/autonomous-operators/counterexamples.md`` records a family
of instances where every width below the branching factor discards the unique
optimum.
"""

from __future__ import annotations

from heapq import heappop, heappush
from itertools import count
from math import exp
from random import Random
from typing import Callable, Hashable

from .problem import SearchProblem, SearchResult, reconstruct


def best_first(problem: SearchProblem, node_limit: int = 200_000) -> SearchResult:
    """Greedy best-first: order by heuristic only.  Not optimal, not complete."""
    result = SearchResult(found=False)
    tie = count()
    frontier: list[tuple[float, int, Hashable, float]] = [
        (problem.heuristic(problem.start), next(tie), problem.start, 0.0)
    ]
    parents: dict[Hashable, tuple[Hashable, object] | None] = {problem.start: None}
    closed: set[Hashable] = set()
    result.generated = 1
    while frontier:
        result.max_frontier = max(result.max_frontier, len(frontier))
        _priority, _order, state, cost = heappop(frontier)
        if state in closed:
            continue
        closed.add(state)
        result.expanded += 1
        if result.expanded > node_limit:
            result.truncated = True
            return result
        if problem.is_goal(state):
            result.found = True
            result.goal = state
            result.path = reconstruct(parents, state)
            result.cost = cost
            return result
        for action, next_state, step in problem.successors(state):
            result.generated += 1
            if next_state in closed:
                continue
            parents.setdefault(next_state, (state, action))
            heappush(frontier, (problem.heuristic(next_state), next(tie), next_state, cost + step))
    result.exhausted = True
    return result


def beam_search(problem: SearchProblem, width: int, max_depth: int = 64) -> SearchResult:
    """Layered beam search keeping the ``width`` best nodes per depth.

    Incomplete by construction: a node outside the beam at some depth is never
    revisited, so an optimum whose prefix scores badly is unreachable.  The
    number of discarded nodes is reported for the pruning experiments.
    """
    if width < 1:
        raise ValueError("beam width must be at least 1")
    result = SearchResult(found=False)
    layer: list[tuple[Hashable, tuple[object, ...], float]] = [(problem.start, (), 0.0)]
    discarded = 0
    seen: set[Hashable] = {problem.start}
    result.generated = 1
    for depth in range(max_depth):
        result.iterations = depth + 1
        if not layer:
            break
        result.max_frontier = max(result.max_frontier, len(layer))
        for state, actions, cost in layer:
            result.expanded += 1
            if problem.is_goal(state):
                result.found = True
                result.goal = state
                result.path = actions
                result.cost = cost
                result.extra["discarded_nodes"] = discarded
                return result
        children: list[tuple[float, Hashable, tuple[object, ...], float]] = []
        for state, actions, cost in layer:
            for action, next_state, step in problem.successors(state):
                result.generated += 1
                if next_state in seen:
                    continue
                children.append(
                    (
                        cost + step + problem.heuristic(next_state),
                        next_state,
                        actions + (action,),
                        cost + step,
                    )
                )
        children.sort(key=lambda item: (item[0], repr(item[1])))
        kept = children[:width]
        discarded += max(0, len(children) - len(kept))
        for _score, state, _actions, _cost in kept:
            seen.add(state)
        layer = [(state, actions, cost) for _score, state, actions, cost in kept]
    result.extra["discarded_nodes"] = discarded
    return result


def simulated_annealing(
    energy: Callable[[Hashable], float],
    neighbours: Callable[[Hashable, Random], Hashable],
    start: Hashable,
    steps: int = 2000,
    initial_temperature: float = 1.0,
    seed: int = 0,
) -> SearchResult:
    """Metropolis-Hastings descent with a geometric cooling schedule.

    Deterministic given ``seed``.  No convergence claim is made: the schedule
    used here is the practical geometric one, not the logarithmic schedule for
    which asymptotic convergence in probability is known (Geman & Geman 1984).
    """
    if steps < 1:
        raise ValueError("steps must be positive")
    rng = Random(seed)
    current = start
    current_energy = energy(current)
    best, best_energy = current, current_energy
    accepted = 0
    for step in range(steps):
        temperature = initial_temperature * (0.995 ** step)
        if temperature <= 1e-12:
            break
        proposal = neighbours(current, rng)
        proposal_energy = energy(proposal)
        delta = proposal_energy - current_energy
        if delta <= 0 or rng.random() < exp(-delta / temperature):
            current, current_energy = proposal, proposal_energy
            accepted += 1
            if current_energy < best_energy:
                best, best_energy = current, current_energy
    return SearchResult(
        found=True,
        goal=best,
        cost=best_energy,
        expanded=steps,
        generated=steps,
        iterations=steps,
        extra={"accepted_moves": accepted, "final_energy": current_energy},
    )
