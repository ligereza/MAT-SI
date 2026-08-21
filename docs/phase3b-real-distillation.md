# Phase 3B — Blind Real-Repository Distillation

## Freeze and scope

`main` was fast-forwarded to controlled Phase 3 commit `2ba30fe`. The real-repository
experiment runs on `phase3-real-distillation`. Phase 1, Phase 2, Phase 3A, and the
semantic core remain unchanged. No full repository ingestion, crawler, embedding, LLM,
or Phase 4 code was created.

The manifest was committed before source acquisition or distillation as commit
`4e8921c`. It fixes five independent Python sources: A and B for discovery, C as
held-out, and N1/N2 as negative controls. See
`corpus/phase3b-real-manifest.json` for URLs, SHAs, paths, language, timestamps, and
assignments.

## Blind adapter pass

Only the selected source files were fetched by exact commit SHA. The blind pass used
Python's AST, not README text, topics, comments, docstrings, function names, or LLM
labels.

The adapter:

- preserves node kinds, field nesting, sequence order, operator kinds, and literal
  type kinds;
- normalizes identifiers and literal values to neutral slots and removes source
  positions;
- records identifiers and literal values as residue/provenance;
- excludes comments, formatting, docstrings from executable bodies, lexical spelling,
  and runtime effects.

Every entry records this preservation/normalization/loss audit. The adapter is a
projection into U, not a MAT-SI ontology or universal code IR.

## Discovery from A+B

The structural/compression frontier produced a candidate G with:

- source units: a `FunctionDef` from A and a `ClassDef` from B;
- shared neutral structure nodes: `18`;
- compression gain: `5` bytes;
- exact reconstruction of both neutral representations;
- semantic status: unavailable;
- static behavior signatures: different.

The candidate was selected before C, N1, or N2 using fixed source-order selection on
the A+B Pareto frontier. No contextual labels were used to create it.

This is already a warning: structural anti-unification can generalize across a
function/class boundary and still reconstruct both inputs. Reconstruction and
compression do not establish reusable behavior.

## Held-out C

G was frozen before C was evaluated. C matched G and reconstructed its neutral slices;
the marginal explanation cost was lower than storing the entire neutral slice. However,
the match was another broad structural skeleton, not verified executable behavior.
The held-out result therefore shows structural transfer but not a trustworthy semantic
prediction.

## Negative controls

Both N1 and N2 also matched the selected G and were marked structurally useful by the
existing recurrence/compression criterion. They were not rejected because semantic
verification was unavailable.

This is the decisive false-abstraction result:

```text
neutral AST recurrence + reconstruction + compression
    -> accepts unrelated real code as useful G
```

The controlled Phase 3 mechanism did not contain enough semantic evidence to reject
these controls. No new semantic mechanism was added after observing this failure.

## Representation alignment

The useful-looking result required known normalization:

```text
Python source -> Python AST -> neutral U
```

The relationship between source text and neutral U was supplied by the adapter, not
discovered by MAT-SI. Alignment was not the principal unresolved bottleneck in this
run; the adapter was deterministic and its losses were recorded. The principal failure
was semantic discrimination after alignment.

## Surprise test

G contained no manifest IDs, source names, or normalization-rule labels. Its recurrence
came from neutral AST relations. This confirms that the false abstraction was not caused
by answer leakage; it was genuinely derived from source structure, but it was not useful
enough semantically.

## Gate answers

1. A reusable structural G can be derived from independent real code, but it is not
   semantically trusted.
2. A and B reconstruct from G plus residue.
3. Misleading similarity is **not** rejected: N1 and N2 are false positives.
4. C receives structural/compression value, but no verified behavioral prediction.
5. The result uses a known AST-to-U normalization; alignment is recorded, not claimed
   as discovery.
6. The apparent discovery came from structure and compression. Missing semantic
   evidence prevented validation.
7. Residue contains source-specific AST structure, identifiers, and literals that G
   does not explain; it is preserved by digest/size/provenance in the result.

## Decision

**C — CONTROLLED DISCOVERY DID NOT TRANSFER.**

Concrete failed assumption:

> Phase 3A's structural anti-unification plus compression criterion is sufficient to
> identify reusable structure in real code. In 3B it accepts recurring neutral AST
> skeletons from negative controls without semantic evidence.

The branch stops here. No Phase 4 begins, and no generalized semantic evaluator is
added to rescue the result.

## Reproduction

```text
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -v
python -m matsi.real_distillation --json-out results/phase3b-real-distillation-results.json
```
