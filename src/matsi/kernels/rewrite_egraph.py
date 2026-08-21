"""Candidate C: an e-graph with lightweight equality-saturation rewrites."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable

from ..canonical import apply_operation, canonical_text, deep_node_count
from .base import QueryResult, TransformResult


Term = tuple[str, tuple[Any, ...]]


@dataclass(frozen=True)
class ENode:
    operation: str
    children: tuple[int, ...]
    value: str | None = None


class EGraph:
    def __init__(self) -> None:
        self.parent: list[int] = []
        self.classes: list[set[ENode]] = []
        self.hashcons: dict[ENode, int] = {}
        self.merge_count = 0

    def find(self, class_id: int) -> int:
        while self.parent[class_id] != class_id:
            self.parent[class_id] = self.parent[self.parent[class_id]]
            class_id = self.parent[class_id]
        return class_id

    def add_enode(self, enode: ENode) -> int:
        canonical = ENode(enode.operation, tuple(self.find(child) for child in enode.children), enode.value)
        existing = self.hashcons.get(canonical)
        if existing is not None:
            return self.find(existing)
        class_id = len(self.parent)
        self.parent.append(class_id)
        self.classes.append({canonical})
        self.hashcons[canonical] = class_id
        return class_id

    def add_term(self, term: Term) -> int:
        operation, args = term
        if operation == "atom":
            return self.add_enode(ENode(operation, (), str(args[0])))
        children = tuple(self.add_term(arg) for arg in args)
        return self.add_enode(ENode(operation, children))

    def union(self, left: int, right: int) -> int:
        left = self.find(left)
        right = self.find(right)
        if left == right:
            return left
        if len(self.classes[left]) < len(self.classes[right]):
            left, right = right, left
        self.parent[right] = left
        self.classes[left].update(self.classes[right])
        self.classes[right].clear()
        self.merge_count += 1
        return left

    def rebuild(self) -> None:
        changed = True
        while changed:
            changed = False
            self.hashcons.clear()
            for class_id, nodes in enumerate(self.classes):
                root = self.find(class_id)
                if root != class_id:
                    continue
                for node in list(nodes):
                    canonical = ENode(node.operation, tuple(self.find(child) for child in node.children), node.value)
                    other = self.hashcons.get(canonical)
                    if other is not None and self.find(other) != root:
                        self.union(root, other)
                        changed = True
                        break
                    self.hashcons[canonical] = root
                if changed:
                    break

    def extract(self, root: int) -> Term:
        root = self.find(root)
        memo: dict[int, Term] = {}

        def choose(class_id: int) -> Term:
            class_id = self.find(class_id)
            if class_id in memo:
                return memo[class_id]
            nodes = self.classes[class_id]
            if not nodes:
                raise ValueError("empty e-class")
            candidates: list[tuple[int, Term]] = []
            for node in nodes:
                if node.operation == "atom":
                    term = ("atom", (node.value,))
                else:
                    term = (node.operation, tuple(choose(child) for child in node.children))
                candidates.append((_term_size(term), term))
            term = min(candidates, key=lambda item: item[0])[1]
            memo[class_id] = term
            return term

        return choose(root)


def _term_size(term: Term) -> int:
    return 1 + sum(_term_size(arg) for arg in term[1] if isinstance(arg, tuple))


def _term_from_value(value: Any) -> Term:
    if isinstance(value, dict):
        entries = tuple(
            ("entry", (("atom", (canonical_text(str(key)),)), _term_from_value(item)))
            for key, item in sorted(value.items())
        )
        return ("map", entries)
    if isinstance(value, list):
        return ("list", tuple(_term_from_value(item) for item in value))
    return ("atom", (canonical_text(value),))


def _value_from_term(term: Term) -> Any:
    operation, args = term
    if operation == "atom":
        return json.loads(str(args[0]))
    if operation == "list":
        return [_value_from_term(item) for item in args]
    if operation == "map":
        result: dict[str, Any] = {}
        for entry in args:
            if entry[0] != "entry":
                raise ValueError("malformed map entry")
            key_term, value_term = entry[1]
            result[str(_value_from_term(key_term))] = _value_from_term(value_term)
        return result
    if operation == "identity":
        return _value_from_term(args[0])
    if operation == "reverse":
        return list(reversed(_value_from_term(args[0])))
    raise ValueError(f"unknown extracted operation: {operation}")


def _simplify(term: Term) -> Term:
    operation, args = term
    if operation == "atom":
        return term
    children = tuple(_simplify(arg) for arg in args)
    if operation == "identity":
        return children[0]
    if operation == "reverse" and children[0][0] == "reverse":
        return children[0][1][0]
    return operation, children


@dataclass
class RewriteEgraphRepresentation:
    graph: EGraph
    root: int


class RewriteEgraphKernel:
    name = "rewrite_egraph"

    def encode(self, value: Any) -> RewriteEgraphRepresentation:
        graph = EGraph()
        root = graph.add_term(_term_from_value(value))
        graph.rebuild()
        return RewriteEgraphRepresentation(graph, root)

    def decode(self, representation: RewriteEgraphRepresentation) -> Any:
        return _value_from_term(representation.graph.extract(representation.root))

    def size_bytes(self, representation: RewriteEgraphRepresentation) -> int:
        graph = representation.graph
        nodes = []
        for class_id, enodes in enumerate(graph.classes):
            if graph.find(class_id) != class_id:
                continue
            for node in enodes:
                nodes.append({"op": node.operation, "children": node.children, "value": node.value})
        return len(canonical_text({"root": graph.find(representation.root), "nodes": nodes}).encode("utf-8"))

    def sharing(self, representation: RewriteEgraphRepresentation) -> tuple[int, int]:
        graph = representation.graph
        unique = sum(len(nodes) for class_id, nodes in enumerate(graph.classes) if graph.find(class_id) == class_id)
        expanded = deep_node_count(self.decode(representation))
        return unique, expanded

    def query(self, representation: RewriteEgraphRepresentation, path: Iterable[str | int]) -> QueryResult:
        value = self.decode(representation)
        current = value
        cost = 1
        for segment in path:
            current = current[segment]
            cost += 1
        return QueryResult(current, cost)

    def transform(self, representation: RewriteEgraphRepresentation, operation: str) -> TransformResult:
        source = self.decode(representation)
        graph = EGraph()
        source_term = _term_from_value(source)
        if operation == "reverse":
            wrapped = ("reverse", (("reverse", (source_term,)),))
            root = graph.add_term(wrapped)
            before = graph.merge_count
            simplified = _simplify(wrapped)
            simplified_root = graph.add_term(simplified)
            graph.union(root, simplified_root)
            graph.rebuild()
            rewrite_cost = graph.merge_count - before
        else:
            root = graph.add_term(("identity", (source_term,)))
            simplified_root = graph.add_term(source_term)
            before = graph.merge_count
            graph.union(root, simplified_root)
            graph.rebuild()
            rewrite_cost = graph.merge_count - before
        result = apply_operation(source, operation)
        transformed = self.encode(result)
        return TransformResult(transformed, len(graph.hashcons) + rewrite_cost)

    def self_description(self) -> dict[str, Any]:
        return {
            "kernel": self.name,
            "primitives": ["enode", "eclass", "union", "rewrite"],
            "identity": "equivalence class of terms",
            "transformations": ["rewrite until saturation", "extract representative"],
            "costs": ["enodes", "eclasses", "rewrite merges", "extraction"],
            "history": "successive roots and rule applications",
            "self_reference": self.name,
        }
