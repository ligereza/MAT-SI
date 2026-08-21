"""Continuity as a represented policy over one raw provenance graph."""

from __future__ import annotations

import hashlib
from typing import Any

from .canonical import canonical_text


def raw_provenance_graph() -> dict[str, Any]:
    """Return evidence without stable object identifiers.

    The integer references are positions in this observation, not identities.
    The same value is encoded once and evaluated with two different policies.
    """

    return {
        "reference_semantics": "observation_position_only",
        "nodes": [
            {"position": 0, "content": {"kind": "document", "value": "old"}},
            {"position": 1, "content": {"kind": "document", "value": "new"}},
        ],
        "events": [
            {
                "from_position": 0,
                "to_position": 1,
                "kind": "replacement",
                "transformation": {"operation": "replace"},
                "provenance": {"source": "raw-history", "event_index": 0},
            }
        ],
    }


def continuity_policies() -> list[dict[str, Any]]:
    """Policies are ordinary U data, not evaluator branches or primitives."""

    return [
        {
            "name": "replacement_breaks_continuity",
            "rules": {"replacement": "breaks"},
        },
        {
            "name": "replacement_preserves_lineage",
            "rules": {"replacement": "preserves"},
        },
    ]


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_text(value).encode("utf-8")).hexdigest()


def derive_continuity_claim(history_representation: Any, policy_representation: Any, kernel: Any) -> dict[str, Any]:
    """Derive a claim from decoded evidence and decoded policy.

    No value named identity or continuity is stored in the raw graph. The
    result is a claim whose provenance points back to both inputs.
    """

    history = kernel.decode(history_representation)
    policy = kernel.decode(policy_representation)
    event = history["events"][0]
    decision = policy["rules"][event["kind"]]
    preserves = decision == "preserves"
    return {
        "kind": "derived_claim",
        "claim": "lineage_continuity",
        "value": preserves,
        "from_position": event["from_position"],
        "to_position": event["to_position"],
        "policy": policy["name"],
        "evidence": {
            "event_kind": event["kind"],
            "transformation": event["transformation"],
        },
        "provenance": {
            "history_digest": _digest(history),
            "policy_digest": _digest(policy),
            "derived_by": "evidence_plus_policy",
        },
    }


def run_continuity_policy_trial(kernels: list[Any]) -> dict[str, Any]:
    history = raw_provenance_graph()
    policies = continuity_policies()
    rows: list[dict[str, Any]] = []
    for kernel in kernels:
        history_representation = kernel.encode(history)
        decoded_histories: list[Any] = []
        for policy in policies:
            policy_representation = kernel.encode(policy)
            decoded_history = kernel.decode(history_representation)
            claim = derive_continuity_claim(history_representation, policy_representation, kernel)
            claim_round_trip = kernel.decode(kernel.encode(claim)) == claim
            decoded_histories.append(decoded_history)
            rows.append(
                {
                    "candidate": kernel.name,
                    "policy": policy["name"],
                    "claim_value": claim["value"],
                    "claim": claim,
                    "history_round_trip": decoded_history == history,
                    "claim_round_trip": claim_round_trip,
                    "stable_id_fields": [
                        key
                        for key in claim
                        if key.lower() in {"id", "identity", "stable_id"} or key.lower().endswith("_id")
                    ],
                }
            )
        if decoded_histories[0] != decoded_histories[1]:
            raise AssertionError("policies changed the raw evidence")
    claims_by_policy = {
        row["policy"]: row["claim_value"] for row in rows if row["candidate"] == kernels[0].name
    }
    return {
        "experiment": "continuity_policy_over_raw_provenance",
        "raw_history": history,
        "policies": policies,
        "rows": rows,
        "same_history_under_both_policies": all(
            row["history_round_trip"] for row in rows
        ),
        "claims_coexist_over_same_evidence": len(set(claims_by_policy.values())) == 2,
        "claims_preserve_provenance": all(
            row["claim_round_trip"] and row["claim"]["provenance"]["derived_by"] == "evidence_plus_policy"
            for row in rows
        ),
        "stable_identity_primitive_used": any(row["stable_id_fields"] for row in rows),
        "conclusion": "Continuity is a derived claim over represented evidence and represented policy; it is not required as a primitive of U.",
    }
