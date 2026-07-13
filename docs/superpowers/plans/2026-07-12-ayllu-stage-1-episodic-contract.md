# Ayllu Stage 1 Episodic Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved Stage 1 episodic contract in `llm-memory`, preserving qhaway as the documentation and stage-evidence owner while adding stable episode identity, explicit bounded search, honest reconciliation standing, source-backed opening, and non-destructive lifecycle behavior.

**Architecture:** New contract-conforming episodes live in dedicated Arango collections and a dedicated search view, leaving the legacy `episodes` collection and `search`/`recall` tools unchanged. Pure contract and adapter modules establish identity outside Arango; an enrollment registry and generation-based reconciler derive searchable state; `search_history` and `open_episode` expose the new contract. Qhaway receives only the final Stage 1 evidence and decision record.

**Tech Stack:** Python >=3.14, stdlib dataclasses/enums/hashlib/base64/json/pathlib, PyYAML, python-arango, ArangoSearch/BM25, FastMCP, pytest, uv.

## Global Constraints

- Authoritative conversation sources are read-only. No task may write, truncate, rename, or normalize a source log.
- Qhaway receives no episodic runtime code. All implementation modules and tests live in `/home/tony/projects/llm-memory`.
- Preserve `/home/tony/projects/llm-memory/pyproject.toml` and `uv.lock` exactly as found. Their DuckDB changes predate Stage 1 and are not part of this work.
- Add no dependency. The existing Python, PyYAML, python-arango, MCP, and pytest dependencies are sufficient.
- Use dedicated Arango names: `episodic_contract_episodes`, `episodic_contract_search`, `episodic_contract_sources`, and `episodic_contract_supersessions`. Never migrate or rewrite the legacy `episodes` collection in Stage 1.
- Public identity is `episode://<corpus-id>/<session-id>/<episode-id>`. A stable `reference_key` is `sha256(episode_ref)`. Generation episode documents use `sha256(generation_id + "\0" + episode_ref)` so staging cannot overwrite the active generation. Neither hash is returned as public identity.
- Identity contains `canonicalization_version` and `boundary_version`, not `implementation_version`.
- Every provider request names concrete corpus identifiers. Do not add `scope="all"`, wildcards, mounted-corpus booleans, facets, pagination, embeddings, graph traversal, federation, Codex ingestion, or resident projection.
- A search snippet and match attribution are derived aids. They never count as authoritative evidence.
- `open_episode` resolves and verifies the source. It never falls back to an Arango document when the source is missing, malformed, unavailable, or mismatched.
- Exact totals describe the indexed snapshot. Freshness separately describes whether that snapshot represents the observed source.
- Tests may create uniquely named Arango records and must remove them in `finally` blocks or through a corpus-scoped cleanup fixture.
- The installed post-commit hook may create an additional `ots: stamp ...` commit after each implementation commit. Do not amend, squash, or stage unrelated files to avoid that behavior.
- Stage 1 ends with one `continue`, `repair`, `stop`, or `reframe` decision. It does not begin Stage 2.

---

### Task 1: Isolate llm-memory Work and Freeze the Dirty Baseline

**Files:**
- Inspect only: `/home/tony/projects/llm-memory/pyproject.toml`
- Inspect only: `/home/tony/projects/llm-memory/uv.lock`

**Interfaces:**
- Consumes: `llm-memory` revision `e95e32fbc739a4f5d3e21131b506472214346ce2` and its pre-existing DuckDB dependency diff.
- Produces: branch `feature/ayllu-stage1-contract` and a verified 17-test baseline without modifying the dirty files.

- [ ] **Step 1: Record repository and dirty-diff standing**

Run:

```bash
cd /home/tony/projects/llm-memory
git status --short
git rev-parse HEAD
git diff -- pyproject.toml uv.lock | sha256sum
```

Expected at plan creation: revision `e95e32fbc739a4f5d3e21131b506472214346ce2`, only `M pyproject.toml` and `M uv.lock`, and diff digest `9fef9719b4cb9e426750097cb41e21c4f365490f6ef0d112c5e3cc526f094792`. If the user has changed these files since plan approval, record the new digest and preserve that current state instead of restoring this historical digest.

- [ ] **Step 2: Create the implementation branch while carrying the unstaged user changes**

Run:

```bash
cd /home/tony/projects/llm-memory
git switch -c feature/ayllu-stage1-contract
```

Expected: branch changes; `pyproject.toml` and `uv.lock` remain unstaged and modified.

- [ ] **Step 3: Verify the existing implementation before adding contract code**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q
```

Expected: `17 passed`.

---

### Task 2: Contract Types, Qualified References, and Stable Identity

**Files:**
- Create: `/home/tony/projects/llm-memory/llm_memory/contract.py`
- Create: `/home/tony/projects/llm-memory/tests/test_contract.py`

**Interfaces:**
- Produces: `ContractError`, `EpisodeBody`, `EpisodeReference`, `EpisodeIdentity`, `SearchRequest`, `ProviderCapabilities`, standing enums, `canonical_bytes(body)`, `content_digest(body)`, `build_identity(...)`, and `reference_key(episode_ref)`.
- Consumes: stdlib only.

- [ ] **Step 1: Write failing identity and validation tests**

Create `tests/test_contract.py` with tests that assert:

```python
from dataclasses import replace

import pytest

from llm_memory.contract import (
    ContractError,
    EpisodeBody,
    EpisodeReference,
    SearchRequest,
    build_identity,
    reference_key,
)


BODY = EpisodeBody(
    timestamp="2026-07-12T18:29:10Z",
    model="claude-test",
    user_message="question",
    response="answer",
    state={"status": "observed"},
    activity_log=[],
    adapter_fields={},
)


def test_identity_round_trips_and_survives_implementation_release():
    first = build_identity(
        corpus_id="corpus-a",
        source_id="source-a",
        native_session_id="session-a",
        event_token="event-a",
        canonicalization_version=1,
        boundary_version=1,
        body=BODY,
    )
    parsed = EpisodeReference.parse(first.episode_ref)
    assert parsed == first.reference
    assert parsed.source_id == "source-a"
    assert parsed.native_session_id == "session-a"
    assert parsed.event_token == "event-a"


