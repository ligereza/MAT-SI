# Phase 1 Results: protocol v1

The first run used the nine-case corpus and the three independent candidates. The raw
machine-readable result is `results/phase1-results.json`.

## Aggregate measurements

Lower is better for `D`, `T`, and `Q`. Higher is better for `R`, `S`, `X`, and `M`.
Sizes are canonical UTF-8 bytes; costs are candidate-defined primitive counts.

| Candidate | D | R | S | T | Q | X | M |
|---|---:|---:|---:|---:|---:|---:|---:|
| atom_pair | 538.2 | 1.000 | 0.000 | 82.0 | 9.6 | 1.000 | 1.000 |
| content_dag | 1384.1 | 1.000 | 0.493 | 13.3 | 9.6 | 1.000 | 1.000 |
| rewrite_egraph | 1169.7 | 1.000 | 0.062 | 15.1 | 3.4 | 1.000 | 1.000 |

## Observations

- `atom_pair` has the smallest measured description under this serialization, but has no
  structural sharing and the highest transformation cost.
- `content_dag` has the strongest sharing result and the lowest transformation cost. Its
  description is expensive because every immutable node carries a content identifier.
- `rewrite_egraph` has the lowest query cost and preserves rewrite alternatives, but its
  current extraction and e-class representation do not share every repeated structure.
- All candidates reconstructed all nine cases exactly, including their self-description.
- The lossy case retained its residue as ordinary data; no candidate was allowed to hide
  it as discarded metadata.

## Counterexamples retained

1. The repeated-structure case separates content identity from plain tree encoding.
2. The lossy case separates result from recoverability and requires explicit residue.
3. The temporal sequence is represented as ordered values rather than a Git primitive.
4. The self-model request shows that exact round-tripping alone is not enough; the
   candidate must expose its own primitives, identity, transformations, costs, and
   history.
5. The current identity experiment is deliberately unresolved: when a human-readable
   `name` is placed inside the represented value, all three candidates treat it as data
   and therefore change the root representation when the name changes. Separating
   semantic content from renameable naming metadata is not yet expressible without
   adding a new primitive. This is preserved as a Phase 2 counterexample.

## Decision

No candidate wins all required dimensions. `K*` is intentionally unset. The gate for
Phase 2 is not passed.

The next experiment should improve fairness before combining ideas: measure dictionary
and hash overhead separately, add longer repeated graphs, add branching histories, and
test rewrite rules that are not hard-coded to one operation. The current result supports
investigating the content-addressed DAG and e-graph candidates further, while preserving
the atom/pair candidate as a compact baseline.
