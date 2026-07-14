# Ayllu Stage 2A SQLite Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lifecycle-complete SQLite FTS5 episodic provider beside the existing Arango provider and prove their portable Stage 1 obligations with synthetic sources only.

**Architecture:** Keep episode identity, enrollment, adapters, work budgets, and source-backed opening shared. Wrap the repaired Arango implementation without changing its state machine; implement SQLite persistence, reconciliation, search, supersession, measurement, and purge independently behind a small provider protocol. Operational configuration selects exactly one provider, while the evaluation harness instantiates providers separately and never merges or falls back between them.

**Tech Stack:** Python 3.12, standard-library `sqlite3`, SQLite 3.50.4 with FTS5, python-arango, pytest, MCP/FastMCP, uv

## Global Constraints

- Implement in `/home/tony/projects/llm-memory`, branching from local `main` at `1826809` or a reviewed descendant; create an isolated worktree with `superpowers:using-git-worktrees` before Task 1.
- Preserve the owner-controlled modifications to `pyproject.toml` and `uv.lock`; do not stage, edit, or revert them unless the owner separately authorizes that work.
- Contract version remains exactly `1`.
- Preserve Arango strategy `lexical_bm25_text_en_v1` and public match semantics `analyzed_any_token`.
- Add SQLite strategy `lexical_bm25_fts5_porter_unicode61_v1` and public match semantics `analyzed_any_segment_phrase`.
- Configure FTS5 exactly as `tokenize = 'porter unicode61 remove_diacritics 2'` with default BM25 column weights.
- Encode SQLite queries by trimming, splitting on Unicode whitespace, escaping each segment as an FTS5 quoted string, and joining segments with explicit `OR`.
- Normalize SQLite public score as `-bm25(...)`, sort descending, then sort `episode_ref` ascending; never compare score magnitudes across providers.
- Index only `user_message`, `response`, and flattened `state_text`.
- Use separate SQLite connections per session or thread, WAL mode, foreign keys, a bounded busy timeout, and transactional compare-and-swap state transitions.
- Search results and all per-corpus and aggregate counts must come from one SQLite read transaction.
- A completed generation and its standing activate atomically; incomplete staging generations never become searchable.
- Exact opening always reads the authoritative source through the enrolled adapter. A selected provider may supply only a supersession observation after exact source resolution fails.
- Do not add vector, hybrid, graph, faceting, pagination, federation, resident projection, Codex/Gemini adapters, framework delivery, or private-history access.
- Phase A fixtures contain synthetic prose only. Do not read, copy, enumerate, hash, index, or open real conversation histories.
- Preserve existing Arango behavior with its current tests; do not refactor its reconciliation state machine merely for structural symmetry.

## File Map

New focused modules in `llm-memory`:

- `llm_memory/provider.py`: provider protocol, capability envelope, purge scope/classes, measurements, and retryable provider errors.
- `llm_memory/arango_provider.py`: thin facade over the existing Arango implementation.
- `llm_memory/opening.py`: shared source-backed opening with an injected supersession resolver.
- `llm_memory/sqlite_store.py`: SQLite connection policy, schema, transactions, state CAS, generation storage, and integrity primitives.
- `llm_memory/sqlite_reconcile.py`: bounded SQLite reconciliation using the existing source adapters and `WorkBudget`.
- `llm_memory/sqlite_history.py`: safe FTS5 query encoding, one-snapshot search/count, ranking, and public response assembly.
- `llm_memory/sqlite_lifecycle.py`: selective purge, complete file removal, rebuild standing, and physical measurement.
- `llm_memory/sqlite_provider.py`: SQLite provider facade.
- `llm_memory/provider_config.py`: explicit startup provider selection and lazy construction.
- `evaluation/stage2a_provider_experiment.py`: synthetic-only operational comparison runner and content-free result envelope.

Existing files changed deliberately:

- `llm_memory/contract.py`: permit provider-specific capability declarations while retaining contract v1 request validation.
- `llm_memory/history.py`: retain Arango search implementation and delegate shared opening to `opening.py`.
- `llm_memory/mcp_server.py`: route contract tools to one selected provider and keep legacy Arango tools lazy.
- `llm_memory/lifecycle.py`: retain declaration lifecycle and make Arango purge available to its facade.
- `tests/conftest.py`: reusable synthetic registries and provider contract fixtures.

---

### Task 1: Provider Contract and Arango Facade

**Files:**
- Create: `llm_memory/provider.py`
- Create: `llm_memory/arango_provider.py`
- Modify: `llm_memory/contract.py`
- Test: `tests/test_provider.py`
- Test: `tests/test_arango_provider.py`

**Interfaces:**
- Consumes: `EnrollmentRegistry`, `SourceEnrollment`, `SearchRequest`, `WorkBudget`, `ReconcileReport`, existing `history.search_history`, `reconcile.reconcile_registry`, `contract_index.ensure_contract_index`, and `lifecycle.purge_derived`.
- Produces: `EpisodicProvider`, `ProviderDescriptor`, `PurgeScope`, `ProviderMeasurement`, `ProviderUnavailable`, `ProviderUnsupported`, and `ArangoProvider`.

- [ ] **Step 1: Write contract validation and facade delegation tests**

```python
def test_provider_descriptor_declares_retrieval_basis():
    descriptor = ProviderDescriptor(
        provider="sqlite",
        implementation_version="1",
        strategies=("lexical_bm25_fts5_porter_unicode61_v1",),
        analyzer="porter unicode61 remove_diacritics 2",
        indexed_fields=("user_message", "response", "state_text"),
        match_semantics="analyzed_any_segment_phrase",
        score_ordering="normalized_desc_episode_ref_asc",
        raw_score_polarity="lower_is_better",
    )
    assert descriptor.as_dict()["raw_score_polarity"] == "lower_is_better"

def test_arango_provider_delegates_search_without_changing_request(arango_db, registry, budget, monkeypatch):
    observed = {}
    monkeypatch.setattr("llm_memory.arango_provider.arango_search", lambda db, reg, req, work: observed.update(request=req) or {"results": []})
    provider = ArangoProvider(arango_db)
    request = SearchRequest.create("reason", ["local"])
    assert provider.search(registry, request, budget) == {"results": []}
    assert observed["request"] is request
```

- [ ] **Step 2: Run the new tests and verify they fail because the provider modules do not exist**

Run: `uv run pytest tests/test_provider.py tests/test_arango_provider.py -q`

Expected: collection errors naming `llm_memory.provider` and `llm_memory.arango_provider`.

- [ ] **Step 3: Add the provider types and protocol**

