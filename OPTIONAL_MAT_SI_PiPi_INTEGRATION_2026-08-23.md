# OPTIONAL — How to unite MAT-SI with Dimensiones del Orden / PiPi

> This is deliberately **optional speculative integration**, not accepted MAT-SI evidence and not a Phase 5 declaration.

## Recommendation in one sentence

Do **not** merge the narratives by renaming MAT-SI concepts. Instead, use PiPi as a new adversarial **experiment family** that asks whether MAT-SI can discover future-relevant representations and whether the total lift cost is actually lower.

## Why the two projects genuinely meet

The strongest overlaps are operational, not poetic:

| MAT-SI | PiPi / Dimensiones del Orden |
|---|---|
| Phase 1 competing representations | representation lift / Order Profile |
| description + mechanism cost | Lift Gain with discovery + transform + solve |
| Phase 3 `G + residue` | model `M` + colita/residual `R` |
| cross-representation normalization | same semantics under alternative surface languages |
| negative controls + held-out C | ANTI-PI falsification |
| Phase 4C minimum observability | evidence needed to compare state before/after a lift |
| separate resource dimensions | Order Profile should remain a vector, not one magic scalar |
| CODEINE CONTINUE/SWITCH/STOP/UNKNOWN | “no vale la pena” stop/fallback protocol |
| provenance + replay | every lift must be auditable/recomputable |

The overlap is strong enough to justify an experiment, but not strong enough to declare identity.

## What I would NOT do

Do not:
- start Phase 5;
- redefine the MAT-SI kernel around Π;
- add π/3/6 numerology to the ontology;
- treat `residue == colita` as proven;
- add quantum machinery to core MAT-SI;
- promote PiPi toy speedups as project claims;
- overwrite historical results;
- use the old Phase 4A `+0.1667` as current predictive evidence (the reproducibility audit corrected same-population gain to `0.0`).

## Branch proposal

If an agent is explicitly authorized to test the integration:

`research/order-dimensions`

Recommended parent:
- actual current `main` HEAD observed: `059574fd6f5fbd28a3f62b705cfd702c243933ba`

Branch metadata should also record:
- `declared_accepted_frontier = c5860520c1f3873db2b32a2970b87ec9c809dfbc`
- `portable_evidence_commit = ebf8f6e978cf7a3ee99f6fc29981a245f11bf92f`

Reason: this prevents confusing Git history with the epistemic acceptance boundary.

## First gate: representation-lift audit

### Question

Can MAT-SI discover a representation whose **total** cost is lower than a frozen baseline, while preserving future-relevant semantics and rejecting cases where no lift exists?

### Three required families

Use one positive, one no-lift control, and one anti-numerology control.

#### A. Tseitin / affine positive
Input: raw CNF.
Candidate discovery: infer local affine structure.
Lift: GF(2).
Expected: positive Lift Gain.

This reuses the strongest PiPi result without telling discovery “XOR” in advance.

#### B. Subset-sum adversarial pair
Two distributions:
- dense / near-equal where future histories collapse;
- superincreasing where they do not.

Expected:
- positive state quotient in first;
- no false compression in second.

#### C. π decimal hidden-code negative
Input: frozen digit slices.
Allow the same family of local Markov/mod/lag proposals used in PiPi-36.
Expected: no held-out lift.

Purpose:
force the system to prove it can say **NO** to the origin story of the research.

## Proposed represented record

Do not invent a new global schema. Extend Phase 4C experimentally through represented residue:

```text
before
intervention: opaque lift-attempt token
after
provenance
resources:
    discovery_steps
    discovery_cpu_or_wall_if_measured
    transform_steps
    solve_steps
    bytes_or_state_count
residue:
    candidate_representation
    certificate
    evidence_for
    evidence_against
    fallback
```

Do not add `success`, `progress`, `good_representation`, or `stuck` to the base record.

Those are derived hypotheses.

## Proposed metrics

Keep independent axes first.

### Representation
- description bytes;
- reconstruction fidelity;
- structural sharing.

### Future sufficiency
- exact equivalence where possible;
- held-out predictive loss otherwise;
- false merges / false splits.

### Width
- number of quotient states;
- separator/treewidth proxy;
- peak local factor/state size.

### Discovery
- candidates tried;
- elapsed/CPU if measured;
- operations;
- model-selection description cost.

### Solve
- operations;
- wall/CPU if measured;
- memory if measured.

### Decision
- baseline total resource vector;
- lifted resource vector;
- Pareto relation;
- optional scalar only after an explicit policy.

## New concept that fits MAT-SI without replacing it: `OrderProfile`

Represent it as ordinary data:

```text
OrderProfile = {
    predictive_state_complexity,
    separator_width,
    algebraic_certificate,
    query_complexity,
    lift_discovery_resources,
    profitable_depth
}
```

None is mandatory if unobservable.
Unknown remains unknown.

The important design choice is that `OrderProfile` is a **measurement/result object**, not a primitive of MAT-SI.

## `Π` should remain external notation

Use Π only in research prose to mean:

> “attempt to distill the current representation/residue into reusable structure under an explicit budget and query class.”

Do not encode the Greek symbol or the numeric constant as a kernel primitive.

A precise research signature would be:

`Π_(L,B,Q)(R) -> candidate (M, R') or NO_LIFT`

where:
- `L` = allowed representation language/candidate family;
- `B` = discovery budget;
- `Q` = future query class;
- `R` = current residual/evidence.

A candidate counts only if:
1. it preserves/reconstructs what the protocol requires;
2. future queries remain correct;
3. held-out/negative controls survive;
4. discovery + transform + solve beats baseline under the declared policy.

## Direct mapping to CODEINE

PiPi-35 suggests a new *hypothesis* that CODEINE could test later:

> if repeated attempts consume measured resources without reducing an observable future-relevant state/width, switch representation before continuing the same strategy.

Do **not** implement that now.

First, use historical/replayable sessions to ask whether an OrderProfile-like observable could have distinguished:
- genuine productive change;
- repeated unchanged state;
- representation switch.

If the current Phase 4C record cannot answer it, the correct result is `UNKNOWN`, not new instrumentation by assumption.

## Quantum role

Quantum should enter as a benchmark family, not as a MAT-SI dependency.

Use:
- Grover as negative/limited-structure control;
- Simon as positive hidden-linear-structure control;
- Shor/order finding as conceptual prior art;
- tensor networks/treewidth as bridge between representation width and simulation effort.

The research question for MAT-SI is:

> can the same represented cost/future-sufficiency language describe why one formulation exposes useful global order while another remains search?

No quantum hardware is required for the first gate.

## Suggested agent work sequence

1. Import this capsule as **external speculative evidence**.
2. Reproduce 3–5 selected PiPi artifacts independently; do not trust CSVs blindly.
3. Lock tests for one positive and two negative controls.
4. Implement only the minimal represented result needed to compare baseline/lift.
5. Run blind discovery.
6. Freeze candidate.
7. Run held-out.
8. Report `PROMOTE / KEEP / DEMOTE / KILL / INVALID`.
9. Only after a successful gate consider whether the result belongs in MAT-SI foundation.

## Success condition for the integration

The integration is successful only if it produces a result MAT-SI did not get merely by renaming existing fields.

The strongest target is:

> **automatic discovery of a lower-cost future-sufficient representation, with discovery cost paid and a matched negative-control family where the system correctly refuses the lift.**

That would genuinely connect MAT-SI's representation/distillation program to Dimensiones del Orden.
