"""Candidate C: a small e-graph with generic term-rewrite schemas."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable

from ..canonical import apply_operation, canonical_text, deep_node_count
from .base import QueryResult, SelfApplicationResult, TransformResult, run_self_application


Term = tuple[str, tuple[Any, ...]]


@dataclass(frozen=True)
class Variable:
    name: str


Pattern = Term | Variable


@dataclass(frozen=True)
class RewriteRule:
    """A first-order rewrite schema over arbitrary operation names."""

    name: str
    lhs: Pattern
    rhs: Pattern

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "lhs": _pattern_to_json(self.lhs),
            "rhs": _pattern_to_json(self.rhs),
        }


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
        term, _ = self.extract_with_stats(root)
        return term

    def extract_with_stats(self, root: int) -> tuple[Term, dict[str, int]]:
        root = self.find(root)
        memo: dict[int, Term] = {}
        visited_classes: set[int] = set()
        enodes_visited = 0

        def choose(class_id: int) -> Term:
            nonlocal enodes_visited
            class_id = self.find(class_id)
            if class_id in memo:
                return memo[class_id]
            visited_classes.add(class_id)
            nodes = self.classes[class_id]
            if not nodes:
                raise ValueError("empty e-class")
            candidates: list[tuple[int, Term]] = []
            for node in nodes:
                enodes_visited += 1
                if node.operation == "atom":
                    term = ("atom", (node.value,))
                else:
                    term = (node.operation, tuple(choose(child) for child in node.children))
                candidates.append((_term_size(term), term))
            term = min(candidates, key=lambda item: item[0])[1]
            memo[class_id] = term
            return term

        return choose(root), {
            "eclasses_visited": len(visited_classes),
            "enodes_visited": enodes_visited,
        }


def _term_size(term: Term) -> int:
    size = 0
    stack = [term]
    while stack:
        current = stack.pop()
        size += 1
        stack.extend(arg for arg in current[1] if isinstance(arg, tuple))
    return size


def _term_to_json(term: Term | Variable) -> Any:
    if isinstance(term, Variable):
        return {"var": term.name}
    return [
        term[0],
        [
            _term_to_json(arg) if isinstance(arg, (tuple, Variable)) else arg
            for arg in term[1]
        ],
    ]


def _pattern_to_json(pattern: Pattern) -> Any:
    return _term_to_json(pattern)


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


def _match(pattern: Pattern, term: Term, bindings: dict[str, Term]) -> bool:
    if isinstance(pattern, Variable):
        bound = bindings.get(pattern.name)
        if bound is None:
            bindings[pattern.name] = term
            return True
        return bound == term
    if pattern[0] != term[0] or len(pattern[1]) != len(term[1]):
        return False
    for pattern_arg, term_arg in zip(pattern[1], term[1]):
        if not isinstance(term_arg, tuple) or not _match(pattern_arg, term_arg, bindings):
            return False
    return True


def _substitute(pattern: Pattern, bindings: dict[str, Term]) -> Term:
    if isinstance(pattern, Variable):
        return bindings[pattern.name]
    return (pattern[0], tuple(_substitute(arg, bindings) for arg in pattern[1]))


def _rewrite_root(term: Term, rule: RewriteRule) -> Term | None:
    bindings: dict[str, Term] = {}
    if not _match(rule.lhs, term, bindings):
        return None
    return _substitute(rule.rhs, bindings)


def _rewrite_once(term: Term, rules: tuple[RewriteRule, ...]) -> tuple[Term, str] | None:
    for rule in rules:
        rewritten = _rewrite_root(term, rule)
        if rewritten is not None and rewritten != term:
            return rewritten, rule.name
    operation, args = term
    for index, arg in enumerate(args):
        if not isinstance(arg, tuple) or len(arg) != 2 or not isinstance(arg[0], str):
            continue
        rewritten = _rewrite_once(arg, rules)
        if rewritten is not None:
            new_args = list(args)
            new_args[index] = rewritten[0]
            return (operation, tuple(new_args)), rewritten[1]
    return None


def _saturate(term: Term, rules: tuple[RewriteRule, ...], limit: int = 256) -> tuple[Term, list[str]]:
    current = term
    applied: list[str] = []
    for _ in range(limit):
        rewritten = _rewrite_once(current, rules)
        if rewritten is None:
            break
        current, rule_name = rewritten
        applied.append(rule_name)
    return current, applied


def _default_rules() -> tuple[RewriteRule, ...]:
    x = Variable("x")
    return (
        RewriteRule("identity_elimination", ("identity", (x,)), x),
        RewriteRule("involution", ("reverse", (("reverse", (x,)),)), x),
        RewriteRule("idempotent_wrap", ("wrap", (("wrap", (x,)),)), ("wrap", (x,))),
    )


@dataclass
class RewriteEgraphRepresentation:
    graph: EGraph
    root: int
    original_term: Term


class RewriteEgraphKernel:
    name = "rewrite_egraph"

    def __init__(self, rules: Iterable[RewriteRule] | None = None) -> None:
        self.rules = tuple(rules) if rules is not None else _default_rules()

    def encode(self, value: Any) -> RewriteEgraphRepresentation:
        graph = EGraph()
        original_term = _term_from_value(value)
        root = graph.add_term(original_term)
        graph.rebuild()
        return RewriteEgraphRepresentation(graph, root, original_term)

    def decode(self, representation: RewriteEgraphRepresentation) -> Any:
        return _value_from_term(representation.graph.extract(representation.root))

    def size_bytes(self, representation: RewriteEgraphRepresentation) -> int:
        return self.storage_breakdown(representation)["total_bytes"]

    def sharing(self, representation: RewriteEgraphRepresentation) -> tuple[int, int]:
        graph = representation.graph
        unique = sum(len(nodes) for class_id, nodes in enumerate(graph.classes) if graph.find(class_id) == class_id)
        expanded = deep_node_count(self.decode(representation))
        return unique, expanded

    def query(self, representation: RewriteEgraphRepresentation, path: Iterable[str | int]) -> QueryResult:
        term, extraction_stats = representation.graph.extract_with_stats(representation.root)
        current = _value_from_term(term)
        path_tuple = tuple(path)
        for segment in path_tuple:
            current = current[segment]
        nodes_visited = (
            extraction_stats["eclasses_visited"]
            + extraction_stats["enodes_visited"]
            + len(path_tuple)
        )
        return QueryResult(current, len(path_tuple) + 1, nodes_visited)

    def transform(self, representation: RewriteEgraphRepresentation, operation: str) -> TransformResult:
        source = self.decode(representation)
        source_term = _term_from_value(source)
        if operation == "reverse":
            wrapped = ("reverse", (("reverse", (source_term,)),))
        else:
            applied = ("apply", (("atom", (canonical_text(operation),)), source_term))
            wrapped = ("identity", (applied,))
        rewritten, applied_rules = _saturate(wrapped, self.rules)
        graph = EGraph()
        root = graph.add_term(wrapped)
        simplified_root = graph.add_term(rewritten)
        before = graph.merge_count
        graph.union(root, simplified_root)
        graph.rebuild()
        rewrite_cost = len(applied_rules) + (graph.merge_count - before)
        result = apply_operation(source, operation)
        transformed = self.encode(result)
        visited = len(graph.hashcons) + rewrite_cost
        return TransformResult(transformed, visited, visited)

    def storage_breakdown(self, representation: RewriteEgraphRepresentation) -> dict[str, int]:
        graph = representation.graph
        eclass_rows = []
        for class_id, enodes in enumerate(graph.classes):
            if graph.find(class_id) != class_id:
                continue
            eclass_rows.append(
                {
                    "id": class_id,
                    "nodes": [
                        {"op": node.operation, "children": node.children, "value": node.value}
                        for node in sorted(enodes, key=lambda item: (item.operation, item.children, item.value or ""))
                    ],
                }
            )
        original_term_bytes = len(canonical_text(_term_to_json(representation.original_term)).encode("utf-8"))
        eclasses_bytes = len(canonical_text(eclass_rows).encode("utf-8"))
        rules_bytes = len(canonical_text([rule.as_dict() for rule in self.rules]).encode("utf-8"))
        total_bytes = original_term_bytes + eclasses_bytes + rules_bytes
        return {
            "payload_bytes": original_term_bytes,
            "hashes_bytes": 0,
            "index_bytes": 0,
            "store_bytes": eclasses_bytes,
            "store_overhead_bytes": 0,
            "original_term_bytes": original_term_bytes,
            "eclasses_bytes": eclasses_bytes,
            "rules_bytes": rules_bytes,
            "root_reference_bytes": 0,
            "total_bytes": total_bytes,
        }

    def self_description(self) -> dict[str, Any]:
        return {
            "kernel": self.name,
            "primitives": ["enode", "eclass", "union", "rewrite"],
            "identity": "equivalence class of terms",
            "transformations": ["rewrite until saturation", "extract representative"],
            "costs": ["original terms", "e-classes", "rewrite rules", "extraction"],
            "history": "successive roots and rule applications",
            "evaluator": {
                "encode": "add terms with hash-consing and rebuild congruence",
                "decode": "extract least-size representative and decode value",
                "query": "extract representative then traverse path",
                "transform": "add wrapped term, saturate generic rules, union, extract result",
            },
            "rules": [rule.as_dict() for rule in self.rules],
            "self_reference": self.name,
        }

    def self_application(self) -> SelfApplicationResult:
        return run_self_application(self)
