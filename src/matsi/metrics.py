"""Explicit, computable Phase 1 metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Measurement:
    candidate: str
    case_id: str
    description_size: int
    reconstruction_fidelity: float
    structural_sharing: float
    transformation_cost: int
    query_cost: int
    cross_domain_generality: float
    self_modeling: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def sharing_ratio(unique_nodes: int, expanded_nodes: int) -> float:
    if expanded_nodes <= 0:
        return 0.0
    return max(0.0, 1.0 - unique_nodes / expanded_nodes)
