# Implementation Review: Ayllu Stage 1 Episodic Contract

**Date:** 2026-07-13
**Target:** `llm-memory` branch `feature/ayllu-stage1-contract` at `5e6be56`
(worktree `../llm-memory-stage1`), reviewed against
[2026-07-12-ayllu-stage-1-episodic-contract-design.md](2026-07-12-ayllu-stage-1-episodic-contract-design.md),
the plan `docs/superpowers/plans/2026-07-12-ayllu-stage-1-episodic-contract.md`,
and the evidence record
`docs/superpowers/baselines/2026-07-12-ayllu-stage-1-evaluation.md`
**Reviewer:** Claude (Fable 5, qhaway session), with three parallel review
agents (reconciler/index, adapters/enrollment, evidence-integrity audit); both
blocking findings verified directly by the reviewer at the cited lines
**Status:** Completed review; verdict below

## Verdict

**Repair within the current boundary, then continue.** The contract design is
validated by this implementation: identity, canonicalization, enrollment
authority, standing separation, exact counts, source-backed opening, and
non-destructive lifecycle are real, tested against a live ArangoDB, and honest
in their committed evidence. Nothing found reframes the architecture or the
ownership boundary. But two blocking and several major defects live in paths
the 203-test suite does not reach, and two of them break the exact honesty
invariants the stage exists to establish. The evaluation record's `continue`
decision is supported for the contract; it should not be treated as durable
for the implementation until the repairs land and the affected gate rows are
re-evidenced.

**Do not enroll a real corpus before I-1 and I-2 are repaired.** A single
duplicated log line in a real source would take down every search over its
corpus (I-1), and crash/conflict windows can expose a tail-only scan as
`current` (I-2).

## Independent verification

- Complete `llm-memory` suite re-run at `5e6be56`: **203 passed in 19.87s**
  (record claims 203 in 19.65s). Complete qhaway suite re-run: **137 passed in
  11.98s**. Collected counts for the 85-test repair slice match.
- The integrity audit located committed evidence for **all fourteen acceptance
  gates**, re-ran the journey tests successfully, and found **no fabrication,
  no mocks anywhere in the codebase** (zero `unittest.mock` hits), no circular
  assertion carrying a gate alone, and no silent real-source scan path (the
  eval runner requires an explicit `--config` and its purge path rejects any
  corpus not prefixed `test-` before touching the database). Redaction is
  whitelist-based reconstruction, verified by a forbidden-marker test.
- Integrity caveats, all declared or minor: half of gate 5's degraded-scope
  evidence uses a stubbed provider (the exact-count half runs against real
  Arango); the specific measured-journey figures come from a declared external
  run and are not reproducible from committed artifacts; historical
  pre-repair "passed" rows were not re-executed.

## Blocking findings

### I-1: A duplicated identical source record crashes search for its corpus

Verbatim-duplicated lines (same native event, identical content — a realistic
log artifact) produce two episodes with the same reference but different
`source_position`. `write_generation` computes the same document key for both
and raises plain `ValueError("conflicting generation document")`
(`contract_index.py:133`), but the reconciler's call sites catch only the
`GenerationStateConflict` subclass (`reconcile.py:530,575`), so the exception
escapes `reconcile_registry` into every `search_history` call for that corpus.
The spec requires a malformed complete record to "fail that source visibly
with its position" without erasing other standing — not a fail-crash of the
search surface. Verified directly at the cited lines.

### I-2: A tail-only scan's `current` freshness is persisted before activation

`_scan_lines_chunk` returns `CURRENT` for any completed, non-exhausted chunk —
including a tail-only append scan (`adapters.py:237-241`). `_reconcile_tail`
persists that value verbatim in the mid-build state patch
(`reconcile.py:589-606`); the downgrade to `tail_validated` happens only later
in the activation patch (`reconcile.py:648`). In any window where the patch
commits but activation does not — crash, `_StateConflict` return, supersession
intent conflict, or a concurrent call whose budget exhausts before this member
— `_member_standing` (`reconcile.py:1149`) reports the stored `current` for a
member that only had its tail scanned. This violates the spec's core freshness
sentence: "the system never calls a tail-only observation `current`."
Verified directly at the cited lines.

## Major findings

