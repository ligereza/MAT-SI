# Phase 2 — Self-Reference / Self-Observation

## Scope

Phase 1 remains closed and frozen at the final V4 state. This experiment does not
discover a new kernel, add VM operations, edit repository source, or start Phase 3.
It tests whether the same U and evaluator mechanisms can operate on a minimal
representation of MAT-SI itself.

The experiment runs over `atom_pair`, `content_dag`, and `rewrite_egraph` only as
substrates. The e-graph remains optional/reference machinery.

## Minimal self-model

`src/matsi/self_reference.py` builds a small ordinary-data self-model containing:

- a `description` object with claims about phase, semantic-core hash, evaluator hash,
  and VM vocabulary;
- an `executable_representation` object containing rule `R1`;
- represented transformation `R1_to_R2`;
- represented cost observations and provenance;
- alternatives and a represented cost policy;
- a represented history slot.

The description and executable representation are separate values. No repository dump
or special self-inspection type is used.

## Inspection

The public substrate operations encode the self-model and query these ordinary paths:

```text
executable_representation/rule
provenance
cost_observations/rule_R1
```

Each queried value is re-encoded and decoded exactly. The inspection code is the same
generic path query used for external U.

## Self-transformation

The represented transformation `R1_to_R2` is itself a rule program. Its `set` paths
modify the rule nested inside the self-model:

```text
R1: value + 1   on {value: 3} -> 4
R2: value * 2   on {value: 3} -> 6
```

The unchanged evaluator executes the transformation against the self-model, queries
the new rule, and executes that new rule. The before rule, transformation, after rule,
cost observations, provenance, and outputs are preserved as an ordinary history value.

The evaluator source hash is unchanged. No Python source or actual rule file is edited.

## Model / reality correspondence

The self-model claims the frozen phase, semantic-core hash, evaluator source hash, and
six-operation vocabulary. The runtime derives the same observations and produces
correspondence claims with provenance to both the represented claim and actual
observation.

The experiment then corrupts one claim at a time:

| Attack | Result |
|---|---|
| stale phase description | `inconsistent` |
| false R1 cost (`999` vs measured `4`) | `inconsistent` |
| corrupted rule opcode `xor` | `unknown`, not repaired |
| vocabulary missing `set` | `inconsistent` |
| fabricated provenance source | `unsupported`, not absorbed |

No checker silently synchronizes or repairs these values.

## Self-evaluation

The self-model carries two alternatives for the same input:

```text
R1       -> 4, observed instruction cost 4
R_short  -> 4, observed instruction cost 2
```

The represented policy minimizes instruction count. The result is a represented
selection claim choosing `R_short`, with alternatives, observations, policy, and
provenance preserved. Source mutation is false.

## Gate

All required Phase 2 evidence passes for all three substrates:

1. executable self-model;
2. ordinary inspection;
3. represented self-transformation;
4. unchanged evaluator executing R2;
5. complete history preservation;
6. model claims checked against observations;
7. false claims detected rather than absorbed;
8. same mechanism for external and self-data.

Decision: **A — CLOSE PHASE 2**.

Phase 3 is permitted by the gate but is not started automatically.

## Reproduction

```text
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -v
python -m matsi.self_reference --json-out results/phase2-self-reference-results.json
```