```python
@dataclass(frozen=True)
class ProviderDescriptor:
    provider: str
    implementation_version: str
    strategies: tuple[str, ...]
    analyzer: str
    indexed_fields: tuple[str, ...]
    match_semantics: str
    score_ordering: str
    raw_score_polarity: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

@dataclass(frozen=True)
class PurgeScope:
    corpus_id: str | None = None
    source_id: str | None = None

    def __post_init__(self) -> None:
        if self.source_id is not None and self.corpus_id is None:
            raise ValueError("source_id requires corpus_id")

@dataclass(frozen=True)
class ProviderMeasurement:
    provider: str
    standing: str
    observations: dict[str, int | float | str | None]

class ProviderUnavailable(RuntimeError):
    """A bounded provider operation could not complete and may be retried."""

class ProviderUnsupported(RuntimeError):
    """The configured runtime cannot implement the declared provider."""

class EpisodicProvider(Protocol):
    def capabilities(self) -> dict[str, object]: ...
    def ensure(self) -> dict[str, object]: ...
    def reconcile(self, registry: EnrollmentRegistry, budget: WorkBudget) -> ReconcileReport: ...
    def search(self, registry: EnrollmentRegistry, request: SearchRequest, budget: WorkBudget) -> dict[str, object]: ...
    def resolve_supersession(self, enrollment: SourceEnrollment, old_ref: str) -> str | None: ...
    def purge(self, scope: PurgeScope, state_classes: frozenset[str]) -> dict[str, int]: ...
    def remove_all(self) -> dict[str, object]: ...
    def measure(self, scope: PurgeScope) -> ProviderMeasurement: ...
```

Make `ProviderCapabilities` accept explicit `strategies` as it already does, and leave `SearchRequest.create()` defaulting to the Arango `STRATEGY` for compatibility.

- [ ] **Step 4: Implement the thin Arango facade**

```python
class ArangoProvider:
    def __init__(self, db):
        self._db = db

    def capabilities(self) -> dict[str, object]:
        return ProviderCapabilities().as_dict() | {"retrieval_basis": ARANGO_DESCRIPTOR.as_dict()}

    def ensure(self) -> dict[str, object]:
        ensure_contract_index(self._db)
        return {"provider": "arango", "index_standing": "available"}

    def reconcile(self, registry, budget):
        return reconcile_registry(self._db, registry, budget)

    def search(self, registry, request, budget):
        return arango_search(self._db, registry, request, budget)

    def resolve_supersession(self, enrollment, old_ref):
        return arango_replacement_ref(self._db, enrollment, old_ref)

    def purge(self, scope, state_classes):
        return purge_derived_scope(self._db, scope, classes=state_classes)

    def remove_all(self):
        return remove_arango_contract_state(self._db)
```

Define `ARANGO_DESCRIPTOR` with provider `arango`, implementation version `1`, strategy `lexical_bm25_text_en_v1`, analyzer `text_en`, indexed fields `user_message`, `response`, and `state_text`, match semantics `analyzed_any_token`, and both raw/public score ordering `higher_is_better`. Implement `measure()` with explicit `standing` and collection document counts; do not present serialized document size as physical disk usage. `purge_derived_scope()` accepts global, corpus, or corpus/source scope. `remove_arango_contract_state()` drops only the episodic view and its three owned collections, reports exact removed object names and declared supersession loss, and never drops the Arango database or unrelated objects.

```python
def remove_arango_contract_state(db) -> dict[str, object]:
    removed = []
    if CONTRACT_VIEW in {view["name"] for view in db.views()}:
        db.delete_view(CONTRACT_VIEW)
        removed.append(CONTRACT_VIEW)
    for name in (CONTRACT_EPISODES, SOURCE_STATES, SUPERSESSIONS):
        if db.has_collection(name):
            db.delete_collection(name)
            removed.append(name)
    return {
        "removed_objects": removed,
        "declared_losses": ["retained supersession observations"],
    }
```

- [ ] **Step 5: Run focused and existing Arango contract tests**

Run: `uv run pytest tests/test_provider.py tests/test_arango_provider.py tests/test_history_search.py tests/test_reconcile.py tests/test_lifecycle.py -q`

Expected: all selected tests pass; existing public Arango responses are unchanged.

- [ ] **Step 6: Commit**

```bash
git add llm_memory/provider.py llm_memory/arango_provider.py llm_memory/contract.py tests/test_provider.py tests/test_arango_provider.py
git commit -m "refactor: define episodic provider boundary"
```

### Task 2: Shared Source-Backed Opening

**Files:**
- Create: `llm_memory/opening.py`
- Modify: `llm_memory/history.py`
- Modify: `llm_memory/arango_provider.py`
- Test: `tests/test_open_episode.py`

**Interfaces:**
- Consumes: `EpisodeReference`, `EnrollmentRegistry`, `SourceEnrollment`, `get_adapter()`, and `Callable[[SourceEnrollment, str], str | None]`.
- Produces: `open_episode(registry, episode_ref, active_corpus_ids, resolve_supersession)` with no database argument.

- [ ] **Step 1: Add tests proving exact opening ignores provider documents and supersession is injected**

```python
def test_exact_open_never_calls_supersession_resolver(registry, exact_episode_ref):
    def forbidden(_enrollment, _old_ref):
        raise AssertionError("exact source-backed opening must not consult provider state")
    response = open_episode(registry, exact_episode_ref, ["local"], forbidden)
    assert response["standing"] == "available"

def test_missing_open_uses_only_selected_supersession_resolver(registry, old_ref, new_ref):
    calls = []
    response = open_episode(registry, old_ref, ["local"], lambda enrollment, ref: calls.append((enrollment.source_id, ref)) or new_ref)
    assert response == {"contract_version": 1, "episode_ref": old_ref, "standing": "superseded", "replacement_ref": new_ref}
    assert calls == [("synthetic", old_ref)]
```

- [ ] **Step 2: Run opening tests and verify the new signature is absent**

Run: `uv run pytest tests/test_open_episode.py -q`

Expected: FAIL until `llm_memory.opening.open_episode` exists.

- [ ] **Step 3: Move source resolution into `opening.py` and inject the resolver**

```python
SupersessionResolver = Callable[[SourceEnrollment, str], str | None]

def open_episode(
    registry: EnrollmentRegistry,
    episode_ref: str,
    active_corpus_ids: list[str] | tuple[str, ...],
    resolve_supersession: SupersessionResolver,
) -> dict[str, object]:
    reference = EpisodeReference.parse(episode_ref)
    enrollment = _opening_enrollment(registry, reference, active_corpus_ids)
    # Retain the existing adapter scan, exact digest match, malformed,
    # unavailable, same-event mismatch, and missing ordering verbatim.
    replacement_ref = resolve_supersession(enrollment, episode_ref)
    if replacement_ref in by_ref:
        return _open_response(episode_ref, OpenStanding.SUPERSEDED, replacement_ref=replacement_ref)
    return _open_response(episode_ref, standing)
```

Keep `history.open_episode(db, ...)` as a compatibility wrapper that passes the existing Arango resolver. Export the resolver from `arango_provider.py` rather than duplicating its AQL.

- [ ] **Step 4: Run all opening and history tests**

Run: `uv run pytest tests/test_open_episode.py tests/test_history_search.py tests/test_arango_provider.py -q`

Expected: all pass, including legacy callers that still pass `db` to `history.open_episode`.

- [ ] **Step 5: Commit**

