# Autonomous operators

Branch `research/autonomous-operators-foundation`, continuing `c91efd8`.

`c91efd8` added a mathematical toolbox — information theory, search, sequential
decision, symbolic rewriting, verification, and the `S = (R, O, H, M, B)`
substrate — but no operators. This milestone turns the primitives into four
operators with different **action spaces**, gives each one a world where its
intuitive strategy provably fails, and answers whether the choice between them can
be made from the structure of the state.

Reproduce every number with:

```text
PYTHONPATH=src python -m matsi.autonomous_operators --json-out results/autonomous-operators-results.json
```

No network, no external dependency, no LLM, no sampling. Every world is finite and
deterministic and ships with an exhaustive oracle.

## Claim labels

| label | meaning |
|---|---|
| `PROVED_BY_ARGUMENT` | true by the construction of the world |
| `VERIFIED_FINITE_CASE` | checked exhaustively on a stated finite instance |
| `COUNTEREXAMPLE` | the intuitive strategy provably fails here |
| `KNOWN_RESULT` | imported from the literature, verified locally |
| `UNKNOWN` | open |

Finite verification is never restated as a universal theorem. Where a check is
scoped to a domain, the scope travels with the result (`equivalence_scope`,
`"not a proof over Z"`).

## The four action spaces

The operators are distinct because what they *do* is of different type. If they
had all reduced to "score, sort, argmax" the experiment would have failed.

| operator | acts on | action | criterion |
|---|---|---|---|
| VIZZ | a belief over hypotheses | buy one experiment | expected information about the target |
| CODEINE | a history of measured steps | continue / switch / stop | sequential structure of the returns |
| X-ANA-X | a representation | apply an equivalence-preserving rewrite | invariant preservation + enabled operation |
| KETAMINE | a tree of simulated worlds | expand a subset of branches | bound-safe pruning + evidence consistency |

## VIZZ — discovery

**Formal object.** Bayesian experimental design on a finite hypothesis space with
a decision-relevant projection `T = target(Θ)`.

**Literature.** Expected information gain as a design criterion is ESTABLISHED
(Lindley 1956; Chaloner & Verdinelli 1995). The greedy `1 − 1/e` bound for
monotone submodular maximisation is KNOWN_RESULT (Nemhauser, Wolsey & Fisher
1978). Information gain is submodular under conditional independence and not in
general — KNOWN_RESULT (Krause & Guestrin 2005). Bayesian surprise as KL from
prior to posterior is IMPORTED (Itti & Baldi 2009). Adaptive submodularity
(Golovin & Krause 2011) was read and not used: these worlds are noiseless, and the
guarantee that matters here is the one that fails.

**What is specific to MAT-SI.** Nothing in the criterion. Two things in the
discipline: submodularity is *tested* on the instance instead of assumed, and the
operator returns `INCOMPARABLE` rather than inventing an exchange rate between
bits and cost.

**Four quantities kept apart.** `expected_rarity` = `H(Y)`,
`expected_bayesian_surprise` = `I(Θ;Y)`, target information = `I(T;Y)`, and
affordability. On `rare_but_uninformative_world` an experiment has positive rarity
and positive surprise about Θ with **exactly zero** information about the target;
on `nuisance_surprise_world` the surprise is large and the target information is
zero (both VERIFIED_FINITE_CASE).

**Failure world — `decoy_parity_world`.** The target is `a XOR b`. Probing `a` or
`b` alone carries zero information about the parity; together they determine it.
A weak decoy is the only experiment with a positive marginal, so greedy takes it
and then finds every remaining marginal zero.

| decoy strength | greedy bits | optimal bits | ratio |
|---|---|---|---|
| 1/4 | 0.045566 | 1.0 | 0.045566 |
| 1/8 | 0.011301 | 1.0 | 0.011301 |
| 1/32 | 0.000705 | 1.0 | 0.000705 |
| 1/128 | 0.000044 | 1.0 | 0.000044 |

COUNTEREXAMPLE: the ratio falls below any constant, so no constant-factor
guarantee can hold for greedy expected-information-gain in general. The
submodularity test reports `COUNTEREXAMPLE` on the same instance and
`VERIFIED_FINITE_CASE` on `conditionally_independent_world`, where the guarantee
is respected. The operator therefore knows *whether it is in the regime where its
guarantee exists*.

