"""Candidate A: an atom and binary-pair calculus without sharing."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable

from ..canonical import apply_operation, canonical_text, deep_node_count
from .base import QueryResult, TransformResult


@dataclass(frozen=True)
class Atom:
    value: str


@dataclass(frozen=True)
class Pair:
    left: "Term"
    right: "Term"


Term = Atom | Pair


@dataclass(frozen=True)
class AtomPairRepresentation:
    root: Term


def _chain(items: list[Term]) -> Term:
    result: Term = Atom("nil")
    for item in reversed(items):
        result = Pair(item, result)
    return result


def _atom(value: Any) -> Atom:
    return Atom("scalar:" + canonical_text(value))


def _encode(value: Any) -> Term:
    if isinstance(value, dict):
        entries = [Pair(Atom("key:" + str(key)), _encode(item)) for key, item in sorted(value.items())]
        return Pair(Atom("map"), _chain(entries))
    if isinstance(value, list):
        return Pair(Atom("list"), _chain([_encode(item) for item in value]))
    return Pair(Atom("atom"), _atom(value))


def _decode(term: Term) -> Any:
    if not isinstance(term, Pair):
        raise ValueError("malformed atom-pair term")
    if term.left == Atom("atom") and isinstance(term.right, Atom):
        if not term.right.value.startswith("scalar:"):
            raise ValueError("malformed scalar atom")
        return json.loads(term.right.value[len("scalar:"):])
    if term.left == Atom("list"):
        return [_decode(item) for item in _items(term.right)]
    if term.left == Atom("map"):
        result: dict[str, Any] = {}
        for entry in _items(term.right):
            if not isinstance(entry, Pair) or not isinstance(entry.left, Atom):
                raise ValueError("malformed map entry")
            if not entry.left.value.startswith("key:"):
                raise ValueError("malformed map key")
            result[entry.left.value[len("key:"):]] = _decode(entry.right)
        return result
    raise ValueError("unknown atom-pair tag")


def _items(term: Term) -> list[Term]:
    items: list[Term] = []
    current = term
    while current != Atom("nil"):
        if not isinstance(current, Pair):
            raise ValueError("malformed list chain")
        items.append(current.left)
        current = current.right
    return items


def _render(term: Term) -> str:
    if isinstance(term, Atom):
        return "a(" + term.value + ")"
    return "p(" + _render(term.left) + "," + _render(term.right) + ")"


def _count(term: Term) -> int:
    if isinstance(term, Atom):
        return 1
    return 1 + _count(term.left) + _count(term.right)


def _query(term: Term, path: tuple[str | int, ...]) -> QueryResult:
    current = term
    cost = 0
    for segment in path:
        if not isinstance(current, Pair):
            raise KeyError(segment)
        tag = current.left
        cost += 1
        if tag == Atom("map"):
            found = False
            for entry in _items(current.right):
                cost += 1
                if isinstance(entry, Pair) and entry.left == Atom("key:" + str(segment)):
                    current = entry.right
                    found = True
                    break
            if not found:
                raise KeyError(segment)
        elif tag == Atom("list"):
            if not isinstance(segment, int):
                raise KeyError(segment)
            values = _items(current.right)
            if segment < 0 or segment >= len(values):
                raise KeyError(segment)
            cost += segment + 1
            current = values[segment]
        else:
            raise KeyError(segment)
    return QueryResult(_decode(current), cost + 1)


class AtomPairKernel:
    name = "atom_pair"

    def encode(self, value: Any) -> AtomPairRepresentation:
        return AtomPairRepresentation(_encode(value))

    def decode(self, representation: AtomPairRepresentation) -> Any:
        return _decode(representation.root)

    def size_bytes(self, representation: AtomPairRepresentation) -> int:
        return len(_render(representation.root).encode("utf-8"))

    def sharing(self, representation: AtomPairRepresentation) -> tuple[int, int]:
        count = _count(representation.root)
        return count, count

    def query(self, representation: AtomPairRepresentation, path: Iterable[str | int]) -> QueryResult:
        return _query(representation.root, tuple(path))

    def transform(self, representation: AtomPairRepresentation, operation: str) -> TransformResult:
        source = self.decode(representation)
        result = apply_operation(source, operation)
        transformed = self.encode(result)
        return TransformResult(transformed, _count(representation.root) + _count(transformed.root))

    def self_description(self) -> dict[str, Any]:
        return {
            "kernel": self.name,
            "primitives": ["atom", "pair"],
            "identity": "positional tree identity",
            "transformations": ["decode", "apply operation", "re-encode"],
            "costs": ["description size", "tree traversal"],
            "history": "external sequence of complete roots",
            "self_reference": self.name,
        }