```bash
git add llm_memory/opening.py llm_memory/history.py llm_memory/arango_provider.py tests/test_open_episode.py
git commit -m "refactor: share source-backed episode opening"
```

### Task 3: SQLite Runtime, Connection Policy, and Schema

**Files:**
- Create: `llm_memory/sqlite_store.py`
- Test: `tests/test_sqlite_store.py`

**Interfaces:**
- Consumes: standard-library `sqlite3`, `Path`, `EpisodeRecord`, `SourceEnrollment`, and `SourceMember`.
- Produces: `SQLiteStore`, `SQLiteSchemaStanding`, `SQLiteStateConflict`, `SQLiteDocumentConflict`, `connect()`, `ensure()`, and transaction context managers.

- [ ] **Step 1: Add runtime, schema, trigger, and connection-isolation tests**

```python
def test_ensure_creates_exact_fts5_configuration(tmp_path):
    store = SQLiteStore(tmp_path / "episodes.sqlite3", busy_timeout_ms=50)
    assert store.ensure().index_standing == "available"
    with store.connect() as connection:
        sql = connection.execute("SELECT sql FROM sqlite_schema WHERE name = 'episode_fts'").fetchone()[0]
    assert "porter unicode61 remove_diacritics 2" in sql

def test_episode_triggers_keep_fts_copy_transactional(sqlite_store, episode_row):
    with sqlite_store.write_transaction() as connection:
        rowid = sqlite_store.insert_episode(connection, episode_row)
    assert sqlite_store.fts_row(rowid)["user_message"] == episode_row["user_message"]
    with pytest.raises(RuntimeError):
        with sqlite_store.write_transaction() as connection:
            sqlite_store.delete_episode(connection, rowid)
            raise RuntimeError("crash")
    assert sqlite_store.fts_row(rowid) is not None
```

- [ ] **Step 2: Run the store tests and verify they fail**

Run: `uv run pytest tests/test_sqlite_store.py -q`

Expected: collection failure for missing `llm_memory.sqlite_store`.

- [ ] **Step 3: Implement connection policy and the visible FTS5 probe**

```python
class SQLiteStore:
    def __init__(self, path: Path, *, busy_timeout_ms: int = 250):
        self.path = Path(path)
        self.busy_timeout_ms = busy_timeout_ms

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        return connection

    def _probe_fts5(self, connection: sqlite3.Connection) -> None:
        try:
            connection.execute("CREATE VIRTUAL TABLE temp.__fts5_probe USING fts5(value, tokenize='porter unicode61 remove_diacritics 2')")
            connection.execute("DROP TABLE temp.__fts5_probe")
        except sqlite3.OperationalError as exc:
            raise ProviderUnsupported("SQLite FTS5 porter/unicode61 is unavailable") from exc

@dataclass(frozen=True)
class SQLiteSchemaStanding:
    provider: str = "sqlite"
    schema_version: int = 1
    index_standing: str = "available"

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

class SQLiteStateConflict(RuntimeError):
    pass

class SQLiteDocumentConflict(RuntimeError):
    pass
```

Translate `sqlite3.OperationalError` containing `locked` or `busy` at provider operation boundaries into `ProviderUnavailable`; do not retry indefinitely.

- [ ] **Step 4: Create schema version 1 and self-contained FTS5 triggers**

```sql
CREATE TABLE provider_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE source_states (
  state_key TEXT PRIMARY KEY,
  corpus_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  member_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  state_json TEXT NOT NULL,
  UNIQUE(corpus_id, source_id, member_id)
);
CREATE TABLE episode_documents (
  rowid INTEGER PRIMARY KEY,
  storage_key TEXT NOT NULL UNIQUE,
  corpus_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  member_id TEXT NOT NULL,
  generation_id TEXT NOT NULL,
  episode_ref TEXT NOT NULL,
  reference_key TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  user_message TEXT NOT NULL,
  response TEXT NOT NULL,
  state_text TEXT NOT NULL,
  document_json TEXT NOT NULL,
  UNIQUE(generation_id, episode_ref)
);
CREATE VIRTUAL TABLE episode_fts USING fts5(
  user_message, response, state_text,
  storage_key UNINDEXED, corpus_id UNINDEXED, generation_id UNINDEXED,
  tokenize='porter unicode61 remove_diacritics 2'
);
CREATE TABLE supersessions (
  observation_key TEXT PRIMARY KEY,
  corpus_id TEXT NOT NULL, source_id TEXT NOT NULL, member_id TEXT NOT NULL,
  event_token TEXT NOT NULL, old_ref TEXT NOT NULL, new_ref TEXT NOT NULL,
  reason TEXT NOT NULL, detected_at TEXT NOT NULL,
  UNIQUE(old_ref, new_ref)
);
CREATE TRIGGER episode_ai AFTER INSERT ON episode_documents BEGIN
  INSERT INTO episode_fts(rowid,user_message,response,state_text,storage_key,corpus_id,generation_id)
  VALUES(new.rowid,new.user_message,new.response,new.state_text,new.storage_key,new.corpus_id,new.generation_id);
END;
CREATE TRIGGER episode_ad AFTER DELETE ON episode_documents BEGIN
  DELETE FROM episode_fts WHERE rowid=old.rowid;
END;
CREATE TRIGGER episode_au AFTER UPDATE ON episode_documents BEGIN
  DELETE FROM episode_fts WHERE rowid=old.rowid;
  INSERT INTO episode_fts(rowid,user_message,response,state_text,storage_key,corpus_id,generation_id)
  VALUES(new.rowid,new.user_message,new.response,new.state_text,new.storage_key,new.corpus_id,new.generation_id);
END;
```

Store `schema_version=1` and reject an unknown schema version visibly. The FTS table deliberately duplicates searchable text; measurements must name this duplication.

- [ ] **Step 5: Run schema tests, including a no-FTS monkeypatch and two independent connections**

Run: `uv run pytest tests/test_sqlite_store.py -q`

Expected: all pass; unsupported FTS and lock timeout have distinct visible exceptions.

- [ ] **Step 6: Commit**

```bash
git add llm_memory/sqlite_store.py tests/test_sqlite_store.py
git commit -m "feat: add sqlite episodic schema"
```

### Task 4: SQLite Generation and State Primitives

**Files:**
- Modify: `llm_memory/sqlite_store.py`
- Test: `tests/test_sqlite_generations.py`

**Interfaces:**
- Consumes: schema from Task 3 and existing `EpisodeRecord`, `SourceEnrollment`, `SourceMember`.
- Produces: `source_states()`, `member_state()`, `compare_and_swap_state()`, `write_generation()`, `seed_generation()`, `generation_count()`, `delete_generation()`, `activate_generation()`, and `verify_generation()`.

- [ ] **Step 1: Add tests for immutable rows, CAS, and atomic activation**

