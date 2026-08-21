# Phase 1 Protocol v2

## Scope

Protocol v2 remains inside Phase 1. The three candidates stay independent:

- `atom_pair`: the baseline with atoms and binary pairs, without sharing;
- `content_dag`: immutable content-addressed nodes;
- `rewrite_egraph`: hash-consed e-classes with generic first-order rewrite schemas.

No hybrid kernel, product surface, DSL, or identity primitive is introduced.

The purpose of v2 is to observe where costs and Pareto membership change with size and
structure. It is not a kernel selection protocol.

## Workloads

The original nine-case corpus remains a baseline. The scaling matrix is generated
deterministically for sizes `10`, `100`, `1000`, and `10000`:

1. `repetition`: one exact payload repeated in an item sequence;
2. `shared_graph`: `n` graph records with repeated payloads and cyclic-looking edge
   references encoded as ordinary data;
3. `temporal_branching`: `n` snapshots with parent links, branch labels, repeated state
   shapes, and evolving actions.

The host generator materializes the same JSON value for every candidate. Repetition in
the host object is not treated as an identity signal; sharing must emerge from the
candidate representation.

## Common measurements

Every candidate is measured at the same operation boundaries:

- encode the value;
- decode the representation;
- query the prescribed path;
- transform an encoded source value;
- run self-application.

The harness records:

- description bytes and stored bytes;
- wall time from `perf_counter_ns`;
- CPU time from `process_time_ns`;
- peak traced memory from `tracemalloc`;
- positive traced allocation-block delta as an allocation proxy;
- nodes visited reported through the common query/transform result fields.

Small CPU samples can be zero on Windows because the process CPU clock is quantized;
wall time, memory, and allocation fields remain available. CPU values are retained as
observations and are never silently substituted with wall time.

Repeated samples use three measurements for `n <= 100`, two for `n <= 1000`, and one
for larger points. The reported sample is the median only within that single workload
point; no cross-size or cross-shape average is used to decide the frontier.

## Storage overhead decomposition

`content_dag` reports:

- `payload_bytes`: canonical node data;
- `store_bytes`: payload plus an 8-byte block-framing proxy;
- `hashes_bytes`: 32-byte digest per stored node plus one root reference;
- `index_bytes`: canonical CID-to-kind index proxy;
- `root_reference_bytes` and `total_bytes`.

`payload_bytes` is diagnostic and is already included in `store_bytes`; it is not added
twice to `total_bytes`.

`rewrite_egraph` reports:

- `original_term_bytes`;
- `eclasses_bytes`;
- `rules_bytes`;
- `total_bytes` as their sum.

The baseline reports its complete pair term as `payload_bytes` and has no external
hash/index/store component.

## Identity attack

The harness includes four counterexamples:

- same content, different name;
- same name, different content;
- two aliases for one object;
- an object whose content evolves while an external identity remains stable.

The analysis encodes content and annotations as separate ordinary fields and compares
their round-trip projections. This is an experiment about representation layout, not a
new primitive or a semantic identity rule. The result therefore distinguishes what can
be separated structurally from what a kernel actually understands.

## MATSI(MATSI)

`self_description()` now contains the candidate's evaluator and actual rule table as
ordinary data. `self_application()` then:

1. encodes that model with the candidate;
2. queries the encoded first rule name;
3. transforms that complete model through the common `identity` path and checks its
   decoded value;
4. encodes the model's rule list and reverses it through the same transform path used
   by external objects;
5. checks all decoded results exactly.

This is stronger than returning a descriptive dictionary without using its own
representation.

## Generic rewrite schemas

The e-graph uses variable-based schemas, not corpus-specific tree cases:

- `identity(x) -> x`;
- `reverse(reverse(x)) -> x`;
- `wrap(wrap(x)) -> wrap(x)`.

The matcher, substitution, and saturation loop operate on arbitrary operation names.
The third rule is retained specifically to exercise a non-corpus operation.

## Pareto rule

For each `(shape, size)` point, a candidate is dominated only if another candidate is
no worse in every dimension and strictly better in at least one. The frontier uses:

- description bytes: minimize;
- transform wall time: minimize;
- query wall time: minimize;
- structural sharing: maximize;
- reconstruction fidelity: maximize;
- self-application: maximize.

No weights or scalar score are used. A second dominance audit asks whether one candidate
dominates another at every scale point of every shape.

## Reproduction

From the repository root:

```text
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -v
python -m matsi.benchmark_v2 --json-out results/phase1-v2-results.json
```

Raw measurements are in `results/phase1-v2-results.json`; identity observations are in
`results/phase1-v2-identity.json`.
