# FARMAKSIA — Mathematical Audit of Evidence, Semantics, and Control

**Status:** provisional research handoff, 2026-08-27.

This note answers the twelve open mathematical questions supplied by the
FARMAKSIA agent. It is not an accepted MAT-SI kernel, not a new benchmark
protocol, and not permission to infer guarantees that the data or authority do
not provide. The central rule is:

```text
evidence lineage -> explicit contract -> admissible inference -> decision
```

An implementation must distinguish what is observed, what is derived, what is
assumed, and what is merely useful as a heuristic.

## 0. Common notation

Let `H` be a set of possible world states or system histories, `E` an
append-only evidence ledger, `D` a derivation/provenance DAG, and `C` an
explicit contract containing query, predicate, authority, coverage and policy
conditions. A claim is not just a Boolean value:

```text
Claim = (predicate, scope, authority, provenance, version, status)
```

The statuses `SUPPORTED`, `REFUTED`, `CONFLICT`, `RETRACTED` and `UNKNOWN`
must remain distinguishable. A probability or a similarity score is not a
certificate.

## 1. Algebra for evidence, contradiction, and retraction

There is no single operation that is simultaneously a monotone information
join and a truth-preserving deletion operation. A join-semilattice can provide

```text
E1 ⊔ E2 = deduplicated union of evidence nodes
```

with associativity, commutativity, idempotence and monotonicity. Retraction is
not the inverse of `⊔`: it is a new, append-only event addressed to an earlier
claim or evidence version.

Use two layers:

```text
evidence_store = join of immutable observations, derivations and tombstones
live_projection = policy-dependent interpretation of that store
```

The first layer remains monotone; the second may change when a correction,
revocation or new contradiction arrives. Never erase the old evidence or
collapse `CONFLICT` into the currently preferred answer.

Minimum event identity should include a stable origin, source version and
content digest:

```text
event_id = (authority, source_event_id, source_version, content_hash)
```

A correction is an event such as `retracts = event_id` or
`supersedes = claim_version`, with reason and authority. If a distributed
implementation needs a CRDT-like store, the CRDT can solve convergence of
records; it does not by itself solve semantic truth or authority.

**Recommendation for FARMAKSIA:** implement an immutable evidence ledger and a
separate claim projection. Make `CONFLICT` and `RETRACTED` first-class. Do not
use a mutable `current_value` as the only representation.

## 2. Probabilities without double counting

Repeated observations are not independent merely because they have different
timestamps or transport IDs. Model evidence as a dependency DAG with root
observations and derived nodes:

```text
raw source event
        -> webhook delivery
        -> cache entry
        -> API response
        -> extracted claim
```

The descendants of one root should not receive independent likelihood weight.
Collapse or discount them by their root lineage before probability is
calculated. A probabilistic model may then use latent source/system states:

```text
P(H | E) ∝ P(H) · P(root_observations | H, source_states)
```

and explicitly model source reliability, dependence and time/version. If the
dependence model is unknown, return an interval or `UNKNOWN`; do not multiply
confidence as `p^n`.

Dempster–Shafer-style belief/plausibility intervals are a possible language for
epistemic uncertainty, but combination rules still need assumptions about
source dependence and conflict. They do not turn duplicated evidence into
independent evidence.

**Operational test:** duplicate a webhook, cache the same response, and replay
the API. The posterior or evidential weight must be unchanged except for an
explicit transport-integrity observation. A genuinely independent raw source
must have a separate root and a declared error model.

## 3. Entity matching without labels

Unsupervised blocking, string similarity, embeddings and graph proximity can
produce candidates; they cannot provide an identity guarantee without
assumptions or authoritative anchors.

Define a candidate set for an entity pair:

```text
M(a) ⊆ candidate_entities
```

