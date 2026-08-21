# Phase 1 Protocol v4

## Objective

Protocol v4 is a gate attack, not an architecture phase. Each branch uses the smallest
experiment that can change the Phase 1 belief and stops once its question is resolved.
No kernel is merged, no final score is introduced, and Phase 2 remains closed.

The four attacks are:

1. locate the minimum trusted semantic boundary;
2. give equality saturation one alternative-rich workload;
3. evaluate continuity as policy over raw provenance;
4. freeze that boundary and test held-out domains.

## 1. Minimum trusted semantic boundary

`src/matsi/minimal_rewrite.py` implements one generic mechanism over ordinary U data:

```text
pattern -> match -> bindings -> substitute -> rewrite
```

The same mechanism expresses two literal behaviors (increment and double) and a
structural field rename. The experiment adds zero behavior-specific Python branches.
Rules are encoded and decoded through each candidate substrate before execution.

This branch stops there. The generic structural mechanism does not provide open-ended
numeric semantics. Replacing the six-op represented-rule VM with a larger generic
arithmetic evaluator would add machinery before removing a demonstrated requirement.
The current trusted boundary therefore remains:

```text
atom equality + generic pattern/match/substitute/rewrite
                         + six-op VM for open arithmetic
```

The six VM operations remain host dispatch semantics:

```text
get, const, add, mul, set, return
```

This is a boundary, not a claim that the six operations are MAT-SI primitives.

## 2. Fair e-graph trial

The workload is an adversarial diamond with overlapping alternatives:

```text
A -> B -> D
|         ==
v         E
C -> E
```

Costs are `A=4`, `B=3`, `C=3`, `D=10`, and `E=1`. The tree normalizer is run with
both equality orientations (`D -> E` and `E -> D`). The e-graph retains both forms,
unions the equality, and extracts by cost.

Observed result:

| Mechanism | Orientation | Result | Alternatives / unique terms | Work | Lowest cost |
|---|---|---|---:|---:|---:|
| reduced tree | `D -> E` | `E` | 4 normalizer terms / 5 exhaustive | 14 / 25 | no |
| reduced tree | `E -> D` | `D` | 3 normalizer terms / 5 exhaustive | 9 / 25 | no |
| e-graph | `D -> E` | `E` | 5 retained | 20 | yes |
| e-graph | `E -> D` | `E` | 5 retained | 20 | yes |

The e-graph's exact contribution is shared equivalence-class retention plus
order-independent cost extraction. The full e-graph is not promoted to the semantic
core or universal substrate. It remains an optional/reference transformation layer;
the property is the part worth preserving for future simplification.

## 3. Continuity as policy over provenance

One raw provenance graph contains two observation positions and one replacement event.
The same encoded history is evaluated with two encoded policies:

```text
replacement_breaks_continuity
replacement_preserves_lineage
```

Both round-trip the identical evidence. They derive different claims, both carrying
digests of the history and policy as provenance. No stable object ID or continuity
primitive is introduced.

The result resolves this branch: continuity is a policy-dependent claim over evidence,
not a fundamental property that must be stored in U as identity.

## 4. Freeze and held-out attack

After the first three branches, the semantic core is frozen. The held-out corpus was
not used to design it:

- software release counter;
- ordinary human action/process queue;
- symbolic subtraction;
- unfamiliar weaving/rotation process.

All three candidates round-trip every held-out payload, rule, and execution input. The
frozen six-op evaluator executes the software and human-process rules. It preserves two
intentional counterexamples without changing the core:

```text
symbolic_subtraction -> unknown represented instruction: sub
unfamiliar_weaving_process -> unknown represented instruction: rotate
```

These are one unresolved boundary class: a represented transformation can be stored
but cannot execute when it requests an operation outside the fixed vocabulary.

## Host leakage audit

The audit retains the v3 categories:

- `HOST`: candidate encode/decode, VM dispatch, arithmetic, matcher/rewrite loop,
  reachability, storage accounting, and measurement;
- `REPRESENTED`: values, patterns, bindings, rules, transformations, history,
  provenance, policies, and claims;
- `DERIVED`: rewritten values, execution output, e-classes, extracted costs, and
  policy-dependent continuity claims.

The goal is minimum trusted semantics, not zero Python code. The held-out failure shows
exactly where semantic work is still trapped in the host.

## Gate status

The gate does not open. Protocol v4 selects decision **B — one counterexample remains**:

> The frozen core represents held-out symbolic and unfamiliar structures, but cannot
> execute a represented rule requiring an operation absent from the six-op VM without
> adding a new host opcode or a new represented operation mechanism.

No unrelated feature work follows this result, and no Phase 2 code is created.
