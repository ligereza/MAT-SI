"""Terms, patterns and cost functions for the symbolic layer.

A term is a tuple ``(head, *children)``:

    ("const", 3)          a leaf carrying a value
    ("var", "x")          a leaf carrying a name
    ("+", left, right)    an operator node

A pattern is a term that may also contain ``("?", name)`` holes.  Using tuples
keeps every term hashable and canonically serialisable by the existing
``canonical_text``, so a term is a represented MAT-SI object and not a new
parallel universe of classes.
"""

from __future__ import annotations

from typing import Any, Callable, Hashable, Iterator

Term = tuple
Pattern = tuple

LEAF_HEADS = frozenset({"const", "var"})


def is_leaf(term: Term) -> bool:
    return term[0] in LEAF_HEADS


def is_hole(pattern: Pattern) -> bool:
    return pattern[0] == "?"


def children(term: Term) -> tuple[Term, ...]:
    return () if is_leaf(term) else tuple(term[1:])


def head_key(term: Term) -> Hashable:
    """The identity of a node's operator, including leaf payloads."""
    return term if is_leaf(term) else term[0]


def subterms(term: Term) -> Iterator[Term]:
    yield term
    for child in children(term):
        yield from subterms(child)


def size(term: Term) -> int:
    """Number of nodes counted as a tree (shared structure counted twice)."""
    return 1 + sum(size(child) for child in children(term))


def depth(term: Term) -> int:
    kids = children(term)
    return 1 if not kids else 1 + max(depth(child) for child in kids)


def operators(term: Term) -> frozenset[str]:
    if is_leaf(term):
        return frozenset()
    return frozenset({term[0]}).union(*(operators(child) for child in children(term)))


def to_text(term: Term) -> str:
    """Readable infix-ish rendering, used only in reports."""
    if term[0] == "const":
        return str(term[1])
    if term[0] == "var":
        return str(term[1])
    if term[0] == "?":
        return f"?{term[1]}"
    kids = [to_text(child) for child in children(term)]
    if len(kids) == 2:
        return f"({kids[0]} {term[0]} {kids[1]})"
    return f"{term[0]}({', '.join(kids)})"


# --- cost functions -------------------------------------------------------
# A cost function maps a head key and the already-computed child costs to the
# cost of the node.  It must be monotone non-decreasing in each child cost for
# the extraction fixpoint to be the least one; see egraph.extract.

CostFunction = Callable[[Hashable, tuple[float, ...]], float]


def tree_size_cost(head: Hashable, child_costs: tuple[float, ...]) -> float:
    """Total node count: the minimum-description proxy."""
    return 1.0 + sum(child_costs)


def depth_cost(head: Hashable, child_costs: tuple[float, ...]) -> float:
    """Critical path length: the maximum-parallelism proxy."""
    return 1.0 + (max(child_costs) if child_costs else 0.0)


def operation_count_cost(head: Hashable, child_costs: tuple[float, ...]) -> float:
    """Count operator nodes only; leaves are free."""
    own = 0.0 if isinstance(head, tuple) else 1.0
    return own + sum(child_costs)


def weighted_execution_cost(weights: dict[str, float], default: float = 1.0) -> CostFunction:
    """Machine-cost proxy: each operator carries its own price."""

    def cost(head: Hashable, child_costs: tuple[float, ...]) -> float:
        if isinstance(head, tuple):
            return 0.0
        return weights.get(head, default) + sum(child_costs)

    return cost


def interpretability_proxy_cost(head: Hashable, child_costs: tuple[float, ...]) -> float:
    """A deliberately different objective: punish nesting harder than width.

    This is a *proxy*, not a measurement of human interpretability.  It exists to
    show that the extraction result depends on the objective, which is the point
    of keeping several.
    """
    if isinstance(head, tuple):
        return 1.0
    return 1.0 + 1.5 * (max(child_costs) if child_costs else 0.0) + 0.5 * sum(child_costs)


DEFAULT_COSTS: dict[str, CostFunction] = {
    "tree_size": tree_size_cost,
    "depth": depth_cost,
    "operation_count": operation_count_cost,
    "execution": weighted_execution_cost({"*": 4.0, "+": 1.0, "<<": 1.0, "-": 1.0}),
    "interpretability_proxy": interpretability_proxy_cost,
}


def evaluate_term(term: Term, environment: dict[str, Any]) -> Any:
    """Evaluate an arithmetic term over Python integers.

    Used by the finite-domain verifier; it is a host semantics, declared as such.
    """
    head = term[0]
    if head == "const":
        return term[1]
    if head == "var":
        return environment[term[1]]
    values = [evaluate_term(child, environment) for child in children(term)]
    if head == "+":
        return values[0] + values[1]
    if head == "-":
        return values[0] - values[1]
    if head == "*":
        return values[0] * values[1]
    if head == "<<":
        return values[0] << values[1]
    if head == "neg":
        return -values[0]
    raise ValueError(f"unknown operator {head!r}")
