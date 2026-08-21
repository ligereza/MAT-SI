"""Phase 3C: test whether structural candidates acquire behavioral evidence."""

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


ROOT = Path(__file__).resolve().parents[2]
PHASE3B_RESULT_PATH = ROOT / "results" / "phase3b-real-distillation-results.json"
CONTROL_MANIFEST_PATH = ROOT / "corpus" / "phase3c-semantic-control-manifest.json"
CONTROL_CACHE = Path(tempfile.gettempdir()) / "matsi-phase3c-controls"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_control_source(spec: dict[str, Any]) -> str:
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
        raise ValueError(f"frozen control hash mismatch for {spec['id']}: {observed}")
    return data.decode("utf-8")


def _strip_annotations(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.FunctionDef | ast.AsyncFunctionDef:
    clean = deepcopy(node)
    clean.decorator_list = []
    clean.returns = None
    clean.type_comment = None
    if clean.body and isinstance(clean.body[0], ast.Expr) and isinstance(clean.body[0].value, ast.Constant):
        if isinstance(clean.body[0].value.value, str):
            clean.body = clean.body[1:]
    for argument in [*clean.args.posonlyargs, *clean.args.args, *clean.args.kwonlyargs]:
        argument.annotation = None
        argument.type_comment = None
    if clean.args.vararg:
        clean.args.vararg.annotation = None
    if clean.args.kwarg:
        clean.args.kwarg.annotation = None
    return clean


def _function_unit(source: str, function_name: str, source_id: str) -> dict[str, Any]:
    tree = ast.parse(source)
    candidates = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
    ]
    if len(candidates) != 1:
        raise ValueError(f"expected one top-level function {function_name!r}")
    clean = _strip_annotations(candidates[0])
    unit_source = ast.unparse(clean)
    representation, residue, _ = _neutralize(unit_source)
    return {
        "ordinal": 0,
        "kind": type(clean).__name__,
        "source_id": source_id,
        "function_name": function_name,
        "representation": representation,
        "adapter_residue": residue,
        "static_behavior": _static_behavior_signature(clean),
        "ast": clean,
        "source_bytes": len(unit_source.encode("utf-8")),
    }


_SAFE_NODES = {
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Return,
    ast.Assign,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.IfExp,
    ast.Compare,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Eq,
    ast.NotEq,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.USub,
    ast.UAdd,
}


