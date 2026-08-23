# PiPi-42 — Future-Equivalence Discovery

This research unit is branched exactly from `c99cfd1`. The PiPi audit v0 result
`results/order-dimensions-lift-audit.json` is not rewritten. No PR is opened, `main`
is untouched, and Phase 5 is not started.

## Question

Can MAT-SI discover a small representation of histories that preserves relevant
future distinctions without paying essentially the full exhaustive-future oracle?

The method is transparent counterexample-driven partition refinement:

```text
all histories
    -> one candidate class
    -> adaptive discovery probe
    -> response signatures
    -> split distinguishable classes
    -> separate validation/counterexample probes
    -> freeze partition and parameters
    -> sealed holdout audit
    -> post-hoc ground-truth oracle
```

No clustering, neural model, quantum routine, tensor network, or opaque ML selector
is used. Each split records the probe, candidate classes before/after, histories by
response, and an assignment digest.

## Evidence boundaries

The implementation has four physically separate phases:

- `DISCOVERY`: adaptive probes are selected by the largest observed split gain.
- `VALIDATION`: a disjoint probe pool may produce counterexamples and refine the
  partition before freeze.
- `SEALED_HOLDOUT`: probes are evaluated only after the partition, stop rule,
  budgets, and parameters are frozen. They cannot alter any decision.
- `GROUND_TRUTH/ORACLE`: exhaustive future signatures are computed only after the
  sealed holdout. They audit the result and never choose probes, classes,
  thresholds, parameters, or stop states.

The old `sampled_future_queries` method from `c99cfd1` is retained as a side-by-side
baseline for the subset-sum families.

## Pre-registered prediction

Before executing the cases, the module records this prediction:

> Small future quotients should be discoverable with fewer queries than exhaustive
> future enumeration; near-maximal quotients should not yield useful compression;
> deceptive families should show early false merges that validation can reduce
> before sealed holdout. If these fail, degrade the hypothesis.

## Families

- A: three deterministic processes with 64 histories and 4 true future classes,
  using different seeds.
- B: three processes with the same 64 histories but 4, 16, and 56 true future
  classes.
- C: the prior dense/redundant and superincreasing subset-sum families. The
  suffix-sum quotient is post-hoc oracle only.
- D: 64 histories with 64 true classes. Correct behaviour is no useful compression
  and an explicit `STOP_NO_GAIN`.
- E: cheap probes are constant, a validation probe reveals an early split, and
  later sealed probes reveal further distinctions.

## Results — every case

| family/case | raw | discovered | oracle | discovery q | validation q | holdout false-merge pairs | oracle false-merge pairs | stop | outcome |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| A / automaton_small_11 | 64 | 4 | 4 | 384 | 192 | 0 | 0 | STOP_NO_GAIN | RECOVERED_QUOTIENT |
| A / automaton_small_17 | 64 | 4 | 4 | 384 | 192 | 0 | 0 | STOP_NO_GAIN | RECOVERED_QUOTIENT |
| A / automaton_small_23 | 64 | 4 | 4 | 384 | 128 | 0 | 0 | FREEZE | RECOVERED_QUOTIENT |
| B / quotient_4 | 64 | 4 | 4 | 384 | 192 | 0 | 0 | STOP_NO_GAIN | RECOVERED_QUOTIENT |
| B / quotient_16 | 64 | 15 | 16 | 384 | 192 | 16 | 16 | STOP_NO_GAIN | PARTIAL_OR_UNRESOLVED_RECOVERY |
| B / quotient_56 | 64 | 27 | 56 | 384 | 192 | 58 | 61 | STOP_NO_GAIN | PARTIAL_OR_UNRESOLVED_RECOVERY |
| C / dense_redundant | 256 | 2 | 2 | 12,288 | 512 | 0 | 0 | FREEZE | RECOVERED_QUOTIENT |
| C / superincreasing | 256 | 1 | 2 | 12,288 | 512 | 255 | 255 | FREEZE | PARTIAL_OR_UNRESOLVED_RECOVERY |
| D / almost_every_history_distinct | 64 | 29 | 64 | 384 | 192 | 48 | 59 | STOP_NO_GAIN | NO_USEFUL_COMPRESSION |
| E / cheap_probes_hide_later_difference | 64 | 4 | 64 | 256 | 64 | 480 | 480 | FREEZE | DECEPTIVE_FALSE_MERGE_REMAINS |

### Subset-sum baseline versus refinement

| case | baseline classes | baseline queries | baseline false-merge pairs | refinement classes | refinement queries | refinement false-merge pairs | oracle queries |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense_redundant | 1 | 4,096 | 3,840 | 2 | 12,288 | 0 | 65,536 |
| superincreasing | 1 | 4,096 | 255 | 1 | 12,288 | 255 | 65,536 |

The dense case is a genuine positive for the refinement procedure: it repairs the
baseline false merge, but uses three times the baseline query budget and still uses
less than the full oracle. The superincreasing case is a negative: the relevant
probe remains outside discovery/validation, so refinement does not repair the
baseline before sealed holdout. This is preserved as a failure, not relabelled as
absence of future structure.

The deceptive family also remains a failure under the sealed holdout. Validation
corrects the first cheap merge (one class becomes four), but later sealed queries
still expose 480 false-merge pairs. This is evidence that validation helps without
being sufficient in general.

The near-maximal control has 64 oracle classes for 64 histories and emits
`STOP_NO_GAIN`. It is not counted as successful compression even though the frozen
candidate has fewer observed classes; the post-hoc oracle shows that those classes
were false merges.

In seven cases the exhaustive oracle used fewer than twice the discovery-plus-
validation query count. That is an important negative pressure: a future quotient
can be a useful post-hoc description while its discovery is not dramatically cheaper
than auditing the whole future space.

## Metrics and provenance

The JSON reports, per case, raw history count, discovered and oracle class counts,
discovery/validation/holdout queries, refinement rounds, counterexamples, splits,
false merges/splits, sealed error, representation and assignment bytes, peak class
count, baseline raw cost, valid history merges, queries per valid merge, fallback,
stop state, and post-hoc oracle comparison.

`discovery_queries / valid_history_merges` is descriptive only. It is not Lift Gain
and is not combined with other resources. Heterogeneous resources remain a vector;
the module explicitly declares `scalar_collapsed: false` and `lift_gain_declared:
false`.

Field classes:

- `DETERMINISTIC`: generators, seeds, probe pools, parameters, response tables,
  partitions, class assignments, integer counts, digests, and post-hoc labels.
- `MEASURED_MACHINE_DEPENDENT`: `query_runtime` and `discovery_runtime`, including
  `wall_ms`-style timing. These are not expected to match byte-for-byte.
- `POST_HOC_ORACLE`: `ground_truth_class_count`, `oracle_query_count`, oracle
  construction cost, and `posthoc_oracle_comparison`.
- `UNKNOWN`: represented by JSON `null` when a requested dimension is not observed;
  no silent estimate is inserted.

Run locally:

```text
$env:PYTHONPATH="src"
python -m matsi.future_equivalence --json-out results/future-equivalence-discovery.json
python -m unittest discover -s tests -v
```

The next candidate experiment is PiPi-43 separator width, but it is not started by
this branch.
