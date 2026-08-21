"""Propositional formulas as immutable tuples.

A formula is one of

    ("const", bool)
    ("var", name)
    ("not", f)
    ("and", f, g)   ("or", f, g)   ("xor", f, g)   ("iff", f, g)

Tuples are used rather than classes so a formula is hashable, comparable and
canonically serialisable with the existing ``canonical_text``, which keeps it
usable as a represented object inside the MAT-SI kernel.
"""

from __future__ import annotations

from typing import Any, Hashable, Mapping

Formula = tuple


def CONST(value: bool) -> Formula:
    return ("const", bool(value))


def VAR(name: Hashable) -> Formula:
    return ("var", name)


def NOT(inner: Formula) -> Formula:
    return ("not", inner)


def AND(*parts: Formula) -> Formula:
    if not parts:
        return CONST(True)
    result = parts[0]
    for part in parts[1:]:
        result = ("and", result, part)
    return result


def OR(*parts: Formula) -> Formula:
    if not parts:
        return CONST(False)
    result = parts[0]
    for part in parts[1:]:
        result = ("or", result, part)
    return result


def XOR(left: Formula, right: Formula) -> Formula:
    return ("xor", left, right)


def IFF(left: Formula, right: Formula) -> Formula:
    return ("iff", left, right)


def variables_of(formula: Formula) -> tuple[Hashable, ...]:
    """Variable names in first-appearance order (deterministic)."""
    seen: list[Hashable] = []

    def walk(node: Formula) -> None:
        kind = node[0]
        if kind == "var":
            if node[1] not in seen:
                seen.append(node[1])
        elif kind == "const":
            return
        else:
            for child in node[1:]:
                walk(child)

    walk(formula)
    return tuple(seen)


def evaluate(formula: Formula, assignment: Mapping[Hashable, bool]) -> bool:
    """Evaluate under a total assignment; missing variables raise."""
    kind = formula[0]
    if kind == "const":
        return bool(formula[1])
    if kind == "var":
        if formula[1] not in assignment:
            raise KeyError(f"variable {formula[1]!r} is unassigned")
        return bool(assignment[formula[1]])
    if kind == "not":
        return not evaluate(formula[1], assignment)
    left = evaluate(formula[1], assignment)
    right = evaluate(formula[2], assignment)
    if kind == "and":
        return left and right
    if kind == "or":
        return left or right
    if kind == "xor":
        return left != right
    if kind == "iff":
        return left == right
    raise ValueError(f"unknown connective {kind!r}")


def size(formula: Formula) -> int:
    """Number of nodes; used as one of the competing cost functions."""
    kind = formula[0]
    if kind in ("const", "var"):
        return 1
    return 1 + sum(size(child) for child in formula[1:])
