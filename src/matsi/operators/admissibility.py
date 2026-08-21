"""Which kind of operation is admissible, decided by the structure of the state.

This is the module that answers the branch's central question.  No operator is
selected by name: each one declares a *structural precondition*, and the
precondition is evaluated against ``S = (R, O, H, M, B)``.

    VIZZ      requires residual uncertainty about a target AND an unperformed,
              affordable experiment with strictly positive information about it.
    CODEINE   requires an existing trajectory with at least two measured utility
              steps AND budget for one more step.
    X-ANA-X   requires an equivalence class with at least two distinct
              representations of the current object.
    KETAMINE  requires at least two mutually exclusive consistent branches.

Two properties are kept apart on purpose:

    admissible  the structure needed by the operator is present
    useful      acting would change something the state does not already have

An operator can be admissible and useless (X-ANA-X on a representation that
already enables the required operation).

NO UNIVERSAL SCORE.  The quantities the four operators produce -- bits about a
target, utility per step, invariants preserved, value of a simulated branch -- are
not commensurable, and this module never adds them.  When more than one operator
is admissible and no external preference is supplied, the verdict is
``INCOMPARABLE``.  That is a result, not a gap.

LITERATURE AUDIT for the selection layer.
* Algorithm selection as a formal problem -- ESTABLISHED (Rice, *The algorithm
  selection problem*, Advances in Computers 1976).
* Metareasoning and the value of computation -- ESTABLISHED (Horvitz 1987;
  Russell & Wefald, *Principles of metareasoning*, Artificial Intelligence 1991).
* Algorithm portfolios and hyper-heuristics -- ESTABLISHED (Gomes & Selman 2001;
  Burke et al. 2013).
* Applying value-of-computation *across operators whose value units differ* --
  UNKNOWN.  Russell & Wefald assume a common utility; here there is none, which is
  precisely why the honest answer is a partial order plus abstention rather than a
  meta-utility.  No novelty is claimed: the negative observation is that the
  standard theory does not apply without a commensurating assumption we decline to
  make.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Hashable, Sequence

from ..substrate import State


@dataclass(frozen=True)
class Trigger:
    """The structural verdict for one operator on one state."""

    operator: str
    admissible: bool
    useful: bool
    condition: str
    witness: dict[str, Any]
    reason: str

    def as_measurement(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "admissible": self.admissible,
            "useful": self.useful,
            "condition": self.condition,
            "witness": self.witness,
            "reason": self.reason,
        }


def _vizz_trigger(state: State) -> Trigger:
    condition = "H(T) > 0 and some unperformed affordable experiment has I(T;Y) > 0"
    belief = state.representation.get("belief")
    if not belief:
        return Trigger("VIZZ", False, False, condition, {}, "no belief over hypotheses in R")
    entropy_bits = float(state.representation.get("target_entropy", 0.0))
    informative = state.representation.get("informative_experiments")
    if informative is None:
        return Trigger(
            "VIZZ",
            entropy_bits > 1e-12,
            entropy_bits > 1e-12,
            condition,
            {"target_entropy_bits": entropy_bits},
            "experiment information not computed; admissibility from entropy alone",
        )
    affordable = [
        item for item in informative if float(item["cost"]) <= state.budget.remaining()
    ]
    positive = [item for item in affordable if float(item["bits"]) > 1e-12]
    admissible = entropy_bits > 1e-12 and bool(positive)
    return Trigger(
        "VIZZ",
        admissible,
        admissible,
        condition,
        {
            "target_entropy_bits": entropy_bits,
            "affordable_experiments": len(affordable),
            "informative_affordable": len(positive),
        },
        "residual target uncertainty with a purchasable reduction"
        if admissible
        else (
            "target already determined"
            if entropy_bits <= 1e-12
            else "no affordable experiment reduces target uncertainty"
        ),
    )


def _codeine_trigger(state: State) -> Trigger:
    condition = "trajectory with >= 2 measured utility steps and budget for one more"
    gains = state.representation.get("gains")
    if gains is None:
        return Trigger("CODEINE", False, False, condition, {}, "no trajectory in R")
    steps = len(tuple(gains))
    budget_left = state.budget.remaining() >= 1
    admissible = steps >= 2 and budget_left
    return Trigger(
        "CODEINE",
        admissible,
        admissible,
        condition,
        {"measured_steps": steps, "budget_remaining": state.budget.remaining()},
        "a measured trajectory exists and can be extended"
        if admissible
        else ("fewer than two measured steps" if steps < 2 else "no budget for another step"),
    )


def _xanax_trigger(state: State) -> Trigger:
    condition = "the equivalence class of R contains >= 2 distinct representations"
    term = state.representation.get("term")
    if term is None:
        return Trigger(
            "X-ANA-X",
            False,
            False,
            condition,
            {},
            "R is not a concrete representation: nothing to rewrite",
        )
    class_size = int(state.representation.get("class_size", 0))
    enabled = bool(state.representation.get("enables_now", False))
    admissible = class_size >= 2
    return Trigger(
        "X-ANA-X",
        admissible,
        admissible and not enabled,
        condition,
        {"class_size": class_size, "required_operation_already_enabled": enabled},
        "several equivalent forms exist"
        if admissible
        else "the equivalence class is a singleton under the available rules",
    )


def _ketamine_trigger(state: State) -> Trigger:
    condition = ">= 2 mutually exclusive branches consistent with the evidence"
    branches = state.representation.get("consistent_branches")
    if branches is None:
        return Trigger("KETAMINE", False, False, condition, {}, "no branch structure in R")
    count = int(branches)
    exhaustive = int(state.representation.get("exhaustive_nodes", 0))
    admissible = count >= 2
    return Trigger(
        "KETAMINE",
        admissible,
        admissible,
        condition,
        {
            "consistent_branches": count,
            "exhaustive_nodes": exhaustive,
            "budget_remaining": state.budget.remaining(),
            "exhaustive_affordable": exhaustive <= state.budget.remaining(),
        },
        "several consistent alternatives remain"
        if admissible
        else "fewer than two consistent branches",
    )


TRIGGERS = (_vizz_trigger, _codeine_trigger, _xanax_trigger, _ketamine_trigger)


def admissible_operators(state: State) -> dict[str, Trigger]:
    """Evaluate every structural precondition against one state."""
    return {trigger.operator: trigger for trigger in (fn(state) for fn in TRIGGERS)}


@dataclass(frozen=True)
class Verdict:
    """What the selection layer can honestly say about one state."""

    admissible: tuple[str, ...]
    useful: tuple[str, ...]
    decision: str
    reason: str
    triggers: dict[str, Trigger]

    def as_measurement(self) -> dict[str, Any]:
        return {
            "admissible": list(self.admissible),
            "useful": list(self.useful),
            "decision": self.decision,
            "reason": self.reason,
            "triggers": {name: item.as_measurement() for name, item in self.triggers.items()},
        }


def select_operation(
    state: State, preference: Sequence[str] | None = None
) -> Verdict:
    """Decide which kind of computation is next, or refuse to decide.

    ``preference`` is an *externally supplied* total order over operator names.  It
    is the only way a tie is broken, and the verdict records that the tie-break was
    external rather than derived.  Without it a genuine tie is ``INCOMPARABLE``.
    """
    triggers = admissible_operators(state)
    admissible = tuple(name for name, item in triggers.items() if item.admissible)
    useful = tuple(name for name, item in triggers.items() if item.admissible and item.useful)
    if not admissible:
        return Verdict(
            (),
            (),
            "ABSTAIN",
            "no operator's structural precondition is satisfied",
            triggers,
        )
    if not useful:
        return Verdict(
            admissible,
            (),
            "STOP",
            "every admissible operator is admissible but useless in this state",
            triggers,
        )
    if len(useful) == 1:
        name = useful[0]
        return Verdict(
            admissible,
            useful,
            f"RUN_{_slug(name)}",
            f"unique useful operator: {triggers[name].reason}",
            triggers,
        )
    if preference:
        ordered = [name for name in preference if name in useful]
        if ordered:
            return Verdict(
                admissible,
                useful,
                f"RUN_{_slug(ordered[0])}",
                "tie broken by an externally supplied preference order, not by a derived score",
                triggers,
            )
    return Verdict(
        admissible,
        useful,
        "INCOMPARABLE",
        "several operators are useful and their value units are not commensurable",
        triggers,
    )


def _slug(name: str) -> str:
    return name.replace("-", "")
