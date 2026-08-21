"""Finite economics of representation discovery.

This module makes the acquisition of a useful representation an explicit
route in a small, auditable selector.  It deliberately keeps resource
dimensions vector-valued; a caller must choose the resource used for a route
comparison.  The mathematical object is small on purpose:

    direct(n) = n B
    transformed(n) = D + n A       (when the transformed object is reusable)

where ``D`` is discovery plus application cost, ``B`` is the direct per-use
cost, and ``A`` is the post-transformation per-use cost.  For a non-reusable
transform, acquisition is paid per use instead.

The selector does not claim that discovery is free, and it refuses to
silently treat a lossy transformation as an exact one.  The graph fixture at
the bottom is intentionally outside the Bayesian ``Opt(r)`` calculus: its
structural object is a connected-component index for repeated connectivity
queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Mapping, Sequence

from .decision_calculus import (
    Number,
    choose_next_computation,
    evaluate_representation_transformation,
    frac,
    quotient_experiment,
    solve_sequential_meta_decision,
    task_sufficient_quotient,
)


CostVector = dict[str, Fraction]


def _cost_vector(values: Mapping[str, Number] | None) -> CostVector:
    result = {str(name): frac(value) for name, value in (values or {}).items()}
    if any(value < 0 for value in result.values()):
        raise ValueError("resource costs must be non-negative")
    return result


def _add_costs(*vectors: Mapping[str, Fraction]) -> CostVector:
    names = {name for vector in vectors for name in vector}
    return {name: sum((vector.get(name, Fraction(0)) for vector in vectors), Fraction(0)) for name in names}


def _scale_cost(vector: Mapping[str, Fraction], count: int) -> CostVector:
    return {name: value * count for name, value in vector.items()}


def _serialize_cost(vector: Mapping[str, Fraction]) -> dict[str, str]:
    return {name: str(value) for name, value in sorted(vector.items())}


def _resource(vector: Mapping[str, Fraction], name: str) -> Fraction:
    return vector.get(name, Fraction(0))


def _strictly_better(left: Fraction, right: Fraction) -> bool:
    return left < right


@dataclass(frozen=True)
class TransformationCandidate:
    """One explicitly supplied representation route.

    ``discovery_status`` is ``UNKNOWN`` when discovery must be paid for and
    ``KNOWN`` when the representation was already produced.  ``reusable`` is
    an explicit claim about scope, not an inference: a transform learned on a
    graph is not automatically reusable on another graph.
    """

    id: str
    structural_property: str
    discovery_cost: Mapping[str, Number]
    apply_cost: Mapping[str, Number]
    solve_cost_after: Mapping[str, Number]
    resulting_regime: str
    discovery_status: str = "UNKNOWN"
    reuse_scope: str = "same_representation"
    reusable: bool = True
    task_preserved: bool = True
    decision_preserved: bool = True
    risk_preserved: bool = True
    risk_degradation: Number = 0
    discovery_complexity: str = "UNKNOWN"
    structural_effect: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.discovery_status not in {"UNKNOWN", "KNOWN"}:
            raise ValueError("discovery_status must be UNKNOWN or KNOWN")
        if not self.id:
            raise ValueError("candidate id must be non-empty")
        object.__setattr__(self, "discovery_cost", _cost_vector(self.discovery_cost))
        object.__setattr__(self, "apply_cost", _cost_vector(self.apply_cost))
        object.__setattr__(self, "solve_cost_after", _cost_vector(self.solve_cost_after))
        degradation = frac(self.risk_degradation)
        if degradation < 0:
            raise ValueError("risk_degradation must be non-negative")
        object.__setattr__(self, "risk_degradation", degradation)

    @property
    def acquisition_cost(self) -> CostVector:
        """One-time discovery plus construction cost for an unknown transform."""
        discovery = self.discovery_cost if self.discovery_status == "UNKNOWN" else {}
        return _add_costs(discovery, self.apply_cost)

    @property
    def route_kind(self) -> str:
        return "APPLY_KNOWN" if self.discovery_status == "KNOWN" else "DISCOVER_AND_APPLY"


def exact_break_even_count(
    discovery_and_apply: Number,
    solve_before: Number,
    solve_after: Number,
) -> int | None:
    """Return the least positive n with D+nA < nB, or None.

    Strict improvement is intentional.  At equality the route has no
    computational advantage under the selected resource policy.
    """
    D, B, A = frac(discovery_and_apply), frac(solve_before), frac(solve_after)
    if min(D, B, A) < 0:
        raise ValueError("costs must be non-negative")
    gain = B - A
    if gain <= 0:
        return None
    quotient = D / gain
    return quotient.numerator // quotient.denominator + 1


def _candidate_total(candidate: TransformationCandidate, uses: int) -> CostVector:
    if uses < 1:
        raise ValueError("uses must be a positive integer")
    if candidate.reusable:
        return _add_costs(candidate.acquisition_cost, _scale_cost(candidate.solve_cost_after, uses))
    return _scale_cost(_add_costs(candidate.acquisition_cost, candidate.solve_cost_after), uses)


def _candidate_break_even(
    candidate: TransformationCandidate,
    direct_cost: Mapping[str, Fraction],
    resource: str,
) -> int | None:
    if not candidate.reusable:
        return None
    return exact_break_even_count(
        _resource(candidate.acquisition_cost, resource),
        _resource(direct_cost, resource),
        _resource(candidate.solve_cost_after, resource),
    )


def _preservation_certificate(
    candidate: TransformationCandidate,
    allowed_degradation: Fraction,
) -> tuple[bool, dict[str, Any] | None]:
    if not candidate.task_preserved:
        return False, {"rule": "TASK_NOT_PRESERVED", "claim": "task preservation is false"}
    if not candidate.decision_preserved:
        return False, {"rule": "DECISION_NOT_PRESERVED", "claim": "decision preservation is false"}
    if not candidate.risk_preserved and candidate.risk_degradation > allowed_degradation:
        return False, {
            "rule": "RISK_DEGRADATION_EXCEEDS_POLICY",
            "risk_degradation": str(candidate.risk_degradation),
            "allowed": str(allowed_degradation),
        }
    return True, None


def _same_effect_dominance(
    left: TransformationCandidate,
    right: TransformationCandidate,
    resource: str,
    uses: int,
) -> bool:
    """Whether ``left`` safely dominates ``right`` for this explicit resource."""
    if left.resulting_regime != right.resulting_regime:
        return False
    if left.risk_degradation != right.risk_degradation:
        return False
    if left.discovery_status != "KNOWN" and right.discovery_status == "KNOWN":
        return False
    left_total = _resource(_candidate_total(left, uses), resource)
    right_total = _resource(_candidate_total(right, uses), resource)
    return left_total < right_total


def _route_public(
    candidate: TransformationCandidate,
    direct_cost: CostVector,
    uses: int,
    resource: str,
) -> dict[str, Any]:
    total = _candidate_total(candidate, uses)
    one_shot_total = _candidate_total(candidate, 1)
    direct_one = _resource(direct_cost, resource)
    break_even = _candidate_break_even(candidate, direct_cost, resource)
    return {
        "id": candidate.id,
        "route": candidate.route_kind,
        "structural_property": candidate.structural_property,
        "structural_effect": candidate.structural_effect,
        "structural_regime_after": candidate.resulting_regime,
        "discovery_status": candidate.discovery_status,
        "reuse_scope": candidate.reuse_scope,
        "reusable": candidate.reusable,
        "acquisition_cost": _serialize_cost(candidate.acquisition_cost),
        "solve_cost_after": _serialize_cost(candidate.solve_cost_after),
        "total_cost": _serialize_cost(total),
        "one_shot_total": _serialize_cost(one_shot_total),
        "selected_resource": resource,
        "selected_resource_total": str(_resource(total, resource)),
        "one_shot_advantage": _resource(one_shot_total, resource) < direct_one,
        "advantage_at_horizon": _resource(total, resource) < _resource(_scale_cost(direct_cost, uses), resource),
        "amortized_advantage": break_even is not None,
        "break_even_count": break_even,
        "preservation": {
            "task": candidate.task_preserved,
            "decision": candidate.decision_preserved,
            "risk": candidate.risk_preserved,
            "risk_degradation": str(candidate.risk_degradation),
        },
        "discovery_complexity": candidate.discovery_complexity,
        "metadata": dict(candidate.metadata),
    }


def select_representation_route(
    solve_cost_before: Mapping[str, Number],
    candidates: Sequence[TransformationCandidate],
    *,
    reuse_count: int = 1,
    policy: Mapping[str, Any] | None = None,
    structural_regime_before: str = "UNKNOWN",
) -> dict[str, Any]:
    """Select ``SOLVE_DIRECT`` or a candidate under an explicit resource policy.

    No default universal score exists.  ``policy['resource']`` is mandatory;
    all other resource dimensions remain in the certificate.  The selector
    compares strict total cost on that resource and is therefore auditable,
    not a claim that time dominates memory, queries, or samples.
    """
    if reuse_count < 1:
        raise ValueError("reuse_count must be a positive integer")
    policy = dict(policy or {})
    resource = policy.get("resource")
    if not resource:
        raise ValueError("an explicit policy resource is required")
    direct = _cost_vector(solve_cost_before)
    allowed_degradation = frac(policy.get("allowed_risk_degradation", 0))
    if allowed_degradation < 0:
        raise ValueError("allowed_risk_degradation must be non-negative")
    direct_total = _scale_cost(direct, reuse_count)
    direct_value = _resource(direct_total, str(resource))
    public_routes = []
    feasible: list[tuple[TransformationCandidate, dict[str, Any]]] = []
    pruned: list[dict[str, Any]] = []

    for candidate in candidates:
        preserved, certificate = _preservation_certificate(candidate, allowed_degradation)
        if not preserved:
            pruned.append({"candidate": candidate.id, **(certificate or {})})
            continue
        route = _route_public(candidate, direct, reuse_count, str(resource))
        public_routes.append(route)
        max_acquisition = policy.get("max_acquisition_cost")
        if max_acquisition is not None and _resource(candidate.acquisition_cost, str(resource)) > frac(max_acquisition):
            pruned.append({
                "candidate": candidate.id,
                "rule": "ACQUISITION_RESOURCE_CONSTRAINT",
                "acquisition": str(_resource(candidate.acquisition_cost, str(resource))),
                "limit": str(frac(max_acquisition)),
            })
            continue
        max_total = policy.get("max_total_cost")
        if max_total is not None and _resource(_candidate_total(candidate, reuse_count), str(resource)) > frac(max_total):
            pruned.append({
                "candidate": candidate.id,
                "rule": "TOTAL_RESOURCE_CONSTRAINT",
                "total": route["selected_resource_total"],
                "limit": str(frac(max_total)),
            })
            continue
        if (
            candidate.resulting_regime == structural_regime_before
            and _resource(candidate.solve_cost_after, str(resource)) >= _resource(direct, str(resource))
        ):
            pruned.append({
                "candidate": candidate.id,
                "rule": "NO_DOWNSTREAM_GAIN",
                "certificate": "same regime and post-transform selected-resource cost is not lower",
            })
            continue
        feasible.append((candidate, route))

    # A known route with the same regime and no worse acquisition/online cost
    # makes an undiscovered equivalent route irrelevant under this policy.
    for left, _left_route in feasible:
        for right, _right_route in feasible:
            if left.id == right.id or not _same_effect_dominance(left, right, str(resource), reuse_count):
                continue
            if any(item[0].id == right.id for item in feasible):
                feasible = [item for item in feasible if item[0].id != right.id]
                pruned.append({
                    "candidate": right.id,
                    "rule": "SAME_REGIME_DOMINATED",
                    "dominated_by": left.id,
                })

    best_id = "SOLVE_DIRECT"
    best_value = direct_value
    selected_route: dict[str, Any] | None = None
    for candidate, route in feasible:
        value = frac(route["selected_resource_total"])
        if value < best_value:
            best_id = candidate.id
            best_value = value
            selected_route = route

    if selected_route is not None:
        why = "strictly lower total cost under the explicit selected-resource policy"
    else:
        why = "direct solve is no more expensive than every feasible transformation route"
    return {
        "decision": best_id,
        "why_selected": why,
        "policy": {
            "resource": str(resource),
            "reuse_count": reuse_count,
            "allowed_risk_degradation": str(allowed_degradation),
            "max_acquisition_cost": (
                None if policy.get("max_acquisition_cost") is None else str(frac(policy["max_acquisition_cost"]))
            ),
            "max_total_cost": (
                None if policy.get("max_total_cost") is None else str(frac(policy["max_total_cost"]))
            ),
            "scalarization": "one explicitly selected resource only; all vectors retained",
        },
        "structural_regime_before": structural_regime_before,
        "direct": {
            "decision": "SOLVE_DIRECT",
            "solve_cost_per_use": _serialize_cost(direct),
            "total_cost": _serialize_cost(direct_total),
            "selected_resource_total": str(direct_value),
        },
        "routes": public_routes,
        "pruned": pruned,
        "selected_route": selected_route,
        "resource_vector_is_not_a_score": True,
    }


def candidate_from_transformation_analysis(
    analysis: Mapping[str, Any],
    *,
    discovery_cost: Mapping[str, Number],
    apply_cost: Mapping[str, Number],
    solve_cost_after: Mapping[str, Number],
    discovery_status: str = "UNKNOWN",
    reusable: bool = True,
    reuse_scope: str = "same_representation",
    discovery_complexity: str = "UNKNOWN",
    structural_property: str = "representation_transform",
) -> TransformationCandidate:
    """Turn an existing exact transform certificate into a route candidate."""
    return TransformationCandidate(
        id=str(analysis["transformation"]),
        structural_property=structural_property,
        structural_effect=(
            f"{analysis['before']['regime']} -> {analysis['after']['regime']}"
        ),
        discovery_cost=discovery_cost,
        apply_cost=apply_cost,
        solve_cost_after=solve_cost_after,
        resulting_regime=str(analysis["after"]["regime"]),
        discovery_status=discovery_status,
        reusable=reusable,
        reuse_scope=reuse_scope,
        task_preserved=bool(analysis["decision_preserved"]),
        decision_preserved=bool(analysis["decision_preserved"]),
        risk_preserved=bool(analysis["decision_preserved"]),
        discovery_complexity=discovery_complexity,
        metadata={
            "source_regime": analysis["before"]["regime"],
            "decision_risk_before": analysis["task_risk_before"],
            "decision_risk_after": analysis["task_risk_after"],
        },
    )


def transformation_discovery_probe(
    candidate: TransformationCandidate,
    channel: Sequence[Sequence[Number]],
) -> dict[str, Any]:
    """Expose discovery as the existing finite-probe meta-action.

    The adapter adds no new host semantics: ``choose_next_computation`` still
    evaluates the supplied channel and returns its ordinary decision-value
    certificate.  The route selector remains responsible for end-to-end
    discovery/apply/solve economics after the meta-action is selected.
    """
    return {
        "id": f"DISCOVER:{candidate.id}",
        "channel": [list(row) for row in channel],
        "cost": dict(candidate.discovery_cost),
        "meta_action": "DISCOVER_TRANSFORMATION",
        "transformation": candidate.id,
    }


def choose_transformation_discovery_action(
    prior: Sequence[Number],
    candidates: Sequence[TransformationCandidate],
    discovery_channels: Mapping[str, Sequence[Sequence[Number]]],
    losses: Sequence[Sequence[Number]],
    *,
    actions: Sequence[Any] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Use the existing one-step meta-solver to choose a discovery action."""
    probes = []
    for candidate in candidates:
        if candidate.id not in discovery_channels:
            raise ValueError(f"missing discovery channel for {candidate.id}")
        probes.append(transformation_discovery_probe(candidate, discovery_channels[candidate.id]))
    return choose_next_computation(prior, probes, losses, actions, policy=dict(policy or {}))