```python
def test_state_compare_and_swap_rejects_stale_revision(sqlite_store, enrollment, member):
    original = sqlite_store.compare_and_swap_state(enrollment, member.member_id, None, {"active_generation_id": None})
    sqlite_store.compare_and_swap_state(enrollment, member.member_id, original, {"freshness_standing": "incomplete"})
    with pytest.raises(SQLiteStateConflict):
        sqlite_store.compare_and_swap_state(enrollment, member.member_id, original, {"freshness_standing": "current"})

def test_incomplete_generation_is_not_active_after_rollback(sqlite_store, enrollment, member, episodes):
    with pytest.raises(RuntimeError):
        with sqlite_store.write_transaction() as connection:
            sqlite_store.write_generation(connection, enrollment, member, "g1", episodes)
            sqlite_store.activate_generation(connection, enrollment, member, "g1", expected_count=len(episodes))
            raise RuntimeError("crash before commit")
    assert sqlite_store.member_state(enrollment, member.member_id) is None
```

- [ ] **Step 2: Run generation tests and verify missing methods**

Run: `uv run pytest tests/test_sqlite_generations.py -q`

Expected: failures naming the unimplemented generation methods.

- [ ] **Step 3: Implement JSON state serialization and revision CAS**

```python
def compare_and_swap_state(self, enrollment, member_id, expected, values):
    state_key = _state_key(enrollment.corpus_id, enrollment.source_id, member_id)
    with self.write_transaction() as connection:
        current = self._state_row(connection, state_key)
        expected_revision = None if expected is None else expected["revision"]
        current_revision = None if current is None else current["revision"]
        if current_revision != expected_revision:
            raise SQLiteStateConflict(state_key)
        state = _merge_state(current, enrollment, member_id, values)
        revision = 1 if current is None else current_revision + 1
        connection.execute(STATE_UPSERT_SQL, (state_key, enrollment.corpus_id, enrollment.source_id, member_id, revision, canonical_json(state)))
    return state | {"revision": revision}
```

Use canonical JSON (`sort_keys=True`, compact separators) and retain the same logical state keys and standings the Arango reconciler reports.

- [ ] **Step 4: Implement immutable generation writes, seeding, validation, and activation**

`write_generation()` must compare an existing `(generation_id, episode_ref)` document byte-for-byte and raise `SQLiteDocumentConflict` on different content. `seed_generation()` copies active rows into a new generation in the same transaction and returns both copied row count and elapsed database work. `activate_generation()` verifies count and FTS row presence before changing `active_generation_id`, `episode_count`, integrity, and freshness in one transaction.

```python
def activate_generation(self, connection, enrollment, member, generation_id, *, expected_count):
    actual_count = self.generation_count(connection, generation_id)
    indexed_count = connection.execute("SELECT count(*) FROM episode_fts WHERE generation_id=?", (generation_id,)).fetchone()[0]
    if (actual_count, indexed_count) != (expected_count, expected_count):
        raise SQLiteDocumentConflict(generation_id)
    self._cas_state_in_transaction(connection, enrollment, member.member_id, expected_state, {
        "active_generation_id": generation_id,
        "staging_generation_id": None,
        "episode_count": expected_count,
        "active_generation_integrity": "valid",
    })
```

- [ ] **Step 5: Run generation and store tests**

Run: `uv run pytest tests/test_sqlite_store.py tests/test_sqlite_generations.py -q`

Expected: all pass, including rollback and stale-writer fixtures.

- [ ] **Step 6: Commit**

```bash
git add llm_memory/sqlite_store.py tests/test_sqlite_generations.py
git commit -m "feat: add sqlite generation state machine"
```

### Task 5: Bounded SQLite Reconciliation

**Files:**
- Create: `llm_memory/sqlite_reconcile.py`
- Modify: `llm_memory/sqlite_store.py`
- Test: `tests/test_sqlite_reconcile.py`

**Interfaces:**
- Consumes: `SQLiteStore`, `WorkBudget`, `ReconcileReport`, existing adapters, enrollment types, and `reconcile.extend_chain()`.
- Produces: `reconcile_registry(store, registry, budget) -> ReconcileReport` with the Stage 1 nested standing shape.

- [ ] **Step 1: Port portable synthetic reconciliation fixtures as SQLite tests**

Cover initial partial build, resume, append, multi-member source sets, malformed input, unavailable source, prefix rewrite, truncation, semantic-version rejection, periodic full validation, supersession creation, and a zero-result but exact current source.

```python
def test_partial_build_persists_staging_but_not_active(sqlite_store, synthetic_registry):
    report = reconcile_registry(sqlite_store, synthetic_registry, WorkBudget(32, NOW))
    member = report.corpus_standing[0]["sources"][0]["members"][0]
    assert member["freshness_standing"] == "incomplete"
    assert sqlite_store.active_episode_refs("local", "synthetic") == ()
    assert sqlite_store.staging_episode_count("local", "synthetic") > 0

def test_rewrite_records_supersession_without_mutating_source(sqlite_store, rewrite_fixture):
    reconcile_registry(sqlite_store, rewrite_fixture.before_registry, WorkBudget(1_000_000, NOW))
    rewrite_fixture.apply_rewrite()
    rewritten_bytes = rewrite_fixture.original_source.read_bytes()
    reconcile_registry(sqlite_store, rewrite_fixture.after_registry, WorkBudget(1_000_000, LATER))
    assert sqlite_store.resolve_supersession(rewrite_fixture.enrollment, rewrite_fixture.old_ref) == rewrite_fixture.new_ref
    assert rewrite_fixture.original_source.read_bytes() == rewritten_bytes
```

The final assertion proves reconciliation did not alter the already-rewritten authoritative source.

- [ ] **Step 2: Run the SQLite reconciliation tests and observe failures**

Run: `uv run pytest tests/test_sqlite_reconcile.py -q`

Expected: failures because `sqlite_reconcile.reconcile_registry` is absent.

- [ ] **Step 3: Implement an independent SQLite reconciliation loop**

Reuse adapter scans, cursors, chain digests, work charging, and public standing construction. Do not call Arango reconciliation or translate Arango documents.

```python
def reconcile_registry(store: SQLiteStore, registry: EnrollmentRegistry, budget: WorkBudget) -> ReconcileReport:
    started = time.monotonic()
    corpus_reports = []
    for corpus_id in sorted(registry.known_corpora):
        source_reports = [_reconcile_source(store, source, budget) for source in registry.sources_for(corpus_id)]
        corpus_reports.append({"corpus_id": corpus_id, "sources": source_reports})
    return ReconcileReport(tuple(corpus_reports), budget.bytes_read, (time.monotonic() - started) * 1000, budget.exhausted)
```

On each member: inspect source standing, validate cursor/integrity, create or resume a staging generation, charge only authoritative bytes to `WorkBudget`, record provider database seeding work separately, and activate only after complete scan and integrity verification. Once the budget is exhausted, continue emitting `incomplete`/`unknown` nested standing for every remaining enrolled source without reading more source bytes; never omit a requested corpus from the report.

- [ ] **Step 4: Add bounded conflict handling and supersession observations**

Catch `SQLiteStateConflict` at the same logical retry boundary as Arango's `_StateConflict`. A bounded retry either returns a defensible current/incomplete report or raises `ProviderUnavailable`; it must not overwrite a newer state. When the same native session/event token has a changed digest, insert a rebuildable old-ref/new-ref observation with a deterministic key and timestamp.

