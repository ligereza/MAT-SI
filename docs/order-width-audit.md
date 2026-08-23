# PiPi-43: separator and elimination-order width audit

This audit is frozen on branch `research/order-width`, whose parent is exactly
`f17d1ff` (PiPi-42). PiPi-42 files and
`results/future-equivalence-discovery.json` are not modified here. The scope is
only exact counting of independent sets in binary graphs.

## Question and boundary

Each vertex has a binary variable `x_v`. Every edge `(u,v)` imposes
`x_u*x_v=0`; the query is the exact number of valid assignments. The module
implements two transparent methods:

* brute force checks every assignment for small graphs;
* variable elimination starts with one Boolean constraint factor per edge and
  multiplies/sums factors when a variable is eliminated.

No external solver, quantum claim, tensor/MPS claim, universal dimension, or
scalar Lift Gain is used. Brute-force assignment checks, order-construction
operations, factor-table cells, factor operations, and wall time are separate
resource vectors. In particular, assignment count is not treated as the same
unit as factor cells.

The factor convention is preregistered: width is the number of active
neighbours immediately before eliminating a variable; the resulting separator
factor has `2**width` states. `peak_factor_scope` is the post-elimination
separator scope, so it equals the peak width under this convention.

## Discovery, post-hoc reference, and stop rule

Discovery orders are `NATURAL`, one frozen-seed `RANDOM`, `MIN_DEGREE`, and
`MIN_FILL`. The star has two additional preregistered controls: center-first
and leaves-first, both on the exact same raw graph. None of these methods sees
the exact-width oracle or a known-good order.

After all discovery decisions are frozen, small cases may receive a
`GROUND_TRUTH/ORACLE` exact-width reference. Larger cases use an explicitly
labelled post-hoc family reference when one exists. The reference reports
`best_known_width` and `width_gap`; it cannot change `FREEZE` or `STOP_NO_GAIN`.

The factor-state fallback budget is 4096 states. An order is `FREEZE` only when
its selected order can run exact VE within the budget. If the next factor would
exceed the budget, the result is `STOP_NO_GAIN` before materialisation. Small
graphs retain a brute-force exact reference; larger graphs retain factorisation
metrics or stop at the factor-state budget. Order construction has its own
operation budget and is recorded separately.

## Separator sufficiency

For `path_8`, a fixed elimination prefix is divided into `PAST` and `FUTURE`.
The separator is the set of future vertices adjacent to the past. All past
assignments are enumerated. Their induced boundary factor/state is compared
with their exhaustive future contribution vector. The report includes raw past
assignment count, separator state count, collapsed histories, and the exact
pass/fail result. This establishes sufficiency for the checked instance only;
separator minimality is not claimed.

## Cases and preregistered predictions

The JSON contains every case, not only positive examples:

* trees and paths;
* cycles, ladders, and 2xk through 5xk grids;
* the same star instance with good and bad orders;
* clique, dense-random, and complete-bipartite high-width controls;
* same-`n` structures with different edge counts and costs;
* a seeded deceptive sparse graph whose construction was fixed before
  results were generated.

Predictions P1--P7 are stored in the JSON before the case results. The report
preserves gaps, high-width stops, same-width cost differences, and any
counterexample to a simple width-only story. A scientific reading is therefore
conditional: width may predict factor memory after a good order is available,
while order discovery can cost something and width need not determine solve
work by itself.

## Reproduction and field classification

From a clean checkout, run:

```text
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

To regenerate the audit JSON:

```text
python -m matsi.order_width --json-out results/order-width-audit.json
```

The following are deterministic for the same Python implementation and frozen
inputs: raw graph edges, input digests, frozen random order, exact counts,
elimination order, induced width, fill edges, factor cells, factor operations,
stop decisions, separator states, and post-hoc reference values. The JSON
records `runtime_ms`/`wall_ms`, `order_discovery_runtime_ms`/
`order_discovery_wall_ms`, and `solve_runtime_ms`/`solve_wall_ms` as
machine-dependent descriptive measurements; they are not expected to match
byte-for-byte across machines or runs. The regenerated JSON may consequently
vary only in those timing fields (and formatting/runtime-dependent summaries
that contain them).

The fields under `posthoc_reference`, `best_known_width`, and `width_gap` are
reference/audit fields, not discovery evidence. Values that cannot be safely
estimated are represented as `null` rather than inferred from wall time.

No PR is opened and no Phase 5 work is started by this audit.
