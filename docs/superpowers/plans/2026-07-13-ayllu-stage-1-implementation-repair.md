# Ayllu Stage 1 Implementation Repair Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the implementation defects found in the 2026-07-13 independent review without expanding Stage 1 into federation, Codex integration, vector retrieval, or backend comparison.

**Architecture:** Preserve the approved contract and generation model. Make adapters fail locally and positionally, make reconciliation publish only non-current build evidence until whole-member validation, translate real Arango concurrency into retryable state conflicts, and make search counts come from one database snapshot. Immutable generation copy cost remains an observed Arango implementation cost for Stage 2 rather than being hidden inside the source-byte budget.

**Tech Stack:** Python 3.11+, pytest, python-arango, ArangoDB/ArangoSearch, FastMCP, YAML.

## Global Constraints

- Authoritative conversation logs remain read-only and outside every derived database.
- Identity contains canonicalization and boundary versions, never implementation version.
- Installed adapters support only semantic pair `(canonicalization_version=1, boundary_version=1)` in Stage 1; unsupported pairs fail enrollment before identity construction.
- A malformed complete record reports the source and byte position without crashing other corpus search.
- A partial trailing record remains incomplete and is retried from the last accepted boundary.
- `current` is published only after a whole-member integrity audit; tail/build observations are never current.
- Active generation replacement remains CAS-guarded and crash recoverable.
- Degraded indexes return available results with unknown counts represented as `null`, never fabricated zero.
- WorkBudget meters physical source bytes. Database document work is optimized and separately declared; it is not misrepresented as byte-bounded source work.
- The original `/home/tony/projects/llm-memory` dependency diff is user-owned and must remain unchanged at digest `9fef9719b4cb9e426750097cb41e21c4f365490f6ef0d112c5e3cc526f094792`.

---

### Task 1: Adapter and Enrollment Truthfulness

**Files:**
- Create: `/home/tony/projects/llm-memory-stage1/llm_memory/adapter_versions.py`
- Modify: `/home/tony/projects/llm-memory-stage1/llm_memory/enrollment.py`
- Modify: `/home/tony/projects/llm-memory-stage1/llm_memory/contract.py`
- Modify: `/home/tony/projects/llm-memory-stage1/llm_memory/adapters.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_enrollment.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_contract.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_adapters.py`

**Interfaces:**
- Produces `validate_adapter_versions(adapter, canonicalization_version, boundary_version)` and strict `EpisodeBody` validation.
- Preserves the existing adapter and enrollment public signatures.

- [ ] **Step 1: Write failing adapter/enrollment tests**

Add focused tests proving: each real adapter rejects semantic versions other than `(1, 1)`; wrong-typed body fields fail as malformed; `RecursionError` from deeply nested JSON reports the line position; a partial first Claude line is `available/incomplete`, not malformed; an empty complete Claude member retains the documented no-session standing; gateway sequence state advances only after record validation; and a missing Claude directory enumerates no phantom live member.

- [ ] **Step 2: Run the tests and capture RED**

Run:

```bash
env -u VIRTUAL_ENV uv run --frozen pytest -q tests/test_contract.py tests/test_enrollment.py tests/test_adapters.py
```

Expected: failures for unsupported semantic versions, recursive JSON, partial Claude standing, poisoned gateway sequence, and phantom member enumeration.

- [ ] **Step 3: Implement strict adapter contracts**

Create a single version-capability mapping containing only `(1, 1)` for the three installed adapters. Validate the selected pair in `SourceEnrollment.__post_init__`. Add `EpisodeBody.__post_init__` checks for four strings, object state/adapter fields, and list activity log. Validate adapter-native scalar fields before coercion. Catch `RecursionError` with the other malformed-record exceptions. In Claude discovery, return an empty member tuple for a missing/non-directory locator; preserve prior vanished members through reconciliation state. Do not override an incomplete scan merely because no session ID has arrived yet. Move gateway sequence increment after all record validation.

- [ ] **Step 4: Verify GREEN and compatibility**

Run the Task 1 tests plus `tests/test_open_episode.py` and `tests/test_reconcile.py`. Future semantic-version transition fixtures may temporarily extend the capability mapping inside the test only; production declarations remain v1-only.

- [ ] **Step 5: Commit**

Commit message: `fix: enforce episodic adapter contracts`.

---

### Task 2: Source-Failure and Freshness Invariants