```python
def _record_supersession(connection, enrollment, member, old_ref, new_ref, now):
    observation_key = hashlib.sha256(f"{old_ref}\0{new_ref}".encode()).hexdigest()
    old = EpisodeReference.parse(old_ref)
    connection.execute(
        "INSERT OR IGNORE INTO supersessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (observation_key, enrollment.corpus_id, enrollment.source_id, member.member_id,
         old.event_token, old_ref, new_ref, "same_event_content_changed", _timestamp(now)),
    )

def _with_one_state_retry(operation):
    try:
        return operation()
    except SQLiteStateConflict:
        try:
            return operation()
        except SQLiteStateConflict as exc:
            raise ProviderUnavailable("concurrent reconciliation did not converge") from exc
```

- [ ] **Step 5: Run SQLite and Arango reconciliation suites together**

Run: `uv run pytest tests/test_sqlite_reconcile.py tests/test_reconcile.py -q`

Expected: all pass; provider-specific internals may differ, public nested standings do not silently improve.

- [ ] **Step 6: Commit**

```bash
git add llm_memory/sqlite_reconcile.py llm_memory/sqlite_store.py tests/test_sqlite_reconcile.py
git commit -m "feat: reconcile episodic sources into sqlite"
```

### Task 6: SQLite Search and Exact Population Counts

**Files:**
- Create: `llm_memory/sqlite_history.py`
- Test: `tests/test_sqlite_history.py`

**Interfaces:**
- Consumes: `SQLiteStore`, SQLite reconciliation, `SearchRequest`, and existing public standing/result helpers extracted only where behavior is provider-neutral.
- Produces: `SQLITE_STRATEGY`, `encode_fts5_query()`, and `search_history()`.

- [ ] **Step 1: Add query-encoding, score, one-snapshot, and standing tests**

```python
@pytest.mark.parametrize(("query", "encoded"), [
    ("why cache", '"why" OR "cache"'),
    ('why OR "drop"', '"why" OR "OR" OR """drop"""'),
    ("caf\u00e9\tdecision", '"caf\u00e9" OR "decision"'),
])
def test_encode_fts5_query_treats_input_as_text(query, encoded):
    assert encode_fts5_query(query) == encoded

def test_search_normalizes_bm25_and_uses_deterministic_tie_break(sqlite_provider, current_registry, budget):
    response = sqlite_provider.search(current_registry, SearchRequest.create("reason", ["local"], strategy=SQLITE_STRATEGY), budget)
    assert response["match_semantics"] == "analyzed_any_segment_phrase"
    assert response["results"] == sorted(response["results"], key=lambda hit: (-hit["score"], hit["episode_ref"]))
```

Add a two-connection fixture where a writer commits between the count and result statements; both statements must remain on the reader's original snapshot.

- [ ] **Step 2: Run SQLite history tests and verify failures**

Run: `uv run pytest tests/test_sqlite_history.py -q`

Expected: missing module/function failures.

- [ ] **Step 3: Implement safe query encoding and strategy validation**

```python
SQLITE_STRATEGY = "lexical_bm25_fts5_porter_unicode61_v1"

def encode_fts5_query(query: str) -> str:
    segments = query.strip().split()
    return " OR ".join(f'"{segment.replace(chr(34), chr(34) * 2)}"' for segment in segments)

def _validated_request(request: SearchRequest) -> SearchRequest:
    if request.strategy != SQLITE_STRATEGY:
        raise ContractError(f"unsupported strategy: {request.strategy}")
    return request
```

- [ ] **Step 4: Implement one-read-snapshot search and exact-or-unknown totals**

Begin a read transaction after reconciliation. Select only enabled source members whose active generation has valid integrity and stored/indexed counts matching `episode_count`. Run both grouped count and bounded result queries before committing the read transaction.

```sql
SELECT d.*, -bm25(episode_fts) AS score
FROM episode_fts
JOIN episode_documents AS d ON d.rowid = episode_fts.rowid
JOIN source_states AS s
  ON s.corpus_id=d.corpus_id AND s.source_id=d.source_id AND s.member_id=d.member_id
WHERE episode_fts MATCH ?
  AND d.corpus_id IN (...)
  AND d.generation_id=json_extract(s.state_json, '$.active_generation_id')
  AND json_extract(s.state_json, '$.active_generation_integrity')='valid'
ORDER BY score DESC, d.episode_ref ASC
LIMIT ?;
```

Use the same active-generation predicate for the grouped population query. Report `indexed_matches` and aggregate `total_matches` only when every requested corpus is fully backed; otherwise use `null` with `unknown`. Build snippets from returned documents and preserve heuristic match attribution.

- [ ] **Step 5: Run focused search and legacy Arango search tests**

Run: `uv run pytest tests/test_sqlite_history.py tests/test_history_search.py -q`

Expected: all pass; SQLite and Arango expose their distinct strategy and match semantics.

- [ ] **Step 6: Commit**

```bash
git add llm_memory/sqlite_history.py tests/test_sqlite_history.py
git commit -m "feat: search episodic history with sqlite fts5"
```

### Task 7: SQLite Purge, Full Removal, and Measurement

**Files:**
- Create: `llm_memory/sqlite_lifecycle.py`
- Test: `tests/test_sqlite_lifecycle.py`

**Interfaces:**
- Consumes: `SQLiteStore`, `PurgeScope`, and state classes `episodes`, `reconciliation`, `supersessions`.
- Produces: `purge()`, `remove_provider_file()`, and `measure()`.

- [ ] **Step 1: Add lifecycle journey tests**

```python
def test_selective_purge_counts_each_class_without_touching_source(sqlite_store, populated_fixture):
    before = populated_fixture.source.read_bytes()
    report = purge(sqlite_store, PurgeScope("local", "synthetic"), frozenset({"episodes", "supersessions"}))
    assert report["episodes"] > 0
    assert report["supersessions"] >= 0
    assert populated_fixture.source.read_bytes() == before

def test_full_removal_declares_supersession_loss(sqlite_store, populated_fixture):
    report = remove_provider_file(sqlite_store)
    assert report["removed_paths"]
    assert "retained supersession observations" in report["declared_losses"]
    assert not sqlite_store.path.exists()
```

Cover `-wal` and `-shm` residual paths, source-level purge, corpus-level purge, rebuild after purge, and removal when files are already absent.

- [ ] **Step 2: Run lifecycle tests and verify missing functions**

Run: `uv run pytest tests/test_sqlite_lifecycle.py -q`

Expected: collection failure for `llm_memory.sqlite_lifecycle`.

- [ ] **Step 3: Implement exact transactional purge**

```python
DERIVED_CLASSES = frozenset({"episodes", "reconciliation", "supersessions"})

def purge(store: SQLiteStore, scope: PurgeScope, state_classes: frozenset[str]) -> dict[str, int]:
    _validate_scope_and_classes(scope, state_classes)
    with store.write_transaction() as connection:
        counts = {}
        if "episodes" in state_classes:
            counts["episodes"] = _delete_scoped(connection, "episode_documents", scope)
        if "reconciliation" in state_classes:
            counts["reconciliation"] = _delete_scoped(connection, "source_states", scope)
        if "supersessions" in state_classes:
            counts["supersessions"] = _delete_scoped(connection, "supersessions", scope)
    return counts
```

