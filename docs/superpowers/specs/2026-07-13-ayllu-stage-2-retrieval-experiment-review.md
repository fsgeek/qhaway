# Design Review: Ayllu Stage 2 Retrieval Experiment

**Date:** 2026-07-13
**Target Spec:** [2026-07-13-ayllu-stage-2-retrieval-experiment-design.md](2026-07-13-ayllu-stage-2-retrieval-experiment-design.md)
**Reviewed Against:** the umbrella Stage 2 gate, the Stage 1 contract at its
repaired endpoint (`1826809`), the Stage 1 evaluation record and repair
addenda, and the Stage 2 question discussion of 2026-07-13
**Reviewer:** Claude (Fable 5, qhaway session)
**Status:** Completed review; S2-1 and S2-4 should close before implementation
begins

## Verdict

Approvable after a small seam-closing round — the strongest specification of
the four review rounds so far. It adopts the comparison-record question shape
("what does each preserve and lose... at what cost"), bounds the stage to two
lexical providers with vector retrieval as an evidence-triggered revisit
rather than scope creep, and makes real-corpus evidence a manifest-gated
prerequisite with enumerated roots and a purge-by-default snapshot. The
experimental-integrity machinery is notably strong: separately named strategy
identifiers so non-identical analyzers cannot manufacture equivalence,
configuration frozen before real results, ground truth established by source
scan and exact opening rather than by either provider's top result, documented
versus recalled fixture classes with the steward as final recall authority,
and the declared loss that failure by both lexical providers does not prove
embeddings would succeed. The rejected eval-only FTS5 mirror is rejected for
exactly the right reason: it would answer a narrower, biased question.

Two findings should close before implementation; the rest are minor or
observations.

## Findings

### S2-1 (major): Recalled-fixture adjudication can launder provider results into ground truth

For documented decisions, the spec explicitly forbids accepting a provider's
top result as ground truth. For recalled decisions, "later evidence
adjudication may confirm, complicate, or contradict" the recall — but the
spec does not say how that evidence is found. If a provider's results surface
the candidate episodes that adjudication then confirms as expected
references, the *other* provider is measured against ground truth discovered
by its competitor — a bias in exactly the fixture class the stage says
matters most. Close it with one rule: whenever provider output contributes to
recalled-fixture adjudication, an independent source scan completes the
expected-reference set before coverage is computed, and the fixture records
that adjudication was provider-assisted.

### S2-4 (major): The evaluation's own agent surfaces are hosted surfaces, and the manifest section doesn't name them

The reconstruction section correctly gates hosted participants on manifest
authorization, and the manifest lists "hosted participant surfaces." But
adjudication, fixture construction, and report writing are performed by agent
sessions (Claude Code, Codex) whose inference is API-hosted — the evaluator
reading opened episode content routes that content through a hosted surface
before any "participant" exists. "The journey uses an authorized local
participant" is similarly blurry: every frontier-model participant is a
hosted surface; truly local means a locally executed model. Close it by
naming the evaluating/adjudicating agent surfaces in the manifest with their
maximum evidence scope, alongside reconstruction participants, and defining
"local participant" as locally-executed inference.

### S2-2 (medium): `open_episode` has no provider selection rule in a two-provider deployment

The provider contract gives each provider its own `resolve_supersession`, and
opening "may ask the selected provider" after source resolution fails — but
nothing defines who selects, the open request has no provider parameter, and
the two providers' independently derived supersession observations can
legitimately disagree (one returns `superseded` with a replacement, the other
`missing`, depending on reconciliation timing). Define the selection rule for
operational use, and treat supersession-standing divergence between providers
as a recorded comparison observation rather than noise.

### S2-3 (minor): The SQLite strategy's match semantics need their own name

The quoted-segment-OR interpretation means a whitespace segment that the
tokenizer splits into several terms becomes a phrase within that segment —
subtly different from `analyzed_any_token`. Gate 3 requires declared rather
than presented-as-identical semantics; reusing `analyzed_any_token` for the
FTS5 strategy would quietly do the latter. Name a distinct value (e.g.,
`analyzed_any_segment_phrase`) in the strategy declaration.

### S2-5 (minor): Phase B's manifest dependency is circular as written

The manifest must name "the adapter and known version standing," but Codex
and Gemini adapter standing cannot be known until Phase B inspects authorized
samples — which requires the manifest. Resolve with a sentence: the initial
manifest may declare a source family `uncharacterized`, and characterization
produces a manifest amendment rather than a new authorization round.

### S2-6 (minor): Vocabulary strata are undefined for unresolved recalled fixtures

Strata are assigned by comparing query vocabulary to expected evidence;
unresolved recalled fixtures have no expected evidence, so their stratum is
unassignable until adjudication (which may be provider-assisted, compounding
S2-1). State that unresolved fixtures carry a `stratum: unassigned` standing
and enter strata analysis only after independent adjudication.

## Observations (not blockers)

- **Gemini is net-new scope relative to the umbrella.** The umbrella named
  Codex as uncharacterized; Gemini appears nowhere in it. The stage boundary
  accounting declares the addition consciously and the `unsupported_adapter`
  escape hatch bounds it, so this is conscious growth, not silent growth —
  but the two new adapters are the largest implementation risk in the stage,
  and the reciprocity rationale ("omitting Codex would make the intended
  reciprocity one-way") is doing real load-bearing work that a future reader
  should find here.
- **Sequencing:** Phase A builds on Stage 1 code that has not yet merged to
  llm-memory main. With V-1 now closed (`1826809` bumps all adapter
  implementation versions to "2"; evidence record re-pinned), the clean order
  is: merge Stage 1, then branch Stage 2 from main. Starting Phase A from the
  feature branch is workable but should be a declared choice.
- **Wrapping, not refactoring:** the provider-contract section's note that
  Arango "may be wrapped... but Stage 2 does not authorize broad refactoring
  merely to make the two implementations look symmetrical" is the right
  guard; the implementation plan should hold that line when symmetry becomes
  tempting.
- **FTS5 BM25 polarity:** FTS5's `bm25()` returns more-negative-is-better
  values; the Stage 1 response's `score DESC` ordering and cross-provider
  envelope should record each provider's score polarity in the retrieval
  basis so descriptive views cannot accidentally invert one provider's
  ranking. Plan-level detail; noting it here so it does not surprise Phase A.

## What the spec gets right (recorded for the decision trail)

The question adopted is the reworded comparison-record form, and every edge
from the question discussion landed: no manufactured winner (the stage
decision explicitly permits deferring selection), the lexical slice bounded
with vector/hybrid behind a qualitative evidence trigger, and the real corpus
as an authorization-gated prerequisite with fixture design as the first
evidence task. The prediction that vocabulary-distant rationale may defeat
both providers equally is built in as a first-class outcome (question 5, the
reframe path, and the declared loss that lexical failure does not prove
embeddings succeed). Ground-truth discipline, frozen configuration,
separately named strategies, per-query records with no aggregate verdict,
purge-by-default with declared repeatability loss, and the atomic-redaction
requirement carry the Stage 1 evidence ethic forward intact.

## Disposition

- **S2-1, S2-4:** close before implementation begins — both are one-paragraph
  spec amendments.
- **S2-2:** close in the spec or explicitly delegate to the implementation
  plan with the divergence-recording requirement stated.
- **S2-3, S2-5, S2-6:** editorial-scale fixes at the author's discretion.
- **Observations:** acknowledge or absorb; the sequencing choice (merge Stage
  1 first) should be made deliberately.
