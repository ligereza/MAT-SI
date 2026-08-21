# MAT-SI

MAT-SI is an experiment in discovering a sufficiently elementary representation for
objects that appear different but can be described, compared, and transformed by the
same rules.

This repository is currently in Phase 1: competing kernel representations. It is not a
product, an agent framework, a programming language, or a final architecture.

## Phase 1

The experiment compares three independent candidates on the same corpus:

- `atom_pair`: atoms and binary pairs only.
- `content_dag`: content-addressed nodes with structural sharing.
- `rewrite_egraph`: e-graph representation with a small rewrite engine.

The candidates are required to represent the same objects, including a usable model of
their own evaluator and rules. Protocol v3 experimentally decomposes structural
substrates, evaluators, and continuity evidence; tests represented rules that control
execution; represents transformations and histories as ordinary data; and audits
semantic leakage into Python. It does not select a final kernel or open Phase 2.

## Run

The implementation uses only the Python standard library:

```text
python -m venv .venv
python -m unittest discover -s tests -v
python -m matsi.benchmark_v3 --json-out results/phase1-v3-results.json
```

The module path is configured by the test runner and benchmark launcher. To invoke the
package directly from a checkout, set `PYTHONPATH=src` first.

## Research boundary

The filesystem is only a bootstrap projection. Files, directories, programming
languages, names, and repositories are not assumed to be MAT-SI primitives.

See `docs/phase1-protocol.md` for the original protocol, `docs/phase1-protocol-v2.md`
for the scaling protocol, `docs/phase1-protocol-v3.md` for kernel decomposition, and
`docs/phase1-v3-results.md` for the current findings.
