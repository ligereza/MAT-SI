"""Portable identity and availability boundary for frozen experiment sources.

Two independent problems are handled here, and only these two.

Identity.  A frozen repository-owned text file was pinned by its raw bytes, so a
checkout with a different newline convention changed its digest and the phase
refused to run.  Phase 3C and Phase 3D already collapsed CRLF to LF before
hashing; that existing rule is reused instead of a new one.  Binary sources stay
byte sensitive because a newline byte can carry payload there.

Availability.  Some frozen sources are private files outside the repository.  A
second machine cannot read them, must not fabricate them, and must not silently
present a stored historical result as an independent reproduction.  Resolution
therefore reports one of three explicit states.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .canonical import canonical_newline_bytes


SOURCE_AVAILABLE = "SOURCE_AVAILABLE"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
SOURCE_HASH_MISMATCH = "SOURCE_HASH_MISMATCH"

TEXT = "text"
BINARY = "binary"

SOURCE_MAP_ENV = "MATSI_SOURCE_MAP"
DEFAULT_SOURCE_MAP = Path("corpus") / "local-source-map.json"


class FrozenSourceMismatch(ValueError):
    """A resolved frozen source does not match its frozen identity."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_identity(data: bytes, content_kind: str = TEXT) -> dict[str, Any]:
    """Return the raw and canonical identity of one frozen payload."""
    raw = _sha256(data)
    if content_kind == BINARY:
        return {
            "raw_sha256": raw,
            "canonical_sha256": raw,
            "canonicalization": "none",
            "raw_bytes": len(data),
            "canonical_bytes": len(data),
        }
    canonical = canonical_newline_bytes(data)
    return {
        "raw_sha256": raw,
        "canonical_sha256": _sha256(canonical),
        "canonicalization": "newline_crlf_to_lf",
        "raw_bytes": len(data),
        "canonical_bytes": len(canonical),
    }


def load_source_map(root: Path) -> dict[str, str]:
    """Load the optional local mapping from frozen paths to local paths.

    The mapping is never committed: it names private locations on one machine.
    """
    configured = os.environ.get(SOURCE_MAP_ENV)
    candidates = [Path(configured)] if configured else []
    candidates.append(root / DEFAULT_SOURCE_MAP)
    for candidate in candidates:
        if candidate.is_file():
            mapping = json.loads(candidate.read_text(encoding="utf-8"))
            return {str(key): str(value) for key, value in mapping.get("sources", mapping).items()}
    return {}


def _candidate_paths(
    spec: dict[str, Any],
    source_id: str,
    root: Path,
    source_map: dict[str, str],
) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    if spec.get("repo_path"):
        candidates.append(("repo_path", root / spec["repo_path"]))
    for key in (source_id, spec.get("path"), spec.get("id"), spec.get("system_id")):
        if key and str(key) in source_map:
            candidates.append(("local_source_map", Path(source_map[str(key)]).expanduser()))
            break
    frozen = spec.get("path")
    if frozen:
        path = Path(frozen)
        candidates.append(("manifest_path", path if path.is_absolute() else root / path))
    return candidates


