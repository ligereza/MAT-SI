"""Phase 4: test transfer of an observed trajectory relation across domains."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from .canonical import canonical_text
from .distillation import _size
from .real_distillation import _digest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "corpus" / "phase4-cross-domain-manifest.json"
ENVELOPE_FIELDS = ("context", "observation", "action", "outcome", "cost", "provenance")
COMPARABLE_FIELDS = ("context", "observation", "action", "outcome", "cost")


def _logical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def _load_source(spec: dict[str, Any]) -> tuple[dict[str, Any], str]:
    data = _logical_bytes(ROOT / spec["path"])
    observed_hash = hashlib.sha256(data).hexdigest()
    if observed_hash != spec["sha256"]:
        raise ValueError(f"frozen Phase 4 source hash mismatch for {spec['id']}: {observed_hash}")
    return json.loads(data.decode("utf-8")), observed_hash


def _blind_adapter(raw: dict[str, Any], source_id: str, source_hash: str) -> tuple[dict[str, Any], dict[str, Any]]:
    trajectories = []
    for trajectory_index, trajectory in enumerate(raw["trajectories"]):
        events = []
        for event_index, event in enumerate(trajectory["events"]):
            if set(event) != set(ENVELOPE_FIELDS):
                raise ValueError(f"event does not match common envelope in {source_id}")
            provenance_token = hashlib.sha256(
                f"{source_hash}:{trajectory_index}:{event_index}".encode("utf-8")
            ).hexdigest()[:16]
            events.append(
                {
                    "context": event["context"],
                    "observation": event["observation"],
                    "action": event["action"],
                    "outcome": event["outcome"],
                    "cost": event["cost"],
                    "provenance": {
                        "opaque_source": provenance_token,
                        "trajectory_index": trajectory_index,
                        "event_index": event_index,
                    },
                }
            )
        trajectories.append({"trajectory_index": trajectory_index, "events": events})
    blind = {"source_id": source_id, "trajectories": trajectories}
    audit = {
        "PRESERVED": ["envelope field presence", "chronology", "adjacency", "observable field values", "cost values"],
        "NORMALIZED": ["source identity", "trajectory identity", "event provenance to opaque tokens"],
        "LOST": ["domain label", "producer label", "trajectory label", "raw filenames", "human interpretation"],
        "RESIDUE": {
            "source_hash": source_hash,
            "removed_top_level_fields": ["domain_label", "producer"],
            "removed_trajectory_fields": ["trajectory_label"],
            "removed_event_provenance_fields": ["raw_id"],
        },
    }
    return blind, audit


def _windows(domain: dict[str, Any], length: int = 4) -> list[dict[str, Any]]:
    result = []
    for trajectory in domain["trajectories"]:
        events = trajectory["events"]
        for start in range(0, len(events) - length + 1):
            result.append(
                {
                    "source_id": domain["source_id"],
                    "trajectory_index": trajectory["trajectory_index"],
                    "start": start,
                    "event_indices": list(range(start, start + length)),
                    "events": events[start : start + length],
                }
            )
    return result


def _atom_id(field: str, relation: str) -> str:
    return f"{field}.{relation}"


def _features_between(left: dict[str, Any], right: dict[str, Any]) -> set[str]:
    features = set()
    for field in COMPARABLE_FIELDS:
        if canonical_text(left[field]) == canonical_text(right[field]):
            features.add(_atom_id(field, "equal"))
        if isinstance(left[field], (int, float)) and isinstance(right[field], (int, float)):
            if right[field] > left[field]:
                features.add(_atom_id(field, "increasing"))
            if right[field] < left[field]:
                features.add(_atom_id(field, "decreasing"))
    return features


def _window_feature_sets(window: dict[str, Any]) -> list[set[str]]:
    return [
        _features_between(window["events"][index], window["events"][index + 1])
        for index in range(len(window["events"]) - 1)
    ]


def _window_ref(window: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": window["source_id"],
        "trajectory_index": window["trajectory_index"],
        "start": window["start"],
        "event_indices": window["event_indices"],
        "provenance": {
            "opaque_source": window["events"][0]["provenance"]["opaque_source"],
            "input_kind": "blind_common_envelope_window",
        },
    }


def _intersection(windows: list[dict[str, Any]], offset: int) -> set[str]:
    sets = [_window_feature_sets(window)[offset] for window in windows]
    return set.intersection(*sets) if sets else set()


def _candidate_relation(
    relation_id: str,
    phase: str,
    features: list[str],
    windows: list[dict[str, Any]],
    residue: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": relation_id,
        "phase": phase,
        "features": features,
        "generated_from": "blind_A_B_observations",
        "evidence_for": [_window_ref(window) for window in windows],
        "evidence_against": [],
        "coverage": len(windows),
        "cost": _size({"phase": phase, "features": features}),
        "residue": residue,
        "provenance": {"source_ids": sorted({window["source_id"] for window in windows})},
    }


def _discover_from_ab(domains: dict[str, dict[str, Any]], audits: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ab_windows = _windows(domains["A"]) + _windows(domains["B"])
    prefix_common = sorted(set.intersection(_intersection(ab_windows, 0), _intersection(ab_windows, 1)))
    prediction_common = sorted(_intersection(ab_windows, 2))
    residue = {
        "unmodeled_envelope_fields": [field for field in COMPARABLE_FIELDS if not any(field in atom for atom in prefix_common + prediction_common)],
        "adapter_residue_digests": {source_id: _digest(audits[source_id]["RESIDUE"]) for source_id in ("A", "B")},
    }
    atomic_candidates = []
    for phase, features in (("prefix", prefix_common), ("prediction", prediction_common)):
        for feature in features:
            atomic_candidates.append(
                _candidate_relation(
                    f"{phase}:{feature}", phase, [feature], ab_windows, residue
                )
            )
    selected = {
        "id": "G_maximal_common_trajectory_relation",
        "window_length": 4,
        "prefix_features": prefix_common,
        "prediction_features": prediction_common,
        "selection_policy": "maximal conjunction of generic field relations supported by every A+B window",
        "generated_from": "blind_A_B_observations",
        "evidence_for": [_window_ref(window) for window in ab_windows],
        "evidence_against": [],
        "coverage": len(ab_windows),
        "cost": _size({"prefix": prefix_common, "prediction": prediction_common}),
        "residue": residue,
        "provenance": {"source_ids": ["A", "B"], "window_count": len(ab_windows)},
    }
    return {
        "windows": [_window_ref(window) for window in ab_windows],
        "atomic_candidates": atomic_candidates,
        "prefix_common_features": prefix_common,
        "prediction_common_features": prediction_common,
        "candidate_count": len(atomic_candidates),
        "selected_G": selected,
    }


def _has_features(events: list[dict[str, Any]], features: list[str], offset: int) -> bool:
    return set(features).issubset(_features_between(events[offset], events[offset + 1]))


def _evaluate_window(window: dict[str, Any], G: dict[str, Any]) -> dict[str, Any]:
    prefix_match = all(
        _has_features(window["events"], G["prefix_features"], offset) for offset in (0, 1)
    )
    prediction_holds = _has_features(window["events"], G["prediction_features"], 2)
    status = "NOT_MATCHED" if not prefix_match else "SURVIVED" if prediction_holds else "FALSIFIED"
    return {
        "window": _window_ref(window),
        "prefix_match": prefix_match,
        "prediction_holds": prediction_holds,
        "status": status,
        "evidence_against": [] if status != "FALSIFIED" else [_window_ref(window)],
        "provenance": _window_ref(window)["provenance"],
    }


def _prediction_metrics(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    matched = [item for item in evaluations if item["prefix_match"]]
    all_windows = evaluations
    true_count = sum(1 for item in all_windows if item["prediction_holds"])
    false_count = len(all_windows) - true_count
    g_accuracy = (
        sum(1 for item in matched if item["prediction_holds"]) / len(matched) if matched else None
    )
    baseline_accuracy = max(true_count, false_count) / len(all_windows) if all_windows else None
    return {
        "matched_windows": len(matched),
        "total_windows": len(all_windows),
        "G_prediction_accuracy_on_matched_windows": g_accuracy,
        "no_G_baseline_modal_accuracy_over_all_C_windows": baseline_accuracy,
        "predictive_gain": g_accuracy - baseline_accuracy if g_accuracy is not None and baseline_accuracy is not None else None,
        "G_beats_no_G_baseline": g_accuracy is not None and baseline_accuracy is not None and g_accuracy > baseline_accuracy,
        "provenance": {"evaluation": "held_out_C_windows", "baseline": "all_C_windows_without_prefix_selection"},
    }


def run_phase4() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    specs = {spec["id"]: spec for spec in manifest["sources"]}

    # C is deliberately not loaded or adapted until after G has been frozen.
    domains_ab = {}
    audits_ab = {}
    source_hashes = {}
    for source_id in ("A", "B"):
        raw, source_hash = _load_source(specs[source_id])
        domains_ab[source_id], audits_ab[source_id] = _blind_adapter(raw, source_id, source_hash)
        source_hashes[source_id] = source_hash

    discovery = _discover_from_ab(domains_ab, audits_ab)
    G = discovery["selected_G"]
    G_digest = _digest(G)
    frozen_G = deepcopy(G)

    raw_c, source_hash_c = _load_source(specs["C"])
    domain_c, audit_c = _blind_adapter(raw_c, "C", source_hash_c)
    source_hashes["C"] = source_hash_c
    c_windows = _windows(domain_c)
    evaluations = [_evaluate_window(window, frozen_G) for window in c_windows]
    metrics = _prediction_metrics(evaluations)

    return {
        "protocol": "phase4-cross-domain",
        "parent_commit": "a79845a",
        "phase3_closed": True,
        "no_products_implemented": ["CODEINE", "X-ANA-X", "VIZZ", "KETAMINE"],
        "common_experience_envelope": {
            "fields": list(ENVELOPE_FIELDS),
            "role": "transport structure only; domain values remain opaque residue",
        },
        "source_hashes": source_hashes,
        "adapter_audit": {"A": audits_ab["A"], "B": audits_ab["B"], "C": audit_c},
        "blind_pass": {
            "domain_names_visible_to_discovery": False,
            "descriptive_labels_visible_to_discovery": False,
            "filenames_visible_to_discovery": False,
            "human_interpretation_visible_to_discovery": False,
            "chronology_and_transitions_preserved": True,
            "costs_preserved": True,
        },
        "discovery_from_A_B": discovery,
        "frozen_G": {
            "G": frozen_G,
            "digest": G_digest,
            "changed_after_C": False,
            "C_was_loaded_after_freeze": True,
        },
        "held_out_C": {
            "evaluations": evaluations,
            "trajectory_window_count": len(c_windows),
            "structural_matches": sum(1 for item in evaluations if item["prefix_match"]),
            "prediction_metrics": metrics,
        },
        "transfer": {
            "STRUCTURAL_TRANSFER": {
                "status": "OBSERVED" if any(item["prefix_match"] for item in evaluations) else "NOT_FOUND",
                "matched_windows": sum(1 for item in evaluations if item["prefix_match"]),
            },
            "BEHAVIORAL_TRANSFER": {
                "status": "OBSERVED" if any(item["status"] == "SURVIVED" for item in evaluations) else "NOT_FOUND",
                "survived_windows": sum(1 for item in evaluations if item["status"] == "SURVIVED"),
                "falsified_windows": sum(1 for item in evaluations if item["status"] == "FALSIFIED"),
            },
            "PREDICTIVE_TRANSFER": {
                "status": "OBSERVED" if metrics["G_beats_no_G_baseline"] else "NOT_FOUND",
                "metrics": metrics,
            },
        },
        "negative_control": {
            "principle": "a prefix can match while the subsequent outcome changes productively",
            "productive_repetition_window_indices": [
                item["window"]["trajectory_index"]
                for item in evaluations
                if item["prefix_match"] and item["status"] == "FALSIFIED"
            ],
            "structural_match_is_not_badness": True,
            "provenance": {"source_id": "C", "selection": "post_freeze_behavioral_outcome"},
        },
        "representation_transfer": {
            "STRUCTURAL_TRANSFER": "prefix feature conjunction matches opaque C windows",
            "BEHAVIORAL_TRANSFER": "the same prefix has both surviving and falsified continuations",
            "PREDICTIVE_TRANSFER": "matched C windows outperform the no-G modal baseline",
        },
        "host_represented_derived": {
            "HOST": ["JSON parsing", "hash verification", "generic field comparison", "metric arithmetic"],
            "REPRESENTED": ["common event envelope", "opaque trajectories", "generic relation atoms", "G and provenance"],
            "DERIVED": ["candidate support", "prefix matching", "continuation status", "predictive gain"],
        },
        "gate": {
            "decision": "A" if metrics["G_beats_no_G_baseline"] else "D",
            "meaning": (
                "a relation derived from A+B predicts a held-out property in C without domain labels"
                if metrics["G_beats_no_G_baseline"]
                else "the discovered structures do not transfer beyond their original domains"
            ),
            "phase5_started": False,
            "product_implementation_started": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 4 cross-domain transfer")
    parser.add_argument("--json-out", type=Path, default=ROOT / "results" / "phase4-cross-domain-results.json")
    args = parser.parse_args(argv)
    result = run_phase4()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("G_digest:", result["frozen_G"]["digest"])
    print("structural_transfer:", result["transfer"]["STRUCTURAL_TRANSFER"]["status"])
    print("behavioral_transfer:", result["transfer"]["BEHAVIORAL_TRANSFER"]["status"])
    print("predictive_transfer:", result["transfer"]["PREDICTIVE_TRANSFER"]["status"])
    print("phase4_gate.decision:", result["gate"]["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