## CODEINE — continuation

**Formal object.** Sequential decision on a trajectory of `(procedure, utility
gain, state digest)` triples with a per-step cost.

**Literature.** Optimal stopping by backward induction is ESTABLISHED (Chow,
Robbins & Siegmund 1971) and used only where a value distribution exists.
Bandits are IMPORTED (Auer, Cesa-Bianchi & Fischer 2002; Garivier & Moulines 2011
for the non-stationary case). Page-Hinkley is IMPORTED (Page 1954). Treating
observed concavity as evidence about the future is ANALOGY, and every certificate
says so.

**Two decouplings.** *Progress* is the utility the world supplies; *state change*
is a digest difference. The CODEINE v0 product rule in `src/codeine/core.py` reads
only digests, so it is the SPECIAL CASE `patience = 2, no utility signal`.

| world | operator | regret | v0 rule on the same digests |
|---|---|---|---|
| productive repetition (frozen digest) | `productive_repetition` | **0.00** | **STOP** (wrong) |
| diminishing returns | `detected_collapse` | 0.12 | CONTINUE |
| plateau then payoff (patience 2) | `diminishing_returns_exhausted` | 5.50 | CONTINUE |
| cycle with an alternative | `regime_change_alternative_better` | 3.00 | CONTINUE |
| late reward vs switch | `regime_change_alternative_better` | 7.40 | CONTINUE |
| deceptive prefix | `detected_collapse` | 1.00 | CONTINUE |

COUNTEREXAMPLE: on a constant digest with paying steps the v0 rule says STOP while
the utility-aware operator reaches the oracle payoff exactly. The four actions
arise from **different mathematical facts**, not from thresholds on one score:
insufficient measurement, recent mean above step cost, a closed cycle with zero
gain around the loop, a plateau shorter than the declared patience, an
alternative's one-step estimate, and a change-point alarm.

**Failure world — `indistinguishable_prefix_pair`.** Two worlds emit gains
`(1, 1, 0, 0)` with identical digests and then diverge: one pays 5, the other
nothing.

| patience | barren regret | fertile regret |
|---|---|---|
| 1 | **0.5** | 4.0 |
| 2 | 1.0 | 4.5 |
| 3 | 1.5 | **0.5** |
| 4 | 2.0 | 0.5 |
| 6 | 2.0 | 0.5 |

PROVED_BY_ARGUMENT: any policy whose decision at step 4 is a function of the
observed prefix takes the same action in both, so it is suboptimal in at least
one. No patience reaches zero regret on both, and the minimisers differ. This
bounds *observability*, not the algorithm: no change detector, plateau estimator
or cycle analysis removes it. It is the strongest negative result in the branch.

## X-ANA-X — re-representation

**Formal object.** Search the congruence class `[R₀]` generated by a rewrite
system for a term that (i) is verified equivalent, (ii) satisfies every declared
invariant, and (iii) satisfies an enabling predicate naming the operation a
consumer needs.

**Literature.** E-graphs and equality saturation are ESTABLISHED (Nelson 1980;
Willsey et al., *egg*, POPL 2021). Congruence closure as the decision procedure
for equality with uninterpreted functions is KNOWN_RESULT (Downey, Sethi & Tarjan
1980). Optimal extraction under a cost with shared subexpressions is NP-hard —
KNOWN_RESULT; only the tree-cost least fixpoint is computed and the limitation is
declared. Term rewriting, normal forms, confluence: ESTABLISHED (Baader & Nipkow
1998). Choosing a representation by a downstream objective rather than by size is
IMPORTED from strength reduction and superoptimisation practice.

**What is specific to MAT-SI.** Separating three predicates that are usually
collapsed into one cost: what becomes *possible*, what must *survive*, and how
*expensive* the result is. Keeping them apart is what allows a rejection.

**Failure world — `linear_read_task`.** The consumer is a single-read machine.
From `x * 2` the saturated class contains `x + x` and `x << 1`. Both are
equivalent and both remove the multiply. Their costs are **identical**:

| form | execution | tree size | `no_multiplication` | `single_read` |
|---|---|---|---|---|
| `(x + x)` | 1.0 | 3.0 | ✓ | ✗ |
| `(x << 1)` | 1.0 | 3.0 | ✓ | ✓ |

