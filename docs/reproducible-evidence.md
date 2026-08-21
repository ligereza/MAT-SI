# Reproducible evidence attack

Branch `attack/reproducible-evidence`, parent commit `4463d84`.

This branch does not start Phase 5, does not add a product, and does not redesign
MAT-SI. It attacks one property of the accepted state: whether a second machine can
audit and replay the evidence the project already claims.

Four concrete failures were found by cloning `main` on Linux and running the suite.
Each one is now locked by a test in `tests/test_reproducible_evidence.py` before its
fix, so the failure mode is executable evidence rather than prose.

## A. Frozen identity was newline sensitive

`corpus/phase4c-observability-manifest.json` pinned the MAT-SI source by raw bytes at
`C:/IA/MATH/results/phase2-self-reference-results.json`, 42 130 bytes,
`a0c8bd22…`. The repository's own `results/phase2-self-reference-results.json` is
40 629 bytes, `a705855…`. The difference is exactly 1 501 bytes over 1 501 lines: the
frozen hash was taken on a CRLF checkout. Converting the committed file to CRLF
reproduces `a0c8bd22…` byte for byte, so the frozen source *is* the repository file,
pinned through an operating-system newline convention.

Phase 3C and Phase 3D already collapsed CRLF to LF before hashing a frozen
repository-owned source. That existing rule is now named once, in
`canonical.canonical_newline_bytes`, and shared. Phase 4A already applied it; Phase 4B
and Phase 4C did not, and now do.

The manifests preserve the original raw hash and add the portable one:

- `sha256` — unchanged historical raw byte hash;
- `canonical_sha256` — identity after CRLF and lone CR collapse to LF;
- `content_kind` — `text` canonicalises newlines, `binary` stays byte sensitive;
- `repo_path` — set when the payload is committed in this repository.

A binary source keeps byte sensitivity because a newline byte can be payload there.

## B. Absent private evidence crashed instead of degrading

Phase 4B and Phase 4C read private files that exist on one machine only. On any other
checkout both raised `FileNotFoundError` from `setUpClass`, so two of the accepted
experiments could not even be inspected.

`matsi/frozen_source.py` adds one explicit boundary with three states:

- `SOURCE_AVAILABLE` — resolved and its frozen identity matched;
- `SOURCE_UNAVAILABLE` — no candidate path exists here; nothing is substituted;
- `SOURCE_HASH_MISMATCH` — resolved but the identity differs; still a hard failure.

Resolution order is `repo_path`, then an optional local mapping, then the frozen
manifest path. The mapping is read from `MATSI_SOURCE_MAP` or
`corpus/local-source-map.json`, is never committed, and only names private locations
on one machine.

When a source is unavailable the phase now runs and reports what it cannot do. Every
result carries `source_resolution` and `reproduction`, and a stored result loaded for
inspection is never relabelled as an independent reproduction.

On this Linux machine:

- Phase 4C is `PARTIALLY_REPRODUCED`. MAT-SI resolves from `repo_path` by canonical
  identity and emits its 3 records; the analytical field-removal counterexamples do
  not read any source at all, so the minimum contract is fully reproducible.
  VIBECODEINE is absent, so its 40-record mapping is not.
- Phase 4B is `NOT_INDEPENDENTLY_REPRODUCED`. Both discovery sources are private, so
  the generic relation attempt is not recomputed and `gate.decision` is `null` with
  `status: REQUIRES_PRIVATE_SOURCES`. The historical gate `B` is recorded as
  `historical_decision`, explicitly not reproduced here.
- Held-out C is still never opened. It is deliberately excluded from resolution so
  that probing it cannot become a side effect of reporting availability.

## C. Session evidence was authored by hand

`results/codeine-v0-real-session.json` is not produced by any code: no generator, no
`--json-out`, and the detailed session lived in gitignored `artifacts/`. It was the
only evidence artefact in the repository written by a human, and it backed the
current product gate.

The session record is now machine generated end to end:

```text
python -m codeine start --test-command "..."
python -m codeine checkpoint
python -m codeine assess
python -m codeine finish
python -m codeine export --out results/codeine-linux-session.json
python -m codeine replay --export results/codeine-linux-session.json
```

The single persistence rule was extracted to `codeine.core.decide`, a pure function of
the attempt diagnostics. `assess` calls it while a session runs; `replay` calls it
afterwards over the recorded observations. A recommendation is therefore recomputed
rather than trusted. Thresholds and fingerprints are unchanged.

