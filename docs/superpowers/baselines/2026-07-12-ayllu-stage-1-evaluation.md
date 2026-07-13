# Ayllu Stage 1 Episodic Contract Evaluation

**Umbrella:** `docs/superpowers/specs/2026-07-10-qhaway-ayllu-memory-design.md`
**Focused specification:** `docs/superpowers/specs/2026-07-12-ayllu-stage-1-episodic-contract-design.md`
**Plan:** `docs/superpowers/plans/2026-07-12-ayllu-stage-1-episodic-contract.md`
**Observed:** 2026-07-12
**Boundary:** Stage 1 contract evidence only; no backend selection or Stage 2 implementation

## Revisions and Evidence Classes

| Surface | Reviewed revision | Standing |
|---|---|---|
| `llm-memory` Stage 1 | `e95e32fbc739a4f5d3e21131b506472214346ce2..5e6be56615956b2ec217958f797c682276ead24e` | Isolated worktree on `feature/ayllu-stage1-contract`; includes the final pending-tail transition and staging-ownership repair |
| qhaway evidence parent | `c8c016352457380cf647a7a20ae8a3fed7b7497a` | Clean on `design/ayllu-stage-1-episodic-contract` before this record |
| ArangoDB | Locally configured service, contract collections, and ArangoSearch view reachable | Used only for implementation tests and the synthetic evaluation corpus |

Evidence in this record has three deliberately separate classes:

- **Implementation test evidence** is repeatable synthetic evidence from the
  committed suites. It establishes contract mechanics, not real retrieval
  usefulness.
- **Observed real-source evidence** requires a concrete, owner-controlled,
  supported enrollment. No such enrollment was available.
- **Declared limitations** identify behavior that neither passing tests nor an
  unavailable journey can establish.

The original `llm-memory` worktree was not modified. Its
pre-existing unstaged `pyproject.toml` and `uv.lock` changes remained present,
and their combined diff digest remained
`9fef9719b4cb9e426750097cb41e21c4f365490f6ef0d112c5e3cc526f094792`,
the Stage 0 value. The isolated worktree's local ignored database-config
symlink was used for evaluation and was not committed.

## Verification

| Evidence | Result | Interpretation |
|---|---|---|
| Corrected evaluation runner at `ea4e3ae` | `2 passed in 0.36s` | The focused journey output test passed with inclusive operation timing and unavailable isolated provider-query timing; atomic redaction, counts, standing, work, index growth, purge evidence, and limitations remained covered |
| Historical focused Stage 1 slice at `0799d7e` | `164 passed in 11.07s` | Pre-correction identity, enrollment, adapters, contract index, reconciliation, search, opening, lifecycle, MCP, and journey behavior passed together; this row is not attributed to the corrected endpoint |
| Historical complete `llm-memory` suite at `ea4e3ae` | `180 passed in 8.69s` | Pre-repair endpoint evidence retained for chronology; it is not the final verification result |
| Complete qhaway suite at the evidence parent | `137 passed in 12.31s` | Existing curated-memory behavior remained green |
| Final reconciliation repair suite at `5e6be56` | `203 passed in 19.65s` | Focused regressions and the complete `llm-memory` suite passed after pending-tail transition, compatibility completion-window, prefix progress, derived-loss, staging-publication CAS, and crash recovery repairs |
| Final qhaway validation before repair-addendum commit | `137 passed in 11.79s` | Existing curated-memory behavior remained green with the final repaired Stage 1 evidence record |
| Arango cleanup | Contract episodes `0`; reconciliation states `0`; supersessions `0` for the evaluation corpus after purge | The test corpus left no derived documents |
| Source immutability | Synthetic source SHA-256 was identical before and after the journey and purge | Derived lifecycle operations did not modify the authoritative source |

The runner writes a same-directory temporary file, flushes and fsyncs it, and
uses `os.replace`. Purge is absent by default, requires the explicit
`--purge-test-corpus` flag, and rejects every corpus identifier that does not
begin with `test-` before reconciliation or database mutation.

