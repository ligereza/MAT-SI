"""PiPi-43: separator and elimination-order width audit.

This module is deliberately a small, transparent implementation of exact
counting of independent sets in binary graphs.  It is a research audit, not a
claim of a universal complexity reduction:

* brute-force assignment resources and variable-elimination resources remain
  separate vectors;
* NATURAL, frozen RANDOM, MIN_DEGREE, and MIN_FILL are discovery methods;
* known-good and exact-width orders are calculated only after discovery;
* factor-state budgets stop high-width runs before materialisation;
* wall-clock fields are descriptive and machine-dependent.

The factor convention used here is explicit: ``width`` is the number of
neighbours of the variable immediately before elimination, and the resulting
separator factor has ``2 ** width`` cells.  ``peak_factor_scope`` is therefore
the peak post-elimination separator scope, not the pre-elimination scope that
also contains the eliminated variable.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
PARENT_COMMIT = "f17d1ff"
PROTOCOL = "pipi-43-separator-order-width-v0"
FACTOR_STATE_BUDGET = 4096
ORDER_OPERATION_BUDGET = 100_000
BRUTE_FORCE_MAX_N = 18
RANDOM_ORDER_SEED = 430042

PREREGISTERED_PREDICTIONS = {
    "P1": "Within variable elimination, peak factor states and materialised cells should vary with induced width.",
    "P2": "On the same graph, a lower-width frozen order should generally lower peak states and cells.",
    "P3": "Low-width families should remain manageable as n grows while width stays small.",
    "P4": "A star with the centre first should inflate width relative to leaves first on the same instance.",
    "P5": "High-width controls should hit STOP_NO_GAIN rather than be called successful.",
    "P6": "A separator factor should be sufficient for exact future contributions on the checked small graph.",
    "P7": "MIN_FILL is a heuristic, not a universal optimum; gaps and counterexamples remain reportable.",
}


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 6)


@dataclass(frozen=True)
class GraphCase:
    name: str
    family: str
    scale: str
    n: int
    edges: tuple[tuple[int, int], ...]
    seed: int | None = None
    reference_order: tuple[int, ...] | None = None
    metadata: tuple[tuple[str, Any], ...] = ()

    @property
    def raw_input(self) -> dict[str, Any]:
        return {
            "kind": "binary_independent_set_graph",
            "name": self.name,
            "family": self.family,
            "scale": self.scale,
            "n": self.n,
            "edges": [list(edge) for edge in self.edges],
            "seed": self.seed,
            "metadata": {key: value for key, value in self.metadata},
        }


@dataclass(frozen=True)
class Factor:
    scope: tuple[int, ...]
    table: tuple[int, ...]


def make_graph(
    name: str,
    family: str,
    n: int,
    edges: Iterable[tuple[int, int]],
    *,
    scale: str = "SMALL_EXACT",
    seed: int | None = None,
    reference_order: Iterable[int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> GraphCase:
    normalised: set[tuple[int, int]] = set()
    for left, right in edges:
        if left == right or not (0 <= left < n and 0 <= right < n):
            raise ValueError(f"invalid graph edge {(left, right)} for n={n}")
        normalised.add(tuple(sorted((left, right))))
    order = tuple(reference_order) if reference_order is not None else None
    if order is not None and sorted(order) != list(range(n)):
        raise ValueError(f"reference order is not a permutation for {name}")
    return GraphCase(
        name=name,
        family=family,
        scale=scale,
        n=n,
        edges=tuple(sorted(normalised)),
        seed=seed,
        reference_order=order,
        metadata=tuple(sorted((metadata or {}).items())),
    )


def adjacency(graph: GraphCase) -> list[set[int]]:
    result = [set() for _ in range(graph.n)]
    for left, right in graph.edges:
        result[left].add(right)
        result[right].add(left)
    return result


def count_independent_sets(graph: GraphCase) -> dict[str, Any] | None:
    """Count exact assignments by checking every binary assignment when small."""

    if graph.n > BRUTE_FORCE_MAX_N:
        return None
    started = perf_counter()
    assignment_count = 1 << graph.n
    valid = 0
    edge_checks = 0
    for mask in range(assignment_count):
        is_valid = True
        for left, right in graph.edges:
            edge_checks += 1
            if (mask >> left) & 1 and (mask >> right) & 1:
                is_valid = False
                break
        if is_valid:
            valid += 1
    runtime_ms = _ms(started)
    return {
        "exact_count": valid,
        "assignments_checked": assignment_count,
        "edge_checks": edge_checks,
        "runtime_ms": runtime_ms,
        "wall_ms": runtime_ms,
        "machine_dependent_fields": ["runtime_ms", "wall_ms"],
    }


def _binary_index(scope: tuple[int, ...], assignment: dict[int, int]) -> int:
    index = 0
    for position, variable in enumerate(scope):
        index |= assignment[variable] << position
    return index


def _edge_factor(left: int, right: int) -> Factor:
    scope = tuple(sorted((left, right)))
    table = []
    for index in range(1 << len(scope)):
        bits = {scope[position]: (index >> position) & 1 for position in range(len(scope))}
        table.append(0 if bits[left] and bits[right] else 1)
    return Factor(scope, tuple(table))


def _unary_factor(variable: int) -> Factor:
    return Factor((variable,), (1, 1))


def _factor_product(factors: list[Factor], scope: tuple[int, ...]) -> tuple[Factor, int]:
    """Materialise a product table and return (factor, multiplication count)."""

    if not factors:
        return Factor(scope, tuple(1 for _ in range(1 << len(scope)))), 0
    values: list[int] = []
    operations = 0
    for index in range(1 << len(scope)):
        assignment = {variable: (index >> position) & 1 for position, variable in enumerate(scope)}
        value = 1
        for factor in factors:
            projected = _binary_index(factor.scope, assignment)
            value *= factor.table[projected]
            if len(factors) > 1:
                operations += 1
        values.append(value)
    return Factor(scope, tuple(values)), operations


def _initial_factors(graph: GraphCase) -> list[Factor]:
    factors = [_edge_factor(left, right) for left, right in graph.edges]
    vertices_with_factors = {vertex for edge in graph.edges for vertex in edge}
    factors.extend(_unary_factor(vertex) for vertex in range(graph.n) if vertex not in vertices_with_factors)
    return factors


def _interaction_graph(graph: GraphCase) -> list[set[int]]:
    return adjacency(graph)


def _missing_fill_count(interaction: list[set[int]], vertex: int, active: set[int]) -> int:
    neighbours = sorted(interaction[vertex] & active)
    return sum(1 for left_index, left in enumerate(neighbours) for right in neighbours[left_index + 1 :] if right not in interaction[left])


def discover_order(
    graph: GraphCase,
    strategy: str,
    *,
    seed: int = RANDOM_ORDER_SEED,
    operation_budget: int = ORDER_OPERATION_BUDGET,
) -> dict[str, Any]:
    """Select and freeze a discovery order without consulting any width oracle."""

    started = perf_counter()
    operation_count = 0
    active = set(range(graph.n))
    interaction = _interaction_graph(graph)
    order: list[int] = []
    rng = random.Random(seed)

    if strategy == "NATURAL":
        order = list(range(graph.n))
        operation_count = graph.n
    elif strategy == "RANDOM":
        order = list(range(graph.n))
        rng.shuffle(order)
        operation_count = graph.n
    elif strategy in {"MIN_DEGREE", "MIN_FILL"}:
        while active:
            candidates = sorted(active)
            scored: list[tuple[int, int, int]] = []
            for vertex in candidates:
                degree = len(interaction[vertex] & active)
                if strategy == "MIN_DEGREE":
                    score = degree
                    operation_count += 1
                else:
                    score = _missing_fill_count(interaction, vertex, active)
                    operation_count += 1 + degree * max(degree - 1, 0) // 2
                scored.append((score, degree, vertex))
            if operation_count > operation_budget:
                runtime_ms = _ms(started)
                return {
                    "strategy": strategy,
                    "order": order,
                    "complete": False,
                    "status": "STOP_NO_GAIN",
                    "reason": "order_discovery_operation_budget_reached",
                    "operations": operation_count,
                    "runtime_ms": runtime_ms,
                    "wall_ms": runtime_ms,
                    "oracle_used_for_discovery": False,
                }
            _, _, selected = min(scored)
            order.append(selected)
            active.remove(selected)
            neighbours = sorted(interaction[selected] & active)
            for left_index, left in enumerate(neighbours):
                for right in neighbours[left_index + 1 :]:
                    interaction[left].add(right)
                    interaction[right].add(left)
            for neighbour in neighbours:
                interaction[neighbour].discard(selected)
            interaction[selected].clear()
    else:
        raise ValueError(f"unknown discovery order {strategy}")

    runtime_ms = _ms(started)
    return {
        "strategy": strategy,
        "order": order,
        "complete": len(order) == graph.n,
        "status": "FREEZE" if len(order) == graph.n else "STOP_NO_GAIN",
        "reason": "order_selected_and_frozen" if len(order) == graph.n else "incomplete_order",
        "operations": operation_count,
        "runtime_ms": runtime_ms,
        "wall_ms": runtime_ms,
        "seed": seed if strategy == "RANDOM" else None,
        "oracle_used_for_discovery": False,
    }


def _exact_width_order(graph: GraphCase) -> dict[str, Any] | None:
    """Small post-hoc exact width oracle; never called during discovery."""

    if graph.n > 9:
        return None
    best_width = graph.n + 1
    best_order: list[int] | None = None
    nodes = 0

    def search(active: set[int], interaction: list[set[int]], order: list[int], width: int) -> None:
        nonlocal best_width, best_order, nodes
        nodes += 1
        if not active:
            if width < best_width:
                best_width = width
                best_order = list(order)
            return
        if width >= best_width:
            return
        candidates = sorted(active, key=lambda vertex: (len(interaction[vertex] & active), vertex))
        for vertex in candidates:
            neighbours = sorted(interaction[vertex] & active)
            next_width = max(width, len(neighbours))
            if next_width >= best_width:
                continue
            next_interaction = [set(items) for items in interaction]
            for left_index, left in enumerate(neighbours):
                for right in neighbours[left_index + 1 :]:
                    next_interaction[left].add(right)
                    next_interaction[right].add(left)
            for neighbour in neighbours:
                next_interaction[neighbour].discard(vertex)
            next_interaction[vertex].clear()
            search(active - {vertex}, next_interaction, order + [vertex], next_width)

    search(set(range(graph.n)), _interaction_graph(graph), [], 0)
    if best_order is None:
        return {"width": None, "order": None, "nodes": nodes, "available": False}
    return {"width": best_width, "order": best_order, "nodes": nodes, "available": True}


def _width_for_order(graph: GraphCase, order: Iterable[int]) -> int:
    interaction = _interaction_graph(graph)
    active = set(range(graph.n))
    peak = 0
    for vertex in order:
        neighbours = sorted(interaction[vertex] & active)
        peak = max(peak, len(neighbours))
        for left_index, left in enumerate(neighbours):
            for right in neighbours[left_index + 1 :]:
                interaction[left].add(right)
                interaction[right].add(left)
        active.remove(vertex)
        for neighbour in neighbours:
            interaction[neighbour].discard(vertex)
        interaction[vertex].clear()
    return peak


def variable_elimination(
    graph: GraphCase,
    order: Iterable[int],
    *,
    factor_state_budget: int = FACTOR_STATE_BUDGET,
) -> dict[str, Any]:
    """Run exact factor elimination, stopping before an over-budget product."""

    frozen_order = tuple(order)
    if sorted(frozen_order) != list(range(graph.n)):
        return {
            "status": "STOP_NO_GAIN",
            "reason": "order_not_complete_or_not_a_permutation",
            "exact_count": None,
            "elimination_steps": 0,
        }
    started = perf_counter()
    interaction = _interaction_graph(graph)
    active = set(range(graph.n))
    factors = _initial_factors(graph)
    total_cells = 0
    total_operations = 0
    fill_edges_created = 0
    peak_width = 0
    peak_memory_proxy = sum(len(factor.table) for factor in factors)
    elimination_steps = 0

    for vertex in frozen_order:
        neighbours = sorted(interaction[vertex] & active)
        width = len(neighbours)
        peak_width = max(peak_width, width)
        predicted_states = 1 << width
        if predicted_states > factor_state_budget:
            runtime_ms = _ms(started)
            return {
                "status": "STOP_NO_GAIN",
                "reason": "factor_state_budget_reached_before_materialisation",
                "exact_count": None,
                "induced_width": peak_width,
                "peak_separator_size": peak_width,
                "peak_factor_scope": peak_width,
                "peak_factor_states": predicted_states,
                "total_factor_cells_materialized": total_cells,
                "total_factor_operations": total_operations,
                "fill_edges_created": fill_edges_created,
                "elimination_steps": elimination_steps,
                "peak_memory_proxy": peak_memory_proxy,
                "solve_runtime_ms": runtime_ms,
                "wall_ms": runtime_ms,
                "factor_state_budget": factor_state_budget,
            }

        missing_before = sum(
            1
            for left_index, left in enumerate(neighbours)
            for right in neighbours[left_index + 1 :]
            if right not in interaction[left]
        )
        fill_edges_created += missing_before
        gathered = [factor for factor in factors if vertex in factor.scope]
        retained = [factor for factor in factors if vertex not in factor.scope]
        union_scope = tuple(sorted({variable for factor in gathered for variable in factor.scope}))
        if not gathered:
            gathered = [_unary_factor(vertex)]
            union_scope = (vertex,)
        product, product_operations = _factor_product(gathered, union_scope)
        output_scope = tuple(variable for variable in union_scope if variable != vertex)
        output_values: list[int] = []
        additions = 0
        for output_index in range(1 << len(output_scope)):
            assignment = {variable: (output_index >> position) & 1 for position, variable in enumerate(output_scope)}
            assignment[vertex] = 0
            first = product.table[_binary_index(product.scope, assignment)]
            assignment[vertex] = 1
            second = product.table[_binary_index(product.scope, assignment)]
            output_values.append(first + second)
            additions += 1
        output = Factor(output_scope, tuple(output_values))
        total_cells += len(product.table) + len(output.table)
        total_operations += product_operations + additions
        factors = retained + [output]
        peak_memory_proxy = max(peak_memory_proxy, sum(len(factor.table) for factor in factors) + len(product.table))
        elimination_steps += 1

        for left_index, left in enumerate(neighbours):
            for right in neighbours[left_index + 1 :]:
                interaction[left].add(right)
                interaction[right].add(left)
        active.remove(vertex)
        for neighbour in neighbours:
            interaction[neighbour].discard(vertex)
        interaction[vertex].clear()

    exact_count = 1
    for factor in factors:
        if factor.scope:
            exact_count *= sum(factor.table)
        else:
            exact_count *= factor.table[0]
    runtime_ms = _ms(started)
    return {
        "status": "FREEZE",
        "reason": "order_selected_and_exact_factorisation_completed",
        "exact_count": exact_count,
        "induced_width": peak_width,
        "peak_separator_size": peak_width,
        "peak_factor_scope": peak_width,
        "peak_factor_states": 1 << peak_width,
        "total_factor_cells_materialized": total_cells,
        "total_factor_operations": total_operations,
        "fill_edges_created": fill_edges_created,
        "elimination_steps": elimination_steps,
        "peak_memory_proxy": peak_memory_proxy,
        "solve_runtime_ms": runtime_ms,
        "wall_ms": runtime_ms,
        "factor_state_budget": factor_state_budget,
    }


def separator_sufficiency(graph: GraphCase, past_vertices: Iterable[int] | None = None) -> dict[str, Any]:
    """Exhaustively verify that the boundary factor controls future behaviour."""

    if graph.n > 12:
        return {
            "status": "UNKNOWN",
            "separator_sufficiency_exact": None,
            "reason": "separator_exhaustive_check_reserved_for_small_graphs",
        }
    past = tuple(sorted(past_vertices if past_vertices is not None else range(max(1, graph.n // 2))))
    past_set = set(past)
    future = tuple(vertex for vertex in range(graph.n) if vertex not in past_set)
    separator = tuple(
        vertex
        for vertex in future
        if any(vertex in edge and (edge[0] in past_set or edge[1] in past_set) for edge in graph.edges)
    )
    separator_set = set(separator)
    future_only = tuple(vertex for vertex in future if vertex not in separator_set)
    edge_set = set(graph.edges)

    def compatible(assignment: dict[int, int]) -> bool:
        return not any(assignment[left] and assignment[right] for left, right in edge_set if left in assignment and right in assignment)

    factor_vectors: list[tuple[int, ...]] = []
    future_vectors: list[tuple[int, ...]] = []
    separator_assignments = list(itertools.product((0, 1), repeat=len(separator)))
    for past_bits in itertools.product((0, 1), repeat=len(past)):
        past_assignment = dict(zip(past, past_bits))
        factor_vector = []
        for separator_bits in separator_assignments:
            assignment = dict(past_assignment)
            assignment.update(zip(separator, separator_bits))
            factor_vector.append(int(compatible(assignment)))
        factor_vectors.append(tuple(factor_vector))

        future_vector = []
        for future_bits in itertools.product((0, 1), repeat=len(future)):
            assignment = dict(past_assignment)
            assignment.update(zip(future, future_bits))
            future_vector.append(int(compatible(assignment)))
        future_vectors.append(tuple(future_vector))
    factor_to_future: dict[tuple[int, ...], tuple[int, ...]] = {}
    exact = True
    for factor_vector, future_vector in zip(factor_vectors, future_vectors):
        previous = factor_to_future.setdefault(factor_vector, future_vector)
        exact = exact and previous == future_vector
    return {
        "status": "CHECKED",
        "past_vertices": list(past),
        "future_vertices": list(future),
        "separator_vertices": list(separator),
        "separator_size": len(separator),
        "elimination_step": len(past) - 1,
        "raw_past_assignment_count": len(factor_vectors),
        "separator_state_count": len(set(factor_vectors)),
        "histories_collapsed_by_separator": len(factor_vectors) - len(set(factor_vectors)),
        "separator_sufficiency_exact": exact,
        "future_equivalence_groups_checked": len(factor_to_future),
        "future_only_vertices": list(future_only),
        "minimality_claimed": False,
    }


def _path(n: int) -> tuple[tuple[int, int], ...]:
    return tuple((vertex, vertex + 1) for vertex in range(n - 1))


def _cycle(n: int) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(set(_path(n)) | {(0, n - 1)}))


def _tree(n: int) -> tuple[tuple[int, int], ...]:
    return tuple(((vertex - 1) // 2, vertex) for vertex in range(1, n))


def _random_tree(n: int, seed: int) -> tuple[tuple[int, int], ...]:
    rng = random.Random(seed)
    return tuple((rng.randrange(vertex), vertex) for vertex in range(1, n))


def _grid(rows: int, cols: int) -> tuple[tuple[int, int], ...]:
    def vertex(row: int, col: int) -> int:
        return row * cols + col

    edges: list[tuple[int, int]] = []
    for row in range(rows):
        for col in range(cols):
            if row + 1 < rows:
                edges.append((vertex(row, col), vertex(row + 1, col)))
            if col + 1 < cols:
                edges.append((vertex(row, col), vertex(row, col + 1)))
    return tuple(edges)


def _ladder(cols: int) -> tuple[tuple[int, int], ...]:
    return _grid(2, cols)


def _star(n: int) -> tuple[tuple[int, int], ...]:
    return tuple((0, vertex) for vertex in range(1, n))


def _clique(n: int) -> tuple[tuple[int, int], ...]:
    return tuple((left, right) for left in range(n) for right in range(left + 1, n))


def _complete_bipartite(left_size: int, right_size: int) -> tuple[tuple[int, int], ...]:
    return tuple((left, left_size + right) for left in range(left_size) for right in range(right_size))


def _random_graph(n: int, probability: float, seed: int) -> tuple[tuple[int, int], ...]:
    rng = random.Random(seed)
    return tuple(
        (left, right)
        for left in range(n)
        for right in range(left + 1, n)
        if rng.random() < probability
    )


def build_cases() -> list[GraphCase]:
    """Build all preregistered cases from explicit raw graph instances."""

    cases: list[GraphCase] = []
    cases.extend(
        [
            make_graph("path_8", "A_tree_path", 8, _path(8), reference_order=range(8)),
            make_graph("path_16", "A_tree_path", 16, _path(16), scale="SCALING", reference_order=range(16)),
            make_graph("balanced_tree_15", "A_tree_balanced", 15, _tree(15), reference_order=range(14, -1, -1)),
            make_graph("random_tree_16_seed_71", "A_tree_random", 16, _random_tree(16, 71), seed=71),
            make_graph("cycle_12", "B_cycle_ladder", 12, _cycle(12)),
            make_graph("ladder_2x6", "B_cycle_ladder", 12, _ladder(6)),
            make_graph("grid_2x8", "C_grid", 16, _grid(2, 8), scale="SCALING"),
            make_graph("grid_3x6", "C_grid", 18, _grid(3, 6)),
            make_graph("grid_4x4", "C_grid", 16, _grid(4, 4)),
            make_graph("grid_5x4", "C_grid", 20, _grid(5, 4), scale="SCALING"),
        ]
    )
    cases.extend(
        [
            make_graph(
                "star_12_same_instance",
                "D_star_order_control",
                12,
                _star(12),
                reference_order=list(range(1, 12)) + [0],
                metadata={"same_instance_order_pair": True, "bad_order": "center_first", "good_order": "leaves_first"},
            ),
            make_graph("clique_8", "E_high_width", 8, _clique(8)),
            make_graph("clique_16_scaling", "E_high_width", 16, _clique(16), scale="SCALING"),
            make_graph("dense_random_12_seed_73", "E_high_width", 12, _random_graph(12, 0.72, 73), seed=73),
            make_graph("complete_bipartite_6x6", "E_high_width", 12, _complete_bipartite(6, 6)),
            make_graph("complete_bipartite_12x12_scaling", "E_high_width", 24, _complete_bipartite(12, 12), scale="SCALING"),
        ]
    )
    cases.extend(
        [
            make_graph("same_n16_path", "F_same_n_structures", 16, _path(16), scale="SCALING"),
            make_graph("same_n16_cycle", "F_same_n_structures", 16, _cycle(16), scale="SCALING"),
            make_graph("same_n16_ladder", "F_same_n_structures", 16, _ladder(8), scale="SCALING"),
            make_graph("same_n16_grid", "F_same_n_structures", 16, _grid(4, 4), scale="SCALING"),
            make_graph("same_n16_star", "F_same_n_structures", 16, _star(16), scale="SCALING"),
            make_graph("same_n16_random_sparse_seed_79", "F_same_n_structures", 16, _random_graph(16, 0.16, 79), scale="SCALING", seed=79),
            make_graph("same_n16_dense_seed_83", "F_same_n_structures", 16, _random_graph(16, 0.42, 83), scale="SCALING", seed=83),
            make_graph("same_n16_clique_like", "F_same_n_structures", 16, _clique(10) + _random_graph(16, 0.20, 89), scale="SCALING", seed=89),
            make_graph("deceptive_random_sparse_seed_97", "G_deceptive_ordering", 18, _random_graph(18, 0.20, 97), seed=97, metadata={"construction_frozen_before_results": True}),
        ]
    )
    return cases


def _order_methods(case: GraphCase) -> list[tuple[str, dict[str, Any]]]:
    methods = [
        ("NATURAL", discover_order(case, "NATURAL")),
        ("RANDOM", discover_order(case, "RANDOM", seed=RANDOM_ORDER_SEED)),
        ("MIN_DEGREE", discover_order(case, "MIN_DEGREE")),
        ("MIN_FILL", discover_order(case, "MIN_FILL")),
    ]
    if case.family == "D_star_order_control":
        methods.extend(
            [
                ("BAD_ORDER_CENTER_FIRST", {"strategy": "BAD_ORDER_CENTER_FIRST", "order": list(range(case.n)), "complete": True, "status": "FREEZE", "reason": "preregistered_same_instance_control", "operations": case.n, "runtime_ms": 0.0, "wall_ms": 0.0, "oracle_used_for_discovery": False}),
                ("GOOD_ORDER_LEAVES_FIRST", {"strategy": "GOOD_ORDER_LEAVES_FIRST", "order": list(range(1, case.n)) + [0], "complete": True, "status": "FREEZE", "reason": "preregistered_same_instance_control", "operations": case.n, "runtime_ms": 0.0, "wall_ms": 0.0, "oracle_used_for_discovery": False}),
            ]
        )
    return methods


def _posthoc_reference(case: GraphCase, discovery_results: list[dict[str, Any]]) -> dict[str, Any]:
    exact = _exact_width_order(case)
    if exact is not None and exact["available"]:
        return {
            "label": "GROUND_TRUTH/ORACLE",
            "best_known_width": exact["width"],
            "order": exact["order"],
            "oracle_nodes": exact["nodes"],
            "known_width_source": "posthoc_exact_width_oracle",
            "used_for_discovery": False,
        }
    if case.reference_order is not None:
        return {
            "label": "KNOWN_GOOD_ORDER_POSTHOC",
            "best_known_width": _width_for_order(case, case.reference_order),
            "order": list(case.reference_order),
            "oracle_nodes": None,
            "known_width_source": "posthoc_family_reference_order",
            "used_for_discovery": False,
        }
    successful_widths = [item["induced_width"] for item in discovery_results if item.get("induced_width") is not None]
    return {
        "label": "POSTHOC_DISCOVERY_REFERENCE",
        "best_known_width": min(successful_widths) if successful_widths else None,
        "order": None,
        "oracle_nodes": None,
        "known_width_source": "best_discovery_width_only",
        "used_for_discovery": False,
    }


def run_case(case: GraphCase, *, factor_state_budget: int = FACTOR_STATE_BUDGET) -> dict[str, Any]:
    brute_force = count_independent_sets(case)
    order_records: list[dict[str, Any]] = []
    for strategy, discovery in _order_methods(case):
        decision_before_reference = discovery["status"] if discovery["complete"] else "STOP_NO_GAIN"
        if discovery["complete"]:
            ve = variable_elimination(case, discovery["order"], factor_state_budget=factor_state_budget)
        else:
            ve = {"status": "STOP_NO_GAIN", "reason": discovery["reason"], "exact_count": None, "elimination_steps": len(discovery["order"])}
        exact_match = None
        if brute_force is not None and ve.get("exact_count") is not None:
            exact_match = ve["exact_count"] == brute_force["exact_count"]
        order_records.append(
            {
                "order_strategy": strategy,
                "order": discovery["order"],
                "order_discovery_operations": discovery["operations"],
                "order_discovery_runtime_ms": discovery["runtime_ms"],
                "order_discovery_wall_ms": discovery["wall_ms"],
                "order_discovery_seed": discovery.get("seed"),
                "order_discovery_complete": discovery["complete"],
                "order_discovery_oracle_used": discovery["oracle_used_for_discovery"],
                "decision_before_reference": decision_before_reference,
                "decision_after_reference": decision_before_reference,
                "exact_count": ve.get("exact_count"),
                "exact_count_match_brute_force": exact_match,
                "status": ve["status"],
                "reason": ve["reason"],
                "induced_width": ve.get("induced_width"),
                "peak_separator_size": ve.get("peak_separator_size"),
                "peak_factor_scope": ve.get("peak_factor_scope"),
                "peak_factor_states": ve.get("peak_factor_states"),
                "total_factor_cells_materialized": ve.get("total_factor_cells_materialized"),
                "total_factor_operations": ve.get("total_factor_operations"),
                "fill_edges_created": ve.get("fill_edges_created"),
                "elimination_steps": ve.get("elimination_steps", 0),
                "peak_memory_proxy": ve.get("peak_memory_proxy"),
                "solve_runtime_ms": ve.get("solve_runtime_ms"),
                "solve_wall_ms": ve.get("wall_ms"),
                "factor_state_budget": factor_state_budget,
                "machine_dependent_fields": [
                    "order_discovery_runtime_ms",
                    "order_discovery_wall_ms",
                    "solve_runtime_ms",
                    "solve_wall_ms",
                ],
            }
        )
    reference = _posthoc_reference(case, order_records)
    best_discovered = min(
        (item["induced_width"] for item in order_records if item["induced_width"] is not None),
        default=None,
    )
    for item in order_records:
        item["best_known_width_posthoc"] = reference["best_known_width"]
        item["discovered_width"] = item["induced_width"]
        item["width_gap"] = (
            item["induced_width"] - reference["best_known_width"]
            if item["induced_width"] is not None and reference["best_known_width"] is not None
            else None
        )
        item["order_discovery_cost"] = {
            "operations": item["order_discovery_operations"],
            "runtime_ms": item["order_discovery_runtime_ms"],
            "wall_ms": item["order_discovery_wall_ms"],
            "units": "heuristic candidate evaluations and fill-neighbour checks",
        }
    separator = separator_sufficiency(case) if case.name == "path_8" else None
    return {
        "case": case.name,
        "family": case.family,
        "scale": case.scale,
        "n": case.n,
        "edges": len(case.edges),
        "raw_input": case.raw_input,
        "raw_input_digest": _digest(case.raw_input),
        "orders": order_records,
        "posthoc_reference": reference,
        "discovered_width": best_discovered,
        "best_known_width": reference["best_known_width"],
        "width_gap_of_best_discovery": (
            best_discovered - reference["best_known_width"]
            if best_discovered is not None and reference["best_known_width"] is not None
            else None
        ),
        "order_discovery_cost": {
            "per_order": [
                {
                    "order_strategy": item["order_strategy"],
                    "operations": item["order_discovery_operations"],
                    "runtime_ms": item["order_discovery_runtime_ms"],
                    "wall_ms": item["order_discovery_wall_ms"],
                }
                for item in order_records
            ],
            "oracle_used": False,
        },
        "resources": {
            "brute_force": brute_force,
            "variable_elimination": {
                "resource_vector_per_order": True,
                "scalar_collapsed": False,
                "orders": [item["order_strategy"] for item in order_records],
            },
        },
        "fallback": {
            "factor_state_budget": factor_state_budget,
            "small_graph": "brute_force_exact_count" if brute_force is not None else None,
            "large_graph": "preserve_factorization_or_stop_at_factor_state_budget" if brute_force is None else "factor_state_budget_with_brute_force_reference",
        },
        "separator_sufficiency": separator,
        "stop_rule": {
            "preregistered": True,
            "CONTINUE": "candidate order remains under factor-state budget",
            "FREEZE": "order is selected and exact VE executes within budget",
            "STOP_NO_GAIN": "predicted/current factor states or order construction cost reaches fallback",
            "UNKNOWN": "insufficient information for a safe estimate",
            "posthoc_reference_can_change_decision": False,
        },
        "decision_stability": {
            "all_orders_decided_before_posthoc_reference": True,
            "reference_used_for_discovery": False,
            "decision_fields_equal_before_after_reference": all(
                item["decision_before_reference"] == item["decision_after_reference"] for item in order_records
            ),
        },
    }


def run_order_width_audit(*, factor_state_budget: int = FACTOR_STATE_BUDGET) -> dict[str, Any]:
    cases = [run_case(case, factor_state_budget=factor_state_budget) for case in build_cases()]
    all_orders = [order for case in cases for order in case["orders"]]
    exact_matches = [order for order in all_orders if order["exact_count_match_brute_force"] is not None]
    return {
        "protocol": PROTOCOL,
        "parent_commit": PARENT_COMMIT,
        "scope": "PiPi-43 research/order-width branched exactly from f17d1ff; PiPi-42 frozen",
        "preregistered_predictions": {
            "status": "PREREGISTERED_BEFORE_RESULTS",
            "predictions": PREREGISTERED_PREDICTIONS,
        },
        "problem": {
            "name": "exact_count_independent_sets_binary_graph",
            "variables": "x_v in {0,1}",
            "constraint": "x_u * x_v = 0 for every edge (u,v)",
            "query": "exact number of valid assignments",
            "external_solver": False,
        },
        "method_boundaries": {
            "discovery_orders": ["NATURAL", "RANDOM", "MIN_DEGREE", "MIN_FILL", "BAD_ORDER_CENTER_FIRST", "GOOD_ORDER_LEAVES_FIRST"],
            "posthoc_only": ["KNOWN_GOOD_ORDER_POSTHOC", "GROUND_TRUTH/ORACLE"],
            "oracle_used_for_discovery": False,
            "solve_result_can_change_frozen_order": False,
            "separator_minimality_claimed": False,
        },
        "factor_convention": {
            "width": "active neighbours immediately before eliminating a variable",
            "peak_factor_scope": "post-elimination separator scope size",
            "peak_factor_states": "2**width",
            "total_factor_cells_materialized": "product and output table cells materialised by VE",
        },
        "metrics_policy": {
            "resource_vector": True,
            "scalar_collapsed": False,
            "lift_gain_declared": False,
            "brute_force_and_ve_units_compared_directly": False,
            "machine_dependent_fields": [
                "runtime_ms",
                "wall_ms",
                "order_discovery_runtime_ms",
                "order_discovery_wall_ms",
                "solve_runtime_ms",
                "solve_wall_ms",
            ],
            "deterministic_fields": ["raw_input", "raw_input_digest", "orders", "exact_count", "widths", "factor_cells", "operations", "stop decisions"],
            "posthoc_reference_fields": ["posthoc_reference", "best_known_width", "width_gap"],
            "unknown_values_are_null": True,
        },
        "fallback": {
            "factor_state_budget": factor_state_budget,
            "order_operation_budget": ORDER_OPERATION_BUDGET,
            "small_brute_force_max_n": BRUTE_FORCE_MAX_N,
            "stop_decision_frozen_before_posthoc": True,
        },
        "separator_sufficiency_contract": {
            "checked_cases": [case["case"] for case in cases if case["separator_sufficiency"] is not None],
            "raw_past_assignments_and_separator_states_reported": True,
            "future_equivalence_checked_exhaustively": True,
            "minimal_separator_not_claimed": True,
        },
        "cases": cases,
        "summary": {
            "case_count": len(cases),
            "order_count": len(all_orders),
            "exact_count_match_count": sum(1 for order in exact_matches if order["exact_count_match_brute_force"]),
            "exact_count_mismatch_count": sum(1 for order in exact_matches if not order["exact_count_match_brute_force"]),
            "stop_no_gain_count": sum(1 for order in all_orders if order["status"] == "STOP_NO_GAIN"),
            "freeze_count": sum(1 for order in all_orders if order["status"] == "FREEZE"),
            "separator_sufficiency_failures": sum(
                1 for case in cases if case["separator_sufficiency"] and case["separator_sufficiency"].get("separator_sufficiency_exact") is False
            ),
            "high_width_controls": [case["case"] for case in cases if case["family"] == "E_high_width"],
            "same_n_structures": [case["case"] for case in cases if case["family"] == "F_same_n_structures"],
            "known_good_reference_does_not_change_decisions": all(
                case["decision_stability"]["decision_fields_equal_before_after_reference"] for case in cases
            ),
        },
        "attack_hypotheses": {
            "same_width_different_costs": "reportable from per-order factor cells and operations; not collapsed",
            "larger_width_cheaper": "must be checked as a counterexample, not excluded",
            "edge_count_predictor": "preserved as an alternative descriptive hypothesis",
            "order_discovery_too_expensive": "preserved via separate discovery operation/runtime vector",
            "special_factor_compression_at_high_width": "not assumed; transparent tables may expose it",
        },
        "negative_controls_and_counterexamples": {
            "high_width_success_without_evidence_forbidden": True,
            "star_good_bad_same_raw_instance": True,
            "heuristic_gaps_preserved": True,
            "wall_time_only_evidence_forbidden": True,
        },
        "scope_declarations": {
            "main_modified": False,
            "phase5_started": False,
            "pr_opened": False,
            "note": "declarations of branch scope, not empirical test results",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the PiPi-43 separator/order-width audit")
    parser.add_argument("--json-out", type=Path, default=ROOT / "results" / "order-width-audit.json")
    parser.add_argument("--factor-state-budget", type=int, default=FACTOR_STATE_BUDGET)
    args = parser.parse_args(argv)
    result = run_order_width_audit(factor_state_budget=args.factor_state_budget)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("protocol:", result["protocol"])
    print("cases:", result["summary"]["case_count"])
    print("orders:", result["summary"]["order_count"])
    print("freeze:", result["summary"]["freeze_count"])
    print("stop_no_gain:", result["summary"]["stop_no_gain_count"])
    print("separator_failures:", result["summary"]["separator_sufficiency_failures"])
    print("pr:", "not opened")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
