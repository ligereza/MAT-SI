# PiPi-45: autonomous representation discovery

PiPi-45 is branched from PiPi-44 commit `4325a71` on
`research/meta-lift`. It does not modify PiPi-42, PiPi-43, PiPi-44, CODEINE,
their JSON, or `main`.

## Blind contract

The selector receives only raw variables, relation tables, optional numeric
targets, and optional future probes. Case names and expected methods are kept
outside the input and appear only in the post-hoc adversarial audit. Candidate
probes inspect generic relation shapes and numeric structure. They do not read
labels such as `affine`, `easy`, `subset_sum_dense`, or `hard`.

The library is explicit and small: `RAW_SEARCH`, `GF2_LIFT`, `HORN`,
`DUAL_HORN`, `2SAT`, `VARIABLE_ELIMINATION`,
`FUTURE_EQUIVALENCE_REFINEMENT`, `SUBSET_SUM_DP`, `MITM`,
`CARDINALITY_LIFT`, and `CLUSTER/LATTICE`. Each exposes an applicability probe,
discovery cost, transform cost, representation, solver, resource vector,
certificate, and raw fallback.

## Budget and selection

The selector spends a fixed discovery budget on candidate probes. Its explicit
experimental policy is to choose the probed applicable candidate with the
smallest predicted discovery+transform+solve operations, while retaining the
full vector. It freezes before post-hoc methods run. If knowledge acquisition
reaches the fallback estimate or the budget blocks candidates, that decision is
recorded; it is not silently repaired.

Post-hoc, all applicable candidates are run as an oracle reference. The report
keeps exact counts, per-method vectors, Pareto frontier, dominance, and a
clearly labelled post-hoc scalar policy. There is no universal regret scalar.

## Surface and adversarial controls

Each raw input receives variable renaming/scope reversal and constraint
reordering/redundancy/metadata variants. The selected method and exact count
are compared across surfaces. Adversarial cases include perturbed affine
relations, a low-width graph whose generic relation shape can induce a false
lift, and a tight-budget subset target that forces a missed lift and raw
fallback. `false_lift`, `missed_lift`, `wasted_discovery_ops`, and
`fallback_rescue` are retained even when they are zero.

The result is deliberately limited: it shows that a small generic candidate
library can select several representations in these toy domains and remain
surface-robust on these variants, but it also records a false lift, missed
lifts under budget, dominated choices, and discovery overhead. This is not an
algorithm of algorithms in the strong sense.

## Reproduction and field classes

```text
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
python -m matsi.meta_lift --json-out results/meta-lift.json
```

Raw inputs, probes, exact counts, decisions, integer resource counts, and
certificates are deterministic. `wall_ms` is machine-dependent. The
`posthoc_oracle`, expected candidate labels, regret, and Pareto frontier are
post-hoc reference fields. No result is promoted to a stable MAT-SI kernel
primitive.
