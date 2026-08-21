"""Representation tasks for X-ANA-X.

A task is not "make it smaller".  A task is:

    start from representation R0,
    reach a representation that ENABLES a required operation,
    while PRESERVING a declared invariant,
    with equivalence VERIFIED, not assumed.

``enables`` and ``invariants`` are separate predicates on purpose: a rewrite can
enable the operation and break the invariant, which must be rejected even when it
is the smallest or cheapest form available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from ..symbolic.egraph import Rule
from ..symbolic.rules import ARITHMETIC_RULES
from ..symbolic.terms import Term, depth, operators, size


def variable_occurrences(term: Term, name: str) -> int:
    if term[0] == "var":
        return 1 if term[1] == name else 0
    if term[0] == "const":
        return 0
    return sum(variable_occurrences(child, name) for child in term[1:])


@dataclass(frozen=True)
class RepresentationTask:
    """One re-representation problem with an explicit downstream requirement."""

    name: str
    start: Term
    rules: tuple[Rule, ...]
    enables: Callable[[Term], bool]
    enables_description: str
    invariants: tuple[tuple[str, Callable[[Term], bool]], ...]
    variables: tuple[str, ...]
    domain: tuple[int, ...]
    note: str = ""

    def invariant_status(self, term: Term) -> dict[str, bool]:
        return {name: bool(predicate(term)) for name, predicate in self.invariants}

    def preserves_invariants(self, term: Term) -> bool:
        return all(self.invariant_status(term).values())


def shift_only_task() -> RepresentationTask:
    """Target machine has no multiplier: the representation must avoid ``*``.

    ``x * 4`` must become ``x << 2``.  Size alone would not force this: both forms
    have three nodes.  The *enabling predicate* forces it.
    """
    return RepresentationTask(
        name="shift_only_machine",
        start=("*", ("var", "x"), ("const", 4)),
        rules=ARITHMETIC_RULES,
        enables=lambda term: "*" not in operators(term),
        enables_description="evaluable on a machine without a multiply instruction",
        invariants=(
            ("no_multiplication", lambda term: "*" not in operators(term)),
        ),
        variables=("x",),
        domain=tuple(range(-8, 9)),
        note="enabling predicate, not size, selects the representation",
    )


def linear_read_task() -> RepresentationTask:
    """The X-ANA-X anti-world: the cheapest form destroys a needed invariant.

    The consumer is a single-read streaming machine: every variable may be read at
    most once.  Starting from ``x * 2`` the equality-saturated class contains

        x * 2      one read of x, uses a multiply
        x + x      two reads of x, no multiply  -- cheaper on the execution cost
        x << 1     one read of x, no multiply

    ``x + x`` is strictly cheaper under the weighted execution cost and is
    perfectly equivalent as a function, yet it violates ``single_read`` and must be
    rejected.  A selector driven by cost or byte size takes it; a selector driven
    by invariant preservation does not.
    """
    return RepresentationTask(
        name="single_read_machine",
        start=("*", ("var", "x"), ("const", 2)),
        rules=ARITHMETIC_RULES,
        enables=lambda term: "*" not in operators(term),
        enables_description="evaluable on a machine without a multiply instruction",
        invariants=(
            ("no_multiplication", lambda term: "*" not in operators(term)),
            ("single_read", lambda term: variable_occurrences(term, "x") <= 1),
        ),
        variables=("x",),
        domain=tuple(range(-8, 9)),
        note="the cheapest equivalent form breaks the single-read invariant",
    )


def parallel_depth_task() -> RepresentationTask:
    """Latency-bound consumer: the critical path must be short.

    ``((x + x) + x) + x`` is a depth-4 chain.  An equivalent balanced or
    multiplicative form has smaller depth, which is the operation being enabled.
    """
    chain = ("+", ("+", ("+", ("var", "x"), ("var", "x")), ("var", "x")), ("var", "x"))
    return RepresentationTask(
        name="latency_bound_machine",
        start=chain,
        rules=ARITHMETIC_RULES,
        enables=lambda term: depth(term) <= 3,
        enables_description="critical path of at most three levels",
        invariants=(("depth_at_most_3", lambda term: depth(term) <= 3),),
        variables=("x",),
        domain=tuple(range(-6, 7)),
        note="the same value with a shorter critical path",
    )


def hidden_decomposition_task() -> RepresentationTask:
    """A rewrite that exposes a factorisation the original form hides.

    ``x*3 + x*5`` and ``x*(3+5)`` denote the same function, but only the second
    exposes a single multiplication by a constant, which is the operation a
    strength-reduction pass can consume.
    """
    start = ("+", ("*", ("var", "x"), ("const", 3)), ("*", ("var", "x"), ("const", 5)))
    return RepresentationTask(
        name="expose_common_factor",
        start=start,
        rules=ARITHMETIC_RULES,
        enables=lambda term: term[0] == "*" or "*" not in operators(term),
        enables_description="a single top-level product, or no product at all",
        invariants=(
            ("at_most_one_multiplication", lambda term: _count_operator(term, "*") <= 1),
        ),
        variables=("x",),
        domain=tuple(range(-6, 7)),
        note="rewriting exposes a decomposition the source form hides",
    )


def _count_operator(term: Term, symbol: str) -> int:
    if term[0] in ("var", "const"):
        return 0
    return (1 if term[0] == symbol else 0) + sum(
        _count_operator(child, symbol) for child in term[1:]
    )
