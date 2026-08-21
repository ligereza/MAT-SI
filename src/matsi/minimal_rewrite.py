"""Smallest generic pattern/match/substitute/rewrite trial for the Phase 1 gate."""

from __future__ import annotations

import hashlib
import inspect
from typing import Any


def variable(name: str) -> dict[str, str]:
    return {"$var": name}


def match(pattern: Any, value: Any, bindings: dict[str, Any] | None = None) -> dict[str, Any] | None:
    bindings = {} if bindings is None else bindings
    if isinstance(pattern, dict) and set(pattern) == {"$var"}:
        name = pattern["$var"]
        if name in bindings and bindings[name] != value:
            return None
        bindings[name] = value
        return bindings
    if isinstance(pattern, dict):
        if not isinstance(value, dict) or set(pattern) != set(value):
            return None
        for key in pattern:
            if match(pattern[key], value[key], bindings) is None:
                return None
        return bindings
    if isinstance(pattern, list):
        if not isinstance(value, list) or len(pattern) != len(value):
            return None
        for pattern_item, value_item in zip(pattern, value):
            if match(pattern_item, value_item, bindings) is None:
                return None
        return bindings
    return bindings if pattern == value else None


def substitute(template: Any, bindings: dict[str, Any]) -> Any:
    if isinstance(template, dict) and set(template) == {"$var"}:
        return bindings[template["$var"]]
    if isinstance(template, dict):
        return {key: substitute(value, bindings) for key, value in template.items()}
    if isinstance(template, list):
        return [substitute(item, bindings) for item in template]
    return template


def rewrite(rule: dict[str, Any], value: Any) -> Any:
    bindings = match(rule["pattern"], value)
    if bindings is not None:
        return substitute(rule["replacement"], bindings)
    if isinstance(value, dict):
        return {key: rewrite(rule, item) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite(rule, item) for item in value]
    return value


def core_source_hash() -> str:
    source = "\n".join(inspect.getsource(function) for function in (match, substitute, rewrite))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def trial_rules() -> list[dict[str, Any]]:
    return [
        {
            "name": "rule_A_increment_literal",
            "pattern": {"op": "add", "left": 3, "right": 1},
            "replacement": 4,
        },
        {
            "name": "rule_B_double_literal",
            "pattern": {"op": "mul", "left": 3, "right": 2},
            "replacement": 6,
        },
        {
            "name": "rename_structural_field",
            "pattern": {"name": "old", "value": variable("x")},
            "replacement": {"name": "new", "value": variable("x")},
        },
    ]


def run_minimum_core_trial(kernels: list[Any]) -> dict[str, Any]:
    inputs = [
        {"id": "rule_A_increment_literal", "value": {"op": "add", "left": 3, "right": 1}, "expected": 4},
        {"id": "rule_B_double_literal", "value": {"op": "mul", "left": 3, "right": 2}, "expected": 6},
        {"id": "rename_structural_field", "value": {"name": "old", "value": "payload"}, "expected": {"name": "new", "value": "payload"}},
    ]
    rules = trial_rules()
    source_hash = core_source_hash()
    rows = []
    for kernel in kernels:
        for rule, case in zip(rules, inputs):
            rule_representation = kernel.encode(rule)
            input_representation = kernel.encode(case["value"])
            decoded_rule = kernel.decode(rule_representation)
            decoded_input = kernel.decode(input_representation)
            output = rewrite(decoded_rule, decoded_input)
            rows.append(
                {
                    "candidate": kernel.name,
                    "case_id": case["id"],
                    "output": output,
                    "expected": case["expected"],
                    "fidelity": output == case["expected"],
                    "core_source_hash": source_hash,
                    "rule_round_trip": decoded_rule == rule,
                    "input_round_trip": decoded_input == case["value"],
                }
            )
    return {
        "experiment": "minimum_trusted_semantic_core",
        "core": ["atom equality", "generic match", "generic substitute", "generic rewrite"],
        "behavior_specific_python_branches": 0,
        "legacy_vm_opcode_count": 6,
        "represented_rules": rules,
        "rows": rows,
        "all_pass": all(row["fidelity"] and row["rule_round_trip"] for row in rows),
        "same_core_source_hash": len({row["core_source_hash"] for row in rows}) == 1,
        "open_arithmetic_limit": "literal arithmetic instances rewrite successfully; open-ended numeric arithmetic still needs host semantics or an expanding represented rule set",
        "decision": "stop_branch_and_preserve_six_op_vm_for_open_arithmetic",
    }
