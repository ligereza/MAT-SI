# Phase 1 Experimental Protocol

## Objective

Estimate whether a common representation can support the same objects and operations
without introducing a special ontology for each domain.

We write the open problem as:

```text
U = candidate representation
T: U -> U = candidate transformation mechanism
C(U) = measured total cost
```

The experiment does not assume the shape of `U`, `T`, or `C`. Each candidate defines its
own representation, while the harness defines only the observable contract:

```text
encode(value) -> representation
decode(representation) -> value
query(representation, path) -> value + cost
transform(representation, operation) -> representation + cost
self_description() -> value
```

## Rival candidates

### A: atom + pair

The only structural constructor is a binary pair. Lists and maps are encoded as tagged
pair chains. There is no interning or external identity store.

### B: content-addressed DAG

Nodes are immutable. A node is identified by a SHA-256 digest of canonical node bytes.
Repeated substructures therefore share a content identifier in the store.

### C: rewrite e-graph

Terms are inserted into an e-graph. Hash-consing provides structural reuse, e-classes
represent equivalence, and a small rewrite set tests equality saturation. Extraction is
the observable reconstruction operation.

The candidates are intentionally not fused in Phase 1. A hybrid is allowed only after a
candidate-specific failure is preserved and measured.

## Common corpus

Every candidate receives the same nine case values from `corpus/phase1.json`:

1. a small algorithm;
2. a stateful program;
3. repeated structure;
4. a temporal sequence;
5. a reversible transformation;
6. a lossy transformation with explicit residue;
7. a text object;
8. a daily problem expressed as states and actions;
9. a request for the candidate to describe itself.

The ninth case is candidate-specific only at response time. Its request schema is shared;
the candidate must return a description containing primitives, identity, transformations,
costs, history, and a self-reference.

## Metrics

The benchmark reports the following computable proxies:

- `D` (`description_size`): canonical UTF-8 bytes for the candidate representation,
  including the candidate's local dictionary/store where applicable.
- `R` (`reconstruction_fidelity`): exact equality after decode, scored as 0 or 1.
- `S` (`structural_sharing`): `1 - unique_nodes / expanded_nodes`, clipped at zero.
- `T` (`transformation_cost`): candidate-reported primitive work for the common
  transformation operation.
- `Q` (`query_cost`): candidate-reported traversal work for the common path query.
- `X` (`cross_domain_generality`): exact reconstruction coverage over corpus cases.
- `M` (`self_modeling`): exact self-description reconstruction for the mandatory ninth
  case. Aggregate `M` is the value of that case, not an average over unrelated cases.

`D` is deliberately not a claim about universal shortest description. It is a measured
proxy that includes representation plus candidate-specific storage or rule overhead.
Kolmogorov complexity remains a theoretical lower bound, not a computable score here.

## TILDE and loss

The lossy case keeps `source`, `result`, and `residue` in the same value. A candidate may
not silently discard the residue. The harness checks the declared lossy result and keeps
the residue queryable as ordinary data.

## Time

The corpus contains an ordered timeline. The protocol treats a temporal system as a
sequence of roots or representations, not as a Git-specific primitive. A later phase
will compare root logs, shared snapshots, and rewrite histories directly.

## Decision gate

Phase 1 does not select a winner from one scalar score. A candidate can advance only when
its aggregate metrics and preserved counterexamples support a decision of the form:

```text
K* = arg min_K C(K)
```

where the cost function and weights are published with the result. If no candidate wins
across the required dimensions, the result is a documented non-selection.
