# Prior-art notes

These notes are hypotheses for the Phase 1 experiment, not commitments to a final kernel.

## Nock and combinatory representations

Nock evaluates formulas over a subject made from nouns, with formulas represented using
atoms and cells. The specification describes composition, subject extension, invocation,
replacement, and conditional computation as reductions over this small universe.

This motivates Candidate A: a very small structural basis can express data and programs
without giving files, names, or language syntax primitive status. The cost is that the
minimal tree does not automatically provide content identity, shared subgraphs, or a
natural history model.

Sources:

- <https://docs.urbit.org/nock/specification>
- <https://docs.urbit.org/nock/definition>

## Lambda calculus and combinatory logic

Variable binding and substitution are powerful, but names and environments can become
representation overhead. Variable-free combinatory styles are relevant as a comparison
point for reducing the number of primitives. Phase 1 does not claim that a lambda or
combinator calculus is the answer; it only tests whether a smaller structural language
helps with cross-domain reconstruction.

Nock's formula basis is used as the primary executable reference for this direction.

## Content-addressed DAGs and IPLD

IPLD separates an abstract data model from serialization codecs and adds links whose
identity is content-addressed. Its DAG-JSON specification requires deterministic key
ordering and whitespace rules so equivalent data has stable encoded bytes. A content
identifier can therefore name a node without depending on a human name or location.

This motivates Candidate B: immutable nodes, shared repeated substructures, and root
sequences for time. It also exposes an important cost: hashes, codecs, and link stores
are part of the total description cost and must not be hidden from `D`.

Sources:

- <https://ipld.io/docs/data-model/>
- <https://ipld.io/specs/codecs/dag-json/spec/>
- <https://ipld.io/docs/intro/primer/>

## Unison-style structural identity

Unison identifies terms and types using hashes of internal structure rather than their
human-readable names. Names are separate metadata and can change while the definition's
identity remains stable. Dependencies are represented structurally, and immutable content
enables persistent caches and codebase history.

This strengthens the Candidate B hypothesis and supplies a concrete test for the
identity principle: renaming metadata should not change the identity of the represented
object. It also warns that canonicalization choices and cycle handling are part of the
identity definition, not implementation trivia.

Sources:

- <https://www.unison-lang.org/docs/language-reference/hashes/>
- <https://www.unison-lang.org/docs/the-big-idea/>
- <https://www.unison-lang.org/docs/usage-topics/resetting-codebase-state/>

## Term rewriting

Term rewriting treats computation as directed application of rules. Termination,
confluence, normal forms, and strategy are observable properties rather than assumptions.
This matters for MAT-SI because a transformation may have multiple valid forms, may not
terminate, or may preserve a residue that a normal form cannot express.

Candidate C includes rewriting as an operation rather than pretending that one canonical
form is always available.

Source:

- <https://ir.cwi.nl/pub/2667/2667D.pdf>

## E-graphs and equality saturation

An e-graph stores equivalence classes of terms. Equality saturation applies rewrites while
retaining alternatives, and extraction later chooses a representative according to a
cost function. The `egg` work emphasizes rebuilding and e-class analyses as practical
mechanisms for making this representation scale.

This motivates Candidate C: transformation can be represented as preserved alternatives
instead of destructive replacement. The risk is that equivalence classes and rewrite
search introduce substantial cost and require a domain-specific extraction metric.

Source:

- <https://arxiv.org/abs/2004.03082>

## Minimum Description Length and Kolmogorov complexity

MDL evaluates a two-part description: model/rule cost plus residual data cost. This maps
directly to the MAT-SI total-cost requirement. Kolmogorov complexity is useful as a
theoretical boundary, but the exact shortest program is not computable in general. Phase
1 therefore reports explicit canonical byte counts and operation costs instead of
claiming to compute `K(x)`.

Sources:

- <https://ir.cwi.nl/pub/11997/11997D.pdf>
- <https://arxiv.org/abs/cs/9901014>

## Working hypotheses

1. Candidate A may minimize local description size when sharing is absent or cheap.
2. Candidate B may dominate repeated structure and identity stability.
3. Candidate C may dominate reversible alternatives and transformation search, but may pay
   more for rules, e-classes, and extraction.
4. None of these hypotheses is a result until the common corpus and counterexamples have
   been measured.
