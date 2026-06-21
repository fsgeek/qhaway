# Qhaway MCP Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the MCP spine over qhaway's existing truncation-cure pipeline: two MCP verbs (`remember`, `recall`), a SQLite-backed persistent index, one shared `reconcile` operation, and a read-only MEMORY.md redirect — so a Claude Code instance reaches its memory through tools instead of hand-writing files.

**Architecture:** Files stay the source of truth; the SQLite index at `<memory_dir>/.qhaway.db` is a derived, rebuildable view. `remember` writes a topic file then reconciles; `recall` is a pure read via the projection engine; `reconcile` is the one shared sync op (incremental stat sweep + self-healing read-only redirect). The existing `parse.py` is reused unchanged; `model.py`/`project.py` are ported from DuckDB to stdlib SQLite; `reconcile.py` and `server.py` are new; `cli.py` gains `reconcile`/`check`/`serve` and aliases `index`→`reconcile`.

**Tech Stack:** Python ≥3.14, stdlib `sqlite3` (WAL mode), `pyyaml`, `fcntl` (POSIX lock), MCP server SDK. DuckDB is removed.

**Spec:** `docs/superpowers/specs/2026-06-21-qhaway-mcp-spine-design.md` (converged through 7 review rounds).

**The test suite is already authored** (`tests/test_qhaway.py`) against this exact design — it imports `qhaway.server`, calls `cli.reconcile`, `model.get_connection`, `project.project_slice_with_overflow`, etc. **This plan makes those already-failing tests pass in dependency order.** Do not rewrite the tests to match the implementation; implement to satisfy the tests. The test names referenced in each task are the falsifiable contract.

## Global Constraints

- **Python ≥ 3.14** (`requires-python` in `pyproject.toml`); do not lower it.
- **Stdlib SQLite only** — no DuckDB, no new third-party DB dependency. Remove `duckdb` from `pyproject.toml` dependencies; keep `pyyaml`.
- **Files are the source of truth.** The DB is derived and rebuildable by deletion. `remember` writes a *file*, never the DB directly.
- **WAL is required, not best-effort.** If `PRAGMA journal_mode=WAL` fails, raise loud (message containing `"WAL"`); never fall back to a rollback journal.
- **All SQL uses `?` parameter bindings** — never string interpolation of parsed fields.
- **All file I/O uses explicit `encoding="utf-8"`.**
- **Idempotence is sacred:** the derived MEMORY.md is a pure function of the topic files — no run-varying content; every ordering ends in a `file`-name terminal tiebreak.
- **No silent loss:** omissions are declared; a hand-edited MEMORY.md is preserved to `MEMORY-<ts>.md` before overwrite.
- **DB artifacts** (`.qhaway.db`, `.qhaway.db-wal`, `.qhaway.db-shm`, `.qhaway.db.reset.lock`) are gitignored and excluded from `topic_files`.
- **Run tests with:** `uv run pytest tests/test_qhaway.py -v` (or `-k <name>` for one test). Commit after each task with a passing suite for that task's tests.

---

### Task 1: SQLite model core — connection, schema, fetch_nodes

**Files:**
- Modify: `src/qhaway/model.py` (rework from DuckDB to SQLite)
- Modify: `pyproject.toml:15-18` (remove `duckdb` dependency)
- Test: `tests/test_qhaway.py::test_unit_model_build_index`

**Interfaces:**
- Consumes: `qhaway.parse.parse_memory_file(filepath: str) -> dict` (unchanged), `qhaway.model.topic_files(memory_dir) -> list[Path]` (keep existing exclusion logic, extend exclusions).
- Produces:
  - `SCHEMA_VERSION: int` (= 1)
  - `get_connection(memory_dir: str) -> sqlite3.Connection` — opens/creates `<memory_dir>/.qhaway.db`, sets WAL (fail loud if unavailable), ensures schema (rebuild on drift), and on first creation populates from topic files. Row access by column name (set `conn.row_factory = sqlite3.Row` internally, but `fetch_nodes` returns plain dicts).
  - `fetch_nodes(conn) -> list[dict]` — all node rows as dicts keyed by column name.
  - `DB_NAME = ".qhaway.db"`, `LOCK_NAME = ".qhaway.db.reset.lock"`

- [ ] **Step 1: Read the failing test to confirm the contract**

Read `tests/test_qhaway.py::test_unit_model_build_index` (lines ~168-231). Note it requires: `model.get_connection(dir)` returns a connection over a db that *already contains* nodes parsed from the dir's topic files; `model.fetch_nodes(conn)` returns dicts with keys `file, content_type, role, status, mtime_ns, size`; `edges` table has `(src_file, dst_slug, kind)`; an index named containing `idx_edges_dst` exists.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_qhaway.py::test_unit_model_build_index -v`
Expected: FAIL (ImportError or AttributeError — `get_connection`/`fetch_nodes` not defined).

- [ ] **Step 3: Rewrite `model.py` for SQLite**

Replace the DuckDB implementation with:

```python
"""Build the embedded qhaway SQLite index from topic files."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from qhaway.parse import parse_memory_file

SCHEMA_VERSION = 1
DB_NAME = ".qhaway.db"
LOCK_NAME = ".qhaway.db.reset.lock"
_DB_SUFFIXES = ("", "-wal", "-shm")

_CREATE_NODES = """
CREATE TABLE IF NOT EXISTS nodes (
    file TEXT PRIMARY KEY,
    name TEXT,
    content_type TEXT,
    description TEXT,
    role TEXT,
    status TEXT,
    origin_session TEXT,
    date_hint TEXT,
    body TEXT,
    mtime_ns INTEGER,
    size INTEGER
)
"""

_CREATE_EDGES = """
CREATE TABLE IF NOT EXISTS edges (
    src_file TEXT NOT NULL,
    dst_slug TEXT NOT NULL,
    kind TEXT NOT NULL,
    PRIMARY KEY (src_file, dst_slug, kind)
)
"""

_CREATE_EDGE_INDEX = "CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges (dst_slug)"

_NODE_COLUMNS = (
    "file", "name", "content_type", "description", "role",
    "status", "origin_session", "date_hint", "body", "mtime_ns", "size",
)


def db_path(memory_dir: str | Path) -> Path:
    return Path(memory_dir) / DB_NAME


def get_connection(memory_dir: str) -> sqlite3.Connection:
    root = Path(memory_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"memory directory is not readable: {memory_dir}")

    conn = _open_wal(db_path(root))
    if _schema_drifted(conn):
        conn.close()
        rebuild_database(str(root))
        conn = _open_wal(db_path(root))
    else:
        _ensure_populated(conn, root)
    return conn


def _open_wal(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    except sqlite3.OperationalError as exc:
        conn.close()
        raise RuntimeError(
            "qhaway requires SQLite WAL mode, which this filesystem does not "
            f"support (move the memory dir to local storage): {exc}"
        ) from exc
    if mode is not None and str(mode[0]).lower() != "wal":
        conn.close()
        raise RuntimeError(
            "qhaway requires SQLite WAL mode; the filesystem refused it "
            "(move the memory dir to local storage)"
        )
    conn.execute(_CREATE_NODES)
    conn.execute(_CREATE_EDGES)
    conn.execute(_CREATE_EDGE_INDEX)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    return conn


def _schema_drifted(conn: sqlite3.Connection) -> bool:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        # version 0 with a pre-existing nodes table = old schema
        existing = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='nodes'"
        ).fetchone()
        if existing is not None and version < SCHEMA_VERSION:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(nodes)")}
            if not {"mtime_ns", "size"}.issubset(cols):
                return True
    return False


def _ensure_populated(conn: sqlite3.Connection, root: Path) -> None:
    count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    if count == 0:
        _full_load(conn, root)


def _full_load(conn: sqlite3.Connection, root: Path) -> None:
    conn.execute("DELETE FROM edges")
    conn.execute("DELETE FROM nodes")
    for path in topic_files(root):
        _upsert_file(conn, path)
    conn.commit()


def _upsert_file(conn: sqlite3.Connection, path: Path) -> None:
    node = parse_memory_file(str(path))
    if node.get("parse_warning"):
        sys.stderr.write(f"warning: {path.name}: {node['parse_warning']}\n")
    stat = path.stat()
    conn.execute("DELETE FROM edges WHERE src_file = ?", [node["file"]])
    conn.execute(
        f"INSERT OR REPLACE INTO nodes ({', '.join(_NODE_COLUMNS)}) "
        f"VALUES ({', '.join('?' for _ in _NODE_COLUMNS)})",
        [
            node["file"], node["name"], node["content_type"], node.get("description"),
            node["role"], node["status"], node["origin_session"], node["date_hint"],
            node["body"], stat.st_mtime_ns, stat.st_size,
        ],
    )
    for dst_slug in node["links"]:
        conn.execute(
            "INSERT OR IGNORE INTO edges (src_file, dst_slug, kind) VALUES (?, ?, 'REFERENCES')",
            [node["file"], dst_slug],
        )


def fetch_nodes(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(f"SELECT {', '.join(_NODE_COLUMNS)} FROM nodes").fetchall()
    return [dict(row) for row in rows]


def rebuild_database(memory_dir: str) -> None:
    """Destructively delete all db files and rebuild from topic files (drift recovery)."""
    raise NotImplementedError  # Implemented in Task 6


def execute_query_with_retry(conn, query, memory_dir, params=None):
    raise NotImplementedError  # Implemented in Task 6


def topic_files(memory_dir: str | Path) -> list[Path]:
    """Return source topic Markdown files, excluding derived indexes and backups."""
    root = Path(memory_dir)
    files: list[Path] = []
    for path in root.glob("*.md"):
        if path.name == "MEMORY.md" or path.name.startswith("MEMORY-"):
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.name)
```

Then in `pyproject.toml` remove `"duckdb",` from `dependencies` (keep `"pyyaml",`).

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_qhaway.py::test_unit_model_build_index -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/qhaway/model.py pyproject.toml
git commit -m "feat(model): port index to stdlib SQLite (WAL), drop duckdb"
```

---

### Task 2: Port projection to SQLite + add project_slice_with_overflow

**Files:**
- Modify: `src/qhaway/project.py` (replace `DESCRIBE` introspection; add overflow sibling)
- Test: `tests/test_qhaway.py::test_unit_project_sort_tiebreak`, `::test_cli_budget_overflow_handling`

**Interfaces:**
- Consumes: `model.fetch_nodes(conn)` (Task 1).
- Produces:
  - `project_slice(db_conn, budget, content_type=None, role=None, status="live") -> str` (signature **unchanged** — stable MVP API).
  - `project_slice_with_overflow(db_conn, budget, content_type=None, role=None, status="live") -> ProjectionResult` where `ProjectionResult` is a dataclass/NamedTuple with fields `markdown: str` and `overflow: dict` (overflow maps `"by_origin_session"`/`"by_date_hint"` → `{value: count}` for omitted nodes).

- [ ] **Step 1: Read the failing tests**

Read `::test_unit_project_sort_tiebreak` (lines ~234-288 — builds an in-memory SQLite `nodes` table with the Task-1 schema, calls `project.project_slice(conn, budget=1000, status="live")`, asserts `file_a.md` sorts before `file_b.md`) and `::test_cli_budget_overflow_handling` (line ~590 — calls `project.project_slice_with_overflow(conn, budget=budget)` and expects a result whose markdown is under budget with declared omissions).

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_qhaway.py::test_unit_project_sort_tiebreak tests/test_qhaway.py::test_cli_budget_overflow_handling -v`
Expected: FAIL (`project_slice` uses `DESCRIBE` which SQLite rejects; `project_slice_with_overflow` undefined).

