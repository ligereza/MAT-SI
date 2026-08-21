"""Diminishing-return estimation on a cumulative-value stream.

Given cumulative values ``V_1 <= V_2 <= ...`` the marginal gains are
``g_t = V_t - V_{t-1}``.  ``diminishing_returns`` fits nothing: it reports the
observable shape of the gain sequence -- whether the recent gains are a
significant fraction of the early ones, and how long the current plateau is.

The deliberate omission: none of these functions decide whether to stop.  A
policy may combine them with a cost model; the estimator only measures.
"""

from __future__ import annotations

from statistics import fmean
from typing import Sequence


def marginal_gains(cumulative: Sequence[float]) -> tuple[float, ...]:
    if not cumulative:
        return ()
    gains = [cumulative[0]]
    for index in range(1, len(cumulative)):
        gains.append(cumulative[index] - cumulative[index - 1])
    return tuple(gains)


def plateau_length(cumulative: Sequence[float], tolerance: float = 1e-9) -> int:
    """Number of trailing steps whose marginal gain is within ``tolerance``."""
    gains = marginal_gains(cumulative)
    count = 0
    for gain in reversed(gains):
        if abs(gain) <= tolerance:
            count += 1
        else:
            break
    return count


def diminishing_returns(
    cumulative: Sequence[float], window: int = 3, tolerance: float = 1e-9
) -> dict[str, object]:
    """Observable summary of the gain sequence.

    ``recent_share`` is the mean of the last ``window`` gains divided by the mean
    of all gains.  It is ``None`` when the total gain is zero, because a ratio
    with a zero denominator is undefined, not zero.
    """
    gains = marginal_gains(cumulative)
    if not gains:
        return {"gains": (), "recent_share": None, "plateau": 0, "monotone": True}
    recent = gains[-window:]
    overall_mean = fmean(gains)
    recent_share = None if abs(overall_mean) <= tolerance else fmean(recent) / overall_mean
    return {
        "gains": gains,
        "total_gain": cumulative[-1] - (0.0 if len(cumulative) == 1 else cumulative[0]),
        "recent_mean_gain": fmean(recent),
        "overall_mean_gain": overall_mean,
        "recent_share": recent_share,
        "plateau": plateau_length(cumulative, tolerance),
        "monotone": all(gain >= -tolerance for gain in gains),
        "window": window,
    }


def concavity_violations(cumulative: Sequence[float], tolerance: float = 1e-9) -> int:
    """Count steps where the marginal gain increased.

    A submodular (concave) value curve has non-increasing gains, so a positive
    count here is direct evidence that the value function is *not* submodular on
    this trajectory.  This is the empirical test used against the VIZZ
    counterexample world.
    """
    gains = marginal_gains(cumulative)
    return sum(
        1 for index in range(1, len(gains)) if gains[index] > gains[index - 1] + tolerance
    )
