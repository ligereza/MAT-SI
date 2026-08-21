"""Multi-armed bandit policies with measured regret.

Policies:

* ``ucb1`` -- KNOWN_RESULT: expected cumulative regret is ``O(sqrt(K T log T))``
  uniformly over stochastic instances (Auer, Cesa-Bianchi & Fischer,
  *Finite-time analysis of the multiarmed bandit problem*, Machine Learning 2002).
  The guarantee is for a **stationary** environment.
* ``epsilon_greedy`` -- linear regret for fixed epsilon, sublinear for a decaying
  schedule; used as the baseline.
* ``sliding_ucb`` -- UCB over a trailing window, a simple non-stationary variant
  in the spirit of discounted/sliding-window UCB (Garivier & Moulines 2011).  No
  regret bound is claimed for the implementation here; its behaviour on the
  non-stationary world is measured.

Regret is computed against the *realised* best arm of the environment, which the
environment must expose.  That keeps the comparison honest for non-stationary
worlds where "the best arm" changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import log, sqrt
from random import Random
from typing import Callable, Sequence


@dataclass
class BanditRun:
    """One policy trace with everything needed to compute regret."""

    policy: str
    choices: tuple[int, ...] = ()
    rewards: tuple[float, ...] = ()
    best_rewards: tuple[float, ...] = ()
    switches: int = 0
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def total_reward(self) -> float:
        return sum(self.rewards)

    @property
    def cumulative_regret(self) -> float:
        return sum(self.best_rewards) - sum(self.rewards)

    def regret_curve(self) -> tuple[float, ...]:
        curve: list[float] = []
        running = 0.0
        for best, got in zip(self.best_rewards, self.rewards):
            running += best - got
            curve.append(running)
        return tuple(curve)

    def as_measurement(self) -> dict[str, object]:
        return {
            "policy": self.policy,
            "steps": len(self.rewards),
            "total_reward": self.total_reward,
            "cumulative_regret": self.cumulative_regret,
            "switches": self.switches,
            **self.extra,
        }


Environment = Callable[[int, int, Random], tuple[float, float]]
"""``environment(arm, step, rng) -> (reward, best_possible_reward_at_this_step)``."""


def _run(
    policy_name: str,
    choose: Callable[[list[int], list[float], int, Random], int],
    arms: int,
    steps: int,
    environment: Environment,
    seed: int,
) -> BanditRun:
    rng = Random(seed)
    counts = [0] * arms
    totals = [0.0] * arms
    choices: list[int] = []
    rewards: list[float] = []
    best: list[float] = []
    switches = 0
    for step in range(steps):
        arm = choose(counts, totals, step, rng)
        reward, best_reward = environment(arm, step, rng)
        counts[arm] += 1
        totals[arm] += reward
        if choices and choices[-1] != arm:
            switches += 1
        choices.append(arm)
        rewards.append(reward)
        best.append(best_reward)
    return BanditRun(
        policy=policy_name,
        choices=tuple(choices),
        rewards=tuple(rewards),
        best_rewards=tuple(best),
        switches=switches,
    )


def ucb1(arms: int, steps: int, environment: Environment, seed: int = 0) -> BanditRun:
    def choose(counts: list[int], totals: list[float], step: int, rng: Random) -> int:
        for arm in range(arms):
            if counts[arm] == 0:
                return arm
        scores = [
            totals[arm] / counts[arm] + sqrt(2.0 * log(step + 1) / counts[arm])
            for arm in range(arms)
        ]
        return max(range(arms), key=lambda arm: (scores[arm], -arm))

    return _run("ucb1", choose, arms, steps, environment, seed)


def epsilon_greedy(
    arms: int,
    steps: int,
    environment: Environment,
    epsilon: float = 0.1,
    decay: bool = False,
    seed: int = 0,
) -> BanditRun:
    def choose(counts: list[int], totals: list[float], step: int, rng: Random) -> int:
        rate = epsilon / (1.0 + step) ** 0.5 if decay else epsilon
        if rng.random() < rate:
            return rng.randrange(arms)
        means = [totals[arm] / counts[arm] if counts[arm] else 0.0 for arm in range(arms)]
        return max(range(arms), key=lambda arm: (means[arm], -arm))

    run = _run("epsilon_greedy", choose, arms, steps, environment, seed)
    run.extra["epsilon"] = epsilon
    run.extra["decay"] = decay
    return run


def sliding_ucb(
    arms: int, steps: int, environment: Environment, window: int = 40, seed: int = 0
) -> BanditRun:
    """UCB restricted to a trailing window, so stale rewards are forgotten."""
    rng = Random(seed)
    history: list[tuple[int, float]] = []
    choices: list[int] = []
    rewards: list[float] = []
    best: list[float] = []
    switches = 0
    for step in range(steps):
        recent = history[-window:]
        counts = [0] * arms
        totals = [0.0] * arms
        for arm, reward in recent:
            counts[arm] += 1
            totals[arm] += reward
        untried = [arm for arm in range(arms) if counts[arm] == 0]
        if untried:
            arm = untried[0]
        else:
            horizon = max(1, len(recent))
            scores = [
                totals[a] / counts[a] + sqrt(2.0 * log(horizon) / counts[a]) for a in range(arms)
            ]
            arm = max(range(arms), key=lambda a: (scores[a], -a))
        reward, best_reward = environment(arm, step, rng)
        history.append((arm, reward))
        if choices and choices[-1] != arm:
            switches += 1
        choices.append(arm)
        rewards.append(reward)
        best.append(best_reward)
    run = BanditRun(
        policy="sliding_ucb",
        choices=tuple(choices),
        rewards=tuple(rewards),
        best_rewards=tuple(best),
        switches=switches,
    )
    run.extra["window"] = window
    return run


def regret_curve(run: BanditRun) -> tuple[float, ...]:
    return run.regret_curve()
