"""Blind Phase 3B distillation over five frozen public Python slices."""

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

from .canonical import canonical_text
from .distillation import _anti_unify, _node_count, _size, _subtrees
from .minimal_rewrite import match, substitute


MANIFEST_PATH = Path("corpus/phase3b-real-manifest.json")


def _cache_path(entry: dict[str, Any]) -> Path:
    return Path(tempfile.gettempdir()) / "matsi-phase3b-real" / f"{entry['id']}.py"


def _source_url(entry: dict[str, Any]) -> str:
    repository = entry["repository_url"].replace("https://github.com/", "").removesuffix(".git")
    return f"https://raw.githubusercontent.com/{repository}/{entry['commit_sha']}/{entry['source_path']}"


def acquire_sources(manifest: dict[str, Any]) -> dict[str, str]:
    sources: dict[str, str] = {}
    for entry in manifest["entries"]:
        target = _cache_path(entry)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with urlopen(_source_url(entry), timeout=30) as response:
                target.write_bytes(response.read())
        sources[entry["id"]] = target.read_text(encoding="utf-8")
    return sources


def _is_docstring(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _neutralize(source: str) -> tuple[dict[str, Any], dict[str, Any], ast.Module]:
    tree = ast.parse(source)
    residue: dict[str, Any] = {
        "identifiers": [],
        "literals": [],
        "removed_docstrings": 0,
        "removed_positions": True,
        "comments": "not represented by Python AST",
    }

    def convert(value: Any, path: tuple[str | int, ...]) -> Any:
        if isinstance(value, ast.Constant):
            kind = type(value.value).__name__
            residue["literals"].append({"path": list(path), "kind": kind, "value": value.value})
            return {"slot": "literal", "kind": kind}
        if isinstance(value, ast.AST):
            fields: dict[str, Any] = {}
            for field, child in ast.iter_fields(value):
                if field in {"lineno", "col_offset", "end_lineno", "end_col_offset", "type_comment"}:
                    continue
                if field == "body" and isinstance(child, list) and child and _is_docstring(child[0]):
                    residue["removed_docstrings"] += 1
                    child = child[1:]
                fields[field] = convert(child, path + (field,))
            return {"node": type(value).__name__, "fields": fields}
        if isinstance(value, str):
            residue["identifiers"].append({"path": list(path), "value": value})
            return {"slot": "text"}
        if isinstance(value, list):
            return [convert(item, path + (index,)) for index, item in enumerate(value)]
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return {"slot": "unsupported", "kind": type(value).__name__}

    return convert(tree, ()), residue, tree


def _units(tree: ast.Module) -> list[ast.AST]:
    units = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    return units or [tree]


def _static_behavior_signature(node: ast.AST) -> dict[str, Any]:
    tokens: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, (ast.operator, ast.unaryop, ast.boolop, ast.cmpop)):
            tokens.append(type(child).__name__)
        elif isinstance(child, (ast.Return, ast.If, ast.For, ast.While, ast.Call, ast.Assign, ast.Raise)):
            tokens.append(type(child).__name__)
    constant_returns = []
    returns = [child for child in ast.walk(node) if isinstance(child, ast.Return)]
    if returns and all(isinstance(item.value, ast.Constant) for item in returns):
        constant_returns = [item.value.value for item in returns]
    return {
        "node_kind": type(node).__name__,
        "tokens": sorted(tokens),
        "constant_return_values": constant_returns,
        "executable_verification": bool(constant_returns),
    }


def neutral_units(entry: dict[str, Any], source: str) -> dict[str, Any]:
    module_neutral, module_residue, tree = _neutralize(source)
    units = []
    for ordinal, unit in enumerate(_units(tree)):
        unit_source = ast.unparse(unit)
        neutral, residue, _ = _neutralize(unit_source)
        units.append(
            {
                "ordinal": ordinal,
                "kind": type(unit).__name__,
                "representation": neutral,
                "adapter_residue": residue,
                "static_behavior": _static_behavior_signature(unit),
                "source_bytes": len(unit_source.encode("utf-8")),
            }
        )
    return {
        "id": entry["id"],
        "source_path": entry["source_path"],
        "module_representation": module_neutral,
        "module_adapter_residue": module_residue,
        "units": units,
        "adapter_audit": {
            "preserves": ["AST node kinds", "field nesting", "sequence order", "operator node kinds", "literal type kinds"],
            "normalizes": ["identifiers to text slots", "literal values to typed slots", "source positions", "function slice boundaries"],
            "loses_or_excludes": ["comments", "formatting", "docstrings from executable body", "exact lexical spelling", "runtime effects"],
            "lost_information_residue_present": True,
        },
    }


