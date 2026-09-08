"""Concrete inert baseline definitions for the first future protocol phase."""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import log
from typing import Iterable, Mapping, Sequence

from .contracts import ForecastModel, PredictiveDistribution
from .spec import BinaryState, CardinalitySpec, Observation, PredictionContext


@dataclass(frozen=True)
class UniformExactDistribution:
    spec: CardinalitySpec

    def log_probability(self, state: BinaryState) -> float:
        state.validate(self.spec)
        return -log(self.spec.support_size)

    def marginal_probabilities(self) -> tuple[float, ...]:
        self.spec.validate()
        probability = self.spec.cardinality / self.spec.universe_size
        return tuple(probability for _ in range(self.spec.universe_size))

    def sample(self, count: int, seed: int | None = None) -> Sequence[BinaryState]:
        if count < 0:
            raise ValueError("count must be non-negative")
        rng = random.Random(seed)
        return tuple(
            BinaryState.from_indices(
                rng.sample(range(self.spec.universe_size), self.spec.cardinality),
                self.spec,
            )
            for _ in range(count)
        )


class UniformExactModel(ForecastModel):
    """The exact-support baseline; construction does not fit or load data."""

    model_id = "uniform_exact"

    def __init__(self, spec: CardinalitySpec) -> None:
        self.spec = spec
        self.spec.validate()

    def fit(self, observations: Iterable[Observation]) -> "UniformExactModel":
        # The baseline intentionally ignores observations.
        return self

    def predict(self, context: PredictionContext) -> UniformExactDistribution:
        context.validate(self.spec)
        return UniformExactDistribution(self.spec)

    def describe(self) -> Mapping[str, object]:
        return {
            "model_id": self.model_id,
            "support": "all exact-cardinality states",
            "learned_parameters": False,
            "status": "ready_not_invoked",
        }
