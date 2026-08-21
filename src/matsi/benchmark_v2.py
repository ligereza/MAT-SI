"""Phase 1 protocol v2: normalized curves, identity attacks, and Pareto sets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from .canonical import apply_operation, get_path
from .corpus import load_corpus
from .identity import run_identity_analysis
from .kernels import AtomPairKernel, ContentDagKernel, RewriteEgraphKernel
from .kernels.base import Kernel
from .metrics import measure_call, sharing_ratio
from .scale import SIZES, scaled_cases, scale_manifest


PARETO_METRICS: dict[str, str] = {
    "description_bytes": "min",
    "transform_wall_time_ns": "min",
    "query_wall_time_ns": "min",
    "structural_sharing": "max",
    "reconstruction_fidelity": "max",
    "self_application": "max",
}


def _repeats(size: int) -> int:
    if size <= 100:
        return 3
    if size <= 1_000:
        return 2
    return 1


def _runtime_dict(runtime) -> dict[str, int]:
    return runtime.as_dict()


def _measure_case(kernel: Kernel, case: dict[str, Any], self_application: float) -> dict[str, Any]:
    value = case["value"]
    query_path = tuple(case["query_path"])
    operation = case["transform"]["operation"]
    source = get_path(value, case["transform"]["source_path"])
    repeats = _repeats(int(case.get("size", 1)))

    representation, encode_runtime = measure_call(lambda: kernel.encode(value), repeats)
    decoded, decode_runtime = measure_call(lambda: kernel.decode(representation), repeats)
    query_result, query_runtime = measure_call(lambda: kernel.query(representation, query_path), repeats)
    source_representation = kernel.encode(source)
    transformed, transform_runtime = measure_call(
        lambda: kernel.transform(source_representation, operation), repeats
    )

    storage = kernel.storage_breakdown(representation)
    unique, expanded = kernel.sharing(representation)
    expected = apply_operation(source, operation)
    transformed_value = kernel.decode(transformed.representation)
    return {
        "candidate": kernel.name,
        "case_id": case["id"],
        "shape": case.get("shape", "baseline"),
        "size": int(case.get("size", 0)),
        "repeats": repeats,
        "description_bytes": storage["total_bytes"],
        "stored_bytes": storage["store_bytes"],
        "storage_breakdown": storage,
        "reconstruction_fidelity": float(decoded == value),
        "structural_sharing": sharing_ratio(unique, expanded),
        "unique_nodes": unique,
        "expanded_nodes": expanded,
        "primitive_query_cost": query_result.cost,
        "query_nodes_visited": query_result.nodes_visited,
        "query_wall_time_ns": query_runtime.wall_time_ns,
        "query_cpu_time_ns": query_runtime.cpu_time_ns,
        "query_peak_memory_bytes": query_runtime.peak_memory_bytes,
        "query_allocation_blocks": query_runtime.allocation_blocks,
        "primitive_transform_cost": transformed.cost,
        "transform_nodes_visited": transformed.nodes_visited,
        "transform_wall_time_ns": transform_runtime.wall_time_ns,
        "transform_cpu_time_ns": transform_runtime.cpu_time_ns,
        "transform_peak_memory_bytes": transform_runtime.peak_memory_bytes,
        "transform_allocation_blocks": transform_runtime.allocation_blocks,
        "encode_wall_time_ns": encode_runtime.wall_time_ns,
        "encode_cpu_time_ns": encode_runtime.cpu_time_ns,
        "encode_peak_memory_bytes": encode_runtime.peak_memory_bytes,
        "encode_allocation_blocks": encode_runtime.allocation_blocks,
        "decode_wall_time_ns": decode_runtime.wall_time_ns,
        "decode_cpu_time_ns": decode_runtime.cpu_time_ns,
        "decode_peak_memory_bytes": decode_runtime.peak_memory_bytes,
        "decode_allocation_blocks": decode_runtime.allocation_blocks,
        "cross_domain_generality": float(decoded == value),
        "transformation_fidelity": float(transformed_value == expected),
        "self_application": self_application,
    }


def _dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    strictly_better = False
    for metric, direction in PARETO_METRICS.items():
        left_value = left[metric]
        right_value = right[metric]
        if direction == "min":
            if left_value > right_value:
                return False
            strictly_better |= left_value < right_value
        else:
            if left_value < right_value:
                return False
            strictly_better |= left_value > right_value
    return strictly_better


def pareto_frontier(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(rows)
    return [row for row in rows if not any(_dominates(other, row) for other in rows if other is not row)]


def _frontiers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["shape"], row["size"]), []).append(row)
    result = []
    for (shape, size), group in sorted(groups.items()):
        result.append(
            {
                "shape": shape,
                "size": size,
                "candidates": [row["candidate"] for row in pareto_frontier(group)],
            }
        )
    return result


def _global_strict_dominance(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    groups: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    candidates = sorted({row["candidate"] for row in rows})
    for row in rows:
        groups.setdefault((row["shape"], row["size"]), {})[row["candidate"]] = row
    result = []
    for left in candidates:
        for right in candidates:
            if left == right:
                continue
            all_no_worse = True
            strictly_better = False
            for group in groups.values():
                if left not in group or right not in group:
                    all_no_worse = False
                    break
                if _dominates(group[left], group[right]):
                    strictly_better = True
                else:
                    for metric, direction in PARETO_METRICS.items():
                        if direction == "min" and group[left][metric] > group[right][metric]:
                            all_no_worse = False
                        if direction == "max" and group[left][metric] < group[right][metric]:
                            all_no_worse = False
                if not all_no_worse:
                    break
            if all_no_worse and strictly_better:
                result.append({"dominant": left, "dominated": right})
    return result


def _self_application_rows(kernels: Iterable[Kernel]) -> list[dict[str, Any]]:
    rows = []
    for kernel in kernels:
        result, runtime = measure_call(kernel.self_application, repeats=3)
        rows.append(
            {
                "candidate": kernel.name,
                "model_round_trip": result.model_round_trip,
                "model_transform_ok": result.model_transform_ok,
                "query_ok": result.query_ok,
                "transform_ok": result.transform_ok,
                "self_application": float(result.model_round_trip and result.query_ok and result.transform_ok),
                "query_path": list(result.query_path),
                "queried_value": result.queried_value,
                "expected_query_value": result.expected_query_value,
                "transformed_rule_count": len(result.transformed_value),
                "runtime": _runtime_dict(runtime),
            }
        )
    return rows


def run_v2(
    corpus_path: str | Path = "corpus/phase1.json",
    sizes: Iterable[int] = SIZES,
) -> dict[str, Any]:
    kernels: list[Kernel] = [AtomPairKernel(), ContentDagKernel(), RewriteEgraphKernel()]
    self_rows = _self_application_rows(kernels)
    self_scores = {row["candidate"]: row["self_application"] for row in self_rows}

    scale_cases = scaled_cases(sizes)
    scale_rows = [
        _measure_case(kernel, case, self_scores[kernel.name])
        for case in scale_cases
        for kernel in kernels
    ]
    baseline_cases = load_corpus(corpus_path)
    baseline_rows = [
        _measure_case(kernel, case, self_scores[kernel.name])
        for case in baseline_cases
        for kernel in kernels
    ]
    frontier_rows = _frontiers(scale_rows)
    return {
        "protocol": "phase1-v2",
        "objective": "observe winner changes by scale and structure without selecting a kernel",
        "scale_manifest": scale_manifest(sizes),
        "measurement": {
            "runtime": "perf_counter_ns and process_time_ns",
            "memory": "tracemalloc peak bytes",
            "allocations": "positive tracemalloc block delta proxy",
            "nodes_visited": "common result field populated by each kernel query/transform",
            "pareto_dimensions": PARETO_METRICS,
            "repetitions": "3 for <=100, 2 for <=1000, 1 above 1000; median within a case",
        },
        "self_application": self_rows,
        "scale_measurements": scale_rows,
        "baseline_measurements": baseline_rows,
        "pareto_frontier_by_workload": frontier_rows,
        "strict_dominance_across_all_scale_points": _global_strict_dominance(scale_rows),
        "selection": None,
        "selection_reason": "Protocol v2 reports curves and Pareto frontiers; it does not choose weights or a winner.",
        "identity_analysis_file": "results/phase1-v2-identity.json",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MAT-SI Phase 1 protocol v2")
    parser.add_argument("--corpus", default="corpus/phase1.json")
    parser.add_argument("--json-out", type=Path, default=Path("results/phase1-v2-results.json"))
    parser.add_argument("--sizes", nargs="*", type=int, default=list(SIZES))
    args = parser.parse_args(argv)
    result = run_v2(args.corpus, args.sizes)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    identity = run_identity_analysis([AtomPairKernel(), ContentDagKernel(), RewriteEgraphKernel()])
    identity_path = Path(result["identity_analysis_file"])
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    identity_path.write_text(json.dumps(identity, indent=2, sort_keys=True), encoding="utf-8")
    for frontier in result["pareto_frontier_by_workload"]:
        print(f"{frontier['shape']} n={frontier['size']}: pareto={','.join(frontier['candidates'])}")
    print("strict dominance:", result["strict_dominance_across_all_scale_points"] or "none")
    print("selection: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
