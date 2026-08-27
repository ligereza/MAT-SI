# MAK — Multimodal Evidence, Semantics, and Control

**Status:** provisional mathematical guidance, 2026-08-27.  
**Scope:** answers to the twelve questions supplied by the MAK plan.  
**Boundary:** this is not a new architectural phase, benchmark, ontology, or
claim of probabilistic certainty.

The minimum safe chain is:

```text
physical artifact
  -> immutable observation
  -> derived representation
  -> candidate relation/claim
  -> authority and validation
  -> decision/action
```

Every arrow must retain provenance. DINOv2, Whisper.cpp and Multilingual-E5
produce derived observations; they do not produce identity, authorship, value or
truth by themselves.

## 1. Physical identity, content identity, snapshots, and versions

One byte sequence can have multiple physical copies, while one physical object
can produce many byte sequences over time. Therefore one identifier is not
enough. Keep at least:

```text
content_id   = H(canonical_bytes, codec_policy)
artifact_id  = opaque identity of the observed physical/logical asset
snapshot_id  = H(content_id, capture_context, observed_at, source)
version_id   = H(parent_version, transform_id, parameters, content_id)
```

`content_id` answers “same canonical content”; `artifact_id` answers “same
tracked object”; `snapshot_id` answers “this observation”; `version_id` answers
“this state in a derivation lineage”. A path is a locator, not identity.

If origin is unknown, do not infer that two identical hashes are the same
physical object. Record `same_content`, `possible_same_artifact` or
`unknown_identity` separately.

**Algorithm v1:** hash raw bytes, optionally hash a documented canonical codec,
create an observation record with source/time/context, and add explicit edges
for `copied_from`, `version_of`, `derived_from` and `reuses`.

**Invariants:** identical content does not imply identical physical origin;
changing bytes creates a new snapshot; a version must point to a parent or
explicitly declare a root; provenance is never inferred from a filename.

**Counterexample:** two different installations export byte-identical images.
Hash equality proves content equality, not common physical provenance.

**Complexity/test:** hashing is `O(bytes)`; graph insertion is `O(1)` amortized.
Test two paths with equal bytes but independent capture origins and require
`content_equal=true`, `artifact_equal=UNKNOWN`.

## 2. Overlapping CandidateObjects

Use a typed hypergraph or bipartite incidence graph, not union-find:

```text
Artifact vertices A
CandidateObject vertices O
membership edges (a, o, role, score, provenance)
```

One artifact may belong to multiple candidate objects; a candidate object may
contain a resource also used by another object. Store a membership matrix
`M[a,o]`, optionally with roles and weights. A connected component is not an
identity claim and must not trigger transitive merging.

`set packing` is appropriate only when the product explicitly requires a
disjoint selection. `set cover` or an ILP can choose a portfolio later, but it
should not define the provisional object model.

**Algorithm v1:** generate blocked candidate edges, score pairwise relations,
create candidate hyperedges, retain overlaps, and require an explicit
selection/validation step before canonicalization.

**Invariants:** no automatic merge transitivity; membership is many-to-many;
each edge has evidence and scope; candidate objects remain provisional;
resource reuse is represented, not duplicated.

**Counterexample:** `A` is similar to `B` and `B` to `C`, but `A` and `C` are
different works. Union-find silently merges all three.

**Complexity/test:** all-pairs candidate generation is `O(n²)`; blocking or ANN
retrieval reduces it to approximately `O(nk)` plus candidate scoring. Test an
`A-B-C` chain and require two non-transitive candidate objects to survive.

## 3. Version, variant, derivative, and reused resource

Use typed edges in a directed acyclic lineage graph:

```text
same_logical_entity_version(x,y)
variant_of(x,y, changed_parameters)
derived_from(x,y, transform, parameters)
reuses(x,y, context)
```

A new version has the same logical entity and a successor state. A variant is a
different realization under an explicitly changed parameter/material/context.
A derivative has a recorded transformation from a parent. A reused resource
points to an existing immutable content object; it does not create new content
evidence.

No edge should be inferred from hash inequality alone. Classification is a
claim with a confidence/validation state and can be `UNKNOWN`.