- [ ] **Step 3: Replace the introspection and add the sibling**

In `project.py`, replace the `_columns` function (which uses `db_conn.execute("DESCRIBE nodes")`) with a SQLite-compatible read via `model.fetch_nodes`. Change the row-loading line:

```python
from qhaway.model import fetch_nodes
# ...
# OLD: columns = _columns(db_conn); rows = [_normalize_row(row, columns) for row in db_conn.execute("SELECT * FROM nodes").fetchall()]
# NEW:
rows = [_normalize_row(node) for node in fetch_nodes(db_conn)]
```

Change `_normalize_row` to take a dict (fetch_nodes already returns dicts):

```python
def _normalize_row(values: dict) -> dict:
    return {
        "file": values.get("file"),
        "name": values.get("name"),
        "content_type": values.get("content_type") or "project",
        "description": values.get("description"),
        "role": values.get("role"),
        "status": values.get("status") or "live",
        "origin_session": values.get("origin_session"),
        "date_hint": values.get("date_hint"),
        "body": values.get("body") or "",
        "mtime_ns": values.get("mtime_ns") or 0,
    }
```

Delete the now-unused `_columns` function. Then add the overflow sibling at the end of the module:

```python
from dataclasses import dataclass, field

@dataclass
class ProjectionResult:
    markdown: str
    overflow: dict = field(default_factory=dict)


def project_slice_with_overflow(
    db_conn, budget, content_type=None, role=None, status="live"
) -> ProjectionResult:
    """Render the slice AND return structured overflow band-counts (F-7/C-1)."""
    markdown = project_slice(db_conn, budget, content_type, role, status)
    rows = [_normalize_row(node) for node in fetch_nodes(db_conn)]
    filtered = [
        r for r in rows
        if r["status"] == status
        and (content_type is None or r["content_type"] == content_type)
        and (role is None or r["role"] == role)
    ]
    omitted = [r for r in filtered if f"]({r['file']})" not in markdown]
    overflow = {
        "by_origin_session": _band(omitted, "origin_session"),
        "by_date_hint": _band(omitted, "date_hint"),
    }
    return ProjectionResult(markdown=markdown, overflow=overflow)


def _band(rows: list[dict], key: str) -> dict:
    counts: dict = {}
    for row in rows:
        value = row.get(key) or "(none)"
        counts[value] = counts.get(value, 0) + 1
    return counts
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_qhaway.py::test_unit_project_sort_tiebreak tests/test_qhaway.py::test_cli_budget_overflow_handling -v`
Expected: PASS. (`test_cli_budget_overflow_handling` also calls `cli.reconcile` — if it errors on that, it is expected to fail until Task 4; run just `test_unit_project_sort_tiebreak` here and revisit the overflow test after Task 4.)

- [ ] **Step 5: Commit**

```bash
git add src/qhaway/project.py
git commit -m "feat(project): SQLite introspection + project_slice_with_overflow sibling"
```

---

### Task 3: reconcile.py — atomic read-only writer + frontmatter/slug/links composer

**Files:**
- Create: `src/qhaway/reconcile.py`
- Test: `tests/test_qhaway.py::test_unit_remember_slug_and_role`, `::test_unit_remember_hostile_frontmatter`, `::test_unit_remember_links_normalization` (these exercise the composer via `server.remember` in Task 5, but the composer + writer are unit-testable now via a small direct test below)

**Interfaces:**
- Consumes: nothing from other new tasks (pure helpers + stdlib).
- Produces:
  - `slugify(title: str) -> str` — lowercase, spaces→hyphens, strip non-`[a-z0-9-]`, collapse repeat hyphens, strip leading/trailing hyphens.
  - `compose_frontmatter(type: str, title: str, description: str | None) -> str` — via `yaml.safe_dump` of `{name, type, description?}` between `---` fences.
  - `normalize_link(raw: str) -> str` — strip `[[ ]]`, strip `.md`, reject path separators (raise `ValueError`), slugify the remainder.
  - `compose_topic_file(type, title, body, description, links) -> str` — full file text: frontmatter + body + (if links) `\n\n` + one `[[slug]]` per line + trailing `\n`.
  - `write_readonly(path: Path, text: str) -> None` — write to a temp file born `0o444`, then `os.replace` over `path` (atomic, born read-only). Explicit utf-8.
  - `REDIRECT_TEMPLATE: str` — the small MEMORY.md redirect text (mentions `recall`/`remember`).

- [ ] **Step 1: Write a focused failing test for the composer/writer**

Add to `tests/test_qhaway.py`:

```python
def test_unit_reconcile_composer_and_readonly_write(temp_memory_dir):
    """reconcile composer slugifies/normalizes, writer makes file born read-only."""
    check_modules_loaded()
    import qhaway.reconcile as reconcile

    assert reconcile.slugify("Review feedback") == "review-feedback"
    assert reconcile.normalize_link("[[Foo Bar]]") == "foo-bar"
    assert reconcile.normalize_link("foo-bar.md") == "foo-bar"

    text = reconcile.compose_topic_file(
        type="project", title="A B", body="last sentence",
        description=None, links=["x"],
    )
    assert "\n\n[[x]]\n" in text

    target = temp_memory_dir / "MEMORY.md"
    reconcile.write_readonly(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"
    import stat as stat_mod
    mode = target.stat().st_mode
    assert not (mode & stat_mod.S_IWUSR)  # owner write bit cleared
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_qhaway.py::test_unit_reconcile_composer_and_readonly_write -v`
Expected: FAIL (`No module named 'qhaway.reconcile'`).

