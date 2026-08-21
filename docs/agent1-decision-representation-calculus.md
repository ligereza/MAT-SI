# MAT-SI Agent 1 — Decision Representation Calculus v1

This block starts from the previous result but does not reopen Phase 4A. The
four-row observation is used only as a regression fact: a representation is
not good or bad in isolation; it is useful relative to the decisions it
supports.

## Mathematical object

For finite world states `Y` and representation symbols `R`, an experiment is a
row-stochastic channel

`E[y,r] = P(R=r | Y=y)`.

A decision task is `D=(A,L)` with finite actions `A` and arbitrary finite loss
matrix `L[y,a]`. Given prior `pi`, the engine computes

`V(E,D,pi) = min_delta sum_y,r pi[y] E[y,r] L[y,delta(r)]`.

The implementation returns exact rational posteriors, all Bayes-optimal action
ties for every symbol, a decoder/policy, and exact Bayes risk. Zero-mass
symbols are retained and marked as having every action tied; they do not
contribute to risk.

## Blackwell comparison

For experiments with the same world-state space, `E1` dominates `E2` when a
row-stochastic channel `K` exists such that

`E1 K = E2`.

The solver returns the requested classification set:

* `DOMINATES`: a witness `K` exists from the first experiment to the second;
* `DOMINATED_BY`: only the reverse witness exists;
* `EQUIVALENT`: witnesses exist in both directions;
* `INCOMPARABLE`: neither direction has a stochastic garbling witness;
* `INVALID`: dimensions or stochastic constraints are invalid.

The feasibility problem is a rational linear program. The current
dependency-free implementation solves small cases by exact vertex enumeration,
returning `K`, residual, and a certificate. Standard LP solvers provide the
polynomial-time formulation; vertex enumeration is intentionally reported as
the implementation's small-instance limitation.

Fixtures distinguish identity, signal permutation, strict garbling, a useless
experiment, and two incomparable experiments that separate different pairs of
three world states.

## Deficiency

The directed finite deficiency is implemented as

`delta(E1,E2) = min_K max_y TV(E1_y K, E2_y)`.

Absolute residual variables produce an LP and an auditable approximate witness
channel. For binary target symbols, the code eliminates the second channel
column and all cell-wise slacks: TV is exactly the absolute residual of one
cell. This reduction changes the solver from a large generic vertex search to
`source_signal_count + 1` variables without changing the objective.

The symmetric reported quantity is

`Delta(E1,E2) = max(delta(E1,E2), delta(E2,E1))`.

An exact Blackwell witness is reused as a zero-deficiency certificate. The
compiler reports the two directions explicitly. For a deterministic quotient,
forward simulation loss is zero because the quotient channel is itself a
witness; reverse reconstruction can still be positive (it is `1/18` in the
three-signal fixture). The chain certificate uses the triangle inequality: the
directed deficiency of a composed path is bounded by the sum of directed step
deficiencies.

## Task-sufficient quotient

Let a deterministic quotient partition representation symbols into blocks.
For a block `B`, the quotient preserves the original Bayes risk for the task
exactly iff

`intersection_{r in B} Opt(r) != empty`,

where `Opt(r)` is the set of Bayes-optimal actions at symbol `r`.

Proof: the quotient's block risk is `min_a sum_{r in B} c(r,a)`, while the
uncompressed risk is `sum_{r in B} min_a c(r,a)`. The latter is always no
greater. Equality holds exactly when one action attains every per-symbol
minimum, which is the non-empty intersection condition.

Therefore the minimum quotient is exactly a minimum set cover of the signal
universe by action-compatibility sets

`C_a = {r : a in Opt(r)}`.

The solver uses bitmask dynamic programming and reconstructs a partition and
common-action witness. This is a real combinatorial reduction. The executable
identity-experiment/loss construction reduces Set Cover in polynomial time:
each universe element is a source symbol and each subset is an action with
zero loss exactly on its members. A risk-zero quotient with at most `k` blocks
exists iff the Set-Cover instance has a cover of size at most `k`. A partition
and one common action per block is a polynomial certificate, so the decision
problem is NP-complete.

When every optimal-action hyperedge has arity at most two, the problem
specializes to Vertex Cover. Singleton hyperedges force vertices and each
two-action ambiguity is an edge. The exact brancher uses this structure; its
worst case remains exponential because Vertex Cover is NP-hard.

`analyze_decision_ambiguity` exposes hyperedges, action coverage, components,
equivalent/dominated actions, and a lower bound. `adaptive_task_quotient`
selects direct grouping, degree-2 branching, exact bitmask cover, or a bounded
greedy fallback from that profile.

