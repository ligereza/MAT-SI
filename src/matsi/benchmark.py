"""Run the common corpus against all Phase 1 candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

from .canonical import apply_operation, canonical_text, get_path
from .corpus import load_corpus
from .kernels import AtomPairKernel, ContentDagKernel, RewriteEgraphKernel
from .metrics import Measurement, sharing_ratio


def run(corpus_path: str | Path = "corpus/phase1.json") -> dict[str, Any]:
    corpus = load_corpus(corpus_path)
    kernels = [AtomPairKernel(), ContentDagKernel(), RewriteEgraphKernel()]
    measurements: list[Measurement] = []

    for kernel in kernels:
        for case in corpus:
            case_id = case["id"]
            if case_id == "self_model_request":
                value = kernel.self_description()
                query_path = ("primitives", 0)
                operation = "identity"
                source = value.get("primitives", [])
                expected = source
                self_modeling = 1.0
            else:
                value = case["value"]
                query_path = tuple(case["query_path"])
                transform = case["transform"]
                operation = transform["operation"]
                source = get_path(value, transform["source_path"])
                expected = apply_operation(source, operation)
                self_modeling = 0.0

            representation = kernel.encode(value)
            decoded = kernel.decode(representation)
            reconstruction = 1.0 if decoded == value else 0.0
            unique, expanded = kernel.sharing(representation)
            query = kernel.query(representation, query_path)
            if case_id == "self_model_request":
                transformed = kernel.transform(representation, operation)
                transformation_ok = kernel.decode(transformed.representation) == value
            else:
                transformed = kernel.transform(kernel.encode(source), operation)
                transformation_ok = kernel.decode(transformed.representation) == expected
            if not transformation_ok:
                raise AssertionError(f"{kernel.name} failed transformation for {case_id}")

            measurements.append(
                Measurement(
                    candidate=kernel.name,
                    case_id=case_id,
                    description_size=kernel.size_bytes(representation),
                    reconstruction_fidelity=reconstruction,
                    structural_sharing=sharing_ratio(unique, expanded),
                    transformation_cost=transformed.cost,
                    query_cost=query.cost,
                    cross_domain_generality=reconstruction,
                    self_modeling=self_modeling * reconstruction,
                )
            )

    aggregate: dict[str, dict[str, float]] = {}
    metric_names = (
        "description_size",
        "reconstruction_fidelity",
        "structural_sharing",
        "transformation_cost",
        "query_cost",
        "cross_domain_generality",
        "self_modeling",
    )
    for kernel_name in {measurement.candidate for measurement in measurements}:
        rows = [row for row in measurements if row.candidate == kernel_name]
        aggregate[kernel_name] = {
            metric: mean(getattr(row, metric) for row in rows)
            for metric in metric_names
            if metric != "self_modeling"
        }
        aggregate[kernel_name]["self_modeling"] = max(row.self_modeling for row in rows)

    return {
        "protocol": "phase1-v1",
        "corpus_cases": len(corpus),
        "measurements": [measurement.as_dict() for measurement in measurements],
        "aggregate": aggregate,
        "selection": None,
        "selection_reason": "No candidate is selected before comparison and counterexample review.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark competing MAT-SI kernels")
    parser.add_argument("--corpus", default="corpus/phase1.json")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    result = run(args.corpus)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    for candidate, metrics in result["aggregate"].items():
        print(
            f"{candidate}: D={metrics['description_size']:.1f} "
            f"R={metrics['reconstruction_fidelity']:.3f} "
            f"S={metrics['structural_sharing']:.3f} "
            f"T={metrics['transformation_cost']:.1f} "
            f"Q={metrics['query_cost']:.1f} "
            f"X={metrics['cross_domain_generality']:.3f} "
            f"M={metrics['self_modeling']:.3f}"
        )
    print("selection: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