- [ ] **Step 3: Create `reconcile.py` with the helpers**

```python
"""The one shared reconcile operation + atomic read-only writer + remember composer."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import yaml

REDIRECT_TEMPLATE = (
    "# Memory\n\n"
    "Your memory lives in a database, not this file. Use the MCP tools:\n\n"
    "- `recall(type?, role?, status?)` — read your memory (omit args for the working set)\n"
    "- `remember(type, title, body, ...)` — write a memory\n\n"
    "Do not hand-edit this file; it is managed by qhaway and is read-only.\n"
)

_SLUG_STRIP = re.compile(r"[^a-z0-9-]+")
_SLUG_COLLAPSE = re.compile(r"-{2,}")


def slugify(title: str) -> str:
    lowered = title.strip().lower().replace(" ", "-")
    cleaned = _SLUG_STRIP.sub("", lowered)
    cleaned = _SLUG_COLLAPSE.sub("-", cleaned).strip("-")
    return cleaned or "memory"


def normalize_link(raw: str) -> str:
    text = raw.strip()
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2]
    if text.endswith(".md"):
        text = text[:-3]
    if "/" in text or "\\" in text:
        raise ValueError(f"link must not contain a path separator: {raw!r}")
    return slugify(text)


def compose_frontmatter(type: str, title: str, description: str | None) -> str:
    data = {"name": title, "type": type}
    if description is not None:
        data["description"] = description
    dumped = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{dumped}---\n"


def compose_topic_file(type, title, body, description, links) -> str:
    text = compose_frontmatter(type, title, description) + body
    if links:
        normalized = [normalize_link(link) for link in links]
        text = text.rstrip() + "\n\n" + "\n".join(f"[[{slug}]]" for slug in normalized) + "\n"
    return text


def write_readonly(path: Path, text: str) -> None:
    """Write text to a temp file created read-only, then atomically replace path."""
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=".qhaway-tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp_name, 0o444)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
```

