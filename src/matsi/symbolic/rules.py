"""The arithmetic rewrite rule set, plus an independent soundness check.

A rule set is not trusted because it looks like algebra.  ``rule_soundness_report``
evaluates both sides of every rule on every point of a finite integer domain and
reports which rules are valid there and which are not.  A rule that fails is kept
in the report rather than deleted, because a failing rule is evidence about the
signature, and the caller decides whether to use it.

The finite check is complete only over the domain it names: agreement on
``[-4, 4]`` is not a proof of an identity over the integers.  That scope travels
with the result.
"""

from __future__ import annotations

from itertools import product
from typing import Any, Sequence

from .egraph import Rule
from .terms import Term, evaluate_term, is_hole, is_leaf

A = ("?", "a")
B = ("?", "b")
C = ("?", "c")


ARITHMETIC_RULES: tuple[Rule, ...] = (
    Rule("comm_add", ("+", A, B), ("+", B, A)),
    Rule("comm_mul", ("*", A, B), ("*", B, A)),
    Rule("assoc_add", ("+", ("+", A, B), C), ("+", A, ("+", B, C))),
    Rule("assoc_mul", ("*", ("*", A, B), C), ("*", A, ("*", B, C))),
    Rule("add_zero", ("+", A, ("const", 0)), A),
    Rule("mul_one", ("*", A, ("const", 1)), A),
    Rule("mul_zero", ("*", A, ("const", 0)), ("const", 0), bidirectional=False),
    Rule("double_is_add", ("*", A, ("const", 2)), ("+", A, A)),
    Rule("double_is_shift", ("*", A, ("const", 2)), ("<<", A, ("const", 1))),
    Rule("quad_is_shift", ("*", A, ("const", 4)), ("<<", A, ("const", 2))),
    Rule("distribute", ("*", A, ("+", B, C)), ("+", ("*", A, B), ("*", A, C))),
    Rule("factor_common", ("+", ("*", A, B), ("*", A, C)), ("*", A, ("+", B, C))),
    Rule("sub_is_neg_add", ("-", A, B), ("+", A, ("neg", B)), bidirectional=True),
)


def pattern_holes(pattern: Term) -> tuple[str, ...]:
    names: list[str] = []

    def walk(node: Term) -> None:
        if is_hole(node):
            if node[1] not in names:
                names.append(node[1])
            return
        if is_leaf(node):
            return
        for child in node[1:]:
            walk(child)

    walk(pattern)
    return tuple(names)


def _instantiate(pattern: Term, binding: dict[str, int]) -> Term:
    if is_hole(pattern):
        return ("const", binding[pattern[1]])
    if is_leaf(pattern):
        return pattern
    return (pattern[0], *(_instantiate(child, binding) for child in pattern[1:]))


def rule_soundness_report(
    rules: Sequence[Rule] = ARITHMETIC_RULES,
    domain: Sequence[int] = range(-4, 5),
) -> dict[str, Any]:
    """Check every rule on every point of ``domain`` for each of its holes."""
    domain = tuple(domain)
    valid: list[str] = []
    invalid: list[dict[str, Any]] = []
    for rule in rules:
        holes = tuple(dict.fromkeys(pattern_holes(rule.lhs) + pattern_holes(rule.rhs)))
        failure: dict[str, Any] | None = None
        checked = 0
        for values in product(domain, repeat=len(holes)):
            binding = dict(zip(holes, values))
            left = _instantiate(rule.lhs, binding)
            right = _instantiate(rule.rhs, binding)
            try:
                left_value = evaluate_term(left, {})
                right_value = evaluate_term(right, {})
            except (ValueError, TypeError) as exc:
                failure = {"rule": rule.name, "binding": binding, "error": type(exc).__name__}
                break
            checked += 1
            if left_value != right_value:
                failure = {
                    "rule": rule.name,
                    "binding": binding,
                    "left_value": left_value,
                    "right_value": right_value,
                }
                break
        if failure is None:
            valid.append(rule.name)
        else:
            invalid.append(failure)
    return {
        "domain": [min(domain), max(domain)],
        "rules_checked": len(rules),
        "valid_on_domain": sorted(valid),
        "invalid_on_domain": invalid,
        "scope": "validity on this finite integer domain only; not a proof over Z",
    }