def solve_transformation_discovery_sequence(
    prior: Sequence[Number],
    candidates: Sequence[TransformationCandidate],
    discovery_channels: Mapping[str, Sequence[Sequence[Number]]],
    losses: Sequence[Sequence[Number]],
    *,
    actions: Sequence[Any] | None = None,
    time_cost_weight: Number = 1,
) -> dict[str, Any]:
    """Use the existing exact sequential meta-solver on discovery actions."""
    probes = []
    for candidate in candidates:
        if candidate.id not in discovery_channels:
            raise ValueError(f"missing discovery channel for {candidate.id}")
        probes.append(transformation_discovery_probe(candidate, discovery_channels[candidate.id]))
    return solve_sequential_meta_decision(
        prior,
        probes,
        losses,
        actions,
        time_cost_weight=time_cost_weight,
    )


def evaluate_connected_component_transformation(
    graph: Sequence[Sequence[int]],
    queries: Sequence[tuple[int, int]],
) -> dict[str, Any]:
    """Evaluate a lossless graph-index transform outside ``Opt(r)``.

    The underlying task is undirected connectivity.  Direct execution uses a
    graph search per query.  The transformed representation is a component
    label index, built once and then queried by constant-time lookup.  No
    loss matrix or Bayes-optimal action is involved.
    """
    adjacency = [sorted(set(int(neighbor) for neighbor in row)) for row in graph]
    node_count = len(adjacency)
    if node_count == 0:
        raise ValueError("graph must be non-empty")
    if any(neighbor < 0 or neighbor >= node_count for row in adjacency for neighbor in row):
        raise ValueError("graph contains an invalid endpoint")
    if any(index not in adjacency[neighbor] for index, row in enumerate(adjacency) for neighbor in row):
        raise ValueError("graph must be undirected for connected-component indexing")

    labels = [-1] * node_count
    components: list[list[int]] = []
    edge_scans = 0
    node_visits = 0
    for start in range(node_count):
        if labels[start] != -1:
            continue
        component_id = len(components)
        stack = [start]
        labels[start] = component_id
        component: list[int] = []
        while stack:
            node = stack.pop()
            node_visits += 1
            component.append(node)
            for neighbor in adjacency[node]:
                edge_scans += 1
                if labels[neighbor] == -1:
                    labels[neighbor] = component_id
                    stack.append(neighbor)
        components.append(sorted(component))

    direct_per_query = node_count + edge_scans
    transformed_per_query = 1
    direct_total = direct_per_query * len(queries)
    discovery_cost = node_visits + edge_scans
    apply_cost = node_count
    transformed_total = discovery_cost + apply_cost + transformed_per_query * len(queries)
    results = [labels[left] == labels[right] for left, right in queries]
    return {
        "task": "undirected_connectivity",
        "task_preserved": True,
        "query_results": results,
        "components": components,
        "structural_analysis": {
            "property": "connected_components",
            "component_count": len(components),
            "nodes": node_count,
            "edge_scans": edge_scans,
        },
        "direct_route": {
            "algorithm_family": "BFS/DFS_PER_QUERY",
            "regime": "UNINDEXED_GRAPH_SEARCH",
            "cost_per_query": direct_per_query,
            "total_cost": direct_total,
        },
        "transformed_route": {
            "algorithm_family": "COMPONENT_LABEL_LOOKUP",
            "regime": "CONNECTED_COMPONENT_INDEX",
            "discovery_cost": discovery_cost,
            "apply_cost": apply_cost,
            "cost_per_query": transformed_per_query,
            "total_cost": transformed_total,
            "reuse_scope": "same_static_graph",
        },
        "different_algorithm_family": True,
        "not_defined_by_opt_r": True,
        "one_shot_advantage": transformed_total < direct_total,
        "amortized_break_even_queries": exact_break_even_count(
            discovery_cost + apply_cost,
            direct_per_query,
            transformed_per_query,
        ),
    }


