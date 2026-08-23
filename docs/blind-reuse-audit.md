# PiPi-47B — Blind Reuse Discovery / Grouping-or-Die

## Finding

PiPi-47B does not establish autonomous cross-domain reuse. The blind policy
can discover some coarse native invariants, but it pays grouping/build/
verification costs and produces future-relevant false merges. Its apparent
solve-operation savings do not survive exact-answer and vector-cost gates.

The exact gates are:

```text
DIES_BOOKKEEPING_ONLY       = true
DIES_GROUPING_ORACLE        = true
DIES_FALSE_MERGES           = true
DIES_DRIFT                  = false
SURVIVES_WITHIN_DOMAIN      = false
SURVIVES_HELDOUT_STRUCTURE  = false
SURVIVES_HELDOUT_DOMAIN     = false
STRONG_SURVIVAL             = false
```

`DIES_DRIFT=false` is the one positive control: the blind policy detected all
120 measured drift onsets before reusing the changed representation. That is
not enough for H1 because grouping and candidate discovery still failed the
exactness/held-out requirements. No next experiment is justified; the branch
should be frozen for conceptual redesign.

## Provenance and scope

The branch starts exactly at:

```text
1bdfa411b10545d4d88f14a2d07c2b317001bd8d
research: falsify closure accessibility
```

`docs/STATE.md` continues to declare
`c5860520c1f3873db2b32a2970b87ec9c809dfbc` as the accepted product frontier.
This is speculative research. It does not modify `main`, start Phase 5,
rewrite PiPi-42 through PiPi-46, or merge Closure Accessibility into accepted
evidence.

## Scale and stream design

The audit uses five native families and a fixed deterministic manifest:

- design domains: repeated sparse linear systems, subset-sum weights, and
  membership sets;
- validation domain: repeated graph queries;
- sealed held-out domain: automaton transition tables, with no blind candidate
  applicability probe;
- six size levels: `64, 128, 256, 512, 1024, 2048`;
- 20 independent structures per domain/size;
- 10 query streams per structure;
- 600 structures, 6,000 streams, and 1,227,600 query events.

The ten stream lengths are `8, 2, 16, 32, 64, 128, 256, 4, 512, 1024`.
They cover below/above break-even cases without passing future stream length
to the blind policy. Stream types include `TRUE_SHARED`, `SHORT_LIVED`,
`DECOY_SIMILAR`, `DRIFT`, `NEAR_SHARED`, and `INDEPENDENT`. Held-out runs use
new deterministic seeds, new structures/sizes within the frozen scale, and a
different drift onset fraction (`0.75` rather than the design `0.50`).

## Blind interface

`BlindPolicy.process(raw_object, query)` receives only the native raw object
and query. It does not receive a domain/family label, case name/path,
structure ID, whole-object hash, oracle grouping, future answer, or stream
length. Raw objects preserve native structure:

```text
rows             sparse linear matrix
values           subset-sum weights
members          membership set
edges            graph adjacency data
transition_rows  automaton transition table
```

Serialization is nuisance-randomized. Row/list/edge ordering changes across
streams; graph node labels are randomly renamed; the semantic payload stays
unchanged for true sharing. The blind policy derives coarse signatures from
native invariants and keeps a separate exact candidate identity. The
applicability probes are structurally discovered but are explicitly marked
`DOMAIN_LEAK` in the anti-leak audit because recognizing these native shapes
is effectively recognizing a candidate/domain boundary. The policy never sees
the held-out automaton candidate.

This separation is important: the method is not allowed to claim autonomous
cross-domain discovery when its candidate applicability probe is already a
domain-equivalent decision.

## Baselines and accounting

All baselines are run on the same manifest:

- `B0_RAW`: solve every query from scratch;
- `B1_ORACLE_GROUPING`: true grouping and candidate supplied, an upper bound;
- `B2_HASH_IDENTITY`: reuse only exact raw serialization identity;
- `B3_SIMPLE_PAYBACK`: supplied candidate/group and frozen
  `k_hat = ceil(G / (raw - reuse))`;
