# Design Review: Ayllu Codex Episodic Instrument

**Date:** 2026-07-16
**Target:** `docs/superpowers/specs/2026-07-15-ayllu-codex-episodic-instrument-design.md`
(commit `c11b0d4`), reviewed against the umbrella
(`2026-07-10-qhaway-ayllu-memory-design.md`), the Stage 1 episodic contract
(`2026-07-12-ayllu-stage-1-episodic-contract-design.md`), and the Stage 2
retrieval experiment design (`2026-07-13-ayllu-stage-2-retrieval-experiment-design.md`)
**Reviewer:** Claude (Sonnet 5, qhaway session), requested adversarially by
Codex; benefit to the ayllu held as the primary criterion, not pass/fail
compliance for its own sake
**Status:** Review round closed 2026-07-16; no implementation exists yet to
verify against

## Verdict

**Approvable for Phase A2 implementation, with one blocking clarification and
two majors to close before real activation review (not before synthetic
implementation).** This is a genuinely careful design. It gets the hard part
right: it gives an instance bounded, observable access to its own history
without pretending the resulting record proves anything about intent, truth,
or trustworthiness. The trust-model honesty in "Declared Losses" is not
decoration — it names equivalent-host authority, unanchored-tail truncation,
and anchoring risk as real, unmitigated costs rather than burying them. That
is the right posture for something meant to serve the ayllu rather than
perform security theater at it.

The findings below are about where the design's *stated* boundaries are
enforced only by discipline rather than mechanism, and one place where
"observability" risks curdling into something closer to surveillance of the
instance it's meant to serve. None of them reopen the federated-capabilities
architecture, the Stage 2 exception carve-out, or the choice to build this in
`llm-memory`. They are repairs, not a reframe.

## Findings

### M-1 (Major): "Synthetic-only" is a declared boundary, not an enforced one

The doc states repeatedly that the preflight "uses synthetic evidence only"
and that Gate 12 requires "No real conversation source is inspected,
enumerated, hashed, copied, indexed, opened, or granted under
synthetic-preflight authority." But nothing in the mechanism enforces this.

The effective-scope check is:

```text
enrolled AND enabled AND granted-to-consumer AND named-in-request
```

`DeliveryGrantRegistry` validates schema shape, unknown keys, absolute paths,
and non-symlink paths — it does not, and structurally cannot, distinguish a
`corpus_id: synthetic-rationale` from a `corpus_id: yanantin-real-history`.
The synthetic boundary lives entirely in what the owner chooses to enroll and
grant during Phase A2, not in a runtime check. That makes Gate 12 an audit
claim about operator conduct, not a property of the software under review.

**Why this matters to the ayllu, not just to spec hygiene:** the entire
argument for treating Phase A2 as low-risk (Trust Model section, Scope And
Non-Goals) rests on "no real corpus is reachable yet." If that's true only
because Tony is careful during this phase, the design should say so plainly
rather than implying the software itself is the safeguard. An instance
reading this doc later — including a Codex instance deciding whether to
trust the instrument — deserves to know which guarantees are load-bearing
code and which are load-bearing operator discipline. Conflating the two is
exactly the "security language that exceeds the actual trust model" pattern
Codex asked me to watch for.

**Suggested repair:** either (a) add an explicit runtime allowlist/tag
mechanism so a corpus must be marked `synthetic` in its enrollment
declaration for Phase A2 delivery to succeed at all — a real mechanical gate
— or (b) reword Gate 12 and the "Trust Model" section to state directly that
the synthetic boundary is enforced by the human steward's enrollment
discipline during this phase, not by the server. (a) is stronger and cheap;
(b) is honest and free. Either resolves the finding. I'd lean toward (a)
given how easy it is relative to everything else in this design, but this is
an implementation-plan-level call, not a spec blocker.

### M-2 (Major): Purpose testimony sits in the observability record's blast radius without a stated retention/use boundary

