"""Stable interfaces separating PREDICAR mathematics from research adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol, Sequence

from .spec import BinaryState, CardinalitySpec, Observation, PredictionContext


class PredictiveDistribution(Protocol):
    """A probability distribution over valid states."""

    spec: CardinalitySpec

    def log_probability(self, state: BinaryState) -> float:
        ...

    def marginal_probabilities(self) -> tuple[float, ...]:
        ...

    def sample(self, count: int, seed: int | None = None) -> Sequence[BinaryState]:
        ...


class ForecastModel(ABC):
    """Model contract; concrete models belong to later protocol phases."""

    model_id: str
    spec: CardinalitySpec

    @abstractmethod
    def fit(self, observations: Iterable[Observation]) -> "ForecastModel":
        raise NotImplementedError

    @abstractmethod
    def predict(self, context: PredictionContext) -> PredictiveDistribution:
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> Mapping[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class ResearchArea:
    """One external mature field that can supply models or evaluation methods."""

    area_id: str
    title: str
    mapping: str
    imported_concepts: tuple[str, ...]
    planned_adapters: tuple[str, ...]
    source_refs: tuple[str, ...]
    data_boundary: str
    status: str = "not_started"


@dataclass(frozen=True)
class PrequentialFold:
    """A future-only evaluation boundary; no data is loaded by this record."""

    fold_id: str
    train_end: int
    test_start: int
    test_end: int

    def validate(self) -> None:
        if self.train_end < 1:
            raise ValueError("train_end must be positive")
        if not self.train_end < self.test_start <= self.test_end:
            raise ValueError("fold boundaries must be strictly future-only")


@dataclass(frozen=True)
class ExperimentPlan:
    """Frozen protocol metadata for a run that has not yet been executed."""

    protocol_id: str
    spec: CardinalitySpec
    folds: tuple[PrequentialFold, ...]
    model_ids: tuple[str, ...]
    score_ids: tuple[str, ...]
    placebo_ids: tuple[str, ...]
    random_seed_policy: str
    data_policy: str

    def validate(self) -> None:
        self.spec.validate()
        for fold in self.folds:
            fold.validate()
        if not self.model_ids:
            raise ValueError("at least one model must be named")
        if not self.score_ids:
            raise ValueError("at least one score must be named")


@dataclass(frozen=True)
class ForecastEvidence:
    """One append-only evidence record, aligned with the MAT-SI boundary."""

    record_id: str
    before_ref: str
    intervention_ref: str
    after_ref: str | None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    scores: Mapping[str, float] = field(default_factory=dict)
    residue: Mapping[str, Any] = field(default_factory=dict)
