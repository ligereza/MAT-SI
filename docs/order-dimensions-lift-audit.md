# PiPi-inspired representation-lift audit

This is a speculative branch experiment derived from the 2026-08-23 PiPi
handoff. It is not a new MAT-SI phase and it does not redefine the MAT-SI kernel.

The audit asks one bounded question: can a candidate representation be discovered,
paid for, and used without losing the future behaviour of the raw problem?

It contains three deterministic families:

1. A raw Tseitin-like CNF family. An exact affine-block detector is applied without
   being told the generating equations. Positive instances are compared with
   perturbed and random-3SAT controls. DPLL nodes, affine row operations, discovery
   steps, and CNF size remain separate measurements. DPLL nodes and GF2 row-xor
   operations are different units, so the audit reports them as a resource vector;
   it does not call one “reduced solver work” and does not declare Lift Gain.
2. A subset-sum future-quotient family. Full residual state is compared with sign,
   parity, and modular projections. The quotient built from enumerating all
   `suffix_sums` is explicitly labelled `GROUND_TRUTH/ORACLE`, and its enumeration
   cost is recorded. Residual collisions, dead-history collapse, and
   future-equivalence collapse are reported separately; those counts are not
   additive because dead-history collapse can contain residual collisions. A second discovery attempt
   uses sampled future probes without the oracle, charges its query cost, and tests
   its proposed classes on held-out probes. The superincreasing control has unique
   residuals but can still collapse dead histories under the stated future query.
3. A pi-digit negative control. A held-out local next-digit predictor is compared
   on generated pi digits, random digits, shuffled pi, and a planted local process.
   Parameters and seeds are frozen before the train/held-out split; random and
   shuffled null replicates are recorded. Comparisons are descriptive until a
   statistical test is preregistered; the planted process remains a smoke control.

The output uses the existing Phase 4C field shape—`before`, opaque `intervention`,
`after`, and `provenance`—but labels these entries `derived_audit_record`: they are
not claims of observed domain snapshots. Their before/transform/after digests are
computed from the generated raw inputs and actual transform/results. Scope
declarations such as “main was not modified” are kept separate from empirical
results. The result is intentionally marked `KEEP-SPECULATIVE`.

Deterministic fields include generators, seeds, parameters, clauses, residual
classes, sampled masks, and exact integer counters. `wall_ms` is retained only as a
machine-dependent measurement and is not expected to match byte-for-byte between
runs. Any promotion would require preserving the negative controls and rerunning
the full suite from a clean checkout.

Run it with:

```text
$env:PYTHONPATH="src"
python -m matsi.order_dimensions --json-out results/order-dimensions-lift-audit.json
```
