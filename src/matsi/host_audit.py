"""Protocol v3 audit of semantic work performed by host Python."""

from __future__ import annotations

from typing import Any


def host_semantics_audit() -> dict[str, Any]:
    audit = {
        "definitions": {
            "HOST": "semantic work executed by Python or a host library rather than read from U",
            "REPRESENTED": "structure, rule, relation, or data explicitly carried in U",
            "DERIVED": "a result computed from represented data by a mechanism or harness",
        },
        "candidates": {
            "atom_pair": {
                "encode": {"HOST": ["Python traversal", "JSON scalar canonicalization", "map key sorting"], "REPRESENTED": ["Atom", "Pair", "list/map tags"], "DERIVED": ["binary tree shape"]},
                "decode": {"HOST": ["Python parser and traversal"], "REPRESENTED": ["tagged pair tree"], "DERIVED": ["host value projection"]},
                "query": {"HOST": ["path loop", "linear scan"], "REPRESENTED": ["pair tree path"], "DERIVED": ["queried value and traversal count"]},
                "transform": {"HOST": ["apply_operation", "decode/re-encode orchestration"], "REPRESENTED": ["input and output pair trees"], "DERIVED": ["transformed value"]},
                "identity": {"HOST": ["equality of decoded values"], "REPRESENTED": ["content/annotation fields when supplied"], "DERIVED": ["projection comparison only"]},
            },
            "content_dag": {
                "encode": {"HOST": ["canonical serialization", "SHA-256 call", "Python store/index"], "REPRESENTED": ["immutable nodes", "CID links"], "DERIVED": ["content-addressed sharing"]},
                "decode": {"HOST": ["Python store lookup", "memoization"], "REPRESENTED": ["root and links"], "DERIVED": ["reconstructed value"]},
                "query": {"HOST": ["map/list edge scan"], "REPRESENTED": ["CID path"], "DERIVED": ["queried value and traversal count"]},
                "transform": {"HOST": ["apply_operation", "decode/re-encode orchestration"], "REPRESENTED": ["old and new immutable roots"], "DERIVED": ["new nodes and root redirect"]},
                "identity": {"HOST": ["CID equality comparison in harness"], "REPRESENTED": ["content and annotations as ordinary nodes"], "DERIVED": ["same-content CID observation"]},
            },
            "rewrite_egraph": {
                "encode": {"HOST": ["Python term construction", "hash-consing data structures"], "REPRESENTED": ["enodes", "e-classes", "rule table"], "DERIVED": ["congruence classes"]},
                "decode": {"HOST": ["extraction algorithm", "JSON projection"], "REPRESENTED": ["e-class alternatives"], "DERIVED": ["least-size representative"]},
                "query": {"HOST": ["representative extraction", "path loop"], "REPRESENTED": ["e-class graph"], "DERIVED": ["query result and visited classes"]},
                "transform": {"HOST": ["matcher/substitution loop", "apply_operation", "graph rebuild"], "REPRESENTED": ["generic rule schemas", "wrapped terms"], "DERIVED": ["rewrite sequence and extracted result"]},
                "identity": {"HOST": ["decoded-term comparison"], "REPRESENTED": ["terms/e-classes"], "DERIVED": ["equivalence observation, not continuity"]},
            },
            "represented_rule_vm": {
                "evaluate": {"HOST": ["fixed VM instruction loop", "stack allocation"], "REPRESENTED": ["rule program", "input U"], "DERIVED": ["output U", "modified rule behavior"]},
                "self_interpretation": {"HOST": ["same VM loop"], "REPRESENTED": ["rule that edits another represented rule"], "DERIVED": ["rule_B and its output"]},
            },
            "continuity_analysis": {
                "path_analysis": {"HOST": ["reachability traversal", "classification comparison"], "REPRESENTED": ["snapshots", "relations", "provenance"], "DERIVED": ["path available, content equality, alias/equivalence facts"]},
            },
        },
        "conclusion": "The current experiment still has substantial HOST semantics. The strongest reduction is represented-rule execution: rule data controls a fixed evaluator, but the evaluator vocabulary remains host code.",
    }
    return audit
