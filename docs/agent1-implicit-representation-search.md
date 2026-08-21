# Agent 1 — Implicit representation search

This block starts at `19060209153d425969f8ecc67b0e175cc7916691` on
`research/agent1-continuation`. It adds no corpus, does not reopen Phase 4,
and does not change `main`.

## What changed

The previous selector received `TransformationCandidate` objects explicitly.
This block instead supplies lazy generators. A generator consumes a current
representation state and produces zero or more transitions. Every transition
contains:

- a precondition witness;
- a target with canonical task-relative identity;
- a non-negative acquisition cost;
- a preservation status and certificate;
- a structural effect;
- executable operation counts.

The planner performs:

```text
generate -> verify -> search -> prune -> compose -> stop
```

The implementation is in
[representation_search.py](C:/IA/MATH/src/matsi/representation_search.py).

## Representation-search object

For a route `p` and reuse horizon `n`:

```text
p = (R0, g1, R1, ..., gk, Rk)
D(p) = sum transition costs
A(p) = terminal solve cost per use in Rk
C(p,n) = D(p) + n A(p)
```

The direct route is always the initial incumbent:

```text
C_direct(n) = n B
```

The planner never searches merely because a representation looks attractive;
it must beat that incumbent under the explicitly selected resource.

## Explicit graph result

If the representation graph is explicit, all transition costs are
non-negative, terminal solve costs are non-negative, and preservation-invalid
states/edges are removed, add a virtual goal edge from each representation `R`
with cost `n A(R)`. Then the route objective is exactly the shortest-path cost
from `R0` to the goal. The proof is direct: every path cost is the sum of its
one-time transformation costs plus its terminal edge, and every complete route
has exactly one such terminal edge.

The finite fixture returns:

```text
R0 -> R1 -> R2
D = 5 + 1 = 6
A = 1
n = 2
C = 8
```

The direct incumbent is `20`; the result is `EXACT_OPTIMUM` with gap `0`.
This imports shortest-path theory; MAT-SI does not claim to have invented it.

## Exact and bounded search

`search_representation_routes()` is a lazy best-first/A*-style search. The
state lower bound is admissible under the explicit assumption that every
descendant terminal solve cost is at least the state lower bound. It retains:

- generated and expanded states;
- duplicate canonical states;
- invalid transitions and preservation failures;
- incumbent updates;
- frontier lower bound;
- optimality gap;
- planner cost separately from route cost.

With no budget, exhaustion or lower-bound domination gives `EXACT_OPTIMUM` or
`NO_BETTER_ROUTE`. With a fixed expansion budget, the result is
`BOUNDED_INCUMBENT`; it never relabels that result as globally optimal.

The bounded fixture spends one expansion and returns:

```text
incumbent = 100
frontier lower bound = 2
gap = 98
status = BOUNDED_INCUMBENT
```

The route may be improved by unexplored descendants, but no unsupported claim
is made about the optimum.

## Admissible lower bound experiment

A three-level branching tree contains `39` generated bad transitions. Direct
solve costs `5`; every descendant has terminal lower bound `100`.

- uninformed search: `40` expanded states;
- lower-bound search: `1` expanded state and `3` generated transitions;
- both return `NO_BETTER_ROUTE` and the same direct optimum.

This is evidence for the finite heuristic certificate only. It is not a
general performance theorem for arbitrary representation spaces.

## Greedy counterexample and composition

Two first transformations are available:

```text
cheap_enabler -> intermediate A: local cost 91
fast_local    -> intermediate B: local cost 15
```

Greedy one-step selection chooses `B`. However, only `A` enables the second
transformation:

```text
G0 -> A -> A2
1  + 1 + 1 = 3
```

The exact search returns `G0 → A → A2`, while the greedy choice is globally
worse. This falsifies “choose the best current structural regime.”

## Quotient regression bridge

The planner does not receive the optimal quotient. It starts from singleton
blocks and lazily generates pairwise merges only when the union has a common
Bayes-optimal action. Partition identity is canonical sorted block syntax.

For the small fixture, the search discovers:

```text
((0),(1),(2),(3))
 -> ((0,1),(2),(3))
 -> ((0,1,2),(3))
```

The terminal block count is `2`, matching the existing exact
`task_sufficient_quotient()` result. This is a bridge experiment, not an
attempt to replace the specialized Set-Cover solver.

## Non-Bayesian directed reachability

The generality test uses a directed graph and repeated queries
`reachable(u,v)`. It does not use a loss matrix.

Available lazy generators are:

```text
RAW_GRAPH
  -> SCC_CONDENSATION_DAG
  -> SCC_REACHABILITY_INDEX

RAW_GRAPH
  -> FULL_REACHABILITY_CLOSURE
```

The SCC and closure computations are real algorithms. Their transitions count
nodes, edges, SCC operations, and closure operations. Each target checks the
query answers against raw reachability before becoming admissible.

For one query, direct BFS wins. For ten repeated queries:

```text
direct                         = 130
RAW -> SCC -> CLOSURE          = 69
RAW -> SCC                     = 76
RAW -> FULL_CLOSURE            = 209
```

The two-step route wins every one-step route and preserves all answers. This
is a finite demonstration that route composition can change the algorithm
family, not merely shorten a representation.

Verdict: `GENERALIZES_WITH_NEW_STRUCTURE`. Route economics, preservation,
composition, canonical identity and reuse transfer. The structural analyzer
itself remains domain-specific.

## Reuse-horizon frontier

For complete reusable routes, a same-preservation route `p` with

```text
D_p <= D_q and A_p <= A_q
```

and at least one strict inequality dominates `q` for every `n >= 1`. The proof
is subtracting the two affine costs.

The converse is false for integer horizons. The routes

```text
direct: D=0, A=10
middle: D=3, A=8
fast:   D=6, A=0
```

are all non-dominated, but `fast` is optimal for every integer `n >= 1`;
`direct` and `middle` never win. Thus a Pareto frontier is not itself the
reuse-horizon lower envelope.

## Preservation and identity

Exact search admits only `VERIFIED_EXACT` transitions. Unverified,
tolerance-only, invalid, or failed transitions are recorded and rejected.
Approximate composition is intentionally not opened here.

State identity is explicit and task-relative. It is not Python object identity,
and syntactic equality is not claimed to equal semantic equality beyond each
fixture's canonical identity definition.

## Complexity and hardness

- explicit non-negative route graph: polynomial shortest path;
- finite generated search: exponential in the reachable implicit state space
  in the worst case;
- finite route-frontier calculation: polynomial in the supplied route set;
- quotient merge discovery: NP-hard in the existing Set-Cover reduction;
- bounded search: produces a sound incumbent/lower-bound certificate, not a
  global optimum unless the gap is zero.

The hardness distinction is explicit: shortest path over a supplied graph is
not the same problem as discovering the graph through generators.

The compatible-merge generator embeds the existing minimum task-quotient
problem. Therefore a polynomial exact optimizer for that implicit language
would solve the already established NP-hard quotient problem. This is a
reduction of the bridge language, not a universal hardness claim for all
representation languages.

## Literature audit

| Theory | Classification | Relation |
|---|---|---|
| Dijkstra shortest path | `ESTABLISHED_THEORY` | explicit graph special case; [primary source](https://ir.cwi.nl/pub/23612) |
| A* admissible search | `ESTABLISHED_THEORY` | terminal lower bound heuristic; [Hart–Nilsson–Raphael](https://www.cs.auckland.ac.nz/courses/compsci709s2c/resources/Mike.d/astarNilsson.pdf) |
| STRIPS/planning | `FORMAL_ANALOGY` | preconditions/effects resemble planning; [SRI publication record](https://ai.stanford.edu/~nilsson/publications.html) |
| equality saturation | `SPECIALIZED_REPRESENTATION_SEARCH` | rewrite alternatives plus extraction; [egg paper](https://homes.cs.washington.edu/~cnandi/docs/popl21-cr.pdf) |
| knowledge compilation | `ESTABLISHED_THEORY` | offline representation and online reuse; [Darwiche–Marquis](https://www.cril.univ-artois.fr/~marquis/darwiche-marquis-jair02.pdf) |
| superoptimization | `ANALOGY` | compositional search for cheaper terminal programs; [Massalin](https://www.brinckerhoff.org/clements/2214-csc530/Files/massalin-1987.pdf) |
| index/physical design | `KNOWN_RESULT` | workload-dependent construction; [Bananno–Maio–Tiberio](https://doi.org/10.1093/comjnl/28.4.398) |
| multiobjective shortest path | `FORMAL_ANALOGY` | frontier mathematics exists; [network-model formulation](https://arxiv.org/abs/1802.08637) |

The false novelty removed is “MAT-SI invented shortest-path search, A*,
planning, or compilation.” The surviving contribution is a finite auditable
instantiation where transformation generators, preservation, route economics,
reuse, direct execution, and search certificates meet.

## Epistemic status

- `PROVED`: explicit-graph reduction to shortest path; same-preservation
  `(D,A)` dominance; exact lower-bound stopping under its stated assumption.
- `KNOWN_RESULT`: implicit compatible-merge discovery inherits the existing
  Set-Cover hardness; general planning/search spaces can be exponential.
- `VERIFIED_FINITE_CASE`: all generated quotient and directed-graph fixtures.
- `COUNTEREXAMPLE`: greedy local choice and non-dominated-but-never-optimal
  route.
- `UNKNOWN`: universal implicit representation language, universal admissible
  heuristic, and general preservation composition outside supplied domains.

## Artifact

The compact result is in
[agent1-implicit-representation-search-v1.json](C:/IA/MATH/results/agent1-implicit-representation-search-v1.json).

The milestone stops after this block; it does not create a planner-of-planners
or another meta-layer.