and let `UNKNOWN` mean that the set is empty, non-singleton, out of calibration
range, or unsupported by the authority contract. A conformal procedure can
calibrate a set-valued predictor with a stated coverage level under an
exchangeability or covariate-shift assumption. It does **not** prove that one
candidate is the true identity, and ordinary marginal coverage may hide poor
coverage for a particular domain or subgroup. Exact conditional coverage is
not available universally in finite samples; this limitation is explicit in
the conformal literature. [Conformal Prediction With Conditional Guarantees](https://arxiv.org/abs/2305.12616)

For cross-domain matching, FARMAKSIA should expose:

```text
candidate_set
coverage_assumption
calibration_domain
nonconformity_score
abstention_reason
authoritative_confirmation
```

Accept a canonical identity only through an authority or a separately defined
identity proof. Conformal prediction may decide when to abstain; it cannot
silently promote a similarity score to a certified match.

## 4. Preserving semantics for queries not known in advance

No finite list of queries can preserve every future query over an unrestricted
domain. Let `𝒬` be the declared family of relevant predicates and define:

```text
x ~_𝒬 y  iff  for every q ∈ 𝒬, q(x) = q(y)
```

The coarsest sufficient representation for `𝒬` is the quotient by `~_𝒬`, but
it is useful only after `𝒬` is specified. If the query family is unrestricted,
the quotient can be as detailed as the original object.

For histories, temporal relations and provenance must be part of the state.
When the system is a labelled transition system, bisimulation is the relevant
stronger notion when preservation must include branching future behavior; a
homomorphism alone may preserve positive structure while losing negative or
temporal distinctions. Bisimulation is explicitly a semantic equivalence of
labelled transition systems and preserves the branching structure being
compared. [Bisimulation, R. J. van Glabbeek](https://www.cse.unsw.edu.au/~rvg/pub/Bisimulation.pdf)

**Recommendation:** declare a versioned query contract `𝒬_v`, preserve a
lossless provenance/state layer for later refinement, and use summaries only
for the compatible query family. Do not promise semantic preservation for
unanticipated queries without preserving the information required to refine.

## 5. Independent verification and common-mode failure

“Different implementation” is not the same as independent failure. Define an
error-factor vector for each verifier:

```text
F = (source, collection, storage, parser, normalization,
     model, cache, policy, clock, operator)
```

Two verifiers can be diverse in code but share the same source, parser,
normalization bug or policy error. The product rule

```text
P(F1 ∧ F2) = P(F1)P(F2)
```

is legal only under a justified independence or conditional-independence
model. With no historical failure data, covariance is unidentifiable; report
the common-mode risk rather than claiming that repetition reduces it
exponentially.

The strongest practical pattern is:

```text
raw source A -> parser/model A -> result A
raw source B -> parser/model B -> result B
```

with separately stored raw inputs, implementations, dependency versions and
provenance. A second verifier sharing the same raw source can detect a parser
bug, but cannot independently verify the source observation.

**Recommendation:** expose a fault/dependency graph and report diversity by
factor, not by verifier count. If a common root is present, the safe status is
“corroborated under shared source”, not “independently verified”.

## 6. Interface actions that change the evidence

When the interface affects what the user sees, clicks, asks, abandons or
reveals, those observations are policy-dependent. A partially observable
controlled process is the correct general model:

```text
s_t = latent user/task/system state
a_t = interface action
o_t = observed interaction/outcome
b_t(s) = belief state after history h_t
```

Use a contextual bandit only when rounds are effectively independent, there is
no meaningful state carry-over, and the action affects only the current reward.
Use a POMDP or controlled hidden-state model when interface actions change
future state, information, fatigue, learning, task progress or observation
policy.

Do not treat a click, request for help or lack of backtracking as direct proof
of understanding. They are observations generated under the chosen policy.
Evaluate policies using randomized assignment when possible, explicit outcome
variables and a causal estimand. If only logged observational data exist,
propensity and support assumptions are required; otherwise counterfactual
policy claims are not identified.

## 7. Verification, value of information, and stopping

Let `H` be possible states, `d` a decision, `U(d,H)` utility, `E` current
evidence, and `v` a possible verification producing observation `Y`. Define:

```text
V(E) = max_d E[U(d,H) | E]

EVI(v | E) = E_Y[V(E,Y)] - V(E) - cost(v)
```

Acquire `v` only when its expected value is positive, subject to hard safety
constraints. Stop when every admissible verification has non-positive EVI or
when the decision meets a separately declared risk bound. For irreversible or
high-impact actions, an EVI threshold is not a substitute for a mandatory
authority or fail-safe gate.

Correlated verifiers require a joint error model with latent common causes.
Ten repetitions of the same pipeline do not justify `p^10`. Without a
defensible dependence model, use a conservative bound and classify the result
as not independently verified. Sequential information acquisition and costly
stopping are standard decision-theoretic problems; a POMDP formulation is
appropriate when knowledge and state evolve together. [Optimal Stopping in a
Partially Observable Markov Process with Costly Information](https://doi.org/10.1287/opre.28.6.1319)

## 8. Capability-safe bridges and revocation

GitLab and Mattermost permissions should not be mapped as a simple role-name
lookup. Represent an effective permission as a scoped capability or ABAC
decision over subject, object, action and environment:

```text
cap = (principal, resource, action, scope, issuer, epoch, expiry, nonce)
```

The bridge must enforce:

```text
allow_destination(action, context)
    implies
capability_source(action, context)
```

and must bind the authorization to the actual execution context. A check made
before a revocation and used later is a TOCTOU gap. Use short-lived,
single-purpose, signed capabilities or an atomic check-and-use transaction;
revalidate the authorization epoch at execution. Default deny when the
mapping is missing or stale. NIST ABAC formalizes authorization as a function
of subject, object, requested operation and environmental attributes, which is
the correct vocabulary for this non-one-to-one mapping. [NIST SP 800-162](https://csrc.nist.gov/pubs/sp/800-162/upd2/final)

## 9. Minimal sufficient representation

For an explicit query family `𝒬_G`, a deterministic representation
`R : X → Y` is task-sufficient when:

```text
R(x) = R(y)  =>  q(x) = q(y)  for every q ∈ 𝒬_G
```

Equivalently, `R` must refine no distinctions that matter to the declared
objective. The coarsest such quotient is by `~_𝒬G`; it is not necessarily
unique as an encoding and need not be computable cheaply.

The representation optimization is therefore constrained multi-objective
optimization, not a universal “smallest representation”:

```text
min (visual_load, tokens, latency, GPU_cost)
subject to semantic_error(𝒬_G) = 0
```

If exact preservation is relaxed, the error tolerance and evaluation
distribution must be explicit. If the user's objective can change, a single
minimal representation does not exist in general. Preserve a refinement path,
provenance and discarded-information markers so a later query can produce
`UNKNOWN` and request more detail rather than fabricate an answer.

This is the direct connection to MAT-SI Certified Refinement: summary
compression is safe only relative to a contract and a compatible query class.

## 10. Precomputation and speculative work

For a candidate prefetch `p`, a useful decision quantity is:

```text
NetValue(p | h) =
  P(needed | h) · latency_saved
  - compute_cost
  - energy_cost
  - privacy_cost
  - storage_cost
  - side_effect_risk
  - cancellation/opportunity_cost
```

This is a heuristic form of expected utility; the exact value depends on the
state and future policy. Use a dynamic program or POMDP when thermal budget,
queue state and future requests interact. A prefetch with irreversible side
effects is not safe merely because it is likely to be used: speculative work
should be pure, authorized, cancellable and isolated until commitment.

The policy should precompute only when expected latency benefit exceeds the
full cost and risk, with a thermal/privacy budget. Cancellation must be a real
state transition, not an accounting fiction.

## 11. Identifiability of VIZZ with one webcam

With one ordinary webcam, the following are generally confounded unless extra
assumptions or calibration are supplied:

```text
eye rotation / gaze direction
head pose and distance
camera intrinsics/extrinsics
screen-plane geometry
eyeglass refraction and frame occlusion
individual eye anatomy
```

A monocular image gives projective observations, not unique metric depth and
screen geometry. A calibration can estimate a mapping for a fixed camera,
screen, user and glasses condition, but it cannot identify every physical
parameter from the video alone.

Use a fixed world coordinate frame, known screen planes and camera calibration;
model head pose explicitly rather than silently rejecting all movement. Treat
glasses condition as a domain/covariate or calibrate it separately unless the
data support an identifiable optical model.

For active calibration, choose targets by information gain. With parameter
vector `β` and feature Jacobian `J_i`, the local Fisher information is:

```text
F = Σ_i J_iᵀ W_i J_i
```

Prefer candidate points/trajectories that maximize `log det(F)` or the smallest
eigenvalue of `F`, while keeping the condition number bounded. Cover screen
corners, center, edges, diagonals and—when multiple monitors exist—each screen
plane and its boundary. Stop adding targets when the uncertainty of the
required parameters meets a declared threshold; add the next point where it
reduces the largest uncertainty. This is shorter and more defensible than a
fixed long calibration, but it cannot defeat non-identifiability.

## 12. Causal evidence of an interface improvement

Do not define “understanding” as an inferred private mental state. Define an
observable outcome `Y`, for example:

```text
delayed transfer-task correctness
novel-task success without the original hints
error correction after a controlled perturbation
retention after a delay
completion time subject to a correctness floor
```

Randomize representation/policy `A` when possible and estimate an explicit
effect such as:

```text
ATE = E[Y | do(A=1)] - E[Y | do(A=0)]
```

Clicks, help requests and backtracking may be mediators or covariates, not
proof of understanding. If the policy adapts over time, use a sequential
causal model and preserve treatment history, eligibility and propensity. Split
validation by user/session/task where the claim requires transfer; frame-level
splits are insufficient for a user-level causal claim.

## 13. The three dangerous questions for FARMAKSIA

### A. Unknown future semantics

The safe architecture is a versioned query contract, provenance-preserving
state, and certified refinement. There is no finite magic query basis for an
unrestricted future. The first product claim should be “preserves this declared
query family under this authority,” not “preserves meaning.”

### B. Independent verification

The safe architecture is a fault/dependency graph plus diverse roots and
separate trust bases. Count independent error factors, not services. If source,
parser or policy is shared, say so explicitly and do not multiply confidence.

### C. Policy changes the evidence

The safe architecture is a controlled partially observable process plus a
causal evaluation protocol. Treat interaction as policy-generated data and
measure transfer or correction outcomes, not inferred mental states.

## 14. One most valuable measurement now

The highest-value shared measurement is an **evidence lineage and replay
record** for one real FARMAKSIA workflow:

```text
raw source roots
-> received events
-> normalized entities
-> derived claims
-> verifiers
-> decisions/actions
-> corrections/retractions
```

For every node record:

```text
origin_id, parent_ids, authority, version, content_hash,
observed_at, derived_at, parser/model version, policy version,
coverage, duplicate_of, conflict_set, actionability
```

This one measurement tests deduplication, provenance, entity resolution,
verification diversity, retraction, semantic scope and causal exposure. It is
more valuable than a single aggregate accuracy number because it reveals where
the claim became unsupported.

## 15. Concrete orientation for the FARMAKSIA agent

Before implementing a probabilistic matcher or adaptive UI, create a thin
typed core with these records:

```text
EvidenceNode
Claim
Authority
DerivationEdge
EntityCandidateSet
VerificationRecord
Capability
DecisionOutcome
```

Minimum invariants:

1. duplicated descendants of one root do not increase independent evidence;
2. every claim has scope, authority, provenance and version;
3. contradiction and retraction remain auditable;
4. incomplete authority yields `UNKNOWN`, not negative evidence;
5. matching produces candidates/abstention before canonical identity;
6. a verifier sharing a root is not counted as independent;
7. authorization is checked at execution under the current epoch;
8. interface events are policy-dependent observations;
9. prefetch is pure, cancellable and budgeted;
10. a representation may discard information only with a declared query contract
    and refinement path.

The first implementation slice should be an append-only evidence/claim ledger
with replay and a provenance DAG. It should not be an MLP, a conformal identity
oracle, a universal semantic quotient, or an autonomous UI policy.

## 16. What remains unproved

This note does **not** prove that FARMAKSIA can:

- identify entities under arbitrary domain shift;
- estimate calibrated probabilities without a dependency model;
- preserve arbitrary future semantics with a compact representation;
- obtain independent verification merely by adding services;
- infer understanding from interaction traces;
- identify full VIZZ geometry from one webcam;
- derive an exact optimal prefetch policy in the presence of all listed costs.

Those are hypotheses requiring explicit contracts, data and failure models.

## References used for orientation

- [Provenance as Dependency Analysis](https://arxiv.org/abs/0708.2173)
- [Conformal Prediction With Conditional Guarantees](https://arxiv.org/abs/2305.12616)
- [Bisimulation, R. J. van Glabbeek](https://www.cse.unsw.edu.au/~rvg/pub/Bisimulation.pdf)
- [NIST SP 800-162: Attribute Based Access Control](https://csrc.nist.gov/pubs/sp/800-162/upd2/final)
- [Optimal Stopping in a Partially Observable Markov Process with Costly Information](https://doi.org/10.1287/opre.28.6.1319)
- [The Value of Information in Stopping Problems](https://arxiv.org/abs/2205.06583)
