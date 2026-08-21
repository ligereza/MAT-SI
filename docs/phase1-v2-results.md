# Phase 1 Protocol v2 Results

## Decision

No kernel is selected. The complete scaling matrix has no candidate that strictly
dominates another candidate at every shape and size point.

The result is not a weighted winner:

- `content_dag` is the query and sharing leader throughout the scale matrix;
- `atom_pair` has the lowest transform time at small and medium points; at n = 10000,
  `content_dag` overtakes it for repetition and is marginally faster for the graph,
  while `atom_pair` remains faster for temporal branching;
- `content_dag` is the smallest representation for repetition;
- `rewrite_egraph` is locally dominated by `content_dag` on every repetition point;
- `rewrite_egraph` remains on the Pareto frontier for every graph and temporal point
  because its description can be smaller than `content_dag` while its query and
  transform costs are much higher.

There is an observed scale-driven switch in repetition: `atom_pair` leaves the frontier
at n = 10000 when the larger repeated structure makes its decode/re-encode transform
more expensive than the DAG path. There is also a structural switch: the e-graph leaves
the frontier for repeated data but re-enters it for graph and temporal branching data.

## Pareto frontiers

The frontier dimensions are description bytes, transform wall time, query wall time,
sharing, reconstruction fidelity, and self-application. Lower is better for the first
three and higher is better for the last three.

| Shape | n = 10 | n = 100 | n = 1000 | n = 10000 |
|---|---|---|---|---|
| repetition | `atom_pair`, `content_dag` | `atom_pair`, `content_dag` | `atom_pair`, `content_dag` | `content_dag` |
| shared_graph | all three | all three | all three | all three |
| temporal_branching | all three | all three | all three | all three |

At every repetition point, `rewrite_egraph` is strictly dominated by `content_dag` in
the Pareto dimensions. No candidate is strictly dominated across all 12 scale points.

## Curves at n = 10000

Times below are wall-time medians for the one large-sample run, shown in milliseconds
or seconds for readability. The raw nanosecond values, CPU time, memory, allocation
blocks, and node counts are preserved in the JSON result.

| Shape | Candidate | D bytes | Sharing | Query wall | Transform wall |
|---|---|---:|---:|---:|---:|
| repetition | `atom_pair` | 3,630,481 | 0.00 | 14.74 ms | 4.51 s |
| repetition | `content_dag` | 672,988 | 1.00 | 0.028 ms | 3.65 s |
| repetition | `rewrite_egraph` | 3,852,783 | 1.00 | 2.25 s | 11.86 s |
| shared_graph | `atom_pair` | 7,107,166 | 0.00 | 12.25 ms | 8.82 s |
| shared_graph | `content_dag` | 15,322,553 | 0.84 | 0.035 ms | 8.58 s |
| shared_graph | `rewrite_egraph` | 13,622,241 | 0.75 | 7.92 s | 29.00 s |
| temporal_branching | `atom_pair` | 5,116,828 | 0.00 | 10.55 ms | 3.88 s |
| temporal_branching | `content_dag` | 10,013,669 | 0.87 | 0.028 ms | 4.35 s |
| temporal_branching | `rewrite_egraph` | 9,992,167 | 0.75 | 4.28 s | 18.42 s |

The query curve is the clearest operational separation: the DAG follows links directly,
while the e-graph extracts a representative before traversing the path. The baseline
keeps the lowest transform time here because its transformation is a direct decode,
host operation, and re-encode path without hashing or e-class maintenance.

## Content-DAG overhead and amortization

For `content_dag`, overhead is `hashes + index + root reference + store framing`; the
payload is already included in `store_bytes`.

| Shape | n | Total D | Hashes | Index | Overhead share |
|---|---:|---:|---:|---:|---:|
| repetition | 10 | 3,658 | 448 | 986 | 51.0% |
| repetition | 10000 | 672,988 | 448 | 986 | 0.3% |
| shared_graph | 10 | 18,953 | 2,176 | 5,060 | 49.1% |
| shared_graph | 10000 | 15,322,553 | 1,600,576 | 3,771,290 | 45.0% |
| temporal_branching | 10 | 15,839 | 1,792 | 4,161 | 48.4% |
| temporal_branching | 10000 | 10,013,669 | 960,832 | 2,271,891 | 41.5% |

The hash/index penalty amortizes when the workload reuses a small dictionary of exact
substructures. It does not amortize in the same way when the graph has approximately
`n` distinct records and the index itself grows with the number of unique nodes. This
explains why `content_dag` wins description size for repetition but not for the other
two shapes.

## E-graph decomposition

At n = 10000, the e-graph totals are decomposed as follows:

| Shape | Original terms | E-classes | Rules | Total D |
|---|---:|---:|---:|---:|
| repetition | 3,820,531 | 31,986 | 266 | 3,852,783 |
| shared_graph | 7,737,214 | 5,884,761 | 266 | 13,622,241 |
| temporal_branching | 5,746,848 | 4,245,053 | 266 | 9,992,167 |

The rule dictionary is constant in this run. The large e-graph costs are therefore
coming from the original term and e-class materialization, not from the generic rule
table itself.

## Identity counterexamples

All three candidates reproduce the intended negative cases exactly:

| Counterexample | Observed result |
|---|---|
| same content, different name | full values differ; content projections match; annotation projections differ |
| same name, different content | full values differ; content projections differ; annotation projections match |
| two names for one object | one content value can be encoded with two external aliases, but alias semantics are not inferred |
| evolving object | each version has a distinct content projection; stable object identity survives only as separate data |

This preserves the unresolved question rather than hiding it: structural identity and
annotations can be placed in separate fields, but no candidate currently knows that one
field is authoritative identity, another is an alias, or that a version chain preserves
identity. No new primitive was added to force that interpretation.

## Real self-application

Every candidate passed all three checks:

1. its evaluator/rule model round-trips through its own representation;
2. the complete encoded model passes the common `identity` transform;
3. the encoded model can be queried at `rules[0].name`;
4. its encoded rule list can be reversed through the same public transform mechanism.

The result is `self_application = 1.0` for all candidates. The measured wall-time and
allocation proxies are diagnostic only; self-application is not reduced to a score that
can outweigh fidelity or scaling behavior.

## Reproduction and artifacts

Run:

```text
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -v
python -m matsi.benchmark_v2 --json-out results/phase1-v2-results.json
```

Artifacts:

- `results/phase1-v2-results.json`: raw curves, normalized runtime fields, storage
  breakdowns, frontiers, and strict-dominance audit;
- `results/phase1-v2-identity.json`: raw identity cases and per-kernel observations;
- `corpus/phase1-v2-scale.json`: deterministic scale manifest.

The next experiment should target identity/annotation semantics and reduce measurement
overhead sensitivity before any kernel fusion or Phase 2 design is considered.
