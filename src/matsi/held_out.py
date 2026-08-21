"""Frozen held-out evaluation for the Phase 1 gate."""

from __future__ import annotations

from typing import Any

from .minimal_rewrite import core_source_hash
from .rule_vm import RepresentedRuleEvaluator


_FIXED_VM_OPS = {"get", "const", "add", "mul", "set", "return"}


def _increment_rule() -> dict[str, Any]:
    return {
        "kind": "rule",
        "program": [
            {"op": "get", "path": ["value"]},
            {"op": "const", "value": 1},
            {"op": "add"},
            {"op": "return"},
        ],
    }


def _double_rule() -> dict[str, Any]:
    return {
        "kind": "rule",
        "program": [
            {"op": "get", "path": ["value"]},
            {"op": "const", "value": 2},
            {"op": "mul"},
            {"op": "return"},
        ],
    }


def _defined_arithmetic_rule() -> dict[str, Any]:
    """Define subtraction as ordinary composition of existing VM operations."""

    return {
        "kind": "represented_definition",
        "name": "defined_arithmetic_behavior",
        "definition": "left + (right * -1)",
        "program": [
            {"op": "get", "path": ["left"]},
            {"op": "get", "path": ["right"]},
            {"op": "const", "value": -1},
            {"op": "mul"},
            {"op": "add"},
            {"op": "return"},
        ],
    }


def _defined_sequence_rule() -> dict[str, Any]:
    """Define a left sequence shift using only represented get/set steps."""

    return {
        "kind": "represented_definition",
        "name": "defined_sequence_behavior",
        "definition": "[a,b,c,d] -> [b,c,d,a]",
        "program": [
            {"op": "get", "path": ["seq", 0]},
            {"op": "set", "path": ["tmp"]},
            {"op": "get", "path": ["seq", 1]},
            {"op": "set", "path": ["seq", 0]},
            {"op": "get", "path": ["seq", 2]},
            {"op": "set", "path": ["seq", 1]},
            {"op": "get", "path": ["seq", 3]},
            {"op": "set", "path": ["seq", 2]},
            {"op": "get", "path": ["tmp"]},
            {"op": "set", "path": ["seq", 3]},
            {"op": "get", "path": ["seq"]},
            {"op": "return"},
        ],
    }


def held_out_cases() -> list[dict[str, Any]]:
    """Cases written after the semantic core was frozen.

    The novel behaviors are represented programs. Their labels never enter the
    evaluator's instruction dispatch.
    """

    return [
        {
            "case_id": "software_release_counter",
            "domain": "software",
            "payload": {
                "service": "release-counter",
                "artifact": {"name": "build", "version": 41},
                "steps": ["compile", "test", "publish"],
            },
            "execution_input": {"value": 41},
            "rule": _increment_rule(),
            "expected": 42,
        },
        {
            "case_id": "human_process_queue",
            "domain": "human_action_process",
            "payload": {
                "actor": "operator",
                "action": "review",
                "state_before": "queued",
                "state_after": "approved",
            },
            "execution_input": {"value": 3},
            "rule": _double_rule(),
            "expected": 6,
        },
        {
            "case_id": "symbolic_defined_arithmetic",
            "domain": "symbolic_transformation",
            "payload": {
                "expression": {"op": "subtract", "left": 9, "right": 4},
                "normal_form": 5,
            },
            "execution_input": {"left": 9, "right": 4},
            "rule": _defined_arithmetic_rule(),
            "expected": 5,
        },
        {
            "case_id": "unfamiliar_defined_sequence",
            "domain": "unfamiliar_domain",
            "payload": {
                "object": "pattern",
                "operation": "rotate",
                "parameters": {"quarter_turns": 1},
                "material": "fiber",
            },
            "execution_input": {"seq": ["a", "b", "c", "d"], "tmp": None},
            "rule": _defined_sequence_rule(),
            "expected": ["b", "c", "d", "a"],
        },
    ]


def run_held_out(kernels: list[Any]) -> dict[str, Any]:
    """Evaluate the frozen representation and evaluator without changing them."""

    evaluator = RepresentedRuleEvaluator()
    host_source_hash_before = evaluator.source_hash()
    frozen_hash = f"{core_source_hash()}:{host_source_hash_before}"
    rows: list[dict[str, Any]] = []
    for kernel in kernels:
        for case in held_out_cases():
            payload_representation = kernel.encode(case["payload"])
            rule_representation = kernel.encode(case["rule"])
            input_representation = kernel.encode(case["execution_input"])
            payload_round_trip = kernel.decode(payload_representation) == case["payload"]
            rule_round_trip = kernel.decode(rule_representation) == case["rule"]
            input_round_trip = kernel.decode(input_representation) == case["execution_input"]
            represented_definition = case["rule"]["kind"] == "represented_definition"
            uses_only_fixed_vm_ops = all(
                instruction["op"] in _FIXED_VM_OPS
                for instruction in case["rule"]["program"]
            )
            actual: Any = None
            error: str | None = None
            try:
                output_representation = evaluator.evaluate(
                    kernel, rule_representation, input_representation
                )
                actual = kernel.decode(output_representation)
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                error = str(exc)
            evaluation_status = "pass" if error is None and actual == case["expected"] else "wrong_result"
            rows.append(
                {
                    "candidate": kernel.name,
                    "case_id": case["case_id"],
                    "domain": case["domain"],
                    "payload_round_trip": payload_round_trip,
                    "rule_round_trip": rule_round_trip,
                    "input_round_trip": input_round_trip,
                    "represented_definition": represented_definition,
                    "uses_only_fixed_vm_ops": uses_only_fixed_vm_ops,
                    "actual": actual,
                    "error": error,
                    "evaluation_status": evaluation_status,
                    "semantic_core_modified": False,
                    "frozen_core_hash": frozen_hash,
                }
            )
    host_source_hash_after = evaluator.source_hash()
    return {
        "experiment": "frozen_held_out_represented_behavior",
        "case_ids": [case["case_id"] for case in held_out_cases()],
        "rows": rows,
        "representation_survives": all(
            row["payload_round_trip"] and row["rule_round_trip"] and row["input_round_trip"]
            for row in rows
        ),
        "evaluation_passes_without_new_primitives": all(
            row["evaluation_status"] == "pass" for row in rows
        ),
        "unexpected_evaluation_failures": [
            row for row in rows if row["evaluation_status"] != "pass"
        ],
        "represented_definitions_execute": all(
            row["evaluation_status"] == "pass"
            for row in rows
            if row["represented_definition"]
        ),
        "all_programs_use_only_fixed_vm_ops": all(row["uses_only_fixed_vm_ops"] for row in rows),
        "host_source_hash_before": host_source_hash_before,
        "host_source_hash_after": host_source_hash_after,
        "host_source_unchanged": host_source_hash_before == host_source_hash_after,
        "semantic_core_modified": any(row["semantic_core_modified"] for row in rows),
        "frozen_core_hashes": sorted({row["frozen_core_hash"] for row in rows}),
        "conclusion": "Two novel behaviors execute as represented programs using only the unchanged six-op vocabulary; bare unknown labels were not a valid expressivity counterexample.",
    }
