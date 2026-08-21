"""Recurrence and cycle detection over a sequence of opaque state digests.

CODEINE's original detector counted *consecutive* equal digests.  That misses the
case the audit of the previous branch flagged: two equal states separated by a
different one are a recurrence, not a streak.  These functions separate the two
notions explicitly.

* ``detect_cycle`` finds the shortest repeated state and the period between its
  occurrences -- PROVED: scanning with a first-occurrence table returns the
  earliest repetition, in O(n) time and space.
* ``recurrence_rate`` is the fraction of steps whose state was seen before; it is
  a property of the trajectory, not a verdict about it.
* ``cycle_report`` also reports the longest *consecutive* run, so a policy can
  distinguish "stuck in place" from "going in circles" -- two different
  observations that the earlier rule collapsed into one.
"""

from __future__ import annotations

from typing import Hashable, Sequence


def detect_cycle(states: Sequence[Hashable]) -> dict[str, object]:
    """Earliest repeated state with its period, or a no-cycle report."""
    first_seen: dict[Hashable, int] = {}
    for index, state in enumerate(states):
        if state in first_seen:
            start = first_seen[state]
            return {
                "cycle_found": True,
                "state": state,
                "first_index": start,
                "repeat_index": index,
                "period": index - start,
                "prefix_length": start,
            }
        first_seen[state] = index
    return {"cycle_found": False, "distinct_states": len(first_seen), "length": len(states)}


def longest_consecutive_run(states: Sequence[Hashable]) -> dict[str, object]:
    """Longest run of identical adjacent states."""
    best = 0
    best_at = None
    current = 0
    for index, state in enumerate(states):
        if index > 0 and state == states[index - 1]:
            current += 1
        else:
            current = 1
        if current > best:
            best, best_at = current, index - current + 1
    return {"longest_run": best, "starts_at": best_at}


def recurrence_rate(states: Sequence[Hashable]) -> float:
    """Fraction of positions whose state already occurred earlier."""
    if not states:
        return 0.0
    seen: set[Hashable] = set()
    repeats = 0
    for state in states:
        if state in seen:
            repeats += 1
        seen.add(state)
    return repeats / len(states)


def cycle_report(states: Sequence[Hashable]) -> dict[str, object]:
    """Everything observable about repetition in one trajectory.

    Note the deliberate separation: ``longest_consecutive_run`` measures standing
    still, ``period`` measures returning, and ``recurrence_rate`` measures how
    much of the trajectory is re-visited.  A trajectory can have a high recurrence
    rate with no consecutive run at all.
    """
    cycle = detect_cycle(states)
    run = longest_consecutive_run(states)
    return {
        **cycle,
        **run,
        "recurrence_rate": recurrence_rate(states),
        "distinct_states": len(set(states)),
        "length": len(states),
        "semantic_claim": "none; these are properties of the digest sequence",
    }


def compress_trajectory(states: Sequence[Hashable]) -> tuple[tuple[Hashable, int], ...]:
    """Run-length encoding of a trajectory: the smallest lossless summary.

    Keeping the counts means the compression is reversible, so it is a
    representation change and not a loss of evidence.
    """
    if not states:
        return ()
    out: list[tuple[Hashable, int]] = [(states[0], 1)]
    for state in states[1:]:
        if state == out[-1][0]:
            out[-1] = (state, out[-1][1] + 1)
        else:
            out.append((state, 1))
    return tuple(out)