def resolve_source(
    spec: dict[str, Any],
    *,
    source_id: str,
    root: Path,
    source_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve one frozen source without raising on absence.

    A hash mismatch is reported as ``SOURCE_HASH_MISMATCH`` here so callers can
    inspect it; :func:`load_source` turns it into a hard failure.
    """
    mapping = load_source_map(root) if source_map is None else source_map
    content_kind = spec.get("content_kind", TEXT)
    expected_raw = spec.get("sha256")
    expected_canonical = spec.get("canonical_sha256")
    availability = spec.get("availability", "private_external" if not spec.get("repo_path") else "repo_owned")
    resolution: dict[str, Any] = {
        "source_id": source_id,
        "status": SOURCE_UNAVAILABLE,
        "resolved_from": None,
        "availability": availability,
        "content_kind": content_kind,
        "expected_raw_sha256": expected_raw,
        "expected_canonical_sha256": expected_canonical,
        "observed_raw_sha256": None,
        "observed_canonical_sha256": None,
        "identity_matched": None,
        "canonicalization": "none" if content_kind == BINARY else "newline_crlf_to_lf",
        "searched": [],
        "reason": None,
        "provenance": {
            "frozen_path": spec.get("path"),
            "repo_path": spec.get("repo_path"),
            "frozen_bytes": spec.get("bytes"),
            "source_map_env": SOURCE_MAP_ENV,
            "payload_committed": bool(spec.get("repo_path")),
        },
    }

    for origin, candidate in _candidate_paths(spec, source_id, root, mapping):
        resolution["searched"].append({"origin": origin, "exists": candidate.is_file()})
        if not candidate.is_file():
            continue
        identity = content_identity(candidate.read_bytes(), content_kind)
        resolution["resolved_from"] = origin
        resolution["observed_raw_sha256"] = identity["raw_sha256"]
        resolution["observed_canonical_sha256"] = identity["canonical_sha256"]
        resolution["observed_bytes"] = identity["raw_bytes"]
        if expected_raw and identity["raw_sha256"] == expected_raw:
            resolution["status"] = SOURCE_AVAILABLE
            resolution["identity_matched"] = "raw"
        elif expected_canonical and identity["canonical_sha256"] == expected_canonical:
            resolution["status"] = SOURCE_AVAILABLE
            resolution["identity_matched"] = "canonical"
        elif expected_raw and content_identity(
            canonical_newline_bytes(candidate.read_bytes()), content_kind
        )["raw_sha256"] == expected_raw:
            # The frozen hash was taken over canonical newlines already.
            resolution["status"] = SOURCE_AVAILABLE
            resolution["identity_matched"] = "canonical"
        else:
            resolution["status"] = SOURCE_HASH_MISMATCH
            resolution["reason"] = "resolved payload does not match the frozen identity"
        return resolution

    resolution["reason"] = "no candidate path for this frozen source exists on this machine"
    return resolution


def load_source(
    spec: dict[str, Any],
    *,
    source_id: str,
    root: Path,
    source_map: dict[str, str] | None = None,
) -> tuple[bytes | None, dict[str, Any]]:
    """Return the payload when available; a mismatch stays a hard failure."""
    resolution = resolve_source(spec, source_id=source_id, root=root, source_map=source_map)
    if resolution["status"] == SOURCE_HASH_MISMATCH:
        raise FrozenSourceMismatch(
            f"frozen source identity mismatch for {source_id}: "
            f"observed raw {resolution['observed_raw_sha256']}, "
            f"canonical {resolution['observed_canonical_sha256']}"
        )
    if resolution["status"] == SOURCE_UNAVAILABLE:
        return None, resolution
    origin = resolution["resolved_from"]
    for candidate_origin, candidate in _candidate_paths(
        spec, source_id, root, load_source_map(root) if source_map is None else source_map
    ):
        if candidate_origin == origin:
            return candidate.read_bytes(), resolution
    return None, resolution


def reproduction_status(resolutions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Summarise what a machine with these resolutions may and may not claim."""
    unavailable = sorted(
        source_id
        for source_id, item in resolutions.items()
        if item["status"] != SOURCE_AVAILABLE
    )
    available = sorted(set(resolutions) - set(unavailable))
    if not unavailable:
        status = "INDEPENDENTLY_REPRODUCED"
    elif available:
        status = "PARTIALLY_REPRODUCED"
    else:
        status = "NOT_INDEPENDENTLY_REPRODUCED"
    return {
        "status": status,
        "independently_reproduced": not unavailable,
        "available_sources": available,
        "unavailable_sources": unavailable,
        "not_independently_reproducible": [
            f"every derivation from {source_id}" for source_id in unavailable
        ],
        "stored_historical_result_is_not_a_reproduction": True,
        "fabrication": "no absent source is substituted, inferred, or synthesised",
    }


def historical_result(path: Path) -> dict[str, Any]:
    """Wrap a stored result so it cannot be mistaken for a fresh reproduction."""
    if not path.is_file():
        return {
            "available": False,
            "path": path.name,
            "independently_reproduced": False,
            "provenance": "stored historical result absent",
        }
    return {
        "available": True,
        "path": path.name,
        "independently_reproduced": False,
        "provenance": "stored historical result committed by the original machine",
        "content_identity": content_identity(path.read_bytes(), TEXT),
        "result": json.loads(path.read_text(encoding="utf-8")),
    }
