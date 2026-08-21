"""Deterministic workloads for Phase 1 protocol v2 scaling curves."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable


SIZES = (10, 100, 1_000, 10_000)
SHAPES = ("repetition", "shared_graph", "temporal_branching")


def _repetition_case(size: int) -> dict[str, Any]:
    unit = {
        "kind": "leaf",
        "value": "x",
        "weight": 1,
        "payload": {"marker": "shared", "levels": ["a", "b", "c"]},
    }
    return {
        "id": f"repetition_{size}",
        "shape": "repetition",
        "size": size,
        "value": {
            "kind": "repeated",
            "unit": deepcopy(unit),
            "items": [deepcopy(unit) for _ in range(size)],
        },
        "query_path": ["items", size - 1, "payload", "levels", 2],
        "transform": {"operation": "reverse", "source_path": ["items"]},
    }


def _shared_graph_case(size: int) -> dict[str, Any]:
    shared_payload = {
        "kind": "edge_payload",
        "labels": ["a", "b", "c"],
        "properties": {"stable": True, "weight": 1},
    }
    nodes = []
    for index in range(size):
        nodes.append(
            {
                "id": f"n{index}",
                "branch": index % 4,
                "payload": deepcopy(shared_payload),
                "edges": [
                    {"to": f"n{(index + 1) % size}", "kind": "next"},
                    {"to": f"n{(index + 2) % size}", "kind": "skip"},
                ],
            }
        )
    return {
        "id": f"shared_graph_{size}",
        "shape": "shared_graph",
        "size": size,
        "value": {
            "kind": "shared_graph",
            "root": "n0",
            "template": deepcopy(shared_payload),
            "nodes": nodes,
        },
        "query_path": ["nodes", size - 1, "payload", "properties", "stable"],
        "transform": {"operation": "reverse", "source_path": ["nodes"]},
    }


def _temporal_branching_case(size: int) -> dict[str, Any]:
    state_templates = (
        {"mode": "cold", "flags": ["safe", "idle"]},
        {"mode": "warm", "flags": ["safe", "active"]},
        {"mode": "hot", "flags": ["busy", "active"]},
        {"mode": "cooling", "flags": ["safe", "active"]},
    )
    snapshots = []
    for index in range(size):
        if index == 0:
            parent = None
        elif index % 3 == 0:
            parent = f"s{index - 2}"
        else:
            parent = f"s{index - 1}"
        snapshots.append(
            {
                "id": f"s{index}",
                "time": index,
                "parent": parent,
                "branch": index % 3,
                "state": deepcopy(state_templates[index % len(state_templates)]),
                "action": {"kind": "advance", "delta": index % 5},
            }
        )
    return {
        "id": f"temporal_branching_{size}",
        "shape": "temporal_branching",
        "size": size,
        "value": {
            "kind": "temporal_branching",
            "root": "s0",
            "snapshots": snapshots,
        },
        "query_path": ["snapshots", size - 1, "state", "mode"],
        "transform": {"operation": "reverse", "source_path": ["snapshots"]},
    }


def scaled_cases(sizes: Iterable[int] = SIZES) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for size in sizes:
        if size <= 0:
            raise ValueError("scale sizes must be positive")
        cases.extend(
            (
                _repetition_case(size),
                _shared_graph_case(size),
                _temporal_branching_case(size),
            )
        )
    return cases


def scale_manifest(sizes: Iterable[int] = SIZES) -> list[dict[str, Any]]:
    """Return the reproducibility manifest without materializing all values."""

    return [
        {"shape": shape, "size": size, "case_id": f"{shape}_{size}"}
        for size in sizes
        for shape in SHAPES
    ]
