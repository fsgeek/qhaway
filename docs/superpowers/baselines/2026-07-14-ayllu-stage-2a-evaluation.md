# Ayllu Stage 2A SQLite Provider Evaluation

**Observed:** 2026-07-14
**Boundary:** Phase A synthetic provider mechanics only
**Standing:** `ready_for_phase_b_authorization`

## Revisions and Review

| Surface | Reviewed revision | Standing |
|---|---|---|
| `llm-memory` Stage 2A base | `fcc19b097e7f2353a8a6e11e8b2c146bbb61b1b6` | Reviewed descendant of the required Stage 1 mainline |
| Initial Tasks 1-11 endpoint | `90802cd536267a488c389cd9b83113c905ebc121` | Complete before Task 12 verification |
| SQLite removal repair | `02c878c7223848595fb369952332ef450f6305a2` | Final reviewed endpoint; open-handle removal defect repaired with regressions |
| qhaway evidence parent | `93d9aa198acdebf5abaa28fbf457fa49e75a82af` | Stage 2A plan commit; clean before this checkpoint |

The complete `fcc19b0..02c878c` diff received independent review after the
Task 12 repair. The reviewer reported no remaining Critical, Important, or
Minor findings. Their complete suite rerun reported `426 passed, 1 skipped in
38.53s`; the skip was the guarded disposable-Arango full-removal journey.

## Verification

| Evidence | Exact result | Interpretation |
|---|---|---|
| `git diff --check $(git merge-base main HEAD)..HEAD` | Exit 0; merge base `fcc19b097e7f2353a8a6e11e8b2c146bbb61b1b6` | No whitespace errors across the complete Stage 2A range |
| Repository lint command | `not configured` | `pyproject.toml` contains pytest configuration but no lint command |
| Repository type command | `not configured` | No type-check command was invented |
| Complete `llm-memory` suite at `02c878c` | `426 passed, 1 skipped in 38.08s` | All executable provider, evaluation, and compatibility tests passed |
| Focused lifecycle/concurrency/portable slice | `38 passed, 1 skipped in 9.42s` | SQLite removal repair, concurrency, and both provider fixtures passed; guarded Arango removal skipped |
| Complete qhaway suite at `93d9aa1` | `137 passed in 12.83s` | Existing curated-memory behavior remained green |
| Python runtime | `3.14.3` | Runtime used by final verification |
| SQLite runtime | `3.50.4` | Standard-library SQLite used by the provider |
| `sqlite_compileoption_used('ENABLE_FTS5')` | `1` | Compile-time FTS5 declaration is present |
| Portable FTS5 probe | Available; one matching row | Create, insert, query, and drop succeeded with `porter unicode61 remove_diacritics 2` |

The final-endpoint concurrency command ran `tests/test_sqlite_concurrency.py`
five times. Each run executed three tests successfully: `3 passed in 0.44s`,
`3 passed in 0.39s`, `3 passed in 0.39s`, `3 passed in 0.33s`, and `3 passed
in 0.36s`. Every run used eight worker threads, separately instrumented SQLite
connections, bounded futures, a lock-timeout journey, and a subprocess crash
journey.

The original `/home/tony/projects/llm-memory` checkout remains at
`fcc19b097e7f2353a8a6e11e8b2c146bbb61b1b6` with only its pre-existing
unstaged `pyproject.toml` and `uv.lock` changes. Their combined diff digest is
unchanged at
`9fef9719b4cb9e426750097cb41e21c4f365490f6ef0d112c5e3cc526f094792`.
Those files were not modified, staged, restored, or committed by Stage 2A.

## Provider Descriptors

| Field | Arango | SQLite |
|---|---|---|
| Provider/version | `arango` / `1` | `sqlite` / `1` |
| Strategy | `lexical_bm25_text_en_v1` | `lexical_bm25_fts5_porter_unicode61_v1` |
| Analyzer/tokenizer | `text_en` | `porter unicode61 remove_diacritics 2` |
| Indexed fields | `user_message`, `response`, `state_text` | `user_message`, `response`, `state_text` |
| Match semantics | `analyzed_any_token` | `analyzed_any_segment_phrase` |
| Public ordering | `higher_is_better` | `normalized_desc_episode_ref_asc` |
| Raw score polarity | `higher_is_better` | `lower_is_better`; exposed publicly as `-bm25()` |

Provider-local BM25 magnitudes are not compared. No aggregate score, backend
winner, fallback, or production default is produced by this checkpoint.

## Synthetic Scope and Readiness

The portable fixture uses temporary synthetic `taste_open_jsonl` sources only:
an enabled primary source, enabled secondary source, available-empty source,
disabled declaration, and a separately scoped sentinel corpus. It exercises
bounded reconciliation and resume, deterministic bounded search, exact or
unknown population standing, source-backed opening, equal-length rewrite and
supersession, disable and re-enable, unenroll with retained derived state,
selective purge, rebuild, provider strategy rejection, and source-byte
preservation. Temporary identifiers are unique to each test run.

Startup selection is explicit. The runtime constructs only the configured
provider, calls `ensure()`, then performs one bounded reconciliation with a
1,000,000-byte work budget before publishing the contract runtime. SQLite
startup does not connect to Arango. Missing enrollment configuration keeps the
legacy service available but does not manufacture an active contract runtime.
Nested or failed lifespans cannot overwrite or leak runtime ownership.

