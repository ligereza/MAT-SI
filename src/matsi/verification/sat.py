"""A deterministic DPLL satisfiability solver.

DPLL (Davis, Putnam, Logemann & Loveland 1962) with unit propagation and pure
literal elimination.  Branching picks the unassigned variable occurring in the
most clauses, breaking ties by index, so the solver is fully deterministic: the
same CNF always produces the same model and the same counters.

Proof status:

* soundness and completeness for finite CNF -- KNOWN_RESULT (DPLL);
  ``tests/test_verification.py`` checks the implementation against exhaustive
  truth tables on all formulas up to a small size, which is an empirical
  validation of *this* implementation, not a proof of it.
* SAT is NP-complete -- KNOWN_RESULT (Cook 1971; Levin 1973).  No polynomial
  behaviour is claimed; ``SatResult`` reports decisions and propagations so the
  cost is measured wherever the solver is used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable, Sequence

from .cnf import CNF, assert_formula
from .formula import Formula, IFF, NOT, XOR


@dataclass
class SatResult:
    satisfiable: bool
    model: dict[int, bool] = field(default_factory=dict)
    decisions: int = 0
    propagations: int = 0
    conflicts: int = 0
    pure_literals: int = 0

    def as_measurement(self) -> dict[str, int | bool]:
        return {
            "satisfiable": self.satisfiable,
            "decisions": self.decisions,
            "propagations": self.propagations,
            "conflicts": self.conflicts,
            "pure_literals": self.pure_literals,
        }


def _simplify(
    clauses: Sequence[tuple[int, ...]], literal: int
) -> list[tuple[int, ...]] | None:
    """Assign ``literal`` true; return the residual clauses or None on conflict."""
    residual: list[tuple[int, ...]] = []
    for clause in clauses:
        if literal in clause:
            continue
        if -literal in clause:
            reduced = tuple(item for item in clause if item != -literal)
            if not reduced:
                return None
            residual.append(reduced)
        else:
            residual.append(clause)
    return residual


def solve_sat(cnf: CNF, node_limit: int = 500_000) -> SatResult:
    """Decide satisfiability of ``cnf`` deterministically."""
    result = SatResult(satisfiable=False)

    def search(clauses: list[tuple[int, ...]], model: dict[int, bool]) -> dict[int, bool] | None:
        if result.decisions > node_limit:
            raise RuntimeError("SAT node limit exceeded")
        # Unit propagation to fixpoint.
        while True:
            units = [clause[0] for clause in clauses if len(clause) == 1]
            if not units:
                break
            literal = units[0]
            result.propagations += 1
            model = dict(model)
            model[abs(literal)] = literal > 0
            simplified = _simplify(clauses, literal)
            if simplified is None:
                result.conflicts += 1
                return None
            clauses = simplified
        if not clauses:
            return model
        # Pure literal elimination.
        occurring = {literal for clause in clauses for literal in clause}
        pure = sorted(
            (literal for literal in occurring if -literal not in occurring),
            key=lambda item: (abs(item), item),
        )
        if pure:
            literal = pure[0]
            result.pure_literals += 1
            model = dict(model)
            model[abs(literal)] = literal > 0
            simplified = _simplify(clauses, literal)
            if simplified is None:
                result.conflicts += 1
                return None
            return search(simplified, model)
        # Branch on the most frequently occurring variable.
        counts: dict[int, int] = {}
        for clause in clauses:
            for literal in clause:
                counts[abs(literal)] = counts.get(abs(literal), 0) + 1
        variable = min(counts, key=lambda item: (-counts[item], item))
        for value in (True, False):
            result.decisions += 1
            literal = variable if value else -variable
            simplified = _simplify(clauses, literal)
            if simplified is None:
                result.conflicts += 1
                continue
            child = dict(model)
            child[variable] = value
            found = search(simplified, child)
            if found is not None:
                return found
        return None

    model = search([tuple(clause) for clause in cnf.clauses], {})
    if model is None:
        result.satisfiable = False
        result.model = {}
    else:
        result.satisfiable = True
        for index in range(1, cnf.variable_count + 1):
            model.setdefault(index, False)
        result.model = model
    return result


def is_satisfiable(formula: Formula) -> tuple[bool, dict[Hashable, bool], SatResult]:
    """Decide satisfiability of a formula and return a named model if any."""
    cnf = assert_formula(formula)
    result = solve_sat(cnf)
    return result.satisfiable, cnf.model_for_named(result.model), result


def is_tautology(formula: Formula) -> tuple[bool, dict[Hashable, bool], SatResult]:
    """A formula is a tautology iff its negation is unsatisfiable.

    Returns ``(is_tautology, counterexample, measurement)``; the counterexample is
    a falsifying assignment when the answer is no, and empty otherwise.
    """
    cnf = assert_formula(formula, negated=True)
    result = solve_sat(cnf)
    return (not result.satisfiable), cnf.model_for_named(result.model), result
