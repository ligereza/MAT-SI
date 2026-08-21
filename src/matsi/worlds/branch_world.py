"""Possible-world trees for KETAMINE, with an exhaustive oracle.

A branch is an explicit record: state, parent, the intervention that created it,
the assumptions it carries, whether those assumptions are consistent with recorded
evidence, its cost, and a bound on the best value reachable through it.

The modal distinction is structural, not a comment: a branch has
``status in {SIMULATED, REJECTED, OBSERVED}``.  Only the root is ``OBSERVED``.
Nothing a search does can promote a simulated branch to observed, so
"possible" can never be read as "actual".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Hashable, Sequence


@dataclass(frozen=True)
class Branch:
    """One node of a possible-world tree."""

    identity: str
    state: Hashable
    parent: str | None
    intervention: str | None
    assumptions: frozenset[str]
    cost: float
    status: str = "SIMULATED"

    def is_root(self) -> bool:
        return self.parent is None


@dataclass(frozen=True)
class BranchWorld:
    """A finite tree of interventions with terminal values and recorded evidence.

    ``evidence`` holds facts already observed.  ``contradictions`` maps an
    assumption to the evidence it contradicts, so a counterfactual whose premise
    denies the record can be rejected before any effort is spent on it.

    ``bound`` must be an upper bound on the value reachable from a state for the
    branch-and-bound experiment to be exact; ``admissible_bound`` records whether
    the world claims that property, and the oracle checks it.
    """

    name: str
    root: Hashable
    children: Callable[[Hashable], Sequence[tuple[str, Hashable, float, frozenset[str]]]]
    value: Callable[[Hashable], float]
    is_terminal: Callable[[Hashable], bool]
    bound: Callable[[Hashable], float]
    evidence: frozenset[str] = frozenset()
    contradictions: dict[str, str] = field(default_factory=dict)
    admissible_bound: bool = True
    novelty: Callable[[Hashable], float] | None = None
    """Declared novelty of a state.  Supplied by the world, never inferred from a
    string form: novelty is a property of the domain, and a proxy for it would
    make the novelty-versus-value experiment a test of the proxy instead."""
    note: str = ""

    def consistent(self, assumptions: frozenset[str]) -> tuple[bool, str | None]:
        for assumption in sorted(assumptions):
            conflicting = self.contradictions.get(assumption)
            if conflicting is not None and conflicting in self.evidence:
                return False, f"{assumption} contradicts recorded evidence {conflicting}"
        return True, None

    # --- oracle ----------------------------------------------------------
    def enumerate_leaves(self, limit: int = 200_000) -> list[dict[str, object]]:
        """Every consistent leaf with its value and path cost."""
        out: list[dict[str, object]] = []
        stack: list[tuple[Hashable, tuple[str, ...], float, frozenset[str]]] = [
            (self.root, (), 0.0, frozenset())
        ]
        while stack and len(out) < limit:
            state, path, cost, assumptions = stack.pop()
            ok, _reason = self.consistent(assumptions)
            if not ok:
                continue
            if self.is_terminal(state):
                out.append(
                    {
                        "state": state,
                        "path": path,
                        "cost": cost,
                        "value": self.value(state),
                        "assumptions": sorted(assumptions),
                    }
                )
                continue
            for name, child, step, new_assumptions in self.children(state):
                stack.append((child, path + (name,), cost + step, assumptions | new_assumptions))
        return out

    def best_leaf(self) -> dict[str, object]:
        leaves = self.enumerate_leaves()
        if not leaves:
            return {"found": False, "leaves": 0}
        best = max(leaves, key=lambda item: (item["value"], -float(item["cost"])))
        return {"found": True, "leaves": len(leaves), **best}

    def bound_is_admissible(self) -> dict[str, object]:
        """Check ``bound(s) >= max value reachable from s`` on every state."""
        violations: list[dict[str, object]] = []
        checked = 0
        stack: list[tuple[Hashable, frozenset[str]]] = [(self.root, frozenset())]
        seen: set[Hashable] = set()
        while stack:
            state, assumptions = stack.pop()
            if state in seen:
                continue
            seen.add(state)
            checked += 1
            reachable = self._max_reachable(state)
            if reachable is not None and self.bound(state) < reachable - 1e-9:
                violations.append(
                    {"state": state, "bound": self.bound(state), "reachable": reachable}
                )
            if not self.is_terminal(state):
                for _name, child, _step, new_assumptions in self.children(state):
                    stack.append((child, assumptions | new_assumptions))
        return {
            "states_checked": checked,
            "admissible": not violations,
            "violations": violations[:4],
            "claimed": self.admissible_bound,
        }

    def _max_reachable(self, state: Hashable) -> float | None:
        if self.is_terminal(state):
            return self.value(state)
        best: float | None = None
        for _name, child, _step, _assumptions in self.children(state):
            candidate = self._max_reachable(child)
            if candidate is not None and (best is None or candidate > best):
                best = candidate
        return best


# --- A/C. a world where a valid bound makes pruning safe ------------------
def bounded_world() -> BranchWorld:
    """A depth-3 binary tree of interventions with a genuine upper bound.

    Leaf value is the sum of the digits of the path, so ``bound(s)`` = current sum
    plus 1 per remaining level is a true upper bound.  Branch and bound must
    therefore return the exhaustive optimum while expanding fewer nodes.
    """
    depth_limit = 3

    def children(state):
        level, total = state
        if level >= depth_limit:
            return ()
        return (
            ("keep", (level + 1, total), 1.0, frozenset()),
            ("push", (level + 1, total + 1), 1.0, frozenset({f"push@{level}"})),
        )

    return BranchWorld(
        name="bounded",
        root=(0, 0),
        children=children,
        value=lambda state: float(state[1]),
        is_terminal=lambda state: state[0] >= depth_limit,
        bound=lambda state: float(state[1] + (depth_limit - state[0])),
        note="an admissible bound makes pruning safe and exact",
    )


# --- B. beam search loses the optimum ------------------------------------
def trap_world(width: int = 1) -> BranchWorld:
    """The KETAMINE anti-world for greedy breadth limits.

    Two first moves: ``bait`` looks better immediately (intermediate value 5, but
    every completion caps at 6) while ``lead`` looks worse (intermediate value 0)
    and is the only route to 100.  Any layered beam of width 1 keeps ``bait`` and
    can never reach the optimum -- and no bound is available to save it, because
    the world declares its bound inadmissible.

    COUNTEREXAMPLE, by construction: beam search with width ``w`` strictly less
    than the number of first moves discards the unique optimal prefix whenever the
    optimal prefix has the worst immediate score.  Increasing ``w`` to the
    branching factor recovers it, which is exhaustive search at that level.
    """

    def children(state):
        if state == "root":
            return (
                ("bait", "bait", 1.0, frozenset()),
                ("lead", "lead", 1.0, frozenset()),
            )
        if state == "bait":
            return (("bait_end", "bait_leaf", 1.0, frozenset()),)
        if state == "lead":
            return (("lead_end", "lead_leaf", 1.0, frozenset()),)
        return ()

    values = {"bait_leaf": 6.0, "lead_leaf": 100.0}
    # A deliberately misleading heuristic: it scores `bait` well and `lead` badly.
    immediate = {"root": 0.0, "bait": 5.0, "lead": 0.0, "bait_leaf": 6.0, "lead_leaf": 100.0}
    return BranchWorld(
        name="trap",
        root="root",
        children=children,
        value=lambda state: values.get(state, 0.0),
        is_terminal=lambda state: state in values,
        bound=lambda state: immediate[state],
        admissible_bound=False,
        note="the optimal prefix has the worst immediate score",
    )


# --- D. a counterfactual that contradicts the evidence -------------------
def contradictory_evidence_world() -> BranchWorld:
    """One branch assumes something the record already denies.

    Evidence says ``test_failed``.  The ``assume_tests_passed`` branch carries an
    assumption that contradicts it, and leads to the highest nominal value.  A
    search that maximises value without a consistency check takes it; KETAMINE
    must reject it and settle for the best *consistent* branch.
    """

    def children(state):
        if state == "root":
            return (
                ("assume_tests_passed", "fantasy", 1.0, frozenset({"tests_passed"})),
                ("fix_then_retest", "repair", 1.0, frozenset()),
                ("revert", "reverted", 1.0, frozenset()),
            )
        return ()

    values = {"fantasy": 50.0, "repair": 8.0, "reverted": 3.0}
    return BranchWorld(
        name="contradictory_evidence",
        root="root",
        children=children,
        value=lambda state: values.get(state, 0.0),
        is_terminal=lambda state: state in values,
        bound=lambda state: max(values.values()) if state == "root" else values.get(state, 0.0),
        evidence=frozenset({"test_failed"}),
        contradictions={"tests_passed": "test_failed"},
        note="the highest-value branch denies the evidence and must be rejected",
    )


# --- E/F. novelty is not value ------------------------------------------
def novelty_trap_world(novel_branches: int = 12) -> BranchWorld:
    """Many mutually dissimilar branches, all worthless; one dull branch pays.

    Each ``novel_k`` leads to a distinct state (maximal pairwise diversity) worth
    1.  ``familiar`` looks like the root and is worth 20.  A diversity- or
    novelty-driven selector spends the whole budget on the novel set.

    Distinction demonstrated: NOVELTY != VALUE.  Diversity is a hedge against
    correlated error, not evidence of quality; with a finite budget it can consume
    everything.
    """

    def children(state):
        if state == "root":
            options = [
                (f"novel_{index}", f"novel_{index}", 1.0, frozenset())
                for index in range(novel_branches)
            ]
            options.append(("familiar", "familiar", 1.0, frozenset()))
            return tuple(options)
        return ()

    def value(state):
        if state == "familiar":
            return 20.0
        if isinstance(state, str) and state.startswith("novel_"):
            return 1.0
        return 0.0

    def novelty(state):
        if isinstance(state, str) and state.startswith("novel_"):
            return 1.0
        return 0.0

    return BranchWorld(
        name="novelty_trap",
        root="root",
        children=children,
        value=value,
        is_terminal=lambda state: state != "root",
        bound=lambda state: 20.0 if state == "root" else value(state),
        novelty=novelty,
        note="maximal declared novelty, minimal value",
    )