The qhaway timing cited in the table is the clean precommit run. A separate
preliminary clean run reported 137 passed in 12.65s; it is not the timing used
for the committed evidence row.

## Synthetic Journey

The committed journey test uses a temporary supported `taste_open_jsonl`
enrollment. A separate non-content report was written outside both repositories
for the measured run. No episode text, raw line, query text, locator, database
credential, enrollment identifier, timestamp, or qualified reference is
included here.

| Observation | Result |
|---|---|
| Query bound | `limit=1`; query represented only by SHA-256 and length |
| Result and population | 1 returned; 2 indexed matches; total standing `exact` |
| Per-member standing | Source `available`; index `available`; freshness `current`; validation age recorded (`0.165s` in this run) |
| Preflight reconciliation | 984 bytes; 69.627ms; not exhausted; measured separately from the public search operation |
| Automatic reconciliation plus search/count operation | 77.257ms inclusive of the automatic pre-search reconciliation and provider search/count work; the automatic reconciliation read 0 bytes in this run because preflight was current |
| Provider search/count query latency | Unavailable and declared `unavailable_not_instrumented`; it is not manufactured from the inclusive operation timing |
| Exact opening | Expected-reference digest matched; standing `available`; authoritative content digest retained; content omitted |
| Additional indexed projection | 2 documents; 2,046 serialized AQL-representation bytes |
| Selective purge | Episodes 2; reconciliation 1; supersessions 0 |
| Post-purge standing | All three contract collections contained zero documents for the test corpus |

The additional-byte figure is a portable report of the documents' AQL string
representation, not Arango storage-engine disk consumption, index segment
size, or resident memory.

## Contract Perturbations

Implementation tests establish the following perturbation behavior:

- Taste Open, gateway, and Claude Code adapters produce qualified identities
  from their documented native session and event shapes.
- Implementation-version-only changes preserve references. Content,
  canonicalization-version, and boundary-version changes cannot silently reuse
  a reference for different evidence.
- Byte-identical relocation preserves identity. Semantic changes create a new
  generation, and retained supersession observations can resolve an old
  reference without becoming source authority.
- Multiple adapters in one corpus, multiple corpora, and multi-member source
  sets preserve separate corpus, source, and member standing.
- Append, partial tail, malformed record, truncation, prefix rewrite, vanished
  member, version change, and failures between write, activation, and
  supersession finalization retain explicit resumable standing.

## Standing, Counts, and Integrity

Search requires concrete, unique corpus identifiers. Responses separately
carry source-set standing, member source standing, member index standing,
freshness, indexed-through position, observed source end, integrity basis, and
validation age. Tests keep stale, `tail_validated`, and incomplete indexes
searchable only while that standing remains visible.

With all requested indexes available, `limit=1` returned one result while
reporting an exact indexed population of three in the focused count test and
two in the measured journey. When one member index is unavailable, existing
hits remain usable but per-corpus and aggregate population standing becomes
`unknown`; partial scope cannot appear exact.

Whole-member audits record full-digest basis, chain and count comparisons,
bytes read, audit offset, validation time, and restart count. Expired
validation becomes `tail_validated` while bounded audit work is incomplete.
Prefix rewrites are detected by the next completed whole-member audit; the
detection interval is bounded by the enrollment's
`full_validation_max_age_seconds` plus the number of bounded invocations needed
to scan the source. The synthetic enrollment used 3,600 seconds. This work is
O(source bytes), remains visible, and is never described as constant-time.

Automatic bounded reconciliation **does converge under observed synthetic
source growth**: append and bounded relocation tests advance across repeated
budgets to `current`, and search reconciles newly appended data before its
population query. No real-source growth was available, so convergence under a
real workload, its arrival rate, and its long-run cost remain unobserved.

## Opening and Lifecycle

`open_episode()` re-reads the enrolled authoritative source and verifies the
qualified identity and content digest. Available opening succeeds without
Arango content fallback. Missing, malformed, unavailable, unsupported, and
content-mismatched source states return standing without episode content; a
retained Arango document cannot substitute for a missing source.

