"""Candidate B: a content-addressed DAG with immutable shared nodes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable

from ..canonical import apply_operation, canonical_text, deep_node_count
from .base import QueryResult, TransformResult


@dataclass(frozen=True)
class Node:
    kind: str
    data: Any


@dataclass(frozen=True)
class Ref:
    cid: str


@dataclass
class ContentDagRepresentation:
    root: Ref
    store: dict[str, Node]


def _node_bytes(node: Node) -> bytes:
    return canonical_text({"kind": node.kind, "data": node.data}).encode("utf-8")


def _cid(node: Node) -> str:
    return hashlib.sha256(_node_bytes(node)).hexdigest()


class _Builder:
    def __init__(self) -> None:
        self.store: dict[str, Node] = {}

    def intern(self, kind: str, data: Any) -> Ref:
        node = Node(kind, data)
        cid = _cid(node)
        self.store.setdefault(cid, node)
        return Ref(cid)

    def encode(self, value: Any) -> Ref:
        if isinstance(value, dict):
            entries = tuple(
                (str(key), self.encode(item).cid) for key, item in sorted(value.items())
            )
            return self.intern("map", entries)
        if isinstance(value, list):
            return self.intern("list", tuple(self.encode(item).cid for item in value))
        return self.intern("atom", {"type": type(value).__name__, "value": value})


def _decode(reference: Ref, store: dict[str, Node], memo: dict[str, Any] | None = None) -> Any:
    memo = {} if memo is None else memo
    if reference.cid in memo:
        return memo[reference.cid]
    node = store[reference.cid]
    if node.kind == "atom":
        value = node.data["value"]
    elif node.kind == "list":
        value = [_decode(Ref(cid), store, memo) for cid in node.data]
    elif node.kind == "map":
        value = {key: _decode(Ref(cid), store, memo) for key, cid in node.data}
    else:
        raise ValueError(f"unknown DAG node kind: {node.kind}")
    memo[reference.cid] = value
    return value


def _query(reference: Ref, store: dict[str, Node], path: tuple[str | int, ...]) -> QueryResult:
    current = reference
    cost = 0
    for segment in path:
        node = store[current.cid]
        cost += 1
        if node.kind == "map":
            for key, cid in node.data:
                cost += 1
                if key == str(segment):
                    current = Ref(cid)
                    break
            else:
                raise KeyError(segment)
        elif node.kind == "list":
            if not isinstance(segment, int) or segment < 0 or segment >= len(node.data):
                raise KeyError(segment)
            current = Ref(node.data[segment])
            cost += segment + 1
        else:
            raise KeyError(segment)
    return QueryResult(_decode(current, store), cost + 1)


class ContentDagKernel:
    name = "content_dag"

    def encode(self, value: Any) -> ContentDagRepresentation:
        builder = _Builder()
        root = builder.encode(value)
        return ContentDagRepresentation(root, builder.store)

    def decode(self, representation: ContentDagRepresentation) -> Any:
        return _decode(representation.root, representation.store)

    def size_bytes(self, representation: ContentDagRepresentation) -> int:
        return sum(len(_node_bytes(node)) for node in representation.store.values()) + len(representation.root.cid)

    def sharing(self, representation: ContentDagRepresentation) -> tuple[int, int]:
        expanded = deep_node_count(self.decode(representation))
        return len(representation.store), expanded

    def query(self, representation: ContentDagRepresentation, path: Iterable[str | int]) -> QueryResult:
        return _query(representation.root, representation.store, tuple(path))

    def transform(self, representation: ContentDagRepresentation, operation: str) -> TransformResult:
        before = len(representation.store)
        result = apply_operation(self.decode(representation), operation)
        transformed = self.encode(result)
        created = len(transformed.store)
        return TransformResult(transformed, before + created)

    def self_description(self) -> dict[str, Any]:
        return {
            "kernel": self.name,
            "primitives": ["node", "content identifier", "link"],
            "identity": "sha256(canonical node)",
            "transformations": ["append immutable nodes", "redirect root"],
            "costs": ["block bytes", "link traversal", "new nodes"],
            "history": "content-addressed roots linked by an external log",
            "self_reference": self.name,
        }