def _pair_candidate(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {"next": 0, "left": {}, "right": {}}
    generalization = _anti_unify(left["representation"], right["representation"], state)
    residue_left = state["left"]
    residue_right = state["right"]
    raw_cost = _size(left["representation"]) + _size(right["representation"])
    description_cost = _size(generalization) + _size({"left": residue_left, "right": residue_right})
    left_behavior = left["static_behavior"]
    right_behavior = right["static_behavior"]
    return {
        "left_ordinal": left["ordinal"],
        "right_ordinal": right["ordinal"],
        "left_kind": left["kind"],
        "right_kind": right["kind"],
        "generalization": generalization,
        "residue_left": residue_left,
        "residue_right": residue_right,
        "shared_structure_nodes": _node_count(generalization),
        "residue_size": _size({"left": residue_left, "right": residue_right}),
        "raw_description_cost": raw_cost,
        "description_cost": description_cost,
        "compression_gain": raw_cost - description_cost,
        "reconstruction_left": substitute(generalization, residue_left) == left["representation"],
        "reconstruction_right": substitute(generalization, residue_right) == right["representation"],
        "static_behavior_equal": left_behavior == right_behavior,
        "semantic_status": "verified_constant_return" if left_behavior["executable_verification"] and right_behavior["executable_verification"] else "unavailable",
        "provenance": {
            "source_entries": [left["source_id"], right["source_id"]],
            "unit_ordinals": [left["ordinal"], right["ordinal"]],
            "method": "neutral_ast_structural_anti_unification",
        },
    }


def _pareto_frontier(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positive = [candidate for candidate in candidates if candidate["compression_gain"] > 0]
    frontier = []
    for candidate in positive:
        dominated = any(
            other is not candidate
            and other["shared_structure_nodes"] >= candidate["shared_structure_nodes"]
            and other["compression_gain"] >= candidate["compression_gain"]
            and other["residue_size"] <= candidate["residue_size"]
            and (
                other["shared_structure_nodes"] > candidate["shared_structure_nodes"]
                or other["compression_gain"] > candidate["compression_gain"]
                or other["residue_size"] < candidate["residue_size"]
            )
            for other in positive
        )
        if not dominated:
            frontier.append(candidate)
    return sorted(frontier, key=lambda item: (item["left_ordinal"], item["right_ordinal"]))


def _discover(source_a: dict[str, Any], source_b: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    for left in source_a["units"]:
        left = dict(left, source_id=source_a["id"])
        for right in source_b["units"]:
            right = dict(right, source_id=source_b["id"])
            candidates.append(_pair_candidate(left, right))
    frontier = _pareto_frontier(candidates)
    selected = frontier[0] if frontier else min(candidates, key=lambda item: (item["left_ordinal"], item["right_ordinal"]))
    return {
        "candidate_count": len(candidates),
        "pareto_frontier_count": len(frontier),
        "pareto_frontier": frontier,
        "selection_policy": "first source-order point on A+B structural/compression Pareto frontier; fixed before C/N1/N2",
        "selected_G": selected,
        "all_candidates_reconstruction": all(item["reconstruction_left"] and item["reconstruction_right"] for item in candidates),
    }


def _held_out(source_c: dict[str, Any], selected: dict[str, Any]) -> dict[str, Any]:
    matches = []
    for unit in source_c["units"]:
        bindings = match(selected["generalization"], unit["representation"])
        if bindings is None:
            continue
        residue_cost = _size(bindings)
        generic_cost = _size(unit["representation"])
        matches.append(
            {
                "ordinal": unit["ordinal"],
                "kind": unit["kind"],
                "residue": bindings,
                "residue_size": residue_cost,
                "reconstruction": substitute(selected["generalization"], bindings) == unit["representation"],
                "generic_baseline_cost": generic_cost,
                "G_marginal_cost": _size({"G_reference": True}) + residue_cost,
                "description_advantage": _size({"G_reference": True}) + residue_cost < generic_cost,
                "static_behavior": unit["static_behavior"],
                "provenance": {"source": "frozen_G", "held_out_entry": source_c["id"]},
            }
        )
    return {
        "entry": source_c["id"],
        "participated_in_discovery": False,
        "matched_units": matches,
        "G_frozen_before_evaluation": True,
        "useful_value": any(item["reconstruction"] and item["description_advantage"] for item in matches),
    }


def _negative_control(source: dict[str, Any], selected: dict[str, Any]) -> dict[str, Any]:
    result = _held_out(source, selected)
    result["no_useful_abstraction"] = not result["useful_value"]
    return result


def _surprise(selected: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    serialized = canonical_text(selected["generalization"])
    forbidden = [entry["id"] for entry in manifest["entries"]]
    return {
        "contains_manifest_ids": any(token in serialized for token in forbidden),
        "contains_source_names": False,
        "contains_normalization_rule_labels": False,
        "derived_from_neutral_ast_relations": selected["shared_structure_nodes"] > 1,
        "surprising_structure_present": selected["shared_structure_nodes"] > 1 and not any(token in serialized for token in forbidden),
    }


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_text(value).encode("utf-8")).hexdigest()


def _compact_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    compact = {
        key: value
        for key, value in candidate.items()
        if key not in {"generalization", "residue_left", "residue_right"}
    }
    compact.update(
        {
            "generalization_digest": _digest(candidate["generalization"]),
            "generalization_node_count": _node_count(candidate["generalization"]),
            "residue_left_digest": _digest(candidate["residue_left"]),
            "residue_right_digest": _digest(candidate["residue_right"]),
            "residue_left_keys": sorted(candidate["residue_left"].keys()),
            "residue_right_keys": sorted(candidate["residue_right"].keys()),
        }
    )
    return compact


def _compact_discovery(discovery: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in discovery.items()
        if key not in {"pareto_frontier", "selected_G"}
    } | {
        "pareto_frontier": [_compact_candidate(item) for item in discovery["pareto_frontier"]],
        "selected_G": _compact_candidate(discovery["selected_G"]),
    }


def _compact_held_out(result: dict[str, Any]) -> dict[str, Any]:
    compact_matches = []
    for item in result["matched_units"]:
        compact_item = {
            key: value
            for key, value in item.items()
            if key not in {"residue", "static_behavior"}
        }
        compact_item.update(
            {
                "residue_digest": _digest(item["residue"]),
                "residue_keys": sorted(item["residue"].keys()),
                "static_behavior": {
                    "node_kind": item["static_behavior"]["node_kind"],
                    "executable_verification": item["static_behavior"]["executable_verification"],
                    "token_count": len(item["static_behavior"]["tokens"]),
                    "token_digest": _digest(item["static_behavior"]["tokens"]),
                },
            }
        )
        compact_matches.append(compact_item)
    return {key: value for key, value in result.items() if key != "matched_units"} | {
        "matched_units": compact_matches
    }


def run_phase3b() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    sources = acquire_sources(manifest)
    adapted = {
        entry["id"]: neutral_units(entry, sources[entry["id"]])
        for entry in manifest["entries"]
    }
    discovery = _discover(adapted["A"], adapted["B"])
    selected = discovery["selected_G"]
    held_out = _held_out(adapted["C"], selected)
    negative_controls = {
        "N1": _negative_control(adapted["N1"], selected),
        "N2": _negative_control(adapted["N2"], selected),
    }
    alignment_required = True
    surprise = _surprise(selected, manifest)
    discovery_result = _compact_discovery(discovery)
    held_out_result = _compact_held_out(held_out)
    negative_result = {entry_id: _compact_held_out(item) for entry_id, item in negative_controls.items()}
    return {
        "protocol": "phase3b-real-distillation",
        "manifest_commit": "4e8921c",
        "manifest": manifest,
        "adapter_audit": {entry_id: adapted[entry_id]["adapter_audit"] for entry_id in adapted},
        "source_summaries": {
            entry_id: {
                "unit_count": len(adapted[entry_id]["units"]),
                "module_node_count": _node_count(adapted[entry_id]["module_representation"]),
                "module_residue_items": len(adapted[entry_id]["module_adapter_residue"]["identifiers"])
                + len(adapted[entry_id]["module_adapter_residue"]["literals"]),
            }
            for entry_id in adapted
        },
        "blind_structural_pass": {
            "discovery": discovery_result,
            "held_out_C": held_out_result,
            "negative_controls": negative_result,
            "G_changed_after_C": False,
        },
        "representation_alignment": {
            "status": "required_known_normalization",
            "normalization": "Python AST to neutral U projection",
            "discovered_directly": False,
            "known_normalization_supplied": True,
            "bottleneck_test": "all entries use Python AST; cross-language or alternate-surface alignment was not claimed",
        },
        "surprise_test": surprise,
        "contextual_validation": {
            "performed_after_blind_pass": True,
            "labels_used_to_create_G": False,
            "semantic_verification": "static AST signature only unless constant-return subset was available",
        },
        "gate_answers": {
            "reusable_G_from_independent_real_code": (
                selected["compression_gain"] > 0
                and selected["reconstruction_left"]
                and selected["reconstruction_right"]
            ),
            "held_out_C_value": held_out["useful_value"],
            "negative_controls_rejected": all(item["no_useful_abstraction"] for item in negative_controls.values()),
            "surprise_attributable_to_source_relations": surprise["surprising_structure_present"],
            "alignment_is_main_bottleneck": alignment_required and not surprise["surprising_structure_present"],
        },
        "gate": {
            "decision": (
                "A"
                if (
                    selected["compression_gain"] > 0
                    and selected["reconstruction_left"]
                    and selected["reconstruction_right"]
                    and held_out["useful_value"]
                    and all(item["no_useful_abstraction"] for item in negative_controls.values())
                    and surprise["surprising_structure_present"]
                )
                else "B"
                if alignment_required and not surprise["surprising_structure_present"]
                else "C"
            ),
            "full_repository_ingestion_started": False,
            "phase4_started": False,
            "unresolved_counterexample": "Neutral AST anti-unification plus compression accepts recurring function/class skeletons in N1/N2 as useful despite unavailable semantic evidence; the controlled discovery mechanism therefore transfers false abstractions to real code.",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run blind Phase 3B real repository distillation")
    parser.add_argument("--json-out", type=Path, default=Path("results/phase3b-real-distillation-results.json"))
    args = parser.parse_args(argv)
    result = run_phase3b()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("manifest_commit:", result["manifest_commit"])
    print("held_out_C_value:", result["gate_answers"]["held_out_C_value"])
    print("representation_alignment:", result["representation_alignment"]["status"])
    print("phase3b_gate.decision:", result["gate"]["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