Deleting episode rows must invoke the FTS trigger in the same transaction. Purging reconciliation without episodes intentionally makes retained episode generations inactive and unauthorized for search.

- [ ] **Step 4: Implement physical measurement and complete removal reports**

`measure()` reports database, WAL, and SHM bytes separately with `stat` standing, row counts separately with query standing, and names self-contained FTS duplication. `remove_provider_file()` closes the operation's connection, removes the configured file and its `-wal`/`-shm` companions, lists residual paths, and declares loss of retained supersession/evaluation state; it never deletes source locators or enrollment configuration.

```python
def remove_provider_file(store: SQLiteStore) -> dict[str, object]:
    candidates = (store.path, Path(f"{store.path}-wal"), Path(f"{store.path}-shm"))
    removed = []
    for path in candidates:
        if path.exists():
            path.unlink()
            removed.append(path.name)
    residual = [path.name for path in candidates if path.exists()]
    return {
        "removed_paths": removed,
        "residual_paths": residual,
        "declared_losses": ["retained supersession observations", "non-reproducible evaluation state"],
    }

def measure(store: SQLiteStore, scope: PurgeScope) -> ProviderMeasurement:
    paths = {"database_bytes": store.path, "wal_bytes": Path(f"{store.path}-wal"), "shm_bytes": Path(f"{store.path}-shm")}
    observations = {name: path.stat().st_size if path.exists() else 0 for name, path in paths.items()}
    observations.update(store.scoped_row_counts(scope))
    observations["fts_representation"] = "self_contained_duplicate"
    return ProviderMeasurement("sqlite", "available", observations)
```

- [ ] **Step 5: Run SQLite and Arango lifecycle suites**

Run: `uv run pytest tests/test_sqlite_lifecycle.py tests/test_lifecycle.py -q`

Expected: all pass; removal reports distinguish retained configuration, source bytes, and derived state.

- [ ] **Step 6: Commit**

```bash
git add llm_memory/sqlite_lifecycle.py tests/test_sqlite_lifecycle.py
git commit -m "feat: add sqlite episodic lifecycle"
```

### Task 8: SQLite Provider Facade

**Files:**
- Create: `llm_memory/sqlite_provider.py`
- Test: `tests/test_sqlite_provider.py`

**Interfaces:**
- Consumes: all SQLite modules from Tasks 3-7 and the `EpisodicProvider` protocol.
- Produces: `SQLiteProvider(path: Path, busy_timeout_ms: int = 250)`.

- [ ] **Step 1: Add end-to-end facade tests**

```python
def test_sqlite_provider_satisfies_protocol(tmp_path, registry, budget):
    provider: EpisodicProvider = SQLiteProvider(tmp_path / "episodes.sqlite3")
    assert provider.ensure()["index_standing"] == "available"
    response = provider.search(registry, SearchRequest.create("reason", ["local"], strategy=SQLITE_STRATEGY), budget)
    assert response["strategy"] == SQLITE_STRATEGY
    assert provider.capabilities()["retrieval_basis"]["provider"] == "sqlite"

def test_sqlite_provider_opening_uses_its_supersession_only(sqlite_provider, rewritten_registry, old_ref):
    response = open_episode(rewritten_registry, old_ref, ["local"], sqlite_provider.resolve_supersession)
    assert response["standing"] in {"superseded", "missing"}
```

- [ ] **Step 2: Run facade tests and verify the class is missing**

Run: `uv run pytest tests/test_sqlite_provider.py -q`

Expected: collection failure for missing `SQLiteProvider`.

- [ ] **Step 3: Implement the facade by direct delegation**

```python
class SQLiteProvider:
    def __init__(self, path: Path, *, busy_timeout_ms: int = 250):
        self.store = SQLiteStore(path, busy_timeout_ms=busy_timeout_ms)

    def capabilities(self):
        return ProviderCapabilities(strategies=(SQLITE_STRATEGY,)).as_dict() | {"retrieval_basis": SQLITE_DESCRIPTOR.as_dict()}

    def ensure(self):
        return self.store.ensure().as_dict()

    def reconcile(self, registry, budget):
        return sqlite_reconcile(self.store, registry, budget)

    def search(self, registry, request, budget):
        return sqlite_search(self.store, registry, request, budget)

    def resolve_supersession(self, enrollment, old_ref):
        return self.store.resolve_supersession(enrollment, old_ref)

    def purge(self, scope, state_classes):
        return sqlite_purge(self.store, scope, state_classes)

    def remove_all(self):
        return remove_provider_file(self.store)

    def measure(self, scope):
        return sqlite_measure(self.store, scope)
```

Define `SQLITE_DESCRIPTOR` in `sqlite_provider.py` with provider `sqlite`, implementation version `1`, the exact FTS5 strategy/tokenizer/indexed fields/match semantics above, public ordering `normalized_desc_episode_ref_asc`, and raw score polarity `lower_is_better`.

- [ ] **Step 4: Run all SQLite tests**

Run: `uv run pytest tests/test_sqlite_store.py tests/test_sqlite_generations.py tests/test_sqlite_reconcile.py tests/test_sqlite_history.py tests/test_sqlite_lifecycle.py tests/test_sqlite_provider.py -q`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add llm_memory/sqlite_provider.py tests/test_sqlite_provider.py
git commit -m "feat: expose sqlite episodic provider"
```

### Task 9: Explicit Operational Provider Selection and MCP Routing

**Files:**
- Create: `llm_memory/provider_config.py`
- Modify: `llm_memory/mcp_server.py`
- Test: `tests/test_provider_config.py`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `ArangoProvider`, `SQLiteProvider`, `get_database()`, and environment variables.
- Produces: `load_provider()` using `LLM_MEMORY_PROVIDER` and `LLM_MEMORY_SQLITE_PATH`.

- [ ] **Step 1: Add provider selection and lazy initialization tests**

```python
def test_default_provider_remains_arango(monkeypatch):
    monkeypatch.delenv("LLM_MEMORY_PROVIDER", raising=False)
    assert isinstance(load_provider(), ArangoProvider)

