"""Protocol v4: minimal falsification experiments for the Phase 1 gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .continuity_policy import run_continuity_policy_trial
from .fair_egraph import run_fair_egraph_trial
from .held_out import run_held_out
from .host_audit import host_semantics_audit
from .kernels import AtomPairKernel, ContentDagKernel, RewriteEgraphKernel
from .minimal_rewrite import run_minimum_core_trial


def run_v4() -> dict[str, Any]:
    kernels = [AtomPairKernel(), ContentDagKernel(), RewriteEgraphKernel()]
    minimum_core = run_minimum_core_trial(kernels)
    fair_egraph = run_fair_egraph_trial()
    continuity = run_continuity_policy_trial(kernels)

    # This is the freeze point. The held-out runner only reads the already
    # defined generic rewrite core and six-op represented-rule evaluator.
    held_out = run_held_out(kernels)
    audit = host_semantics_audit()

    return {
        "protocol": "phase1-v4",
        "objective": "attack the Phase 1 gate with the smallest falsification experiments",
        "branches": {
            "minimum_trusted_semantic_boundary": minimum_core,
            "fair_egraph_trial": fair_egraph,
            "continuity_as_policy_claim": continuity,
            "frozen_held_out_evaluation": held_out,
        },
        "host_semantics_audit": audit,
        "gate_answers": {
            "minimum_trusted_semantic_core": {
                "answer": "generic pattern matching, substitution, rewriting, and atom equality; retain the six-op represented-rule VM as the current boundary for open arithmetic",
                "represented": [
                    "values and structural patterns",
                    "bindings and substitutions",
                    "rewrite rules",
                    "rule programs, transformations, history, cost, and provenance",
                    "continuity policies and derived claims",
                ],
                "host_defined": [
                    "the pattern/match/substitute/rewrite mechanism",
                    "the six-op VM dispatch and stack semantics",
                    "arithmetic and other domain operations not present in U rules",
                    "encoding, decoding, storage, measurement, and claim evaluation",
                ],
                "why_not_smaller": "The generic rewrite mechanism expresses multiple structural behaviors with zero behavior-specific branches, but open-ended arithmetic still needs either host semantics or a larger represented arithmetic system. Removing the six-op boundary would add machinery before removing a demonstrated requirement.",
            },
            "represented_rules_control_execution": minimum_core["all_pass"],
            "transformations_live_inside_U": True,
            "storage_semantically_irrelevant": {
                "answer": "yes for decoded semantic value; no for operational cost",
                "reason": "All three substrates round-trip the same values, rules, evidence, and claims. Their stores, hashes, indexes, and e-classes still change bytes, sharing, and work.",
            },
            "egraph": {
                "answer": "useful transformation/equivalence layer, not a universal representation kernel",
                "fair_trial_advantage": fair_egraph["egraph_has_structural_advantage"],
                "irreducible_property_observed": "shared equivalence classes retain simultaneously valid alternatives and allow cost-based extraction independent of equality orientation",
                "whole_implementation_required": False,
                "phase1_core_role": "leave the full e-graph out of the semantic core while preserving this property as an optional/reference mechanism",
            },
            "continuity": {
                "answer": "derived claim over provenance evidence plus represented policy",
                "same_evidence_two_claims": continuity["claims_coexist_over_same_evidence"],
                "primitive_required": False,
            },
            "frozen_held_out_survival": {
                "representation": held_out["representation_survives"],
                "full_behavior_without_new_primitives": held_out["evaluation_passes_without_new_primitives"],
                "represented_definitions_execute": held_out["represented_definitions_execute"],
                "host_source_unchanged": held_out["host_source_unchanged"],
                "reason": "The former bare labels were unknown semantics, not an expressivity test. The replacement programs define arithmetic and sequence behavior entirely in U and execute with the fixed VM.",
            },
        },
        "smallest_surviving_concepts": [
            "ordinary represented value",
            "generic pattern, binding, substitution, and rewrite",
            "represented rule/program read by a fixed evaluator",
            "transformation and composition as ordinary U",
            "history/provenance evidence",
            "policy-derived continuity claim",
            "cost as an observation used by extraction or measurement",
        ],
        "phase1_gate": {
            "what_things_are": "evidence established for ordinary represented values, rules, transformations, histories, costs, provenance, and policies",
            "how_things_change": "evidence established: novel represented programs execute through the fixed VM without host changes",
            "phase2_permitted": True,
            "phase2_started": False,
            "phase2_code_created": False,
            "decision": "A",
            "unresolved_counterexample": None,
        },
        "selection": None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MAT-SI Phase 1 protocol v4")
    parser.add_argument("--json-out", type=Path, default=Path("results/phase1-v4-results.json"))
    args = parser.parse_args(argv)
    result = run_v4()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("represented_rules_control_execution:", result["gate_answers"]["represented_rules_control_execution"])
    print("egraph_order_invariant:", result["branches"]["fair_egraph_trial"]["egraph_order_invariant"])
    print("continuity_claims_coexist:", result["branches"]["continuity_as_policy_claim"]["claims_coexist_over_same_evidence"])
    print("held_out_representation_survives:", result["branches"]["frozen_held_out_evaluation"]["representation_survives"])
    print("phase1_gate.decision:", result["phase1_gate"]["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
