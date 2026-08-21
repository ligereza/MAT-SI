"""Deterministic synthetic worlds with exhaustive oracles.

Every world is small enough that ground truth can be computed by enumeration, so
an operator's decision can be compared with the exact answer rather than with a
plausible-looking one.  No world reads external data, the network, or an LLM.

Each world ships with an *anti-world*: an instance of the same family where the
operator's intuitive strategy provably fails.  The anti-worlds are research
outputs, not test fixtures.
"""

from .hypothesis_world import (
    Experiment,
    HypothesisWorld,
    conditionally_independent_world,
    decoy_parity_world,
    nuisance_surprise_world,
    rare_but_uninformative_world,
)
from .trajectory_world import (
    TrajectoryWorld,
    cycling_world,
    deceptive_prefix_world,
    delayed_payoff_world,
    diminishing_world,
    productive_repetition_world,
)
from .expression_world import (
    RepresentationTask,
    linear_read_task,
    parallel_depth_task,
    shift_only_task,
)
from .branch_world import (
    Branch,
    BranchWorld,
    bounded_world,
    contradictory_evidence_world,
    novelty_trap_world,
    trap_world,
)

__all__ = [
    "Branch",
    "BranchWorld",
    "Experiment",
    "HypothesisWorld",
    "RepresentationTask",
    "TrajectoryWorld",
    "bounded_world",
    "conditionally_independent_world",
    "contradictory_evidence_world",
    "cycling_world",
    "deceptive_prefix_world",
    "decoy_parity_world",
    "delayed_payoff_world",
    "diminishing_world",
    "linear_read_task",
    "novelty_trap_world",
    "nuisance_surprise_world",
    "parallel_depth_task",
    "productive_repetition_world",
    "rare_but_uninformative_world",
    "shift_only_task",
    "trap_world",
]
