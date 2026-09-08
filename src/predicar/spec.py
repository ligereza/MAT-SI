"""Domain-neutral state and observation contracts for PREDICAR."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import comb
from typing import Any, Iterable, Iterator, Mapping


@dataclass(frozen=True)
class CardinalitySpec:
    """A finite universe with an exact number of active elements."""

    universe_size: int
    cardinality: int
    name: str = "finite-set"

    def validate(self) -> None:
        if self.universe_size < 1:
            raise ValueError("universe_size must be positive")
        if not 0 <= self.cardinality <= self.universe_size:
            raise ValueError("cardinality must lie inside the universe")

    @property
    def support_size(self) -> int:
        """Number of valid states; evaluated only when explicitly requested."""
        self.validate()
        return comb(self.universe_size, self.cardinality)


@dataclass(frozen=True)
class BinaryState:
    """One exact-cardinality state represented as a tuple of 0/1 values."""

    values: tuple[int, ...]

    @classmethod
    def from_indices(
        cls, indices: Iterable[int], spec: CardinalitySpec
    ) -> "BinaryState":
        spec.validate()
        selected = tuple(sorted(set(indices)))
        if len(selected) != spec.cardinality:
            raise ValueError("indices do not satisfy the requested cardinality")
        if any(index < 0 or index >= spec.universe_size for index in selected):
            raise ValueError("an index lies outside the universe")
        values = tuple(1 if index in selected else 0 for index in range(spec.universe_size))
        return cls(values)

    def validate(self, spec: CardinalitySpec) -> None:
        spec.validate()
        if len(self.values) != spec.universe_size:
            raise ValueError("state width does not match the universe")
        if any(value not in (0, 1) for value in self.values):
            raise ValueError("state values must be binary")
        if sum(self.values) != spec.cardinality:
            raise ValueError("state does not satisfy exact cardinality")

    def indices(self, spec: CardinalitySpec) -> tuple[int, ...]:
        self.validate(spec)
        return tuple(index for index, value in enumerate(self.values) if value)


def iter_states(spec: CardinalitySpec) -> Iterator[BinaryState]:
    """Enumerate the support lazily; callers must choose to consume it."""

    spec.validate()
    for indices in combinations(range(spec.universe_size), spec.cardinality):
        yield BinaryState.from_indices(indices, spec)


@dataclass(frozen=True)
class Observation:
    """An observed state plus non-semantic context and provenance."""

    state: BinaryState
    ordinal: int
    timestamp: str | None = None
    context: Mapping[str, Any] = field(default_factory=dict)
    source_ref: str = ""


@dataclass(frozen=True)
class PredictionContext:
    """The information allowed at one prequential forecast boundary."""

    history: tuple[Observation, ...]
    horizon: int = 1
    context: Mapping[str, Any] = field(default_factory=dict)
    cutoff: str | None = None

    def validate(self, spec: CardinalitySpec) -> None:
        if self.horizon < 1:
            raise ValueError("horizon must be positive")
        for observation in self.history:
            observation.state.validate(spec)
