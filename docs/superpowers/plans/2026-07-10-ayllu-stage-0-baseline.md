# Ayllu Stage 0 Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Characterize current qhaway and `llm-memory` behavior, preserve the evidence in a reviewable decision record, and decide whether Stage 1 is earned without implementing any later-stage capability.

**Architecture:** Stage 0 is an evidence-only slice. It exercises the existing test, lifecycle, ingestion, and retrieval surfaces; records source and environment standing separately from product behavior; and creates declarative adversarial fixtures for later stages without adding a shared runtime or new storage.

**Tech Stack:** Markdown, YAML, Python >=3.14, pytest, uv, SQLite 3, ArangoDB/ArangoSearch, existing qhaway and `llm-memory` commands only.

## Global Constraints

- The approved umbrella is `docs/superpowers/specs/2026-07-10-qhaway-ayllu-memory-design.md`; Stage 0 does not revise its authority model or authorize Stage 1.
- Do not modify qhaway product code, `llm-memory` product code, either database schema, or any authoritative memory/conversation source.
- Do not install dependencies, ingest a corpus, rebuild an ArangoSearch view, or delete pre-existing persistent state during this stage. Existing tests may create and remove their uniquely keyed test records as designed.
- `llm-memory/pyproject.toml` and `llm-memory/uv.lock` were already modified before Stage 0. Do not stage, edit, restore, or attribute those changes to this work.
- Never commit database credentials, absolute paths containing credentials, or raw conversation and memory content. Counts, identifiers, digests, standing, and redacted snippets are acceptable evidence.
- Keep source availability, index availability, index freshness, query correctness, and retrieval quality as separate observations.
- Report fidelity, declared loss, selectivity, dissent retention, provenance, continuity, isolation, recoverability, unobtrusiveness, generativity, and complexity independently. Do not calculate an aggregate score.
- End with exactly one decision: `continue`, `repair within the current boundary`, `stop because the capability did not earn continuation`, or `reframe because the evidence revealed a different problem`.
- A `continue` decision means only that a focused Stage 1 episodic-contract specification is earned. It does not authorize Stage 1 implementation.

---

### Task 1: Freeze the Baseline Boundary and Evidence Protocol

**Files:**
- Create: `docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md`

**Interfaces:**
- Consumes: the approved umbrella, qhaway commit `6c90f8655a9e651218ae849d76d0fccb2029a80f`, and `llm-memory` commit `e95e32fbc739a4f5d3e21131b506472214346ce2`.
- Produces: the single Stage 0 evidence and decision record used by Tasks 2-5.

- [ ] **Step 1: Verify that the implementation starts from the reviewed product revisions**

Run:

```bash
git -C /home/tony/projects/qhaway log -1 --format='%H %s' 6c90f8655a9e651218ae849d76d0fccb2029a80f
git -C /home/tony/projects/llm-memory log -1 --format='%H %s' e95e32fbc739a4f5d3e21131b506472214346ce2
git -C /home/tony/projects/llm-memory status --short
```

Expected: both commits resolve; the `llm-memory` status includes the pre-existing `M pyproject.toml` and `M uv.lock`. Additional changes must be described in the report before proceeding, and none may be silently included in Stage 0.

- [ ] **Step 2: Create the evidence record with explicit observation rules**

Create `docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md` with this initial content:

```markdown
# Ayllu Stage 0 Baseline

**Umbrella:** `docs/superpowers/specs/2026-07-10-qhaway-ayllu-memory-design.md`
**Observation date:** 2026-07-10
**Boundary:** Evidence gathering only; no Stage 1 capability is implemented or authorized here.

## Revisions and Environment

| Surface | Reviewed revision | Worktree standing | Runtime dependency standing |
|---|---|---|---|
| qhaway | `6c90f8655a9e651218ae849d76d0fccb2029a80f` | Recorded before execution | Python, uv, and SQLite recorded below |
| llm-memory | `e95e32fbc739a4f5d3e21131b506472214346ce2` | Pre-existing modifications to `pyproject.toml` and `uv.lock`; untouched by Stage 0 | Python, uv, ArangoDB, and ArangoSearch recorded below |

Command outputs in this report are summaries, not raw transcripts. A passing test establishes only the behavior asserted by that test. A failed evaluation is classified separately as an unavailable source, unavailable index, stale index, contract mismatch, implementation defect, or retrieval-quality result before it is used as evidence.

## qhaway Baseline

## llm-memory Baseline

## Adversarial Fixture Standing

## Evaluation Dimensions

## Stage Decision
```