**Algorithm v1:** compare content IDs, inspect declared parent/transform edges,
and use metadata only as candidate evidence. Resolve ambiguous edges through
authority or human review.

**Invariants:** no cycles in derivation edges; parent and transform are
replayable; reuse does not duplicate storage or evidence; version and variant
are not interchangeable.

**Counterexample:** a re-encoded file has different bytes but identical content
under the canonical codec; it is not necessarily a new creative version.

**Complexity/test:** direct edge classification is `O(1)` after hashes; cycle
detection is `O(V+E)`. Test raw copy, re-encode, edited derivative and unrelated
same-format file.

## 4. Fusion of dependent evidence

Evidence must be a DAG whose leaves are source roots:

```text
root observation -> webhook -> cache -> API -> embedding -> claim
```

Define `root_ids(e)` as the set of independent origin observations supporting
`e`. Derived descendants of one root do not count as independent tests. A
probabilistic model may use a factor graph:

```text
P(H | E) ∝ P(H) · ∏_r P(root_r | H, source_state_r)
```

with explicit dependence between roots. Without a defensible dependence model,
use evidence intervals or an `UNKNOWN` validation state, not `p^n`.

**Algorithm v1:** deduplicate by `(authority, source_event_id, version,
content_hash)`, trace ancestry, collapse derivative evidence for independence
counting, retain contradictions, then apply a calibrated model only to the
root-level evidence.

**Invariants:** duplicate transport does not increase independent support;
derived evidence inherits provenance; contradictions remain visible; source
dependence is explicit.

**Counterexample:** one API response appears as a webhook, cache entry and
comment. Naive counting calls it three corroborations.

**Complexity/test:** lineage traversal is `O(V+E)`; exact factor-graph inference
may be exponential in treewidth. Replay one root through three transports and
require unchanged independent-evidence count.

## 5. Strength, probability, validation, and decision source

These are different typed fields:

```text
evidence_strength      = ordered/weighted support descriptor with provenance
estimated_probability  = P(claim | model, calibration, domain, time)
validation_state       = UNVALIDATED | CORROBORATED | CONFLICT | RETRACTED | UNKNOWN
decision_source        = AUTHORITY | RULE | MODEL | HUMAN | POLICY
```

`evidence_strength` is not a probability. `estimated_probability` is not a
certificate. `validation_state` describes process status, not truth magnitude.
`decision_source` records why an action was taken.

**Algorithm v1:** allow a probability only if the model version, calibration
set, target domain, sampling assumptions and uncertainty are recorded. Measure
Brier score, calibration error and coverage on held-out groups. Keep the
deterministic claim checker separate from the estimator.

**Invariants:** no score is silently promoted to `CERTIFIED`; calibration is
not reused across an unsupported domain; decisions retain the evidence/model
version that produced them.

**Counterexample:** a high cosine similarity receives `0.97` probability with
no labels or calibration. It is an uncalibrated score, not a probability.

**Complexity/test:** field separation is `O(1)` per claim; calibration is
`O(n)`. Test a claim with high strength but `validation_state=UNKNOWN` and
require no certified action.

## 6. Similarity across modalities

Raw embedding coordinates from DINOv2, E5 and audio models are not comparable.
Use late fusion in v1:

```text
s_m(x,y) = calibrated similarity for modality m
S(x,y) = Σ_m w_m s_m(x,y),  Σ_m w_m = 1
```

Normalize scores per modality on a paired calibration set. Missing modalities
must be masked and renormalized, not treated as zero similarity. Record each
modality's contribution and model version.

Use a common projection only when paired cross-modal data justify learning it.
Use a learned distance only with labelled or defensibly weakly labelled pairs.
Otherwise use rank aggregation and abstention.

**Invariants:** no cosine comparison across uncalibrated spaces; missing data do
not become negative evidence; a fused score retains modality provenance; score
fusion proposes candidates, not identity.

**Counterexample:** text captions happen to share vocabulary with a project and
overwhelm a visually dissimilar image. Per-modality calibration and ablation
must expose this.

**Complexity/test:** late fusion is `O(M)` after retrieval; ANN lookup is
approximately sublinear in corpus size. Test each modality alone, all fused,
and one missing; require no unexplained score jump.

## 7. Negative memory