def representation_economics_literature_audit() -> list[dict[str, Any]]:
    """Primary-source audit for this block; classifications stay conservative."""
    return [
        {
            "theory": "knowledge compilation",
            "source": "https://www.cril.univ-artois.fr/~marquis/darwiche-marquis-jair02.pdf",
            "classification": "ESTABLISHED_THEORY",
            "offline_online": "offline compilation -> online query/transform classes",
            "relation": "closest match; MAT-SI makes choosing the compilation route an explicit meta-decision",
        },
        {
            "theory": "kernelization / parameterized preprocessing",
            "source": "https://arxiv.org/abs/1104.4217",
            "classification": "FORMAL_SPECIAL_CASE",
            "offline_online": "polynomial preprocessing -> equivalent bounded-parameter instance",
            "relation": "captures size/parameter reduction, not every representation change or solver-selection policy",
        },
        {
            "theory": "incompressibility and polynomial kernels",
            "source": "https://doi.org/10.1145/1374376.1374398",
            "classification": "ESTABLISHED_LOWER_BOUND",
            "offline_online": "efficient compression is constrained unless NP is contained in coNP/poly",
            "relation": "supports the warning that a useful compact representation need not be efficiently discoverable",
        },
        {
            "theory": "cell-probe preprocessing/query tradeoffs",
            "source": "https://doi.org/10.1137/S0097539705447256",
            "classification": "ESTABLISHED_THEORY",
            "offline_online": "stored state/update work <-> query work under an explicit cost model",
            "relation": "supports vector/resource-specific online-offline accounting; not a representation-discovery theorem",
        },
        {
            "theory": "algorithm selection",
            "source": "https://doi.org/10.1016/S0065-2458(08)60520-3",
            "classification": "ESTABLISHED_THEORY",
            "offline_online": "features -> selected algorithm under a performance criterion",
            "relation": "MAT-SI adds acquisition/construction costs to the feature/representation route",
        },
        {
            "theory": "value of computation / metareasoning",
            "source": "https://doi.org/10.1016/0004-3702(91)90015-C",
            "classification": "IMPORTED_THEORY",
            "offline_online": "computation cost traded against expected downstream value",
            "relation": "the route selector is a finite explicit-cost instantiation, not a novelty claim",
        },
    ]


