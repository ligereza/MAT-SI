"""Implicit representation-route search with certified stopping.

The previous milestone priced an explicitly supplied transformation.  This
module makes the next step executable: transformation generators lazily
produce verified successors, and a finite cost search compares composed routes
against a direct-solve incumbent.

The object is intentionally modest.  A state has a canonical task-relative
identity, a terminal solver cost, and an admissible terminal lower bound.  A
generator is a callable partial operator.  The search cost is kept separate
from the route cost, and an explicit resource policy is required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from heapq import heappop, heappush
from itertools import count
from ast import literal_eval
from typing import Any, Callable, Iterable, Mapping, Sequence

from .decision_calculus import Number, frac, quotient_experiment, task_sufficient_quotient


@dataclass(frozen=True)
class RepresentationState:
    """A canonical task-relative representation state."""

    id: str
    regime: str
    terminal_solve_cost: Number
    terminal_algorithm: str
    terminal_lower_bound: Number = 0
    payload: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("representation state id must be non-empty")
        solve = frac(self.terminal_solve_cost)
        lower = frac(self.terminal_lower_bound)
        if solve < 0 or lower < 0 or lower > solve:
            raise ValueError("terminal costs must satisfy 0 <= lower_bound <= solve_cost")
        object.__setattr__(self, "terminal_solve_cost", solve)
        object.__setattr__(self, "terminal_lower_bound", lower)


@dataclass(frozen=True)
class RepresentationTransition:
    """One generated, auditable transformation application."""

    generator_id: str
    source_id: str
    target: RepresentationState | None
    cost: Number
    precondition_witness: Mapping[str, Any] = field(default_factory=dict)
    preservation_status: str = "VERIFIED_EXACT"
    preservation_certificate: Mapping[str, Any] = field(default_factory=dict)
    structural_effect: str = ""
    operation_counts: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if frac(self.cost) < 0:
            raise ValueError("transition cost must be non-negative")
        if self.preservation_status not in {
            "VERIFIED_EXACT",
            "VERIFIED_WITH_TOLERANCE",
            "UNVERIFIED",
            "INVALID_FOR_TASK",
        }:
            raise ValueError("unknown preservation status")
        object.__setattr__(self, "cost", frac(self.cost))


GeneratorFunction = Callable[[RepresentationState], Iterable[RepresentationTransition]]


@dataclass(frozen=True)
class TransformationGenerator:
    """A lazy partial transformation operator."""

    id: str
    generate: GeneratorFunction


def _route_cost(acquisition: Fraction, terminal: Fraction, reuse_horizon: int) -> Fraction:
    return acquisition + reuse_horizon * terminal


def _transition_public(transition: RepresentationTransition) -> dict[str, Any]:
    return {
        "generator": transition.generator_id,
        "source": transition.source_id,
        "target": None if transition.target is None else transition.target.id,
        "cost": str(frac(transition.cost)),
        "precondition_witness": dict(transition.precondition_witness),
        "preservation_status": transition.preservation_status,
        "preservation_certificate": dict(transition.preservation_certificate),
        "structural_effect": transition.structural_effect,
        "operation_counts": dict(transition.operation_counts),
    }


def _route_certificate(
    initial: RepresentationState,
    states: Sequence[RepresentationState],
    transitions: Sequence[RepresentationTransition],
    acquisition: Fraction,
    reuse_horizon: int,
) -> dict[str, Any]:
    terminal = states[-1]
    return {
        "initial_representation": initial.id,
        "representation_sequence": [state.id for state in states],
        "transformation_sequence": [_transition_public(item) for item in transitions],
        "structural_regimes": [state.regime for state in states],
        "total_acquisition_cost": str(acquisition),
        "terminal_solve_cost_per_use": str(terminal.terminal_solve_cost),
        "reuse_horizon": reuse_horizon,
        "total_route_cost": str(_route_cost(acquisition, terminal.terminal_solve_cost, reuse_horizon)),
        "terminal_algorithm": terminal.terminal_algorithm,
    }


def search_representation_routes(
    initial: RepresentationState,
    generators: Sequence[TransformationGenerator],
    *,
    direct_solve_cost: Number,
    reuse_horizon: int = 1,
    resource: str = "time",
    max_expansions: int | None = None,
    use_lower_bound: bool = True,
) -> dict[str, Any]:
    """Search a generated representation space against a direct incumbent.

    ``resource`` names the selected scalar route resource. Other resources can
    remain in ``operation_counts`` and metadata, but this finite search does
    not invent a universal conversion between them. ``use_lower_bound`` turns
    the same exact search into an A*/branch-and-bound experiment; with a sound
    state lower bound it remains exact when unbounded.
    """
    if reuse_horizon < 1:
        raise ValueError("reuse_horizon must be positive")
    if max_expansions is not None and max_expansions < 0:
        raise ValueError("max_expansions must be non-negative")
    direct = frac(direct_solve_cost)
    if direct < 0:
        raise ValueError("direct solve cost must be non-negative")

    direct_total = reuse_horizon * direct
    incumbent_total = direct_total
    incumbent = {
        "kind": "SOLVE_DIRECT",
        "total_cost": str(direct_total),
        "acquisition_cost": "0",
        "terminal_solve_cost_per_use": str(direct),
        "terminal_algorithm": "DIRECT_SOLVER",
        "representation_sequence": [initial.id],
        "transformation_sequence": [],
    }

    sequence = count()
    initial_h = reuse_horizon * initial.terminal_lower_bound if use_lower_bound else Fraction(0)
    frontier: list[tuple[Fraction, int, Fraction, RepresentationState, list[RepresentationState], list[RepresentationTransition]]] = [
        (initial_h, next(sequence), Fraction(0), initial, [initial], [])
    ]
    best_acquisition: dict[str, Fraction] = {initial.id: Fraction(0)}
    state_registry: dict[str, RepresentationState] = {initial.id: initial}
    expanded_best: dict[str, Fraction] = {}
    generated = 0
    expanded = 0
    duplicates_removed = 0
    invalid_transitions = 0
    preservation_failures = 0
    pruned: list[dict[str, Any]] = []
    frontier_snapshots: list[dict[str, Any]] = []
    incumbent_updates: list[dict[str, Any]] = []
    stopped_by_budget = False

    while frontier:
        lower_bound, _, acquisition, state, states, transitions = heappop(frontier)
        if acquisition != best_acquisition.get(state.id):
            duplicates_removed += 1
            pruned.append({"state": state.id, "rule": "STALE_HIGHER_COST_ENTRY"})
            continue
        if state.id in expanded_best and acquisition >= expanded_best[state.id]:
            duplicates_removed += 1
            pruned.append({"state": state.id, "rule": "ALREADY_EXPANDED_AT_LOWER_COST"})
            continue
        if max_expansions is not None and expanded >= max_expansions:
            stopped_by_budget = True
            heappush(
                frontier,
                (lower_bound, next(sequence), acquisition, state, states, transitions),
            )
            break
        expanded_best[state.id] = acquisition

        terminal_total = _route_cost(acquisition, state.terminal_solve_cost, reuse_horizon)
        if terminal_total < incumbent_total:
            incumbent_total = terminal_total
            incumbent = {
                "kind": "TRANSFORMED_ROUTE",
                **_route_certificate(initial, states, transitions, acquisition, reuse_horizon),
            }
            incumbent_updates.append({"state": state.id, "total_cost": str(terminal_total)})

        expanded += 1

        state_bound = _route_cost(
            acquisition,
            state.terminal_lower_bound,
            reuse_horizon,
        ) if use_lower_bound else acquisition
        if state_bound >= incumbent_total:
            pruned.append({
                "state": state.id,
                "rule": "LOWER_BOUND_GE_INCUMBENT",
                "lower_bound": str(state_bound),
                "incumbent": str(incumbent_total),
            })
            continue

        for generator in generators:
            try:
                successors = list(generator.generate(state))
            except Exception as error:  # generator failures are evidence, not a crash
                invalid_transitions += 1
                pruned.append({
                    "state": state.id,
                    "generator": generator.id,
                    "rule": "GENERATOR_ERROR",
                    "error": type(error).__name__,
                })
                continue
            for transition in successors:
                generated += 1
                if transition.source_id != state.id:
                    invalid_transitions += 1
                    pruned.append({"generator": generator.id, "rule": "SOURCE_MISMATCH"})
                    continue
                if transition.preservation_status != "VERIFIED_EXACT" or transition.target is None:
                    invalid_transitions += 1
                    if transition.preservation_status != "VERIFIED_EXACT":
                        preservation_failures += 1
                    pruned.append({
                        "state": state.id,
                        "generator": generator.id,
                        "rule": "PRESERVATION_FAILURE",
                        "status": transition.preservation_status,
                    })
                    continue
                target = transition.target
                previous = state_registry.get(target.id)
                if previous is not None and previous.regime != target.regime:
                    invalid_transitions += 1
                    pruned.append({
                        "state": target.id,
                        "rule": "CANONICAL_ID_COLLISION",
                        "existing_regime": previous.regime,
                        "new_regime": target.regime,
                    })
                    continue
                state_registry[target.id] = target
                next_acquisition = acquisition + frac(transition.cost)
                if next_acquisition >= incumbent_total:
                    pruned.append({
                        "state": target.id,
                        "rule": "ACQUISITION_GE_INCUMBENT",
                        "acquisition": str(next_acquisition),
                        "incumbent": str(incumbent_total),
                    })
                    continue
                if best_acquisition.get(target.id, None) is not None and best_acquisition[target.id] <= next_acquisition:
                    duplicates_removed += 1
                    pruned.append({
                        "state": target.id,
                        "rule": "DUPLICATE_CANONICAL_STATE",
                        "existing_cost": str(best_acquisition[target.id]),
                        "new_cost": str(next_acquisition),
                    })
                    continue
                target_bound = _route_cost(
                    next_acquisition,
                    target.terminal_lower_bound,
                    reuse_horizon,
                ) if use_lower_bound else next_acquisition
                if target_bound >= incumbent_total:
                    pruned.append({
                        "state": target.id,
                        "rule": "LOWER_BOUND_GE_INCUMBENT",
                        "lower_bound": str(target_bound),
                        "incumbent": str(incumbent_total),
                    })
                    continue
                best_acquisition[target.id] = next_acquisition
                heappush(
                    frontier,
                    (
                        target_bound,
                        next(sequence),
                        next_acquisition,
                        target,
                        [*states, target],
                        [*transitions, transition],
                    ),
                )

    if frontier:
        global_lower_bound = min(item[0] for item in frontier)
    else:
        global_lower_bound = incumbent_total
    gap = max(Fraction(0), incumbent_total - global_lower_bound)
    exact = not frontier and not stopped_by_budget
    if exact and incumbent["kind"] == "SOLVE_DIRECT":
        status = "NO_BETTER_ROUTE"
    elif exact:
        status = "EXACT_OPTIMUM"
    else:
        status = "BOUNDED_INCUMBENT"
    frontier_public = [
        {
            "state": item[3].id,
            "lower_bound": str(item[0]),
            "acquisition": str(item[2]),
            "regime": item[3].regime,
        }
        for item in sorted(frontier, key=lambda value: value[0])[:25]
    ]
    return {
        "status": status,
        "resource_policy": {"resource": resource, "reuse_horizon": reuse_horizon},
        "direct_incumbent": {
            "cost_per_use": str(direct),
            "total_cost": str(direct_total),
        },
        "best_route": incumbent,
        "best_route_cost": str(incumbent_total),
        "lower_bound": str(global_lower_bound),
        "optimality_gap": str(gap),
        "optimality_certificate": {
            "exact": exact,
            "statement": (
                "all generated continuations are exhausted or bounded below by the incumbent"
                if exact else
                "the incumbent is executable but unexplored frontier remains"
            ),
        },
        "search_cost": {
            "states_generated": generated,
            "states_expanded": expanded,
            "duplicate_states_removed": duplicates_removed,
            "invalid_transitions": invalid_transitions,
            "preservation_failures": preservation_failures,
            "planner_operation_units": generated + expanded,
        },
        "incumbent_updates": incumbent_updates,
        "pruned": pruned,
        "unexplored_frontier": frontier_public,
        "search_budget": {
            "max_expansions": max_expansions,
            "spent_expansions": expanded,
            "stopped_by_budget": stopped_by_budget,
        },
        "heuristic": {
            "used": use_lower_bound,
            "kind": "state terminal lower bound" if use_lower_bound else "zero",
            "admissible_assumption": "every descendant terminal solve cost is >= state.terminal_lower_bound",
        },
        "canonical_identity": "state.id is task-relative canonical identity; Python object identity is not used",
    }


def search_explicit_route_graph(
    initial: RepresentationState,
    transitions_by_source: Mapping[str, Sequence[RepresentationTransition]],
    *,
    direct_solve_cost: Number,
    reuse_horizon: int = 1,
    resource: str = "time",
) -> dict[str, Any]:
    """Run the explicit-graph shortest-path special case through the same solver."""
    def generate(state: RepresentationState) -> Iterable[RepresentationTransition]:
        return transitions_by_source.get(state.id, ())

    return search_representation_routes(
        initial,
        [TransformationGenerator("explicit_edges", generate)],
        direct_solve_cost=direct_solve_cost,
        reuse_horizon=reuse_horizon,
        resource=resource,
    )


def greedy_one_step_choice(
    initial: RepresentationState,
    generators: Sequence[TransformationGenerator],
    *,
    reuse_horizon: int = 1,
) -> dict[str, Any]:
    """Choose the best immediately terminal-looking successor, for falsification."""
    options = []
    for generator in generators:
        for transition in generator.generate(initial):
            if transition.target is None or transition.preservation_status != "VERIFIED_EXACT":
                continue
            score = frac(transition.cost) + reuse_horizon * transition.target.terminal_solve_cost
            options.append({
                "generator": generator.id,
                "target": transition.target.id,
                "local_score": str(score),
                "transition": _transition_public(transition),
            })
    if not options:
        return {"status": "NO_VALID_SUCCESSOR", "choice": None, "options": []}
    choice = min(options, key=lambda item: (frac(item["local_score"]), item["target"]))
    return {
        "status": "GREEDY_ONE_STEP",
        "choice": choice["target"],
        "chosen_local_score": choice["local_score"],
        "options": options,
    }


def route_economics_frontier(
    routes: Sequence[Mapping[str, Any]],
    *,
    max_enumerated_horizon: int = 100_000,
) -> dict[str, Any]:
    """Compute a one-resource (D,A) frontier and exact finite breakpoints."""
    if not routes:
        raise ValueError("at least one complete route is required")
    normalized = []
    for route in routes:
        if "id" not in route or "D" not in route or "A" not in route:
            raise ValueError("routes require id, D, and A")
        normalized.append({
            **dict(route),
            "D": frac(route["D"]),
            "A": frac(route["A"]),
            "preservation_key": route.get("preservation_key", "EXACT"),
        })
    frontier = []
    dominated = []
    for candidate in normalized:
        is_dominated = False
        for other in normalized:
            if other["id"] == candidate["id"] or other["preservation_key"] != candidate["preservation_key"]:
                continue
            if (
                other["D"] <= candidate["D"]
                and other["A"] <= candidate["A"]
                and (other["D"] < candidate["D"] or other["A"] < candidate["A"])
            ):
                is_dominated = True
                dominated.append({"route": candidate["id"], "dominated_by": other["id"]})
                break
        if not is_dominated:
            frontier.append(candidate)

    breakpoints = []
    for left_index, left in enumerate(normalized):
        for right in normalized[left_index + 1:]:
            if left["A"] == right["A"]:
                continue
            crossing = (right["D"] - left["D"]) / (left["A"] - right["A"])
            if crossing >= 1:
                breakpoints.append({
                    "first": left["id"],
                    "second": right["id"],
                    "horizon": str(crossing),
                })
    integer_events = {1}
    for point in breakpoints:
        value = frac(point["horizon"])
        floor_value = value.numerator // value.denominator
        for candidate in (floor_value, floor_value + 1, floor_value + 2):
            if candidate >= 1:
                integer_events.add(candidate)
    largest_event = max(integer_events)
    if largest_event + 2 > max_enumerated_horizon:
        raise ValueError("frontier fixture exceeds finite enumeration limit")
    horizon_limit = largest_event + 1
    winners = []
    for horizon in range(1, horizon_limit + 1):
        winner = min(
            normalized,
            key=lambda route: (route["D"] + horizon * route["A"], str(route["id"])),
        )
        winners.append((horizon, winner["id"], winner["D"] + horizon * winner["A"]))
    intervals = []
    for horizon, route_id, value in winners:
        if intervals and intervals[-1]["route"] == route_id and intervals[-1]["end"] == horizon - 1:
            intervals[-1]["end"] = horizon
        else:
            intervals.append({"route": route_id, "start": horizon, "end": horizon, "cost_at_start": str(value)})
    if intervals:
        intervals[-1]["end"] = None
    optimal_ids = {interval["route"] for interval in intervals}
    return {
        "frontier": [
            {**route, "D": str(route["D"]), "A": str(route["A"])}
            for route in frontier
        ],
        "dominated": dominated,
        "pairwise_breakpoints": breakpoints,
        "optimal_integer_intervals": intervals,
        "non_dominated_never_optimal": [route["id"] for route in frontier if route["id"] not in optimal_ids],
        "theorem": "same-preservation route with D<= and A<= dominates for every n>=1",
    }


def _invalid_generator(generator_id: str, source_id: str, status: str) -> TransformationGenerator:
    def generate(state: RepresentationState) -> Iterable[RepresentationTransition]:
        if state.id == source_id:
            yield RepresentationTransition(
                generator_id,
                state.id,
                None,
                1,
                preservation_status=status,
                preservation_certificate={"reason": "controlled failure fixture"},
            )
    return TransformationGenerator(generator_id, generate)


def build_quotient_merge_search(
    source_experiment: Sequence[Sequence[Number]],
    prior: Sequence[Number],
    losses: Sequence[Sequence[Number]],
) -> tuple[RepresentationState, list[TransformationGenerator], dict[str, Any]]:
    """Build implicit compatible-block merges for the exact quotient bridge."""
    state_count = len(source_experiment[0])
    loss_rows = [[frac(value) for value in row] for row in losses]
    optimal_actions = []
    for row in loss_rows:
        best = min(row)
        optimal_actions.append(frozenset(index for index, value in enumerate(row) if value == best))
    initial_blocks = tuple((index,) for index in range(state_count))

    def state_for(blocks: tuple[tuple[int, ...], ...]) -> RepresentationState:
        canonical = tuple(sorted(tuple(sorted(block)) for block in blocks))
        block_count = len(canonical)
        return RepresentationState(
            id=f"partition:{canonical!r}",
            regime="TASK_SUFFICIENT_PARTITION",
            terminal_solve_cost=100 * block_count,
            terminal_algorithm="BLOCK_SOLVER",
            terminal_lower_bound=100,
            payload=canonical,
            metadata={"blocks": canonical},
        )

    initial = state_for(initial_blocks)

    def merge_generator(state: RepresentationState) -> Iterable[RepresentationTransition]:
        blocks = tuple(state.payload)
        for left_index in range(len(blocks)):
            for right_index in range(left_index + 1, len(blocks)):
                left, right = blocks[left_index], blocks[right_index]
                common = set.intersection(
                    *(set(optimal_actions[symbol]) for symbol in (*left, *right))
                )
                if not common:
                    continue
                merged = [block for index, block in enumerate(blocks) if index not in {left_index, right_index}]
                merged.append(tuple(sorted((*left, *right))))
                target = state_for(tuple(merged))
                yield RepresentationTransition(
                    "merge_compatible_blocks",
                    state.id,
                    target,
                    1,
                    precondition_witness={"common_optimal_actions": sorted(common)},
                    preservation_status="VERIFIED_EXACT",
                    preservation_certificate={
                        "criterion": "all symbols in merged block share a Bayes-optimal action",
                        "common_optimal_actions": sorted(common),
                    },
                    structural_effect="merge compatible task symbols",
                    operation_counts={"merge_tested": 1},
                )

    expected = task_sufficient_quotient(source_experiment, prior, losses)
    return initial, [TransformationGenerator("merge_compatible_blocks", merge_generator)], {
        "expected_minimum_blocks": expected["minimum_quotient_states"],
        "expected_blocks": expected["blocks"],
        "identity": "canonical sorted partition of source symbols",
    }


def _dfs_reachability(adjacency: tuple[tuple[int, ...], ...], start: int) -> tuple[set[int], int]:
    visited = {start}
    stack = [start]
    operations = 1
    while stack:
        node = stack.pop()
        for neighbor in adjacency[node]:
            operations += 1
            if neighbor not in visited:
                visited.add(neighbor)
                stack.append(neighbor)
    return visited, operations


def _scc_decomposition(adjacency: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], tuple[tuple[int, ...], ...], int]:
    n = len(adjacency)
    reverse = [[] for _ in range(n)]
    operations = 0
    for node, row in enumerate(adjacency):
        operations += 1
        for neighbor in row:
            reverse[neighbor].append(node)
            operations += 1
    seen: set[int] = set()
    order: list[int] = []

    def first(node: int) -> None:
        nonlocal operations
        seen.add(node)
        operations += 1
        for neighbor in adjacency[node]:
            operations += 1
            if neighbor not in seen:
                first(neighbor)
        order.append(node)

    for node in range(n):
        if node not in seen:
            first(node)
    labels = [-1] * n

    def second(node: int, component: int) -> None:
        nonlocal operations
        labels[node] = component
        operations += 1
        for neighbor in reverse[node]:
            operations += 1
            if labels[neighbor] == -1:
                second(neighbor, component)

    component_count = 0
    for node in reversed(order):
        if labels[node] == -1:
            second(node, component_count)
            component_count += 1
    condensation_sets = [set() for _ in range(component_count)]
    for node, row in enumerate(adjacency):
        for neighbor in row:
            if labels[node] != labels[neighbor]:
                condensation_sets[labels[node]].add(labels[neighbor])
            operations += 1
    condensation = tuple(tuple(sorted(row)) for row in condensation_sets)
    return tuple(labels), condensation, operations


def _transitive_closure(adjacency: tuple[tuple[int, ...], ...]) -> tuple[tuple[bool, ...], int]:
    n = len(adjacency)
    closure = [[False] * n for _ in range(n)]
    operations = 0
    for node, row in enumerate(adjacency):
        closure[node][node] = True
        operations += 1
        for neighbor in row:
            closure[node][neighbor] = True
            operations += 1
    for middle in range(n):
        for left in range(n):
            operations += 1
            if closure[left][middle]:
                for right in range(n):
                    operations += 1
                    closure[left][right] = closure[left][right] or closure[middle][right]
    return tuple(tuple(row) for row in closure), operations


def _graph_state_id(kind: str, payload: Any) -> str:
    return f"directed:{kind}:{payload!r}"


def build_directed_reachability_search(
    graph: Sequence[Sequence[int]],
    queries: Sequence[tuple[int, int]],
) -> tuple[RepresentationState, list[TransformationGenerator], dict[str, Any]]:
    """Create lazy RAW -> SCC -> CLOSURE generators with exact answers."""
    adjacency = tuple(tuple(sorted(set(int(value) for value in row))) for row in graph)
    n = len(adjacency)
    if n == 0 or any(neighbor < 0 or neighbor >= n for row in adjacency for neighbor in row):
        raise ValueError("graph must be non-empty with valid endpoints")
    edge_count = sum(len(row) for row in adjacency)
    direct_per_query = n + edge_count
    initial = RepresentationState(
        id=_graph_state_id("RAW", adjacency),
        regime="RAW_GRAPH",
        terminal_solve_cost=direct_per_query,
        terminal_algorithm="BFS_PER_QUERY",
        terminal_lower_bound=1,
        payload=adjacency,
        metadata={"kind": "RAW", "nodes": n, "edges": edge_count},
    )

    def raw_answers(value: tuple[tuple[int, ...], ...]) -> list[bool]:
        return [right in _dfs_reachability(value, left)[0] for left, right in queries]

    expected_answers = raw_answers(adjacency)

    def raw_to_scc(state: RepresentationState) -> Iterable[RepresentationTransition]:
        if state.id != initial.id:
            return ()
        labels, condensation, operations = _scc_decomposition(adjacency)
        component_count = len(condensation)
        cond_edges = sum(len(row) for row in condensation)
        target_payload = (adjacency, labels, condensation)
        target = RepresentationState(
            id=_graph_state_id("SCC", target_payload),
            regime="SCC_CONDENSATION_DAG",
            terminal_solve_cost=component_count + cond_edges,
            terminal_algorithm="CONDENSATION_BFS_PER_QUERY",
            terminal_lower_bound=1,
            payload=target_payload,
            metadata={"kind": "SCC", "component_count": component_count, "operation_count": operations},
        )
        target_answers = [
            labels[left] == labels[right]
            or labels[right] in _dfs_reachability(condensation, labels[left])[0]
            for left, right in queries
        ]
        yield RepresentationTransition(
            "compute_scc_condensation",
            state.id,
            target,
            operations,
            precondition_witness={"directed_graph": True, "queries": len(queries)},
            preservation_status=("VERIFIED_EXACT" if target_answers == expected_answers else "INVALID_FOR_TASK"),
            preservation_certificate={"reachability_answers_equal": target_answers == expected_answers},
            structural_effect="RAW_GRAPH -> SCC_CONDENSATION_DAG",
            operation_counts={"nodes_visited": n, "edges_inspected": edge_count, "scc_operations": operations},
        )

    def raw_to_closure(state: RepresentationState) -> Iterable[RepresentationTransition]:
        if state.id != initial.id:
            return ()
        closure, operations = _transitive_closure(adjacency)
        target = RepresentationState(
            id=_graph_state_id("CLOSURE", (adjacency, closure)),
            regime="FULL_REACHABILITY_CLOSURE",
            terminal_solve_cost=1,
            terminal_algorithm="MATRIX_LOOKUP",
            terminal_lower_bound=1,
            payload=(adjacency, closure),
            metadata={"kind": "CLOSURE", "operation_count": operations},
        )
        target_answers = [closure[left][right] for left, right in queries]
        yield RepresentationTransition(
            "compute_full_closure",
            state.id,
            target,
            operations,
            precondition_witness={"directed_graph": True},
            preservation_status=("VERIFIED_EXACT" if target_answers == expected_answers else "INVALID_FOR_TASK"),
            preservation_certificate={"reachability_answers_equal": target_answers == expected_answers},
            structural_effect="RAW_GRAPH -> FULL_REACHABILITY_CLOSURE",
            operation_counts={"closure_operations": operations},
        )

    def scc_to_closure(state: RepresentationState) -> Iterable[RepresentationTransition]:
        if state.regime != "SCC_CONDENSATION_DAG":
            return ()
        original, labels, condensation = state.payload
        closure, closure_operations = _transitive_closure(condensation)
        target_payload = (original, labels, condensation, closure)
        target = RepresentationState(
            id=_graph_state_id("SCC_CLOSURE", target_payload),
            regime="SCC_REACHABILITY_INDEX",
            terminal_solve_cost=1,
            terminal_algorithm="SCC_LABEL_PLUS_DAG_LOOKUP",
            terminal_lower_bound=1,
            payload=target_payload,
            metadata={"kind": "SCC_CLOSURE", "operation_count": closure_operations},
        )
        target_answers = [
            labels[left] == labels[right] or closure[labels[left]][labels[right]]
            for left, right in queries
        ]
        yield RepresentationTransition(
            "close_condensation_dag",
            state.id,
            target,
            closure_operations,
            precondition_witness={"condensation_dag": True, "component_count": len(condensation)},
            preservation_status=("VERIFIED_EXACT" if target_answers == expected_answers else "INVALID_FOR_TASK"),
            preservation_certificate={"reachability_answers_equal": target_answers == expected_answers},
            structural_effect="SCC_CONDENSATION_DAG -> SCC_REACHABILITY_INDEX",
            operation_counts={"condensation_closure_operations": closure_operations},
        )

    return initial, [
        TransformationGenerator("compute_scc_condensation", raw_to_scc),
        TransformationGenerator("compute_full_closure", raw_to_closure),
        TransformationGenerator("close_condensation_dag", scc_to_closure),
    ], {
        "graph": adjacency,
        "queries": list(queries),
        "expected_answers": expected_answers,
        "direct_per_query": direct_per_query,
    }


def run_representation_search_suite() -> dict[str, Any]:
    """Run the finite theorem, implicit search, bridge, and graph fixtures."""
    explicit_r0 = RepresentationState("R0", "RAW", 10, "DIRECT", terminal_lower_bound=1)
    explicit_r1 = RepresentationState("R1", "INTERMEDIATE", 2, "INDEX", terminal_lower_bound=1)
    explicit_r2 = RepresentationState("R2", "COMPILED", 1, "LOOKUP", terminal_lower_bound=1)
    explicit_transitions = {
        "R0": [
            RepresentationTransition("r0_to_r1", "R0", explicit_r1, 5),
            RepresentationTransition("r0_to_r2", "R0", explicit_r2, 20),
        ],
        "R1": [RepresentationTransition("r1_to_r2", "R1", explicit_r2, 1)],
    }
    explicit = search_explicit_route_graph(
        explicit_r0,
        explicit_transitions,
        direct_solve_cost=10,
        reuse_horizon=2,
    )

    greedy_r0 = RepresentationState("G0", "RAW", 100, "DIRECT", terminal_lower_bound=1)
    greedy_a = RepresentationState("GA", "ATTRACTIVE_LATER", 90, "SLOW_INTERMEDIATE", terminal_lower_bound=1)
    greedy_a2 = RepresentationState("GA2", "COMPILED", 1, "LOOKUP", terminal_lower_bound=1)
    greedy_b = RepresentationState("GB", "ATTRACTIVE_NOW", 10, "MEDIUM", terminal_lower_bound=1)

    def greedy_first(state: RepresentationState) -> Iterable[RepresentationTransition]:
        if state.id == "G0":
            yield RepresentationTransition("cheap_enabler", "G0", greedy_a, 1, structural_effect="G0 -> GA")
            yield RepresentationTransition("fast_local", "G0", greedy_b, 5, structural_effect="G0 -> GB")

    def greedy_second(state: RepresentationState) -> Iterable[RepresentationTransition]:
        if state.id == "GA":
            yield RepresentationTransition("compile_after_enabler", "GA", greedy_a2, 1, structural_effect="GA -> GA2")

    greedy_generators = [
        TransformationGenerator("greedy_first", greedy_first),
        TransformationGenerator("greedy_second", greedy_second),
    ]
    greedy = greedy_one_step_choice(greedy_r0, greedy_generators)
    greedy_exact = search_representation_routes(
        greedy_r0,
        greedy_generators,
        direct_solve_cost=100,
    )
    bounded = search_representation_routes(
        greedy_r0,
        greedy_generators,
        direct_solve_cost=100,
        max_expansions=1,
    )

    no_better_r0 = RepresentationState("N0", "RAW", 10, "DIRECT", terminal_lower_bound=1)
    no_better_target = RepresentationState("N1", "EASIER_BUT_EXPENSIVE", 2, "INDEX", terminal_lower_bound=2)

    def no_better_generator(state: RepresentationState) -> Iterable[RepresentationTransition]:
        if state.id == "N0":
            yield RepresentationTransition("expensive_transform", "N0", no_better_target, 10)

    no_better = search_representation_routes(
        no_better_r0,
        [TransformationGenerator("expensive_transform", no_better_generator)],
        direct_solve_cost=10,
    )

    failure = search_representation_routes(
        no_better_r0,
        [_invalid_generator("invalid_semantics", "N0", "INVALID_FOR_TASK")],
        direct_solve_cost=10,
    )

    bad_root = RepresentationState("B0", "RAW", 5, "DIRECT", terminal_lower_bound=1)
    bad_states = {"B0": bad_root}
    for depth in range(3):
        for index in range(3 ** (depth + 1)):
            state_id = f"B{depth + 1}-{index}"
            bad_states[state_id] = RepresentationState(
                state_id,
                "UNHELPFUL_STRUCTURE",
                100,
                "SLOW_SOLVER",
                terminal_lower_bound=100,
            )

    def bad_tree_generator(state: RepresentationState) -> Iterable[RepresentationTransition]:
        if state.id == "B0":
            children = [f"B1-{index}" for index in range(3)]
        elif state.id.startswith("B") and "-" in state.id:
            depth_text, index_text = state.id[1:].split("-")
            depth = int(depth_text)
            if depth >= 3:
                return
            children = [
                f"B{depth + 1}-{int(index_text) * 3 + offset}"
                for offset in range(3)
            ]
        else:
            return
        for child in children:
            yield RepresentationTransition("expand_unhelpful", state.id, bad_states[child], 0)

    bad_generator = TransformationGenerator("expand_unhelpful", bad_tree_generator)
    uninformed_bad = search_representation_routes(
        bad_root,
        [bad_generator],
        direct_solve_cost=5,
        use_lower_bound=False,
    )
    bounded_bad = search_representation_routes(
        bad_root,
        [bad_generator],
        direct_solve_cost=5,
        use_lower_bound=True,
    )

    quotient_source = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    quotient_prior = [Fraction(1, 4)] * 4
    quotient_losses = [[0, 0, 0], [0, 0, 0], [0, 1, 1], [1, 0, 1]]
    quotient_initial, quotient_generators, quotient_expected = build_quotient_merge_search(
        quotient_source, quotient_prior, quotient_losses
    )
    quotient_search = search_representation_routes(
        quotient_initial,
        quotient_generators,
        direct_solve_cost=quotient_initial.terminal_solve_cost,
    )
    quotient_blocks = literal_eval(
        quotient_search["best_route"]["representation_sequence"][-1].split(":", 1)[1]
    )

    graph = [[1], [2], [0, 3], [4], [5], [3]]
    graph_queries_small = [(0, 5)]
    graph_queries_many = [(0, 5)] * 10
    graph_initial_small, graph_generators_small, graph_meta_small = build_directed_reachability_search(
        graph, graph_queries_small
    )
    graph_initial_many, graph_generators_many, graph_meta_many = build_directed_reachability_search(
        graph, graph_queries_many
    )
    graph_small = search_representation_routes(
        graph_initial_small,
        graph_generators_small,
        direct_solve_cost=graph_meta_small["direct_per_query"],
        reuse_horizon=1,
        resource="operation_units",
    )
    graph_many = search_representation_routes(
        graph_initial_many,
        graph_generators_many,
        direct_solve_cost=graph_meta_many["direct_per_query"],
        reuse_horizon=10,
        resource="operation_units",
    )
    one_step_graph_routes = []
    for generator in graph_generators_many[:2]:
        for transition in generator.generate(graph_initial_many):
            if transition.target is not None and transition.preservation_status == "VERIFIED_EXACT":
                one_step_graph_routes.append({
                    "generator": generator.id,
                    "cost": str(frac(transition.cost) + 10 * transition.target.terminal_solve_cost),
                })

    frontier = route_economics_frontier([
        {"id": "direct", "D": 0, "A": 10},
        {"id": "middle", "D": 3, "A": 8},
        {"id": "fast", "D": 6, "A": 0},
    ])

    return {
        "protocol": "agent1-implicit-representation-search-v1",
        "starting_commit": "19060209153d425969f8ecc67b0e175cc7916691",
        "corpus_policy": "no new corpus; finite generated fixtures only",
        "literature_audit": representation_search_literature_audit(),
        "explicit_graph": explicit,
        "greedy_counterexample": {"greedy": greedy, "exact": greedy_exact},
        "bounded_search": bounded,
        "no_better_route": no_better,
        "preservation_failure": failure,
        "lower_bound_experiment": {
            "uninformed": uninformed_bad,
            "admissible_lower_bound": bounded_bad,
            "same_optimum": uninformed_bad["best_route_cost"] == bounded_bad["best_route_cost"],
            "expanded_reduction": (
                uninformed_bad["search_cost"]["states_expanded"]
                - bounded_bad["search_cost"]["states_expanded"]
            ),
        },
        "quotient_regression": {
            "expected": quotient_expected,
            "search_status": quotient_search["status"],
            "search_best_route": quotient_search["best_route"],
            "terminal_blocks": quotient_blocks,
            "matches_minimum": len(quotient_blocks) == quotient_expected["expected_minimum_blocks"],
        },
        "directed_reachability": {
            "small_workload": graph_small,
            "reused_workload": graph_many,
            "small_metadata": graph_meta_small,
            "many_metadata": graph_meta_many,
            "answers_preserved": graph_meta_many["expected_answers"] == [True] * 10,
            "one_step_routes": one_step_graph_routes,
            "multi_step_beats_all_one_step": all(
                int(graph_many["best_route_cost"]) < int(route["cost"])
                for route in one_step_graph_routes
            ),
        },
        "reuse_horizon_frontier": frontier,
        "complexity": {
            "explicit_graph": "POLYNOMIAL shortest path with nonnegative edge/goal costs",
            "implicit_generator_search": "KNOWN_EXPONENTIAL in generated state space in the worst case",
            "quotient_discovery": "NP-HARD by existing Set-Cover reduction embedded in compatible-merge generators",
            "bounded_search": "KNOWN_RESULT incumbent with sound frontier lower bound; not globally optimal unless gap=0",
        },
        "hardness": {
            "status": "KNOWN_RESULT",
            "scope": "implicit compatible-partition generator space",
            "claim": "a polynomial exact optimizer for this implicit space would solve the existing NP-hard minimum quotient problem",
        },
        "epistemic": {
            "explicit_shortest_path": "PROVED",
            "finite_implicit_fixtures": "VERIFIED_FINITE_CASE",
            "greedy_failure": "COUNTEREXAMPLE",
            "general_implicit_representation_search": "UNKNOWN",
        },
    }


def representation_search_literature_audit() -> list[dict[str, Any]]:
    return [
        {
            "theory": "Dijkstra shortest path",
            "classification": "ESTABLISHED_THEORY",
            "source": "https://ir.cwi.nl/pub/23612",
            "relation": "explicit nonnegative route graph special case",
        },
        {
            "theory": "A* admissible heuristic search",
            "classification": "ESTABLISHED_THEORY",
            "source": "https://www.cs.auckland.ac.nz/courses/compsci709s2c/resources/Mike.d/astarNilsson.pdf",
            "relation": "state terminal lower bound supplies the finite admissible heuristic",
        },
        {
            "theory": "STRIPS planning",
            "classification": "FORMAL_ANALOGY",
            "source": "https://ai.stanford.edu/~nilsson/publications.html",
            "relation": "preconditions and effects make the implicit space planning-like; no planning completeness claim",
        },
        {
            "theory": "equality saturation / egg",
            "classification": "SPECIALIZED_REPRESENTATION_SEARCH",
            "source": "https://homes.cs.washington.edu/~cnandi/docs/popl21-cr.pdf",
            "relation": "compositional rewrite search with extraction, but different equivalence and cost semantics",
        },
        {
            "theory": "knowledge compilation",
            "classification": "ESTABLISHED_THEORY",
            "source": "https://www.cril.univ-artois.fr/~marquis/darwiche-marquis-jair02.pdf",
            "relation": "offline representation construction and online query reuse",
        },
        {
            "theory": "superoptimization",
            "classification": "ANALOGY",
            "source": "https://www.brinckerhoff.org/clements/2214-csc530/Files/massalin-1987.pdf",
            "relation": "search over transformations for a cheaper terminal program; MAT-SI does not claim instruction-level equivalence",
        },
        {
            "theory": "physical database/index selection",
            "classification": "KNOWN_RESULT",
            "source": "https://doi.org/10.1093/comjnl/28.4.398",
            "relation": "workload-dependent representation/index construction and resource constraints",
        },
        {
            "theory": "multiobjective shortest path",
            "classification": "FORMAL_ANALOGY",
            "source": "https://arxiv.org/abs/1802.08637",
            "relation": "frontier machinery exists; this block selects one resource and does not open general Pareto theory",
        },
    ]


__all__ = [
    "RepresentationState",
    "RepresentationTransition",
    "TransformationGenerator",
    "build_directed_reachability_search",
    "build_quotient_merge_search",
    "greedy_one_step_choice",
    "representation_search_literature_audit",
    "route_economics_frontier",
    "run_representation_search_suite",
    "search_explicit_route_graph",
    "search_representation_routes",
]
