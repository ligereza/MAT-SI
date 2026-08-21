"""Exact and heuristic combinatorial search with measured effort.

Every algorithm here takes the same ``SearchProblem`` and returns the same
``SearchResult``, which carries the node counters used for the complexity
measurements in ``docs/autonomous-operators/complexity.md``.  Nothing is
hardcoded per problem: the worlds supply the problem, the search supplies the
strategy.
"""

from .problem import SearchProblem, SearchResult
from .exact import (
    astar,
    branch_and_bound,
    breadth_first,
    depth_first,
    iterative_deepening,
    uniform_cost,
)
from .heuristic import beam_search, best_first, simulated_annealing

__all__ = [
    "SearchProblem",
    "SearchResult",
    "astar",
    "beam_search",
    "best_first",
    "branch_and_bound",
    "breadth_first",
    "depth_first",
    "iterative_deepening",
    "simulated_annealing",
    "uniform_cost",
]
