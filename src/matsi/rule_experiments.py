"""Protocol v3 experiments for represented execution and U transformations."""

from __future__ import annotations

from typing import Any, Iterable

from .metrics import measure_call
from .rule_vm import (
    RepresentedRuleEvaluator,
    ordinary_data,
    rule_a,
    rule_b_from_a,
    rule_modifier,
    transformation_add_one,
    transformation_double,
)


def run_rule_control(kernels: Iterable[Any]) -> dict[str, Any]:
    rows = []
    evaluator = RepresentedRuleEvaluator()
    source_hash = evaluator.source_hash()
    input_value = {"value": 3}
    for kernel in kernels:
        input_representation = kernel.encode(input_value)
        rule_a_value = rule_a()
        rule_b_value = rule_b_from_a()
        rule_a_representation = kernel.encode(rule_a_value)
        rule_b_representation = kernel.encode(rule_b_value)
        modifier_representation = kernel.encode(rule_modifier())

        output_a_representation, runtime_a = measure_call(
            lambda: evaluator.evaluate(kernel, rule_a_representation, input_representation), repeats=3
        )
        output_b_representation, runtime_b = measure_call(
            lambda: evaluator.evaluate(kernel, rule_b_representation, input_representation), repeats=3
        )
        modified_rule_representation, runtime_modify = measure_call(
            lambda: evaluator.evaluate(kernel, modifier_representation, rule_a_representation), repeats=3
        )
        output_self_representation = evaluator.evaluate(
            kernel, modified_rule_representation, input_representation
        )
        output_a = kernel.decode(output_a_representation)
        output_b = kernel.decode(output_b_representation)
        modified_rule = kernel.decode(modified_rule_representation)
        output_self = kernel.decode(output_self_representation)
        rows.append(
            {
                "candidate": kernel.name,
                "input": input_value,
                "rule_a": rule_a_value,
                "rule_b": rule_b_value,
                "output_a": output_a,
                "output_b": output_b,
                "modified_rule": modified_rule,
                "output_after_self_modification": output_self,
                "rule_a_round_trip": kernel.decode(rule_a_representation) == rule_a_value,
                "rule_b_round_trip": kernel.decode(rule_b_representation) == rule_b_value,
                "rule_change_changes_behavior": output_a != output_b,
                "self_modifier_changes_rule": modified_rule == rule_b_value,
                "self_modifier_changes_behavior": output_a != output_self,
                "same_evaluator_source_hash": evaluator.source_hash() == source_hash,
                "evaluator_source_hash": source_hash,
                "runtime": {
                    "rule_a": runtime_a.as_dict(),
                    "rule_b": runtime_b.as_dict(),
                    "self_modifier": runtime_modify.as_dict(),
                },
            }
        )
    return {
        "experiment": "represented_rule_controls_execution",
        "evaluator": evaluator.name,
        "instruction_vocabulary": ["get", "const", "add", "mul", "set", "return"],
        "no_host_branch_added_between_variants": True,
        "rows": rows,
        "all_pass": all(
            row["rule_change_changes_behavior"]
            and row["self_modifier_changes_rule"]
            and row["self_modifier_changes_behavior"]
            and row["same_evaluator_source_hash"]
            for row in rows
        ),
    }


def transformation_universe() -> dict[str, Any]:
    value = {"value": 3}
    t1 = transformation_add_one()
    t2 = transformation_double()
    composition = {
        "kind": "composition",
        "name": "double_after_add_one",
        "steps": [t1, t2],
        "provenance": {"source": "protocol-v3", "relation": "T2(T1(x))"},
    }
    history = [
        {"step": 1, "input": value, "transformation": t1, "output": {"value": 4}},
        {"step": 2, "input": {"value": 4}, "transformation": t2, "output": {"value": 8}},
    ]
    return {
        "value": value,
        "rules": [t1["rule"], t2["rule"]],
        "transformations": [t1, t2],
        "composition": composition,
        "history": history,
        "cost": {"unit": "abstract", "encode": 1, "evaluate": 1, "query": 1},
        "provenance": {"source": "phase1-v3", "claim": "ordinary data only"},
    }


def run_transformation_universe(kernels: Iterable[Any]) -> dict[str, Any]:
    rows = []
    evaluator = RepresentedRuleEvaluator()
    universe = transformation_universe()
    for kernel in kernels:
        universe_representation = kernel.encode(universe)
        composition_representation = kernel.encode(universe["composition"])
        input_representation = kernel.encode(universe["value"])
        result_representation, runtime = measure_call(
            lambda: evaluator.apply_composition(
                kernel, composition_representation, input_representation
            ),
            repeats=3,
        )
        result = kernel.decode(result_representation)
        decoded_universe = kernel.decode(universe_representation)
        rows.append(
            {
                "candidate": kernel.name,
                "universe_round_trip": decoded_universe == universe,
                "composition_round_trip": kernel.decode(composition_representation) == universe["composition"],
                "composition_result": result,
                "composition_expected": {"value": 8},
                "composition_ok": result == {"value": 8},
                "ordinary_data_only": ordinary_data(decoded_universe),
                "universe_bytes": kernel.size_bytes(universe_representation),
                "composition_bytes": kernel.size_bytes(composition_representation),
                "runtime": runtime.as_dict(),
            }
        )
    return {
        "experiment": "transformations_as_ordinary_U",
        "universe": universe,
        "rows": rows,
        "all_pass": all(
            row["universe_round_trip"]
            and row["composition_round_trip"]
            and row["composition_ok"]
            and row["ordinary_data_only"]
            for row in rows
        ),
    }