- [ ] **Step 3: Record tool and dependency standing without disclosing configuration**

Run:

```bash
python3 --version
uv --version
sqlite3 --version
docker ps --format '{{.Image}} {{.Status}}' | sed -E 's/(arangodb[^ ]*).*/\1 running/' | sort -u
```

Expected: version/status output only. Record exact versions under `Revisions and Environment`; record an unavailable command or container as an operational dependency failure, not a product failure.

- [ ] **Step 4: Commit the bounded evidence shell**

```bash
git add docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md
git commit -m "docs: establish ayllu stage 0 evidence boundary"
```

Expected: the commit contains only the new baseline Markdown file.

---

### Task 2: Characterize qhaway Projection and Lifecycle Behavior

**Files:**
- Modify: `docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md`

**Interfaces:**
- Consumes: existing qhaway tests and temporary pytest directories.
- Produces: evidence for projection fidelity, declared loss, recoverability, continuity, unobtrusiveness, and lifecycle preservation. It does not modify a real Claude memory directory.

- [ ] **Step 1: Run the frozen qhaway suite**

Run:

```bash
cd /home/tony/projects/qhaway
uv run --frozen --group dev pytest -q
```

Expected at the reviewed revision: `137 passed`. Record the exact result and elapsed time under `qhaway Baseline`.

- [ ] **Step 2: Exercise the current session lifecycle and non-destructive disengagement assertions**

Run:

```bash
cd /home/tony/projects/qhaway
uv run --frozen --group dev pytest -q \
  tests/test_lifecycle_integration.py \
  tests/test_exit_sequence.py \
  tests/test_setup.py \
  tests/test_cli_session.py
```

Expected: PASS. In the report, name the assertions this establishes: dormancy without topic files, activation after a topic appears, preservation of a pre-install `MEMORY.md`, signed bounded exit projection, truthful omission count, and removal of only qhaway-owned configuration.

- [ ] **Step 3: Exercise projection loss and derived-state recovery assertions**

Run:

```bash
cd /home/tony/projects/qhaway
uv run --frozen --group dev pytest -q \
  tests/test_qhaway.py::test_cli_budget_overflow_handling \
  tests/test_qhaway.py::test_cli_no_silent_omissions \
  tests/test_qhaway.py::test_unit_reconcile_schema_auto_rebuild \
  tests/test_qhaway.py::test_unit_rebuild_on_drift_bounded \
  tests/test_qhaway.py::test_cli_concurrent_remember_no_lost_body \
  tests/test_qhaway.py::test_cli_destructive_rebuild_serialized
```

Expected: six passing tests. Record what each assertion covers and explicitly record what current qhaway does not cover: cross-corpus conflict envelopes, bilateral isolation, export withdrawal, framework switching, and Codex delivery.

- [ ] **Step 4: Add the qhaway evidence table**

Under `qhaway Baseline`, add one row per command group with these columns:

```markdown
| Probe | Result | Established | Not established |
|---|---|---|---|
```

Populate `Result` from the observed commands. Use assertion names for `Established`; do not infer runtime behavior that the selected tests do not exercise.

- [ ] **Step 5: Commit the qhaway characterization**

```bash
git add docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md
git commit -m "docs: record qhaway stage 0 baseline"
```

Expected: only the baseline report changes.

---

### Task 3: Characterize llm-memory Source, Schema, and Retrieval Standing

**Files:**
- Modify: `docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md`

**Interfaces:**
- Consumes: the existing ArangoDB collection and views read-only, `eval/queries.yaml`, and existing tests/evaluation scripts.
- Produces: a separated account of implementation tests, current corpus shape, fixture availability, and query outcomes. It does not ingest, delete, update, or reindex data.