COUNTEREXAMPLE: cost and size *cannot* separate them — they tie — so a selector
driven by either decides by tie-break and can take the inadmissible form. Only the
invariant decides. The certificate records `cost_driven_choice = (x + x)` with
`cost_driven_choice_is_admissible = false`.

**Objective dependence.** On `parallel_depth_task` the same class yields
`((x + x) << 1)` under the execution cost and `((2 * 2) * x)` under tree size,
depth and the interpretability proxy — two distinct extractions from one class
(VERIFIED_FINITE_CASE). With no objective supplied the operator returns
`INCOMPARABLE`.

**Declared limits.** Saturation with associativity, commutativity and
distributivity does not terminate; runs report `saturated`, `stopped_by` and
`match_truncated`, and a verdict is relative to the fragment explored.
Identity-introduction directions (`a → a + 0`) are dropped because a bare hole as a
left-hand side matches every class; `dropped_directions` names them, so the
congruence generated is the one induced by the kept directions only.

## KETAMINE — branching

**Formal object.** A rooted tree of simulated states generated by interventions,
each branch carrying the assumptions its path introduced, with recorded evidence,
a value function on terminals, a node budget and optionally a bound.

**Literature.** Branch and bound is ESTABLISHED (Land & Doig 1960). A* optimality
under admissibility is KNOWN_RESULT (Hart, Nilsson & Raphael 1968). Beam search
incompleteness is KNOWN_RESULT. Conditioning on the factual record before
intervening is IMPORTED (Pearl 2009, ch. 7); the check implemented here is the
finite syntactic special case. **MCTS was deliberately not implemented**: these
worlds are finite, deterministic and equipped with an admissible bound, so branch
and bound is exact and cheaper, and UCT's asymptotic guarantee would add no
capability. Adding it would have been decoration.

**Modal discipline, enforced structurally.** Every generated node carries
`status = SIMULATED`; only the root is `OBSERVED`; a node whose assumptions
contradict the evidence is `REJECTED` and never expanded. No operation can promote
a simulated node, so `observed ≠ simulated`, `possible ≠ probable` (no probability
is attached to a branch at all) and `probable ≠ true` hold by construction.

**Results.** With a *verified* admissible bound, pruning never loses the optimum
(VERIFIED_FINITE_CASE). On `contradictory_evidence_world` the highest-value branch
(50.0) assumes `tests_passed` against recorded `test_failed` and is rejected; the
operator settles for 8.0.

**Failure worlds.** `trap_world`: the optimal prefix has the worst immediate score,
so beam width 1 returns 6.0 instead of 100.0 and width 2 — exhaustive at that
level — recovers it (COUNTEREXAMPLE). `novelty_trap_world`: with a declared
novelty function, diversity-first expansion returns 1.0 against an oracle of 20.0
under the same budget, while bound-guided expansion is optimal (COUNTEREXAMPLE).
Novelty is a hedge against correlated error, not evidence of value.

## Structural triggers — the central result

`src/matsi/operators/admissibility.py` evaluates a *precondition* per operator
against `S`, and nothing is ever selected by name.

| operator | precondition |
|---|---|
| VIZZ | `H(T) > 0` and an unperformed affordable experiment has `I(T;Y) > 0` |
| CODEINE | ≥ 2 measured utility steps and budget for one more |
| X-ANA-X | the equivalence class of `R` has ≥ 2 distinct members |
| KETAMINE | ≥ 2 mutually exclusive branches consistent with the evidence |

`admissible` (the structure is present) and `useful` (acting would change
something) are separate: X-ANA-X can be admissible and useless on a representation
that already enables the required operation.

On `cross_operator.CrossOperatorWorld` — implement an unknown linear map on a
machine without a multiply — each stage admits **exactly one** useful operator:

```text
R = belief over coefficients   →  RUN_VIZZ       (X-ANA-X: "nothing to rewrite")
R = concrete term x * 4        →  RUN_XANAX      (VIZZ: "target already determined")
R = schedule with branches     →  RUN_KETAMINE
```

The sequence `VIZZ → X-ANA-X → KETAMINE` is not written anywhere. CODEINE's
precondition is the only one about *history* rather than the current object, and it
flips from inadmissible to admissible exactly at the second measured step.