**Files:**
- Modify: `/home/tony/projects/llm-memory-stage1/llm_memory/adapters.py`
- Modify: `/home/tony/projects/llm-memory-stage1/llm_memory/contract_index.py`
- Modify: `/home/tony/projects/llm-memory-stage1/llm_memory/reconcile.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_adapters.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_contract_index.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_reconcile.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_history_search.py`

**Interfaces:**
- Produces a positioned generation-document conflict that reconciliation converts to malformed source standing.
- Keeps existing public reconciliation functions.

- [ ] **Step 1: Write failing invariant regressions**

Add tests for: duplicated identical Taste Open and Claude records; tail-build state inspected after the scan patch but before activation; replace build whose source becomes missing/malformed after staging; a malformed line followed by later valid bytes across repeated calls; mid-record truncation during audit; and a blank-line/whitespace rewrite whose canonical episode is unchanged but byte positions shift.

- [ ] **Step 2: Run and capture RED**

Run the named tests and confirm they reproduce I-1 through I-6 rather than failing from fixture errors.

- [ ] **Step 3: Implement accepted-boundary and activation rules**

Advance `complete_end` only after a blank or successfully handled record; malformed records leave both cursor and accepted boundary at their start. Raise a positioned `GenerationDocumentConflict` when one generation receives the same reference with inconsistent source position, and catch it in reconciliation to persist malformed standing without activation. Persist `incomplete`, `stale`, `unknown`, or `tail_validated` during every build; never persist adapter `current` before activation/audit. Activate only when the source is available, has no error, is not incomplete/exhausted, and the accepted cursor reaches the observed end. Keep the old generation active on failed replacement. Evaluate truncation mismatch before the incomplete early return. Compare `(episode_ref, source_position.start, source_position.end)` during audits.

- [ ] **Step 4: Verify focused and integrated GREEN**

Run adapter, storage, reconciliation, search, and lifecycle suites. Confirm duplicate/malformed sources do not prevent independently enrolled corpora from returning results.

- [ ] **Step 5: Commit**

Commit message: `fix: preserve episodic source failure standing`.

---

### Task 3: Real Arango Concurrency and Database Work

**Files:**
- Modify: `/home/tony/projects/llm-memory-stage1/llm_memory/contract_index.py`
- Modify: `/home/tony/projects/llm-memory-stage1/llm_memory/reconcile.py`
- Modify: `/home/tony/projects/llm-memory-stage1/llm_memory/history.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_contract_index.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_reconcile.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_history_search.py`

**Interfaces:**
- Produces helpers that translate Arango conflict codes `1200` and `1210` into existing retryable transition conflicts.
- Search computes state selection, generation backing, matches, and counts in one AQL snapshot.

- [ ] **Step 1: Write failing real-concurrency and query-work tests**

Use two actual threads with separate database handles and deterministic barriers to reconcile the same member. Assert neither call leaks Arango write-write/unique exceptions and exactly one valid active generation remains. Add query-inspection tests proving active-generation backing uses `COUNT`/projected refs rather than full episode bodies, audits fetch only their current source-position window, and search does not pass a stale pre-read generation list into its population query.

- [ ] **Step 2: Run and capture RED**

Run focused live-Arango tests repeatedly enough to exercise the barrier once per test, not probabilistic race loops. Record actual exception classes and codes before adding translation.

- [ ] **Step 3: Implement conflict translation and snapshot search**

Catching is limited to Arango concurrency/unique codes at state/generation publication boundaries. On insert uniqueness, refetch and accept byte-identical deterministic documents; otherwise raise the positioned document conflict. Translate write-write conflicts into `_StateConflict`/`GenerationStateConflict` and defer the stale worker. Replace full-body backing checks with count AQL. Query audit windows using source-position bounds and projected reference/position fields. Move active-state selection and backing validation into the same AQL query that materializes the search population and counts. Add `seed_generation()` in `contract_index.py` as one server-side AQL `INSERT ... SELECT` operation that clones the active generation under deterministic new keys and CAS-publishes its staged count; reconciliation must not materialize full episode bodies in Python for seeding.

Append generation seeding remains an immutable-generation copy and therefore O(active generation documents). Keep it server-side through `seed_generation()`, measure/declare it, and do not claim WorkBudget covers it.

- [ ] **Step 4: Verify concurrency, crash recovery, and exact counts**

Run contract-index, reconciliation, search, lifecycle, and MCP suites. Confirm prior injected crash/CAS tests and new real parallel tests all pass with zero residual test documents.

- [ ] **Step 5: Commit**

Commit message: `fix: harden episodic database concurrency`.

---