- **I-3 (reconciler):** After a replace-build has staged episodes, a source
  that vanishes or goes malformed mid-build still activates the partial
  generation (`reconcile.py:613-621` guards only on empty staging count) and
  supersession finalization deletes the complete old generation — search then
  serves a partial index as `available` with zeroed `indexed_through`.
- **I-4 (reconciler):** A malformed complete record is skipped by the next
  append build: `complete_end` is advanced past it before parsing
  (`adapters.py:216`), append resumes from `complete_end`
  (`reconcile.py:327`), and the successful chunk clears `error_position` —
  the visible failure the spec requires is erased until a whole-member audit
  rediscovers it.
- **I-5 (reconciler):** Mid-record truncation stalls the whole-member audit
  forever: the `INCOMPLETE` early return (`reconcile.py:845-864`) preempts the
  truncation-mismatch check (`:806-808`), so vanished content remains indexed
  and searchable indefinitely and the member never reaches `stale` or rebuild.
- **I-6 (reconciler):** The audit compares episode-reference sequences only
  (`reconcile.py:799-808,953-957`). A byte-shifting rewrite with identical
  canonical content (blank line prepended, reserialized whitespace) certifies
  the audit while every stored byte position is stale; subsequent tail scans
  read from mid-record offsets and report a spurious `malformed` on an intact
  file.
- **I-7 (reconciler):** The bounded allowance meters only source bytes. Every
  search fetches all generation documents for every member
  (`_active_generation_backed`, full bodies, should be a count), append builds
  seed-copy the entire active generation regardless of budget
  (`reconcile.py:518-531`), and audits refetch active documents per chunk —
  O(total indexed episodes) of uncharged database work per search,
  contradicting "routine append reconciliation advances indexing cheaply."
- **I-8 (reconciler):** Genuinely parallel ArangoDB writers raise uncaught
  write-write (1200) and unique-constraint (1210) exceptions instead of
  degrading to `_StateConflict`; the CAS interleaving tests inject only
  sequential conflicts via adapter hooks, so the real-parallelism mode is
  unexercised. Multiple concurrent MCP sessions are the normal deployment.
- **I-9 (adapters/enrollment):** A declaration may select
  `boundary_version`/`canonicalization_version` values the adapter does not
  implement (`enrollment.py:59-62`); the adapter stamps them into identity
  while always executing v1 (`adapters.py:105-113`), minting falsely-versioned
  identities. The test helper itself declares fictional versions 2/3.
- **I-10 (adapters):** A deeply nested JSON record raises `RecursionError`,
  which is absent from the scan's catch list (`adapters.py:221-225`) and from
  `open_episode`'s `OSError` handling — a single pathological line crashes
  scan, search, and opening instead of producing `malformed` with a position.
- **I-11 (adapters):** The Claude Code adapter reports a merely-incomplete new
  session file (partial first line, no `sessionId` yet) as `MALFORMED`
  (`adapters.py:499-519`); the spec's complete-record boundary requires
  `incomplete`. The three adapters also disagree on empty-file semantics.

## Minor findings

- **I-12:** `open_episode` reconstructs under the enrollment's current
  versions, never the reference's recorded boundary version
  (`history.py:152-185`) — latent while only v1 exists; after any version bump
  every old reference degrades even when the recorded-version reconstruction
  would verify.
- **I-13:** The supersession lookup swallows every exception
  (`history.py:141-142`), silently degrading `superseded` to
  `missing`/`content_mismatch` on a transient database failure — the spec
  permits that degradation only after purge.
- **I-14:** A corpus with an unavailable index still reports
  `indexed_matches: 0` alongside `match_standing: unknown`
  (`history.py:356-361`); the spec says no fabricated zero.
- **I-15:** `_mark_due_audit` demotes a shrunk file to `tail_validated`
  (should be `stale`), and an audit completing over a member that grew during
  restart publishes `tail_validated` though the grown tail was never
  validated (`reconcile.py:1040-1089`).
- **I-16:** The exported `reconcile_member` entrypoint omits expired-audit
  demotion, reporting stale `current` under budget exhaustion
  (`reconcile.py:1274-1291`).
- **I-17:** Wrong-typed evidence fields (dict/int `user_message`, bool
  `cycle`) are silently accepted into evidence bodies instead of `malformed`
  (`adapters.py:307-316,374-381,479-486`; `EpisodeBody` validates nothing).
