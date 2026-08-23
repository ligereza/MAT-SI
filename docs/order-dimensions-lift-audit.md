# PiPi-inspired representation-lift audit

This is a speculative branch experiment derived from the 2026-08-23 PiPi
handoff. It is not a new MAT-SI phase and it does not redefine the MAT-SI kernel.

The audit asks one bounded question: can a candidate representation be discovered,
paid for, and used without losing the future behaviour of the raw problem?

It contains three deterministic families:

1. A raw Tseitin-like CNF family. An exact affine-block detector is applied without
   being told the generating equations. Positive instances are compared with
   perturbed and random-3SAT controls. DPLL nodes, affine row operations, discovery
   steps, and CNF size remain separate measurements.
2. A subset-sum future-quotient family. Full residual state is compared with sign,
   parity, and modular projections. A projection is rejected when one projected
   state contains histories with different future classes. A superincreasing family
   is a no-collapse control.
3. A pi-digit negative control. A held-out local next-digit predictor is compared
   on generated pi digits, random digits, shuffled pi, and a planted local process.
   The planted process must be detected; pi need not be “proved random”.

The observation envelope uses the existing Phase 4C shape—`before`, opaque
`intervention`, `after`, and `provenance`—with independent resource dimensions and
an explicit residue/fallback slot. The result is intentionally marked
`KEEP-SPECULATIVE`. Any promotion would require freezing parameters, adding
held-out instances, rerunning from a clean checkout, and preserving the negative
controls.

Run it with:

```text
$env:PYTHONPATH="src"
python -m matsi.order_dimensions --json-out results/order-dimensions-lift-audit.json
```
