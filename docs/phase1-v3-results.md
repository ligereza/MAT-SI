# Phase 1 Protocol v3 Results

## Decision

Protocol v3 does not select or merge a final kernel. It does change the interpretation of
the v2 comparison:

1. structural representation and transformation/equivalence are different experimental
   axes;
2. represented rules can control a fixed evaluator;
3. transformations, history, cost, and provenance can be stored as ordinary U;
4. relation paths can carry continuity evidence without a stable ID, but continuity is
   not discovered by the candidates;
5. the useful e-graph mechanism reduces to a simpler generic rewrite mechanism in the
   tested workloads.

The Phase 1 gate remains closed because much operational semantics and continuity
interpretation are still host-defined.

## S x E separation

The v3 matrix uses `atom_pair` and `content_dag` as substrates and compares direct and
rewrite evaluators above them. All combinations preserve exact fidelity for both
`reverse` and `double_reverse` across repetition, shared graph, and temporal branching
at n = 10, 100, and 1000.

The Pareto frontiers contain direct evaluator combinations only. Both substrates remain
visible because they trade description/sharing/query costs differently; the rewrite
evaluator adds evaluation cost without improving those substrate dimensions in this
matrix. Therefore the apparent competition between e-graph D and substrate D largely
disappears when the roles are separated, but the e-graph does not become an operational
winner merely by being moved to E.

Representative `double_reverse`, n = 1000:

| Combination | Shape | D bytes | Sharing | Evaluation wall |
|---|---|---:|---:|---:|
| `atom_pair + direct` | repetition | 363,481 | 0.00 | 160 ms |
| `atom_pair + rewrite` | repetition | 363,481 | 0.00 | 888 ms |
| `content_dag + direct` | repetition | 69,988 | 1.00 | 397 ms |
| `content_dag + rewrite` | repetition | 69,988 | 1.00 | 1,105 ms |

For the same operation at n = 1000 on shared graphs, direct/rewrite evaluation is
approximately 505/2,096 ms over `atom_pair` and 672/2,581 ms over `content_dag`.
The substrate's query time is unchanged by the evaluator choice in this experiment,
which is the intended separation of measurements.

## Represented rule controls execution

All three candidate representations pass the same data-driven VM experiment:

| Candidate | rule_A(3) | rule_B(3) | Self-modified rule | Self-modified output | VM source unchanged |
|---|---:|---:|---|---:|---|
| `atom_pair` | 4 | 6 | `rule_B` | 6 | yes |
| `content_dag` | 4 | 6 | `rule_B` | 6 | yes |
| `rewrite_egraph` | 4 | 6 | `rule_B` | 6 | yes |

This is stronger than descriptive self-application: the evaluator reads an encoded rule,
the rule data changes, and the unchanged evaluator produces different behavior. The
same evaluator edits a represented rule and then executes that modified rule on external
data. The remaining limitation is explicit: the six-instruction VM is still host code,
so this is evidence of represented executable semantics, not self-hosting.

## Transformations as ordinary U

The represented universe contains values, rules, transformations, a composition, two
history records, cost observations, and provenance. Every candidate round-trips the
universe and the composition. The composition is executed as:

```text
T1({value: 3}) = {value: 4}
T2(T1({value: 3})) = {value: 8}
```

The composition itself is represented as a dictionary with a list of transformation
records. No privileged metadata class is required for the stored cost or provenance.

## Continuity without an ID primitive

All nine cases round-trip for all three candidates without a stable ID field. The facts
below are generated from the represented relation graph and are deliberately not
collapsed into one identity value:

| Case | Content equal | Historical path | Alias relation | Equivalence relation | Provenance |
|---|---:|---:|---:|---:|---:|
| rename only | no | yes | no | no | yes |
| small mutation | no | yes | no | no | yes |
| complete replacement | no | yes | no | no | yes |
| fork | no | yes | no | no | yes |
| merge | no | yes | no | no | yes |
| independent convergence | yes | no | no | no | yes |
| divergence | no | yes | no | no | yes |
| alias relation | yes | no | yes | no | yes |
| equivalence relation | yes | no | no | yes | yes |

The convergence case is the critical counterexample: identical content does not provide
a historical path between two independent origins. Conversely, a complete replacement
has a provenance path but no content-based reason to infer continuity. The result is that
continuity can be represented relationally, but it is not discovered by any candidate in
this phase. That failure is preserved rather than converted into an ID primitive.

## E-graph verdict

The provisional answer is `C`: reduce the useful mechanism to a simpler generic rewrite
layer.

- v2: e-graph was dominated by `content_dag` on every repetition point;
- v3: moving rewrite above either substrate removes e-graph storage from D but does not
  make its evaluation Pareto-competitive;
- v3: the reduced tree-rewrite mechanism reaches fidelity 1.0 on all 36 reduction points
  and is faster than the full e-graph mechanism on the same equivalence workloads;
- v3: no new MAT-SI primitive is claimed.

The e-graph is therefore not retained as a universal representation. It remains a useful
comparison mechanism for equality workloads, but current evidence favors the generic
rewrite mechanism without preserving e-classes. Larger alternative-rich workloads would
be needed before concluding that e-graphs are unnecessary for all equivalence problems.

A failure is preserved: unioning a term with a rewritten descendant can create an
e-class cycle for the current minimal extractor. The v3 equivalence experiment keeps the
e-graph proof but uses the already-rewritten representative rather than hiding the
extractor limitation.

## Host language leakage

The audit identifies these remaining semantic concentrations in Python:

- encode/decode and canonicalization for all candidates;
- direct arithmetic, list/string operations, and transformation orchestration;
- e-graph matching, substitution, rebuild, and extraction;
- continuity reachability and interpretation;
- measurement, storage accounting, and provenance judgment.

The strongest reduction is the represented-rule VM: rule structure is in U and controls
execution, but the VM vocabulary remains host semantics. The continuity analyzer is the
opposite result: relations are in U, while continuity meaning remains host judgment.

## Smallest surviving concept set

The current evidence preserves only these concepts as candidates for further Phase 1
work:

```text
value
represented rule/program
evaluator that reads represented rules
transformation and composition as U
history, cost, and provenance as U
relation/path for continuity evidence
```

No final separation is assumed. The next Phase 1 attack should reduce the host VM
vocabulary and test whether continuity relations can acquire executable semantics without
introducing a stable identity primitive.

## Reproduction

```text
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -v
python -m matsi.benchmark_v3 --json-out results/phase1-v3-results.json
```

Raw results are in `results/phase1-v3-results.json`. The v2 raw artifacts remain in the
repository for comparison.
