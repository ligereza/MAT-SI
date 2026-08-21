"""Complete search: BFS, DFS, uniform cost, A*, iterative deepening, B&B.

Proof status of the guarantees relied on elsewhere:

* ``breadth_first`` returns a path with the fewest actions -- PROVED (standard;
  BFS expands in non-decreasing depth order).
* ``uniform_cost`` returns a minimum-cost path when all step costs are
  non-negative -- PROVED (Dijkstra 1959).
* ``astar`` returns a minimum-cost path when the heuristic is admissible, and is
  additionally optimally efficient among admissible algorithms using the same
  heuristic -- KNOWN_RESULT (Hart, Nilsson & Raphael 1968; Dechter & Pearl 1985).
  Admissibility is *not* checked here; ``tests/test_search.py`` compares A* to
  uniform cost on generated instances, which is an empirical check.
* ``iterative_deepening`` finds the shallowest goal using O(depth) memory --
  PROVED (Korf 1985).
* ``branch_and_bound`` returns an optimal solution when the bound function is a
  valid lower bound on completions -- PROVED for the finite acyclic case.
"""

from __future__ import annotations

from collections import deque
from heapq import heappop, heappush
from itertools import count
from typing import Hashable

from .problem import SearchProblem, SearchResult, reconstruct

MAX_NODES = 2_000_000


def breadth_first(problem: SearchProblem, node_limit: int = MAX_NODES) -> SearchResult:
    result = SearchResult(found=False)
    if problem.is_goal(problem.start):
        return SearchResult(found=True, goal=problem.start, path=(), cost=0.0, expanded=0, generated=1)
    frontier: deque[tuple[Hashable, float]] = deque([(problem.start, 0.0)])
    parents: dict[Hashable, tuple[Hashable, object] | None] = {problem.start: None}
    result.generated = 1
    while frontier:
        result.max_frontier = max(result.max_frontier, len(frontier))
        state, cost = frontier.popleft()
        result.expanded += 1
        if result.expanded > node_limit:
            result.truncated = True
            return result
        for action, next_state, step in problem.successors(state):
            if next_state in parents:
                continue
            parents[next_state] = (state, action)
            result.generated += 1
            if problem.is_goal(next_state):
                result.found = True
                result.goal = next_state
                result.path = reconstruct(parents, next_state)
                result.cost = cost + step
                return result
            frontier.append((next_state, cost + step))
    result.exhausted = True
    return result


def depth_first(problem: SearchProblem, depth_limit: int | None = None, node_limit: int = MAX_NODES) -> SearchResult:
    result = SearchResult(found=False)
    stack: list[tuple[Hashable, tuple[object, ...], float, int]] = [(problem.start, (), 0.0, 0)]
    visited: set[Hashable] = set()
    result.generated = 1
    while stack:
        result.max_frontier = max(result.max_frontier, len(stack))
        state, actions, cost, depth = stack.pop()
        if state in visited:
            continue
        visited.add(state)
        result.expanded += 1
        if result.expanded > node_limit:
            result.truncated = True
            return result
        if problem.is_goal(state):
            result.found = True
            result.goal = state
            result.path = actions
            result.cost = cost
            return result
        if depth_limit is not None and depth >= depth_limit:
            continue
        for action, next_state, step in problem.successors(state):
            result.generated += 1
            if next_state not in visited:
                stack.append((next_state, actions + (action,), cost + step, depth + 1))
    result.exhausted = True
    return result


