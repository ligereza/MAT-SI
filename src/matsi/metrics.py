"""Explicit, computable Phase 1 metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import statistics
import time
import tracemalloc
from typing import Any


@dataclass(frozen=True)
class Measurement:
    candidate: str
    case_id: str
    description_size: int
    reconstruction_fidelity: float
    structural_sharing: float
    transformation_cost: int
    query_cost: int
    cross_domain_generality: float
    self_modeling: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def sharing_ratio(unique_nodes: int, expanded_nodes: int) -> float:
    if expanded_nodes <= 0:
        return 0.0
    return max(0.0, 1.0 - unique_nodes / expanded_nodes)


@dataclass(frozen=True)
class RuntimeMeasurement:
    """Runtime observations shared by all candidates.

    Allocation blocks are a tracemalloc proxy, not a VM-level allocation count.
    Keeping the proxy explicit prevents it from being mistaken for a universal
    primitive cost.
    """

    wall_time_ns: int
    cpu_time_ns: int
    peak_memory_bytes: int
    allocation_blocks: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _median(values: list[int]) -> int:
    return int(statistics.median(values)) if values else 0


def measure_call(callable_, repeats: int = 1) -> tuple[Any, RuntimeMeasurement]:
    """Measure a pure operation with common wall/CPU/memory proxies.

    One warm-up call is deliberately excluded. Every measured repeat starts a new
    tracemalloc session, so the candidates see the same measurement boundary.
    """

    result = callable_()
    samples: list[RuntimeMeasurement] = []
    for _ in range(max(1, repeats)):
        tracemalloc.start()
        before = tracemalloc.take_snapshot()
        wall_start = time.perf_counter_ns()
        cpu_start = time.process_time_ns()
        result = callable_()
        cpu_time_ns = time.process_time_ns() - cpu_start
        wall_time_ns = time.perf_counter_ns() - wall_start
        _, peak_memory_bytes = tracemalloc.get_traced_memory()
        after = tracemalloc.take_snapshot()
        allocation_blocks = sum(
            max(stat.count, 0)
            for stat in after.compare_to(before, "lineno")
            if stat.count > 0
        )
        tracemalloc.stop()
        samples.append(
            RuntimeMeasurement(
                wall_time_ns=wall_time_ns,
                cpu_time_ns=cpu_time_ns,
                peak_memory_bytes=peak_memory_bytes,
                allocation_blocks=allocation_blocks,
            )
        )
    return result, RuntimeMeasurement(
        wall_time_ns=_median([sample.wall_time_ns for sample in samples]),
        cpu_time_ns=_median([sample.cpu_time_ns for sample in samples]),
        peak_memory_bytes=_median([sample.peak_memory_bytes for sample in samples]),
        allocation_blocks=_median([sample.allocation_blocks for sample in samples]),
    )