(Note: the spec's "born read-only via fchmod" — the SPIKE in Task 0 below confirms whether `os.replace` of a 0444 temp over an existing 0444 file works on this box. `tempfile.mkstemp` already creates the file 0600; we `chmod 0444` before replace. If the spike shows replace-over-0444 fails, the writer must `os.chmod(path, 0o644)` before `os.replace`; see Task 0.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_qhaway.py::test_unit_reconcile_composer_and_readonly_write -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/qhaway/reconcile.py tests/test_qhaway.py
git commit -m "feat(reconcile): slug/frontmatter/links composer + atomic read-only writer"
```

---

### Task 0 (SPIKE) — confirm born-read-only atomic replace

> **Execution order:** despite the "0", run this spike *after* Task 3 (it edits `reconcile.write_readonly`) and *before* Task 4 (which relies on the fence). It is numbered 0 because it validates the single empirical assumption seven review rounds could not settle on paper.

**Files:**
- Create (throwaway): `tmp/spike_readonly.py`
- Test: manual run; encode the finding as a comment in `reconcile.write_readonly`.

**Interfaces:** none (empirical confirmation only).

- [ ] **Step 1: Write the spike**

```python
# tmp/spike_readonly.py
import os, stat, tempfile
d = tempfile.mkdtemp()
target = os.path.join(d, "MEMORY.md")

def born_ro_write(path, text):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        h.write(text)
    os.chmod(tmp, 0o444)
    os.replace(tmp, path)

born_ro_write(target, "first")          # (a) create a 0444 file
print("created mode:", oct(os.stat(target).st_mode & 0o777))
try:
    open(target, "w").write("x")         # (b) direct write must FAIL
    print("DIRECT WRITE SUCCEEDED — fence is weaker than expected")
except PermissionError:
    print("direct write blocked: OK")
born_ro_write(target, "second")          # (c) atomic replace over 0444 must SUCCEED
print("replace-over-0444:", open(target, encoding="utf-8").read())
print("final mode:", oct(os.stat(target).st_mode & 0o777))
```

- [ ] **Step 2: Run it and record the result**

Run: `uv run python tmp/spike_readonly.py`
Expected (Linux): `direct write blocked: OK`, `replace-over-0444: second`, final mode `0o444`.
If `replace-over-0444` raises `PermissionError`: edit `reconcile.write_readonly` to `os.chmod(path, 0o644)` before `os.replace` when `path` already exists (documented fallback, C-6).

- [ ] **Step 3: Record the finding as a comment in `reconcile.write_readonly`**

Add one line above the `os.replace` call stating the spike result, e.g. `# SPIKE 2026-06-21: replace-over-0444 confirmed OK on Linux/WSL.`

- [ ] **Step 4: Commit**

```bash
git add src/qhaway/reconcile.py
git commit -m "spike: confirm born-read-only atomic replace on Linux"
```

---

### Task 4: reconcile() — incremental sweep, transaction, redirect self-heal, (D) preservation

**Files:**
- Modify: `src/qhaway/reconcile.py` (add `reconcile`)
- Modify: `src/qhaway/cli.py` (expose `reconcile` as `cli.reconcile` re-export so tests calling `cli.reconcile(...)` work)
- Test: `::test_unit_reconcile_incremental_skip`, `::test_unit_reconcile_changed_file`, `::test_unit_reconcile_idempotence`, `::test_unit_reconcile_no_orphaned_edges`, `::test_cli_reconcile_atomic_failure`, `::test_cli_non_destructive_edit_handling`, `::test_cli_matching_redirect_but_missing_sidecar`, `::test_cli_redirect_cannot_truncate`

**Interfaces:**
- Consumes: `model.get_connection`, `model.fetch_nodes`, `model._upsert_file` (rename to public `model.upsert_file`), `model.topic_files`; `reconcile.write_readonly`, `reconcile.REDIRECT_TEMPLATE`.
- Produces: `reconcile(memory_dir: str) -> None` — the one shared sync op. Also `cli.reconcile = reconcile.reconcile` (re-export).
- Sidecar: `.qhaway.json` with `{"version": 1, "last_output_hash": <sha256 of MEMORY.md redirect>}`.

- [ ] **Step 1: Read the failing tests**

Key contracts: incremental skip parses **zero** files on a no-change second run (`::test_unit_reconcile_incremental_skip`, patches `qhaway.parse.parse_memory_file` and asserts `call_count == 0`); a changed file is re-parsed and a deleted file's node is dropped (`::test_unit_reconcile_changed_file`); two no-change runs create **zero** `MEMORY-*.md` (`::test_unit_reconcile_idempotence`); deleting a linked node leaves zero edges (`::test_unit_reconcile_no_orphaned_edges`); a mid-reconcile parse failure rolls back fully (`::test_cli_reconcile_atomic_failure`); a hand-edited MEMORY.md is preserved to `MEMORY-<ts>.md` before rewrite (`::test_cli_non_destructive_edit_handling`); a valid redirect + missing sidecar creates **zero** backups (`::test_cli_matching_redirect_but_missing_sidecar`); the redirect is well under budget (`::test_cli_redirect_cannot_truncate`).

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_qhaway.py -k "reconcile or non_destructive or matching_redirect or redirect_cannot" -v`
Expected: FAIL (`cli.reconcile` / `reconcile.reconcile` not defined).

- [ ] **Step 3: Implement `reconcile`**

In `model.py`, rename `_upsert_file` to `upsert_file` (public) and update its internal caller. Add a deletion helper:

```python
def delete_node(conn, file_name: str) -> None:
    conn.execute("DELETE FROM edges WHERE src_file = ?", [file_name])
    conn.execute("DELETE FROM nodes WHERE file = ?", [file_name])
```

In `reconcile.py` add:

```python
import hashlib
import json
from datetime import datetime, timezone

from qhaway import model

SIDECAR_NAME = ".qhaway.json"
MEMORY_NAME = "MEMORY.md"


def reconcile(memory_dir: str) -> None:
    root = Path(memory_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"memory directory is not readable: {memory_dir}")

    conn = model.get_connection(memory_dir)
    try:
        conn.execute("BEGIN IMMEDIATE")
        _reconcile_nodes(conn, root)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

    _heal_redirect(root)


def _reconcile_nodes(conn, root: Path) -> None:
    db_state = {
        row["file"]: (row["mtime_ns"], row["size"])
        for row in conn.execute("SELECT file, mtime_ns, size FROM nodes")
    }
    on_disk = {}
    for path in model.topic_files(root):
        stat = path.stat()
        on_disk[path.name] = path
        prior = db_state.get(path.name)
        if prior is None or prior != (stat.st_mtime_ns, stat.st_size):
            model.upsert_file(conn, path)
    for gone in set(db_state) - set(on_disk):
        model.delete_node(conn, gone)


def _heal_redirect(root: Path) -> None:
    memory_file = root / MEMORY_NAME
    sidecar_file = root / SIDECAR_NAME
    desired = REDIRECT_TEMPLATE
    desired_hash = _sha256(desired)

    if memory_file.exists():
        current = memory_file.read_text(encoding="utf-8")
        if current == desired:
            _write_sidecar(sidecar_file, desired_hash)  # repair/idempotent (C-9)
            return
        recorded = _recorded_hash(sidecar_file)
        if _sha256(current) != recorded:
            memory_file.rename(_backup_path(memory_file))  # (D) preserve hand edit

    write_readonly(memory_file, desired)
    _write_sidecar(sidecar_file, desired_hash)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _recorded_hash(sidecar_file: Path) -> str | None:
    if not sidecar_file.exists():
        return None
    try:
        data = json.loads(sidecar_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if data.get("version") != 1:
        return None
    value = data.get("last_output_hash")
    return value if isinstance(value, str) else None


def _write_sidecar(sidecar_file: Path, output_hash: str) -> None:
    sidecar_file.write_text(
        json.dumps({"version": 1, "last_output_hash": output_hash}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _backup_path(memory_file: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    base = memory_file.with_name(f"MEMORY-{timestamp}.md")
    if not base.exists():
        return base
    for index in range(1, 100):
        candidate = memory_file.with_name(f"MEMORY-{timestamp}-{index:02d}.md")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"could not allocate backup name for {memory_file}")
```

In `cli.py` add near the top (after imports): `from qhaway.reconcile import reconcile`. This makes `cli.reconcile` resolve to the same function the tests patch and call.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_qhaway.py -k "reconcile or non_destructive or matching_redirect or redirect_cannot" -v`
Expected: PASS. (`test_unit_reconcile_incremental_skip` patches `qhaway.parse.parse_memory_file`; the skip works because unchanged files never reach `upsert_file`.)

- [ ] **Step 5: Commit**

```bash
git add src/qhaway/reconcile.py src/qhaway/model.py src/qhaway/cli.py
git commit -m "feat(reconcile): shared incremental sync, redirect self-heal, (D) preservation"
```

---

### Task 5: server.py — remember, recall, initialize_server

**Files:**
- Create: `src/qhaway/server.py`
- Test: `::test_unit_remember_slug_and_role`, `::test_unit_remember_hostile_frontmatter`, `::test_unit_remember_links_normalization`, `::test_cli_serve_reconciles_once`, `::test_cli_concurrent_remember_no_lost_body`, `::test_cli_mcp_failures_structured`

**Interfaces:**
- Consumes: `reconcile.compose_topic_file`, `reconcile.slugify`, `reconcile.reconcile`; `model.get_connection`, `model.fetch_nodes`; `project.project_slice_with_overflow`.
- Produces:
  - `VALID_TYPES = {"user", "feedback", "project", "reference"}`
  - `remember(type, title, body, description, links, memory_dir) -> str` — returns the written filename. Raises `ValueError` on invalid `type`. Uses `O_CREAT|O_EXCL` exclusive create with a hard-capped suffix loop. Calls `reconcile.reconcile(memory_dir)` after writing.
  - `recall(type, role, status, memory_dir) -> str` — pure read; returns the rendered markdown via `project_slice_with_overflow(...).markdown`. Raises on unreadable dir.
  - `initialize_server(memory_dir) -> None` — runs exactly one `cli.reconcile(memory_dir)` (the test patches `qhaway.cli.reconcile`), then is ready for tool calls.

- [ ] **Step 1: Read the failing tests**

`remember` signature is keyword-style: `server.remember(type=, title=, body=, description=, links=, memory_dir=)` returning a filename string containing the slug (`::test_unit_remember_slug_and_role`); hostile title/description round-trip through `parse` intact (`::test_unit_remember_hostile_frontmatter`); links normalize to a single `[[foo-bar]]` with `\n\n` padding (`::test_unit_remember_links_normalization`); two concurrent same-title calls yield two distinct files, both bodies present (`::test_cli_concurrent_remember_no_lost_body`); `initialize_server` triggers exactly one reconcile and a following `recall` triggers none (`::test_cli_serve_reconciles_once`); invalid type and unreadable dir raise (`::test_cli_mcp_failures_structured`).

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_qhaway.py -k "remember or serve_reconciles or concurrent_remember or mcp_failures" -v`
Expected: FAIL (`No module named 'qhaway.server'`).

- [ ] **Step 3: Create `server.py`**

```python
"""MCP spine: the remember/recall verbs over the existing pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from qhaway import cli, model, project, reconcile

VALID_TYPES = {"user", "feedback", "project", "reference"}
_MAX_SUFFIX = 100


def remember(type, title, body, description=None, links=None, memory_dir=".") -> str:
    if type not in VALID_TYPES:
        raise ValueError(f"invalid type {type!r}; must be one of {sorted(VALID_TYPES)}")
    root = Path(memory_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"memory directory is not readable: {memory_dir}")

    text = reconcile.compose_topic_file(type, title, body, description, links)
    stem = reconcile.slugify(title)
    filename = _exclusive_write(root, stem, text)
    reconcile.reconcile(str(root))
    return filename


def _exclusive_write(root: Path, stem: str, text: str) -> str:
    for suffix in range(0, _MAX_SUFFIX):
        name = f"{stem}.md" if suffix == 0 else f"{stem}-{suffix}.md"
        path = root / name
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        return name
    raise RuntimeError(f"could not allocate a unique topic filename for {stem!r} after {_MAX_SUFFIX} attempts")


def recall(type=None, role=None, status="live", memory_dir=".") -> str:
    root = Path(memory_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"memory directory is not readable: {memory_dir}")
    conn = model.get_connection(str(root))
    try:
        from qhaway.project import DEFAULT_BUDGET
        result = project.project_slice_with_overflow(
            conn, budget=DEFAULT_BUDGET, content_type=type, role=role, status=status
        )
    finally:
        conn.close()
    return result.markdown


def initialize_server(memory_dir: str) -> None:
    """Run exactly one reconcile at startup, before accepting tool calls (C-3)."""
    cli.reconcile(memory_dir)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_qhaway.py -k "remember or serve_reconciles or concurrent_remember or mcp_failures" -v`
Expected: PASS. (`initialize_server` calls `cli.reconcile`, which the test patches — call count 1; `recall` does not reconcile — count stays 1.)

- [ ] **Step 5: Commit**

```bash
git add src/qhaway/server.py
git commit -m "feat(server): remember/recall/initialize_server MCP spine verbs"
```

---

### Task 6: rebuild_database + execute_query_with_retry (drift recovery, reset lock)

**Files:**
- Modify: `src/qhaway/model.py` (implement the two stubs)
- Test: `::test_unit_reconcile_schema_auto_rebuild`, `::test_unit_reconcile_database_persistence`, `::test_unit_reconcile_sqlite_fallback`, `::test_unit_rebuild_on_drift_bounded`, `::test_unit_rebuild_only_on_true_drift`, `::test_cli_destructive_rebuild_serialized`

**Interfaces:**
- Consumes: `model.get_connection`, `model._full_load`, `_DB_SUFFIXES`, `LOCK_NAME`.
- Produces:
  - `rebuild_database(memory_dir: str) -> None` — acquire `.qhaway.db.reset.lock` via `fcntl.flock(LOCK_EX|LOCK_NB)` in a bounded retry loop (~5 s, raise with `"lock"` in the message on timeout); delete all three db files; rebuild from topic files; release lock (do not delete the lock file).
  - `execute_query_with_retry(conn, query, memory_dir, params=None)` — run the query; on `OperationalError`, rebuild **only if** the error is a true-drift signal (`"no such column"` / `"no such table"` referencing an *expected* schema element) AND not already rebuilt this call; otherwise re-raise. At most one rebuild.

- [ ] **Step 1: Read the failing tests**

`::test_unit_reconcile_schema_auto_rebuild` (old-schema db → `get_connection` rebuilds, new columns present, `user_version > 0`); `::test_unit_reconcile_sqlite_fallback` (WAL PRAGMA patched to raise → `get_connection` raises with `"WAL"`); `::test_unit_rebuild_on_drift_bounded` (a query that triggers drift rebuilds **exactly once** then propagates — `mock_rebuild.call_count == 1`); `::test_unit_rebuild_only_on_true_drift` (a *syntax* error rebuilds **zero** times and the db file survives); `::test_cli_destructive_rebuild_serialized` (lock held by another fd → `rebuild_database` raises with `"lock"`).

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_qhaway.py -k "auto_rebuild or sqlite_fallback or database_persistence or rebuild_on_drift or rebuild_only_on or destructive_rebuild" -v`
Expected: FAIL (`rebuild_database`/`execute_query_with_retry` raise `NotImplementedError`).

- [ ] **Step 3: Implement the two functions**

```python
import fcntl
import time

_DRIFT_MARKERS = ("no such column", "no such table")


def rebuild_database(memory_dir: str) -> None:
    root = Path(memory_dir)
    lock_path = root / LOCK_NAME
    lock_fd = open(lock_path, "a+", encoding="utf-8")
    deadline = time.monotonic() + 5.0
    try:
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"could not acquire reset lock {LOCK_NAME} (another rebuild in progress)"
                    )
                time.sleep(0.1)
        for suffix in _DB_SUFFIXES:
            target = root / f"{DB_NAME}{suffix}"
            if target.exists():
                target.unlink()
        conn = _open_wal(db_path(root))
        try:
            _full_load(conn, root)
        finally:
            conn.close()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        # Do not delete the lock file (avoids deletion races, U2-2).


def execute_query_with_retry(conn, query, memory_dir, params=None):
    try:
        return conn.execute(query, params or [])
    except sqlite3.OperationalError as exc:
        message = str(exc).lower()
        is_drift = any(marker in message for marker in _DRIFT_MARKERS)
        if not is_drift or getattr(conn, "_qhaway_rebuilt", False):
            raise
        rebuild_database(memory_dir)
        new_conn = get_connection(memory_dir)
        new_conn._qhaway_rebuilt = True
        try:
            return new_conn.execute(query, params or [])
        except sqlite3.OperationalError:
            new_conn.close()
            raise
```

Note for `::test_unit_rebuild_on_drift_bounded`: the test runs a drift query (`SELECT nonexistent_column`), so `is_drift` is true → one rebuild → the rebuilt db *still* lacks the column → second `execute` raises → propagates. `mock_rebuild.call_count == 1`. For `::test_unit_rebuild_only_on_true_drift` the malformed `... WHERE` (no condition) is a syntax error, not in `_DRIFT_MARKERS` → zero rebuilds, db survives.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_qhaway.py -k "auto_rebuild or sqlite_fallback or database_persistence or rebuild_on_drift or rebuild_only_on or destructive_rebuild" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/qhaway/model.py
git commit -m "feat(model): drift-only rebuild (bounded), WAL fail-loud, reset lock"
```

---

### Task 7: CLI surface — reconcile/check/serve subcommands, index alias, dir discovery, stdout discipline

**Files:**
- Modify: `src/qhaway/cli.py` (subparsers, dir-discovery chain, serve stderr discipline)
- Test: `::test_cli_wikilink_rot_checking`, `::test_cli_orphan_visibility`, `::test_cli_zero_topic_files_guard`, `::test_cli_dry_run_action`, `::test_cli_read_only_fence`, `::test_cli_server_stderr_safety`, plus the remaining retargeted MVP cure tests (tombstone, role-filter, machine-contract, idempotence, prioritized-set, self-destruct, budget-pinned)

**Interfaces:**
- Consumes: `reconcile.reconcile`, `model.get_connection`, `project.project_slice` / `project_slice_with_overflow`, `server.initialize_server`.
- Produces CLI commands: `qhaway reconcile --dir`, `qhaway check --dir`, `qhaway serve --dir`, `qhaway index` (alias→reconcile; `--dry-run`/`--budget`/facet flags retained for the projection-preview path), `qhaway index --check` (deprecated alias→check). Memory-dir resolution chain: `--dir` → `QHAWAY_MEMORY_DIR` → cwd for CLI; `serve` fails loud (exit non-zero, stderr only) if the dir is unreadable.

- [ ] **Step 1: Read the failing tests**

`qhaway check` reports body wikilink rot (`::test_cli_wikilink_rot_checking`) and orphan `MEMORY-*.md` (`::test_cli_orphan_visibility`); empty-dir `reconcile` succeeds and writes the redirect, `check` warns "low topic" on stderr with exit 0 (`::test_cli_zero_topic_files_guard`); `index --dry-run` prints a projection (`::test_cli_dry_run_action`); after `reconcile`, MEMORY.md is mode 0444 and a direct write raises (`::test_cli_read_only_fence`); `serve` on a bad dir exits non-zero with empty stdout and `"memory directory is not readable"` on stderr (`::test_cli_server_stderr_safety`).

- [ ] **Step 2: Run the whole suite to see what remains**

Run: `uv run pytest tests/test_qhaway.py -v`
Expected: the CLI-subcommand tests above FAIL (subcommands not wired); most unit tests from Tasks 1-6 PASS.

- [ ] **Step 3: Rewrite `cli.py`'s argument surface**

Implement `main(args=None)` with subparsers `reconcile`, `check`, `serve`, and `index` (alias). Resolve the dir via `_resolve_dir(namespace)`: explicit `--dir`, else `os.environ.get("QHAWAY_MEMORY_DIR")`, else `"."`. For `serve`, if the resolved dir is not a readable directory, write `f"memory directory is not readable: {dir}\n"` to `sys.stderr` and return non-zero **without writing to stdout**. Wire:

```python
import os
import sys

from qhaway.reconcile import reconcile
from qhaway import model, project, server


def main(args=None) -> int:
    parser = argparse.ArgumentParser(prog="qhaway")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("reconcile", "check", "serve", "index"):
        p = sub.add_parser(name)
        p.add_argument("--dir")
        p.add_argument("--budget", type=int, default=project.DEFAULT_BUDGET)
        p.add_argument("--type", dest="content_type")
        p.add_argument("--role")
        p.add_argument("--status", default="live")
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--check", action="store_true")  # deprecated alias on index
    ns = parser.parse_args(args)
    directory = _resolve_dir(ns)

    if ns.command == "serve":
        return _serve(directory)
    if ns.command == "check" or (ns.command == "index" and ns.check):
        return _check(directory, ns.budget)
    if ns.command == "index" and ns.dry_run:
        return _dry_run(directory, ns)
    # reconcile, and index-as-reconcile-alias
    try:
        reconcile(directory)
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    return 0


def _resolve_dir(ns) -> str:
    return ns.dir or os.environ.get("QHAWAY_MEMORY_DIR") or "."


def _serve(directory: str) -> int:
    if not os.path.isdir(directory):
        sys.stderr.write(f"memory directory is not readable: {directory}\n")
        return 1
    server.initialize_server(directory)
    # The blocking MCP event loop is started here in production; tests only
    # assert the pre-serve failure path and initialize_server behavior.
    return 0
```

Port the existing `_check` (dangling links + orphan list + would-overflow) and `_dry_run` (print `project_slice`) onto `model.get_connection`/`project_slice`, keeping their current output strings (`"qhaway check"` wording, `"low topic"` warning, `+N ... not shown` footer). Preserve the `--check` low-topic warning to stderr with exit 0.

- [ ] **Step 4: Run the full suite to verify all pass**

Run: `uv run pytest tests/test_qhaway.py -v`
Expected: PASS (all tests green — the spine is complete and the retargeted MVP cure tests pass on the new surfaces).

- [ ] **Step 5: Commit**

```bash
git add src/qhaway/cli.py
git commit -m "feat(cli): reconcile/check/serve subcommands, index alias, dir discovery, serve stderr discipline"
```

---

### Task 8: Package metadata, gitignore, MCP server entry, docs

**Files:**
- Modify: `pyproject.toml` (keywords/description mention SQLite; add `qhaway` MCP entry if the SDK requires it)
- Modify: `.gitignore` (add db + lock artifacts)
- Modify: `README.md` (remember/recall verbs, the redirect, `qhaway serve`)
- Test: full suite remains green; manual `qhaway --help`.

**Interfaces:** none new.

- [ ] **Step 1: Update `.gitignore`**

Add lines: `.qhaway.db`, `.qhaway.db-wal`, `.qhaway.db-shm`, `.qhaway.db.reset.lock` (these live inside memory dirs, but guard against accidental in-repo memory dirs).

- [ ] **Step 2: Update `pyproject.toml` metadata**

Change `keywords` to drop `"duckdb"` and add `"sqlite"`, `"mcp"`. Confirm `dependencies` no longer lists `duckdb`. (Add the MCP server SDK dependency here when the serve event loop is implemented — out of scope for the test suite, which stubs serve.)

- [ ] **Step 3: Update `README.md`**

Document: memory is reached via `recall`/`remember` MCP tools; MEMORY.md is a managed read-only redirect; `qhaway serve --dir <memory_dir>` runs the server (reconciling once at startup); `qhaway reconcile` syncs and `qhaway check` inspects. Keep it short; match existing README voice.

- [ ] **Step 4: Verify the suite and help**

Run: `uv run pytest tests/test_qhaway.py -v` (expect all PASS) and `uv run qhaway --help` (expect subcommands listed).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore README.md
git commit -m "chore: package metadata, gitignore db artifacts, README for the MCP spine"
```

---

## Self-Review

**Spec coverage** — each spec section maps to a task: SQLite backend + WAL-required + co-located db (Task 1, 6); `mtime_ns`/`size`/edges-PK+index (Task 1); projection port + overflow sibling C-1/F-7 (Task 2); slug F-2 / safe-YAML F-4 / links C-11/G-6 / born-RO writer + spike C-6 (Task 3, 0); incremental reconcile + transaction C-5 + (D) preservation + redirect self-heal C-9 (Task 4); remember/recall/serve C-3/C-4/C-10 + suffix cap G-7 (Task 5); drift-only rebuild FFUP-2 + bounded U-1 + reset lock TFUP-1/U2-2 + WAL fail-loud G-2 (Task 6); check/serve/index-alias OQ-3/SFUP-1 + dir discovery OQ-2 + stdout discipline G-5/TFUP-2 (Task 7); gitignore U2-1 + metadata (Task 8). FFUP-1 residual race is a named deferral (no task — correct). U-3 Windows is step-3 (no task — correct).

**Placeholder scan** — `rebuild_database`/`execute_query_with_retry` are `NotImplementedError` stubs in Task 1 *by design* (the test that exercises them is in Task 6, which implements them); this is dependency-ordered, not a placeholder. No "TBD"/"add error handling"/"similar to" remain.

**Type consistency** — `get_connection(memory_dir)`, `fetch_nodes(conn) -> list[dict]`, `upsert_file(conn, path)`, `delete_node(conn, file)`, `reconcile(memory_dir)`, `project_slice(conn, budget, ...) -> str`, `project_slice_with_overflow(...) -> ProjectionResult`, `remember(type,title,body,description,links,memory_dir) -> str`, `recall(type,role,status,memory_dir) -> str`, `initialize_server(memory_dir)`, `rebuild_database(memory_dir)`, `execute_query_with_retry(conn,query,memory_dir,params=None)` — names and arities match the test file's calls and the cross-task Interfaces blocks.
