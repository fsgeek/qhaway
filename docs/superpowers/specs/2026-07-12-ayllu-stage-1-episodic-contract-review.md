# Design Review: Ayllu Stage 1 Episodic Contract

**Date:** 2026-07-12
**Target Spec:** [2026-07-12-ayllu-stage-1-episodic-contract-design.md](2026-07-12-ayllu-stage-1-episodic-contract-design.md)
**Reviewed Against:** [2026-07-10-qhaway-ayllu-memory-design.md](2026-07-10-qhaway-ayllu-memory-design.md) (umbrella), `docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md`
**Reviewer:** Claude (Fable 5, qhaway session)
**Status:** Round closed 2026-07-12; all findings resolved in `9a6153a` (see Closure)

## Verdict

Mergeable after a seam-closing round. The specification satisfies all six Stage 1
preconditions declared by the Stage 0 baseline: cycle-free result identity,
mandatory concrete corpus scope, separated source/index/freshness/population
standing, exact-or-declared total-match standing, three characterized adapters
with Codex deferred until observed, and ArangoDB preserved as the implementation
under test with no FTS5 selection. Its evidence claims match the baseline
exactly (the 1,221/2,659 record split, the absent taste_open episode keys, the
reinterpretation of the 0/5 replay as a fixture/standing failure rather than
ranking evidence). The honesty machinery — declared instability for synthesized
gateway identities, no silent fallback from source-backed opening, heuristic-
labeled match attribution, the declared-losses section — is consistent with the
umbrella's invariants throughout.

The findings below are contract seams, not architectural objections. None
challenges the ownership boundary, the identity approach, or the staging.

## Summary of Findings

| ID | Category | Severity | Description |
| :--- | :--- | :--- | :--- |
| **E-1** | Contract shape | **Major** | Per-corpus standing cannot represent a multi-source corpus, which the enrollment model explicitly permits. |
| **E-2** | Contract shape | **Major** | `indexed_through: byte_offset` cannot be produced by the Claude Code adapter, whose locator is a multi-file source set. |
| **E-3** | Freshness semantics | **Major** | "Validated through the observed source end" is ambiguous between tail validation and full-prefix validation; in-place prefix rewrite detection is either unbounded work or an undeclared loss. |
| **E-4** | Identity lifecycle | **Medium** | `adapter_version` inside `episode_id` churns every issued reference on any adapter release; supersession history has no owning component. |
| **E-5** | Editorial | **Minor** | The worked search-response example contradicts the contract's own rules. |
| **E-6** | Scope accounting | **Observation** | Stage 1 as drafted is materially larger than the umbrella's Stage 1 sentence; the growth is defensible but should be accepted consciously. |
| **E-7** | Adapter rules | **Observation** | The Claude Code boundary algorithm has undeclared edge cases (multi-assistant turns, unanswered user prose). |
| **E-8** | Extensibility | **Observation** | The required-extension failure rule has no carrier field in any request shape. |
| **E-9** | Ergonomics | **Observation** | Full-digest episode identifiers make qualified references long; a cost Stage 3 evidence links will feel. |

## Detailed Findings

### E-1: Per-corpus standing cannot represent a multi-source corpus (Major)

The enrollment model states that `source_id` "identifies one enrolled stream or
source set within that corpus" — a corpus may therefore enroll multiple
sources. But the corpus standing block carries singular `adapter`,
`adapter_version`, `freshness`, `indexed_through`, and `observed_source_end`
fields. A corpus enrolling both a Claude Code stream and a gateway stream has
two adapters, two positions, and potentially two different freshness standings,
and the schema has nowhere to put them.

**Recommendation:** Either declare that Stage 1 restricts each corpus to
exactly one enrolled source (and state it in the enrollment model), or nest
per-source standing inside corpus standing. This is the finding to block on:
contract shapes are the deliverable of this stage.

### E-2: `byte_offset` indexed-through does not fit the flagship adapter (Major)

The corpus standing example shows a single `byte_offset` for
`claude_code_jsonl`, but that adapter's locator is a "source-or-source-set" —
a Claude Code project directory contains many session `.jsonl` files. A single
byte offset cannot be the indexed-through position for a file set. The escape
hatch ("adapter-defined and names its kind") technically covers this, but the
one worked example in the contract is one the flagship adapter cannot emit.

**Recommendation:** Show a shape the Claude Code adapter can actually produce
(e.g., a per-file position map or per-stream vector), or note explicitly that
set-sources require a compound kind.

### E-3: The cost and meaning of `current` is unstated where it matters (Major)

`current` requires that "the adapter validated the source through the reported
observed end," and change detection promises to catch rewrite — implicitly
including an in-place rewrite of already-indexed prefix bytes. Tail validation
from `indexed_through` is cheap; prefix-rewrite detection is O(entire file) per
validation. Under a bounded work allowance, one of two things happens:

- every pre-search reconciliation re-hashes every enrolled source, and large
  corpora degrade toward permanent `stale`/`unknown` standing; or
- `current` quietly means "tail-validated," and an in-place prefix rewrite goes
  undetected while standing claims `current`.

"Correctness outranks a cheap claim of freshness" is the right principle, but
it is ambiguous about exactly this case.

**Recommendation:** Pick one and declare it. Either define `current` as
tail-validated with prefix rewrite as a declared detection-lag loss (adding it
to the declared-losses section), or require a prefix-integrity mechanism
(stored whole-source digest, source generations) and accept its cost in the
convergence-gate accounting.

### E-4: `adapter_version` in `episode_id` churns identity on every release (Medium)

