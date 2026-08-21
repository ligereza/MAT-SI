# Agent 1 — Representation discovery economics

This block starts at `f3f8816ad9e49c95668ef5030354d169d983e1a7` on
`research/agent1-continuation`. It uses only finite mathematical fixtures; no
new corpus was added and `main` was not touched.

## Central distinction

For one representation `R` and a candidate transformation `T`, the experiment
separates:

1. existence: `T(R)` is a useful representation;
2. discovery: identify that `T` is available or worth trying;
3. construction: materialize `T(R)`;
4. exploitation: solve the downstream task in `T(R)`.

For `n` uses, in an explicitly selected resource dimension,

```text
C_direct(n)       = n B
C_transform(n)    = D + n A       reusable transform
C_transform(n)    = n(D + A)      non-reusable transform
D                 = C_discover + C_apply
```

`B` is the direct per-use cost and `A` is the post-transform per-use cost.
The implementation retains all cost dimensions as vectors. A selector must
declare one resource, such as `time`, before making a strict route comparison;
there is no hidden universal exchange rate between time, memory, queries, or
samples.

## Exact amortization result

If the transform is reusable and `B > A`, the least positive integer with a
strict end-to-end advantage is

```text
n* = floor(D / (B - A)) + 1.
```

This follows directly from `D + nA < nB`, with strict inequality preserved.
If `B <= A`, no positive reuse count repays a non-negative acquisition cost.
If `D = 0` and `B > A`, `n* = 1`. For a non-reusable transformation there is
no amortization: the acquisition term is paid on every use.

The function `exact_break_even_count()` computes this with rational arithmetic.

## Executable object and selector

`TransformationCandidate` records only information consumed by the selector:

- structural property/effect and resulting regime;
- discovery, application, and post-transform cost vectors;
- whether discovery is already known;
- explicit reuse scope and reusability claim;
- task, decision, and loss preservation;
- approximation degradation and discovery-complexity annotation.

`select_representation_route()` compares `SOLVE_DIRECT` with an explicit finite
portfolio. Its possible transformation decisions are `DISCOVER_AND_APPLY` or
`APPLY_KNOWN`. The result includes:

- total vector costs for the requested reuse horizon;
- one-shot and horizon advantages;
- exact break-even count;
- structural regime change;
- preservation certificate;
- pruning certificates.

The selector has no default weighted score. It refuses a missing resource
policy. It can therefore say `SOLVE_DIRECT` even when a structurally easier
representation exists.

The existing `choose_next_computation()` and
`solve_sequential_meta_decision()` can consume a discovery action through
`transformation_discovery_probe()`. This is an adapter, not a second meta-solver:
the existing probe channel supplies decision value, while the route selector
accounts for discovery + construction + exploitation.

## Required fixtures

The generated result is in
`results/agent1-representation-discovery-economics-v1.json`.

### Negative: easy after transformation, direct is better now

```text
B = 10, D = 8 + 3 = 11, A = 1
```

For one use, direct costs `10` and the transformed route costs `12`, so the
selector returns `SOLVE_DIRECT`. The transformed regime is still cheaper per
future use, with `n* = 2`; this is not a contradiction, but the required
counterexample to “the prettier representation is automatically preferable.”

### Positive: end-to-end one-shot advantage

The candidate is derived from the existing exact task-sufficient quotient
certificate. The representation changes `GENERAL_SET_COVER` to
`UNIQUE_OPTIMUM` while preserving the task decision. With

```text
B = 10, discovery = 2, apply = 1, A = 3,
```

the transformed route costs `6` and is selected.

### Amortized-only advantage

```text
B = 10, D = 5 + 3 = 8, A = 4
```

At `n=1`, direct costs `10` and compilation costs `12`; at `n=2`, direct costs
`20` and compilation costs `16`. The exact break-even is `n*=2`. The returned
certificate changes from `SOLVE_DIRECT` to `DISCOVER_AND_APPLY` exactly there.

### Preservation counterexample

A fast candidate with `risk_degradation = 1/10` and
`task_preserved = false` is pruned under an exact policy. No time-versus-risk
exchange rate is invented. A downstream policy may explicitly permit an
approximation, but that is a different decision problem.

## Pruning rules justified in the finite selector

- `TASK_NOT_PRESERVED`, `DECISION_NOT_PRESERVED`, or degradation over the
  allowed policy: the candidate is not an admissible exact route.