### Task 4: Public Standing, Opening, and Startup Behavior

**Files:**
- Modify: `/home/tony/projects/llm-memory-stage1/llm_memory/reconcile.py`
- Modify: `/home/tony/projects/llm-memory-stage1/llm_memory/history.py`
- Modify: `/home/tony/projects/llm-memory-stage1/llm_memory/mcp_server.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_reconcile.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_history_search.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_open_episode.py`
- Modify: `/home/tony/projects/llm-memory-stage1/tests/test_mcp_server.py`

**Interfaces:**
- Unknown per-corpus and aggregate counts serialize as `None`/JSON `null`.
- FastMCP lifespan performs one bounded startup reconciliation only when a valid local registry exists; missing config still leaves legacy tools available.

- [ ] **Step 1: Write failing public-contract tests**

Cover: unavailable corpus counts are null; supersession database failure is visible rather than silently degraded; shrunk current source becomes stale; growth during an audit cannot be called tail-validated until the new complete tail is parsed; `reconcile_member` demotes expired current before spending/exhausting its budget; startup lifespan performs bounded reconciliation with config and tolerates missing config for legacy use.

- [ ] **Step 2: Run and capture RED**

Run reconciliation, search, opening, and MCP tests.

- [ ] **Step 3: Implement honest public behavior**

Set corpus `indexed_matches` and response `total_matches` to `None` whenever their scope is unknown. Remove the blanket supersession exception catch; exact source-backed opening still succeeds without Arango because it never queries supersessions. Classify known shrink/replacement as stale, and unparsed observed tail as incomplete rather than tail-validated. Call `_mark_due_audit` from the exported `reconcile_member` path. Add a lazy FastMCP lifespan that reconciles configured sources once at startup, catches only absent configuration for legacy-only operation, and does not load configuration at module import.

Reference-version reconstruction remains v1-only by enforced enrollment capability. Record that a future semantic-version implementation must add a versioned resolver before enabling the new version.

- [ ] **Step 4: Verify complete public compatibility**

Run opening, history, MCP, legacy search/recall, and the full suite.

- [ ] **Step 5: Commit**

Commit message: `fix: report episodic standing without silent loss`.

---

### Task 5: Evidence Repair and Final Review

**Files:**
- Modify: `/home/tony/projects/qhaway/docs/superpowers/specs/2026-07-12-ayllu-stage-1-episodic-contract-design.md`
- Modify: `/home/tony/projects/qhaway/docs/superpowers/baselines/2026-07-12-ayllu-stage-1-evaluation.md`
- Create: `/home/tony/projects/llm-memory-stage1/.superpowers/sdd/claude-review-repair-report.md`

- [ ] **Step 1: Run final evidence**

Run every focused Stage 1 suite, the complete llm-memory suite, and the complete qhaway suite. Verify source digests, Arango cleanup, both committed worktrees, full-range `git diff --check`, and the original dirty dependency digest.

- [ ] **Step 2: Record accepted findings and pushback**

Append a dated evidence addendum that re-evidences Gates 2, 5, 7, 8, 11, and 14. State that I-1 through I-6 and I-8 through I-11 were repaired. Record I-7's immutable-generation copy as measured, unbounded database work relative to the source-byte allowance and a Stage 2 comparison input. Record I-12 as safely deferred by v1-only enrollment. Explicitly list any unresolved items from I-13 through I-21 with their tested standing; do not summarize them as unspecified future work. Do not retain pre-repair `continue` as the active implementation decision unless all affected gates pass.

- [ ] **Step 3: Commit qhaway evidence**

Commit message: `docs: record stage 1 implementation review repairs`.

- [ ] **Step 4: Request broad final review**

Review the full llm-memory and qhaway ranges against the focused specification and Claude review. Fix every Critical/Important finding, then run fresh controller-side verification before presenting merge options again.

---

## Review Triage

- **Accepted for repair:** I-1 through I-6, I-8 through I-11, I-13 through I-21 where covered by Tasks 1-4.
- **Accepted with bounded implementation plus declared loss:** I-7. Full-body count/audit fetches and stale search snapshots are repaired; immutable append-generation copy remains an explicit Arango cost for Stage 2.
- **Deferred safely, not ignored:** I-12. Stage 1 enables only semantic version 1, so historical-version resolution cannot yet arise; enabling any later version is gated on adding that resolver.
- **No architecture reframe:** the review validates the authority, identity, and federation boundaries. The active decision remains `repair within the current boundary` until Task 5 evidence passes.
