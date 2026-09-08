"""Lazy state-space helpers; nothing is enumerated on import."""

from __future__ import annotations

from math import log

from .spec import BinaryState, CardinalitySpec, iter_states


def support(spec: CardinalitySpec):
    """Return a lazy iterator over the exact-cardinality support."""

    return iter_states(spec)


def uniform_log_probability(spec: CardinalitySpec) -> float:
    """Log probability of one state under the exact uniform baseline."""

    return -log(spec.support_size)