Because adapter and boundary versions participate in `episode_id`, an adapter
release invalidates every previously issued reference — including, at Stage 3,
evidence links in curated memories — even when canonical content is
byte-identical. The spec partially defends this ("changing the included
evidence fields requires a new adapter or boundary version"), but adapters will
also rev for parsing fixes that do not change canonical output.

Relatedly: the relocation/rewrite section says a prior reference may resolve to
"an explicit superseded standing when such history is available," but none of
the five components owns recording old-identity-to-new-identity history. If
superseded standing is promised, the reconciler's responsibilities should name
it.

**Recommendation:** Split identity-bearing versions (canonicalization version,
boundary version) from the adapter's implementation version so only semantic
changes churn identity — or explicitly accept the churn as a declared cost.
Assign supersession-history ownership either way. This finding requires a
decision, not necessarily a change.

### E-5: The worked search-response example contradicts its own rules (Minor)

The example shows `returned_count: 1` with `results: []`, and
`corpus_standing: []` despite one considered corpus and the rule that "every
named corpus receives its own standing." These are obviously elisions, but this
is a contract document — examples become fixtures.

**Recommendation:** Make the example self-consistent: one corpus standing
entry, one result item.

## Observations (not blockers)

### E-6: Stage growth relative to the umbrella

The umbrella scoped Stage 1 to identity, bounded search, and exact opening. The
draft pulls in the enrollment registry, automatic bounded reconciliation, and
the disable/unenroll/purge lifecycle. Each pull-in is defensible — freshness
standing is meaningless without reconciliation observations, and purge is a
declared privacy obligation the moment Arango holds a second copy — but this
makes Stage 1 the largest implementation stage yet. The umbrella's
change-control section asks for exactly this kind of conscious acceptance
rather than inherited scope.

### E-7: Undeclared Claude Code boundary edge cases

Several assistant-prose events following one user message each pair with the
same user prose, duplicating that evidence across episodes; user prose with no
subsequent assistant prose yields no episode at all. Both are acceptable under
a versioned boundary algorithm, but the adapter rules section declares weaker
things than these. A line each would match the document's own honesty standard.

### E-8: Required-extension failure has no carrier

"An unknown required extension fails visibly" — but no request shape shows
where a required extension would ride. The set is empty in Stage 1, so this is
acceptable; a sentence deferring the carrier field would prevent a later
retrofit argument.

### E-9: Reference length

A full untruncated SHA-256 plus versions plus event token inside `episode_id`
makes qualified references unwieldy for humans citing them in curated
memories. This is a deliberate and probably correct trade for offline
verifiability; noting it as a cost Stage 3 will feel.

## Framing note

This specification is neither multi-model expansion nor cross-project memory
access — it defers Codex ingestion entirely and is explicitly local-only with
no export or mount. What it is: the identity and standing groundwork both of
those expansions require. That is the right sequencing; the expectation should
be set that the draft delivers the foundation, not the capability.

## Disposition

- **E-1, E-2, E-3:** close before the spec's status advances past review.
- **E-4:** requires a recorded decision (accepted churn is a valid outcome).
- **E-5:** editorial fix.
- **E-6 through E-9:** acknowledge or absorb at the author's discretion.

## Closure (2026-07-12, revision `9a6153a`)

All nine findings verified resolved against the revision diff:

- **E-1:** Corpus standing nests `sources`; multi-adapter corpora explicit;
  counts aggregate at corpus level while availability and freshness remain
  attached to observed source members. Fixture added.
- **E-2:** Source-set adapters report per-member `indexed_through`; "no single
  byte offset claims to cover a file set." Disappeared members remain visible
  as `unavailable`/`missing` until reconciled or purged — stronger than
  requested.
- **E-3:** `current` is now a timestamped whole-member integrity-audit
  observation with a configured maximum age; new `tail_validated` standing
  covers the between-audit interval; the resumable bounded audit procedure is
  specified; O(source bytes) cost is reported separately; the detection-lag
  window is a declared loss. Acceptance gates 7–8 pin the behavior.
- **E-4:** Decision recorded as the split: identity-bearing
  `canonicalization_version` + `boundary_version` (selected in the enrollment
  declaration) versus provenance-only `implementation_version`, with visible
  compatibility-validation failure if an implementation change alters
  canonical output. The reconciler owns old-to-new supersession observations
  as operational state, not source authority, with a named purge class.
- **E-5:** Worked example fully populated and self-consistent.
- **E-6:** New "Stage boundary accounting" section makes the growth conscious
  and requires the implementation plan to keep supporting mechanisms
  separable.
- **E-7:** Both Claude Code boundary edge cases declared under boundary
  version 1.
- **E-8:** Version 1 schemas declared strict with no extension carrier;
  unknown fields fail schema validation; the first extension specification
  must define its negotiated carrier.
- **E-9:** Reference length recorded as a declared loss, with the instruction
  that Stage 3 accommodate the cost rather than invent a shorter reference
  with weaker offline integrity.

**Residual (minor, absorb at implementation plan):** audit procedure steps 3
and 5 restart the whole-member audit if the member changes during it, which
conflates benign append past the recorded end with rewrite inside the audited
range. A continuously active member could starve `current` and sit
indefinitely at `tail_validated`. Nothing dishonest results — the standing is
truthful and the convergence gate would surface chronic starvation — but the
implementation may distinguish append-beyond-recorded-end (audit remains valid
through its recorded end) from change-within-audited-range (restart).

**Verdict: mergeable.** The review round is closed.
