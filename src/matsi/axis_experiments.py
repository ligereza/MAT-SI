"""Experimental separation of structural substrate and evaluator mechanisms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .canonical import apply_operation, get_path
from .kernels import AtomPairKernel, ContentDagKernel, RewriteEgraphKernel
from .metrics import measure_call, sharing_ratio
from .scale import scaled_cases
from .kernels.rewrite_egraph import (
    EGraph,
    _default_rules,
    _saturate,
    _term_from_value,
    _value_from_term,
)


@dataclass(frozen=True)
class EvaluationResult:
    representation: Any
    mechanism_cost: int


class DirectEvaluator:
    name = "direct_evaluator"

    def evaluate(self, substrate: Any, representation: Any, operation: str) -> EvaluationResult:
        value = substrate.decode(representation)
        if operation == "double_reverse":
            result = apply_operation(apply_operation(value, "reverse"), "reverse")
            cost = 2
        else:
            result = apply_operation(value, operation)
            cost = 1
        return EvaluationResult(substrate.encode(result), cost)


class RewriteEvaluator:
    name = "rewrite_equality"

    def __init__(self) -> None:
        self.kernel = RewriteEgraphKernel()

    def evaluate(self, substrate: Any, representation: Any, operation: str) -> EvaluationResult:
        value = substrate.decode(representation)
        if operation == "double_reverse":
            term = _term_from_value(value)
            wrapped = ("reverse", (("reverse", (term,)),))
            reduced, applied = _saturate(wrapped, _default_rules())
            graph = EGraph()
            root = graph.add_term(wrapped)
            reduced_root = graph.add_term(reduced)
            graph.union(root, reduced_root)
            graph.rebuild()
            # The e-graph stores the equivalence proof. The already-rewritten
            # representative is used here because the minimal extractor is not
            # cycle-safe for a union between a term and one of its descendants.
            result = _value_from_term(reduced)
            return EvaluationResult(substrate.encode(result), len(graph.hashcons) + len(applied))
        inner = self.kernel.encode(value)
        transformed = self.kernel.transform(inner, operation)
        result = self.kernel.decode(transformed.representation)
        return EvaluationResult(substrate.encode(result), transformed.cost)


class ReducedRewriteEvaluator:
    """The same generic rewrite schemas without e-classes or equality saturation."""

    name = "reduced_tree_rewrite"

    def evaluate(self, substrate: Any, representation: Any, operation: str) -> EvaluationResult:
        value = substrate.decode(representation)
        term = _term_from_value(value)
        if operation == "double_reverse":
            wrapped = ("reverse", (("reverse", (term,)),))
        else:
            wrapped = ("identity", (term,))
        reduced, applied = _saturate(wrapped, _default_rules())
        if operation == "double_reverse":
            result = _value_from_term(reduced)
        else:
            result = apply_operation(value, operation)
        return EvaluationResult(substrate.encode(result), len(applied))


def _pareto_dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    dimensions = {
        "description_bytes": "min",
        "evaluation_wall_time_ns": "min",
        "query_wall_time_ns": "min",
        "structural_sharing": "max",
        "fidelity": "max",
    }
    strict = False
    for dimension, direction in dimensions.items():
        if direction == "min":
            if left[dimension] > right[dimension]:
                return False
            strict |= left[dimension] < right[dimension]
        else:
            if left[dimension] < right[dimension]:
                return False
            strict |= left[dimension] > right[dimension]
    return strict


def _frontier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["shape"], row["size"], row["operation"]), []).append(row)
    return [
        {
            "shape": shape,
            "size": size,
            "operation": operation,
            "combinations": [
                row["combination"]
                for row in group
                if not any(_pareto_dominates(other, row) for other in group if other is not row)
            ],
        }
        for (shape, size, operation), group in sorted(groups.items())
    ]


def run_axis_experiment(sizes: Iterable[int] = (10, 100, 1_000)) -> dict[str, Any]:
    substrates = [AtomPairKernel(), ContentDagKernel()]
    evaluators = [DirectEvaluator(), RewriteEvaluator()]
    rows: list[dict[str, Any]] = []
    for case in scaled_cases(sizes):
        source = get_path(case["value"], case["transform"]["source_path"])
        source_path = case["transform"]["source_path"]
        query_path = tuple(case["query_path"])
        for substrate in substrates:
            full_representation = substrate.encode(case["value"])
            source_representation = substrate.encode(source)
            unique, expanded = substrate.sharing(full_representation)
            storage = substrate.storage_breakdown(full_representation)
            query_result, query_runtime = measure_call(
                lambda: substrate.query(full_representation, query_path), repeats=2
            )
            for evaluator in evaluators:
                for operation in ("reverse", "double_reverse"):
                    result, runtime = measure_call(
                        lambda: evaluator.evaluate(substrate, source_representation, operation), repeats=2
                    )
                    expected = (
                        apply_operation(source, "reverse")
                        if operation == "reverse"
                        else source
                    )
                    decoded_result = substrate.decode(result.representation)
                    rows.append(
                        {
                            "substrate": substrate.name,
                            "evaluator": evaluator.name,
                            "combination": f"{substrate.name}+{evaluator.name}",
                            "shape": case["shape"],
                            "size": case["size"],
                            "operation": operation,
                            "query_path": list(query_path),
                            "source_path": list(source_path),
                            "description_bytes": storage["total_bytes"],
                            "structural_sharing": sharing_ratio(unique, expanded),
                            "query_wall_time_ns": query_runtime.wall_time_ns,
                            "query_cpu_time_ns": query_runtime.cpu_time_ns,
                            "evaluation_wall_time_ns": runtime.wall_time_ns,
                            "evaluation_cpu_time_ns": runtime.cpu_time_ns,
                            "evaluation_peak_memory_bytes": runtime.peak_memory_bytes,
                            "evaluation_allocation_blocks": runtime.allocation_blocks,
                            "mechanism_cost": result.mechanism_cost,
                            "fidelity": float(decoded_result == expected),
                            "source_representation_bytes": substrate.size_bytes(source_representation),
                        }
                    )
    reduction = run_rewrite_reduction(sizes)
    return {
        "experiment": "separate_S_and_E",
        "substrates": [substrate.name for substrate in substrates],
        "evaluators": [evaluator.name for evaluator in evaluators],
        "operations": ["reverse", "double_reverse"],
        "rows": rows,
        "pareto_frontier_by_workload": _frontier(rows),
        "rewrite_reduction": reduction,
        "hypothesis_test": {
            "question": "Does e-graph behave better as an evaluator layer over a substrate than as universal U?",
            "answer_status": "provisional",
            "interpretation": "The experiment separates storage and rewrite costs; no architecture is selected.",
        },
    }


def run_rewrite_reduction(sizes: Iterable[int]) -> list[dict[str, Any]]:
    rows = []
    for case in scaled_cases(sizes):
        source = get_path(case["value"], case["transform"]["source_path"])
        for substrate in (AtomPairKernel(), ContentDagKernel()):
            source_representation = substrate.encode(source)
            mechanisms = (RewriteEvaluator(), ReducedRewriteEvaluator())
            for mechanism in mechanisms:
                result, runtime = measure_call(
                    lambda: mechanism.evaluate(substrate, source_representation, "double_reverse"),
                    repeats=2,
                )
                rows.append(
                    {
                        "substrate": substrate.name,
                        "mechanism": mechanism.name,
                        "shape": case["shape"],
                        "size": case["size"],
                        "operation": "double_reverse",
                        "wall_time_ns": runtime.wall_time_ns,
                        "cpu_time_ns": runtime.cpu_time_ns,
                        "peak_memory_bytes": runtime.peak_memory_bytes,
                        "allocation_blocks": runtime.allocation_blocks,
                        "fidelity": float(substrate.decode(result.representation) == source),
                        "mechanism_cost": result.mechanism_cost,
                    }
                )
    return rows
