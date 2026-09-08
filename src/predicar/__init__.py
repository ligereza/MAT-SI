"""PREDICAR: neutral finite-set probabilistic forecasting laboratory.

This package is intentionally inert at import time.  It defines the contracts
and experiment metadata needed to begin the investigation; no model is fit and
no dataset is loaded automatically.
"""

from .contracts import (
    ForecastModel,
    PredictiveDistribution,
    ResearchArea,
)
from .spec import BinaryState, CardinalitySpec, Observation, PredictionContext

__all__ = [
    "BinaryState",
    "CardinalitySpec",
    "ForecastModel",
    "Observation",
    "PredictionContext",
    "PredictiveDistribution",
    "ResearchArea",
]
