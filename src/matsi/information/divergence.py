"""Divergences between finite distributions, in bits.

``kl_divergence`` returns ``math.inf`` when the support of ``p`` is not contained
in the support of ``q``: that is the correct value, not an error, and callers
must handle it rather than smoothing it away silently.  Jensen-Shannon is used
wherever a bounded symmetric quantity is needed; it is bounded by 1 bit
(Lin 1991), which makes it safe as a novelty score.
"""

from __future__ import annotations

from fractions import Fraction
from math import inf, log2
from typing import Hashable, Mapping

from .entropy import TOLERANCE, entropy

Distribution = Mapping[Hashable, float | Fraction]


def _support(*distributions: Distribution) -> list[Hashable]:
    keys: list[Hashable] = []
    for distribution in distributions:
        for key in distribution:
            if key not in keys:
                keys.append(key)
    return keys


def kl_divergence(p: Distribution, q: Distribution) -> float:
    """D(p || q) in bits; ``inf`` when q assigns zero mass to a p-atom."""
    total = 0.0
    for key in _support(p, q):
        p_value = float(p.get(key, 0))
        q_value = float(q.get(key, 0))
        if p_value <= 0.0:
            continue
        if q_value <= 0.0:
            return inf
        total += p_value * log2(p_value / q_value)
    return 0.0 if abs(total) < TOLERANCE else total


def _mixture(p: Distribution, q: Distribution) -> dict[Hashable, float]:
    return {
        key: 0.5 * float(p.get(key, 0)) + 0.5 * float(q.get(key, 0))
        for key in _support(p, q)
    }


def jensen_shannon_divergence(p: Distribution, q: Distribution) -> float:
    """JSD(p, q) in bits, in [0, 1]; symmetric and always finite.

    Computed as H(m) - (H(p) + H(q)) / 2 with m the equal mixture, which is the
    identity form and avoids the infinities of KL.
    """
    mixture = _mixture(p, q)
    value = entropy(mixture) - 0.5 * entropy(dict(p)) - 0.5 * entropy(dict(q))
    if abs(value) < TOLERANCE:
        return 0.0
    return min(1.0, value)


def total_variation_distance(p: Distribution, q: Distribution) -> float:
    """Total variation distance, in [0, 1]."""
    return 0.5 * sum(abs(float(p.get(key, 0)) - float(q.get(key, 0))) for key in _support(p, q))