def _best_first_complete(
    problem: SearchProblem,
    use_heuristic: bool,
    node_limit: int,
) -> SearchResult:
    result = SearchResult(found=False)
    tie = count()
    start_h = problem.heuristic(problem.start) if use_heuristic else 0.0
    frontier: list[tuple[float, int, Hashable]] = [(start_h, next(tie), problem.start)]
    best_cost: dict[Hashable, float] = {problem.start: 0.0}
    parents: dict[Hashable, tuple[Hashable, object] | None] = {problem.start: None}
    closed: set[Hashable] = set()
    result.generated = 1
    while frontier:
        result.max_frontier = max(result.max_frontier, len(frontier))
        _priority, _order, state = heappop(frontier)
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
            result.cost = best_cost[state]
            return result
        for action, next_state, step in problem.successors(state):
            if step < 0:
                raise ValueError("negative step cost is not supported")
            tentative = best_cost[state] + step
            result.generated += 1
            if tentative < best_cost.get(next_state, float("inf")):
                best_cost[next_state] = tentative
                parents[next_state] = (state, action)
                estimate = problem.heuristic(next_state) if use_heuristic else 0.0
                heappush(frontier, (tentative + estimate, next(tie), next_state))
    result.exhausted = True
    return result


def uniform_cost(problem: SearchProblem, node_limit: int = MAX_NODES) -> SearchResult:
    return _best_first_complete(problem, use_heuristic=False, node_limit=node_limit)


def astar(problem: SearchProblem, node_limit: int = MAX_NODES) -> SearchResult:
    return _best_first_complete(problem, use_heuristic=True, node_limit=node_limit)


def iterative_deepening(problem: SearchProblem, max_depth: int = 64, node_limit: int = MAX_NODES) -> SearchResult:
    total = SearchResult(found=False)
    for depth in range(max_depth + 1):
        attempt = depth_first(problem, depth_limit=depth, node_limit=node_limit)
        total.expanded += attempt.expanded
        total.generated += attempt.generated
        total.max_frontier = max(total.max_frontier, attempt.max_frontier)
        total.iterations = depth + 1
        if attempt.truncated:
            total.truncated = True
            return total
        if attempt.found:
            total.found = True
            total.goal = attempt.goal
            total.path = attempt.path
            total.cost = attempt.cost
            return total
    total.exhausted = True
    return total


def branch_and_bound(
    problem: SearchProblem,
    bound: "callable[[Hashable, float], float] | None" = None,
    node_limit: int = MAX_NODES,
) -> SearchResult:
    """Depth-first branch and bound over a finite acyclic space.

    ``bound(state, cost_so_far)`` must be a lower bound on the total cost of any
    completion through ``state``.  With the default bound (cost so far plus the
    problem heuristic) the procedure is exact whenever the heuristic is
    admissible; the pruning counter is reported so pruning can be studied rather
    than trusted.
    """
    if bound is None:

        def bound(state: Hashable, cost_so_far: float) -> float:  # type: ignore[misc]
            return cost_so_far + problem.heuristic(state)

    result = SearchResult(found=False)
    incumbent = problem.upper_bound if problem.upper_bound is not None else float("inf")
    best: tuple[Hashable, tuple[object, ...], float] | None = None
    pruned = 0
    stack: list[tuple[Hashable, tuple[object, ...], float, frozenset[Hashable]]] = [
        (problem.start, (), 0.0, frozenset({problem.start}))
    ]
    result.generated = 1
    while stack:
        result.max_frontier = max(result.max_frontier, len(stack))
        state, actions, cost, on_path = stack.pop()
        result.expanded += 1
        if result.expanded > node_limit:
            result.truncated = True
            break
        if bound(state, cost) >= incumbent:
            pruned += 1
            continue
        if problem.is_goal(state):
            if cost < incumbent:
                incumbent = cost
                best = (state, actions, cost)
            continue
        for action, next_state, step in problem.successors(state):
            result.generated += 1
            if next_state in on_path:
                continue
            stack.append((next_state, actions + (action,), cost + step, on_path | {next_state}))
    if best is not None:
        result.found = True
        result.goal, result.path, result.cost = best
    else:
        result.exhausted = not result.truncated
    result.extra["pruned_subtrees"] = pruned
    result.extra["incumbent"] = None if incumbent == float("inf") else incumbent
    return result
