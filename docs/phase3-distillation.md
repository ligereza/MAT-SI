# Phase 3 — Distillation / Structure Discovery

## Scope

Phase 1 and Phase 2 remain closed. `main` was fast-forwarded to Phase 2 commit
`03ba1b0`, and this experiment runs on `phase3-distillation` without ingesting external
repositories.

The corpus is deliberately small and uses neutral IDs (`u_a`, `u_b`, etc.). It does not
name the abstraction being sought. Every object is a small executable rule program.

## Discovery from A and B

For `u_a` and `u_b`, the structural anti-unifier derives this ordinary U template:

```text
{
  name: variable,
  meta: shared,
  program: [
    {op: get, path: variable},
    {op: const, value: 1},
    {op: add},
    {op: return}
  ]
}
```

The abstraction was not supplied as a label. Its evidence is independent:

- shared structural nodes: `39`;
- semantic signatures: both `[1, 2, 3, 6]`;
- raw A+B description cost: `366`;
- G plus residues description cost: `271`;
- compression gain: `95`.

The exact structural baseline does not match. The naive subtree baseline finds repeated
subtrees but cannot reconstruct either object or predict behavior. Simple
anti-unification reconstructs both, but only the combined candidate uses semantic and
compression evidence to call it useful.

## Residue

The residue is preserved, not discarded:

```text
residue_A = {name: rho, path: [value]}
residue_B = {name: sigma, path: [payload, n]}
```

Applying G with each residue reconstructs the original rules exactly. The residue
explains surface-specific names and data paths; G explains the executable operation
skeleton.

## Negative controls

| Control | Structural recurrence | Semantic equivalence | Compression | Decision |
|---|---:|---:|---:|---|
| similar surface, different behavior | present | no | positive but small | reject |
| partial shared structure | present | no | negative | reject |
| no useful shared abstraction | weak | no | negative | reject |
| same transformation, different names | present | yes | positive | accept |

This prevents compression or repeated syntax from becoming a semantic abstraction by
itself.

## Held-out C

G was frozen after A and B. C (`u_c`) did not participate in discovery. It matches G
with residue `{name: tau, path: [packet, count]}` and reconstructs exactly.

The predicted and observed semantic signatures are both `[1, 2, 3, 6]`. Because G is
already paid for by discovery, the held-out comparison uses marginal explanation cost:

```text
G reference + C residue: 62 bytes
generic full C:         188 bytes
```

Therefore G gives C measurable explanatory value without modifying G after seeing C.

## Cross-representation test

One increment transformation is represented canonically as `program/op/path` and in a
substantially different surface form as `steps/kind/target`. Raw anti-unification of
the two surfaces collapses to a useless whole-object variable and has negative
compression.

The same existing represented rewrite mechanism applies ordinary normalization rules
to the second surface. After normalization, anti-unification recovers the same
operation skeleton, reconstructs both forms, and preserves semantic equivalence. The
normalization rules and provenance are themselves represented data; no host alias table
or LLM label is used.

The result is precise: raw layout alone is insufficient, but G survives a surface
change when the relationship between surfaces is expressed as represented
transformation evidence.

## Gate answers

1. **Can MAT-SI derive G from A and B without being told G?** Yes. Structural
   anti-unification derives it; semantic and compression checks validate it.
2. **Can A and B be reconstructed from G + residue?** Yes, exactly.
3. **Does it reject misleading similarity?** Yes. Similar syntax with different
   behavior and negative compression controls are rejected.
4. **Does G provide value on held-out C?** Yes. C is reconstructed and its behavior is
   predicted with lower marginal description cost than the generic baseline.
5. **Does G survive surface representation changes?** Yes, after represented
   normalization; raw unnormalized layout alone is rejected.
6. **Which signal produced the useful discovery?** A combination: structure proposes
   G, semantics rejects false generalizations, and compression measures reuse. No
   single signal is treated as the score.
7. **What remained as residue and why?** Names and access paths remained because they
   differ while the executable operation skeleton remains shared.

## Decision

**A — DISCOVERY DEMONSTRATED.**

Controlled distillation works on the small corpus. Real repository experiments are now
permitted by this gate, but no repository ingestion starts automatically.

## Reproduction

```text
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -v
python -m matsi.distillation --json-out results/phase3-distillation-results.json
```
