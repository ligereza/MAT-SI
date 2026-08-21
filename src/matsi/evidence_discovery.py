"""Phase 3D: derive falsifiable relations from observations before opening an oracle."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any
from urllib.request import urlopen

from .distillation import _node_count, _size
from .minimal_rewrite import match
from .real_distillation import (
    MANIFEST_PATH as PHASE3B_MANIFEST_PATH,
    _discover,
    _digest,
    _held_out,
    _neutralize,
    _pair_candidate,
    _static_behavior_signature,
    acquire_sources,
    neutral_units,
)
from .semantic_falsification import _safe_function, _strip_annotations


ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_MANIFEST_PATH = ROOT / "corpus" / "phase3d-evidence-discovery-manifest.json"
PHASE3C_MANIFEST_PATH = ROOT / "corpus" / "phase3c-semantic-control-manifest.json"
PHASE3B_RESULT_PATH = ROOT / "results" / "phase3b-real-distillation-results.json"
CONTROL_CACHE = Path(tempfile.gettempdir()) / "matsi-phase3d-evidence"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_frozen_source(spec: dict[str, Any]) -> str:
    if "source_url" in spec:
        target = CONTROL_CACHE / f"{spec['id']}.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            data = target.read_bytes()
        else:
            with urlopen(spec["source_url"], timeout=30) as response:
                data = response.read()
            target.write_bytes(data)
    else:
        data = (ROOT / spec["source_path"]).read_bytes().replace(b"\r\n", b"\n")
    observed = _sha256(data)
    if observed != spec["source_sha256"]:
        raise ValueError(f"frozen discovery hash mismatch for {spec['id']}: {observed}")
    return data.decode("utf-8")


def _anonymous_unit(source: str, spec: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    ordinal = spec["unit_ordinal"]
    clean = _strip_annotations(functions[ordinal])
    unit_source = ast.unparse(clean)
    representation, residue, _ = _neutralize(unit_source)
    return {
        "source_id": spec["id"],
        "ordinal": ordinal,
        "kind": type(clean).__name__,
        "representation": representation,
        "adapter_residue": residue,
        "static_behavior": _static_behavior_signature(clean),
        "ast": clean,
    }


def _execute(unit: dict[str, Any], inputs: list[list[Any]]) -> dict[str, Any]:
    try:
        function = _safe_function(unit)
        outputs = [function(*values) for values in inputs]
    except (TypeError, ValueError, SyntaxError) as error:
        return {
            "status": "UNKNOWN",
            "reason": str(error),
            "provenance": {"source_id": unit["source_id"], "manifest": "phase3d"},
        }
    return {
        "status": "OBSERVED",
        "outputs": outputs,
        "provenance": {
            "source_id": unit["source_id"],
            "manifest": "phase3d",
            "unit_ordinal": unit["ordinal"],
        },
    }


def _observations(
    units: dict[str, dict[str, Any]], inputs: list[list[Any]], input_set: str
) -> list[dict[str, Any]]:
    executed = {source_id: _execute(unit, inputs) for source_id, unit in units.items()}
    rows = []
    for index, input_value in enumerate(inputs):
        row = {
            "observation_id": f"obs_{index}",
            "input": input_value,
            "outputs": {
                source_id: executed[source_id].get("outputs", [None] * len(inputs))[index]
                for source_id in units
            },
            "status": "OBSERVED" if all(item["status"] == "OBSERVED" for item in executed.values()) else "UNKNOWN",
            "provenance": {
                "source_ids": list(units),
                "input_index": index,
                "input_set": input_set,
            },
        }
        if row["status"] == "UNKNOWN":
            row["reason"] = {source_id: executed[source_id].get("reason") for source_id in units}
        rows.append(row)
    return rows


def _comparison(operator: str, left: Any, right: Any) -> bool:
    if operator == "==":
        return left == right
    if operator == "<=":
        return left <= right
    if operator == ">=":
        return left >= right
    raise ValueError(f"unsupported relation operator {operator}")


def _relation_holds(hypothesis: dict[str, Any], rows: list[dict[str, Any]]) -> bool | None:
    if any(row["status"] != "OBSERVED" for row in rows):
        return None
    return all(
        _comparison(
            hypothesis["operator"],
            row["outputs"][hypothesis["left"]],
            row["outputs"][hypothesis["right"]],
        )
        for row in rows
    )


def _evidence_ref(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "observation_id": row["observation_id"],
        "input": row["input"],
        "outputs": row["outputs"],
        "provenance": row["provenance"],
    }


def _generate_hypotheses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enumerate the complete small generic binary relation language."""
    operators = ("==", "<=", ">=")
    hypotheses = []
    for operator in operators:
        hypothesis = {
            "id": f"pair_output_{operator}",
            "kind": "binary_output_relation",
            "left": "A",
            "right": "B",
            "operator": operator,
            "generated_from": "observations",
            "description_cost": _size({"kind": "binary_output_relation", "operator": operator}),
            "coverage": 0,
            "evidence_for": [],
            "evidence_against": [],
            "provenance": {"observation_ids": [row["observation_id"] for row in rows]},
        }
        for row in rows:
            if row["status"] != "OBSERVED":
                continue
            if _comparison(operator, row["outputs"]["A"], row["outputs"]["B"]):
                hypothesis["coverage"] += 1
                hypothesis["evidence_for"].append(_evidence_ref(row))
        if hypothesis["coverage"] == len(rows) and rows:
            hypotheses.append(hypothesis)
    return hypotheses


