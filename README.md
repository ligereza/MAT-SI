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
their own evaluator and rules. Protocol v4 attacks the Phase 1 gate with a minimum-core
trial, one alternative-rich e-graph workload, policy-based continuity, and a frozen
held-out corpus. It closes the Phase 1 gate without selecting a final kernel or creating
Phase 2 code.

## Run

The implementation uses only the Python standard library:

```text
python -m venv .venv
python -m unittest discover -s tests -v
python -m matsi.benchmark_v4 --json-out results/phase1-v4-results.json
```

The module path is configured by the test runner and benchmark launcher. To invoke the
package directly from a checkout, set `PYTHONPATH=src` first.

## Research boundary

The filesystem is only a bootstrap projection. Files, directories, programming
languages, names, and repositories are not assumed to be MAT-SI primitives.

See `docs/phase1-protocol.md` for the original protocol, `docs/phase1-protocol-v2.md`
for the scaling protocol, `docs/phase1-protocol-v3.md` for kernel decomposition, and
`docs/phase1-protocol-v4.md` and `docs/phase1-v4-results.md` for the gate attack and
current findings. Phase 2 self-reference results are in
`docs/phase2-self-reference.md`.

## Phase 2

Run the minimal self-reference/self-observation experiment without modifying the
frozen Phase 1 evaluator:

```text
python -m matsi.self_reference --json-out results/phase2-self-reference-results.json
```

## Phase 3

The controlled distillation gate runs without repository ingestion:

```text
python -m matsi.distillation --json-out results/phase3-distillation-results.json
```

See `docs/phase3-distillation.md` for discovery, residue, negative-control, held-out,
and cross-representation results.

## Phase 3B

The blind real-repository gate uses a frozen manifest and five exact public source
slices; it does not ingest full repositories:

```text
python -m matsi.real_distillation --json-out results/phase3b-real-distillation-results.json
```

See `docs/phase3b-real-distillation.md` for the manifest, adapter audit, false-positive
controls, and gate decision.

## Phase 3C

Phase 3C freezes the Phase 3B structural candidate and tests whether observable
behavior can falsify it. It uses two independent public `clamp` implementations, a
comparable negative control, provenance, and a small restricted oracle adapter:

```text
python -m matsi.semantic_falsification --json-out results/phase3c-semantic-falsification-results.json
```

See `docs/phase3c-semantic-falsification.md` for the held-out `UNKNOWN` results,
host/represented/derived audit, and the Phase 3 gate decision. Phase 4 has not begun.

## Phase 3D

Phase 3D derives generic behavioral hypotheses from observations before opening the
Phase 3C oracle:

```text
python -m matsi.evidence_discovery --json-out results/phase3d-evidence-discovery-results.json
```

See `docs/phase3d-evidence-discovery.md` for the frozen hypotheses, held-out
falsification, negative control, sealed-oracle validation, and the Phase 3D gate.
Phase 4 has not begun.

## Phase 4

Phase 4 tests transfer of a relation discovered from blind A+B trajectories to a
held-out C trajectory family using the minimal common experience envelope:

```text
python -m matsi.cross_domain --json-out results/phase4-cross-domain-results.json
```

See `docs/phase4-cross-domain.md` for the separate structural, behavioral, and
predictive transfer results. Product implementations have not begun.

## Phase 4B

Phase 4B tests real pre-existing records without authoring replacement events:

```text
python -m matsi.real_experience_transfer --json-out results/phase4b-real-experience-transfer-results.json
```

See `docs/phase4b-real-experience-transfer.md` for the frozen evidence manifest,
derivation audits, missing observables, held-out contamination boundary, and gate.

## Phase 4C

Phase 4C attacks the observability boundary using the frozen MAT-SI and VIBECODEINE
outputs. It identifies the smallest append-only record needed for future falsification
without inventing action, outcome, success, or scalar cost semantics:

```text
python -m matsi.minimum_observability --json-out results/phase4c-minimum-observability-results.json
```

See `docs/phase4c-minimum-observability.md` for the falsifying pairs, source mappings,
residue audits, instrumentation boundary, and gate decision. Phase 5 has not begun.

## CODEINE v0

CODEINE v0 is the first local product using the Phase 4C observation contract. It
captures auditable Git checkpoints and emits only `CONTINUE`, `SWITCH`, `STOP`, or
`UNKNOWN` from one explicit persistence hypothesis:

```text
$env:PYTHONPATH="src"
python -m codeine start --test-command "python -m unittest discover -s tests -v"
python -m codeine checkpoint
python -m codeine assess
python -m codeine finish
```

See `docs/codeine-v0.md` for the contract, detector, and real-session gate. No
dashboard, daemon, IDE integration, LLM integration, or additional product has been
started.
