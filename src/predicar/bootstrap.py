"""Build the frozen preparation plan without loading data or fitting models."""

from __future__ import annotations

from .adapters import ALL_AREAS
from .contracts import ExperimentPlan
from .models import planned_model_ids
from .spec import CardinalitySpec


INITIAL_SPEC = CardinalitySpec(universe_size=25, cardinality=14, name="cardinality-14-25")


def preparation_plan() -> ExperimentPlan:
    """Return the protocol metadata for the not-started laboratory."""

    return ExperimentPlan(
        protocol_id="predicar-v0",
        spec=INITIAL_SPEC,
        folds=(),
        model_ids=planned_model_ids(),
        score_ids=(
            "set_log_score",
            "marginal_brier",
            "calibration_error",
            "posterior_entropy",
            "compute_cost",
        ),
        placebo_ids=(
            "temporal_shuffle",
            "label_permutation",
            "history_cutoff_shuffle",
            "random_parameter_placebo",
        ),
        random_seed_policy="explicit_and_recorded",
        data_policy="manifests_first_no_external_dataset_by_default",
    )


def research_area_ids() -> tuple[str, ...]:
    """Return the six imported areas without activating any adapter."""

    return tuple(area.area_id for area in ALL_AREAS)