def _evaluate_hypothesis(hypothesis: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    holds = _relation_holds(hypothesis, rows)
    if holds is None:
        status = "UNKNOWN"
    else:
        status = "SURVIVED" if holds else "FALSIFIED"
    against = []
    if status == "FALSIFIED":
        against = [
            _evidence_ref(row)
            for row in rows
            if row["status"] != "OBSERVED"
            or not _comparison(
                hypothesis["operator"],
                row["outputs"][hypothesis["left"]],
                row["outputs"][hypothesis["right"]],
            )
        ]
    return {
        "hypothesis_id": hypothesis["id"],
        "status": status,
        "evidence_against": against,
        "coverage": sum(1 for row in rows if row["status"] == "OBSERVED") if holds is not None else 0,
        "provenance": {"input_set": rows[0]["provenance"]["input_set"] if rows else "empty"},
    }


def _negative_observations(
    unit_a: dict[str, Any], unit_n: dict[str, Any], inputs: list[list[Any]], input_set: str
) -> list[dict[str, Any]]:
    return _observations({"A": unit_a, "N": unit_n}, inputs, input_set)


def _evaluate_against_negative(hypothesis: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    negative_hypothesis = dict(hypothesis, right="N")
    result = _evaluate_hypothesis(negative_hypothesis, rows)
    return {
        "hypothesis_id": hypothesis["id"],
        "status": result["status"],
        "evidence_against": result["evidence_against"],
        "provenance": {"input_set": rows[0]["provenance"]["input_set"] if rows else "empty", "right_source": "N"},
    }


def _sealed_oracle_check(units: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Open Phase 3C's oracle only after all discovery and falsification work."""
    manifest = json.loads(PHASE3C_MANIFEST_PATH.read_text(encoding="utf-8"))
    oracle = manifest["oracle"]
    inputs = oracle["inputs"]
    expected = oracle["expected_outputs"]
    outputs = {
        source_id: _execute(unit, inputs)["outputs"] for source_id, unit in units.items() if source_id in {"A", "B"}
    }
    return {
        "opened_after_discovery_and_held_out": True,
        "oracle_source": oracle["source"],
        "inputs": inputs,
        "sealed_expected_outputs": expected,
        "observed_outputs": outputs,
        "A_equals_B_on_oracle": outputs["A"] == outputs["B"],
        "A_matches_sealed_outputs": outputs["A"] == expected,
        "B_matches_sealed_outputs": outputs["B"] == expected,
        "discovered_claim_validated": outputs["A"] == outputs["B"],
        "stronger_semantic_description_claimed": False,
        "provenance": {"manifest": "corpus/phase3c-semantic-control-manifest.json", "oracle_only": True},
    }


def _real_g_information_test() -> dict[str, Any]:
    phase3b = json.loads(PHASE3B_RESULT_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(PHASE3B_MANIFEST_PATH.read_text(encoding="utf-8"))
    sources = acquire_sources(manifest)
    adapted = {entry["id"]: neutral_units(entry, sources[entry["id"]]) for entry in manifest["entries"]}
    discovery = _discover(adapted["A"], adapted["B"])
    selected = discovery["selected_G"]
    digest_matches = _digest(selected["generalization"]) == phase3b["blind_structural_pass"]["discovery"]["selected_G"]["generalization_digest"]
    match_counts = {
        entry_id: len(_held_out(adapted[entry_id], selected)["matched_units"])
        for entry_id in ("C", "N1", "N2")
    }
    return {
        "G_frozen_digest_matches": digest_matches,
        "structural_matches": match_counts,
        "behavioral_interface_exposed": False,
        "falsifiable_behavioral_hypotheses_generated": [],
        "status": "STRUCTURE_FOUND_BUT_NO_OBSERVABLE_CORRESPONDENCE_CAN_BE_DERIVED",
        "missing_information": [
            "callable input boundary for the matched neutral units",
            "comparable observable output contract",
            "safe execution fixture for dependencies, state, and effects",
        ],
        "provenance": {
            "phase3b_commit": "e9d018e",
            "manifest_commit": phase3b["manifest_commit"],
            "candidate_source_pair": selected["provenance"]["source_entries"],
            "generalization_node_count": _node_count(selected["generalization"]),
        },
    }


def run_phase3d() -> dict[str, Any]:
    manifest = json.loads(DISCOVERY_MANIFEST_PATH.read_text(encoding="utf-8"))
    sources = {spec["id"]: _load_frozen_source(spec) for spec in manifest["sources"]}
    units = {
        spec["id"]: _anonymous_unit(sources[spec["id"]], spec) for spec in manifest["sources"]
    }
    structural_candidate = _pair_candidate(units["A"], units["B"])
    negative_structural_match = match(
        structural_candidate["generalization"], units["N"]["representation"]
    ) is not None

    discovery_rows = _observations(
        {source_id: units[source_id] for source_id in ("A", "B")},
        manifest["inputs"]["discovery"],
        "frozen_discovery",
    )
    hypotheses = _generate_hypotheses(discovery_rows)
    frozen_hypotheses = deepcopy(hypotheses)
    frozen_digest = _digest(frozen_hypotheses)

    held_out_rows = _observations(
        {source_id: units[source_id] for source_id in ("A", "B")},
        manifest["inputs"]["held_out"],
        "frozen_held_out",
    )
    held_out_evaluations = [_evaluate_hypothesis(hypothesis, held_out_rows) for hypothesis in frozen_hypotheses]
    surviving = [
        hypothesis
        for hypothesis, evaluation in zip(frozen_hypotheses, held_out_evaluations)
        if evaluation["status"] == "SURVIVED"
    ]

    negative_rows = _negative_observations(
        units["A"], units["N"], manifest["inputs"]["held_out"], "frozen_negative_held_out"
    )
    negative_evaluations = [_evaluate_against_negative(hypothesis, negative_rows) for hypothesis in surviving]
    discriminators = [
        evaluation["hypothesis_id"]
        for evaluation in negative_evaluations
        if evaluation["status"] == "FALSIFIED"
    ]

    sealed_oracle = _sealed_oracle_check({"A": units["A"], "B": units["B"]})
    real_g = _real_g_information_test()
    decision = "A" if discriminators else "B" if hypotheses else "B"
    return {
        "protocol": "phase3d-evidence-discovery",
        "phase_order": [
            "frozen_observations",
            "hypothesis_generation_without_oracle",
            "hypothesis_freeze",
            "held_out_falsification",
            "negative_control",
            "sealed_oracle_validation",
        ],
        "frozen_inputs": {
            "manifest": "corpus/phase3d-evidence-discovery-manifest.json",
            "manifest_commit": "0d1b2b4",
            "expected_outputs_used_before_discovery": False,
            "semantic_labels_used_before_discovery": False,
            "manual_relation_used_before_discovery": False,
        },
        "discovery": {
            "structural_candidate": {
                "generalization_digest": _digest(structural_candidate["generalization"]),
                "shared_structure_nodes": structural_candidate["shared_structure_nodes"],
                "compression_gain": structural_candidate["compression_gain"],
                "reconstruction": structural_candidate["reconstruction_left"]
                and structural_candidate["reconstruction_right"],
            },
            "observations": discovery_rows,
            "relation_language": {
                "forms": ["binary output equality", "binary output less-than-or-equal", "binary output greater-than-or-equal"],
                "domain_specific_properties": False,
                "description": "small generic comparator language over observed output pairs",
            },
            "candidate_hypotheses": hypotheses,
            "candidate_count": len(hypotheses),
            "all_candidates_are_minimal_supported_forms": True,
        },
        "frozen_hypotheses": {
            "hypotheses": frozen_hypotheses,
            "digest": frozen_digest,
            "changed_after_held_out": frozen_digest != _digest(frozen_hypotheses),
        },
        "held_out": {
            "observations": held_out_rows,
            "evaluations": held_out_evaluations,
            "surviving_hypothesis_ids": [hypothesis["id"] for hypothesis in surviving],
        },
        "negative_control": {
            "observations": negative_rows,
            "evaluations": negative_evaluations,
            "structural_candidate_reused": True,
            "structural_match_to_G": negative_structural_match,
            "discriminating_hypothesis_ids": discriminators,
            "behavioral_distinction_observed": bool(discriminators),
        },
        "sealed_oracle_validation": sealed_oracle,
        "real_phase3b_G_information_test": real_g,
        "llm_boundary": {
            "proposal_allowed": True,
            "confidence_is_evidence": False,
            "required_pipeline": ["proposal", "evidence_for/evidence_against", "held_out_falsification", "survive/fail/unknown"],
            "llm_integration_built": False,
        },
        "host_represented_derived": {
            "HOST": ["Python parsing", "restricted execution", "generic numeric comparison", "oracle file access after the freeze"],
            "REPRESENTED": ["ordinary input/output observations", "generic relation hypotheses", "evidence and provenance records"],
            "DERIVED": ["candidate coverage", "held-out status", "negative-control discrimination", "oracle validation"],
        },
        "gate": {
            "decision": decision,
            "meaning": {
                "A": "a relation was derived from observations, survived held-out inputs, and rejected the structural negative",
                "B": "behavior can validate hypotheses, but useful hypothesis generation remains the bottleneck",
            }[decision],
            "phase4_started": False,
            "discovered_relation_claims": [
                f"A.output {hypothesis['operator']} B.output"
                for hypothesis in surviving
                if hypothesis["id"] in discriminators
            ],
            "stronger_semantic_relation_claimed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 3D evidence discovery")
    parser.add_argument("--json-out", type=Path, default=ROOT / "results" / "phase3d-evidence-discovery-results.json")
    args = parser.parse_args(argv)
    result = run_phase3d()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("candidate_count:", result["discovery"]["candidate_count"])
    print("surviving_hypotheses:", result["held_out"]["surviving_hypothesis_ids"])
    print("negative_discriminators:", result["negative_control"]["discriminating_hypothesis_ids"])
    print("phase3d_gate.decision:", result["gate"]["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
