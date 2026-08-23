# MAT-SI order-program synthesis: PiPi-42 → PiPi-46

This document is a synthesis of the frozen audits. It does not rewrite their
JSON or promote a provisional profile to a theorem. The strongest allowed
conclusion is conditional: several interface and discovery axes explain
specific measured differences, while the held-out quantum prediction and
general cross-domain mapping remain incomplete.

## Frozen checkpoints

| Audit | Branch | Parent | Commit | Result boundary |
| --- | --- | --- | --- | --- |
| PiPi-42 future equivalence | `research/future-equivalence` | `c99cfd1` | `f17d1ff` | sampled discovery, validation, sealed holdout, oracle only post-hoc |
| PiPi-43 order width | `research/order-width` | `f17d1ff` | `1d5a1d9` | exact independent-set counts, VE factor budgets, separator sufficiency |
| PiPi-44 cross-axis order | `research/cross-axis-order` | `1d5a1d9` | `4325a71` | same-domain Q/W/message tables and exhaustive finite minimality attack |
| PiPi-45 meta-lift | `research/meta-lift` | `4325a71` | `81be791` | blind candidate probes, budget, fallback, surface and Pareto audit |
| PiPi-46 quantum stress | `research/quantum-order-stress` | `81be791` | `634355a` | idealized query controls, information traces, held-out prediction |

All branches were pushed without opening a PR. `main`, PiPi-42, PiPi-43, and
the earlier JSON/results remain frozen.

## WHAT SURVIVED

### 1. Future sufficiency is an operational question

PiPi-42 made false merges visible: sampled or adaptive discovery can leave
histories that a later future query separates. A quotient is therefore not
evidence merely because a cheap projection looks compact. The sealed holdout
and post-hoc oracle boundary survived as useful protocol requirements.

PiPi-43 then demonstrated exact separator sufficiency on a checked small graph
and preserved the distinction between residual collision and future-equivalence
collapse. Its high-width controls stopped at the factor-state budget rather
than being called successes.

### 2. The interface has multiple axes in one domain

PiPi-44 is the clearest positive result. Within one layered binary factor
process domain it produced controlled small/large combinations of:

* `Q`: full future-equivalence quotient;
* `W`: structural boundary width;
* `D=2**W`: boundary-domain cells;
* `M`: distinct exact messages plus values, bytes, nonzero cells, and rank.

The same `W=1,Q=2` appeared with Boolean messages, very large weighted
messages, and many more ignored raw histories. Natural messages also fused
safely in finite cases. In that domain, `Q <= distinct_messages` is an exact
reproducible relation because future responses are functions of the message.
It is not a universal theorem about arbitrary representations.

### 3. Discovery must pay separately from solving

PiPi-45 showed that a small generic candidate library can select GF2, Horn,
dual-Horn, 2SAT, subset/MITM, cardinality, and future-refinement
representations from raw structures in the tested cases. The result is useful
only together with its costs: it recorded 10/10 surface-variant robustness,
one false lift, two missed lifts, one dominated selection, and 421 wasted
discovery operations. A raw fallback kept every selected answer exact.

The surviving operational rule is therefore budgeted knowledge acquisition,
not omniscience: probe, expose discovery/transform/solve vectors, freeze, and
fall back when characterization is not worth its budget.

### 4. Information gained per query is a meaningful descriptive axis

PiPi-46 preserved a real contrast without saying “quantum is free”. Grover's
ideal amplitude amplification changes query count without producing a small
classical global constraint. Simon's ideal samples produce independent GF2
constraints and shrink the secret candidate set until the secret is recovered.
Oracle construction, query count, postprocessing, repetitions, state dimension,
and success probability remain separate. This supports an information-flow
profile for these controls, not a universal speedup law.

## WHAT DIED

### 1. A single width or quotient is not enough

`W` is not `Q`; `Q` is not `M`; and `M` is not `W`. PiPi-44 directly attacks
all three identifications. PiPi-43 also showed that equal or manageable width
does not automatically determine solve operations, especially when order
discovery and factor materialization are separate costs.

### 2. A discovered lift is not automatically a valid lift

PiPi-45's adversarial graph produced a false specialized lift from a cheap
relation-shape probe. The audit preserved it rather than relabeling it as
success. Tight budgets also produced missed lifts. “The selector found a
representation” is therefore not enough; semantic certificates, exact
fallbacks, and post-hoc comparison are necessary.

### 3. Query advantage alone does not validate an OrderProfile predictor

The PiPi-46 rule was frozen before Simon and toy period-finding labels were
revealed. It got Simon right and period-finding wrong: held-out accuracy was
`0.5`. The toy period result also exposed the importance of classical
postprocessing and the exact oracle model. The profile is not yet predictive
outside its measured controls.

### 4. The strong thesis “Dimensions of Order was demonstrated” is rejected

The audits support conditional, domain-specific operational statements. They
do not establish a stable universal dimension, a universal scalar speedup, a
quantum/classical predictor, or a representation-discovery policy whose cost
is known to be small on new problems.

## WHAT WE STILL CANNOT EXPLAIN

* A general bound relating `Q`, `W`, message description/rank, discovery cost,
  and solve cost across graph, subset-sum, XOR, and future-query domains.
* When a same-width/same-quotient message is cheaper to operate on rather than
  merely different in value or byte description.
* Whether order discovery can be made predictively cheap without paying nearly
  the cost of solving. PiPi-45 exposes this cost but does not remove it.
* Why a simple profile rule should transfer from Simon to period finding. The
  held-out failure is evidence against assuming that global constraints alone
  predict the category.
* The relationship between quantum query complexity and gate/contraction
  width. Full gate costs were `NOT_MEASURED`, and the optional tensor bridge was
  deliberately `NOT_RUN`.
* How the measured axes behave at scales where exhaustive future quotients,
  brute force, or ideal oracle tables are no longer available.

## Reproducibility boundary

Raw inputs, frozen seeds, exact counts, integer resource counts, partitions,
constraint ranks, candidate decisions, and stop decisions are deterministic in
the committed implementations. `wall_ms` fields are machine-dependent and
not expected to match byte-for-byte. Oracle, expected-label, and held-out
evaluation fields are marked post-hoc in the corresponding results.

The common checkout command is:

```text
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

The final PiPi-46 checkout passed 139 tests with one pre-existing skip. No
Phase 5 work was started.