Disable atomically preserves the declaration and source while revoking new
search. Unenroll removes authority but retains derived data. Purge deletes only
the explicitly selected derived classes within corpus and optional source
scope, never the legacy collection or authoritative logs. Re-enrollment
validates retained state and rebuilds when source or semantic versions require
it. Purging supersession evidence intentionally reduces old-reference standing
and reports that loss honestly.

## Real-Source Standing

Observed real-source standing is **unavailable**. There was no
owner-controlled `config/sources.yaml` with an enabled supported enrollment, so
no real source was scanned, indexed, queried, opened, or purged. Synthetic
success is not substituted for real-source evidence.

The historical five-query Stage 0 evaluation also remains **unavailable**.
Its named cycle-addressed source episodes were not concretely enrolled under a
corpus identifier. It was therefore not replayed, re-ingested, or recast as a
Stage 1 success. Its prior 0/5 standing remains a source-fixture unavailability,
not a semantic retrieval verdict.

## Arango Operational Dependencies

The Stage 1 Arango provider requires a reachable ArangoDB service, valid local
database configuration, collection and view administration privileges, three
contract collections, the `episodic_contract_search` ArangoSearch view, the
`text_en` analyzer, and permission to reconcile derived state before search.
It also retains active and sometimes staging generations during crash-safe
replacement. These are operational costs separate from the 2-document / 2,046
byte synthetic projection measurement.

No credential is included in the runner output or this record. This stage did
not measure server disk amplification, view-segment growth, memory use,
compaction, backup cost, or behavior during an Arango outage. Those costs are
reasons to compare a peer backend, not evidence that Arango is superior.

## Evaluation Dimensions

| Dimension | Finding | Evidence | Declared limitation |
|---|---|---|---|
| Fidelity | Versioned adapters and source-backed opening preserve the documented evidence and verify its digest | Adapter identity tests; exact opening; source digest preservation | No real corpus or human relevance judgment was available |
| Declared loss | Partial tails, malformed sources, unavailable indexes, heuristic match attribution, redacted output, and purged supersession standing are explicit | Adapter, search, opening, lifecycle, and journey tests | Adapter-specific extraction omits events outside each documented episode boundary |
| Selectivity | Concrete corpus scope, bounded results, deterministic ordering, and limit-independent exact counts are enforced | Search request and population tests; measured 1-of-2 journey | Dynamic facets, pagination, semantic filtering, and inferred scope are deferred |
| Dissent retention | Old evidence can remain addressable through supersession observations while changed evidence receives a new identity | Reconciliation and supersession-opening tests | Stage 1 does not interpret disagreement or implement curated conflict envelopes |
| Provenance | Qualified references bind corpus, source, native session/event identity, semantic versions, and body digest; opening returns source-derived provenance | Contract, adapter, index, and opening tests | Serialized evaluation retains only digests and standing by design |
| Continuity | Append, relocation, bounded resume, disable, unenroll, purge, and re-enroll have distinct resumable behavior | Reconciliation and lifecycle suites | Cross-framework delivery and federation are not Stage 1 capabilities |
| Isolation | Contract collections are isolated from the legacy index and queries/purges are corpus scoped | Contract-index, search-scope, and lifecycle tests | Corpus scope is not an authorization boundary |
| Recoverability | Incomplete generation writes, state-patch failures, activation failures, and audit changes resume without exposing mixed generations as current | Contract-index and reconciliation crash-recovery tests | Recovery still depends on the authoritative source and a reachable Arango service |
| Unobtrusiveness | No daemon is required; bounded reconciliation runs before search and exposes incomplete work | Search/reconciliation tests and work measurements | Explicit enrollment, database configuration, and Arango operation remain required |
| Generativity | Not observed | Historical fixture retained; real-source journey classified unavailable | Synthetic lexical hits do not establish useful new connections or semantic quality |
| Complexity | The contract makes identity and standing explicit but adds adapters, registry, three collections, one view, reconciliation state, audits, and lifecycle operations | Implementation history, dependency inventory, measured projection and purge | Total production storage and operator cost remain unmeasured |

These dimensions are independent. No aggregate score is calculated.

