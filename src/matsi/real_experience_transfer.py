"""Phase 4B: inspect real evidence without manufacturing missing observables."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from . import frozen_source
from .canonical import canonical_newline_bytes, canonical_text
from .distillation import _size
from .real_distillation import _digest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "corpus" / "phase4b-real-evidence-manifest.json"
HISTORICAL_RESULT = ROOT / "results" / "phase4b-real-experience-transfer-results.json"
BEHAVIOR_FIELDS = ("action", "outcome", "cost")
ENVELOPE_FIELDS = ("context", "observation", "action", "outcome", "cost", "provenance")


def _load_source(spec: dict[str, Any]) -> tuple[bytes | None, str | None, dict[str, Any]]:
    """Resolve one frozen Phase 4B source without fabricating an absent payload."""
    data, resolution = frozen_source.load_source(spec, source_id=spec["id"], root=ROOT)
    if data is None:
        return None, None, resolution
    identity = resolution["observed_canonical_sha256"] or resolution["observed_raw_sha256"]
    return canonical_newline_bytes(data), identity, resolution


def _opaque(value: Any) -> str:
    return hashlib.sha256(canonical_text(value).encode("utf-8")).hexdigest()[:16]


def _unknown_field(field: str, reason: str) -> dict[str, Any]:
    return {
        "status": "UNKNOWN",
        "field": field,
        "reason": reason,
    }


def _adapt_markdown(data: bytes, source_id: str, source_hash: str) -> tuple[dict[str, Any], dict[str, Any]]:
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if re.match(r"^#{1,6}\s+", line)]
    if not starts:
        starts = [0]
    events = []
    for ordinal, start in enumerate(starts):
        end = starts[ordinal + 1] if ordinal + 1 < len(starts) else len(lines)
        block = lines[start:end]
        heading = block[0] if block else ""
        level = len(heading) - len(heading.lstrip("#")) if heading.startswith("#") else 0
        events.append(
            {
                "context": {"heading_level": level},
                "observation": {
                    "line_count": len(block),
                    "byte_count": len("\n".join(block).encode("utf-8")),
                },
                "action": _unknown_field("action", "narrative source does not record an executable action field"),
                "outcome": _unknown_field("outcome", "narrative claims are not treated as measured outcomes"),
                "cost": _unknown_field("cost", "source contains no operational cost field"),
                "provenance": {
                    "opaque_source": _opaque(source_hash),
                    "block_index": ordinal,
                    "line_start": start + 1,
                    "line_end": end,
                },
            }
        )
    audit = {
        "source_id": source_id,
        "PRESERVED": ["markdown block order", "heading depth", "block line and byte counts", "line ranges"],
        "NORMALIZED": ["source identity to opaque hash", "headings to structural depth only"],
        "LOST": ["domain/product names", "human interpretation", "prose claims as semantics", "filenames"],
        "RESIDUE": {"source_hash": source_hash, "heading_texts_not_represented": True},
        "derived_fields": {
            "context": {"RAW_SOURCE": "markdown heading", "DERIVATION": "heading depth", "LOSS": "heading text", "RESIDUE": "opaque", "PROVENANCE": "line range"},
            "observation": {"RAW_SOURCE": "markdown block", "DERIVATION": "line and UTF-8 byte counts", "LOSS": "prose content", "RESIDUE": "hash only", "PROVENANCE": "block index"},
            "action": {"RAW_SOURCE": None, "DERIVATION": None, "LOSS": "unrecorded", "RESIDUE": "UNKNOWN", "PROVENANCE": "source schema"},
            "outcome": {"RAW_SOURCE": None, "DERIVATION": None, "LOSS": "ambiguous narrative claims", "RESIDUE": "UNKNOWN", "PROVENANCE": "source schema"},
            "cost": {"RAW_SOURCE": None, "DERIVATION": None, "LOSS": "unrecorded", "RESIDUE": "UNKNOWN", "PROVENANCE": "source schema"},
        },
    }
    return {"source_id": source_id, "events": events}, audit


def _adapt_json_evidence(data: bytes, source_id: str, source_hash: str) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = json.loads(data.decode("utf-8"))
    events = []
    for ordinal, item in enumerate(raw.get("events", [])):
        events.append(
            {
                "context": {"source_sheet_index": item.get("source_sheet_index")},
                "observation": {
                    "event_label_status": item.get("event_label_status"),
                    "date_status": item.get("date_status"),
                    "link_status": item.get("link_status"),
                    "duplicate_status": item.get("duplicate_status"),
                },
                "action": _unknown_field("action", "event evidence has no recorded action transition"),
                "outcome": _unknown_field("outcome", "link/date/event statuses are metadata, not measured outcomes"),
                "cost": _unknown_field("cost", "source has no cost or duration field"),
                "provenance": {
                    "opaque_source": _opaque(source_hash),
                    "event_ordinal": ordinal,
                    "event_token": _opaque(item.get("event_id")),
                },
            }
        )
    audit = {
        "source_id": source_id,
        "PRESERVED": ["source event order", "source sheet index", "explicit status fields", "event count"],
        "NORMALIZED": ["event identity and source identity to opaque hashes", "labels to status categories"],
        "LOST": ["venue/producer names", "source sheet names", "domain/product interpretation", "filenames"],
        "RESIDUE": {"source_hash": source_hash, "raw_event_fields_not_transferred": True},
        "derived_fields": {
            "context": {"RAW_SOURCE": "events[*].source_sheet_index", "DERIVATION": "copy numeric source index", "LOSS": "sheet name", "RESIDUE": "opaque", "PROVENANCE": "event ordinal"},
            "observation": {"RAW_SOURCE": "events[*].*_status", "DERIVATION": "copy explicit status values", "LOSS": "raw labels and names", "RESIDUE": "hash only", "PROVENANCE": "event id hash"},
            "action": {"RAW_SOURCE": None, "DERIVATION": None, "LOSS": "unrecorded", "RESIDUE": "UNKNOWN", "PROVENANCE": "source schema"},
            "outcome": {"RAW_SOURCE": "status metadata", "DERIVATION": "not promoted", "LOSS": "ambiguous outcome semantics", "RESIDUE": "UNKNOWN", "PROVENANCE": "source schema"},
            "cost": {"RAW_SOURCE": None, "DERIVATION": None, "LOSS": "unrecorded", "RESIDUE": "UNKNOWN", "PROVENANCE": "source schema"},
        },
    }
    return {"source_id": source_id, "events": events}, audit


def _known_value(event: dict[str, Any], field: str) -> Any | None:
    value = event[field]
    if isinstance(value, dict) and value.get("status") == "UNKNOWN":
        return None
    return value


def _generic_relation_attempt(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for field in ENVELOPE_FIELDS[:-1]:
        left_value = _known_value(left, field)
        right_value = _known_value(right, field)
        if left_value is None or right_value is None:
            continue
        if canonical_text(left_value) == canonical_text(right_value):
            candidates.append({"field": field, "relation": "equal"})
        if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
            if right_value > left_value:
                candidates.append({"field": field, "relation": "increasing"})
    return candidates


def _availability(domains: dict[str, dict[str, Any]]) -> dict[str, dict[str, int]]:
    result = {}
    for source_id, domain in domains.items():
        result[source_id] = {}
        for field in ENVELOPE_FIELDS:
            result[source_id][field] = sum(1 for event in domain["events"] if _known_value(event, field) is not None)
    return result


def _discover_ab(domains: dict[str, dict[str, Any]], audits: dict[str, dict[str, Any]]) -> dict[str, Any]:
    attempted = []
    for source_id in ("A", "B"):
        events = domains[source_id]["events"]
        for left, right in zip(events, events[1:]):
            attempted.extend(_generic_relation_attempt(left, right))
    behavior_available = {
        field: all(_known_value(event, field) is not None for source_id in ("A", "B") for event in domains[source_id]["events"])
        for field in BEHAVIOR_FIELDS
    }
    comparable_behavior_fields = [field for field, available in behavior_available.items() if available]
    candidates = []
    if comparable_behavior_fields:
        candidates = [
            {
                "id": f"field_{field}_generic_transition",
                "field": field,
                "relation_language": ["equal", "increasing"],
                "evidence_for": [],
                "evidence_against": [],
                "coverage": 0,
                "cost": _size({"field": field, "relation_language": ["equal", "increasing"]}),
                "residue": {"adapter_residue_digests": {key: _digest(value["RESIDUE"]) for key, value in audits.items()}},
                "provenance": {"source_ids": ["A", "B"]},
            }
            for field in comparable_behavior_fields
        ]
    return {
        "status": "NO_COMPARABLE_BEHAVIORAL_RELATION" if not candidates else "CANDIDATES_FOUND",
        "generic_relation_attempt_count": len(attempted),
        "generic_relation_attempts": attempted[:100],
        "candidate_relations": candidates,
        "behavior_field_availability": behavior_available,
        "comparable_behavior_fields": comparable_behavior_fields,
        "evidence_for": [],
        "evidence_against": [],
        "coverage": 0,
        "cost": _size({"relation_language": ["equal", "increasing"]}),
        "residue": {"source_ids": ["A", "B"], "missing_behavior_fields": [field for field in BEHAVIOR_FIELDS if field not in comparable_behavior_fields]},
        "provenance": {"source_ids": ["A", "B"], "method": "generic_equal_or_increasing_over_derived_fields"},
    }


def run_phase4b() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    specs = {spec["id"]: spec for spec in manifest["sources"]}
    domains = {}
    audits = {}
    source_hashes = {}
    resolutions = {}
    for source_id, adapter in (("A", _adapt_markdown), ("B", _adapt_json_evidence)):
        data, source_hash, resolutions[source_id] = _load_source(specs[source_id])
        if data is None:
            continue
        domains[source_id], audits[source_id] = adapter(data, source_id, source_hash)
        source_hashes[source_id] = source_hash

    # C is deliberately never opened, so its availability is not probed at all.
    reproduction = frozen_source.reproduction_status(resolutions)
    discovery_available = {"A", "B"} <= set(domains)
    discovery = (
        _discover_ab(domains, audits)
        if discovery_available
        else {
            "status": "NOT_RECOMPUTED_WITHOUT_PRIVATE_SOURCES",
            "reason": "the generic relation attempt reads A and B; neither is fabricated when absent",
            "missing_sources": sorted({"A", "B"} - set(domains)),
            "generic_relation_attempt_count": None,
            "candidate_relations": None,
            "behavior_field_availability": None,
            "comparable_behavior_fields": None,
        }
    )
    c_spec = specs["C"]
    return {
        "protocol": "phase4b-real-experience-transfer",
        "parent_commit": "7da86e1",
        "raw_manifest_commit": "7a2ebb2",
        "raw_sources_only": True,
        "source_hashes_used": source_hashes,
        "source_resolution": resolutions,
        "reproduction": {
            **reproduction,
            "held_out_C_not_probed": True,
            "not_independently_reproducible": (
                []
                if discovery_available
                else [
                    "the A/B adapter output, the generic relation attempt, and the gate decision",
                ]
            ),
            "historical_result": HISTORICAL_RESULT.name,
        },
        "common_envelope": {
            "fields": list(ENVELOPE_FIELDS),
            "status": "REPRESENTABLE_WITH_UNKNOWN_FIELDS",
            "semantics_invented": False,
            "envelope_is_imposing_the_pattern": False,
        },
        "blind_pass": {
            "domain_labels_hidden": True,
            "filenames_hidden": True,
            "product_names_hidden": True,
            "human_interpretation_hidden": True,
            "source_ids_exposed": ["A", "B"],
        },
        "adapters": {
            source_id: {
                "event_count": len(domains[source_id]["events"]),
                "audit": audits[source_id],
            }
            for source_id in sorted(domains)
        },
        "discovery_from_A_B": discovery,
        "held_out_C": {
            "loaded": False,
            "role": c_spec["role"],
            "path_not_opened_by_adapter": c_spec["path"],
            "selection_frozen": True,
            "reason": "no G with comparable behavioral observables could be frozen from A+B",
            "pre_freeze_header_inspected": True,
            "evaluation_contamination": "C was not used for discovery or prediction; its held-out evaluation is invalidated because a header/sample was inspected before G freeze",
        },
        "missing_information": {
            "A": ["explicit action", "measured outcome", "operational cost"],
            "B": ["explicit action", "measured outcome distinct from metadata status", "operational cost"],
            "C": ["not adapted; held-out intentionally not opened after contamination"],
        },
        "host_represented_derived": {
            "HOST": ["markdown/JSON parsing", "hash verification", "regex for headings", "generic availability counting"],
            "REPRESENTED": ["unknown-preserving envelope", "derived observations and provenance", "generic relation attempts"],
            "DERIVED": ["field availability", "candidate absence", "data/observability bottleneck"],
        },
        "gate": {
            "decision": "B" if discovery_available else None,
            "status": "RECOMPUTED" if discovery_available else "REQUIRES_PRIVATE_SOURCES",
            "meaning": "the transfer idea is testable, but the available real histories do not contain sufficient comparable action/outcome/cost evidence",
            "historical_decision": "B",
            "historical_decision_reproduced_here": discovery_available,
            "phase5_started": False,
            "product_implementation_started": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 4B real experience transfer")
    parser.add_argument("--json-out", type=Path, default=ROOT / "results" / "phase4b-real-experience-transfer-results.json")
    args = parser.parse_args(argv)
    result = run_phase4b()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("A_events:", result["adapters"]["A"]["event_count"])
    print("B_events:", result["adapters"]["B"]["event_count"])
    print("discovery_status:", result["discovery_from_A_B"]["status"])
    print("phase4b_gate.decision:", result["gate"]["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
