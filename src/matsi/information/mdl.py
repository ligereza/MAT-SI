"""Two-part minimum description length.

MDL scores a model by ``L(model) + L(data | model)`` (Rissanen 1978; Grünwald,
*The Minimum Description Length Principle*, 2007).  MAT-SI already used a
two-part cost in Phase 1: canonical byte counts for the rule plus residual data
cost.  This module keeps that shape but makes both parts explicit and reusable,
and it never claims to compute Kolmogorov complexity.
"""

from __future__ import annotations

from math import ceil, log2
from typing import Any, Callable, Hashable, Sequence

from ..canonical import canonical_text


def description_length(value: Any) -> float:
    """Bits needed for the canonical projection of a represented value.

    This is a *host* measurement: it counts the canonical UTF-8 encoding, which
    is a projection choice and not an intrinsic property of the object.  It is
    used only to compare candidates under one fixed encoding.
    """
    return float(len(canonical_text(value).encode("utf-8")) * 8)


def code_length_under(distribution: dict[Hashable, float], outcome: Hashable) -> float:
    """Ideal code length -log2 P(outcome); ``inf`` for an unmodelled outcome."""
    probability = float(distribution.get(outcome, 0.0))
    if probability <= 0.0:
        return float("inf")
    return -log2(probability)


def two_part_cost(
    model: Any,
    data: Sequence[Hashable],
    predictor: Callable[[Any, int], dict[Hashable, float]],
) -> dict[str, float]:
    """Return the model cost, the data cost given the model, and their sum.

    ``predictor(model, index)`` returns the model's predictive distribution for
    ``data[index]``.  A model that cannot predict an observed atom pays ``inf``,
    which is the honest answer rather than a smoothed one.
    """
    model_bits = description_length(model)
    data_bits = 0.0
    for index, outcome in enumerate(data):
        data_bits += code_length_under(predictor(model, index), outcome)
    return {
        "model_bits": model_bits,
        "data_bits": data_bits,
        "total_bits": model_bits + data_bits,
    }


def uniform_baseline_bits(alphabet_size: int, length: int) -> float:
    """Bits to encode a length-n string over a fixed alphabet with no model."""
    if alphabet_size < 1 or length < 0:
        raise ValueError("alphabet size must be >= 1 and length >= 0")
    return float(length) * ceil(log2(alphabet_size)) if alphabet_size > 1 else 0.0