- acquisition or total-resource constraint: the route violates an explicit
  budget.
- `NO_DOWNSTREAM_GAIN`: same structural regime and no lower selected-resource
  exploitation cost; non-negative acquisition cannot make it better.
- `SAME_REGIME_DOMINATED`: within the feasible portfolio, a same-regime route
  with equal preservation and strictly lower total cost at the requested
  horizon removes the other route.

These are policy-relative pruning rules. They are not a claim that one resource
dominates every other resource.

## Difficulty: what moved and what did not

For an explicit finite candidate portfolio, evaluating route costs, selecting
the minimum under one declared resource, and computing `n*` are polynomial or
`O(1)` in the relevant finite input sizes. This is the complexity of selection
after candidates and costs are supplied.

The harder task is discovery. The existing exact task-sufficient transform
contains a Set-Cover reduction, so finding an optimal exact quotient is
NP-hard even though evaluating a supplied candidate is easy. The existing
sequential meta-solver remains exponential in the number of probes/reachable
posterior states. No PSPACE claim is made.

Thus downstream tractability does not imply end-to-end tractability: hardness
can move into discovering or constructing the representation.

## Generality test outside `Opt(r)`

`evaluate_connected_component_transformation()` uses no loss matrix and no
posterior optimal-action intersection. Its underlying task is undirected graph
connectivity:

```text
unindexed graph + query  ->  BFS/DFS per query
connected-component index -> component-label lookup
```

For the fixture with components `{0,1,2}` and `{3,4}`, direct per-query cost is
`11`, component construction costs `11 + 5`, and indexed queries cost `1`.
For three queries, direct cost is `33`, transformed cost is `19`; the exact
break-even is two queries. The query answers are unchanged. This is a new
structural object, not a forced Bayesian encoding.

Verdict: `GENERALIZES_WITH_NEW_OBJECT`. The economics of acquisition and reuse
transfers cleanly, while the structural analyzer must be supplied by the
domain; MAT-SI has not proved a universal representation language.

## Literature audit and removed novelty

| Theory | Classification | What is imported | MAT-SI relation |
|---|---|---|---|
| Knowledge compilation map, Darwiche–Marquis | `ESTABLISHED_THEORY` | offline compilation trades succinctness against polynomial query/transform classes | closest analogue; this block makes route selection itself explicit |
| Kernelization / parameterized preprocessing, Bodlaender–Jansen–Kratsch | `FORMAL_SPECIAL_CASE` | preprocessing can reduce an equivalent instance to a parameter-bounded kernel, with conditional lower bounds | covers a size/parameter case, not every structural transform |
| Fortnow–Santhanam incompressibility | `ESTABLISHED_LOWER_BOUND` | broad efficient compression would imply unlikely complexity collapse | supports not treating compact existence as cheap discovery |
| Pătraşcu–Demaine cell-probe tradeoffs | `ESTABLISHED_THEORY` | preprocessing/update/query resources trade off under an explicit model | motivates retaining resource vectors and reuse scope |
| Rice algorithm selection | `ESTABLISHED_THEORY` | select an algorithm from instance/features and performance criterion | MAT-SI adds discovery/construction cost for the representation route |
| Russell–Wefald value of computation | `IMPORTED_THEORY` | pay for computation only when expected downstream value justifies it | existing MAT-SI probe solver is a finite instantiation |

The false novelty removed here is “MAT-SI invented paying for preprocessing or
feature discovery.” Those are established concerns. The concrete surviving
capability is an auditable finite selector that makes representation discovery,
construction, exploitation, and reuse part of one explicit route certificate.

## Status

- `PROVED`: exact decomposition and strict integer break-even theorem;
  preservation pruning for exact routes; polynomial selection after an explicit
  finite portfolio is supplied.
- `KNOWN_RESULT`: exact task-sufficient discovery is NP-hard by the existing
  Set-Cover reduction; knowledge compilation and kernelization are established
  neighboring theories.
- `DISPROVED`: “if the transformed representation is easier, transforming is
  preferable.”
- `CONJECTURE`: none required for this milestone.
- `UNKNOWN`: general discovery complexity for arbitrary representation
  languages, and any universal transfer of a structural analyzer beyond the
  supplied finite examples.

The block stops here. No Pareto theory, product work, corpus expansion, or
additional meta-layer is opened.