def run_representation_economics_suite() -> dict[str, Any]:
    """Run the required finite negative, positive, amortized, and graph cases."""
    negative = TransformationCandidate(
        id="expensive_easy_representation",
        structural_property="hidden_decomposition",
        discovery_cost={"time": 8},
        apply_cost={"time": 3},
        solve_cost_after={"time": 1},
        resulting_regime="UNIQUE_OPTIMUM",
        structural_effect="GENERAL_SET_COVER -> UNIQUE_OPTIMUM",
        discovery_complexity="NP-HARD_SEARCH_IN_GENERAL_CASE",
    )
    transform_source = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    transform_prior = [Fraction(1, 4)] * 4
    transform_losses = [[0, 0, 0], [0, 0, 0], [0, 1, 1], [1, 0, 1]]
    transform_quotient = task_sufficient_quotient(
        transform_source, transform_prior, transform_losses
    )
    transform_target = quotient_experiment(transform_source, transform_quotient["blocks"])
    positive_analysis = evaluate_representation_transformation(
        transform_source,
        transform_target,
        transform_prior,
        transform_losses,
        transformation_id="cheap_task_sufficient_quotient",
        cost={"time": 3},
    )
    positive = TransformationCandidate(
        id="cheap_task_sufficient_quotient",
        structural_property="known_task_sufficient_partition",
        discovery_cost={"time": 2},
        apply_cost={"time": 1},
        solve_cost_after={"time": 3},
        resulting_regime=positive_analysis["after"]["regime"],
        structural_effect=(
            f"{positive_analysis['before']['regime']} -> {positive_analysis['after']['regime']}"
        ),
        discovery_complexity="POLYNOMIAL_FOR_THIS_GIVEN_CANDIDATE",
        decision_preserved=positive_analysis["decision_preserved"],
        risk_preserved=positive_analysis["decision_preserved"],
        metadata={"exact_transform_certificate": positive_analysis},
    )
    amortized = TransformationCandidate(
        id="compiled_reusable_representation",
        structural_property="reusable_decomposition",
        discovery_cost={"time": 5},
        apply_cost={"time": 3},
        solve_cost_after={"time": 4},
        resulting_regime="COMPILED_QUERY",
        structural_effect="DIRECT_SEARCH -> COMPILED_QUERY",
        discovery_complexity="UNKNOWN_GENERAL; EXPLICIT_FINITE_COST_HERE",
    )
    direct = {"time": 10}
    negative_choice = select_representation_route(direct, [negative], policy={"resource": "time"})
    positive_choice = select_representation_route(direct, [positive], policy={"resource": "time"})
    amortized_one = select_representation_route(direct, [amortized], reuse_count=1, policy={"resource": "time"})
    amortized_many = select_representation_route(direct, [amortized], reuse_count=2, policy={"resource": "time"})

    lossy = TransformationCandidate(
        id="lossy_shortcut",
        structural_property="coarse_partition",
        discovery_cost={"time": 0},
        apply_cost={"time": 1},
        solve_cost_after={"time": 1},
        resulting_regime="FAST_BUT_LOSSY",
        task_preserved=False,
        decision_preserved=False,
        risk_preserved=False,
        risk_degradation=Fraction(1, 10),
    )
    preservation_choice = select_representation_route(
        direct,
        [lossy],
        policy={"resource": "time", "allowed_risk_degradation": 0},
    )
    graph = evaluate_connected_component_transformation(
        [[1], [0, 2], [1], [4], [3]],
        [(0, 2), (0, 4), (3, 4)],
    )
    return {
        "protocol": "agent1-representation-discovery-economics-v1",
        "starting_commit": "f3f8816ad9e49c95668ef5030354d169d983e1a7",
        "corpus_policy": "no new corpus; finite mathematical fixtures only",
        "literature_audit": representation_economics_literature_audit(),
        "cost_decomposition": {
            "formula": "C_direct(n)=nB; C_transform(n)=D+nA when reusable; C_transform(n)=n(D+A) otherwise",
            "D": "discovery + apply",
            "B": "direct solve per use",
            "A": "solve after transformation per use",
            "separation": ["EXISTENCE", "DISCOVERY", "CONSTRUCTION", "EXPLOITATION"],
        },
        "false_principle": {
            "statement": "T(R) easier than R implies transforming is preferable",
            "status": "DISPROVED",
            "reason": "the negative fixture has a lower after-cost but a higher one-shot end-to-end cost",
        },
        "negative_case": negative_choice,
        "positive_case": {
            "exact_representation_analysis": positive_analysis,
            "route_selection": positive_choice,
        },
        "amortized_case": {
            "one_use": amortized_one,
            "two_uses": amortized_many,
            "exact_break_even_count": exact_break_even_count(8, 10, 4),
        },
        "preservation_case": preservation_choice,
        "outside_opt_r": graph,
        "complexity": {
            "known_candidate_evaluation": "PROVED_POLYNOMIAL in explicit portfolio size and cost-vector dimensions",
            "portfolio_selection": "PROVED_POLYNOMIAL after candidates are supplied and one resource policy is fixed",
            "break_even": "PROVED_O(1) exact rational arithmetic",
            "exact_task_sufficient_discovery": "NP-HARD in the explicit Set-Cover reduction already present; candidate evaluation is not discovery",
            "sequential_transformation_search": "KNOWN_EXPONENTIAL in candidate count/reachable states for the existing exact recursion",
            "kernelization": "KNOWN_PARAMETERIZED_SPECIAL_CASE; no general MAT-SI complexity claim",
        },
        "reuse_condition": "the transformed representation must remain valid for the same static object/task scope; transfer is not inferred",
        "generality_verdict": "GENERALIZES_WITH_NEW_OBJECT",
    }


__all__ = [
    "TransformationCandidate",
    "candidate_from_transformation_analysis",
    "choose_transformation_discovery_action",
    "evaluate_connected_component_transformation",
    "exact_break_even_count",
    "representation_economics_literature_audit",
    "run_representation_economics_suite",
    "select_representation_route",
    "solve_transformation_discovery_sequence",
    "transformation_discovery_probe",
]