- **I-18:** TOCTOU between the reconciliation standing snapshot and the count
  query: a concurrent activation plus old-generation deletion between
  `active_states` and the AQL search can yield `total_standing: exact` for a
  generation that no longer exists (`history.py:309-335`).
- **I-19:** Gateway synthesized-sequence state increments before record
  validation completes and the poisoned cursor is persisted
  (`adapters.py:360-368`) — currently unexploitable, but identity rests on a
  non-local invariant.
- **I-20:** A vanished/non-directory Claude Code locator degrades to a single
  phantom file member instead of a source-set enumeration failure
  (`adapters.py:407-423`), manufacturing a spurious state row.
- **I-21:** Reconciliation runs only before search; the spec also requires it
  at service startup. Declared unestablished in the evaluation record.

## Notes

- `open_episode` is O(corpus): it fully scans every member and materializes
  all episodes to resolve one reference — declared unestablished; also means
  I-10's pathological line kills every open.
- taste_open bodies carry the activity log twice (inside `state` and as
  `activity_log`); deterministic, so no identity hazard, but inconsistent
  field semantics.
- A duplicate native event id with *different* content coexists as two
  distinct openable references — digest rule satisfied, but the reuse is
  surfaced nowhere.
- Enormous single lines are read whole into memory (documented by test).
- MCP request errors surface as raised exceptions through FastMCP rather than
  structured request-error payloads — acceptable at this layer, worth a
  deliberate choice later.
- The legacy `ingest.py` change is a behavior-preserving refactor to a shared
  `turn_text` helper; legacy tools gain no capability, consistent with the
  migration posture.

## Clean areas verified

Identity construction and reversible canonical encoding match the spec
exactly, including re-encode verification and full untruncated digests.
Canonicalization covers exactly the seven evidence-body fields; absent
optionals are explicit, never synthesized; gateway prompt-only records stay
prompt-only. Enrollment authority is local-only and never inferred from
directories or database state (test-enforced); the real config is gitignored;
Codex cannot be declared. The append-only compatibility exception is confined
to implementation-change audits; ordinary audits require exact generation
snapshots and restart on change. Partial trailing records are never parsed;
reads are bounded by the post-open size snapshot against concurrent appends.
Search filters to per-member active, fully-backed, integrity-valid
generations; activation recounts staged documents under CAS; missing/malformed
initial sources cannot activate phantom empty generations. Supersessions are
derived operational state with reason and detection time, a separately named
purge class, and no source authority. No code path writes to a source log
(all adapter access is read-only + stat; the only writes are the atomic
enrollment-config replace and Arango documents). Per-source failure isolation
and affected-source-only rebuilds hold. Exact counts are computed before
`SLICE` and are limit-independent; degraded scope poisons `exact` at corpus
and aggregate levels; deterministic ordering ties break on the qualified
reference. Lifecycle disable/unenroll/purge match their declared distinctions
and never touch sources or the legacy collection.

## Benefit judgment

This stage delivers the ayllu's first honest episodic access: a fresh instance
can search conversation history it never lived through and open the exact
source-backed evidence, with standing that admits what the index does not
know. qhaway remains the small curated projector it was — untouched, green,
and still removable — and the second indexed copy of conversation data now has
a named, tested purge path, which is the obligation that indexing sensitive
material was always going to create. The cost is real: three new collections,
a view, generation state, audits, and an Arango dependency whose production
behavior is still unmeasured. That cost is exactly what Stage 2's peer-backend
comparison exists to interrogate, and this implementation gives it a
measurable baseline to compare against. The work earns continuation; it does
not yet earn contact with a real corpus.

## Disposition

- **I-1, I-2:** repair before any real-corpus enrollment; add the duplicate
  line and crash-window freshness fixtures the suite lacks.
- **I-3 through I-8:** repair before the Stage 1 decision record's gate rows
  (2, 5, 7, 8, 11) are cited as durable evidence; each needs a regression
  fixture for the currently untested path.
- **I-9 through I-11:** repair with the same round (I-9 is a one-check fix in
  the registry or adapter).
- **I-12 through I-21 and notes:** absorb into the repair round or record as
  declared limitations at the author's judgment.
- Re-run the evaluation's affected rows after repair and append an addendum,
  as the prior repair addendum did.
