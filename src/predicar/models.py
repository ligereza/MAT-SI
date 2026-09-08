"""Model-family registry for the six PREDICAR research adapters."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import ForecastModel
from .spec import CardinalitySpec


@dataclass(frozen=True)
class ModelFamily:
    model_id: str
    origin_area: str
    role: str
    exact_cardinality: bool
    status: str = "planned"


MODEL_FAMILIES = (
    ModelFamily("uniform_exact", "core", "minimum baseline", True),
    ModelFamily("conditional_cardinality", "statistical_physics", "marginal baseline", True),
    ModelFamily("pairwise_gibbs", "neural_population", "interaction model", True),
    ModelFamily("finite_set_bayes", "rfs_tracking", "set-valued filter", True),
    ModelFamily("noisy_channel", "error_correcting", "observation recovery", True),
    ModelFamily("memory_kernel", "point_processes", "temporal dynamics", True),
    ModelFamily("constraint_weighted", "constraint_programming", "constrained inference", True),
    ModelFamily("complex_amplitude", "statistical_physics", "optional challenger", True),
)


def planned_model_ids() -> tuple[str, ...]:
    """Return identifiers only; model fitting is deliberately not performed."""

    return tuple(item.model_id for item in MODEL_FAMILIES)
