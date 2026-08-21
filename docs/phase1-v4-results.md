# Phase 1 Protocol v4 Results

## Decision

**B — ONE COUNTEREXAMPLE REMAINS.**

The unresolved counterexample is not storage, identity, or representation fidelity.
It is executable semantics at the frozen boundary: a represented rule can be carried
through U but cannot run if it requests an operation not in the six-op VM vocabulary.

Concrete held-out failures are `sub` in symbolic subtraction and `rotate` in the
unfamiliar process. They are preserved; no new primitive is added.

## Gate questions

### 1. Minimum trusted semantic core

The smallest demonstrated core is:

```text
ordinary value
atom equality
generic pattern matching
binding/substitution
generic rewrite
represented rule/program
fixed evaluator boundary for open arithmetic
```

The generic rewrite trial controls three behaviors with zero behavior-specific Python
branches. It does not make open-ended arithmetic represented. The six-op VM remains the
current practical boundary until that specific counterexample is attacked.

### 2. Represented versus host-defined

| Concern | Status |
|---|---|
| values, patterns, bindings, rules | `REPRESENTED` |
| transformations, compositions, history | `REPRESENTED` |
| cost observations, provenance, policies, claims | `REPRESENTED` |
| matcher/substitution/rewrite mechanism | `HOST` mechanism reading U |
| six-op dispatch and stack semantics | `HOST` boundary reading U |
| domain arithmetic and unsupported operations | `HOST` or absent |
| encoding, decoding, measurement, storage accounting | `HOST` |
| rewritten outputs, extracted costs, policy claims | `DERIVED` |

The v3 host audit is retained in the raw v4 result for the complete candidate-by-candidate
breakdown.

### 3. Is storage semantically irrelevant?

Yes for the decoded semantic value: all candidates round-trip the same held-out values,
rules, histories, policies, and claims. No for operational behavior: hashes, stores,
indexes, e-classes, bytes, sharing, and traversal work change cost and performance.

So storage is semantically irrelevant only after the representation is decoded under the
candidate contract. It remains operationally relevant and is not erased from the
measurements.

### 4. E-graph contribution

The fair diamond trial reverses the simple-workload result. The reduced tree rewrite is
order-sensitive: one equality orientation yields `D`, the other yields `E`. The e-graph
retains five alternatives in one shared root class and extracts `E`, the cost-1 form,
under both orientations.

The irreducible observed property is simultaneous alternative retention with
order-independent cost-based extraction. The whole e-graph is not a universal kernel;
it leaves the Phase 1 semantic core as an optional/reference transformation layer.

### 5. Continuity

Continuity is not fundamental in the tested evidence. The same raw replacement history
supports both `breaks` and `preserves lineage` interpretations when the policy is also
represented. The output is a derived claim with provenance to evidence and policy.

This separates:

```text
evidence + policy -> continuity claim
```

from a primitive `identity` or `continuity` field.

### 6. Held-out survival

Representation survives all four domains on all three candidates. Full behavior does
not survive without new semantics: two held-out transformations deliberately request
unsupported operations. The frozen system therefore provides evidence about both what
things are and how supported rules change them, but not closure over arbitrary domain
operations.

## Smallest surviving set

```text
value
generic pattern/match/substitute/rewrite
represented rule/program
fixed evaluator boundary
transformation and composition as U
history and provenance
policy-derived continuity claim
cost as observation
```

`atom_pair`, `content_dag`, and `rewrite_egraph` remain experimental substrates or
layers. No final kernel is selected, and no weighted global score is used.

## Reproduction

```text
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -v
python -m matsi.benchmark_v4 --json-out results/phase1-v4-results.json
```

Raw results: `results/phase1-v4-results.json`.
