# Agent 1 — Structural Probes and Meta-Decision

This block starts at `0274ab2` on `research/agent1-continuation`. It does not
reopen Phase 4, add a corpus, or change the existing ambiguity-complexity
calculus.

## New finite object

Let `Theta` be finite world/structural states, `pi` a prior, `A` the finite
set of downstream algorithms/actions, and `L(theta,a)` their loss. A probe
`q` is a finite channel `Q_q(o | theta)` plus a vector-valued resource cost
`C(q)`.

The current risk is

`R(pi) = min_a sum_theta pi(theta) L(theta,a)`.

The probe risk and gross decision value are

`R_q(pi) = sum_o P(o | pi,q) min_a E[L(theta,a) | o,q]`,

`DV(q;pi) = R(pi) - R_q(pi)`.

The implementation reports `decision_value`, `information_value_bits`, and
each cost dimension separately. It does not introduce an implicit weighted
utility.

## Zero-value theorem

For every positive-probability outcome `o`, let `Opt_q(o)` be the set of
Bayes-optimal downstream actions under the posterior after `o`. Then

`DV(q;pi) = 0` iff `intersection_o Opt_q(o) != emptyset`,

where the intersection is over positive-probability outcomes.

Proof: write `c_o(a)` for the joint prior-weighted loss of action `a` on
outcome `o`. The current risk is `min_a sum_o c_o(a)` and the post-probe risk
is `sum_o min_a c_o(a)`. The latter is no larger. Equality holds exactly when
one action attaining the global minimum also attains every positive-outcome
minimum. This is the same finite min-sum equality used by task-sufficient
quotients: a block can be merged iff its symbols share a common optimal action.

This is a common theorem, but not a full duality theorem: compression removes
distinctions while a probe reveals them, and both are evaluated by the same
min-sum equality. Their feasible objects and optimization directions differ.

## Blackwell and meta-cost

If `q1` Blackwell-dominates `q2`, then every finite downstream task satisfies
`R_q1 <= R_q2`, hence `DV(q1) >= DV(q2)` before resource costs. This is an
informativeness order, not a complete meta-action preference. A more expensive
dominant probe may be rejected by an explicit time/memory budget.

The selector applies only theory-backed pruning:

* zero decision value → prune, by the theorem above;
* Blackwell-dominated probe with no cost advantage → prune under the explicit
  decision-value-under-constraints policy;
* resource-infeasible probe → prune by the supplied constraint;
* identical posterior action partitions remain structurally redundant.

`structural_analysis_cost_model()` records the dependency graph from a
property to its acquisition cost, enabled algorithm, and possible decision
improvement. Exact quotient and deficiency analysis are not free assumptions:
their current exact implementations are exponential finite solvers over
polynomial LP/set-cover formulations. Posterior/optimal-action extraction and
component computation are polynomial for explicit finite inputs.

## Exact meta-solvers

`evaluate_probe`, `analyze_structural_probe`, `compare_probes`, and
`choose_next_computation` expose one-step meta-decisions. The latter keeps a
vector cost and uses an explicit resource-constraint policy; without such a
policy it does not pretend that time and memory have a universal exchange
rate.

`solve_sequential_meta_decision` is an exact finite recursion over belief states
and remaining probes. It includes `execute_now` as a terminal action and uses a
caller-supplied time-cost weight only for the sequential scalar policy. This
is a finite metalevel-MDP/rational-metareasoning instance, not a new general
metareasoning theory. Its current complexity is exponential in the number of
available probes and reachable posterior states.

For the new finite problems: fixed-probe evaluation and zero-value checking
are polynomial in the explicit channel/task size; selection from an explicit
finite probe portfolio is polynomial under a fixed constraint policy; the
current exact Blackwell subroutine is exponential because it enumerates finite
LP vertices; sequential selection is exponential in reachable belief states;
and selecting a representation transform is NP-hard when exact
task-sufficient quotient construction is part of the candidate operation.
No PSPACE claim is made for this finite implementation.

## Controlled results

The executable fixtures establish:

1. positive mutual information with zero decision value when all posterior
   outcomes retain a common optimal action;
2. zero mutual information with zero decision value for the fixed task;
3. a higher-MI probe with lower decision value than a lower-MI targeted probe;
4. equal-MI probes with different decision values for different tasks;
5. a Blackwell-dominant identity probe rejected when its time cost violates the
   explicit budget, while a weaker affordable probe is selected;
