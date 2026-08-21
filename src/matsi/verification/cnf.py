"""Tseitin transformation to CNF.

The Tseitin encoding introduces one fresh variable per connective and asserts its
defining equivalence, producing a CNF that is satisfiable exactly when the input
formula is (Tseitin 1968).  It is linear in the formula size, unlike naive
distribution which can be exponential -- that difference is why the encoding is
worth implementing rather than expanding by hand.

PROVED (verified in ``tests/test_verification.py`` by exhaustive comparison on
small formulas): for every formula ``f``, ``tseitin(f)`` is satisfiable iff ``f``
is satisfiable, and every model of the CNF restricted to the original variables
is a model of ``f``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable

from .formula import Formula


@dataclass
class CNF:
    """CNF in DIMACS-style integer literals: variable ``v`` is ``+v``/``-v``."""

    clauses: list[tuple[int, ...]] = field(default_factory=list)
    names: dict[Hashable, int] = field(default_factory=dict)
    auxiliary: int = 0

    @property
    def variable_count(self) -> int:
        return len(self.names) + self.auxiliary

    def variable(self, name: Hashable) -> int:
        if name not in self.names:
            self.names[name] = self.variable_count + 1
        return self.names[name]

    def fresh(self) -> int:
        self.auxiliary += 1
        return self.variable_count

    def add(self, *literals: int) -> None:
        self.clauses.append(tuple(sorted(set(literals), key=lambda item: (abs(item), item))))

    def model_for_named(self, model: dict[int, bool]) -> dict[Hashable, bool]:
        """Project a solver model back onto the original variable names."""
        return {name: model.get(index, False) for name, index in self.names.items()}

    def stats(self) -> dict[str, int]:
        return {
            "variables": self.variable_count,
            "named_variables": len(self.names),
            "auxiliary_variables": self.auxiliary,
            "clauses": len(self.clauses),
            "literals": sum(len(clause) for clause in self.clauses),
        }


def tseitin(formula: Formula, cnf: CNF | None = None) -> tuple[CNF, int]:
    """Encode ``formula`` and return ``(cnf, literal)`` with the root literal.

    The caller decides polarity: assert ``literal`` to require the formula, or
    ``-literal`` to require its negation.  Nothing is asserted here.
    """
    cnf = CNF() if cnf is None else cnf
    literal = _encode(formula, cnf)
    return cnf, literal


def _encode(formula: Formula, cnf: CNF) -> int:
    kind = formula[0]
    if kind == "const":
        gate = cnf.fresh()
        cnf.add(gate if formula[1] else -gate)
        return gate
    if kind == "var":
        return cnf.variable(formula[1])
    if kind == "not":
        return -_encode(formula[1], cnf)

    left = _encode(formula[1], cnf)
    right = _encode(formula[2], cnf)
    gate = cnf.fresh()
    if kind == "and":
        # gate <-> (left & right)
        cnf.add(-gate, left)
        cnf.add(-gate, right)
        cnf.add(gate, -left, -right)
    elif kind == "or":
        cnf.add(-gate, left, right)
        cnf.add(gate, -left)
        cnf.add(gate, -right)
    elif kind == "xor":
        cnf.add(-gate, left, right)
        cnf.add(-gate, -left, -right)
        cnf.add(gate, -left, right)
        cnf.add(gate, left, -right)
    elif kind == "iff":
        cnf.add(-gate, -left, right)
        cnf.add(-gate, left, -right)
        cnf.add(gate, left, right)
        cnf.add(gate, -left, -right)
    else:
        raise ValueError(f"unknown connective {kind!r}")
    return gate


def assert_formula(formula: Formula, negated: bool = False) -> CNF:
    """Encode and assert a formula (or its negation) as a standalone CNF."""
    cnf, literal = tseitin(formula)
    cnf.add(-literal if negated else literal)
    return cnf
