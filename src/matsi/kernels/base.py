"""Shared measurement contracts; candidates choose their own representations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol


@dataclass(frozen=True)
class QueryResult:
    value: Any
    cost: int


@dataclass(frozen=True)
class TransformResult:
    representation: Any
    cost: int


class Kernel(Protocol):
    name: str

    def encode(self, value: Any) -> Any: ...

    def decode(self, representation: Any) -> Any: ...

    def size_bytes(self, representation: Any) -> int: ...

    def sharing(self, representation: Any) -> tuple[int, int]: ...

    def query(self, representation: Any, path: Iterable[str | int]) -> QueryResult: ...

    def transform(self, representation: Any, operation: str) -> TransformResult: ...

    def self_description(self) -> dict[str, Any]: ...
