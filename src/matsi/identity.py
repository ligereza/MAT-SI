"""Identity/annotation counterexamples for Phase 1 protocol v2."""

from __future__ import annotations

from typing import Any, Iterable

from .canonical import canonical_text
from .kernels.base import Kernel


def identity_cases() -> list[dict[str, Any]]:
    base = {"kind": "document", "body": "same content", "revision": 1}
    return [
        {
            "id": "same_content_different_name",
            "objects": [
                {"content": base, "annotations": {"name": "alpha"}},
                {"content": base, "annotations": {"name": "beta"}},
            ],
            "expected": {"content_equal": True, "annotation_equal": False, "full_equal": False},
        },
        {
            "id": "same_name_different_content",
            "objects": [
                {"content": base, "annotations": {"name": "shared-name"}},
                {"content": {"kind": "document", "body": "changed content", "revision": 2}, "annotations": {"name": "shared-name"}},
            ],
            "expected": {"content_equal": False, "annotation_equal": True, "full_equal": False},
        },
        {
            "id": "two_names_one_object",
            "object": {"object_id": "object-1", "content": base},
            "annotations": {"names": ["primary", "alias"]},
            "expected": {"stable_identity": "object-1", "content_occurrences": 1, "alias_count": 2},
        },
        {
            "id": "evolving_object",
            "object_id": "object-2",
            "versions": [
                {"revision": 0, "content": {"state": "cold", "counter": 0}},
                {"revision": 1, "content": {"state": "warm", "counter": 1}},
                {"revision": 2, "content": {"state": "hot", "counter": 2}},
            ],
            "annotations": {"aliases": ["sensor", "main-sensor"]},
            "expected": {"stable_identity": "object-2", "content_changes": 3, "alias_count": 2},
        },
    ]


def _projection_token(kernel: Kernel, value: Any) -> str:
    """Harness-only token; kernels do not receive an identity operation."""

    return canonical_text(kernel.decode(kernel.encode(value)))


def analyze_identity(kernel: Kernel, cases: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for case in cases:
        if case["id"] in {"same_content_different_name", "same_name_different_content"}:
            left, right = case["objects"]
            observations.append(
                {
                    "candidate": kernel.name,
                    "case_id": case["id"],
                    "full_equal_after_round_trip": kernel.decode(kernel.encode(left)) == kernel.decode(kernel.encode(right)),
                    "content_projection_equal": _projection_token(kernel, left["content"]) == _projection_token(kernel, right["content"]),
                    "annotation_projection_equal": _projection_token(kernel, left["annotations"]) == _projection_token(kernel, right["annotations"]),
                    "finding": "content and annotations can be separated structurally, but the kernel does not assign their roles",
                }
            )
        elif case["id"] == "two_names_one_object":
            content = case["object"]["content"]
            observations.append(
                {
                    "candidate": kernel.name,
                    "case_id": case["id"],
                    "content_projection_token": _projection_token(kernel, content),
                    "alias_count": len(case["annotations"]["names"]),
                    "content_occurrences_in_object_table": 1,
                    "finding": "aliases remain annotations if the content table is encoded once; no kernel-level alias semantics are inferred",
                }
            )
        else:
            versions = case["versions"]
            tokens = [_projection_token(kernel, version["content"]) for version in versions]
            observations.append(
                {
                    "candidate": kernel.name,
                    "case_id": case["id"],
                    "stable_external_identity": case["object_id"],
                    "version_content_tokens": tokens,
                    "content_tokens_distinct": len(set(tokens)) == len(tokens),
                    "finding": "content identity changes per version while stable identity survives only as separate data",
                }
            )
    return observations


def run_identity_analysis(kernels: Iterable[Kernel]) -> dict[str, Any]:
    cases = identity_cases()
    return {
        "protocol": "phase1-v2",
        "cases": cases,
        "observations": [observation for kernel in kernels for observation in analyze_identity(kernel, cases)],
        "conclusion": "No new identity primitive was introduced; structural content and annotations are separable by representation layout, while alias and evolution semantics remain external annotations.",
    }