**Representation sensitivity.** Same object, same task, two representations of it:
`R = belief` admits VIZZ and refuses X-ANA-X; `R = term` admits X-ANA-X and
refuses VIZZ. Which operator deserves to act is a function of `R`, not of runtime
(VERIFIED_FINITE_CASE).

## Meta-selector — DEFERRED

Implemented: structural admissibility plus a partial order with an explicit
`INCOMPARABLE`. Not implemented: a scalar meta-utility over operators.

Algorithm selection (Rice 1976), metareasoning and value of computation (Horvitz
1987; Russell & Wefald 1991) and algorithm portfolios (Gomes & Selman 2001) are
ESTABLISHED and would be the right imports — but they assume a **common utility**.
The four operators produce bits about a target, utility per step, invariant
preservation, and the value of a simulated branch. These have no common unit.
Applying value-of-computation across operators whose value units differ is
UNKNOWN, and inventing a weighted sum would have destroyed the mathematics rather
than extended it. When two operators are useful, the honest output is
`INCOMPARABLE`; supplying an external preference order breaks the tie and the
verdict records that the tie-break was external.

## Answers to the ten questions

1. **Distinct?** Yes, by action space: an experiment, a trajectory decision, a
   rewrite, a branch set. Verified by the fact that the four preconditions are
   satisfied by disjoint structures in the cross-operator world.
2. **What makes each applicable?** The four preconditions above, computed from `S`.
3. **Can any two collapse?** VIZZ and KETAMINE both reduce uncertainty and are the
   nearest pair; they stay distinct because VIZZ acts on a belief and returns a
   posterior while KETAMINE acts on a hypothetical tree and returns no belief at
   all. A partial collapse is real: X-ANA-X *is* a search, so it shares machinery
   with KETAMINE — but its search space is an equivalence class, and its acceptance
   test is invariant preservation rather than value.
4. **Which known theory contains each?** Bayesian experimental design; optimal
   stopping and bandits; equality saturation and term rewriting; branch and bound
   with counterfactual consistency. Nothing here is new theory.
5. **When does each fail?** `decoy_parity_world`, `indistinguishable_prefix_pair`,
   `linear_read_task`, `trap_world` / `novelty_trap_world`.
6. **Compose?** CLOSED for VIZZ → X-ANA-X (the identified coefficient becomes the
   term to rewrite; tested). INVALID for KETAMINE before a branch structure exists
   (reported as inadmissible, not as an error). CODEINE composes with any of them
   because it reads history.
7. **Choose without a universal scalar?** Yes when the preconditions single out one
   operator, which happens in every stage of the cross-operator world. No in
   general.
8. **When must it abstain?** `ABSTAIN` when no precondition holds; `INCOMPARABLE`
   when several are useful and their units differ; `STOP` when everything
   admissible is useless.
9. **Does representation change which operator acts?** Yes — demonstrated.
10. **Emergent sequence?** Yes: `RUN_VIZZ → RUN_XANAX → RUN_KETAMINE`, from state
    structure alone.

## Open questions

- Is there a *principled* commensuration between bits, utility-per-step and
  invariant preservation, or is `INCOMPARABLE` irreducible? UNKNOWN.
- Can the X-ANA-X precondition be decided without enumerating the class? Deciding
  "the class has ≥ 2 members" currently requires saturation, which may not
  terminate. UNKNOWN.
- Is there a condition on a trajectory under which CODEINE's myopic
  `recent_mean > step_cost` rule is optimal rather than merely reasonable? UNKNOWN.
- The `decoy_parity_world` failure is detected but not repaired. Is there a
  tractable non-greedy design policy with a guarantee on non-submodular
  information objectives? UNKNOWN.

## What failed and was kept

- A character-distance proxy for novelty in KETAMINE did **not** exhibit the
  predicted diversity failure: it happened to pick the valuable branch first. The
  proxy was replaced by a novelty function *declared by the world*, because
  otherwise the experiment tests the proxy rather than novelty-driven search. The
  earlier version is recorded here rather than silently deleted.
- The first CODEINE rule counted only exactly-zero gains as a plateau, so a
  geometrically decaying trajectory never triggered stopping. Fixed by comparing
  the recent mean against the step cost; the plateau branch now handles only the
  flat-stretch case.
- `counterfactual/` existed briefly as a package whose `__init__` imported modules
  that were never written. It was deleted rather than filled with stubs: a folder
  exists only if it holds a real capability.