def test_sqlite_selection_never_connects_to_arango(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MEMORY_PROVIDER", "sqlite")
    monkeypatch.setenv("LLM_MEMORY_SQLITE_PATH", str(tmp_path / "episodes.sqlite3"))
    monkeypatch.setattr("llm_memory.provider_config.get_database", lambda: (_ for _ in ()).throw(AssertionError("Arango must stay lazy")))
    assert isinstance(load_provider(), SQLiteProvider)

def test_unknown_provider_fails_visibly(monkeypatch):
    monkeypatch.setenv("LLM_MEMORY_PROVIDER", "fallback")
    with pytest.raises(ValueError, match="LLM_MEMORY_PROVIDER"):
        load_provider()
```

- [ ] **Step 2: Run selection and MCP tests and verify failures**

Run: `uv run pytest tests/test_provider_config.py tests/test_mcp_server.py -q`

Expected: failures until selection is explicit and MCP import no longer eagerly constructs `_db`.

- [ ] **Step 3: Implement exact startup selection**

```python
def load_provider() -> EpisodicProvider:
    provider_name = os.environ.get("LLM_MEMORY_PROVIDER", "arango")
    if provider_name == "arango":
        return ArangoProvider(get_database())
    if provider_name == "sqlite":
        raw_path = os.environ.get("LLM_MEMORY_SQLITE_PATH")
        if not raw_path:
            raise ValueError("LLM_MEMORY_SQLITE_PATH is required for sqlite")
        return SQLiteProvider(Path(raw_path))
    raise ValueError("LLM_MEMORY_PROVIDER must be 'arango' or 'sqlite'")
```

Do not auto-select based on provider availability. Do not instantiate the unselected provider.

- [ ] **Step 4: Route contract MCP tools through one lifespan-selected provider**

The lifespan loads the registry and provider once into process-local module state, calls `provider.ensure()` and `provider.reconcile()`, and clears the state on shutdown. `search_history` uses that same selected provider. `open_episode` passes only its `resolve_supersession` method to shared opening. Keep legacy `search` and `recall` Arango-only, but acquire their database lazily on invocation so a SQLite contract server can start without Arango.

```python
_selected_provider: EpisodicProvider | None = None
_selected_registry: EnrollmentRegistry | None = None

def _contract_runtime() -> tuple[EpisodicProvider, EnrollmentRegistry]:
    if _selected_provider is None or _selected_registry is None:
        raise RuntimeError("episodic provider lifespan is not active")
    return _selected_provider, _selected_registry

@asynccontextmanager
async def _lifespan(_server):
    global _selected_provider, _selected_registry
    provider = load_provider()
    provider.ensure()
    registry = load_registry()
    report = provider.reconcile(registry, _budget())
    _selected_provider, _selected_registry = provider, registry
    try:
        yield {"startup_reconciliation": report}
    finally:
        _selected_provider = _selected_registry = None

@mcp.tool()
def search_history(query: str, corpus_ids: list[str], limit: int = 10) -> dict:
    provider, registry = _contract_runtime()
    strategy = provider.capabilities()["strategies"][0]
    request = SearchRequest.create(query, corpus_ids, limit=limit, strategy=strategy)
    return provider.search(registry, request, _budget())

@mcp.tool()
def open_episode(episode_ref: str, active_corpus_ids: list[str]) -> dict:
    provider, registry = _contract_runtime()
    return source_open_episode(registry, episode_ref, active_corpus_ids, provider.resolve_supersession)
```

- [ ] **Step 5: Run MCP, provider, and legacy compatibility tests**

Run: `uv run pytest tests/test_provider_config.py tests/test_mcp_server.py tests/test_history_search.py tests/test_search.py tests/test_recall.py -q`

Expected: all pass; default behavior remains Arango and explicit SQLite startup makes no Arango connection.

- [ ] **Step 6: Commit**

```bash
git add llm_memory/provider_config.py llm_memory/mcp_server.py tests/test_provider_config.py tests/test_mcp_server.py
git commit -m "feat: select episodic provider explicitly"
```

### Task 10: Portable Provider Contract and Concurrency Fixtures

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/provider_contract.py`
- Create: `tests/test_provider_contract_arango.py`
- Create: `tests/test_provider_contract_sqlite.py`
- Create: `tests/test_sqlite_concurrency.py`

**Interfaces:**
- Consumes: `EpisodicProvider`, synthetic registry factories, and provider-specific fixtures.
- Produces: `SyntheticSourceFixture` and `assert_portable_provider_contract(provider_factory, synthetic_source)` with shared cases executed separately for Arango and SQLite.

- [ ] **Step 1: Extract a provider-neutral synthetic contract suite**

The shared suite must assert identity preservation, nested standing, bounded reconciliation/resume, exact-or-unknown count, deterministic bounded results, exact source opening, rewrite supersession, disable/reenable, retained data after unenroll, state-class purge, rebuild, and no cross-provider fallback.

```python
@dataclass(frozen=True)
class SyntheticSourceFixture:
    registry: EnrollmentRegistry
    path: Path
    original_bytes: bytes

def assert_portable_provider_contract(provider, registry, source, strategy):
    provider.ensure()
    first = provider.search(registry, SearchRequest.create("decision", ["local"], limit=1, strategy=strategy), WorkBudget(1_000_000, NOW))
    assert first["returned_count"] <= 1
    assert first["total_standing"] in {"exact", "unknown"}
    if first["results"]:
        opened = open_episode(registry, first["results"][0]["episode_ref"], ["local"], provider.resolve_supersession)
        assert opened["standing"] == "available"
    assert source.path.read_bytes() == source.original_bytes
```

- [ ] **Step 2: Run shared suites against both providers**

Run: `uv run pytest tests/test_provider_contract_arango.py tests/test_provider_contract_sqlite.py -q`

Expected: both pass without normalizing their strategy identifiers, tokenizers, match semantics, or scores.

- [ ] **Step 3: Add real parallel SQLite writer, lock, and crash fixtures**

Use eight threads, each with its own `SQLiteStore.connect()` connection and a barrier start. Assert either successful CAS progression or bounded `ProviderUnavailable`, never lost state or partial active generations. Hold `BEGIN IMMEDIATE` on one connection longer than `busy_timeout_ms` and assert the contender exits visibly. Simulate a process-level crash with a subprocess that writes staging rows and exits before commit; reopen and prove no partial generation is active.

```python
with ThreadPoolExecutor(max_workers=8) as pool:
    outcomes = list(pool.map(lambda _: reconcile_with_new_connection(), range(8)))
assert all(outcome in {"available", "retryable"} for outcome in outcomes)
assert sqlite_store.verify_all_active_generations()
```

- [ ] **Step 4: Run concurrency tests repeatedly**

Run: `for run in 1 2 3 4 5; do uv run pytest tests/test_sqlite_concurrency.py -q || exit 1; done`

Expected: five clean runs with no hangs, raw `database is locked` leakage, or partial activation.

- [ ] **Step 5: Run existing and portable provider suites together**

Run: `uv run pytest tests/test_reconcile.py tests/test_history_search.py tests/test_lifecycle.py tests/test_open_episode.py tests/test_provider_contract_arango.py tests/test_provider_contract_sqlite.py tests/test_sqlite_concurrency.py -q`

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/provider_contract.py tests/test_provider_contract_arango.py tests/test_provider_contract_sqlite.py tests/test_sqlite_concurrency.py
git commit -m "test: verify portable episodic providers"
```

### Task 11: Synthetic Stage 2A Evaluation Runner

**Files:**
- Create: `evaluation/stage2a_provider_experiment.py`
- Create: `tests/test_stage2a_provider_experiment.py`
- Create: `docs/stage2a-provider-evaluation-schema.md`

**Interfaces:**
- Consumes: separately constructed `ArangoProvider` and `SQLiteProvider`, synthetic sources, `ProviderMeasurement`, and provider capability envelopes.
- Produces: `Stage2AExperiment`, `run_stage2a()`, and `write_report_atomic()` for a JSON-serializable Phase A report containing no source prose, query text, paths, credentials, ports, or raw episode references.

- [ ] **Step 1: Add report redaction and independent-provider tests**

```python
def test_report_excludes_content_and_identifiers(synthetic_experiment):
    report = run_stage2a(synthetic_experiment)
    encoded = json.dumps(report, sort_keys=True)
    for forbidden in synthetic_experiment.private_values:
        assert forbidden not in encoded
    assert set(report["providers"]) == {"arango", "sqlite"}
    assert "aggregate_score" not in report

def test_provider_failure_is_not_fallback(synthetic_experiment):
    synthetic_experiment.arango.search = Mock(side_effect=ProviderUnavailable("offline"))
    report = run_stage2a(synthetic_experiment)
    assert report["providers"]["arango"]["standing"] == "unavailable"
    assert report["providers"]["sqlite"]["standing"] == "available"
```

- [ ] **Step 2: Run evaluation tests and verify missing runner**

Run: `uv run pytest tests/test_stage2a_provider_experiment.py -q`

Expected: missing module failure.

- [ ] **Step 3: Implement a content-free measurement envelope**

```python
@dataclass(frozen=True)
class Stage2AExperiment:
    arango: EpisodicProvider
    sqlite: EpisodicProvider
    registry: EnrollmentRegistry
    requests: tuple[SearchRequest, ...]
    private_values: tuple[str, ...]

def run_stage2a(experiment: Stage2AExperiment) -> dict[str, object]:
    return {
        "stage": "2A",
        "contract_version": 1,
        "source_basis": "synthetic_only",
        "providers": {
            name: _run_provider(name, provider, experiment)
            for name, provider in (("arango", experiment.arango), ("sqlite", experiment.sqlite))
        },
        "decision": "phase_a_checkpoint_only",
    }

def write_report_atomic(path: Path, report: dict[str, object]) -> None:
    payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
```

Each provider record declares implementation version, strategy, analyzer/tokenizer, indexed fields, match semantics, public/raw score polarity, schema readiness, source bytes read, provider database work, elapsed measurement basis, exact/unknown totals, derived physical bytes with standing, lock/outage standing, purge counts, rebuild standing, full-removal residuals, and declared losses. Do not compute a winner or aggregate score.

- [ ] **Step 4: Document the report schema and privacy boundary**

The schema document must state that Phase A proves mechanics only, contains synthetic data only, does not establish rationale usefulness, does not authorize Phase B or real histories, and reports provider-local scores without magnitude comparison.

```markdown
# Stage 2A Provider Evaluation Schema

This envelope records synthetic provider mechanics only. It establishes neither
rationale-recovery usefulness nor authority to inspect native tool histories.

Provider records retain independent readiness, strategy, match semantics, score
polarity, exactness, resource basis, purge standing, residual state, and declared
loss. Provider-local BM25 magnitudes are not comparable and no aggregate score
or backend winner is produced.

Phase B remains unauthorized until a separate real-source manifest is reviewed.
```

- [ ] **Step 5: Run evaluation and privacy tests**

Run: `uv run pytest tests/test_stage2a_provider_experiment.py -q`

Expected: all pass, including atomic write failure tests that leave no partial public report.

- [ ] **Step 6: Commit**

```bash
git add evaluation/stage2a_provider_experiment.py tests/test_stage2a_provider_experiment.py docs/stage2a-provider-evaluation-schema.md
git commit -m "feat: add synthetic stage 2a provider evaluation"
```

### Task 12: Full Verification and Phase A Checkpoint

**Files:**
- Create in qhaway: `docs/superpowers/baselines/2026-07-14-ayllu-stage-2a-evaluation.md`
- Modify only if verification exposes a defect: files owned by Tasks 1-11 with a failing regression test committed beside the repair.

**Interfaces:**
- Consumes: reviewed endpoints of Tasks 1-11.
- Produces: exact verification evidence and one Phase A checkpoint standing: `ready_for_phase_b_authorization`, `repair`, `stop`, or `reframe`.

- [ ] **Step 1: Run formatting and static repository checks**

Run: `git diff --check $(git merge-base main HEAD)..HEAD`

Expected: no whitespace errors.

Run the repository's configured lint/type commands if present in `pyproject.toml`; record `not configured` rather than inventing an unreviewed tool when absent.

- [ ] **Step 2: Run the complete llm-memory suite from a clean test environment**

Run: `uv run pytest -q`

Expected: all tests pass. Record the exact count, commit hash, Python version, SQLite version, and `sqlite_compileoption_used('ENABLE_FTS5')`/portable-probe standing.

- [ ] **Step 3: Verify the owner-controlled dependency files were not changed by Stage 2A**

Run: `git diff -- pyproject.toml uv.lock`

Expected: only the owner's pre-existing DuckDB-related changes remain outside the Stage 2A commits; compare their digest with the execution-session starting digest and stop if it changed.

- [ ] **Step 4: Run qhaway's suite before recording cross-repository evidence**

Run: `uv run pytest -q`

Working directory: `/home/tony/projects/qhaway`

Expected: all tests pass.

- [ ] **Step 5: Write the Phase A checkpoint in qhaway**

The checkpoint records reviewed commit hashes, test counts, provider descriptors, synthetic fixture scope, concurrency repetitions, startup/readiness standing, one-snapshot count evidence, purge/removal residuals, declared FTS duplication, Arango service assumptions, defects repaired, and a gate-by-gate accounting limited to Stage 2 acceptance gates 1-6, 15, 18, and 19. It must state explicitly:

```text
No real conversation source was read, copied, enumerated, hashed, indexed, or opened.
Phase A does not establish rationale-recovery usefulness and does not authorize Phase B.
```

- [ ] **Step 6: Request independent code review before changing the checkpoint standing**

Invoke `superpowers:requesting-code-review` against the complete Stage 2A diff. Repair substantive findings with reproducing tests, rerun Steps 1-4, and append reviewer disposition to the checkpoint.

- [ ] **Step 7: Commit the qhaway checkpoint**

```bash
git add docs/superpowers/baselines/2026-07-14-ayllu-stage-2a-evaluation.md
git commit -m "docs: record ayllu stage 2a evaluation"
```

Do not merge, delete the feature worktree, inspect native Codex/Gemini formats, or propose a real-corpus manifest as part of this task. Branch integration uses `superpowers:finishing-a-development-branch` only after the independent review is closed.

---

## Phase A Completion Boundary

This plan is complete when the provider boundary and SQLite FTS5 peer pass the synthetic portable fixtures, both repositories' existing suites pass, independent review findings are closed, and the qhaway checkpoint records evidence without private content. The checkpoint may authorize preparation of a Phase B manifest proposal, but it cannot itself authorize source-format inspection or real-corpus access.