6. a sequential exact policy that reveals the state and then executes rather
   than paying for a now-useless second probe;
7. a task-sufficient representation transform changing the selected regime from
   `GENERAL_SET_COVER` to `UNIQUE_OPTIMUM` while preserving Bayes risk.

The last example is a decision-equivalent structural transformation, not a
claim that a toy instance separates standard complexity classes.

## Literature audit matrix

| Claim | Primary source | Status | Exact result | MAT-SI relation |
|---|---|---|---|---|
| Rice algorithm selection | [Rice, 1976](https://doi.org/10.1016/S0065-2458(08)60520-3) | ESTABLISHED THEORY | problem/algorithm/performance spaces and a selection mapping; the basic model is one-shot and does not itself define sequential probes, feature-cost accounting, or representation transformations | MAT-SI adds explicit structural probes and acquisition cost |
| Value of computation / rational metareasoning | [Russell–Wefald, 1991](https://doi.org/10.1016/0004-3702(91)90015-C) | ESTABLISHED THEORY | choose computations by expected downstream utility and computation cost | MAT-SI instantiates this with finite statistical probes |
| Metalevel MDP | [Hay et al., 2012](https://arxiv.org/abs/1207.5879) | ESTABLISHED THEORY | sequential computation selection over belief states with a stop action | the exact recursive solver is a finite special case |
| Succinct/representation-dependent complexity | [Galperin–Wigderson, 1983](https://www.math.ias.edu/~avi/PUBLICATIONS/ABSTRACT/gw84.pdf) | ESTABLISHED THEORY | changing the encoding can raise graph-problem complexity | validates separating object, encoding, representation, and algorithm |
| Knowledge compilation | [Darwiche–Marquis, 2002](https://www.cril.univ-artois.fr/~marquis/darwiche-marquis-jair02.pdf) | ESTABLISHED THEORY | succinctness trades off against polynomial queries and transformations | closest external analogue to representation-dependent accessibility |
| Pitman–Koopman–Darmois | [Fraser, 1963](https://utstat.toronto.edu/dfraser/documents/25.pdf) | ESTABLISHED WITH REGULARITY | fixed-dimensional IID sufficiency implies exponential-family structure under assumptions | ordinary statistical sufficiency is not task-specific quotient sufficiency |
| RG ↔ deep learning | [Mehta–Schwab, 2014](https://arxiv.org/abs/1410.3831) | SPECIAL CASE | exact variational-RG/RBM mapping for a stated construction | no algorithm-selection or resource-cost semantics |
| RG limitations/debate | [Lin–Tegmark–Rolnick, 2016](https://arxiv.org/abs/1608.08225), [Schwab–Mehta, 2016](https://arxiv.org/abs/1609.03541) | DISPUTED SPECIAL CASE | papers debate the scope/interpretation of the mapping | not evidence for a general MAT-SI equivalence |
| DFA ↔ MPS | [Adhikary et al., 2021](https://proceedings.mlr.press/v130/adhikary21a.html) | PARTIAL CORRESPONDENCE | uniform MPS relate to weighted/probabilistic automata | no source found establishing DFA minimization = MPS canonicalization |
| Causal representation learning | [Morioka–Hyvärinen, 2024](https://proceedings.mlr.press/v235/morioka24a.html) | ESTABLISHED IDENTIFIABILITY RESULTS | latent causal representations can be identifiable under explicit assumptions | identifiability is not meta-algorithm selection |

## Classification of the external claims

The strongest false novelty was treating “choose a computation because its
expected downstream effect exceeds its cost” as a new MAT-SI principle. That is
already rational metareasoning/VOC. The valid MAT-SI contribution here is the
finite, auditable instantiation whose probes are representation/structure
channels and whose downstream action is the existing complexity-guided solver.

The strongest useful external result is the separation of representation
succinctness from supported polynomial queries/transformations. It gives MAT-SI
a precise reason to treat representation changes as algorithmic operations,
without calling every coarse-graining step renormalization.

## Remaining gaps

The exact sequential problem is exponential and its general complexity is not
claimed here. Positive-tolerance multi-task stochastic compression remains
unknown outside finite search. The structural transform consumer is currently
finite and decision-specific; a general representation-language calculus is a
later frontier.
