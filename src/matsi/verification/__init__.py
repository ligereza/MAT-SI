"""Verification capability: propositional formulas, CNF, SAT, equivalence.

No external solver is available on the reference machine and none is required:
this package implements a deterministic DPLL solver and a Tseitin encoding in the
standard library, so every equivalence claim MAT-SI makes can be *checked*
offline instead of asserted.  ``docs/autonomous-operators/toolbox.md`` records
why an external SMT dependency was declined and what the fallback costs.
"""

from .formula import (
    AND,
    Formula,
    IFF,
    NOT,
    OR,
    VAR,
    XOR,
    CONST,
    evaluate,
    variables_of,
)
from .cnf import CNF, tseitin
from .sat import SatResult, solve_sat, is_satisfiable, is_tautology
from .equivalence import (
    equivalent_by_exhaustion,
    equivalent_by_sat,
    equivalent_over_domain,
)

__all__ = [
    "AND",
    "CNF",
    "CONST",
    "Formula",
    "IFF",
    "NOT",
    "OR",
    "SatResult",
    "VAR",
    "XOR",
    "equivalent_by_exhaustion",
    "equivalent_by_sat",
    "equivalent_over_domain",
    "evaluate",
    "is_satisfiable",
    "is_tautology",
    "solve_sat",
    "tseitin",
    "variables_of",
]
