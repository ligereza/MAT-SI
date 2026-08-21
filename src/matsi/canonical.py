"""Canonical host projections used only by the experiment harness."""

from __future__ import annotations

import json
from typing import Any, Iterable


def canonical_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_bytes(value: Any) -> bytes:
    return canonical_text(value).encode("utf-8")


def canonical_newline_bytes(data: bytes) -> bytes:
    """Collapse CRLF and lone CR to LF for textual evidence.

    Phase 3C and Phase 3D already applied this rule before hashing a frozen
    repository-owned source.  It is named here so every phase can share it
    instead of freezing an operating-system specific newline convention.
    """
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def deep_node_count(value: Any) -> int:
    if isinstance(value, dict):
        return 1 + sum(deep_node_count(key) + deep_node_count(item) for key, item in value.items())
    if isinstance(value, list):
        return 1 + sum(deep_node_count(item) for item in value)
    return 1


def get_path(value: Any, path: Iterable[str | int]) -> Any:
    current = value
    for segment in path:
        current = current[segment]
    return current


def apply_operation(value: Any, operation: str) -> Any:
    if operation == "identity":
        return value
    if operation == "reverse":
        if not isinstance(value, list):
            raise TypeError("reverse requires a list")
        return list(reversed(value))
    if operation == "lowercase":
        if not isinstance(value, str):
            raise TypeError("lowercase requires a string")
        return value.lower()
    raise ValueError(f"unknown operation: {operation}")
