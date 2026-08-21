"""X-ANA-X: change the representation while tracking equivalence and residue.

FORMAL OBJECT.  Let ``R0`` be a term, ``E`` a set of rewrite rules, and ``~`` the
congruence they generate.  Let ``Inv`` be a finite set of predicates (the declared
invariants) and ``Enables`` a predicate naming the operation a consumer needs.
X-ANA-X searches the equivalence class ``[R0]`` for a term ``R`` with

    R ~ R0        verified, not assumed
    Inv(R)        every declared invariant holds
    Enables(R)    the required downstream operation becomes available

and reports the residue: what the rewrite lost.

ACTION SPACE.  An equivalence-preserving transformation of the representation.
It buys no observation, decides nothing about a trajectory, and opens no branch.

LITERATURE AUDIT.
* E-graphs and equality saturation -- ESTABLISHED (Nelson 1980; Willsey, Nandi,
  Wang, Flatt, Tatlock & Panchekha, *egg*, POPL 2021).
* Congruence closure as the decision procedure for the theory of equality with
  uninterpreted functions -- KNOWN_RESULT (Downey, Sethi & Tarjan 1980).
* Optimal extraction from an e-graph under a cost with shared subexpressions is
  NP-hard -- KNOWN_RESULT (discussed in the egg paper; Stepp 2011).  Only the
  tree-cost least fixpoint is computed, and that limitation is declared.
* Term rewriting, normal forms, confluence and termination -- ESTABLISHED (Baader
  & Nipkow, *Term Rewriting and All That*, 1998).
* Selecting a representation by a downstream objective rather than by size --
  IMPORTED from compiler strength reduction and superoptimisation practice; not a
  new theory.

WHAT REMAINS SPECIFIC TO MAT-SI.  The separation of three predicates that are
usually collapsed into one cost: ``Enables`` (what becomes possible),
``Inv`` (what must survive), and the cost vector (how expensive the result is).
Keeping them apart is what lets the operator *reject* the cheapest equivalent
form.  That rejection is the result; the search machinery is imported.

FAILURE REGIME.  ``worlds.linear_read_task`` is the anti-world: the cheapest and
smallest equivalent representation destroys a required invariant.  Any selector
driven by size or execution cost takes it.  A second failure regime is saturation
itself -- with associativity, commutativity and distributivity the class is
unbounded, so the search reports ``saturated=False`` and its verdict is relative
to the fragment explored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..symbolic.egraph import EGraph
from ..symbolic.terms import DEFAULT_COSTS, Term, depth, evaluate_term, operators, size, to_text
from ..substrate import Candidate, Declaration, Decision, State
from ..verification.equivalence import equivalent_over_domain
from ..worlds.expression_world import RepresentationTask


@dataclass
class XanaxConfig:
    """Search limits and the optional downstream objective."""

    objective: str | None = None
    """Name of a cost in ``DEFAULT_COSTS``.  ``None`` means the consumer supplied
    no preference, so several admissible forms must be reported as INCOMPARABLE."""

    max_iterations: int = 3
    node_limit: int = 1200
    enumeration_depth: int = 4
    enumeration_limit: int = 600


@dataclass(frozen=True)
class Reframing:
    """One candidate representation with its full audit."""

    term: Term
    equivalent: bool
    equivalence_checker: str
    equivalence_points: int
    invariants: dict[str, bool]
    enables: bool
    costs: dict[str, float]
    residue: dict[str, object]

    @property
    def admissible(self) -> bool:
        return self.equivalent and self.enables and all(self.invariants.values())

    def as_measurement(self) -> dict[str, object]:
        return {
            "term": to_text(self.term),
            "equivalent": self.equivalent,
            "checker": self.equivalence_checker,
            "points_checked": self.equivalence_points,
            "invariants": dict(self.invariants),
            "enables": self.enables,
            "admissible": self.admissible,
            "costs": {name: round(value, 4) for name, value in self.costs.items()},
            "residue": self.residue,
        }


def _residue(start: Term, candidate: Term) -> dict[str, object]:
    lost = sorted(operators(start) - operators(candidate))
    gained = sorted(operators(candidate) - operators(start))
    return {
        "operators_lost": lost,
        "operators_gained": gained,
        "size_delta": size(candidate) - size(start),
        "depth_delta": depth(candidate) - depth(start),
        "note": "the source form is retained; nothing is discarded by rewriting",
    }


def explore_objects(
    task: RepresentationTask, config: XanaxConfig | None = None
) -> tuple[list[Reframing], object]:
    """Saturate, enumerate the class, and audit every candidate representation."""
    config = config or XanaxConfig()
    graph = EGraph()
    root = graph.add_term(task.start)
    report = graph.saturate(
        task.rules, max_iterations=config.max_iterations, node_limit=config.node_limit
    )
    terms = graph.enumerate_terms(
        root, max_depth=config.enumeration_depth, limit=config.enumeration_limit
    )
    seen: set[Term] = set()
    candidates: list[Reframing] = []
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        try:
            equivalent, _counterexample, measurement = equivalent_over_domain(
                lambda *values, t=task.start: evaluate_term(t, dict(zip(task.variables, values))),
                lambda *values, t=term: evaluate_term(t, dict(zip(task.variables, values))),
                arity=len(task.variables),
                domain=task.domain,
            )
        except (ValueError, TypeError):
            # A term the host evaluator cannot interpret (for example a negative
            # shift) is not equivalence-checkable and is recorded as such.
            equivalent, measurement = False, {"checker": "uninterpretable", "points": 0}
        candidates.append(
            Reframing(
                term=term,
                equivalent=bool(equivalent),
                equivalence_checker=str(measurement["checker"]),
                equivalence_points=int(measurement["points"]),
                invariants=task.invariant_status(term),
                enables=bool(task.enables(term)),
                costs={name: _cost_of(term, name) for name in DEFAULT_COSTS},
                residue=_residue(task.start, term),
            )
        )
    return candidates, report


def explore(task: RepresentationTask, config: XanaxConfig | None = None) -> dict[str, object]:
    """Serialisable view of the exploration, for reports and tests."""
    candidates, report = explore_objects(task, config)
    admissible = [item for item in candidates if item.admissible]
    rejected_for_invariant = [
        item
        for item in candidates
        if item.equivalent and item.enables and not all(item.invariants.values())
    ]
    return {
        "task": task.name,
        "note": task.note,
        "start": to_text(task.start),
        "enables_description": task.enables_description,
        "declared_invariants": [name for name, _ in task.invariants],
        "saturation": report.as_measurement(),  # type: ignore[union-attr]
        "class_size_explored": len(candidates),
        "candidates": [item.as_measurement() for item in candidates],
        "admissible": [item.as_measurement() for item in admissible],
        "rejected_for_invariant": [item.as_measurement() for item in rejected_for_invariant],
        "equivalence_scope": (
            f"verified on {len(task.domain)}^{len(task.variables)} integer points; "
            "not a proof over Z"
        ),
    }


def _cost_of(term: Term, name: str) -> float:
    """Evaluate one named cost function on a concrete term."""
    cost_fn = DEFAULT_COSTS[name]

    def walk(node: Term) -> float:
        from ..symbolic.terms import children, head_key

        kids = children(node)
        return cost_fn(head_key(node), tuple(walk(child) for child in kids))

    return walk(term)


def cheapest(candidates: Sequence[Reframing], objective: str) -> Reframing | None:
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item.costs[objective], to_text(item.term)))


class Xanax:
    """The re-representation operator over the shared substrate."""

    name = "X-ANA-X"

    def __init__(self, task: RepresentationTask, config: XanaxConfig | None = None) -> None:
        self.task = task
        self.config = config or XanaxConfig()
        self.exploration: dict[str, object] | None = None
        self.reframings: list[Reframing] = []
        self.certificates: list[dict[str, object]] = []

    def observe(self, state: State) -> State:
        if self.exploration is None:
            self.reframings, _report = explore_objects(self.task, self.config)
            self.exploration = explore(self.task, self.config)
        representation = dict(state.representation)
        representation.setdefault("term", self.task.start)
        representation["enables_now"] = bool(self.task.enables(representation["term"]))
        representation["invariants_now"] = self.task.invariant_status(representation["term"])
        return state.with_representation(representation)

    def propose(self, state: State) -> list[Candidate]:
        current = state.representation["term"]
        out: list[Candidate] = []
        for item in self.reframings:
            if item.term == current:
                continue
            payload = item.as_measurement()
            payload["_term"] = item.term
            out.append(
                Candidate(
                    name=payload["term"],
                    operator=self.name,
                    declared=Declaration(
                        cost=float(item.costs["tree_size"]),
                        evidence=(f"{item.equivalence_checker}:{item.equivalence_points} points",),
                        uncertainty=None,
                        information_gain=None,
                        residue=item.residue,
                        invariants=tuple(
                            name for name, ok in item.invariants.items() if ok
                        ),
                    ),
                    payload=payload,
                )
            )
        return out

    def select(self, state: State, candidates: Sequence[Candidate]) -> Candidate | None:
        assert self.exploration is not None
        admissible = [item for item in candidates if item.payload["admissible"]]
        certificate: dict[str, object] = {
            "current": to_text(state.representation["term"]),
            "admissible_count": len(admissible),
            "rejected_for_invariant": [
                item["term"] for item in self.exploration["rejected_for_invariant"]  # type: ignore[index]
            ],
            "objective": self.config.objective,
        }
        if not admissible:
            certificate["decision"] = "ABSTAIN: no equivalent form both preserves the invariants and enables the operation"
            self.certificates.append(certificate)
            return None
        if len(admissible) > 1 and self.config.objective is None:
            certificate["decision"] = "INCOMPARABLE: several admissible forms and no downstream objective"
            certificate["admissible"] = [item.name for item in admissible]
            self.certificates.append(certificate)
            return None
        if len(admissible) == 1:
            chosen = admissible[0]
            certificate["reason"] = "unique admissible representation"
        else:
            objective = self.config.objective or "tree_size"
            chosen = min(
                admissible,
                key=lambda item: (item.payload["costs"][objective], item.name),
            )
            certificate["reason"] = f"least {objective} among admissible forms"
        # What a size- or cost-driven selector would have picked instead.
        equivalent_enabling = [item for item in candidates if item.payload["equivalent"] and item.payload["enables"]]
        if equivalent_enabling:
            naive = min(
                equivalent_enabling,
                key=lambda item: (item.payload["costs"]["execution"], item.name),
            )
            certificate["cost_driven_choice"] = naive.name
            certificate["cost_driven_choice_is_admissible"] = bool(naive.payload["admissible"])
        certificate["decision"] = f"SELECT {chosen.name}"
        certificate["preserved"] = [
            name for name, ok in chosen.payload["invariants"].items() if ok
        ]
        certificate["enabled"] = self.task.enables_description
        self.certificates.append(certificate)
        return chosen

    def apply(self, state: State, candidate: Candidate) -> State:
        representation = dict(state.representation)
        representation["term"] = candidate.payload["_term"]
        representation["history"] = tuple(state.representation.get("history", ())) + (
            to_text(state.representation["term"]),
        )
        return state.with_representation(representation).charge(1)

    def validate(self, state: State, candidate: Candidate, after: State) -> bool | None:
        """Re-verify from scratch: equivalence to the original and all invariants."""
        term = after.representation["term"]
        equivalent, _cex, _m = equivalent_over_domain(
            lambda *values: evaluate_term(self.task.start, dict(zip(self.task.variables, values))),
            lambda *values: evaluate_term(term, dict(zip(self.task.variables, values))),
            arity=len(self.task.variables),
            domain=self.task.domain,
        )
        return bool(equivalent and self.task.preserves_invariants(term))

    def conclude(self, state: State, turn_index: int, validated: bool | None) -> tuple[Decision, str]:
        term = state.representation["term"]
        if validated is False:
            return Decision.ABSTAIN, "re-verification failed; the rewrite was not accepted"
        if self.task.enables(term) and self.task.preserves_invariants(term):
            return Decision.STOP, f"representation enables the operation: {self.task.enables_description}"
        return Decision.CONTINUE, "the required operation is still not enabled"