A negative is a scoped constraint, not a universal fact:

```text
NegativeConstraint = (
  subject_scope, relation, object_scope, context_contract,
  authority, reason, evidence, created_at, expires_at
)
```

Canonicalize the relation and context into a key, but retain the original
provenance. A future candidate is blocked only if it matches the declared
scope and contract. New contrary evidence creates `CONFLICT` or reopens review;
it does not erase history.

**Algorithm v1:** check exact scoped negatives first, then retrieve semantic
near-negatives for human review. Never generalize “not this pair in context C”
to “never this relation”.

**Invariants:** scoped applicability; expiry/invalidation; no silent promotion
from candidate rejection to world claim; rejection remains auditable.

**Counterexample:** rejecting one proposed merge because of a version mismatch
accidentally blocks a later legitimate variant.

**Complexity/test:** exact lookup is `O(1)` average; semantic retrieval is
`O(log n)` or ANN-dependent. Test same relation/context (blocked), different
context (not blocked), expired constraint (not blocking).

## 8. Curatorial selection as constrained optimization

Do not select the most similar elements. Let `S` be a chosen portfolio and use a
transparent objective:

```text
F(S) = quality(S) + λ coverage(S) + μ diversity(S)
       + ν coherence(S) + ξ temporal_fit(S)
       + η evidence(S) - κ redundancy(S) - cost(S)
```

subject to budget, required coverage, evidence floors, sensitivity/licence
constraints and any reuse limits. For diversity/coverage terms that are
monotone submodular, greedy selection has a known approximation guarantee under
the declared constraint; an ILP is appropriate when exact constraints matter.
A determinantal point process is another option, but it is more expensive and
harder to explain.

**Algorithm v1:** generate candidate objects, filter hard constraints, apply a
normalized weighted greedy marginal-gain rule, and emit the marginal reasons
for every selected/rejected item. Keep overlapping resources as shared
references rather than duplicate items.

**Invariants:** score normalization is frozen; no duplicate resource is counted
twice for coverage; selected items meet hard constraints; every selection is
replayable and explainable.

**Counterexample:** the top 20 nearest embeddings are copies of one work and
miss temporal, geographic or medium diversity.

**Complexity/test:** greedy submodular selection is typically `O(k n)` objective
updates; exact set cover/portfolio selection is NP-hard. Test a corpus with a
large duplicate cluster and a unique low-similarity item required by a hard
coverage constraint.

## 9. Value of information for the next operation

Let `a` be OCR, transcription, metadata extraction, search or native inspection
and let `Y_a` be its possible result. Choose by expected value of information:

```text
VOI(a | E) = E_y[ V(E, y, a) ] - V(E) - cost(a)
V(E) = max_d E[ utility(d, H) | E ]
```

Include latency, GPU, privacy, rate limits, storage and side-effect risk in
`cost(a)`. In v1 use myopic one-step VOI; use a POMDP only when several future
operations interact materially.

**Algorithm v1:** enumerate authorized actions, estimate which unresolved claim
or decision each can change, compute expected reduction/utility, execute the
highest positive-VOI action, log predicted and realized information gain, and
stop when all remaining VOIs are non-positive or a safety gate is met.

**Invariants:** no action outside authority; no evidence claim before result
validation; cost includes failed/cancelled work; `UNKNOWN` remains available.

**Counterexample:** run expensive OCR on a document whose answer cannot change
any current decision. It has positive information but negative net value.

**Complexity/test:** one-step evaluation is `O(|A||Y|)` times decision cost;
multi-step planning can be exponential. Test two actions where the cheaper one
resolves the only decision-relevant uncertainty and require it to win.

## 10. Weak and self-supervision without leakage

Weak signals are observations with a provenance label, not ground truth. A
useful separation is:

```text
same immutable content hash       -> positive content pair
explicit derivation edge          -> positive lineage pair
near duplicate + edit record      -> candidate variant pair
different projects or artists     -> possible hard negative, never automatic
external publication/outcome      -> delayed label, not an input to its cause
```

The v1 pipeline is:

```text
provenance graph
  -> weak labels with confidence and source
  -> policy-defined hard negatives
  -> group-aware split by artist/project/session/time
  -> small ranker or selector
  -> held-out artists/projects and post-outcome evaluation
```