## Declared Losses and Limits

- Gateway evidence follows its documented request-event boundary; Claude Code
  evidence includes assistant prose episodes and omits non-episode events.
- Snippets and match attribution are bounded heuristic projections, not
  authoritative source opening.
- Exact counts describe the available indexed population. Degraded scope is
  `unknown`. Search and count share a provider request, but that request's
  isolated latency is unavailable because the measured public operation also
  includes automatic reconciliation.
- Evaluation output deliberately removes content, raw lines, query text,
  identifiers, locators, timestamps, credentials, and raw qualified references.
- Codex support, federation, bilateral withdrawal, cross-project authorization,
  semantic retrieval, and backend superiority remain deferred or unestablished.
- Real-source retrieval quality, real growth convergence, and production Arango
  resource amplification were not observed.
- Compatibility auditing treats same-inode monotonic growth beyond its fixed
  trusted prefix as append-only. An external writer that mutates already-scanned
  prefix bytes in place and appends before observation can evade that model;
  append-only discipline, atomic replacement, coordination, or filesystem
  snapshots are required. Ordinary whole-member audits retain exact generation
  snapshot checks and are not covered by this exception.

## Acceptance Gates

| Gate | Standing | Evidence |
|---:|---|---|
| 1 | Evidenced | Taste Open, gateway, and Claude Code documented identity tests |
| 2 | Evidenced | At `5e6be56`, bounded compatibility audits retain fixed-prefix progress, publish final-stat tail standing, and admit pending tail only for the same published file with monotonic growth; shrink/replacement/disappearance take conservative replacement paths |
| 3 | Evidenced | Byte-identical relocation and retained source-verified supersession tests |
| 4 | Evidenced | Versioned requests/responses require concrete corpora and retain source/member standing |
| 5 | Evidenced | Limit-independent exact aggregate/per-corpus counts; incompatible or unbacked active generations make index and population standing `unknown`, while an available empty source remains exact-empty |
| 6 | Evidenced | Source set, member source, index, freshness, and indexed-through fields tested separately |
| 7 | Evidenced | Stale, `tail_validated`, and incomplete indexes remain usable only with visible age/standing |
| 8 | Evidenced | At `5e6be56`, pending-tail generation identity distinguishes append from shrink, inode replacement, disappearance, and same-size mutation while retaining rewrite restart, CAS, and crash recovery |
| 9 | Evidenced | Expected-reference opening re-reads source and verifies content digest |
| 10 | Evidenced | Negative opening standings expose no derived fallback or content |
| 11 | Evidenced | Automatic pre-search reconciliation and repeated bounded synthetic growth converge to `current` |
| 12 | Evidenced | Disable, unenroll, selective purge, and re-enroll distinctions preserve source bytes |
| 13 | Evidenced | Arango dependencies and measured additional 2-document / 2,046-byte projection reported separately |
| 14 | Evidenced | Final endpoint `5e6be56`: complete `llm-memory` suite 203 passed; repair-focused storage/reconciliation/search/lifecycle slice 85 passed; qhaway companion suite 137 passed |

All fourteen gates have implementation evidence. Gate 11 is limited to
observed synthetic growth, and gate 13's byte measurement is not physical
storage usage; those limitations are declared rather than treated as failures
of the contract gate.

## Stage Decision

**Decision: continue**

Stable identity and explicit standing were the principal Stage 0 problems, and
Stage 1 resolves them across all fourteen acceptance gates. A Stage 2 peer
backend comparison is warranted because the Arango implementation now has a
measurable, reviewable contract but retains meaningful service, indexing,
reconciliation, and removal costs. This decision authorizes consideration of
that comparison only. It does not establish semantic retrieval quality, select
a backend, or authorize Stage 2 implementation automatically.

## 2026-07-12 Final Review Repair Addendum

Revision `5e6be56615956b2ec217958f797c682276ead24e` repairs the final
whole-branch review findings without widening Stage 1 startup, scan, or opening
scope.

