"""Optimal stopping by backward induction, and the classical secretary rule.

Two settings are implemented because they answer different questions:

* ``optimal_stopping_threshold`` -- finite horizon, known i.i.d. value
  distribution, one irrevocable choice, payoff = value of the accepted item minus
  a per-step continuation cost.  Backward induction gives the exact optimal
  threshold for every remaining horizon -- PROVED: the value function satisfies
  ``V_k = E[max(x, V_{k-1} - c)]`` and the optimal rule accepts iff
  ``x >= V_{k-1} - c`` (Chow, Robbins & Siegmund, *Great Expectations*, 1971).
  ``tests/test_sequential.py`` compares the policy against exhaustive enumeration
  of all value sequences on small instances.
* ``secretary_stopping`` -- unknown distribution, relative ranks only.  The
  optimal rule observes ``n/e`` items then takes the next record -- KNOWN_RESULT
  (Lindley 1961; Dynkin 1963), success probability ``-> 1/e``.

The distinction matters for CODEINE: with a known value scale the threshold rule
applies, and without one only rank information is available.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import e
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class StoppingPolicy:
    """Thresholds indexed by the number of remaining opportunities."""

    thresholds: tuple[float, ...]
    continuation_cost: float
    expected_value: float
    method: str

    def accept(self, value: float, remaining: int) -> bool:
        if remaining <= 1:
            return True
        index = min(remaining - 1, len(self.thresholds) - 1)
        return value >= self.thresholds[index]


def optimal_stopping_threshold(
    distribution: Mapping[float, float],
    horizon: int,
    continuation_cost: float = 0.0,
) -> StoppingPolicy:
    """Exact backward induction over a finite value distribution."""
    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    total = sum(distribution.values())
    if abs(total - 1.0) > 1e-7:
        raise ValueError("distribution must sum to 1")
    thresholds = [float("-inf")]  # with one opportunity left you must accept
    value = sum(item * probability for item, probability in distribution.items())
    for _ in range(1, horizon):
        threshold = value - continuation_cost
        thresholds.append(threshold)
        value = sum(
            probability * max(item, threshold) for item, probability in distribution.items()
        )
    return StoppingPolicy(
        thresholds=tuple(thresholds),
        continuation_cost=continuation_cost,
        expected_value=value,
        method="backward_induction",
    )


def run_stopping_policy(
    policy: StoppingPolicy, values: Sequence[float]
) -> dict[str, object]:
    """Apply a threshold policy to one realised sequence."""
    horizon = len(values)
    for index, value in enumerate(values):
        remaining = horizon - index
        if policy.accept(value, remaining):
            return {
                "stopped_at": index,
                "accepted": value,
                "payoff": value - policy.continuation_cost * index,
                "observed": index + 1,
            }
    return {
        "stopped_at": None,
        "accepted": values[-1] if values else None,
        "payoff": (values[-1] if values else 0.0) - policy.continuation_cost * (horizon - 1),
        "observed": horizon,
    }


def exhaustive_best_stopping(
    values: Sequence[float], continuation_cost: float = 0.0
) -> dict[str, object]:
    """The best achievable payoff with hindsight: the oracle to compare against."""
    if not values:
        return {"stopped_at": None, "payoff": 0.0}
    best_index = max(
        range(len(values)), key=lambda index: values[index] - continuation_cost * index
    )
    return {
        "stopped_at": best_index,
        "accepted": values[best_index],
        "payoff": values[best_index] - continuation_cost * best_index,
    }


def secretary_stopping(values: Sequence[float]) -> dict[str, object]:
    """Observe ``n/e`` items, then accept the first record; rank information only."""
    horizon = len(values)
    if horizon == 0:
        return {"stopped_at": None, "accepted": None, "found_best": False}
    cutoff = max(1, int(horizon / e))
    best_seen = max(values[:cutoff]) if cutoff else float("-inf")
    for index in range(cutoff, horizon):
        if values[index] > best_seen:
            return {
                "stopped_at": index,
                "accepted": values[index],
                "found_best": values[index] == max(values),
                "cutoff": cutoff,
            }
    return {
        "stopped_at": horizon - 1,
        "accepted": values[-1],
        "found_best": values[-1] == max(values),
        "cutoff": cutoff,
    }


def value_of_information(
    prior_best: float,
    outcomes: Mapping[float, float],
    query_cost: float,
) -> dict[str, float]:
    """Expected value of one perfect observation before choosing.

    ``EVPI = E[max(prior_best, outcome)] - prior_best``; the query is worth making
    only when ``EVPI > query_cost`` (Howard, *Information Value Theory*, 1966).
    """
    expected = sum(
        probability * max(prior_best, outcome) for outcome, probability in outcomes.items()
    )
    evpi = expected - prior_best
    return {
        "expected_with_information": expected,
        "expected_value_of_perfect_information": evpi,
        "query_cost": query_cost,
        "net_value": evpi - query_cost,
        "worth_querying": evpi > query_cost,
    }
