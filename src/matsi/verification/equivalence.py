"""Equivalence checking: exhaustive, SAT-based, and finite-domain.

X-ANA-X may never accept a re-representation because it "looks equivalent".  Every
transformation it applies is checked by one of these, and the checker used is
recorded with the result so a weaker check can never be mistaken for a stronger
one:

* ``equivalent_by_exhaustion`` -- complete for propositional formulas, cost
  ``2^n``; the ground truth used to validate the other two.
* ``equivalent_by_sat`` -- complete, via UNSAT of ``f XOR g``; returns a
  counterexample assignment when the two differ.
* ``equivalent_over_domain`` -- complete only over the finite domain given.  It
  reports the domain it checked, because agreement on a finite domain is not
  agreement in general.
"""

from __future__ import annotations

from itertools import product
from typing import Any, Callable, Hashable, Sequence

from .cnf import assert_formula
from .formula import Formula, XOR, evaluate, variables_of
from .sat import solve_sat


def equivalent_by_exhaustion(
    left: Formula, right: Formula
) -> tuple[bool, dict[Hashable, bool] | None, dict[str, Any]]:
    """Truth-table equivalence.  Complete; exponential in the variable count."""
    names = tuple(dict.fromkeys(variables_of(left) + variables_of(right)))
    rows = 0
    for values in product((False, True), repeat=len(names)):
        assignment = dict(zip(names, values))
        rows += 1
        if evaluate(left, assignment) != evaluate(right, assignment):
            return False, assignment, {"checker": "exhaustion", "rows": rows, "variables": len(names)}
    return True, None, {"checker": "exhaustion", "rows": rows, "variables": len(names)}


def equivalent_by_sat(
    left: Formula, right: Formula
) -> tuple[bool, dict[Hashable, bool] | None, dict[str, Any]]:
    """Equivalence by deciding ``UNSAT(left XOR right)``.

    PROVED: ``left`` and ``right`` are equivalent iff ``left XOR right`` is
    unsatisfiable, since the XOR is satisfied exactly by assignments where the two
    formulas disagree.
    """
    cnf = assert_formula(XOR(left, right))
    result = solve_sat(cnf)
    measurement = {"checker": "sat", **cnf.stats(), **result.as_measurement()}
    if result.satisfiable:
        return False, cnf.model_for_named(result.model), measurement
    return True, None, measurement


def equivalent_over_domain(
    left: Callable[..., Any],
    right: Callable[..., Any],
    arity: int,
    domain: Sequence[Any],
) -> tuple[bool, tuple[Any, ...] | None, dict[str, Any]]:
    """Compare two callables on every point of ``domain ** arity``.

    Used for arithmetic re-representations where no propositional encoding is
    available.  The returned measurement names the domain so the scope of the
    claim travels with it.
    """
    points = 0
    for values in product(domain, repeat=arity):
        points += 1
        if left(*values) != right(*values):
            return (
                False,
                values,
                {"checker": "finite_domain", "points": points, "domain_size": len(domain), "arity": arity},
            )
    return (
        True,
        None,
        {
            "checker": "finite_domain",
            "points": points,
            "domain_size": len(domain),
            "arity": arity,
            "scope": "agreement on this finite domain only; not a general identity",
        },
    )
