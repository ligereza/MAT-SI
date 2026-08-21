"""Small controlled Phase 3 distillation experiment."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from .canonical import canonical_text
from .kernels import AtomPairKernel, ContentDagKernel, RewriteEgraphKernel
from .minimal_rewrite import match, rewrite, substitute, variable
from .rule_vm import RepresentedRuleEvaluator


def _rule(name: str, path: list[str], operation: str, constant: int) -> dict[str, Any]:
    return {
        "name": name,
        "meta": {"version": 1, "flags": ["u", "v"], "limits": {"low": 0, "high": 100}},
        "program": [
            {"op": "get", "path": path},
            {"op": "const", "value": constant},
            {"op": operation},
            {"op": "return"},
        ],
    }


def controlled_corpus() -> dict[str, Any]:
    """Neutral corpus; IDs do not name the abstraction being sought."""

    return {
        "u_a": {"rule": _rule("rho", ["value"], "add", 1)},
        "u_b": {"rule": _rule("sigma", ["payload", "n"], "add", 1)},
        "u_c": {"rule": _rule("tau", ["packet", "count"], "add", 1)},
        "u_d": {"rule": _rule("upsilon", ["value"], "mul", 1)},
        "u_e": {"rule": _rule("phi", ["value"], "add", 2)},
        "u_f": {"rule": _rule("chi", ["x"], "mul", 7)},
        "u_g": {
            "rule": {
                "name": "psi",
                "meta": {"version": 1, "flags": ["u", "v"], "limits": {"low": 0, "high": 100}},
                "program": [
                    {"op": "get", "path": ["nested", "q"]},
                    {"op": "const", "value": 3},
                    {"op": "add"},
                    {"op": "const", "value": 2},
                    {"op": "mul"},
                    {"op": "return"},
                ],
            }
        },
        "u_n1": {"rule": _rule("left_label", ["value"], "add", 1)},
        "u_n2": {"rule": _rule("right_label", ["value"], "add", 1)},
    }


def _size(value: Any) -> int:
    return len(canonical_text(value).encode("utf-8"))


def _node_count(value: Any) -> int:
    if isinstance(value, dict):
        return 1 + sum(_node_count(key) + _node_count(item) for key, item in value.items())
    if isinstance(value, list):
        return 1 + sum(_node_count(item) for item in value)
    return 1


def _put_path(path: list[str], value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current = result
    for segment in path[:-1]:
        current[segment] = {}
        current = current[segment]
    current[path[-1]] = value
    return result


def _semantic_signature(rule: dict[str, Any], evaluator: RepresentedRuleEvaluator) -> list[Any]:
    if "program" not in rule:
        raise ValueError("surface is not in executable program form")
    getter = next(instruction for instruction in rule["program"] if instruction["op"] == "get")
    path = list(getter["path"])
    signature = []
    for value in (0, 1, 2, 5):
        input_value = _put_path(path, value)
        rule_representation = AtomPairKernel().encode(rule)
        input_representation = AtomPairKernel().encode(input_value)
        output = evaluator.evaluate(AtomPairKernel(), rule_representation, input_representation)
        signature.append(AtomPairKernel().decode(output))
    return signature


def _new_variable(state: dict[str, int], left: Any, right: Any) -> dict[str, str]:
    name = f"v{state['next']}"
    state["next"] += 1
    state.setdefault("left", {})[name] = deepcopy(left)
    state.setdefault("right", {})[name] = deepcopy(right)
    return variable(name)


def _anti_unify(left: Any, right: Any, state: dict[str, Any]) -> Any:
    if left == right:
        return deepcopy(left)
    if isinstance(left, dict) and isinstance(right, dict) and set(left) == set(right):
        return {key: _anti_unify(left[key], right[key], state) for key in left}
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [_anti_unify(a, b, state) for a, b in zip(left, right)]
    return _new_variable(state, left, right)


def _anti_unification_candidate(left: dict[str, Any], right: dict[str, Any], evaluator: RepresentedRuleEvaluator) -> dict[str, Any]:
    state: dict[str, Any] = {"next": 0, "left": {}, "right": {}}
    generalization = _anti_unify(left, right, state)
    left_residue = state["left"]
    right_residue = state["right"]
    reconstructed_left = substitute(generalization, left_residue)
    reconstructed_right = substitute(generalization, right_residue)
    try:
        left_signature = _semantic_signature(left, evaluator)
    except (KeyError, StopIteration, TypeError, ValueError):
        left_signature = None
    try:
        right_signature = _semantic_signature(right, evaluator)
    except (KeyError, StopIteration, TypeError, ValueError):
        right_signature = None
    raw_cost = _size(left) + _size(right)
    description_cost = _size(generalization) + _size({"left": left_residue, "right": right_residue})
    return {
        "generalization": generalization,
        "residue_left": left_residue,
        "residue_right": right_residue,
        "shared_structure_nodes": _node_count(generalization),
        "residue_size_left": _size(left_residue),
        "residue_size_right": _size(right_residue),
        "raw_description_cost": raw_cost,
        "description_cost": description_cost,
        "compression_gain": raw_cost - description_cost,
        "reconstruction_left": reconstructed_left == left,
        "reconstruction_right": reconstructed_right == right,
        "left_semantic_signature": left_signature,
        "right_semantic_signature": right_signature,
        "semantic_equivalence": left_signature is not None and left_signature == right_signature,
        "provenance": {
            "method": "structural_anti_unification",
            "inputs": [left.get("name"), right.get("name")],
        },
    }


def _subtrees(value: Any) -> set[str]:
    result = {canonical_text(value)}
    if isinstance(value, dict):
        for key, item in value.items():
            result.update(_subtrees(key))
            result.update(_subtrees(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_subtrees(item))
    return result


def _baseline_comparison(left: dict[str, Any], right: dict[str, Any], candidate: dict[str, Any], evaluator: RepresentedRuleEvaluator) -> dict[str, Any]:
    common_subtrees = _subtrees(left) & _subtrees(right)
    exact = left == right
    compression_only = {
        "candidate": "anti_unification",
        "description_cost": candidate["description_cost"],
        "compression_gain": candidate["compression_gain"],
        "semantic_test_performed": False,
        "would_keep_compressed_description": candidate["compression_gain"] > 0,
    }
    return {
        "exact_structural_matching": {
            "matches": exact,
            "explains_pair": exact,
        },
        "naive_subtree_recurrence": {
            "common_subtree_count": len(common_subtrees),
            "largest_common_subtree_bytes": max((len(item.encode("utf-8")) for item in common_subtrees), default=0),
            "reconstructs_pair": False,
            "predicts_semantics": False,
        },
        "simple_anti_unification": {
            "reconstructs_pair": candidate["reconstruction_left"] and candidate["reconstruction_right"],
            "semantic_equivalence": candidate["semantic_equivalence"],
            "compression_gain": candidate["compression_gain"],
        },
        "compression_only_selection": compression_only,
    }


def discover_pair(pair_id: str, left: dict[str, Any], right: dict[str, Any], evaluator: RepresentedRuleEvaluator) -> dict[str, Any]:
    candidate = _anti_unification_candidate(left, right, evaluator)
    baselines = _baseline_comparison(left, right, candidate, evaluator)
    useful = (
        candidate["reconstruction_left"]
        and candidate["reconstruction_right"]
        and candidate["semantic_equivalence"]
        and candidate["compression_gain"] > 0
    )
    return {
        "pair": pair_id,
        "candidate_G": candidate,
        "baselines": baselines,
        "signals": {
            "structural_recurrence": candidate["shared_structure_nodes"],
            "semantic_equivalence": candidate["semantic_equivalence"],
            "compression_gain": candidate["compression_gain"],
        },
        "useful_abstraction": useful,
        "rejection_reason": None if useful else (
            "semantic_mismatch" if not candidate["semantic_equivalence"] else "no_positive_compression_gain"
        ),
    }


def _held_out_test(generalization: dict[str, Any], held_out: dict[str, Any], discovery: dict[str, Any], evaluator: RepresentedRuleEvaluator) -> dict[str, Any]:
    template = generalization["generalization"]
    bindings = match(template, held_out)
    reconstructed = substitute(template, bindings) if bindings is not None else None
    held_signature = _semantic_signature(held_out, evaluator)
    predicted_signature = generalization["left_semantic_signature"]
    generic_cost = _size(held_out)
    explanation_cost = _size(template) + _size(bindings or {})
    marginal_explanation_cost = _size({"generalization_ref": "G"}) + _size(bindings or {})
    return {
        "held_out_id": held_out["name"],
        "participated_in_discovery": False,
        "matches_G": bindings is not None,
        "residue": bindings,
        "residue_size": _size(bindings or {}),
        "reconstruction": reconstructed == held_out,
        "generic_baseline_cost": generic_cost,
        "G_explanation_cost": explanation_cost,
        "G_marginal_explanation_cost": marginal_explanation_cost,
        "description_advantage": marginal_explanation_cost < generic_cost,
        "predicted_signature": predicted_signature,
        "held_out_signature": held_signature,
        "predicts_property": predicted_signature == held_signature,
        "provenance": {
            "source": "frozen_discovery_G",
            "discovery_pair": discovery["pair"],
        },
    }


def _normalization_rules() -> list[dict[str, Any]]:
    return [
        {"pattern": {"steps": variable("items")}, "replacement": {"program": variable("items")}},
        {"pattern": {"kind": "read", "target": variable("path")}, "replacement": {"op": "get", "path": variable("path")}},
        {"pattern": {"kind": "literal", "content": variable("value")}, "replacement": {"op": "const", "value": variable("value")}},
        {"pattern": {"kind": "combine", "symbol": "+"}, "replacement": {"op": "add"}},
        {"pattern": {"kind": "emit"}, "replacement": {"op": "return"}},
    ]


def _cross_representation_test(evaluator: RepresentedRuleEvaluator) -> dict[str, Any]:
    surface_a = {
        "program": [
            {"op": "get", "path": ["value"]},
            {"op": "const", "value": 1},
            {"op": "add"},
            {"op": "return"},
        ]
    }
    surface_b = {
        "steps": [
            {"kind": "read", "target": ["payload", "n"]},
            {"kind": "literal", "content": 1},
            {"kind": "combine", "symbol": "+"},
            {"kind": "emit"},
        ]
    }
    raw = _anti_unification_candidate(surface_a, surface_b, evaluator)
    normalized = surface_b
    for rule in _normalization_rules():
        normalized = rewrite(rule, normalized)
    normalized_candidate = _anti_unification_candidate(surface_a, normalized, evaluator)
    return {
        "surface_a": surface_a,
        "surface_b": surface_b,
        "represented_normalization_rules": _normalization_rules(),
        "raw_surface": {
            "exact_match": surface_a == surface_b,
            "generalization": raw["generalization"],
            "compression_gain": raw["compression_gain"],
            "semantic_equivalence_available": False,
        },
        "normalized_surface": {
            "normalized_b": normalized,
            "generalization": normalized_candidate["generalization"],
            "reconstructs_b": normalized_candidate["reconstruction_right"],
            "compression_gain": normalized_candidate["compression_gain"],
            "semantic_equivalence": normalized_candidate["semantic_equivalence"],
        },
        "G_survives_surface_change_after_represented_normalization": (
            normalized_candidate["reconstruction_left"]
            and normalized_candidate["reconstruction_right"]
            and normalized_candidate["compression_gain"] > 0
        ),
        "raw_layout_alone_would_fail": raw["compression_gain"] <= 0,
        "provenance": {"source": "represented_normalization_then_distillation"},
    }


def run_phase3() -> dict[str, Any]:
    corpus = controlled_corpus()
    evaluator = RepresentedRuleEvaluator()
    discovery = discover_pair(
        "u_a+u_b", corpus["u_a"]["rule"], corpus["u_b"]["rule"], evaluator
    )
    held_out = _held_out_test(
        discovery["candidate_G"], corpus["u_c"]["rule"], discovery, evaluator
    )
    controls = {
        "similar_surface_different_behavior": discover_pair(
            "u_d+u_e", corpus["u_d"]["rule"], corpus["u_e"]["rule"], evaluator
        ),
        "partial_shared_structure": discover_pair(
            "u_e+u_f", corpus["u_e"]["rule"], corpus["u_f"]["rule"], evaluator
        ),
        "no_useful_shared_abstraction": discover_pair(
            "u_f+u_g", corpus["u_f"]["rule"], corpus["u_g"]["rule"], evaluator
        ),
        "same_transformation_different_names": discover_pair(
            "u_n1+u_n2", corpus["u_n1"]["rule"], corpus["u_n2"]["rule"], evaluator
        ),
    }
    cross_representation = _cross_representation_test(evaluator)
    return {
        "protocol": "phase3-distillation",
        "phase1_closed": True,
        "phase2_closed": True,
        "full_repository_ingestion": False,
        "corpus": corpus,
        "discovery_from_A_B": discovery,
        "held_out_C": held_out,
        "controlled_controls": controls,
        "cross_representation": cross_representation,
        "signals_kept_separate": True,
        "gate_answers": {
            "derive_G_without_being_told": discovery["useful_abstraction"],
            "reconstruct_A_B_from_G_residue": discovery["candidate_G"]["reconstruction_left"] and discovery["candidate_G"]["reconstruction_right"],
            "reject_misleading_similarity": (
                not controls["similar_surface_different_behavior"]["useful_abstraction"]
                and not controls["no_useful_shared_abstraction"]["useful_abstraction"]
            ),
            "held_out_C_has_measurable_value": (
                held_out["reconstruction"]
                and held_out["description_advantage"]
                and held_out["predicts_property"]
            ),
            "G_survives_surface_representation_change": cross_representation["G_survives_surface_change_after_represented_normalization"],
            "useful_signal": {
                "structure": True,
                "semantics": discovery["candidate_G"]["semantic_equivalence"],
                "compression": discovery["candidate_G"]["compression_gain"] > 0,
                "combination_required": True,
            },
            "residue": {
                "A": discovery["candidate_G"]["residue_left"],
                "B": discovery["candidate_G"]["residue_right"],
                "C": held_out["residue"],
                "meaning": "surface path/name differences not explained by shared program skeleton",
            },
        },
        "gate": {
            "decision": "A" if (
                discovery["useful_abstraction"]
                and held_out["reconstruction"]
                and held_out["description_advantage"]
                and held_out["predicts_property"]
                and cross_representation["G_survives_surface_change_after_represented_normalization"]
            ) else "B",
            "full_repository_ingestion_started": False,
            "unresolved_counterexample": None,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MAT-SI Phase 3 distillation")
    parser.add_argument("--json-out", type=Path, default=Path("results/phase3-distillation-results.json"))
    args = parser.parse_args(argv)
    result = run_phase3()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("derive_G_without_being_told:", result["gate_answers"]["derive_G_without_being_told"])
    print("held_out_C_has_measurable_value:", result["gate_answers"]["held_out_C_has_measurable_value"])
    print("cross_representation:", result["gate_answers"]["G_survives_surface_representation_change"])
    print("phase3_gate.decision:", result["gate"]["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
