"""Shared measurement contracts; candidates choose their own representations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol


@dataclass(frozen=True)
class QueryResult:
    value: Any
    cost: int
    nodes_visited: int = 0


@dataclass(frozen=True)
class TransformResult:
    representation: Any
    cost: int
    nodes_visited: int = 0


@dataclass(frozen=True)
class SelfApplicationResult:
    """Evidence that a kernel can inspect and transform its own model."""

    model: dict[str, Any]
    query_path: tuple[str | int, ...]
    queried_value: Any
    expected_query_value: Any
    transformed_value: Any
    expected_transformed_value: Any
    model_round_trip: bool
    model_transform_ok: bool
    query_ok: bool
    transform_ok: bool


def run_self_application(kernel: Any) -> SelfApplicationResult:
    """Run MATSI(MATSI) without adding an identity primitive to a kernel.

    The kernel describes its actual evaluator and rewrite table as ordinary data.
    That data is encoded, queried, and then one of its rule records is transformed
    through the same public encode/transform/decode path used by corpus objects.
    """

    model = kernel.self_description()
    representation = kernel.encode(model)
    decoded_model = kernel.decode(representation)
    model_transform = kernel.transform(representation, "identity")
    model_transform_ok = kernel.decode(model_transform.representation) == model
    query_path = ("rules", 0, "name")
    query_result = kernel.query(representation, query_path)
    rules = model["rules"]
    transformed = kernel.transform(kernel.encode(rules), "reverse")
    transformed_value = kernel.decode(transformed.representation)
    expected_transformed = list(reversed(rules))
    expected_query = rules[0]["name"]
    return SelfApplicationResult(
        model=model,
        query_path=query_path,
        queried_value=query_result.value,
        expected_query_value=expected_query,
        transformed_value=transformed_value,
        expected_transformed_value=expected_transformed,
        model_round_trip=decoded_model == model,
        model_transform_ok=model_transform_ok,
        query_ok=query_result.value == expected_query,
        transform_ok=model_transform_ok and transformed_value == expected_transformed,
    )


class Kernel(Protocol):
    name: str

    def encode(self, value: Any) -> Any: ...

    def decode(self, representation: Any) -> Any: ...

    def size_bytes(self, representation: Any) -> int: ...

    def sharing(self, representation: Any) -> tuple[int, int]: ...

    def query(self, representation: Any, path: Iterable[str | int]) -> QueryResult: ...

    def transform(self, representation: Any, operation: str) -> TransformResult: ...

    def self_description(self) -> dict[str, Any]: ...

    def storage_breakdown(self, representation: Any) -> dict[str, int]: ...

    def self_application(self) -> SelfApplicationResult: ...