- `B4_DOMAIN_SPECIALIST`: domain-aware future-aware comparator, upper bound;
- `B5_BLIND_POLICY`: the actual discovery method.

No heterogeneous values are added into a scalar score. Every policy reports:

```text
H  grouping/similarity cost       Q  raw query/solver accesses
G  representation build          R  residue/update cost
S  post-build solve cost          V  verification cost
I  invalidation/drift cost        M  memory
P  precision bits                 W  wall time, machine-dependent
```

The JSON reports raw-minus-blind and blind-minus-raw deltas componentwise.
For example, negative `S` means fewer solve operations, while positive `G`,
`H`, `R`, `V`, or `M` are overheads. There is no claim that those different
units form one total scalar.

### Blind result by domain

The following deltas are `blind - raw` over the comparable vector fields; a
negative `S` is only an apparent solve saving until exactness and other
components are checked.

| Domain | Blind exactness | False merges | Stale errors | ΔG | ΔH | ΔR | ΔS | ΔV |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Linear systems | 10.56% | 120 | 219,600 | +7,749,600 | +126,720 | +245,040 | -1,319,295,360 | +980,160 |
| Subset-sum | 100% | 0 | 0 | +7,267,800 | +124,080 | +244,920 | -989,721,720 | +734,760 |
| Membership | 100% | 0 | 0 | +4,848,600 | +65,979 | +244,920 | -496,207,920 | +489,840 |
| Graph queries | 15.39% | 492 | 207,746 | +1,577,004 | +240,240 | +245,412 | -1,486,361,952 | +1,227,060 |
| Automaton held-out | 100% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

The automaton's blind policy correctly falls back to RAW, so it has no blind
gain. The oracle and specialist baselines remain exact and can amortize
stable streams; that is bookkeeping/upper-bound evidence, not evidence of
blind discovery.

## Grouping, drift, and break-even metrics

Across stream representatives:

```text
pairwise precision       = 0.3303
pairwise recall          = 0.8000
false-merge rate         = 0.0731
false-split rate         = 0.1000
stale-reuse errors       = 427,346
future-relevant merges   = 612
drift onsets             = 600
detected before reuse    = 600
```

The grouping figures are separate from answer correctness. A coarse invariant
can have a plausible pairwise grouping score while still reusing a candidate
against a future-relevant decoy. Verification in this audit checks the
discovered invariant, not hidden future truth; those stale errors are retained
instead of silently corrected.

The frozen break-even interval is emitted before a stream is consumed and
never receives its future length. On 24 candidate/size calibration cells:

```text
interval coverage                  = 100%
median multiplicative width        = 3.5x
future stream length as input      = false
```

This calibrates the supplied-cost payback calculation. It does not rescue H1:
the candidate and grouping decision remain the missing capability.

## Anti-leak audit

```text
case names removed                         true
serialization randomized                   true
variable/node renaming                     true
raw whole-object hash used by blind       false
future stream length exposed               false
held-out domain label exposed              false
oracle grouping available to blind         false
verification uses ground-truth future      false
candidate applicability domain-equivalent  true
marks                                      DOMAIN_LEAK
```

`B1_ORACLE_GROUPING` is physically separated and labelled as an upper bound.
`B2_HASH_IDENTITY` is deliberately present as a baseline; its large `H`
cost shows why exact serialization identity is not discovery.

## Reproduction and determinism

The implementation uses only the Python standard library:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m matsi.blind_reuse
```

The artifact is [results/blind-reuse.json](../results/blind-reuse.json).
Seeds, structures, stream manifest, logical action paths, cost counts except
`W`, grouping metrics, and gate outcomes are deterministic. `W` in cost
vectors and `machine_metadata` (`python`, OS, runtime wall measurements) are
machine-dependent and must be removed before replay comparison.
