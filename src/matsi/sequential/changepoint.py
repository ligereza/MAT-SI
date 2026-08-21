"""Change detection on a scalar observable stream.

Three detectors with different failure modes, kept side by side because none
dominates:

* ``page_hinkley`` -- cumulative deviation from the running mean with a tolerance
  and a threshold (Page, *Continuous inspection schemes*, Biometrika 1954).
  KNOWN_RESULT: for a fixed threshold the detection delay decreases and the false
  alarm rate increases as the threshold falls; there is no setting that is best
  for both.  ``tests/test_sequential.py`` measures that trade-off rather than
  asserting one setting.
* ``cusum`` -- two-sided cumulative sum, sensitive to small persistent shifts.
* ``sliding_window_mean_shift`` -- compares two adjacent windows; needs no
  parameter tuned to the drift magnitude but cannot see a shift smaller than the
  window noise.

None of them label a regime as good or bad.  They report *where the distribution
of the observable appears to change*, which is an observable claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean, pstdev
from typing import Sequence


@dataclass
class ChangeDetection:
    """Detector output: alarm indices and the statistic that produced them."""

    detector: str
    alarms: tuple[int, ...] = ()
    statistic: tuple[float, ...] = ()
    parameters: dict[str, float] = field(default_factory=dict)

    @property
    def first_alarm(self) -> int | None:
        return self.alarms[0] if self.alarms else None

    def delay_from(self, true_change: int) -> int | None:
        """Detection delay relative to a known change point, or None if missed."""
        for alarm in self.alarms:
            if alarm >= true_change:
                return alarm - true_change
        return None

    def false_alarms_before(self, true_change: int) -> int:
        return sum(1 for alarm in self.alarms if alarm < true_change)

    def as_measurement(self) -> dict[str, object]:
        return {
            "detector": self.detector,
            "alarms": list(self.alarms),
            "first_alarm": self.first_alarm,
            "parameters": dict(self.parameters),
        }


def page_hinkley(
    stream: Sequence[float],
    delta: float = 0.005,
    threshold: float = 1.0,
    direction: str = "decrease",
) -> ChangeDetection:
    """Page-Hinkley test for a persistent shift in the mean.

    ``direction='decrease'`` alarms when the stream drops below its running mean
    (the deteriorating-return case); ``'increase'`` is the mirror image; ``'both'``
    tracks the two statistics and alarms on either.
    """
    if direction not in ("increase", "decrease", "both"):
        raise ValueError("direction must be increase, decrease or both")
    running_mean = 0.0
    cumulative_down = 0.0
    cumulative_up = 0.0
    min_down = 0.0
    max_up = 0.0
    alarms: list[int] = []
    statistic: list[float] = []
    for index, value in enumerate(stream):
        running_mean += (value - running_mean) / (index + 1)
        cumulative_down += value - running_mean - delta
        cumulative_up += value - running_mean + delta
        min_down = min(min_down, cumulative_down)
        max_up = max(max_up, cumulative_up)
        down_statistic = cumulative_down - min_down
        up_statistic = max_up - cumulative_up
        current = 0.0
        if direction in ("increase", "both"):
            current = max(current, down_statistic)
        if direction in ("decrease", "both"):
            current = max(current, up_statistic)
        statistic.append(current)
        if current > threshold:
            alarms.append(index)
            running_mean = value
            cumulative_down = cumulative_up = min_down = max_up = 0.0
    return ChangeDetection(
        detector="page_hinkley",
        alarms=tuple(alarms),
        statistic=tuple(statistic),
        parameters={"delta": delta, "threshold": threshold},
    )


def cusum(stream: Sequence[float], drift: float = 0.05, threshold: float = 1.0) -> ChangeDetection:
    """Two-sided CUSUM against the mean of the observed prefix."""
    positive = 0.0
    negative = 0.0
    alarms: list[int] = []
    statistic: list[float] = []
    for index, value in enumerate(stream):
        reference = fmean(stream[: index + 1])
        positive = max(0.0, positive + value - reference - drift)
        negative = max(0.0, negative + reference - value - drift)
        current = max(positive, negative)
        statistic.append(current)
        if current > threshold:
            alarms.append(index)
            positive = negative = 0.0
    return ChangeDetection(
        detector="cusum",
        alarms=tuple(alarms),
        statistic=tuple(statistic),
        parameters={"drift": drift, "threshold": threshold},
    )


def sliding_window_mean_shift(
    stream: Sequence[float], window: int = 8, sigmas: float = 2.0
) -> ChangeDetection:
    """Alarm when two adjacent windows differ by more than ``sigmas`` of noise.

    Parameter-light but blind to shifts under the local noise level; that blindness
    is a measured failure mode, not a bug.
    """
    if window < 2:
        raise ValueError("window must be at least 2")
    alarms: list[int] = []
    statistic: list[float] = [0.0] * len(stream)
    for index in range(2 * window, len(stream) + 1):
        left = stream[index - 2 * window : index - window]
        right = stream[index - window : index]
        spread = max(pstdev(left) if len(left) > 1 else 0.0, 1e-9)
        score = abs(fmean(right) - fmean(left)) / spread
        statistic[index - 1] = score
        if score > sigmas:
            alarms.append(index - 1)
    return ChangeDetection(
        detector="sliding_window_mean_shift",
        alarms=tuple(alarms),
        statistic=tuple(statistic),
        parameters={"window": float(window), "sigmas": sigmas},
    )
