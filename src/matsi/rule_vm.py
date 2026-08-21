"""A minimal data-driven evaluator used for the Phase 1 v3 attacks."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import inspect
import json
from typing import Any


def _get_path(value: Any, path: list[str | int]) -> Any:
    current = value
    for segment in path:
        current = current[segment]
    return current


def _set_path(value: Any, path: list[str | int], replacement: Any) -> None:
    if not path:
        raise ValueError("set requires a non-empty path")
    current = value
    for segment in path[:-1]:
        current = current[segment]
    current[path[-1]] = replacement


def _execute(rule: dict[str, Any], input_value: Any) -> Any:
    """Execute an ordinary-data stack program.

    The instruction vocabulary is fixed once in this evaluator. The experiment
    changes only rule data, including an opcode already understood by this same
    loop; no Python branch is added between rule variants.
    """

    working = deepcopy(input_value)
    stack: list[Any] = []
    for instruction in rule["program"]:
        operation = instruction["op"]
        if operation == "get":
            stack.append(_get_path(working, list(instruction["path"])))
        elif operation == "const":
            stack.append(instruction["value"])
        elif operation == "add":
            right = stack.pop()
            left = stack.pop()
            stack.append(left + right)
        elif operation == "mul":
            right = stack.pop()
            left = stack.pop()
            stack.append(left * right)
        elif operation == "set":
            replacement = stack.pop()
            _set_path(working, list(instruction["path"]), replacement)
            stack.append(working)
        elif operation == "return":
            return stack[-1] if stack else working
        else:
            raise ValueError(f"unknown represented instruction: {operation}")
    return stack[-1] if stack else working


class RepresentedRuleEvaluator:
    """Interpret rules and inputs after reading both from a substrate."""

    name = "represented_rule_vm"

    def source_hash(self) -> str:
        source = inspect.getsource(_execute).encode("utf-8")
        return hashlib.sha256(source).hexdigest()

    def evaluate(self, substrate: Any, rule_representation: Any, input_representation: Any) -> Any:
        rule = substrate.decode(rule_representation)
        input_value = substrate.decode(input_representation)
        output = _execute(rule, input_value)
        return substrate.encode(output)

    def apply_transformation(self, substrate: Any, transformation_representation: Any, input_representation: Any) -> Any:
        transformation = substrate.decode(transformation_representation)
        rule_representation = substrate.encode(transformation["rule"])
        return self.evaluate(substrate, rule_representation, input_representation)

    def apply_composition(self, substrate: Any, composition_representation: Any, input_representation: Any) -> Any:
        composition = substrate.decode(composition_representation)
        current = input_representation
        for transformation in composition["steps"]:
            current = self.apply_transformation(substrate, substrate.encode(transformation), current)
        return current


def rule_a() -> dict[str, Any]:
    return {
        "kind": "rule",
        "name": "rule_A",
        "program": [
            {"op": "get", "path": ["value"]},
            {"op": "const", "value": 1},
            {"op": "add"},
            {"op": "return"},
        ],
    }


def rule_b_from_a() -> dict[str, Any]:
    result = deepcopy(rule_a())
    result["name"] = "rule_B"
    result["program"][1]["value"] = 2
    result["program"][2]["op"] = "mul"
    return result


def rule_modifier() -> dict[str, Any]:
    return {
        "kind": "rule",
        "name": "modify_rule_A_to_B",
        "program": [
            {"op": "const", "value": 2},
            {"op": "set", "path": ["program", 1, "value"]},
            {"op": "const", "value": "mul"},
            {"op": "set", "path": ["program", 2, "op"]},
            {"op": "const", "value": "rule_B"},
            {"op": "set", "path": ["name"]},
            {"op": "return"},
        ],
    }


def transformation_add_one() -> dict[str, Any]:
    rule = {
        "kind": "rule",
        "name": "add_one_record",
        "program": [
            {"op": "get", "path": ["value"]},
            {"op": "const", "value": 1},
            {"op": "add"},
            {"op": "set", "path": ["value"]},
            {"op": "return"},
        ],
    }
    return {
        "kind": "transformation",
        "name": "add_one",
        "rule": rule,
        "provenance": {"source": "represented-rule-vm", "operation": "add"},
    }


def transformation_double() -> dict[str, Any]:
    rule = {
        "kind": "rule",
        "name": "double_record",
        "program": [
            {"op": "get", "path": ["value"]},
            {"op": "const", "value": 2},
            {"op": "mul"},
            {"op": "set", "path": ["value"]},
            {"op": "return"},
        ],
    }
    return {
        "kind": "transformation",
        "name": "double",
        "rule": rule,
        "provenance": {"source": "represented-rule-vm", "operation": "multiply"},
    }


def ordinary_data(value: Any) -> bool:
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return False
    return True
