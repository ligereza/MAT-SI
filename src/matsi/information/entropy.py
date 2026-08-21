"""Shannon entropy and its conditional and mutual forms, in bits.

Definitions follow Cover & Thomas, *Elements of Information Theory*, 2nd ed.,
chapter 2.  Conventions used throughout:

* ``0 log 0 = 0`` (continuity at zero);
* a distribution is a mapping ``outcome -> probability`` that must sum to one
  within ``TOLERANCE``, or be exactly one when Fractions are used;
* a joint distribution is a mapping ``(x, y) -> probability``.

``PROVED`` statements verified in ``tests/test_information.py``:
``H(X) >= 0``; ``H(X) <= log2 |support|`` with equality iff uniform;
``H(X,Y) = H(X) + H(Y|X)``; ``I(X;Y) = H(X) + H(Y) - H(X,Y) >= 0``;
``I(X;Y) = 0`` iff X and Y are independent.
"""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from math import isclose, log2
from typing import Any, Hashable, Iterable, Mapping, Sequence

TOLERANCE = 1e-9

Distribution = Mapping[Hashable, float | Fraction]


def _check(distribution: Distribution) -> None:
    if not distribution:
        raise ValueError("distribution must be non-empty")
    total = sum(distribution.values())
    if any(float(p) < -TOLERANCE for p in distribution.values()):
        raise ValueError("distribution has a negative probability")
    if isinstance(total, Fraction):
        if total != 1:
            raise ValueError(f"exact distribution must sum to 1, got {total}")
    elif not isclose(float(total), 1.0, abs_tol=1e-7):
        raise ValueError(f"distribution must sum to 1, got {float(total)}")


def normalise(weights: Mapping[Hashable, float | Fraction]) -> dict[Hashable, Fraction]:
    """Turn non-negative weights into an exact distribution of Fractions."""
    if not weights:
        raise ValueError("cannot normalise empty weights")
    exact = {key: Fraction(value).limit_denominator(10**9) for key, value in weights.items()}
    total = sum(exact.values())
    if total <= 0:
        raise ValueError("weights must have positive mass")
    return {key: value / total for key, value in exact.items()}


def empirical_distribution(samples: Iterable[Hashable]) -> dict[Hashable, Fraction]:
    """Maximum-likelihood distribution of a finite sample, exactly."""
    counts = Counter(samples)
    if not counts:
        raise ValueError("cannot build a distribution from an empty sample")
    total = sum(counts.values())
    return {outcome: Fraction(count, total) for outcome, count in counts.items()}


def _plogp(p: float | Fraction) -> float:
    value = float(p)
    if value <= 0.0:
        return 0.0
    return -value * log2(value)


def entropy(distribution: Distribution) -> float:
    """H(X) in bits."""
    _check(distribution)
    return sum(_plogp(p) for p in distribution.values())


def _marginal(joint: Distribution, axis: int) -> dict[Hashable, Fraction | float]:
    marginal: dict[Hashable, Any] = {}
    for outcome, p in joint.items():
        key = outcome[axis]
        marginal[key] = marginal.get(key, 0) + p
    return marginal


def joint_entropy(joint: Distribution) -> float:
    """H(X,Y) in bits for a distribution over pairs."""
    _check(joint)
    return sum(_plogp(p) for p in joint.values())


def conditional_entropy(joint: Distribution) -> float:
    """H(Y|X) in bits, with X the first component of each pair.

    Uses the chain rule H(Y|X) = H(X,Y) - H(X), which is exact and avoids
    building every conditional distribution explicitly.
    """
    _check(joint)
    return joint_entropy(joint) - entropy(_marginal(joint, 0))


def mutual_information(joint: Distribution) -> float:
    """I(X;Y) = H(X) + H(Y) - H(X,Y), in bits, clamped at zero.

    The clamp removes floating-point residue only: the quantity is provably
    non-negative (Cover & Thomas, theorem 2.6.3), so a tiny negative float is an
    artefact of ``log2``, never a signal.  With Fraction inputs and independent
    variables the result is exactly ``0.0``.
    """
    _check(joint)
    value = (
        entropy(_marginal(joint, 0))
        + entropy(_marginal(joint, 1))
        - joint_entropy(joint)
    )
    return 0.0 if abs(value) < TOLERANCE else value


def conditional_mutual_information(triple_joint: Distribution) -> float:
    """I(X;Y|Z) in bits for a distribution over triples ``(x, y, z)``.

    Computed as I(X;Y|Z) = H(X|Z) + H(Y|Z) - H(X,Y|Z).
    """
    _check(triple_joint)
    xz: dict[Hashable, Any] = {}
    yz: dict[Hashable, Any] = {}
    z: dict[Hashable, Any] = {}
    xyz: dict[Hashable, Any] = {}
    for (x, y, zz), p in triple_joint.items():
        xz[(zz, x)] = xz.get((zz, x), 0) + p
        yz[(zz, y)] = yz.get((zz, y), 0) + p
        z[zz] = z.get(zz, 0) + p
        xyz[(zz, (x, y))] = xyz.get((zz, (x, y)), 0) + p
    value = conditional_entropy(xz) + conditional_entropy(yz) - conditional_entropy(xyz)
    return 0.0 if abs(value) < TOLERANCE else value


def joint_from_samples(samples: Sequence[tuple[Hashable, ...]]) -> dict[Hashable, Fraction]:
    """Exact empirical joint distribution over tuples."""
    return empirical_distribution(tuple(sample) for sample in samples)


def information_gain_of_subset(
    joint_table: Sequence[tuple[tuple[Hashable, ...], Hashable]],
    subset: Sequence[int],
) -> float:
    """I(X_subset ; Y) from an explicit table of ``(features, target)`` rows.

    Each row is one equiprobable atom of the joint distribution; repeated rows
    encode higher probability.  This is the set function whose submodularity is
    examined in ``docs/autonomous-operators/vizz.md``.
    """
    if not joint_table:
        raise ValueError("empty joint table")
    indices = tuple(subset)
    pairs = [
        (tuple(features[i] for i in indices), target) for features, target in joint_table
    ]
    return mutual_information(empirical_distribution(pairs))