- [ ] **Step 1: Run the frozen llm-memory suite**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q
```

Expected at the reviewed revision: `17 passed`. Record the exact result while noting that these tests use a live ArangoDB and unique temporary records that they clean up.

- [ ] **Step 2: Record aggregate corpus shape and expected-fixture standing without reading conversation text**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen python - <<'PY'
from llm_memory.db import get_database

db = get_database()
rows = db.aql.execute('''
FOR doc IN episodes
  COLLECT label = doc.experiment_label, has_cycle = HAS(doc, "cycle")
  AGGREGATE count = LENGTH(1)
  SORT label, has_cycle
  RETURN {label, has_cycle, count}
''')
print("corpus shape:")
for row in rows:
    print(row)
print("expected episode standing:")
for key in ("000430", "000431", "000444", "000456", "000457"):
    doc = db.collection("episodes").get(key)
    print({
        "key": key,
        "present": doc is not None,
        "cycle": None if doc is None else doc.get("cycle"),
        "label": None if doc is None else doc.get("experiment_label"),
    })
PY
```

Expected from the planning observation: the collection contains `claude_code` records with `cycle` and `yanantin_construction` records without `cycle`; keys `000430`, `000431`, `000444`, `000456`, and `000457` are absent. Treat any changed result as current evidence, not as a reason to rewrite history.

- [ ] **Step 3: Replay the real retrieval queries and preserve exit semantics**

Run each command independently so the expected nonzero replay exit does not suppress later evidence:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen python eval/replay.py
uv run --frozen python eval/stress.py
```

Expected from the planning observation: `replay.py` exits 1 with 0/5 because the expected source episodes are absent; `stress.py` reports the expected cycles absent from the top ten. Do not classify those results as retrieval-quality failures: first classify them as unavailable evaluation evidence caused by absent source episodes and unscoped mixed-corpus hits. Do not run `eval/compare.py`; it calls `ensure_index()` and updates or creates ArangoSearch views.

- [ ] **Step 4: Run the state-only comparison without changing either view**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen python - <<'PY'
from pathlib import Path
import yaml

from llm_memory.db import get_database
from llm_memory.evaluate import hit_at_k
from llm_memory.index import VIEW
from llm_memory.search import search

STATE_ONLY_VIEW = "episodes_state_only"
spec = yaml.safe_load(Path("eval/queries.yaml").read_text())
db = get_database()
available = {view["name"] for view in db.views()}
required = {VIEW, STATE_ONLY_VIEW}
if not required <= available:
    print({"standing": "unavailable", "missing_views": sorted(required - available)})
else:
    k = spec.get("k", 3)
    totals = {"state_only": 0, "conversation_inclusive": 0}
    for item in spec["queries"]:
        expected = item["expected"]
        state = [hit["cycle"] for hit in search(db, item["query"], limit=k, view=STATE_ONLY_VIEW)]
        conversation = [hit["cycle"] for hit in search(db, item["query"], limit=k, view=VIEW)]
        totals["state_only"] += hit_at_k(state, expected, k)
        totals["conversation_inclusive"] += hit_at_k(conversation, expected, k)
    print({"standing": "observed", "queries": len(spec["queries"]), **totals})
PY
```

Expected from the planning observation: both required views exist and both totals are 0/5. If a view is absent, record the comparison as unavailable; do not create it.

- [ ] **Step 5: Characterize existing source adapters using their isolated test records**

Run:

```bash
cd /home/tony/projects/llm-memory
uv run --frozen pytest -q \
  tests/test_ingest.py \
  tests/test_search.py \
  tests/test_recall.py \
  tests/test_mcp_server.py
```

Expected: PASS. Record separately that taste_open identity is cycle-based, gateway identity is session plus synthesized sequence, Claude Code identity is session plus assistant UUID, and no Codex adapter has yet been characterized. Also record that current `search()` can return mixed corpora under `scope="all"`, and that Claude-session records do not carry `cycle`.

- [ ] **Step 6: Add the llm-memory evidence table and known-failure entry**

Under `llm-memory Baseline`, use:

```markdown
| Probe | Source standing | Index standing | Result | Interpretation |
|---|---|---|---|---|
```