def _safe_function(unit: dict[str, Any]) -> Any:
    tree = ast.Module(body=[deepcopy(unit["ast"])], type_ignores=[])
    for node in ast.walk(tree):
        if type(node) not in _SAFE_NODES:
            raise ValueError(f"control function uses unsupported node {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in {"min", "max"}:
                raise ValueError("control function calls a non-whitelisted function")
    tree = ast.fix_missing_locations(tree)
    namespace: dict[str, Any] = {"__builtins__": {"min": min, "max": max}}
    exec(compile(tree, "<phase3c-control>", "exec"), namespace)
    return namespace[unit["ast"].name]


def _observe_control(unit: dict[str, Any], inputs: list[list[Any]], expected: list[Any]) -> dict[str, Any]:
    try:
        function = _safe_function(unit)
        outputs = [function(*values) for values in inputs]
    except (TypeError, ValueError, SyntaxError) as error:
        return {
            "status": "UNKNOWN",
            "reason": str(error),
            "provenance": {"source_id": unit["source_id"], "function_name": unit["function_name"]},
        }
    return {
        "status": "OBSERVED",
        "inputs": inputs,
        "outputs": outputs,
        "expected_outputs": expected,
        "matches_oracle": outputs == expected,
        "provenance": {"source_id": unit["source_id"], "function_name": unit["function_name"]},
    }


def _first_node_path(value: Any, path: tuple[str | int, ...] = ()) -> tuple[str | int, ...] | None:
    if isinstance(value, dict):
        if "node" in value:
            return path
        for key, child in value.items():
            found = _first_node_path(child, path + (key,))
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _first_node_path(child, path + (index,))
            if found is not None:
                return found
    return None


def _replace_path(value: Any, path: tuple[str | int, ...], replacement: Any) -> Any:
    if not path:
        return replacement
    result = deepcopy(value)
    head, *tail = path
    if isinstance(result, dict):
        result[head] = _replace_path(result[head], tuple(tail), replacement)
    else:
        result[head] = _replace_path(result[head], tuple(tail), replacement)
    return result


def _intervene_on_match(selected: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]:
    before = unit["representation"]
    bindings = match(selected["generalization"], before)
    path = _first_node_path(selected["generalization"])
    if bindings is None or path is None:
        return {
            "status": "UNKNOWN",
            "reason": "frozen G did not expose a common node path in this matched unit",
            "provenance": {"source": "frozen_G", "unit": unit.get("source_id", "unknown")},
        }
    after = _replace_path(before, path, {"node": "Phase3CIntervention", "fields": {}})
    after_bindings = match(selected["generalization"], after)
    return {
        "status": "UNKNOWN",
        "before": {"representation_digest": _digest(before), "match": True},
        "intervention": {
            "operation": "replace_first_shared_node_with_unseen_node_kind",
            "path": list(path),
            "representation_digest": _digest(after),
        },
        "after": {"representation_digest": _digest(after), "match": after_bindings is not None},
        "delta": {
            "structural_match": f"True -> {after_bindings is not None}",
            "behavior": "UNKNOWN",
        },
        "reusable_relation": "a structural mutation changes matchability; G supplies no behavioral prediction",
        "provenance": {"source": "frozen_G", "unit": unit.get("source_id", "unknown")},
    }


def _frozen_real_evidence() -> dict[str, Any]:
    phase3b_result = json.loads(PHASE3B_RESULT_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(PHASE3B_MANIFEST_PATH.read_text(encoding="utf-8"))
    sources = acquire_sources(manifest)
    adapted = {
        entry["id"]: neutral_units(entry, sources[entry["id"]]) for entry in manifest["entries"]
    }
    discovery = _discover(adapted["A"], adapted["B"])
    selected = discovery["selected_G"]
    frozen_selected = phase3b_result["blind_structural_pass"]["discovery"]["selected_G"]
    digest_matches = _digest(selected["generalization"]) == frozen_selected["generalization_digest"]
    targets = {}
    for entry_id in ("C", "N1", "N2"):
        held_out = _held_out(adapted[entry_id], selected)
        rows = []
        for unit in adapted[entry_id]["units"]:
            bindings = match(selected["generalization"], unit["representation"])
            if bindings is not None:
                row = {
                    "unit_ordinal": unit["ordinal"],
                    "kind": unit["kind"],
                    "structural_match": True,
                    "phase3b_useful_value": held_out["useful_value"],
                    "semantic_status": "UNKNOWN",
                    "semantic_reason": "frozen real-repository slices were not executed; AST recurrence is not a behavioral oracle",
                    "intervention": _intervene_on_match(selected, unit),
                    "provenance": {
                        "manifest_commit": phase3b_result["manifest_commit"],
                        "entry_id": entry_id,
                        "source_path": unit.get("source_path", adapted[entry_id]["source_path"]),
                        "unit_ordinal": unit["ordinal"],
                    },
                }
                rows.append(row)
        targets[entry_id] = {
            "participated_in_G": entry_id in {"A", "B"},
            "phase3b_structural_false_positive": entry_id in {"C", "N1", "N2"},
            "matched_units": rows,
            "semantic_evidence": "UNKNOWN",
        }
    return {
        "frozen_phase3b_commit": "e9d018e",
        "frozen_manifest_commit": phase3b_result["manifest_commit"],
        "G_recomputed_without_C_N1_N2": True,
        "G_digest_matches_phase3b_result": digest_matches,
        "selected_G_summary": {
            "source_pair": selected["provenance"]["source_entries"],
            "shared_structure_nodes": selected["shared_structure_nodes"],
            "compression_gain": selected["compression_gain"],
            "generalization_digest": _digest(selected["generalization"]),
        },
        "targets": targets,
        "conclusion": "C/N1/N2 remain structurally matched but behaviorally UNKNOWN; G is descriptive, not predictive, on these slices",
    }


def _control_evidence() -> dict[str, Any]:
    manifest = json.loads(CONTROL_MANIFEST_PATH.read_text(encoding="utf-8"))
    positive_specs = manifest["positive_controls"]
    negative_spec = manifest["negative_control"]
    positive_sources = [_load_control_source(spec) for spec in positive_specs]
    negative_source = _load_control_source(negative_spec)
    positive_units = [
        _function_unit(source, spec["function_name"], spec["id"])
        for source, spec in zip(positive_sources, positive_specs)
    ]
    negative_unit = _function_unit(negative_source, negative_spec["function_name"], negative_spec["id"])
    left, right = positive_units
    generalization = _pair_candidate(left, right)
    inputs = manifest["oracle"]["inputs"]
    expected = manifest["oracle"]["expected_outputs"]
    observations = {
        unit["source_id"]: _observe_control(unit, inputs, expected)
        for unit in [*positive_units, negative_unit]
    }
    positive_ok = all(
        observations[unit["source_id"]]["status"] == "OBSERVED"
        and observations[unit["source_id"]]["matches_oracle"]
        for unit in positive_units
    )
    negative_rejected = (
        observations[negative_unit["source_id"]]["status"] == "OBSERVED"
        and not observations[negative_unit["source_id"]]["matches_oracle"]
    )
    negative_match = match(generalization["generalization"], negative_unit["representation"]) is not None
    return {
        "corpus_manifest": "corpus/phase3c-semantic-control-manifest.json",
        "labels_used_to_discover_G": False,
        "candidate": {
            "source_pair": [left["source_id"], right["source_id"]],
            "generalization_digest": _digest(generalization["generalization"]),
            "shared_structure_nodes": generalization["shared_structure_nodes"],
            "reconstruction": generalization["reconstruction_left"] and generalization["reconstruction_right"],
        },
        "observations": observations,
        "negative_control": {
            "structural_match_to_positive_G": negative_match,
            "behaviorally_rejected_by_oracle": negative_rejected,
        },
        "represented_evidence": {
            "hypothesis": {"relation": "both implementations satisfy the frozen clamp oracle"},
            "interventions": [
                {
                    "name": "low_boundary",
                    "input": inputs[0],
                    "delta": "both positive implementations return the lower bound",
                    "provenance": {"source_ids": [unit["source_id"] for unit in positive_units], "oracle": manifest["oracle"]["source"]},
                },
                {
                    "name": "interior_value",
                    "input": inputs[1],
                    "delta": "both positive implementations preserve the interior value",
                    "provenance": {"source_ids": [unit["source_id"] for unit in positive_units], "oracle": manifest["oracle"]["source"]},
                },
                {
                    "name": "high_boundary",
                    "input": inputs[2],
                    "delta": "both positive implementations return the upper bound",
                    "provenance": {"source_ids": [unit["source_id"] for unit in positive_units], "oracle": manifest["oracle"]["source"]},
                },
            ],
            "provenance": {
                "oracle": manifest["oracle"]["source"],
                "source_ids": [unit["source_id"] for unit in [*positive_units, negative_unit]],
            },
        },
        "distinguishes_reusable_behavior": positive_ok and negative_rejected,
    }
def run_phase3c() -> dict[str, Any]:
    real_evidence = _frozen_real_evidence()
    controls = _control_evidence()
    decision = "A" if controls["distinguishes_reusable_behavior"] else "B"
    return {
        "protocol": "phase3c-semantic-falsification",
        "frozen_inputs": {
            "phase3b_result": "results/phase3b-real-distillation-results.json",
            "phase3b_commit": real_evidence["frozen_phase3b_commit"],
            "control_manifest": "corpus/phase3c-semantic-control-manifest.json",
            "phase3b_semantic_core_modified": False,
        },
        "host_represented_derived": {
            "HOST": [
                "Python parsing and restricted control-function execution",
                "network/file acquisition and SHA-256 verification",
                "comparison of observed outputs with the external oracle",
            ],
            "REPRESENTED": [
                "neutral AST U and frozen G",
                "generic structural match and provenance-bearing observations",
                "input interventions and the clamp relation as ordinary data",
            ],
            "DERIVED": [
                "structural matchability and reconstruction",
                "output equality with the oracle",
                "behavioral rejection of the comparable negative control",
                "UNKNOWN when no safe behavioral oracle is available",
            ],
        },
        "frozen_real_repository_evidence": real_evidence,
        "positive_control_evidence": controls,
        "gate": {
            "decision": decision,
            "meaning": {
                "A": "behavioral falsification distinguishes a reusable abstraction from misleading structural similarity",
                "B": "evidence is possible but hard to acquire",
            }[decision],
            "phase4_started": False,
            "unresolved": (
                "The Phase 3B real-repository G remains behaviorally UNKNOWN on C/N1/N2; this is not converted into a positive claim."
                if decision == "A"
                else "The frozen control oracle did not distinguish the positive and negative controls."
            ),
        },
        "closure": {
            "universal_ir_introduced": False,
            "semantic_ast_introduced": False,
            "embeddings_or_llm_used": False,
            "domain_opcode_added": False,
            "full_execution_platform_built": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 3C semantic falsification")
    parser.add_argument("--json-out", type=Path, default=ROOT / "results" / "phase3c-semantic-falsification-results.json")
    args = parser.parse_args(argv)
    result = run_phase3c()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("frozen_G_digest_matches:", result["frozen_real_repository_evidence"]["G_digest_matches_phase3b_result"])
    print("positive_control_distinguishes:", result["positive_control_evidence"]["distinguishes_reusable_behavior"])
    print("phase3c_gate.decision:", result["gate"]["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