- **Gate 2 remains evidenced.** An implementation-version audit whose
  canonical identities change under unchanged semantic versions now preserves
  the old active generation and references, reports the member index
  unavailable, and records implementation incompatibility. Repeated audits do
  not replace it. A canonicalization- or boundary-version change is required
  before changed output can activate. A compatible implementation-only audit
  retains the active generation, current standing, and provenance version.
  The final repair validates the previously indexed prefix before tail or
  derived-loss activation when an implementation change and append are first
  observed together. This validation is bounded and resumable; trusted prefix
  chain/count evidence supports derived-loss validation without treating
  missing derived documents as compatible output. Repeated valid appends beyond
  the fixed trusted boundary no longer restart a bounded compatibility cursor;
  the accumulated tail is processed only after prefix compatibility succeeds.
  If a tail append lands after the final prefix scan snapshot but before the
  final stat, completion publishes that final size/generation and
  `tail_validated`, not stale-snapshot `current`; the next bounded call ingests
  the tail without changing established prefix identities.
  Before that next call, reconciliation compares the live generation with the
  published final generation. Only same-inode monotonic growth remains append
  work. Shrinkage, inode/device replacement, disappearance, and same-size
  mutation invalidate the old active generation for search and schedule a
  replacement from byte zero; missing or malformed replacement cannot activate
  a phantom empty generation.
- **Gate 5 remains evidenced.** Availability now requires the stored active
  generation population to equal its recorded episode count. Episode-only
  derived purge is rebuilt before exact search is reported; otherwise index and
  total standing remain unknown. A missing, unavailable, or wholly malformed
  initial source cannot activate a phantom empty generation, while an
  available empty source can still establish exact-empty standing.
- **Gate 8 remains evidenced.** Audit and build transitions use guarded
  compare-and-set updates tied to the state revision, active/build generation,
  and build cursor. Deterministic interleaving tests show stale audit evidence
  cannot certify a competing activation and stale build work cannot overwrite
  competing progress. Failed guards defer work instead of publishing stale
  freshness. Generation staging publication now uses the same revision,
  active/build generation, cursor, and prior staging-owner guard. A stale
  worker may leave inert deterministic documents but cannot move staging
  ownership or counts. Replacement clears abandoned staging metadata, and a
  zero-document generation remains stageable and recoverable after an
  activation crash.

  Prefix stability uses device/inode identity, the frozen trusted byte end,
  and monotonic size. Same-inode growth beyond that end is treated as
  append-only; truncation, atomic replacement, same-size mtime change, and
  canonical mismatch restart or quarantine the audit. An external writer that
  mutates already-scanned prefix bytes in place and appends before the next
  observation can evade this model. Preventing that case requires writer
  coordination or filesystem snapshots and remains an explicit operational
  assumption rather than an unbounded reread on every bounded call.

- **Gate 14 remains evidenced.** At `5e6be56`, the focused storage,
  reconciliation, search, and lifecycle slice passed `85` tests in `16.27s`
  and the final complete `llm-memory` suite passed `203` tests in `19.65s`. The qhaway
  companion suite remains 137 tests. The earlier 180-test row is retained only
  as historical pre-repair evidence.

The final repair suite passed `203` tests in `19.65s`; the qhaway companion suite
passed `137` tests in `11.79s`. Test-derived Arango rows were zero afterward in
the episodes, source-state, and supersession collections. The original
`llm-memory` worktree remained limited to its two pre-existing dependency files
with diff digest
`9fef9719b4cb9e426750097cb41e21c4f365490f6ef0d112c5e3cc526f094792`.

Task 12's concrete synthetic source immutability evidence is incorporated as
digests:
`source_before_sha256=cf10468e288be56a717631e3e261171641b75f08cafa8c06158e6fc0d56d6bf3`
and
`source_after_sha256=cf10468e288be56a717631e3e261171641b75f08cafa8c06158e6fc0d56d6bf3`.
Their equality establishes that the measured journey and purge did not alter
the authoritative synthetic source.

**Revised decision: continue.** The repaired gates support proceeding to
consider a Stage 2 peer-backend comparison. Real-source retrieval quality,
provider resource amplification, startup reconciliation, bounded opening, and
backend selection remain unestablished and are not authorized by this record.

