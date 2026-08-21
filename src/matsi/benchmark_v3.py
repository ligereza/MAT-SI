"""Phase 1 protocol v3: decompose structure, evaluation, and continuity evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .axis_experiments import run_axis_experiment
from .continuity import run_continuity_analysis
from .host_audit import host_semantics_audit
from .kernels import AtomPairKernel, ContentDagKernel, RewriteEgraphKernel
from .rule_experiments import run_rule_control, run_transformation_universe


def _v2_reference() -> dict[str, Any]:
    path = Path("results/phase1-v2-results.json")
    if not path.exists():
        return {"available": False}
    result = json.loads(path.read_text(encoding="utf-8"))
    repetition = [
        row for row in result["scale_measurements"] if row["shape"] == "repetition"
    ]
    return {
        "available": True,
        "repetition_egraph_locally_dominated_at_all_points": all(
            "rewrite_egraph" not in next(
                item for item in result["pareto_frontier_by_workload"]
                if item["shape"] == row["shape"] and item["size"] == row["size"]
            )["candidates"]
            for row in repetition
        ),
        "global_strict_dominance": result["strict_dominance_across_all_scale_points"],
    }


def _rewrite_verdict(axis: dict[str, Any], v2: dict[str, Any]) -> dict[str, Any]:
    reduction = axis["rewrite_reduction"]
    reduced_rows = [row for row in reduction if row["mechanism"] == "reduced_tree_rewrite"]
    egraph_rows = [row for row in reduction if row["mechanism"] == "rewrite_equality"]
    paired: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in reduction:
        paired.setdefault((row["substrate"], row["shape"], row["size"]), {})[row["mechanism"]] = row
    reduced_faster = sum(
        pair["reduced_tree_rewrite"]["wall_time_ns"] < pair["rewrite_equality"]["wall_time_ns"]
        for pair in paired.values()
    )
    reduced_less_work = sum(
        pair["reduced_tree_rewrite"]["mechanism_cost"] < pair["rewrite_equality"]["mechanism_cost"]
        for pair in paired.values()
    )
    reduced_fidelity = all(row["fidelity"] == 1.0 for row in reduced_rows)
    egraph_fidelity = all(row["fidelity"] == 1.0 for row in egraph_rows)
    return {
        "answer": "C",
        "status": "provisional_phase1_verdict",
        "options": {
            "A_discard_entirely": False,
            "B_use_only_for_equivalence_workloads": True,
            "C_reduce_useful_mechanism_to_simpler_rewrite": True,
            "D_claim_new_primitive": False,
        },
        "evidence": {
            "v2_repetition_dominance": v2,
            "axis_separates_storage_from_evaluation": True,
            "reduced_rewrite_all_fidelity": reduced_fidelity,
            "egraph_all_fidelity": egraph_fidelity,
            "reduction_points": len(reduction),
            "reduction_pairs": len(paired),
            "reduced_rewrite_faster_points": reduced_faster,
            "reduced_rewrite_lower_mechanism_work_points": reduced_less_work,
            "egraph_is_not_treated_as_universal_U": True,
        },
        "interpretation": "The useful mechanism is generic represented rewriting; the full e-graph remains an optional equality mechanism for equivalence workloads, not a universal substrate. No final architecture is selected.",
    }


def run_v3() -> dict[str, Any]:
    kernels = [AtomPairKernel(), ContentDagKernel(), RewriteEgraphKernel()]
    axis = run_axis_experiment()
    rule_control = run_rule_control(kernels)
    transformation_universe = run_transformation_universe(kernels)
    continuity = run_continuity_analysis(kernels)
    audit = host_semantics_audit()
    v2 = _v2_reference()
    return {
        "protocol": "phase1-v3",
        "objective": "decompose the kernel and test structure, evaluation, and continuity as separate experimental axes",
        "axes": {
            "S": ["atom_pair", "content_dag"],
            "E": ["direct_evaluator", "rewrite_equality", "reduced_tree_rewrite"],
            "I": ["relation_path_observation", "stable_id_primitive_absent"],
        },
        "axis_experiment": axis,
        "represented_rule_execution": rule_control,
        "transformations_as_U": transformation_universe,
        "continuity_without_id": continuity,
        "host_semantics_audit": audit,
        "egraph_verdict": _rewrite_verdict(axis, v2),
        "known_failures_preserved": [
            {
                "candidate": "rewrite_egraph",
                "failure": "unioning a term with a rewritten descendant can make minimal extraction recurse through an e-class cycle",
                "observed_in": "double_reverse equivalence layer",
                "status": "preserved",
                "experimental_workaround": "retain the e-graph equivalence proof and use the already-rewritten representative",
            },
            {
                "candidate": "all",
                "failure": "continuity is not discovered from relation paths; the analyzer only reports path, equality, alias, equivalence, and provenance facts",
                "observed_in": "continuity_without_stable_id",
                "status": "preserved",
            },
        ],
        "smallest_surviving_concepts": [
            "value as ordinary represented data",
            "represented rule/program",
            "evaluator that reads represented rules",
            "transformation as ordinary U",
            "composition and history as ordinary U",
            "relation/path for continuity evidence",
            "cost and provenance as observations/data",
        ],
        "semantics_still_trapped_in_host": [
            "candidate encode/decode implementations",
            "direct arithmetic and list/string operations",
            "generic rewrite matcher and saturation loop",
            "continuity reachability and interpretation",
            "measurement, storage accounting, and provenance judgment",
        ],
        "phase1_gate": {
            "what_things_are_evidence": "partial",
            "how_things_change_evidence": "partial",
            "open_phase2": False,
            "reason": "Represented rules control a fixed evaluator, but continuity interpretation and substantial operation semantics remain host-defined.",
        },
        "selection": None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MAT-SI Phase 1 protocol v3")
    parser.add_argument("--json-out", type=Path, default=Path("results/phase1-v3-results.json"))
    args = parser.parse_args(argv)
    result = run_v3()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("represented_rule_execution:", result["represented_rule_execution"]["all_pass"])
    print("transformations_as_U:", result["transformations_as_U"]["all_pass"])
    print("continuity_cases:", len(result["continuity_without_id"]["cases"]))
    print("egraph_verdict:", result["egraph_verdict"]["answer"])
    print("phase1_gate.open_phase2:", result["phase1_gate"]["open_phase2"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
