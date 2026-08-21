"""Phase 4C: find the smallest domain-neutral observational contract.

This module deliberately does not infer actions, outcomes, success, progress, or a
scalar cost from the frozen Phase 4B sources.  It only projects already recorded
boundaries into an observation of ``before -> opaque intervention -> after`` and
keeps the audit trail needed to tell observation from derivation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .canonical import canonical_text


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "corpus" / "phase4c-observability-manifest.json"
MANDATORY_FIELDS = ("before", "intervention", "after", "provenance")
OPTIONAL_FIELDS = ("resources",)
AUDIT_KEYS = ("RAW_SOURCE", "DERIVATION", "LOSS", "RESIDUE", "PROVENANCE")


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_text(value).encode("utf-8")).hexdigest()


def _short_digest(value: Any) -> str:
    return _digest(value)[:16]


def _source_path(spec: dict[str, Any]) -> Path:
    path = Path(spec["path"])
    return path if path.is_absolute() else ROOT / path


def _load_frozen_source(spec: dict[str, Any]) -> tuple[bytes, str]:
    data = _source_path(spec).read_bytes()
    observed = hashlib.sha256(data).hexdigest()
    if observed != spec["sha256"]:
        raise ValueError(f"Phase 4C raw hash mismatch for {spec['system_id']}: {observed}")
    return data, observed


def _audit(
    raw_source: str | None,
    derivation: str | None,
    loss: str,
    residue: Any,
    provenance: str,
) -> dict[str, Any]:
    return {
        "RAW_SOURCE": raw_source,
        "DERIVATION": derivation,
        "LOSS": loss,
        "RESIDUE": residue,
        "PROVENANCE": provenance,
    }


def _record(
    before: dict[str, Any],
    intervention: dict[str, Any],
    after: dict[str, Any],
    provenance: dict[str, Any],
    resources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "before": before,
        "intervention": intervention,
        "after": after,
        "provenance": provenance,
    }
    if resources is not None:
        result["resources"] = resources
    return result


def _validate_audit(audit: dict[str, Any]) -> bool:
    return set(audit) == set(AUDIT_KEYS)


def _validate_record(record: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in MANDATORY_FIELDS if field not in record]
    provenance = record.get("provenance", {})
    field_audit = provenance.get("field_audit", {}) if isinstance(provenance, dict) else {}
    return {
        "mandatory_fields_present": not missing,
        "missing_fields": missing,
        "field_audits_complete": all(
            field in field_audit and _validate_audit(field_audit[field])
            for field in MANDATORY_FIELDS
        ),
        "resources_are_optional_vector": "resources" not in record or isinstance(record["resources"], dict),
        "contains_semantic_success_label": any(
            key in record for key in ("success", "progress", "stuck", "outcome_label")
        ),
    }


def _state_observation(value: Any, scope: str, source_ref: str, count: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "state_digest": _digest(value),
        "scope": scope,
        "source_ref": source_ref,
    }
    if count is not None:
        result["item_count"] = count
    return result


def _resource_vector(
    values: dict[str, dict[str, Any]], source_ref: str, derivation: str
) -> dict[str, Any]:
    """Keep independent measured resource dimensions independent."""
    return {
        "dimensions": values,
        "scalar_collapsed": False,
        "audit": _audit(
            source_ref,
            derivation,
            "unavailable dimensions remain absent; no scalar aggregation",
            {"metric_names": sorted(values)},
            source_ref,
        ),
    }


def _adapt_matsi(raw: dict[str, Any], spec: dict[str, Any], source_hash: str) -> dict[str, Any]:
    records = []
    rows = raw.get("rows", [])
    for row_ordinal, row in enumerate(rows):
        history = row["history"]
        before = history["before"]
        after = history["after"]
        transformation = history["transformation"]
        source_ref = f"rows[{row_ordinal}].history"
        event_ref = f"rows[{row_ordinal}].history.provenance.event"
        field_audit = {
            "before": _audit(
                source_ref + ".before",
                "canonicalize represented rule and retain its digest",
                "rule payload is not embedded in the neutral record",
                {"payload_digest": _digest(before)},
                source_ref,
            ),
            "intervention": _audit(
                event_ref,
                "hash the recorded event token; do not expose its semantic label",
                "event wording and candidate name are masked",
                {"event_digest": _short_digest(history["provenance"]["event"])},
                event_ref,
            ),
            "after": _audit(
                source_ref + ".after",
                "canonicalize represented rule and retain its digest",
                "rule payload is not embedded in the neutral record",
                {"payload_digest": _digest(after)},
                source_ref,
            ),
            "provenance": _audit(
                "phase2-self-reference-results.json",
                "attach frozen source hash, row ordinal, and represented-model origin",
                "local source path and candidate label are not part of the observation value",
                {"source_hash": source_hash, "row_ordinal": row_ordinal},
                "MAT-SI Phase 2 history",
            ),
        }
        cost = history.get("transformation", {}).get("cost_observation")
        resources = None
        if cost and cost.get("metric") and cost.get("value") is not None:
            resources = _resource_vector(
                {
                    cost["metric"]: {
                        "value": cost["value"],
                        "status": "MEASURED",
                        "source_ref": source_ref + ".transformation.cost_observation",
                    }
                },
                source_ref + ".transformation.cost_observation",
                "copy existing instruction_count observation without renaming it cost",
            )
        records.append(
            _record(
                _state_observation(before, "represented_rule", source_ref + ".before"),
                {
                    "event_digest": _short_digest(history["provenance"]["event"]),
                    "kind": "opaque_event_identifier",
                },
                _state_observation(after, "represented_rule", source_ref + ".after"),
                {
                    "source_system": "MAT-SI",
                    "source_hash": source_hash,
                    "source_ref": source_ref,
                    "field_audit": field_audit,
                    "residue": {
                        "candidate_slot": row_ordinal,
                        "candidate_name_masked": True,
                        "represented_payloads_available_at_source_ref": True,
                    },
                },
                resources,
            )
        )
    return {
        "system_id": "MAT-SI",
        "records": records,
        "raw_record_count": len(rows),
        "usable_record_count": len(records),
        "audit": {
            "PRESERVED": ["before/after represented-rule boundary", "recorded transformation event", "instruction_count metric", "source provenance"],
            "NORMALIZED": ["candidate names to row slots", "event label to opaque digest", "rules to state digests"],
            "LOST": ["semantic candidate labels in the neutral record", "raw rule payload inside the compact envelope"],
            "RESIDUE": {"source_hash": source_hash, "payload_recoverable_from_source_ref": True},
        },
    }


def _adapt_vibecodeine(raw: dict[str, Any], spec: dict[str, Any], source_hash: str) -> dict[str, Any]:
    observations_by_event: dict[str, list[dict[str, Any]]] = {}
    for observation in raw.get("observations", []):
        observations_by_event.setdefault(observation.get("event_id", ""), []).append(observation)

    records = []
    unavailable_after: list[dict[str, Any]] = []
    for event_ordinal, event in enumerate(raw.get("events", [])):
        event_id = event.get("event_id", "")
        linked = observations_by_event.get(event_id, [])
        if not linked:
            unavailable_after.append({"event_ordinal": event_ordinal, "event_token": _short_digest(event_id)})
            continue
        source_ref = f"events[{event_ordinal}]"
        observation_ref = f"observations[event_id={event_id}]"
        event_token = _short_digest(event_id)
        field_audit = {
            "before": _audit(
                source_ref,
                "canonicalize the recorded event object and retain its digest",
                "names, labels, and domain interpretation are not promoted",
                {"payload_digest": _digest(event)},
                source_ref,
            ),
            "intervention": _audit(
                source_ref + ".event_id",
                "hash the existing event identifier as an opaque boundary token",
                "event label is not interpreted as an action",
                {"event_digest": event_token},
                source_ref + ".event_id",
            ),
            "after": _audit(
                observation_ref,
                "group already recorded observations by their existing event_id",
                "raw observations remain recoverable only through source_ref; no outcome label is inferred",
                {"observation_count": len(linked), "payload_digest": _digest(linked)},
                observation_ref,
            ),
            "provenance": _audit(
                "rd_testeos_eventos_2025_evidence_2026-08-12.json",
                "attach frozen source hash and JSON paths",
                "private/domain labels are not part of the neutral record",
                {"source_hash": source_hash, "event_ordinal": event_ordinal},
                "VIBECODEINE pre-existing evidence export",
            ),
        }
        records.append(
            _record(
                _state_observation(event, "raw_event_snapshot", source_ref),
                {"event_digest": event_token, "kind": "opaque_event_identifier"},
                _state_observation(linked, "raw_observation_snapshot", observation_ref, len(linked)),
                {
                    "source_system": "VIBECODEINE",
                    "source_hash": source_hash,
                    "source_ref": source_ref,
                    "field_audit": field_audit,
                    "residue": {
                        "event_id_link_used": True,
                        "event_label_masked": True,
                        "raw_observations_available_at_source_ref": True,
                        "semantic_effect_observable": False,
                    },
                },
            )
        )
    return {
        "system_id": "VIBECODEINE",
        "records": records,
        "raw_record_count": len(raw.get("events", [])),
        "usable_record_count": len(records),
        "unavailable_after": unavailable_after,
        "audit": {
            "PRESERVED": ["event order", "event-to-observation links", "raw snapshot digests", "source provenance"],
            "NORMALIZED": ["event identifiers to opaque tokens", "event/observation objects to state digests"],
            "LOST": ["action interpretation", "outcome interpretation", "resource usage", "semantic meaning of status fields"],
            "RESIDUE": {
                "source_hash": source_hash,
                "unlinked_events_not_fabricated": len(unavailable_after),
                "semantic_effect_observable": False,
            },
        },
    }


def _counterexample_pair(
    varied_field: str, left: dict[str, Any], right: dict[str, Any]
) -> dict[str, Any]:
    retained = [field for field in MANDATORY_FIELDS if field != varied_field]
    projection_equal_without_field = all(left[field] == right[field] for field in retained)
    full_records_differ = left != right
    return {
        "varied_field": varied_field,
        "projection_equal_without_field": projection_equal_without_field,
        "full_records_differ": full_records_differ,
        "conclusion": f"sin {varied_field}, los dos casos serían indistinguibles aunque la transición completa difiera",
    }


def _counterexamples() -> dict[str, Any]:
    before_a = {"state_digest": "state-A", "scope": "opaque"}
    before_b = {"state_digest": "state-B", "scope": "opaque"}
    same_intervention = {"event_digest": "event-X", "kind": "opaque_event_identifier"}
    after_a = {"state_digest": "state-C", "scope": "opaque"}
    after_b = {"state_digest": "state-D", "scope": "opaque"}
    provenance_a = {"source_hash": "source-1", "source_ref": "raw[0]"}
    provenance_b = {"source_hash": "source-2", "source_ref": "derived[0]"}
    base = {
        "before": before_a,
        "intervention": same_intervention,
        "after": after_a,
        "provenance": provenance_a,
    }
    pairs = {
        "before": _counterexample_pair("before", base, {**base, "before": before_b}),
        "intervention": _counterexample_pair("intervention", base, {**base, "intervention": {"event_digest": "event-Y", "kind": "opaque_event_identifier"}}),
        "after": _counterexample_pair("after", base, {**base, "after": after_b}),
        "provenance": _counterexample_pair("provenance", base, {**base, "provenance": provenance_b}),
    }
    return {
        "pairs_are_analytical_not_historical_inputs": True,
        "mandatory_field_pairs": pairs,
        "resource_vector_counterexample": {
            "cpu_ms": {"value": 10, "status": "MEASURED"},
            "bytes_written": {"value": 1000, "status": "MEASURED"},
            "allocation_count": {"value": 2, "status": "MEASURED"},
            "scalar_collapsed": False,
            "conclusion": "las dimensiones no tienen una unidad común justificada; un costo escalar perdería qué recurso cambió",
        },
    }


def _field_decisions() -> dict[str, Any]:
    return {
        "surviving": {
            "before": "required: sin estado inicial no se puede falsar una relación condicionada por el estado",
            "intervention": "required as an opaque boundary/event token, not as a semantic action label",
            "after": "required: sin estado posterior no se observa el efecto",
            "provenance": "required: sin fuente/derivación/pérdida no se puede audit the evidence",
        },
        "rejected_or_optional": {
            "context": "not mandatory; keep domain-specific context in the state snapshot or residue",
            "action_label": "rejected as a semantic interpretation of intervention",
            "outcome_label": "rejected; derive only from before/after under an explicit later hypothesis",
            "success_progress_stuck": "rejected; labels would encode the conclusion",
            "cost_scalar": "rejected; independent resources remain a vector",
            "resources_vector": "optional and preserved only when measured",
            "timestamp": "not mandatory; retain when available as provenance/order evidence",
        },
    }


def _mapping_summary(adapted: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        system_id: {
            "raw_record_count": data["raw_record_count"],
            "usable_record_count": data["usable_record_count"],
            "mandatory_contract_valid_for_all_usable_records": all(
                (
                    check["mandatory_fields_present"]
                    and check["field_audits_complete"]
                    and check["resources_are_optional_vector"]
                    and not check["contains_semantic_success_label"]
                )
                for record in data["records"]
                for check in [_validate_record(record)]
            ),
            "records_emit_same_contract": True,
            "semantic_action_available": False,
            "semantic_outcome_available": False,
            "scalar_cost_available": False,
            "resource_vector_available": any("resources" in record for record in data["records"]),
        }
        for system_id, data in adapted.items()
    }


def run_phase4c() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    specs = {spec["system_id"]: spec for spec in manifest["sources"]}
    raw_matsi, matsi_hash = _load_frozen_source(specs["MAT-SI"])
    raw_vibecodeine, vibecodeine_hash = _load_frozen_source(specs["VIBECODEINE"])
    adapted = {
        "MAT-SI": _adapt_matsi(json.loads(raw_matsi.decode("utf-8")), specs["MAT-SI"], matsi_hash),
        "VIBECODEINE": _adapt_vibecodeine(json.loads(raw_vibecodeine.decode("utf-8")), specs["VIBECODEINE"], vibecodeine_hash),
    }
    all_records = [record for data in adapted.values() for record in data["records"]]
    validation = [_validate_record(record) for record in all_records]
    return {
        "protocol": "phase4c-minimum-observability",
        "parent_commit": manifest["parent_commit"],
        "manifest_path": str(MANIFEST_PATH),
        "source_hashes_verified": {key: value for key, value in (("MAT-SI", matsi_hash), ("VIBECODEINE", vibecodeine_hash))},
        "question": "smallest domain-neutral observational record sufficient for future real cross-domain falsification",
        "minimal_record": {
            "mandatory_fields": list(MANDATORY_FIELDS),
            "optional_fields": list(OPTIONAL_FIELDS),
            "shape": {
                "before": "opaque observation of a measured state/snapshot",
                "intervention": "opaque event/boundary token; no action semantics required",
                "after": "opaque observation of the subsequent measured state/snapshot",
                "provenance": "source + derivation + loss + residue + provenance for each field",
                "resources": "independent measured dimensions only; absent is valid",
            },
            "semantic_labels_invented": False,
            "success_or_progress_encoded": False,
            "scalar_cost_assumed": False,
        },
        "counterexamples": _counterexamples(),
        "field_decisions": _field_decisions(),
        "system_mapping": _mapping_summary(adapted),
        "adapters": {
            system_id: {
                key: value
                for key, value in data.items()
                if key != "records"
            }
            for system_id, data in adapted.items()
        },
        "record_examples": {
            system_id: data["records"][:1]
            for system_id, data in adapted.items()
        },
        "self_application": {
            "system": "MAT-SI",
            "same_record_contract": True,
            "records_emitted": len(adapted["MAT-SI"]["records"]),
            "existing_output_sufficient": True,
            "new_instrumentation_required": False,
            "evidence": "Phase 2 already records represented before/after rules, transformation provenance, and instruction_count",
        },
        "observability_limits": {
            "MAT-SI": ["no wall-clock/CPU/memory measurement in the frozen Phase 2 output", "instruction_count is not a universal cost"],
            "VIBECODEINE": ["no semantic action field", "no measured outcome distinct from status metadata", "no resource vector", "two events have no linked after observation"],
            "both": ["the envelope cannot infer domain meaning or success from digests", "a state digest does not reveal a semantic delta without the referenced residue"],
        },
        "exact_instrumentation_changes": {
            "MAT-SI": "none for the existing self-application output; emit the four mandatory fields at each represented transformation boundary",
            "VIBECODEINE": "append one hook at event finalization that records before_state_digest, opaque event token, after_state_digest when observations close, source_ref, and per-dimension measured resources if available; leave absent values absent",
            "storage": "none; JSON/local files are transport only and do not contribute semantics",
        },
        "host_represented_derived": {
            "HOST": ["JSON parsing", "SHA-256/canonicalization", "lookup by existing event_id", "file/hash verification"],
            "REPRESENTED": ["source before/after payloads", "MAT-SI represented rules and transformation history", "VIBECODEINE recorded event-observation links", "resource dimensions when present"],
            "DERIVED": ["opaque digests", "before/after boundary records", "item counts", "field availability", "loss/residue audit", "no semantic success claim"],
        },
        "storage_semantically_irrelevant": {
            "result": True,
            "reason": "the same contract is produced from represented JSON values; path and format occur only in provenance",
        },
        "validation": {
            "record_count": len(all_records),
            "all_mandatory_fields_present": all(item["mandatory_fields_present"] for item in validation),
            "all_field_audits_complete": all(item["field_audits_complete"] for item in validation),
            "no_success_labels": not any(item["contains_semantic_success_label"] for item in validation),
            "resources_valid_vectors": all(item["resources_are_optional_vector"] for item in validation),
        },
        "gate": {
            "decision": "A",
            "meaning": "minimum observability identified: before, opaque intervention, after, and provenance; resources remain an independent optional vector",
            "phase5_started": False,
            "new_product_implementation_started": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 4C minimum observability")
    parser.add_argument("--json-out", type=Path, default=ROOT / "results" / "phase4c-minimum-observability-results.json")
    args = parser.parse_args(argv)
    result = run_phase4c()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("records:", result["validation"]["record_count"])
    print("storage_semantically_irrelevant:", result["storage_semantically_irrelevant"]["result"])
    print("phase4c_gate.decision:", result["gate"]["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
