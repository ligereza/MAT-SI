"""Continuity experiments using relations and paths, without stable ID primitives."""

from __future__ import annotations

from typing import Any, Iterable


def _node(position: str, content: Any) -> dict[str, Any]:
    return {"position": position, "content": content}


def _relation(source: str, target: str, kind: str, operation: str) -> dict[str, Any]:
    return {
        "from": source,
        "to": target,
        "kind": kind,
        "transformation": {"operation": operation},
        "provenance": {"source": source, "operation": operation},
    }


def continuity_cases() -> list[dict[str, Any]]:
    return [
        {
            "id": "rename_only",
            "value": {
                "nodes": [_node("x0", {"name": "old", "value": 7}), _node("x1", {"name": "new", "value": 7})],
                "relations": [_relation("x0", "x1", "rename", "rename")],
            },
            "compare": ["x0", "x1"],
            "expected": {"content_equal": False, "historical_path": True, "continuity_claim": True},
        },
        {
            "id": "small_mutation",
            "value": {
                "nodes": [_node("x0", {"value": 7, "flag": False}), _node("x1", {"value": 8, "flag": False})],
                "relations": [_relation("x0", "x1", "mutation", "increment")],
            },
            "compare": ["x0", "x1"],
            "expected": {"content_equal": False, "historical_path": True, "continuity_claim": True},
        },
        {
            "id": "complete_replacement",
            "value": {
                "nodes": [_node("x0", {"kind": "old", "value": 7}), _node("x1", {"kind": "new", "value": 99})],
                "relations": [_relation("x0", "x1", "replacement", "replace")],
            },
            "compare": ["x0", "x1"],
            "expected": {"content_equal": False, "historical_path": True, "continuity_claim": False},
        },
        {
            "id": "fork",
            "value": {
                "nodes": [_node("x0", {"value": 7}), _node("x1", {"value": 8}), _node("x2", {"value": 9})],
                "relations": [
                    _relation("x0", "x1", "fork", "increment"),
                    _relation("x0", "x2", "fork", "increment_twice"),
                ],
            },
            "compare": ["x0", "x1"],
            "expected": {"content_equal": False, "historical_path": True, "continuity_claim": "branch"},
        },
        {
            "id": "merge",
            "value": {
                "nodes": [_node("x0", {"value": 7}), _node("x1", {"value": 9}), _node("x2", {"value": 8})],
                "relations": [
                    _relation("x0", "x2", "merge", "increment"),
                    _relation("x1", "x2", "merge", "decrement"),
                ],
            },
            "compare": ["x0", "x2"],
            "expected": {"content_equal": False, "historical_path": True, "continuity_claim": "merged"},
        },
        {
            "id": "independent_convergence",
            "value": {
                "nodes": [
                    _node("a0", {"value": 0}),
                    _node("b0", {"value": 10}),
                    _node("a1", {"value": 5}),
                    _node("b1", {"value": 5}),
                ],
                "relations": [
                    _relation("a0", "a1", "mutation", "add_five"),
                    _relation("b0", "b1", "mutation", "subtract_five"),
                ],
            },
            "compare": ["a1", "b1"],
            "expected": {"content_equal": True, "historical_path": False, "continuity_claim": False},
        },
        {
            "id": "divergence",
            "value": {
                "nodes": [_node("x0", {"value": 1}), _node("x1", {"value": 2}), _node("x2", {"value": -1})],
                "relations": [
                    _relation("x0", "x1", "divergence", "add_one"),
                    _relation("x0", "x2", "divergence", "subtract_two"),
                ],
            },
            "compare": ["x0", "x2"],
            "expected": {"content_equal": False, "historical_path": True, "continuity_claim": "descendant"},
        },
        {
            "id": "alias_relation",
            "value": {
                "nodes": [_node("x0", {"value": 7}), _node("x1", {"value": 7})],
                "relations": [
                    {
                        "from": "x0",
                        "to": "x1",
                        "kind": "alias",
                        "provenance": {"source": "annotation-observation"},
                    }
                ],
            },
            "compare": ["x0", "x1"],
            "expected": {"content_equal": True, "historical_path": False, "continuity_claim": False},
        },
        {
            "id": "equivalence_relation",
            "value": {
                "nodes": [_node("x0", {"value": 7}), _node("x1", {"value": 7})],
                "relations": [
                    {
                        "from": "x0",
                        "to": "x1",
                        "kind": "equivalence",
                        "provenance": {"source": "rewrite-observation", "rule": "same_value"},
                    }
                ],
            },
            "compare": ["x0", "x1"],
            "expected": {"content_equal": True, "historical_path": False, "continuity_claim": False},
        },
    ]


def _reachable(relations: list[dict[str, Any]], source: str, target: str) -> bool:
    adjacency: dict[str, list[str]] = {}
    for relation in relations:
        if relation["kind"] in {"rename", "mutation", "replacement", "fork", "merge", "divergence"}:
            adjacency.setdefault(relation["from"], []).append(relation["to"])
    pending = [source]
    visited = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(adjacency.get(current, []))
    return False


def _facts(value: dict[str, Any], compare: list[str]) -> dict[str, Any]:
    nodes = {node["position"]: node for node in value["nodes"]}
    source, target = compare
    relations = value["relations"]
    relation_kinds = [relation["kind"] for relation in relations]
    provenance_complete = all("provenance" in relation for relation in relations)
    outgoing = sum(1 for relation in relations if relation["from"] == source)
    return {
        "content_equal": nodes[source]["content"] == nodes[target]["content"],
        "historical_path_available": _reachable(relations, source, target),
        "aliasing_relation_present": "alias" in relation_kinds,
        "equivalence_relation_present": "equivalence" in relation_kinds,
        "provenance_present": provenance_complete,
        "outgoing_relation_count": outgoing,
        "stable_id_field_present": any(
            key in node for node in value["nodes"] for key in ("id", "object_id", "stable_id")
        ),
    }


def run_continuity_analysis(kernels: Iterable[Any]) -> dict[str, Any]:
    cases = continuity_cases()
    rows = []
    for kernel in kernels:
        for case in cases:
            representation = kernel.encode(case["value"])
            decoded = kernel.decode(representation)
            facts = _facts(decoded, case["compare"])
            rows.append(
                {
                    "candidate": kernel.name,
                    "case_id": case["id"],
                    "round_trip": decoded == case["value"],
                    "facts": facts,
                    "expected_harness_classification": case["expected"],
                    "representation_bytes": kernel.size_bytes(representation),
                    "continuity_is_discovered": False,
                    "finding": "relations and paths are representable; continuity semantics are not inferred by the candidate",
                }
            )
    return {
        "experiment": "continuity_without_stable_id",
        "cases": [{"id": case["id"], "value": case["value"], "compare": case["compare"], "expected": case["expected"]} for case in cases],
        "rows": rows,
        "distinctions": ["content_equality", "historical_continuity", "aliasing", "equivalence", "provenance"],
        "conclusion": "A relation/path can carry historical evidence without a stable ID; the current candidates do not discover continuity semantics from that path.",
    }
