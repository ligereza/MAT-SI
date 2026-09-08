"""Prequential evaluation contracts; runners are intentionally not wired yet."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .contracts import ForecastEvidence, ForecastModel, PrequentialFold
from .spec import Observation, PredictionContext


SCORE_IDS = (
    "set_log_score",
    "marginal_brier",
    "calibration_error",
    "posterior_entropy",
    "compute_cost",
)

PLACEBO_IDS = (
    "temporal_shuffle",
    "label_permutation",
    "history_cutoff_shuffle",
    "random_parameter_placebo",
)


@dataclass(frozen=True)
class EvaluationBoundary:
    fold: PrequentialFold
    model_id: str
    score_ids: tuple[str, ...] = SCORE_IDS


def plan_boundaries(
    folds: Iterable[PrequentialFold], model_ids: Iterable[str]
) -> tuple[EvaluationBoundary, ...]:
    """Create metadata for future evaluation without reading or scoring data."""

    return tuple(
        EvaluationBoundary(fold=fold, model_id=model_id)
        for fold in folds
        for model_id in model_ids
    )


def run_prequential(*args, **kwargs):
    """Reserved entry point; execution is intentionally not part of setup."""

    raise RuntimeError(
        "PREDICAR research is not started: implement and explicitly invoke a runner "
        "after the protocol review."
    )