The split unit must be a project or artist, not a frame or embedding row. No
feature computed from a future publication, outcome, or later correction may
enter an earlier decision. Every weak label retains `label_source`,
`source_ids`, `observed_at`, and `assumption_set`.

**Invariant:** no project leakage; no future feature; weak labels are never
silently upgraded to gold labels; outcomes are evaluated as outcomes, not used
as evidence for the decision that preceded them.

**Counterexample:** the same file appears in two projects. It is evidence of
resource reuse, but not proof that both projects have the same semantic object,
intent, or artistic value.

**Complexity/test:** provenance traversal and group splitting are `O(V+E)`;
training cost belongs to the chosen head. Make a fixture where a duplicate
appears in train and test and require the splitter to reject the fold.

## 11. Planning under uncertainty

MAK does not need a full POMDP in the first slice. The minimal composition is:

1. a typed capability/action graph for feasibility and authority;
2. a finite-state workflow for deterministic progress, replay, retries, and
   rollback boundaries;
3. one-step VOI for choosing the next observation;
4. a belief state only when an action changes a hidden state relevant to a later
   action.

An action is typed as:

```text
Action = {
  preconditions, authority, inputs, effects, cost,
  uncertainty, reversibility, evidence_required
}
```

An action may run only when its preconditions and authority are certified. Its
effects are appended as events and later verified; an intended effect is not
the same thing as an observed effect. `UNKNOWN` blocks promotion and may select
an inspection action. A STRIPS/PDDL layer is justified later only if bounded
graph search cannot express the required constraints.

**Counterexample:** a command reports success, but the exported file is absent
or has the wrong hash. The action is not complete; the workflow must enter a
verification or recovery state.

**Complexity/test:** bounded capability-graph reachability is polynomial;
optimal planning and general POMDP control are intractable in the general case.
Test missing authority, failed effects, idempotent retry, rollback after a
partial export, and an action whose result is stale.

## 12. Complexity, limits, and guarantees

The following are reasonable polynomial or near-polynomial v1 operations:

- content hashing, immutable deduplication, and DAG traversal;
- cycle detection and provenance reachability;
- typed overlap membership checks;
- missing-aware late fusion of modality scores;
- bounded capability-graph reachability;
- greedy constrained selection, provided its approximation status is stated;
- exact bipartite matching when the candidate graph is fixed.

The following should remain explicitly approximate or bounded:

- global entity resolution and correlation clustering;
- portfolio selection with general coverage/diversity constraints;
- unrestricted Bayesian inference on dependency graphs;
- optimal multi-step VOI and POMDP planning;
- a universally minimal sufficient representation for arbitrary queries;
- semantic equivalence of arbitrary programs or transformations.

The architecture can promise local guarantees, not a universal semantic oracle:

```text
replayable provenance
idempotent ingestion
scoped negative memory
contract-bounded claims
auditable abstention
no silent promotion
```

Any heuristic must preserve these safety properties:

- no merge transitivity without a declared proof or policy;
- no double-counting evidence through derived descendants;
- no loss of source provenance;
- no action without the required authority;
- no irreversible speculative effect;
- `UNKNOWN` stays explicit.

## Recommended first slice

The first slice should be a typed evidence ledger and deterministic replay,
not an MLP, a universal quotient, or a full POMDP. Its minimum records are:

```text
EvidenceNode
Claim
Authority
DerivationEdge
CandidateObject
MembershipEdge
VerificationRecord
NegativeConstraint
Action / Capability
DecisionOutcome
```

Every derived DINOv2, Whisper.cpp, or Multilingual-E5 output is a versioned
observation with model, parser, preprocessing, and replay metadata. It may
support a candidate or ranking decision, but it does not by itself certify
identity, authorship, artistic value, or causal intent.

The four implementation priorities are therefore:

```text
CandidateObject overlap
  -> provenance-aware evidence fusion
  -> constrained transparent curation
  -> one-step value of information
```

The unresolved questions should remain unresolved rather than be hidden inside
the schema: arbitrary domain-shift identity, authorship/value inference,
universal future semantics, and independent verification that would require
new external authorities.
