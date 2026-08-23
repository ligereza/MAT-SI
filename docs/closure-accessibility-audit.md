# Closure Accessibility falsification audit

## Outcome

This experiment does not support H1: no tested black-box route recovered the
global order with `Q << r` while keeping representation/discovery cost below
the order scale. The exact return methods paid one query per start-orbit
period. The only low-`Q` exact route was full permutation-matrix inspection,
and its `G`/`M` cost was `N^2`; it is therefore an encoding/materialization
result, not a closure-accessibility result.

The gates are:

- `DIES_REPRESENTATION_LEAK`: the explicit phase-like `1/r` descriptor control
  is classified as leakage and is not main evidence.
- `DIES_ENCODING_COST`: full-matrix spectrum/order recovery is disqualified by
  its counted `N^2` representation cost.
- `SURVIVES_FAMILY_SPECIFIC`: false.
- `SURVIVES_CROSS_REPRESENTATION`: false.
- `STRONG_SURVIVAL`: false.

This is an exact finding for this finite audit, not a universal theorem about
all representations or all possible algorithms. No Lift Gain is declared.

## Provenance and scope

The actual parent of this branch is:

```text
ef55054f11cea576ddb95e40f09ba53b8c6261d1
docs: synthesize order program results
```

`docs/STATE.md` still names `c5860520c1f3873db2b32a2970b87ec9c809dfbc` as
the accepted product frontier. This branch is speculative research from the
later order-program synthesis hito; it does not move the accepted frontier.
`main`, Phase 5, and frozen PiPi-42 through PiPi-46 artifacts are out of
scope.

The audit has 40 cases: 10 hidden orders (`5, 6, 7, 8, 9, 10, 11, 12, 14,
15`) across four raw permutation families, all with the same raw state
dimension `N=24`. `5, 6, 7, 8, 9, 10` are the design set and `11, 12, 14,
15` are held-out prime/compound values. The decoder receives only an
interface, raw state dimension `N`, a start state, and black-box operations.
It receives neither hidden `r` nor the family name; `N` itself cannot encode
which tested `r` was selected.

## Representation audit

The three same-order families are paired at each `r`:

1. `CANONICAL_CYCLE`: an active `r`-cycle with fixed filler states.
2. `CONJUGATED_CYCLE`: `P^-1 T P` using a frozen seed, preserving order while
   destroying canonical local labels.
3. `RANDOM_SINGLE_CYCLE`: a frozen random ordering of the active cycle.

`MULTI_CYCLE_CONTROL` has the same state count and permutation one-step
surface, but contains a start cycle of length `r-1` and a second small cycle
whose length is the first value in `(3, 4, 5, 6, 7)` that does not divide
`r-1`. Its global order is consequently `lcm(r-1, k)`, deliberately not the
hidden single-cycle target. A start-orbit answer on this control is not a
global-order answer. This prevents a collision/local-period result from being
reported as future/global equivalence.

Each raw permutation is recorded by a SHA-256 digest of its actual integer
mapping. These are raw-instance digests, not synthetic `{family, phase}`
records. The phase-like descriptor appears only as an explicitly excluded
leak control:

```text
observable includes 1/r or an equivalent explicit order descriptor
representation_leak = true
counts_as_main_evidence = false
```

## Interfaces and methods

The interfaces are kept separate:

- `STEP_ORACLE`: counted calls to `T(x)`.
- `SCALAR_OBSERVABLE`: observations of the fixed universal
  `h(x) = x^2 + 3x + 7`; no order descriptor and no float precision.
- `MATRIX_VECTOR_PRODUCT`: counted vector products without matrix
  materialization.
- `FULL_PERMUTATION_MATRIX`: full `N x N` matrix; materialization is counted.

The attempted methods are sequential return, Floyd cycle detection, a
baby-step/giant-step baseline (retained as not applicable without a group
operation/inverse), autocorrelation/FFT, Prony/matrix pencil, DMD/Koopman,
and full-matrix eigenspectrum/order recovery. The latter is exact by cycle
decomposition of the acquired permutation matrix, but its resource record
has `Q=1`, `G=N^2`, and `M=N^2`.

Every result retains the resource vector instead of collapsing incomparable
units:

```text
Q = oracle calls / observations
P = precision bits
M = working-memory cells
G = representation, materialization, or encoding cells
D = decoder primitive operations
W = wall-clock milliseconds (machine-dependent)
C = certificate bit
```

All main scalar/black-box records use `P=0`; they do not receive an encoded
response phase. The report does not compare `Q` to `D` as if they were the
same unit.

## Discovery, validation, and held-out protocol

Parameters were frozen before held-out execution:

- discovery prefix: 8 observations/queries;
- scalar-method window: 12 observations;
- train orders: `5, 6, 7, 8, 9, 10`;
- held-out orders: `11, 12, 14, 15`;
- seeds: canonical `0`, conjugated `1000+r`, random `2000+r`, control
  `3000+r`.

Discovery and validation are separate fields in every method record. Exact
return methods continue until a repeat, with only the raw state-space size
used as a safety bound; the order is never supplied as a stopping parameter.
Autocorrelation, Prony, and DMD retain their uncertified/failed outcomes when
the fixed window does not identify a model. No `+0.02`, null-tuning, or
post-hoc held-out adjustment is used.

The cross-representation predictor is frozen from canonical/conjugated train
cases: predict linear return cost unless a validated repeat appears inside
the fixed discovery prefix. On random held-out representations it finds no
sublinear route; on the multi-cycle control it exposes the local/global order
ambiguity rather than converting it into evidence.

## Reproduction

The implementation is standard-library-only:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m matsi.closure_accessibility
```

The generated artifact is [results/closure-accessibility.json](../results/closure-accessibility.json).
Logical construction, seeds, raw digests, method statuses, `Q/P/M/G/D/C`,
gate values, and conclusions are deterministic. `W` in the resource vector
is intentionally not byte-reproducible because it depends on interpreter and
machine scheduling. Replay compares JSON after ignoring `W` (and any
`wall_ms` fields if a later renderer expands the field name).
