"""Bayesian surprise over an explicit finite hypothesis space.

Bayesian surprise is the KL divergence from prior to posterior after an
observation (Itti & Baldi, *Bayesian surprise attracts human attention*, NIPS
2005 / Vision Research 2009).  It is a property of the *belief change*, not of
the observation's rarity, which is exactly the distinction VIZZ needs: a rare
observation that leaves the posterior unchanged has zero surprise.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Callable, Hashable, Mapping

from .divergence import kl_divergence
from .entropy import normalise

Belief = Mapping[Hashable, float | Fraction]


def posterior_update(
    prior: Belief,
    likelihood: Callable[[Hashable], float | Fraction],
) -> dict[Hashable, Fraction]:
    """Bayes rule over a finite hypothesis space.

    ``likelihood(h)`` is P(observation | h).  Raises when the observation is
    impossible under every hypothesis, because renormalising zero mass would
    invent a belief.
    """
    weights = {h: Fraction(prior[h]) * Fraction(likelihood(h)) for h in prior}
    if sum(weights.values()) <= 0:
        raise ValueError("observation has zero likelihood under every hypothesis")
    return normalise(weights)


def bayesian_surprise(
    prior: Belief,
    likelihood: Callable[[Hashable], float | Fraction],
) -> tuple[float, dict[Hashable, Fraction]]:
    """Return ``(surprise_in_bits, posterior)``.

    Surprise is ``D(posterior || prior)``.  It is finite whenever the posterior
    support is contained in the prior support, which Bayes guarantees.
    """
    posterior = posterior_update(prior, likelihood)
    return kl_divergence(posterior, prior), posterior
