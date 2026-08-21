"""Executable information-theory primitives for MAT-SI.

Everything here works on explicit finite distributions given as mappings from an
outcome to a probability, or on empirical counts.  Probabilities are handled as
``fractions.Fraction`` when exactness matters, so a value like ``I(X;Y) = 0`` is
reported as exactly zero instead of a float residue that a policy could mistake
for a signal.
"""

from .entropy import (
    conditional_entropy,
    empirical_distribution,
    entropy,
    joint_entropy,
    mutual_information,
    conditional_mutual_information,
    normalise,
)
from .divergence import (
    jensen_shannon_divergence,
    kl_divergence,
    total_variation_distance,
)
from .surprise import bayesian_surprise, posterior_update
from .mdl import two_part_cost, description_length

__all__ = [
    "bayesian_surprise",
    "conditional_entropy",
    "conditional_mutual_information",
    "description_length",
    "empirical_distribution",
    "entropy",
    "jensen_shannon_divergence",
    "joint_entropy",
    "kl_divergence",
    "mutual_information",
    "normalise",
    "posterior_update",
    "posterior_update",
    "total_variation_distance",
    "two_part_cost",
]