A compact synthetic suite exercises unique optima, degree-2 cycles,
decomposable components, symmetry, dense overlap, and a larger general case.
It records symbols, actions, ambiguity, selected regime/algorithm, explored
nodes, runtime, bounds, and whether an exact certificate was obtained. These
are controlled mathematical fixtures, not a new corpus.

## Multi-task and decision spectrum

For tasks `D_1,...,D_m`, a quotient block is valid iff it has a common optimal
action for every task. Equivalently, cover signals by joint action tuples
`(a_1,...,a_m)`. Adding a task can only add constraints, so the minimum
multi-task quotient cannot be smaller than any single-task quotient.

The decision spectrum reports the minimum quotient size and preserved risk for
each task. In the finite fixture, binary classification requires two symbols,
while an asymmetric loss can be preserved with one symbol. The same experiment
therefore has task-dependent structural complexity.

Mutual information does not replace this analysis. With three equiprobable
world states and a binary action task (action `0` correct only for state `0`),
one experiment has `I(Y;R)=0.9183` bits but Bayes risk `1/3`; a task-targeted
experiment has only `0.4791` bits but Bayes risk `1/10`. The higher-information
experiment is worse for the specified decision. This is a constructed finite
counterexample, not a claim about mutual information being useless in every
task.

## Epsilon compression

For small spaces the solver traverses canonical set partitions with an
incumbent upper bound and prunes candidates with no fewer blocks. It keeps the
smallest partition satisfying

`V(E',D_i,pi) - V(E,D_i,pi) <= epsilon_i`

for every task. It returns risk deltas, quotient channel, feasibility count,
and lower/upper bounds. Exact runs close the gap to zero; resource-limited
runs retain the feasible upper bound and expose the remaining gap. The
worst-case search is `O(Bell(|R|))` partitions. The greedy fallback keeps the
standard Set-Cover guarantee `H_|R| * OPT`; its observed upper/lower ratio is
reported separately and is not presented as the theoretical ratio.

## Separation witnesses and stochastic compression

For the Blackwell-incomparable fixture, a bounded rational grid search finds a
decision witness in each direction. This demonstrates concrete task-wise
separation without replacing the garbling criterion; general separating-loss
extraction remains a distinct convex-analysis problem.

Deterministic and stochastic compression were compared on exact finite grids.
For zero tolerance there is no size advantage from randomization: if a
stochastic compressor followed by a decoder has zero excess risk, every output
used with positive probability at a source symbol uses an action optimal there.
Selecting one such output per source symbol yields a deterministic quotient
with no more outputs. Positive-tolerance multi-task frontiers were only
searched on finite grids and remain `UNKNOWN` in general.

## Transformations and identification

Each representation transition records task risk changes, Blackwell relation,
deficiency, and preserved/lost tasks. A path records the sum-of-deficiencies
upper bound and whether every step has an exact Blackwell witness.

Identification assumptions are an explicit interface. The compiler can report
that a decision is `IDENTIFIED` under supplied assumptions such as labels,
partial labels, calibration, symmetries, monotonicity, or structural
constraints; missing assumptions remain missing. No decoder is inferred from
an unlabeled representation by fiat.

## Complexity status

| Problem | Exact formulation | Current status |
|---|---|---|
| Bayes value | posterior/action minimum | polynomial arithmetic enumeration |
| Blackwell dominance | LP feasibility for `K` | polynomial formulation; exact small LP implementation |
| Directed deficiency | LP with TV residuals | polynomial formulation; exact small LP implementation |
| Single-task quotient | minimum set cover over `C_a` | NP-complete decision problem; exact small solver |
| Degree-2 quotient | Vertex Cover on ambiguity graph | exact branch-and-bound; NP-hard |
| Multi-task quotient | set cover over joint action tuples | exact bitmask solver; exponential in signals/tasks |
| Epsilon compression | constrained set partitions | branch-and-bound bounds; `Bell(m)` worst case; NP-hard at `epsilon=0` |
| Stochastic compression | finite rational channel grid | no zero-tolerance size advantage; positive-epsilon multi-task case `UNKNOWN` |

## References used

* David Blackwell, “Equivalent Comparisons of Experiments” (1953),
  [Annals of Mathematical Statistics](https://projecteuclid.org/journals/annals-of-mathematical-statistics/volume-24/issue-2/Equivalent-Comparisons-of-Experiments/10.1214/aoms/1177729032.full).
* Lucien Le Cam, “Sufficiency and Approximate Sufficiency” (1964),
  [Annals of Mathematical Statistics](https://projecteuclid.org/journals/annals-of-mathematical-statistics/volume-35/issue-4/Sufficiency-and-Approximate-Sufficiency/10.1214/aoms/1177700372.full).

These references changed the implemented objects: Blackwell supplies the
garbling equivalence and Le Cam supplies directed approximate simulation and
the symmetric deficiency distance. They are not being used as decorative
bibliography.