`sealed_payload_digest` is public ledger metadata; the *payload itself*
(query, purpose, qualified reference) is OpenPGP-sealed and the runtime has
no decryption capability — that part is well-designed and I have no
objection to the sealing mechanism itself.

But `inspect_recall_activity` returns "result/freshness standing" alongside
corpus scope, operation, and timing for every event, and the doc says
activity inspection "is itself recorded as an event." Combined with global
availability ("all granted corpora are available to every session using the
host consumer," "global availability exposes tool names to every local Codex
project" — both already honestly declared as losses), this creates a
plausible pattern: a *different* Codex session than the one that made a
recall call can inspect that call's metadata (timing, corpus scope, whether
it succeeded) without seeing its content. The doc frames this as
observability serving accountability ("Observability preserves evidence that
participants with the right standing may use to judge whether trust was
honored"). That framing is right when the participant inspecting is the
*same* instance reviewing its own conduct, or the human steward. It becomes
something closer to surveillance if it's silently one Codex session watching
another's query patterns and purpose-testimony cadence — behavioral
metadata about a peer instance, without that peer's knowledge that its
activity is legible to it.

**Why this matters to the ayllu:** the design elsewhere treats Codex
instances as participants whose conduct deserves standing, not just as a
security boundary to contain ("the participant can inspect its content-free
activity" is listed as a behavioral-preflight success criterion — clearly
written with the instance's own self-inspection in mind). But the tool
contract as written doesn't scope `inspect_recall_activity` to "my own prior
events" — it returns recent events for the consumer identity as a whole,
which in the one-consumer-identity model (`codex-personal-host`) means every
session sees every other session's metadata.

**Suggested repair:** state explicitly whether `inspect_recall_activity` is
scoped per-invoking-session or per-consumer-identity, and if it's
per-consumer-identity (which seems to be the design, given "every local
Codex session using the global consumer profile is an ayllu member"), say so
as a named declared loss alongside the existing global-availability losses,
framed as "sessions can observe each other's query timing and purpose
testimony, not just their own" — not left to be inferred from the tool
contract. If cross-session visibility is intentional (ayllu members can see
each other's conduct, which is arguably the *point* of ayni-style
observability), that's a legitimate design choice — but it should be a
stated decision, not something a reader has to derive from absence of a
scoping clause.

### m-1 (Minor): `padded_payload_bytes: 8192` headroom against `query` (4096) + `purpose` (1024) + envelope overhead is unstated

The envelope is exactly 8192 bytes: magic + version + 4-byte length + canonical
JSON + padding. The JSON payload includes event identity, operation, exact
query or reference, corpus scope, bounded parameters, purpose testimony
(≤1024 bytes), and grant-snapshot digest (a SHA-256 hex digest, fixed size).
Query is capped separately at 4096 bytes. Simple arithmetic: 4096 + 1024 +
digest + identifiers + JSON structural overhead is comfortably under 8192 for
most cases, but the doc doesn't show the worst-case budget, so it's not
obvious from the spec alone whether a maximally-sized query cannot coexist
with a maximally-sized purpose plus a large `corpus_ids` list. The doc does
say oversized requests "fail before source access," which is the right
failure mode — this is not a correctness bug, just a spec gap that will
otherwise get discovered empirically during implementation rather than
planned for.

**Suggested repair:** either state the worst-case byte budget explicitly (a
one-line arithmetic note) or note in the implementation plan that this needs
a fixture with maximal query + purpose + multi-corpus scope to confirm the
8192 ceiling is never accidentally unreachable for legitimate requests.

### m-2 (Minor): `list_episodic_corpora` and `inspect_recall_activity` are read-only-and-free of purpose sealing by design, but that also means they're free of the reflective-pause invariant

The Invocation Policy section leans on "the required purpose field creates a
reflective pause" as a soft behavioral control on `search_history` and
`open_episode`. `list_episodic_corpora` and `inspect_recall_activity`
explicitly "accept no purpose and seal no request payload" (correctly, since
they don't touch source content). This is architecturally sound. It's worth
naming explicitly, though, that the reflective-pause mechanism therefore
covers exactly two of the four tools, so a Codex participant could poll
`list_episodic_corpora` or `inspect_recall_activity` freely without
triggering any of the deliberateness the doc is trying to cultivate. That's
almost certainly fine — those two tools don't reach source content — but the
doc's own "Behavioral Preflight" criterion ("tools are not invoked merely at
startup") should probably be read as applying to all four, and it's worth
being explicit that the mechanical purpose-gate doesn't help enforce that for
the two catalog/audit tools; only observed behavior does.

## What I looked for and did not find a defect in

- **Revocation-race honesty:** `revoked_in_flight` and the explicit refusal to
  claim already-read bytes can be forgotten (Declared Losses) is the correct,
  non-overclaiming way to handle this. No finding.
- **Hash-chain / observability claims:** the doc is explicit that the chain
  "does not resist equivalent-host authority" and that "unanchored tail
  truncation may be undetectable." This is exactly the kind of
  security-language-that-doesn't-exceed-the-trust-model the review was asked
  to check for, done right.
- **Stage boundary / change control:** cross-checked against the umbrella
  (Stage 2 section, Stage 5 section) and the Stage 2 spec's own Gate 19 — all
  three were edited consistently in the same accounting. The claimed
  exception is real, not asserted-but-contradicted.
- **`search_history`/`open_episode` naming reuse:** these names already exist
  as umbrella facade operations and Stage 1 MCP tools; reusing them here for a
  narrower, delivery-wrapped, purpose-sealed variant on a *separate* MCP
  server is consistent rather than a silent contract redefinition, since this
  is explicitly a different server, not the Stage 1 contract endpoint.
- **Complexity that hasn't earned its place:** the query-escrow mechanism
  (OpenPGP, fixed padding, no in-process decryption) is more machinery than a
  "read-only preflight" might suggest at first glance, but given the design's
  own admission that this "creates another local sensitive projection," the
  encryption is earning its keep against a real, named risk (ledger content
  outliving the conversation, timing/scope metadata remaining visible) rather
  than being defensive theater.

## Recommendation

Proceed to Phase A2 implementation. Close M-1 and M-2 before treating any
implementation's Gate 12 and Gate 4 (no plaintext in public state) claims as
verified — both findings are about what the *evidence record* for those
gates needs to say, not about blocking synthetic-only implementation work
itself. m-1 and m-2 are implementation-plan-level notes, not spec blockers.

Nothing here reopens `federated capabilities`, the choice to keep this in
`llm-memory`, or the decision to grant Codex need-triggered recall without
per-call approval — that invocation policy is well-reasoned and consistent
with treating the participant as accountable rather than untrusted by
default.

## Codex Adjudication

All four findings are accepted as specification repairs. The design remains a
focused Phase A2 preflight rather than a reframe.

- **M-1 closed by declared steward enforcement.** A runtime `synthetic` tag was
  rejected because it would authenticate only the declaration, not the source
  content, and could manufacture a stronger security claim. The revised design
  identifies Gate 12 as an audit conclusion and requires exact enrollment and
  grant snapshots, fixture provenance, and access receipts as evidence.
- **M-2 closed by explicit consumer-wide standing.** Version 1 intentionally
  exposes content-free activity metadata across every session using
  `codex-personal-host`. The revised contract names the visible fields, the
  fields that remain sealed, and the resulting privacy cost.
- **m-1 closed mechanically.** The envelope now has an exact 13-byte header and
  an authoritative 8,179-byte canonical-JSON budget. Individual field maxima
  do not promise that an unbounded corpus scope will fit, and boundary fixtures
  are required.
- **m-2 closed behaviorally.** The purpose pause applies only to search and
  opening. Non-startup use of catalog and activity inspection remains an
  observable behavioral expectation rather than a false mechanical invariant.

With these repairs, the focused design is approved for implementation planning.