Add a distinct known-failure entry for the stale evaluation fixture assumption: the five real queries name cycle-addressed episodes that are not present in the current collection, while the default query scope admits corpora without `cycle`. State that Stage 1 must make corpus identity and result identity explicit before retrieval quality can be compared honestly.

- [ ] **Step 7: Commit the llm-memory characterization without staging its worktree**

```bash
git -C /home/tony/projects/llm-memory status --short
git -C /home/tony/projects/qhaway add docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md
git -C /home/tony/projects/qhaway commit -m "docs: record llm-memory stage 0 baseline"
```

Expected: the first command still shows the pre-existing dependency-file changes; the qhaway commit contains only the baseline report.

---

### Task 4: Establish Declarative Adversarial Fixtures

**Files:**
- Create: `docs/superpowers/baselines/2026-07-10-ayllu-stage-0-adversarial-fixtures.yaml`
- Modify: `docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md`

**Interfaces:**
- Consumes: umbrella authority, withdrawal, conflict, isolation, and provenance invariants.
- Produces: non-sensitive, backend-neutral scenario inputs for focused later-stage specifications. These fixtures assert expected standing but do not pretend current software implements it.

- [ ] **Step 1: Create the fixture catalog**

Create `docs/superpowers/baselines/2026-07-10-ayllu-stage-0-adversarial-fixtures.yaml` with exactly:

```yaml
schema_version: 1
standing: declarative_only
fixtures:
  - id: curated-conflict-local-mounted
    earliest_stage: 4
    arrangement:
      local_memory: consumer:local-position
      mounted_memory: source:foreign-position
      consumer_local_relationship: consumer:conflict-1
    perturbation: project a budget that cannot fit both positions in full
    expected:
      - no position appears as an unqualified standalone assertion
      - any partial envelope declares the number and standing of omitted positions

  - id: export-withdrawal
    earliest_stage: 4
    arrangement:
      exporter: source
      consumer: consumer
      mounted_memory: source:withdrawn-position
    perturbation: source removes the named-consumer export
    expected:
      - foreign content and owner identity are suppressed
      - a retained consumer-local conflict discloses only withdrawn position count and standing
      - consumer-local authoritative state survives

  - id: missing-episode-evidence
    earliest_stage: 1
    arrangement:
      memory_reference: source/session-1/episode-1
      source_standing: unavailable
    perturbation: open the exact episode reference
    expected:
      - the reference resolves to an honest unavailable standing
      - no cached snippet is presented as authoritative episode content

  - id: bilateral-isolation
    earliest_stage: 4
    arrangement:
      exporter: source
      authorized_consumer: consumer-a
      unauthorized_consumer: consumer-b
    perturbation: consumer-b declares a mount without a matching named-consumer export
    expected:
      - access is denied
      - cached coordinator state does not authorize access

  - id: stale-index-bounded-search
    earliest_stage: 1
    arrangement:
      source_standing: available
      index_standing: stale
      result_limit: 1
    perturbation: search while reconciliation is incomplete
    expected:
      - at most one result is returned
      - total-match standing and indexed-through standing are separate
      - incompleteness is declared
```

- [ ] **Step 2: Validate fixture shape and required coverage**

Run:

```bash
cd /home/tony/projects/qhaway
uv run --frozen python - <<'PY'
from pathlib import Path
import yaml

path = Path("docs/superpowers/baselines/2026-07-10-ayllu-stage-0-adversarial-fixtures.yaml")
data = yaml.safe_load(path.read_text())
assert data["schema_version"] == 1
assert data["standing"] == "declarative_only"
fixtures = {item["id"]: item for item in data["fixtures"]}
required = {
    "curated-conflict-local-mounted",
    "export-withdrawal",
    "missing-episode-evidence",
    "bilateral-isolation",
    "stale-index-bounded-search",
}
assert set(fixtures) == required
assert all(item["expected"] for item in fixtures.values())
print("5 declarative fixtures validated")
PY
```

Expected: `5 declarative fixtures validated`.

- [ ] **Step 3: Record fixture standing honestly**