def test_content_or_semantic_version_change_churns_identity():
    base = dict(
        corpus_id="corpus-a",
        source_id="source-a",
        native_session_id="session-a",
        event_token="event-a",
        canonicalization_version=1,
        boundary_version=1,
    )
    original = build_identity(body=BODY, **base)
    changed_body = build_identity(body=replace(BODY, response="different"), **base)
    changed_boundary = build_identity(body=BODY, **(base | {"boundary_version": 2}))
    assert len({original.episode_ref, changed_body.episode_ref, changed_boundary.episode_ref}) == 3


def test_reference_key_is_backend_only_sha256():
    identity = build_identity(
        corpus_id="corpus-a", source_id="source-a", native_session_id="session-a",
        event_token="event-a", canonicalization_version=1, boundary_version=1, body=BODY,
    )
    assert len(reference_key(identity.episode_ref)) == 64
    assert reference_key(identity.episode_ref) not in identity.episode_ref


@pytest.mark.parametrize("limit", [0, 101, True])
def test_search_request_rejects_invalid_limit(limit):
    with pytest.raises(ContractError):
        SearchRequest.create("query", ["corpus-a"], limit=limit)


def test_search_request_requires_concrete_unique_corpora():
    with pytest.raises(ContractError):
        SearchRequest.create("query", [])
    with pytest.raises(ContractError):
        SearchRequest.create("query", ["corpus-a", "corpus-a"])
    with pytest.raises(ContractError):
        SearchRequest.create("query", ["*"])
```

- [ ] **Step 2: Run the contract tests and verify the module is absent**

Run: `cd /home/tony/projects/llm-memory && uv run --frozen pytest -q tests/test_contract.py`

Expected: collection error with `ModuleNotFoundError: No module named 'llm_memory.contract'`.

- [ ] **Step 3: Implement the contract primitives**

Implement these exact public shapes in `llm_memory/contract.py`:

```python
CONTRACT_VERSION = 1
STRATEGY = "lexical_bm25_text_en_v1"
MAX_LIMIT = 100