Arango tests assume a reachable configured service with permission to use the
shared contract collections and ArangoSearch view. Configured credentials could
not list or provision a uniquely owned disposable database (`HTTP 401 not
authorized`). Arango full removal therefore remains unverified in this
environment. The shared Arango fixture never calls `remove_all()`.

## Count and Lifecycle Evidence

SQLite count and result statements share one read transaction. In the focused
snapshot regression, another connection committed a second matching document
between the grouped count and result statements. The in-flight response
retained the original snapshot: `total_matches=1`, `returned_count=1`, and the
original result. A later transaction observed two documents. Partial or
unbacked requested scope reports `unknown` with null counts rather than exact
zero.

The shared lifecycle fixture records exact primary counts of three episode
documents, one source-state document, and one supersession observation.
Selective purge removes exactly three episodes and one reconciliation record,
retains the selected supersession observation, and leaves sentinel counts of
one episode, one source state, and zero supersessions unchanged. Source-backed
rebuild restores the primary `3/1/1` counts for both providers.

SQLite full removal creates and removes the configured database, WAL, and SHM
artifacts, reports no residual paths, retains enrollment configuration and
source locators, and declares loss of retained supersession observations and
non-reproducible evaluation state. After the Task 12 repair, a successful
removal first invalidates provider-owned tables transactionally and checkpoints
the WAL. An idle pre-existing handle can no longer read derived rows. An active
pre-removal snapshot prevents unlink, produces explicit residual paths and
reasons, and permits a successful retry only after the reader closes.

The SQLite FTS representation is explicitly
`self_contained_duplicate`: searchable `user_message`, `response`, and
`state_text` are duplicated in the FTS5 table. Measurements report database,
WAL, and SHM bytes and stat standing separately. Provider database-only work
units remain `not_measured` because the contract exposes no defensible separate
unit; source-byte charges and inclusive elapsed time are not relabeled as that
work.

The public synthetic evaluation runner does not receive disposable ownership
proof and therefore never calls `purge()` or `remove_all()`. Its purge, rebuild,
and full-removal execution fields remain unavailable while fixed declared-loss
tokens stay visible. Portable lifecycle tests provide the destructive SQLite
evidence. Arango full-removal residual counts remain unavailable until explicit
test credentials can create and delete a uniquely owned disposable database.

## Repaired Defects

Review-driven repairs before the checkpoint include SQLite runtime and schema
classification, exact schema ownership, stale generation activation,
reconciliation audit/staging transitions, lifecycle invalidation and path
policy, MCP lifespan ownership and sole-strategy validation, NUL query
rejection, portable-fixture ownership guards and concurrency instrumentation,
and malformed evaluation-measurement containment.

Task 12 independent review then found that pathname unlink could report zero
residuals while an existing SQLite handle still read derived state. Commit
`02c878c` added two reproducing regressions and repaired full removal with
transactional provider-content invalidation plus a required truncating WAL
checkpoint. The same reviewer independently reproduced the repaired idle and
active-reader behavior and approved the complete range.

## Acceptance Gates

Only the Stage 2 gates in the Phase A checkpoint scope are accounted here.

| Gate | Phase A standing | Evidence and limit |
|---:|---|---|
| 1 | Evidenced | Shared identity, enrollment, adapters, and source-backed opening remain provider-neutral; derived schemas, reconciliation, search, supersession, measurement, purge, and removal remain provider-owned |
| 2 | Evidenced | The same portable synthetic obligations pass independently for Arango and SQLite with explicit strategy rejection and no cross-provider fallback |
| 3 | Evidenced | Descriptors preserve distinct strategies, analyzers, match semantics, ordering, and raw polarity; SQLite exposes `-bm25()` and no magnitude comparison is made |
| 4 | Evidenced | SQLite results and per-corpus/aggregate counts share one read snapshot; the concurrent writer regression preserves the original exact count and result, while partial scope remains unknown |
| 5 | Evidenced | Five repeated eight-writer runs, bounded lock contention, stale-writer guards, crash rollback, integrity checks, and atomic activation expose no partial generation as current |
| 6 | Evidenced for scoped Phase A, with one integration gap | Disable, unenroll, selective purge, rebuild, and SQLite full removal are exercised. The open-handle removal defect is repaired. Arango full-removal integration remains unverified because no uniquely owned disposable database can be provisioned; no shared state is destructively tested |
| 15 | Evidenced for available Phase A measurements | Startup/readiness, bounded reconciliation, concurrency, lock/outage, physical SQLite artifacts, purge/rebuild, declared losses, and measurement bases are explicit. Database-only work and destructive runner evidence remain honestly unavailable |
| 18 | Evidenced | Final `llm-memory`, qhaway, focused provider, lifecycle, concurrency, evaluation, and privacy coverage pass at the reviewed endpoints with one guarded Arango skip disclosed |
| 19 | Evidenced | The complete diff adds no vector, hybrid, graph, federation, resident projection, Codex/Gemini adapter, or framework-delivery capability |

## Authorization Boundary

No real conversation source was read, copied, enumerated, hashed, indexed, or opened.

Phase A does not establish rationale-recovery usefulness and does not authorize Phase B.

`ready_for_phase_b_authorization` authorizes only preparation and review of a
separate Phase B manifest proposal. It does not authorize native-source
inspection or real corpus access. Any Phase B source-format characterization
still requires a separately presented and human-authorized manifest.
