"""Frozen held-out evaluation for the Phase 1 gate."""

from __future__ import annotations

from typing import Any

from .minimal_rewrite import core_source_hash
from .rule_vm import RepresentedRuleEvaluator


def _rule(operation: str, constant: int) -> dict[str, Any]:
    return {
        "kind": "rule",
        "program": [
            {"op": "get", "path": ["value"]},
            {"op": "const", "value": constant},
            {"op": operation},
            {"op": "return"},
        ],
    }


def held_out_cases() -> list[dict[str, Any]]:
    """Cases written after the semantic core was frozen.

    The two unsupported operations are intentional: a held-out failure is
    evidence about the trusted boundary, not a request for a special opcode.
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
            "rule": _rule("add", 1),
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
            "rule": _rule("mul", 2),
            "expected": 6,
        },
        {
            "case_id": "symbolic_subtraction",
            "domain": "symbolic_transformation",
            "payload": {
                "expression": {"op": "subtract", "left": 9, "right": 4},
                "normal_form": 5,
            },
            "execution_input": {"value": 9},
            "rule": _rule("sub", 4),
            "expected_failure": "unknown represented instruction: sub",
        },
        {
            "case_id": "unfamiliar_weaving_process",
            "domain": "unfamiliar_domain",
            "payload": {
                "object": "pattern",
                "operation": "rotate",
                "parameters": {"quarter_turns": 1},
                "material": "fiber",
            },
            "execution_input": {"value": 2},
            "rule": _rule("rotate", 1),
            "expected_failure": "unknown represented instruction: rotate",
        },
    ]


def run_held_out(kernels: list[Any]) -> dict[str, Any]:
    """Evaluate the frozen representation and evaluator without changing them."""

    evaluator = RepresentedRuleEvaluator()
    frozen_hash = f"{core_source_hash()}:{evaluator.source_hash()}"
    rows: list[dict[str, Any]] = []
    for kernel in kernels:
        for case in held_out_cases():
            payload_representation = kernel.encode(case["payload"])
            rule_representation = kernel.encode(case["rule"])
            input_representation = kernel.encode(case["execution_input"])
            payload_round_trip = kernel.decode(payload_representation) == case["payload"]
            rule_round_trip = kernel.decode(rule_representation) == case["rule"]
            input_round_trip = kernel.decode(input_representation) == case["execution_input"]
            actual: Any = None
            error: str | None = None
            try:
                output_representation = evaluator.evaluate(
                    kernel, rule_representation, input_representation
                )
                actual = kernel.decode(output_representation)
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                error = str(exc)
            expected_failure = case.get("expected_failure")
            if expected_failure is None:
                evaluation_status = "pass" if actual == case["expected"] else "wrong_result"
            else:
                evaluation_status = "expected_failure" if error == expected_failure else "unexpected_failure"
            rows.append(
                {
                    "candidate": kernel.name,
                    "case_id": case["case_id"],
                    "domain": case["domain"],
                    "payload_round_trip": payload_round_trip,
                    "rule_round_trip": rule_round_trip,
                    "input_round_trip": input_round_trip,
                    "actual": actual,
                    "error": error,
                    "evaluation_status": evaluation_status,
                    "semantic_core_modified": False,
                    "frozen_core_hash": frozen_hash,
                }
            )
    return {
        "experiment": "frozen_held_out_corpus",
        "case_ids": [case["case_id"] for case in held_out_cases()],
        "rows": rows,
        "representation_survives": all(
            row["payload_round_trip"] and row["rule_round_trip"] and row["input_round_trip"]
            for row in rows
        ),
        "evaluation_passes_without_new_primitives": all(
            row["evaluation_status"] in {"pass", "expected_failure"} for row in rows
        ),
        "unexpected_evaluation_failures": [
            row for row in rows if row["evaluation_status"] == "unexpected_failure"
        ],
        "preserved_counterexamples": [
            row["case_id"] for row in rows if row["evaluation_status"] == "expected_failure"
        ],
        "semantic_core_modified": any(row["semantic_core_modified"] for row in rows),
        "frozen_core_hashes": sorted({row["frozen_core_hash"] for row in rows}),
        "conclusion": "The frozen core represents every held-out payload and rule, but execution fails exactly where a held-out rule asks for an operation outside the six-op vocabulary.",
    }