`export` writes a deterministic projection of the raw session: observation order,
opaque intervention token digests, before and after state digests, raw *and* stable
test output digests, measured resource dimensions, detector inputs, recommendations
and provenance. `replay` recomputes each recommendation from the attempt ids that
recommendation names, and compares decision, strength, reason, evidence and
fingerprint. It also recomputes `determinism.export_digest`, so an edited export fails
replay.

Withheld from the export, and represented only by digests and provenance: the
repository root path, git status lines, untracked file paths, and diff or test output
payloads. `export_session` also audits the raw records for forbidden conclusion keys
(`progress`, `stuck`, `success`, `failure`, `productive`, `bad_strategy`) and reports
that none are present.

## D. The Phase 4A baseline compared two populations

Phase 4A scored G on the windows it matched and the no-G baseline on every window:
`0.6667` over 3 matched windows against `0.5` over 4 windows, gain `0.1667`. Those are
different populations, so the reported gain credits G partly for *not* matching a
window.

`matsi/baseline_audit.py` reports both comparisons without touching the historical
result. Scoring G and the best no-G constant answer on the same matched-window
population:

| | population | G | baseline | gain | gate |
|---|---|---|---|---|---|
| historical | matched vs all | 0.6667 | 0.5 | 0.1667 | A |
| corrected | matched only | 0.6667 | 0.6667 | **0.0** | D |

The corrected gain is `0.0` and the gate changes from A to D. Coverage is reported
separately as `0.75` rather than folded into accuracy.

`results/phase4-cross-domain-results.json` is not modified. The audit records its
identity and `overwritten: false`, and writes to
`results/phase4a-baseline-audit-results.json`:

```text
python -m matsi.baseline_audit --json-out results/phase4a-baseline-audit-results.json
```

This audit corrects arithmetic only. The Phase 4A corpus is still three authored
fixtures with four held-out windows, where one window decides the gate, so no
corrected transfer result is claimed either way.

## Session captured on this machine

CODEINE observed the work that made CODEINE reproducible. The session was captured by
the mechanism itself while this branch was written, not reconstructed afterwards. Its
export is `results/codeine-linux-session.json`; the raw session stays local in
gitignored `artifacts/`, and the export alone is enough to replay.

Session `e927d94b52464df1836fc054d6c157f8`, 7 checkpoints. The first three ran with the
locked failure tests red (`exit_code` 1); from `attempt-0005` the suite is green.
`attempt-0007` is a genuinely unchanged observable boundary: the suite ran twice with
no file edited between the two checkpoints, so `before` and `after` digests are equal
with `elapsed_ms` measured. The detector emitted `CONTINUE` with `weak_repetition`,
because one boundary does not reach the threshold of two. Two recommendations were
issued, both `CONTINUE`; no `SWITCH` or `STOP` was justified, and no causal help is
claimed.

One bootstrap detail, stated because it affects what the replay proves. The exporter
and the extraction of the rule into `decide` happened *during* this session, at
`attempt-0004`. The raw observations were machine generated from `start` onward by the
pre-existing checkpoint mechanism; the exporter was then applied to them. The rule
extraction was behaviour preserving, and replay is what verifies that: recommendation
`recommendation-0001` was issued by the pre-refactor code path and still recomputes to
the same decision, evidence and fingerprint from the recorded observations. Had the
refactor changed the rule, replay would have reported a mismatch instead.

## Gate

**B — PORTABILITY FIXED, BUT SOME HISTORICAL EVIDENCE REMAINS NON-REPRODUCIBLE.**

The suite runs on a second machine with no Windows paths, the frozen identity of
repository-owned text no longer depends on checkout newlines, the new session is
replayable from committed evidence, and the Phase 4A baseline audit is reproducible.
What remains outside this branch's reach is evidence that was never committed:
Phase 4B's two discovery sources and Phase 4C's VIBECODEINE export are private files.
They can be supplied through the local source map, and until they are, both phases
report exactly which derivations are not independently reproduced.

## Unresolved, reported and not fixed here

- Phase 3C and Phase 3D fetch two frozen sources over the network into a temporary
  cache. That is the same failure class as B on a different axis: no network means no
  run. It was left alone because it needs a fetch-and-cache policy, not an identity
  rule.
- `product/codeine-v0` points at the same commit as `main`. Reported only; branch
  administration is left to the coordinating agent.
- `results/codeine-v0-real-session.json`, the hand-authored Windows summary, is kept
  as historical evidence. It is not regenerated, because its raw session was never
  committed and cannot be recovered from this machine.
- Several accepted documents are written in Spanish while the rest of the repository
  is in English. Not touched here.
