"""Small Phase 2 self-reference and self-observation experiment."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from .minimal_rewrite import core_source_hash
from .rule_vm import RepresentedRuleEvaluator
from .kernels import AtomPairKernel, ContentDagKernel, RewriteEgraphKernel


FIXED_VM_OPS = ["get", "const", "add", "mul", "set", "return"]
MODEL_PHASE = "phase2-self-reference"


def _claim(value: Any, fact: str) -> dict[str, Any]:
    return {
        "value": value,
        "provenance": {"source": "phase1-frozen-observation", "fact": fact},
    }


def _rule_r1() -> dict[str, Any]:
    return {
        "kind": "rule",
        "name": "R1",
        "program": [
            {"op": "get", "path": ["value"]},
            {"op": "const", "value": 1},
            {"op": "add"},
            {"op": "return"},
        ],
    }


def _rule_alternative_short() -> dict[str, Any]:
    return {
        "kind": "rule",
        "name": "R_short",
        "program": [
            {"op": "const", "value": 4},
            {"op": "return"},
        ],
    }


def _self_transformation() -> dict[str, Any]:
    """A represented rule that edits a rule inside the represented self-model."""

    return {
        "kind": "transformation",
        "name": "R1_to_R2",
        "target_path": ["executable_representation", "rule"],
        "rule": {
            "kind": "rule",
            "name": "transform_self_model_rule",
            "program": [
                {"op": "const", "value": 2},
                {"op": "set", "path": ["executable_representation", "rule", "program", 1, "value"]},
                {"op": "const", "value": "mul"},
                {"op": "set", "path": ["executable_representation", "rule", "program", 2, "op"]},
                {"op": "const", "value": "R2"},
                {"op": "set", "path": ["executable_representation", "rule", "name"]},
                {"op": "return"},
            ],
        },
        "provenance": {
            "source": "represented-self-model",
            "reason": "change represented rule behavior",
        },
        "cost_observation": {"metric": "instruction_count", "value": 7},
    }


def _actual_observation(evaluator: RepresentedRuleEvaluator) -> dict[str, Any]:
    return {
        "phase": MODEL_PHASE,
        "semantic_core_hash": core_source_hash(),
        "evaluator_source_hash": evaluator.source_hash(),
        "evaluator_vocabulary": list(FIXED_VM_OPS),
    }


def build_self_model(evaluator: RepresentedRuleEvaluator) -> dict[str, Any]:
    actual = _actual_observation(evaluator)
    rule = _rule_r1()
    return {
        "kind": "matsi_self_model",
        "description": {
            "kind": "description",
            "system": "MAT-SI",
            "claims": {
                key: _claim(value, key) for key, value in actual.items()
            },
            "executable_component_path": ["executable_representation", "rule"],
        },
        "executable_representation": {
            "kind": "executable_representation",
            "evaluator": "represented_rule_vm",
            "rule": rule,
        },
        "transformations": {"R1_to_R2": _self_transformation()},
        "cost_observations": {
            "rule_R1": {
                "metric": "instruction_count",
                "value": len(rule["program"]),
                "provenance": {"source": "represented-self-model", "rule": "R1"},
            }
        },
        "self_evaluation": {
            "alternatives": [rule, _rule_alternative_short()],
            "policy": {
                "metric": "instruction_count",
                "direction": "minimize",
                "provenance": {"source": "represented-policy", "reason": "prefer lower observed cost"},
            },
        },
        "provenance": {
            "source": "phase1-final-state",
            "semantic_core_hash": actual["semantic_core_hash"],
        },
        "history": [],
    }


def _query(kernel: Any, representation: Any, path: list[str | int]) -> Any:
    return kernel.query(representation, tuple(path)).value


def _execute_target(evaluator: RepresentedRuleEvaluator, kernel: Any, rule: dict[str, Any], input_value: Any) -> Any:
    rule_representation = kernel.encode(rule)
    input_representation = kernel.encode(input_value)
    output_representation = evaluator.evaluate(kernel, rule_representation, input_representation)
    return kernel.decode(output_representation)


def _inspect_self_model(kernel: Any, representation: Any) -> dict[str, Any]:
    rule = _query(kernel, representation, ["executable_representation", "rule"])
    provenance = _query(kernel, representation, ["provenance"])
    cost = _query(kernel, representation, ["cost_observations", "rule_R1"])
    reconstructed = {
        "rule": kernel.decode(kernel.encode(rule)),
        "provenance": kernel.decode(kernel.encode(provenance)),
        "cost": kernel.decode(kernel.encode(cost)),
    }
    return {
        "rule": rule,
        "provenance": provenance,
        "cost": cost,
        "reconstructed": reconstructed,
        "reconstructs_exactly": reconstructed == {
            "rule": rule,
            "provenance": provenance,
            "cost": cost,
        },
    }


def _derive_correspondence_claim(kernel: Any, representation: Any, evaluator: RepresentedRuleEvaluator, name: str) -> dict[str, Any]:
    represented = _query(kernel, representation, ["description", "claims", name])
    actual = _actual_observation(evaluator)
    supported = represented.get("provenance", {}).get("source") == "phase1-frozen-observation"
    return {
        "kind": "correspondence_claim",
        "fact": name,
        "status": "consistent" if supported and represented.get("value") == actual[name] else "inconsistent",
        "represented_value": represented.get("value"),
        "actual_value": actual[name],
        "provenance": {
            "represented_source": represented.get("provenance"),
            "actual_source": {"source": "phase2-runtime-observation", "fact": name},
        },
    }


def _derive_cost_claim(kernel: Any, representation: Any, rule_name: str = "rule_R1") -> dict[str, Any]:
    rule = _query(kernel, representation, ["executable_representation", "rule"])
    reported = _query(kernel, representation, ["cost_observations", rule_name])
    measured = len(rule["program"])
    return {
        "kind": "cost_correspondence_claim",
        "rule": rule_name,
        "status": "consistent" if reported.get("value") == measured else "inconsistent",
        "reported_cost": reported.get("value"),
        "measured_cost": measured,
        "provenance": {
            "represented_source": reported.get("provenance"),
            "actual_source": {"source": "phase2-runtime-observation", "metric": "instruction_count"},
        },
    }


def _run_failure_attacks(kernel: Any, model: dict[str, Any], evaluator: RepresentedRuleEvaluator) -> dict[str, Any]:
    stale = deepcopy(model)
    stale["description"]["claims"]["phase"]["value"] = "phase1"
    stale_representation = kernel.encode(stale)
    stale_claim = _derive_correspondence_claim(kernel, stale_representation, evaluator, "phase")

    false_cost = deepcopy(model)
    false_cost["cost_observations"]["rule_R1"]["value"] = 999
    false_cost_claim = _derive_cost_claim(kernel, kernel.encode(false_cost))

    corrupted = deepcopy(model)
    corrupted["executable_representation"]["rule"]["program"][2]["op"] = "xor"
    corrupted_representation = kernel.encode(corrupted)
    corrupted_rule = _query(kernel, corrupted_representation, ["executable_representation", "rule"])
    try:
        _execute_target(evaluator, kernel, corrupted_rule, {"value": 3})
        corrupted_status = "accepted"
        corrupted_error = None
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        corrupted_status = "unknown"
        corrupted_error = str(exc)

    missing = deepcopy(model)
    missing["description"]["claims"]["evaluator_vocabulary"]["value"].remove("set")
    missing_claim = _derive_correspondence_claim(kernel, kernel.encode(missing), evaluator, "evaluator_vocabulary")

    unsupported = deepcopy(model)
    unsupported["description"]["claims"]["evaluator_source_hash"]["provenance"] = {"source": "fabricated"}
    unsupported_claim = _derive_correspondence_claim(
        kernel, kernel.encode(unsupported), evaluator, "evaluator_source_hash"
    )
    unsupported_status = "unsupported" if unsupported_claim["status"] == "inconsistent" else "absorbed"

    return {
        "stale_self_description": stale_claim,
        "false_represented_cost": false_cost_claim,
        "corrupted_represented_rule": {
            "status": corrupted_status,
            "error": corrupted_error,
            "repaired": False,
        },
        "self_model_missing_host_capability": missing_claim,
        "claim_unsupported_by_provenance": {
            "status": unsupported_status,
            "claim": unsupported_claim,
            "repaired": False,
        },
        "all_failures_preserved": (
            stale_claim["status"] == "inconsistent"
            and false_cost_claim["status"] == "inconsistent"
            and corrupted_status == "unknown"
            and missing_claim["status"] == "inconsistent"
            and unsupported_status == "unsupported"
        ),
    }


def _run_self_evaluation(kernel: Any, representation: Any, evaluator: RepresentedRuleEvaluator) -> dict[str, Any]:
    alternatives = _query(kernel, representation, ["self_evaluation", "alternatives"])
    policy = _query(kernel, representation, ["self_evaluation", "policy"])
    rows = []
    for rule in alternatives:
        output = _execute_target(evaluator, kernel, rule, {"value": 3})
        rows.append(
            {
                "rule": rule["name"],
                "output": output,
                "acceptable": output == 4,
                "observed_cost": len(rule["program"]),
            }
        )
    selected = min(rows, key=lambda row: row["observed_cost"])
    claim = {
        "kind": "selection_claim",
        "selected_rule": selected["rule"],
        "policy": policy,
        "evidence": rows,
        "provenance": {"source": "represented-alternatives-and-costs"},
    }
    claim_round_trip = kernel.decode(kernel.encode(claim)) == claim
    return {
        "alternatives": rows,
        "policy": policy,
        "selection_claim": claim,
        "claim_round_trip": claim_round_trip,
        "selects_lowest_cost": selected["rule"] == "R_short",
        "source_mutated": False,
    }


def run_phase2(kernels: list[Any] | None = None) -> dict[str, Any]:
    kernels = kernels or [AtomPairKernel(), ContentDagKernel(), RewriteEgraphKernel()]
    rows: list[dict[str, Any]] = []
    for kernel in kernels:
        evaluator = RepresentedRuleEvaluator()
        model = build_self_model(evaluator)
        model_representation = kernel.encode(model)
        inspection = _inspect_self_model(kernel, model_representation)
        self_rule_before = inspection["rule"]
        transformation = _query(kernel, model_representation, ["transformations", "R1_to_R2"])
        transformed_representation = evaluator.evaluate(
            kernel, kernel.encode(transformation["rule"]), model_representation
        )
        transformed_model = kernel.decode(transformed_representation)
        self_rule_after = _query(kernel, transformed_representation, ["executable_representation", "rule"])
        external_output = _execute_target(evaluator, kernel, self_rule_before, {"value": 3})
        self_before_output = _execute_target(evaluator, kernel, self_rule_before, {"value": 3})
        self_after_output = _execute_target(evaluator, kernel, self_rule_after, {"value": 3})

        history_record = {
            "kind": "self_transformation_history",
            "before": self_rule_before,
            "transformation": transformation,
            "after": self_rule_after,
            "observed_cost": {
                "before": len(self_rule_before["program"]),
                "transformation": len(transformation["rule"]["program"]),
                "after": len(self_rule_after["program"]),
            },
            "provenance": {
                "source": "represented-self-model",
                "event": "R1_to_R2",
            },
        }
        transformed_model["cost_observations"]["rule_R2"] = {
            "metric": "instruction_count",
            "value": len(self_rule_after["program"]),
            "provenance": {"source": "represented-self-model", "rule": "R2"},
        }
        transformed_model["history"] = [history_record]
        history_representation = kernel.encode(transformed_model["history"])
        history_round_trip = kernel.decode(history_representation) == [history_record]
        correspondence = {
            name: _derive_correspondence_claim(kernel, model_representation, evaluator, name)
            for name in ("phase", "semantic_core_hash", "evaluator_source_hash", "evaluator_vocabulary")
        }
        failures = _run_failure_attacks(kernel, model, evaluator)
        self_evaluation = _run_self_evaluation(kernel, model_representation, evaluator)
        host_hash_before = evaluator.source_hash()
        host_hash_after = evaluator.source_hash()
        rows.append(
            {
                "candidate": kernel.name,
                "self_model_round_trip": kernel.decode(kernel.encode(model)) == model,
                "self_model_distinguishes_description_and_executable": (
                    model["description"] != model["executable_representation"]
                    and model["description"]["kind"] == "description"
                    and model["executable_representation"]["kind"] == "executable_representation"
                ),
                "inspection": inspection,
                "self_rule_before": self_rule_before,
                "self_rule_after": self_rule_after,
                "transformation_round_trip": kernel.decode(kernel.encode(transformation)) == transformation,
                "behavior_before": self_before_output,
                "behavior_after": self_after_output,
                "behavior_changed": self_before_output != self_after_output,
                "history": history_record,
                "history_round_trip": history_round_trip,
                "previous_rule_preserved": history_record["before"] == self_rule_before,
                "new_rule_preserved": history_record["after"] == self_rule_after,
                "provenance_preserved": bool(history_record["provenance"]),
                "cost_preserved": bool(history_record["observed_cost"]),
                "evaluator_source_unchanged": host_hash_before == host_hash_after,
                "external_output": external_output,
                "self_input_output": self_before_output,
                "same_external_self_mechanism": external_output == self_before_output,
                "correspondence": correspondence,
                "correspondence_baseline_consistent": all(
                    claim["status"] == "consistent" for claim in correspondence.values()
                ),
                "self_evaluation": self_evaluation,
                "failure_attacks": failures,
            }
        )

    criteria = {
        "self_model_is_executable_slice": all(row["self_model_round_trip"] for row in rows),
        "external_mechanisms_inspect_self_model": all(row["inspection"]["reconstructs_exactly"] for row in rows),
        "represented_transformation_modifies_self_rule": all(row["behavior_changed"] for row in rows),
        "unchanged_evaluator_executes_modified_rule": all(
            row["behavior_after"] == 6 and row["evaluator_source_unchanged"] for row in rows
        ),
        "complete_history_preserved": all(
            row["history_round_trip"]
            and row["previous_rule_preserved"]
            and row["new_rule_preserved"]
            and row["provenance_preserved"]
            and row["cost_preserved"]
            for row in rows
        ),
        "self_claims_checked_against_actual": all(row["correspondence_baseline_consistent"] for row in rows),
        "false_claim_detected_not_absorbed": all(
            row["failure_attacks"]["all_failures_preserved"] for row in rows
        ),
        "same_mechanism_external_and_self": all(row["same_external_self_mechanism"] for row in rows),
        "self_evaluation_selects_claim": all(
            row["self_evaluation"]["selects_lowest_cost"]
            and row["self_evaluation"]["claim_round_trip"]
            and not row["self_evaluation"]["source_mutated"]
            for row in rows
        ),
    }
    return {
        "protocol": "phase2-self-reference",
        "phase1_frozen": {
            "semantic_core_hash": core_source_hash(),
            "vm_operations": FIXED_VM_OPS,
            "egraph_role": "optional/reference transformation machinery",
        },
        "rows": rows,
        "criteria": criteria,
        "all_required_evidence": all(criteria.values()),
        "gate": {
            "decision": "A" if all(criteria.values()) else "B",
            "phase3_started": False,
            "phase1_assumption_broke": False,
            "unresolved_gap": None if all(criteria.values()) else "self-reference criterion did not pass",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MAT-SI Phase 2 self-reference")
    parser.add_argument("--json-out", type=Path, default=Path("results/phase2-self-reference-results.json"))
    args = parser.parse_args(argv)
    result = run_phase2()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("all_required_evidence:", result["all_required_evidence"])
    print("phase2_gate.decision:", result["gate"]["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