class SourceStanding(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNSUPPORTED_ADAPTER = "unsupported_adapter"
    MALFORMED = "malformed"

class IndexStanding(StrEnum):
    AVAILABLE = "available"
    REBUILDING = "rebuilding"
    UNAVAILABLE = "unavailable"

class FreshnessStanding(StrEnum):
    CURRENT = "current"
    TAIL_VALIDATED = "tail_validated"
    STALE = "stale"
    INCOMPLETE = "incomplete"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"

class TotalStanding(StrEnum):
    EXACT = "exact"
    ESTIMATED = "estimated"
    LOWER_BOUND = "lower_bound"
    UNKNOWN = "unknown"

class OpenStanding(StrEnum):
    AVAILABLE = "available"
    SOURCE_UNAVAILABLE = "source_unavailable"
    MISSING = "missing"
    CONTENT_MISMATCH = "content_mismatch"
    UNSUPPORTED_ADAPTER = "unsupported_adapter"
    MALFORMED_SOURCE = "malformed_source"
    SUPERSEDED = "superseded"
```

Use frozen dataclasses. `EpisodeBody` contains `timestamp`, `model`, `user_message`, `response`, `state`, `activity_log`, and `adapter_fields`, plus `as_dict()`. Canonicalize with:

```python
json.dumps(body.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
```

`EpisodeReference` stores `corpus_id`, `session_id`, and `episode_id`, exposes
decoded properties `source_id`, `native_session_id`,
`canonicalization_version`, `boundary_version`, `event_token`, and
`content_digest`, and renders through `str(reference)`. `EpisodeIdentity` stores
`reference` and `body_digest`, with `episode_ref` delegating to
`str(reference)`.

Encode tuple components as unpadded URL-safe base64 joined by `.`. `EpisodeReference.build()` encodes `(source_id, native_session_id)` into `session_id` and `(canonicalization_version, boundary_version, event_token, full_sha256_digest)` into `episode_id`. `EpisodeReference.parse()` must require scheme `episode`, exactly two path segments, four decoded episode components, positive integer semantic versions, and a 64-character lowercase hexadecimal digest.

`SearchRequest.create()` strips and validates a non-empty query, rejects bool limits, enforces `1..100`, rejects empty/duplicate corpora and `*`/`all`, and defaults strategy to `STRATEGY`.

`ProviderCapabilities.as_dict()` returns exactly:

```python
{
    "contract_versions": [1],
    "strategies": ["lexical_bm25_text_en_v1"],
    "supports_facets": False,
    "supports_continuation": False,
    "max_limit": 100,
}
```

- [ ] **Step 4: Verify contract behavior**

Run: `cd /home/tony/projects/llm-memory && uv run --frozen pytest -q tests/test_contract.py`

Expected: all contract tests pass.

- [ ] **Step 5: Commit contract code and tests explicitly**

```bash
cd /home/tony/projects/llm-memory
git add llm_memory/contract.py tests/test_contract.py
git commit -m "feat: define episodic contract identity"
```

Expected: no dependency file is staged; the OTS hook may add its own follow-up commit.

---

### Task 3: Local Enrollment Registry and Strict Configuration

**Files:**
- Create: `/home/tony/projects/llm-memory/llm_memory/enrollment.py`
- Create: `/home/tony/projects/llm-memory/tests/test_enrollment.py`
- Modify: `/home/tony/projects/llm-memory/.gitignore`
- Create: `/home/tony/projects/llm-memory/config/sources.example.yaml`

**Interfaces:**
- Produces: `SourceEnrollment`, `EnrollmentRegistry`, `load_registry(path=None)`, `sources_for(corpus_id)`, and `known_corpora`.
- Consumes: PyYAML and contract version 1.

- [ ] **Step 1: Write failing registry tests**

Tests must cover one corpus with both Claude and gateway sources, a disabled source, duplicate `(corpus_id, source_id)`, unsupported top-level keys, missing locator, non-positive semantic versions, and environment override `LLM_MEMORY_SOURCES_CONFIG`.

Use this valid fixture:

```yaml
contract_version: 1
sources:
  - corpus_id: project-history
    source_id: claude-sessions
    adapter: claude_code_jsonl
    boundary_version: 1
    canonicalization_version: 1
    locator: /tmp/claude
    enabled: true
    full_validation_max_age_seconds: 86400
  - corpus_id: project-history
    source_id: gateway-log
    adapter: gateway_jsonl
    boundary_version: 1
    canonicalization_version: 1
    locator: /tmp/gateway.jsonl
    enabled: true
    full_validation_max_age_seconds: 86400
```

Assert `sources_for("project-history")` returns both enabled sources and that no database contents influence the result.

- [ ] **Step 2: Run registry tests to verify failure**

Run: `cd /home/tony/projects/llm-memory && uv run --frozen pytest -q tests/test_enrollment.py`

Expected: module import failure for `llm_memory.enrollment`.

- [ ] **Step 3: Implement strict registry loading**

`SourceEnrollment` is a frozen dataclass with fields exactly matching the YAML fixture. `EnrollmentRegistry` stores a tuple of declarations and validates:

- top-level keys are exactly `contract_version` and `sources`;
- source keys are exactly the eight fixture keys;
- `(corpus_id, source_id)` pairs are unique;
- identifiers are non-empty and contain no `/`;
- adapter is one of `taste_open_jsonl`, `gateway_jsonl`, `claude_code_jsonl`;
- semantic versions and validation age are positive integers; and
- locator is retained as a `Path` without being resolved into identity.

Implement these signatures:

```python
DEFAULT_SOURCES_PATH = Path(__file__).resolve().parent.parent / "config" / "sources.yaml"

@dataclass(frozen=True)
class SourceEnrollment:
    corpus_id: str
    source_id: str
    adapter: str
    boundary_version: int
    canonicalization_version: int
    locator: Path
    enabled: bool
    full_validation_max_age_seconds: int

@dataclass(frozen=True)
class EnrollmentRegistry:
    sources: tuple[SourceEnrollment, ...]

    @property
    def known_corpora(self) -> frozenset[str]: ...
    def sources_for(self, corpus_id: str, *, enabled_only: bool = True) -> tuple[SourceEnrollment, ...]: ...

def load_registry(path: Path | None = None) -> EnrollmentRegistry: ...
```

Default path is `config/sources.yaml` relative to the repository; `LLM_MEMORY_SOURCES_CONFIG` overrides it. Missing configuration raises `FileNotFoundError` only when the new contract path is invoked.

- [ ] **Step 4: Add safe configuration packaging**

Append `config/sources.yaml` to `.gitignore`. Create `config/sources.example.yaml` using the valid fixture with illustrative locators `/srv/llm-memory/sources/claude-code` and `/srv/llm-memory/sources/gateway.jsonl`. Do not create a real `sources.yaml` in this task.

- [ ] **Step 5: Verify registry behavior and legacy tests**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q tests/test_enrollment.py tests/test_db.py
```

Expected: pass; legacy DB configuration remains usable.

- [ ] **Step 6: Commit only registry-owned paths**

```bash
cd /home/tony/projects/llm-memory
git add .gitignore config/sources.example.yaml llm_memory/enrollment.py tests/test_enrollment.py
git commit -m "feat: add local episodic source enrollment"
```

---

### Task 4: Versioned Source Adapters and Canonical Episodes

**Files:**
- Create: `/home/tony/projects/llm-memory/llm_memory/adapters.py`
- Create: `/home/tony/projects/llm-memory/tests/test_adapters.py`
- Modify: `/home/tony/projects/llm-memory/llm_memory/ingest.py`
- Modify: `/home/tony/projects/llm-memory/tests/test_ingest.py`

**Interfaces:**
- Produces: `SourceMember`, `EpisodeRecord`, `MemberScan`, `SourceAdapter`, `get_adapter(name)`, and adapters for taste_open, gateway, and Claude Code.
- Consumes: `SourceEnrollment`, `EpisodeBody`, and `build_identity()`.
- Preserves: legacy transform and ingest functions in `ingest.py`.

- [ ] **Step 1: Write adapter tests using portable JSONL**

Tests must establish:

- taste_open uses declared stream plus native cycle;
- gateway uses native session plus session-local request sequence and preserves prompt-only standing as empty response provenance;
- Claude uses `sessionId` plus assistant UUID;
- two Claude prose assistant events after one user produce two episodes sharing the same user text;
- unanswered user prose and tool-only assistant events produce no episode;
- a final line without newline returns `FreshnessStanding.INCOMPLETE` and is not emitted;
- malformed newline-terminated JSON returns `SourceStanding.MALFORMED` with byte position;
- moving identical files under the same enrollment leaves episode references unchanged; and
- changing implementation version alone is not an adapter input and cannot change identity.

- [ ] **Step 2: Run adapter tests to verify failure**

Run: `cd /home/tony/projects/llm-memory && uv run --frozen pytest -q tests/test_adapters.py`

Expected: module import failure for `llm_memory.adapters`.

- [ ] **Step 3: Implement adapter data shapes**

Use frozen dataclasses:

```python
@dataclass(frozen=True)
class SourceMember:
    member_id: str
    path: Path

@dataclass(frozen=True)
class EpisodeRecord:
    identity: EpisodeIdentity
    body: EpisodeBody
    native_event_id: str | None
    source_position: dict
    state_text: str

@dataclass(frozen=True)
class MemberScan:
    member: SourceMember
    episodes: tuple[EpisodeRecord, ...]
    observed_end: int
    complete_end: int
    source_standing: SourceStanding
    freshness: FreshnessStanding
    error_position: int | None = None
```

`SourceAdapter` exposes `members(enrollment) -> tuple[SourceMember, ...]` and `scan(enrollment, member) -> MemberScan`.

Each registered adapter also exposes immutable `name` and
`implementation_version` attributes. `get_adapter(name)` fails visibly for an
unregistered name; it never guesses from a filename.

Use binary line iteration so source positions are byte offsets. Only newline-terminated records are complete. Decode each complete line as UTF-8 JSON; a decoding or JSON error makes the member malformed at that byte offset.

For a source-set member whose native session cannot be parsed, use an
operational member ID `unresolved-<sha256(source-set-relative-name)>` solely to
report malformed standing. That provisional member ID never participates in an
episode reference and must change to the source-native member ID once parsing
succeeds.

- [ ] **Step 4: Implement the three boundary algorithms**

Use the approved canonical body fields. Taste_open excludes `_activity_log` from `state_text` but retains it in `activity_log`. Gateway retains `messages_full` in `adapter_fields` and selects the last user message. Claude retains the most recent user prose and emits one episode per prose-bearing assistant event. Adapter `members()` returns one member for file locators; Claude directory locators return sorted `*.jsonl` files. To avoid unbounded, uncharged discovery reads, each Claude member uses a stable operational ID derived from the source-set-relative filename. Episode identity still uses the source-native `sessionId`, never that operational member ID.

Every adapter calls `build_identity()` with enrollment semantic versions. No adapter reads or embeds `implementation_version` in identity.

Register adapters explicitly:

```python
_ADAPTERS: dict[str, SourceAdapter] = {
    "taste_open_jsonl": TasteOpenAdapter(),
    "gateway_jsonl": GatewayAdapter(),
    "claude_code_jsonl": ClaudeCodeAdapter(),
}

def get_adapter(name: str) -> SourceAdapter:
    try:
        return _ADAPTERS[name]
    except KeyError as exc:
        raise ContractError(f"unsupported adapter: {name}") from exc
```

- [ ] **Step 5: Preserve legacy ingest behavior through compatibility wrappers**

Keep existing public functions and existing legacy keys unchanged. Move only shared text extraction into `adapters.py` if helpful, then import it from `ingest.py`. The original 17 tests must continue to pass without requiring `sources.yaml`.

- [ ] **Step 6: Verify adapters and legacy ingestion**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q tests/test_adapters.py tests/test_ingest.py
```

Expected: all adapter and existing ingestion tests pass.

- [ ] **Step 7: Commit adapter paths**

```bash
cd /home/tony/projects/llm-memory
git add llm_memory/adapters.py llm_memory/ingest.py tests/test_adapters.py tests/test_ingest.py
git commit -m "feat: add versioned episodic source adapters"
```

---

### Task 5: Dedicated Arango Contract Collections and Generation Storage

**Files:**
- Create: `/home/tony/projects/llm-memory/llm_memory/contract_index.py`
- Create: `/home/tony/projects/llm-memory/tests/test_contract_index.py`

**Interfaces:**
- Produces: collection constants, `ensure_contract_index(db)`, `write_generation(db, enrollment, member, generation_id, episodes)`, `activate_generation(...)`, and `active_states(db, corpus_ids)`.
- Consumes: adapter episode records.

- [ ] **Step 1: Write live-Arango storage tests**

Tests use a unique corpus prefix and assert:

- all four dedicated collections and the dedicated view are created idempotently;
- legacy `episodes` documents are untouched;
- generated documents contain `episode_ref`, corpus/source/member IDs, semantic versions, generation ID, canonical evidence fields, and search text;
- `_key == generation_storage_key(generation_id, episode_ref)` and the stable `reference_key` is stored separately;
- activation changes the source-member state only after every generation document is written; and
- cleanup deletes only the unique test corpus.

- [ ] **Step 2: Verify storage tests fail before implementation**

Run: `cd /home/tony/projects/llm-memory && uv run --frozen pytest -q tests/test_contract_index.py`

Expected: import failure for `llm_memory.contract_index`.

- [ ] **Step 3: Implement dedicated storage**

Define:

```python
CONTRACT_EPISODES = "episodic_contract_episodes"
CONTRACT_VIEW = "episodic_contract_search"
SOURCE_STATES = "episodic_contract_sources"
SUPERSESSIONS = "episodic_contract_supersessions"
```

Define `generation_storage_key(generation_id, episode_ref)` as SHA-256 over the
UTF-8 generation ID, one NUL byte, and the episode reference. This permits active
and staging generations to contain the same unchanged public reference without
key collision.

The view indexes `user_message`, `response`, and `state_text` with `text_en`. A source-member state `_key` is the SHA-256 of `corpus_id/source_id/member_id`; it stores active/staging generation, positions, semantic and implementation versions, member generation metadata, freshness, integrity audit progress, and validation time.

Write a complete generation under a new `generation_id`, then update one source-state document to activate it. Search filters against active generation IDs obtained before query execution. Delete old generations only after activation; a crash may leave inert staging documents but cannot expose them as current.

Generation document writes and staging-state patches are idempotent. Retrying
after a crash may overwrite an identical deterministic generation document but
must reject conflicting content. Injected-failure tests cover crashes after
document insert, before staged count/cursor persistence, and during generation
seeding.

Implement these public signatures:

```python
def ensure_contract_index(db) -> None: ...
def generation_storage_key(generation_id: str, episode_ref: str) -> str: ...
def write_generation(db, enrollment, member, generation_id: str, episodes) -> int: ...
def activate_generation(db, enrollment, member, generation_id: str, state: dict) -> None: ...
def active_states(db, corpus_ids: tuple[str, ...]) -> tuple[dict, ...]: ...
def delete_generation(db, corpus_id: str, source_id: str, member_id: str, generation_id: str) -> int: ...
```

- [ ] **Step 4: Verify storage behavior and legacy index isolation**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q tests/test_contract_index.py tests/test_index.py
```

Expected: pass; both legacy and contract views exist independently.

- [ ] **Step 5: Commit storage module and tests**

```bash
cd /home/tony/projects/llm-memory
git add llm_memory/contract_index.py tests/test_contract_index.py
git commit -m "feat: add isolated episodic contract index"
```

---

### Task 6: Bounded Reconciliation, Member Standing, and Integrity Audits

**Files:**
- Create: `/home/tony/projects/llm-memory/llm_memory/reconcile.py`
- Create: `/home/tony/projects/llm-memory/tests/test_reconcile.py`
- Modify: `/home/tony/projects/llm-memory/llm_memory/adapters.py`
- Modify: `/home/tony/projects/llm-memory/tests/test_adapters.py`

**Interfaces:**
- Produces: `WorkBudget`, `ReconcileReport`, `reconcile_registry(db, registry, budget)`, `reconcile_source(db, enrollment, budget)`, and source/member standing dictionaries consumed by search.
- Produces: resumable `ScanCursor` and `MemberChunk` adapter reads while preserving whole-member `scan()` as a compatibility wrapper.
- Consumes: enrollment, adapters, and generation storage.

**Plan correction discovered during execution:** The Task 4 whole-member
`scan()` interface cannot enforce a physical work bound or resume boundary state.
Task 6 therefore extends adapters with
`scan_chunk(enrollment, member, cursor, max_bytes)`. Cursor adapter state retains
gateway session sequences and Claude session/last-user context. JSONL records
are atomic: a single record may exceed the scheduling allowance, but actual
bytes and the one-record overshoot are reported rather than hidden through
logical metering.

- [ ] **Step 1: Write reconciliation perturbation tests**

Use temporary JSONL plus unique Arango corpus IDs. Cover:

1. initial build reaches current and indexes complete episodes;
2. append advances the active generation and exact position;
3. partial tail indexes only through the last complete newline and reports incomplete;
4. malformed complete line reports malformed without fabricating an episode;
5. a Claude directory reports two members with independent positions;
6. a corpus with Claude and gateway sources preserves both source standings;
7. relocation with unchanged declaration IDs preserves episode references;
8. bounded work reports incomplete and resumes automatically;
9. a whole-member audit uses a persisted chain digest and eventually reports current;
10. expiration changes current to tail_validated until the next audit;
11. an in-place prefix rewrite is detected by the next full audit and activates a replacement generation;
12. implementation-version change with unchanged canonical output preserves references;
13. canonicalization- or boundary-version change creates new references and supersession observations; and
14. a previously indexed member that vanishes remains visible with missing or unavailable standing until purge.
15. truncation, unavailable source, and malformed source cannot certify stale active episodes as current;
16. audit completion compares the full ordered active-generation reference chain and count;
17. a semantic version change during a bounded build discards and restarts that staging generation;
18. blank complete lines advance the physical cursor under small budgets;
19. supersession finalization resumes idempotently after activation-time failure; and
20. gateway supersessions match native session plus session-local event token.

Adapter regression tests additionally prove that chunked scans equal whole
scans, cursor boundary state survives between chunks, `bytes_read` reflects
physical input, and one oversized complete record makes progress with a declared
overshoot.

- [ ] **Step 2: Run reconciliation tests to verify failure**

Run: `cd /home/tony/projects/llm-memory && uv run --frozen pytest -q tests/test_reconcile.py`

Expected: import failure for `llm_memory.reconcile`.

- [ ] **Step 3: Implement byte-bounded work and automatic source traversal**

`WorkBudget(max_bytes: int, now: datetime)` rejects non-positive budgets and tracks consumed source bytes. `reconcile_registry()` iterates enabled declarations and their sorted members, spending work on complete tail records first and then the oldest due integrity audit. It returns every source and member standing even after the budget is exhausted.

Use these report fields consistently:

```python
@dataclass(frozen=True)
class ReconcileReport:
    corpus_standing: tuple[dict, ...]
    bytes_read: int
    elapsed_ms: float
    work_exhausted: bool
```

`corpus_standing` uses the same nested corpus/source/member shape later returned
by search, except it omits match counts until a query supplies a population.

Persist member generation metadata as file size and `st_mtime_ns`, but never use it alone to claim current. Newly discovered and vanished members remain represented in source state until purge.

Implement orchestration through:

```python
def reconcile_registry(db, registry: EnrollmentRegistry, budget: WorkBudget) -> ReconcileReport: ...
def reconcile_source(db, enrollment: SourceEnrollment, budget: WorkBudget) -> tuple[dict, ...]: ...
def reconcile_member(db, enrollment: SourceEnrollment, member: SourceMember, budget: WorkBudget) -> dict: ...
```

Use these adapter shapes:

```text
ScanCursor(byte_offset: int, adapter_state: dict)
MemberChunk(member, episodes, next_cursor, observed_end, complete_end,
            source_standing, freshness, bytes_read, exhausted,
            error_position=None)
SourceAdapter.scan_chunk(enrollment, member, cursor, max_bytes) -> MemberChunk
```

`SourceAdapter.scan()` loops `scan_chunk()` to completion; reconciliation calls
only the chunked interface.

- [ ] **Step 4: Implement resumable integrity chain**

Use a resumable chain rather than serializing a `hashlib` object:

```python
def extend_chain(previous_hex: str, episode_ref: str) -> str:
    previous = bytes.fromhex(previous_hex) if previous_hex else bytes(32)
    return hashlib.sha256(previous + episode_ref.encode("utf-8")).hexdigest()
```

Persist audit byte offset, chain digest, start size, start `mtime_ns`, and start observed end. On completion, verify the member generation is unchanged, compare episode identities with the active generation, record `validated_at`, and report current. Restart an audit whose member changes. Expired validation reports tail_validated until another audit completes.

Record audit bytes, elapsed time, validation age, and restart count separately.
The evidence report must declare whole-member validation as O(source bytes), not
fold that work into search latency.

- [ ] **Step 5: Record supersession observations on semantic change**

When the same `(corpus_id, source_id, member_id, event_token)` yields a new reference, insert a supersession document containing old ref, new ref, reason, and detection time. This mapping is derived and separately purgeable.

- [ ] **Step 6: Verify reconciliation and storage together**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q tests/test_reconcile.py tests/test_contract_index.py
```

Expected: all tests pass and cleanup leaves no unique test corpus documents.

- [ ] **Step 7: Commit reconciliation paths**

```bash
cd /home/tony/projects/llm-memory
git add llm_memory/reconcile.py tests/test_reconcile.py
git commit -m "feat: reconcile episodic sources with honest freshness"
```

---

### Task 7: Explicit Bounded Search and Exact Indexed Population

**Files:**
- Create: `/home/tony/projects/llm-memory/llm_memory/history.py`
- Create: `/home/tony/projects/llm-memory/tests/test_history_search.py`

**Interfaces:**
- Produces: `search_history(db, registry, request, budget) -> dict` and provider capability response.
- Consumes: `SearchRequest`, reconciliation reports, active generations, and the contract view.

- [ ] **Step 1: Write search contract tests**

Tests must assert:

- unknown, disabled, duplicate, wildcard, and empty corpus scope fails before AQL;
- `LIMIT=1` returns one result with exact per-corpus and aggregate totals greater than one;
- two differently adapted sources under one corpus appear under nested source/member standing;
- two requested corpora preserve independent standing;
- one unavailable member index prevents a fabricated exact aggregate while available results remain visible;
- results carry qualified references, deterministic ref tie-break, heuristic match attribution, and bounded snippets;
- every request and response carries `contract_version: 1`;
- no result exposes `_key` as identity;
- stale, tail_validated, and incomplete indexes remain searchable with their standing; and
- automatic bounded reconciliation runs before the query.

- [ ] **Step 2: Verify search tests fail**

Run: `cd /home/tony/projects/llm-memory && uv run --frozen pytest -q tests/test_history_search.py`

Expected: `search_history` import failure.

- [ ] **Step 3: Implement one AQL population and result query**

Build bind variables only; never interpolate corpus identifiers. Obtain active generation IDs for every enabled source/member. Query the dedicated view, filter concrete corpus IDs and active generations, calculate BM25, sort by score descending then `episode_ref` ascending, materialize the indexed match population, calculate per-corpus counts and aggregate length, and slice results to `limit`.

Use one AQL request with this structure:

```aql
LET matches = (
  FOR doc IN @@view
    SEARCH ANALYZER(
      doc.user_message IN TOKENS(@query, @analyzer) OR
      doc.response IN TOKENS(@query, @analyzer) OR
      doc.state_text IN TOKENS(@query, @analyzer),
      @analyzer
    )
    FILTER doc.corpus_id IN @corpus_ids
    FILTER doc.generation_id IN @active_generations
    LET score = BM25(doc)
    SORT score DESC, doc.episode_ref ASC
    RETURN MERGE(doc, {score})
)
LET corpus_totals = (
  FOR doc IN matches
    COLLECT corpus_id = doc.corpus_id WITH COUNT INTO count
    SORT corpus_id
    RETURN {corpus_id, count}
)
RETURN {
  total_matches: LENGTH(matches),
  corpus_totals,
  results: SLICE(matches, 0, @limit)
}
```

Return `match_semantics: analyzed_any_token`. Attribution uses the legacy overlap heuristic but returns:

```yaml
match_attribution:
  field: response
  method: provider_heuristic_v1
  standing: heuristic
```

Return nested standing with this exact shape:

```yaml
corpus_standing:
  - corpus_id: project-history
    indexed_matches: 12
    match_standing: exact
    sources:
      - source_id: claude-sessions
        adapter: claude_code_jsonl
        implementation_version: 1.0.0
        canonicalization_version: 1
        boundary_version: 1
        source_set_standing: available
        members:
          - member_id: session-a
            source_standing: available
            index_standing: available
            freshness: current
            indexed_through: {kind: byte_offset, value: 182734}
            observed_source_end: {kind: byte_offset, value: 182734}
            integrity:
              basis: full_digest
              validated_at: 2026-07-12T18:30:00Z
```

Never collapse multiple source or member standings into one freshness value.

If every requested member index is available, totals are exact for the indexed snapshot. Otherwise retain available results but set affected corpus and aggregate match standing to unknown rather than treating absent members as zero.

- [ ] **Step 4: Verify search behavior and legacy search compatibility**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q tests/test_history_search.py tests/test_search.py
```

Expected: new and legacy search tests pass against separate views.

- [ ] **Step 5: Commit search provider and tests**

```bash
cd /home/tony/projects/llm-memory
git add llm_memory/history.py tests/test_history_search.py
git commit -m "feat: add bounded episodic history search"
```

---

### Task 8: Source-Backed Exact Opening and Supersession Standing

**Files:**
- Modify: `/home/tony/projects/llm-memory/llm_memory/history.py`
- Create: `/home/tony/projects/llm-memory/tests/test_open_episode.py`

**Interfaces:**
- Produces: `open_episode(db, registry, episode_ref, active_corpus_ids) -> dict`.
- Consumes: qualified references, source adapters, active enrollment, and derived supersession observations.

- [ ] **Step 1: Write exact-opening tests**

Tests cover available source-backed content, inactive corpus rejection, missing event, malformed source, unavailable source, digest mismatch after rewrite, superseded with replacement ref, supersession mapping purged to content mismatch/missing, unsupported adapter standing, and Arango unavailability not causing a cached-document fallback.

Every opening response must carry `contract_version: 1`, the requested
`episode_ref`, and exactly one standing.

For the fallback test: reconcile an episode, remove or rename only the temporary test source, leave the Arango episode document present, call `open_episode`, and assert `standing == "source_unavailable"` and that response/user/state content keys are absent.

This test specifically prohibits a derived-document fallback: the retained
Arango document may help search, but it cannot satisfy authoritative opening.

- [ ] **Step 2: Run opening tests to verify failure**

Run: `cd /home/tony/projects/llm-memory && uv run --frozen pytest -q tests/test_open_episode.py`

Expected: import or missing-function failure for `open_episode`.

- [ ] **Step 3: Implement source resolution**

Parse the reference, verify its corpus appears exactly once in `active_corpus_ids`, decode source/session/event identity, locate the enabled declaration, and ask the adapter to scan the authoritative member/event. Recompute the canonical digest and compare with the reference.

Keep the public entry point exact:

```python
def open_episode(
    db,
    registry: EnrollmentRegistry,
    episode_ref: str,
    active_corpus_ids: list[str] | tuple[str, ...],
) -> dict: ...
```

Return the canonical evidence body plus provenance only for available. For superseded return the replacement ref only. For every other non-available standing, omit `user_message`, `response`, `state`, `activity_log`, `adapter_fields`, and any derived snippet.

- [ ] **Step 4: Verify opening and legacy recall independently**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q tests/test_open_episode.py tests/test_recall.py
```

Expected: both source-backed opening and legacy Arango recall tests pass; their authority differences remain visible.

- [ ] **Step 5: Commit exact opening**

```bash
cd /home/tony/projects/llm-memory
git add llm_memory/history.py tests/test_open_episode.py
git commit -m "feat: open exact source-backed episodes"
```

---

### Task 9: Disable, Unenroll, Purge, and Re-enroll

**Files:**
- Create: `/home/tony/projects/llm-memory/llm_memory/lifecycle.py`
- Create: `/home/tony/projects/llm-memory/tests/test_lifecycle.py`

**Interfaces:**
- Produces: `disable_source(config_path, corpus_id, source_id)`, `unenroll_source(...)`, `purge_derived(db, corpus_id, source_id=None, classes=...)`, and structured operation reports.
- Consumes: strict enrollment YAML and dedicated Arango collections.

- [ ] **Step 1: Write lifecycle tests**

Tests assert:

- disable atomically writes `enabled: false`, preserves all other declarations and source bytes, and excludes the source from subsequent search;
- unenroll atomically removes only the named declaration, preserves source bytes and derived documents, and removes authority to search/open it;
- purge names `episodes`, `reconciliation`, and `supersessions` independently, deletes only selected corpus/source derived data, and reports counts;
- purging supersessions degrades old reference standing honestly;
- re-enrollment validates retained state before current and rebuilds when semantic versions differ; and
- malformed enrollment YAML is preserved byte-for-byte when an operation fails.

- [ ] **Step 2: Run lifecycle tests to verify failure**

Run: `cd /home/tony/projects/llm-memory && uv run --frozen pytest -q tests/test_lifecycle.py`

Expected: module import failure for `llm_memory.lifecycle`.

- [ ] **Step 3: Implement non-destructive lifecycle operations**

Use same-directory temporary file plus `os.replace` for configuration changes. Never infer a source path from Arango. `purge_derived` accepts a non-empty frozen set drawn only from `episodes`, `reconciliation`, and `supersessions`; invalid classes fail before deletion. Episode purge filters by corpus and optional source and cannot access the legacy collection.

Use these signatures:

```python
def disable_source(config_path: Path, corpus_id: str, source_id: str) -> dict: ...
def unenroll_source(config_path: Path, corpus_id: str, source_id: str) -> dict: ...
def purge_derived(
    db,
    corpus_id: str,
    source_id: str | None = None,
    *,
    classes: frozenset[str],
) -> dict[str, int]: ...
```

- [ ] **Step 4: Verify lifecycle, search, and opening together**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q tests/test_lifecycle.py tests/test_history_search.py tests/test_open_episode.py
```

Expected: pass with source files unchanged.

- [ ] **Step 5: Commit lifecycle paths**

```bash
cd /home/tony/projects/llm-memory
git add llm_memory/lifecycle.py tests/test_lifecycle.py
git commit -m "feat: add non-destructive episodic lifecycle"
```

---

### Task 10: Add Contract MCP Tools Without Recasting Legacy Tools

**Files:**
- Modify: `/home/tony/projects/llm-memory/llm_memory/mcp_server.py`
- Modify: `/home/tony/projects/llm-memory/tests/test_mcp_server.py`

**Interfaces:**
- Produces: MCP tools `search_history` and `open_episode` alongside legacy `search` and `recall`.
- Consumes: lazy registry loading, database handle, contract request validation, and history operations.

- [ ] **Step 1: Update MCP tests first**

Assert tool names are exactly:

```python
{"search", "recall", "search_history", "open_episode"}
```

Retain the existing legacy composition test. Add a contract composition test that creates a temporary ignored source configuration, reconciles a test episode through `search_history`, opens its `episode_ref`, and asserts source-backed content. Add a missing-config test proving legacy tools still load while a new tool fails visibly when invoked.

- [ ] **Step 2: Run MCP tests to verify the tools are absent**

Run: `cd /home/tony/projects/llm-memory && uv run --frozen pytest -q tests/test_mcp_server.py`

Expected: tool-name assertion fails because only `search` and `recall` exist.

- [ ] **Step 3: Implement lazy contract tools**

Do not load `sources.yaml` at module import. The new tools accept:

```python
def search_history(query: str, corpus_ids: list[str], limit: int = 10) -> dict
def open_episode(episode_ref: str, active_corpus_ids: list[str]) -> dict
```

They load the registry on invocation, construct validated contract requests, use a documented default reconciliation work budget, and return JSON-serializable dictionaries. Update the module docstring to label `search` and `recall` as legacy reduced-standing tools. Do not alter their signatures or output.

- [ ] **Step 4: Verify all MCP and complete llm-memory behavior**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q
```

Expected: all original and Stage 1 tests pass.

- [ ] **Step 5: Commit MCP integration**

```bash
cd /home/tony/projects/llm-memory
git add llm_memory/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: expose episodic contract MCP tools"
```

---

### Task 11: Real-Source Evaluation and Stage 1 Decision Record

**Files:**
- Create: `/home/tony/projects/llm-memory/eval/contract_journeys.py`
- Create: `/home/tony/projects/llm-memory/tests/test_contract_journeys.py`
- Create: `/home/tony/projects/qhaway/docs/superpowers/baselines/2026-07-12-ayllu-stage-1-evaluation.md`

**Interfaces:**
- Produces: non-content local journey report, acceptance-gate evidence, and exactly one Stage 1 decision.
- Consumes: all Stage 1 contract behavior and the historical unavailable-query standing.

- [ ] **Step 1: Write evaluation-output tests**

`contract_journeys.py` must emit JSON containing contract version, redacted enrollment identifiers, per-source/member standing, query and count outcomes, reconciliation bytes/time, validation age, index growth, purge counts, and declared limitations. It must never emit database credentials, absolute locators, full episode content, or raw source lines.

Test with temporary synthetic sources and assert forbidden marker text from those sources is absent from serialized output while episode-reference digests and counts remain.

- [ ] **Step 2: Implement the evaluation runner**

The CLI accepts `--config`, `--query`, `--limit`, and `--output`. It calls `search_history`, optionally opens only the expected qualified reference supplied through a local non-committed invocation, records standing rather than content, performs a selective test-corpus purge only when `--purge-test-corpus` is explicitly supplied, and writes JSON atomically.

Expose:

```python
def run_journey(config: Path, query: str, limit: int, expected_ref: str | None = None) -> dict: ...
def redact_journey(result: dict) -> dict: ...
def main(argv: list[str] | None = None) -> int: ...
```

- [ ] **Step 3: Verify portable evaluation behavior**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q tests/test_contract_journeys.py
```

Expected: pass without exposing fixture content.

- [ ] **Step 4: Run local real-source journeys without committing content**

Use an owner-controlled `config/sources.yaml` containing at least one available supported local source. Run bounded queries whose disclosure is acceptable and store raw JSON output outside both repositories. If no suitable source is available, record real-journey standing as unavailable rather than substituting synthetic success.

Also rerun the historical five-query evaluation only if its named source corpus is available under a concrete enrolled corpus ID. Otherwise retain the Stage 0 unavailable standing.

- [ ] **Step 5: Write the Stage 1 evidence record in qhaway**

The Markdown record must include revisions, dirty-file preservation, tests, identity perturbations, nested standing, count evidence, integrity-audit work, exact opening, lifecycle/purge results, real-journey standing, all eleven umbrella evaluation dimensions, declared losses, and one decision. It must state whether automatic bounded reconciliation converges under observed source growth, report Arango operational dependencies separately, and measure the additional indexed data projection. Do not calculate an aggregate score.

Decision rules:

- `continue` only if all fourteen acceptance gates in the focused specification are evidenced and Stage 2 comparison is warranted;
- `repair within the current boundary` if a Stage 1 contract gate remains achievable without changing the architecture;
- `stop because the capability did not earn continuation` if operational/privacy cost defeats its observed value; or
- `reframe because the evidence revealed a different problem` if stable identity and explicit standing were not the principal issue.

- [ ] **Step 6: Commit evaluation code in llm-memory**

```bash
cd /home/tony/projects/llm-memory
git add eval/contract_journeys.py tests/test_contract_journeys.py
git commit -m "test: add episodic contract journey evaluation"
```

- [ ] **Step 7: Commit the decision record in qhaway**

```bash
cd /home/tony/projects/qhaway
git add docs/superpowers/baselines/2026-07-12-ayllu-stage-1-evaluation.md
git commit -m "docs: record ayllu stage 1 decision"
```

---

### Task 12: Final Cross-Repository Verification and Scope Audit

**Files:**
- Verify only: both repositories and all Stage 1 artifacts.

**Interfaces:**
- Produces: completion evidence; no new behavior.

- [ ] **Step 1: Run both complete suites**

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q
cd /home/tony/projects/qhaway
uv run --frozen --group dev pytest -q
```

Expected: every original and Stage 1 `llm-memory` test passes; qhaway reports its complete suite passing.

- [ ] **Step 2: Verify the pre-existing dependency diff was preserved**

```bash
cd /home/tony/projects/llm-memory
git status --short
git diff -- pyproject.toml uv.lock | sha256sum
git diff --check
```

Expected at plan creation: only the independently owned `pyproject.toml` and `uv.lock` changes remain unstaged with digest `9fef9719b4cb9e426750097cb41e21c4f365490f6ef0d112c5e3cc526f094792`, unless the Task 1 baseline recorded a later user-owned digest.

- [ ] **Step 3: Audit implementation scope**

Run:

```bash
cd /home/tony/projects/llm-memory
rg -n 'scope="all"|include_mounted|facet|embedding|vector|Codex|AGENTS.md|CLAUDE.md' llm_memory tests eval
git diff e95e32f..HEAD --name-only
cd /home/tony/projects/qhaway
git diff 3d1ecf4..HEAD --name-only
```

Expected: matches appear only in legacy code/tests or explicit deferral/compatibility assertions; new runtime paths contain no forbidden later-stage capability. Qhaway changes after Stage 0 are specifications, plans, reviews, and the Stage 1 evidence record only.

- [ ] **Step 4: Verify source immutability and derived cleanup evidence**

Compare before/after digests for every synthetic and real source used in evaluation. Confirm test-corpus derived documents are purged or intentionally retained with their corpus/source IDs recorded. Never claim source preservation without these digests.

- [ ] **Step 5: Inspect final histories and worktrees**

```bash
git -C /home/tony/projects/llm-memory log --oneline --decorate -20
git -C /home/tony/projects/llm-memory status --short
git -C /home/tony/projects/qhaway log --oneline --decorate -12
git -C /home/tony/projects/qhaway status --short
```

Expected: Stage 1 commits are reviewable, qhaway is clean, and only the preserved user-owned dependency changes remain dirty in `llm-memory`.