## 2026-07-13 Independent Implementation Review Repair Addendum

The independent review at
`docs/superpowers/specs/2026-07-13-ayllu-stage-1-implementation-review.md`
identified two blocking, nine major, and ten minor implementation findings at
`5e6be56`. Repaired llm-memory endpoint
`55558d8b5d5d632c908e28d7326a836ca6b1335e` closes the findings that could
invalidate Stage 1 standing. The focused contract architecture and authority
boundary did not require revision.

- **Gate 2 remains evidenced.** Duplicate references with different source
  positions now become positioned malformed-source failures instead of
  uncaught generation-document errors. Replace builds cannot activate after a
  source becomes missing, malformed, incomplete, or shorter than its accepted
  end; the complete active generation remains available with degraded source
  standing. A malformed record does not advance the accepted cursor. Audits
  compare reference and byte-position triples, so content-equivalent byte
  shifts cannot certify stale opening positions.
- **Gate 5 remains evidenced.** Search selects active, fully backed,
  integrity-valid generations inside the same AQL request that computes
  results and counts. There is no state-read/query TOCTOU interval. When any
  member index in a corpus is unavailable, per-corpus `indexed_matches` and
  aggregate `total_matches` are JSON `null` with `unknown` standing; returned
  defensible hits do not manufacture a zero or an exact population.
- **Gate 7 remains evidenced.** Build and tail observations persist only
  `incomplete`, `stale`, `unknown`, `unavailable`, or `tail_validated`; only a
  completed whole-member audit publishes `current`. Activation conflict cannot
  leave a tail-only observation current. Shrink is stale, and bytes observed
  beyond an audited end but not yet parsed are incomplete rather than
  tail-validated.
- **Gate 8 remains evidenced.** Eight concurrent generation writers with
  independent Arango handles reproduced unique error 1210 before repair, and
  eight concurrent reconcilers reproduced write/write error 1200. Publication
  now accepts only identical deterministic insert winners and translates 1200
  or 1210 at state/generation boundaries into retryable contract conflicts.
  Live parallel tests and all prior crash/CAS tests pass.
- **Gate 11 remains evidenced.** FastMCP lifespan performs one bounded startup
  reconciliation when enrollment configuration exists. Missing configuration
  leaves the legacy service loadable and does not pretend contract enrollment.
  Pre-search reconciliation remains bounded. Direct `reconcile_member()` now
  performs the same expired-audit demotion before exhausted work can preserve a
  stale current claim.
- **Gate 14 remains evidenced.** The affected Stage 1 slice passed `223` tests
  in `30.73s`; the complete llm-memory suite passed `237` tests in `31.82s`;
  the qhaway companion suite passed `137` tests in `14.15s`. Contract episodes,
  source states, and supersessions each counted zero after verification. Both
  full ranges passed `git diff --check`. The original llm-memory checkout still
  contains only its owner-controlled `pyproject.toml` and `uv.lock` changes at
  the unchanged combined diff digest
  `9fef9719b4cb9e426750097cb41e21c4f365490f6ef0d112c5e3cc526f094792`.

Findings I-1 through I-6, I-8 through I-11, and I-13 through I-21 are repaired
and regression-tested. I-12 is deferred without exposure: all installed
adapters reject semantic versions other than `(1, 1)`, and enabling a later
version is gated on opening historical references with their recorded
algorithm. I-7 is partly a measured implementation cost, not a correctness
claim: backing checks use counts, audit chunks use position-bounded reads,
append seeding occurs server-side, and routine append finalization avoids full
supersession scans, but immutable Arango generation cloning remains O(active
generation documents). `WorkBudget` meters authoritative source bytes and does
not mislabel that database work as byte-bounded. Stage 2 must compare this cost
against the peer backend.

**Active implementation decision: continue.** Stage 1 is mergeable after broad
final review. This continues to authorize consideration of a Stage 2 peer
backend comparison only; it does not authorize real-corpus enrollment, choose a
backend, or establish retrieval usefulness.
