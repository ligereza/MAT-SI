# Phase 1 Protocol v3

## Objective

Protocol v3 tests whether v2 compared two categories as if they were one:

```text
S = structural substrate
E = evaluation/transformation mechanism
I = identity/continuity evidence
```

This is an experimental factorization, not a proposed architecture. The combinations
are measured and can be rejected independently. No final kernel is selected and Phase 2
remains closed.

## Part A: separated axes

Structural substrates:

- `atom_pair`;
- `content_dag`.

Evaluation mechanisms:

- `direct_evaluator`, which decodes, applies the common operation, and re-encodes;
- `rewrite_equality`, which uses the e-graph mechanism for ordinary transforms and for
  `reverse(reverse(x)) -> x` equivalence, then stores the result in the substrate;
- `reduced_tree_rewrite`, a comparison mechanism using the same generic rules without
  e-classes.

The primary matrix measures all four `S x E` combinations over repetition, shared
graph, and temporal branching cases at 10, 100, and 1000 elements. It reports substrate
bytes/sharing/query separately from evaluator time, memory, allocations, mechanism
work, and fidelity. The `double_reverse` workload is included because a rewrite layer
must be tested on equivalence, not only on ordinary host operations.

## Part B: represented execution

The minimal represented-rule evaluator is a fixed stack machine with the instruction
vocabulary:

```text
get, const, add, mul, set, return
```

`rule_A` and `rule_B` are ordinary dictionaries and instruction lists. The experiment
checks:

1. `rule_A` on `{"value": 3}` returns 4;
2. changing only represented rule data to `rule_B` returns 6;
3. a represented modifier rule changes `rule_A` into `rule_B`;
4. the modified rule then returns 6;
5. the evaluator source hash is unchanged.

The same evaluator runs against external input and against a represented rule object.
This is not full self-hosting: the instruction vocabulary and VM loop remain host code.

## Part C: transformations as U

The experiment creates one ordinary-data universe containing:

```text
value, rules, transformations, composition, history, cost, provenance
```

Two represented transformations compose as `T2(T1(x))`, with `T1` adding one and `T2`
doubling a record field. The composition itself is represented, round-tripped, and
executed. No privileged metadata class is used in that value.

## Part D: continuity without a stable ID

The continuity corpus uses sequence positions such as `x0` and `x1` only as relation
endpoints. It does not inject `object_id`, `stable_id`, or an equivalent field. Cases
cover rename, small mutation, complete replacement, fork, merge, independent
convergence, divergence, alias relation, and explicit equivalence relation.

The harness keeps these observables distinct:

- content equality;
- historical path availability;
- alias relation;
- equivalence relation;
- provenance completeness.

The analyzer does not convert a path into identity. It records whether continuity
evidence can be represented as a relation/path and preserves the failure that no
candidate discovers continuity semantics from it.

## Part E: e-graph test

The e-graph is tested as:

1. a universal representation, as in v2;
2. an evaluator layer over each structural substrate;
3. a rewrite mechanism reduced to a tree-rewrite loop without e-classes.

The decision is evidence-based and provisional. If the simpler tree rewrite preserves
fidelity and the e-graph is not Pareto-competitive in the tested workloads, v3 prefers
reducing the useful mechanism rather than preserving the implementation. This does not
claim that equality saturation is never useful for larger equivalence workloads.

## Part F: host leakage

Every candidate and v3 mechanism receives a semantic audit with three labels:

- `HOST`: semantic work performed by Python or a host library;
- `REPRESENTED`: structure or rules carried in U;
- `DERIVED`: results computed from represented data.

The objective is to reduce `HOST` semantics over time, not to pretend that Python
infrastructure has disappeared. Measurement, storage accounting, and continuity
interpretation remain explicitly identified as host/derived work.

## Gate

The Phase 1 gate stays closed until there is evidence about both:

```text
WHAT THINGS ARE   -> structural representation and ordinary data
HOW THINGS CHANGE -> represented rules, transformations, histories, and continuity evidence
```

Protocol v3 does not select a kernel, merge S and E, or advance to Phase 2.