Under `Adversarial Fixture Standing`, state that all five fixtures are established as reviewable scenarios and none is executable in current qhaway/`llm-memory` federation because Stage 1 and Stage 4 contracts do not exist. Map each fixture to its `earliest_stage`; do not mark declarative coverage as passing product behavior.

- [ ] **Step 4: Commit the fixtures and standing**

```bash
git add \
  docs/superpowers/baselines/2026-07-10-ayllu-stage-0-adversarial-fixtures.yaml \
  docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md
git commit -m "docs: establish ayllu adversarial fixtures"
```

Expected: the commit contains only the fixture catalog and its report section.

---

### Task 5: Evaluate Without Aggregation and Make the Stage Decision

**Files:**
- Modify: `docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md`

**Interfaces:**
- Consumes: all evidence and fixture standing from Tasks 1-4.
- Produces: the Stage 0 decision and explicit preconditions for any focused Stage 1 specification.

- [ ] **Step 1: Add one evidence-backed finding for every evaluation dimension**

Under `Evaluation Dimensions`, add this table and populate every row from named probes or explicitly mark it `not observable at Stage 0` with the reason:

```markdown
| Dimension | Finding | Evidence | Declared limitation |
|---|---|---|---|
| Fidelity | | | |
| Declared loss | | | |
| Selectivity | | | |
| Dissent retention | | | |
| Provenance | | | |
| Continuity | | | |
| Isolation | | | |
| Recoverability | | | |
| Unobtrusiveness | | | |
| Generativity | | | |
| Complexity | | | |
```

Do not add numeric ratings, weights, colors, or an overall score.

- [ ] **Step 2: Apply the decision rule**

Choose exactly one decision using these gates:

- `continue` only if current behavior and known failures are sufficiently characterized to write a focused Stage 1 episodic-contract specification, and the missing historical evaluation corpus is recorded as a contract/input problem rather than hidden.
- `repair within the current boundary` if Stage 0 evidence is internally ambiguous because an existing baseline probe, fixture, or read-only diagnostic is defective and can be repaired without designing Stage 1.
- `stop because the capability did not earn continuation` if episodic evidence adds no observable value beyond current curated projection or its operational/removal cost defeats the umbrella constraints.
- `reframe because the evidence revealed a different problem` if the principal problem is not stable episodic identity and bounded retrieval standing.

Under `Stage Decision`, write the selected phrase verbatim, followed by evidence for the choice and evidence against the strongest alternative. This is a reasoned decision, not a vote or score.

- [ ] **Step 3: State the only permitted continuation**

If and only if the decision is `continue`, list these Stage 1 specification preconditions:

1. Define a result identity that does not assume every corpus has `cycle`.
2. Require concrete corpus scope in the evaluation fixture and retrieval contract.
3. Separate source, index, freshness, and match-population standing.
4. Define bounded results plus exact or explicitly unavailable total-match standing.
5. Characterize taste_open, gateway, and Claude Code identity; characterize Codex only after its actual source format is observed.
6. Preserve ArangoDB as the implementation under test; do not select or implement SQLite FTS5 in Stage 1.

For any other decision, state the bounded repair, stopping condition, or reframed question instead.

- [ ] **Step 4: Run final integrity checks**

Run:

```bash
cd /home/tony/projects/qhaway
rg -n 'FIXME|PLACEHOLDER|\|[[:space:]]*\||aggregate score|weighted total' \
  docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md \
  docs/superpowers/baselines/2026-07-10-ayllu-stage-0-adversarial-fixtures.yaml
git diff --check
uv run --frozen --group dev pytest -q
git -C /home/tony/projects/llm-memory status --short
```

Expected: no unfinished markers or empty table cells; any occurrence of `aggregate score` or `weighted total` appears only in a prohibition; `git diff --check` is silent; qhaway reports all tests passing; `llm-memory` still shows only its independently owned worktree changes unless the report explicitly documented others.

- [ ] **Step 5: Commit the completed Stage 0 decision record**

```bash
git add docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md
git commit -m "docs: decide ayllu stage 0 outcome"
git status --short
```

Expected: the qhaway worktree is clean. No commit in this plan changes product behavior or begins Stage 1.
