# qhaway init Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `uvx qhaway init` / `uvx qhaway uninstall` — one-command, idempotent setup that wires qhaway into user-scope Claude Code config, plus self-gating `session-start` / `session-end` subcommands that activate only in projects that have memory.

**Architecture:** A new `setup.py` module owns the user-scope settings surgery (derive paths, write/remove a tagged hook block, idempotent + non-destructive). A new `paths.py` module owns deriving Claude Code's per-project memory dir from `CLAUDE_PROJECT_DIR` (verified slug rule: replace `/` with `-`). The CLI gains four subcommands that delegate to these modules. `session-start`/`session-end` derive the dir, gate on *topic files present*, and no-op cleanly when a project has no memory — so one user-scope install serves all projects and no hardcoded path can go stale.

**Tech Stack:** Python ≥3.14, stdlib only (json, os, pathlib), pytest. No new dependencies.

## Global Constraints

- `requires-python = ">=3.14"`; stdlib SQLite + pyyaml + mcp only — add no dependencies.
- Run tests with `.venv/bin/python -m pytest` (NOT `uv run` — 3.14 interpreter trap).
- Code and tests land in SEPARATE commits (authorship-separation; a pre-commit hook enforces it). Each task below splits its test commit from its code commit.
- All file writes that touch user data use atomic temp-file + replace; never write a partial/corrupt file.
- Settings surgery is NON-DESTRUCTIVE: preserve every key/hook/server qhaway did not write.
- Memory-dir derivation rule (verified against hamutay, governance, probe-proj):
  `~/.claude/projects/<CLAUDE_PROJECT_DIR with every "/" → "-">/memory`.
- The dormancy gate keys on **topic files present**, NOT on `MEMORY.md` present.
  A lone hand-written `MEMORY.md` with no topic files is NOT "has memory".

---

### Task 1: Derive the per-project memory dir from CLAUDE_PROJECT_DIR

**Files:**
- Create: `src/qhaway/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Produces: `memory_dir_for(project_dir: str, home: Path | None = None) -> Path`
  — returns the derived memory dir Path. `home` defaults to `Path.home()`
  (injectable for tests). Pure function, no filesystem access.
- Produces: `derive_from_env(environ: dict, home: Path | None = None) -> Path | None`
  — reads `CLAUDE_PROJECT_DIR` from `environ`; returns the memory dir, or
  `None` if the var is unset/empty.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_paths.py
from pathlib import Path
from qhaway import paths

HOME = Path("/home/tony")

def test_derives_known_hamutay_mapping():
    got = paths.memory_dir_for("/home/tony/projects/hamutay", home=HOME)
    assert got == HOME / ".claude/projects/-home-tony-projects-hamutay/memory"

def test_derives_known_governance_mapping():
    got = paths.memory_dir_for("/home/tony/projects/governance", home=HOME)
    assert got == HOME / ".claude/projects/-home-tony-projects-governance/memory"

def test_derives_probe_mapping():
    got = paths.memory_dir_for("/home/tony/probe-proj", home=HOME)
    assert got == HOME / ".claude/projects/-home-tony-probe-proj/memory"

def test_derive_from_env_returns_none_when_unset():
    assert paths.derive_from_env({}, home=HOME) is None
    assert paths.derive_from_env({"CLAUDE_PROJECT_DIR": ""}, home=HOME) is None

def test_derive_from_env_uses_the_var():
    env = {"CLAUDE_PROJECT_DIR": "/home/tony/projects/hamutay"}
    got = paths.derive_from_env(env, home=HOME)
    assert got == HOME / ".claude/projects/-home-tony-projects-hamutay/memory"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qhaway.paths'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/qhaway/paths.py
"""Derive Claude Code's per-project memory dir from CLAUDE_PROJECT_DIR.

Verified slug rule (hamutay, governance, probe-proj): Claude Code names the
per-project dir by replacing every "/" in the project's absolute path with "-".
NOTE: verified only for simple alphanumeric path components. Exotic components
(dots, spaces) are an untested edge — acceptable for alpha.
"""
from __future__ import annotations

from pathlib import Path


def memory_dir_for(project_dir: str, home: Path | None = None) -> Path:
    home = home or Path.home()
    slug = project_dir.replace("/", "-")
    return home / ".claude" / "projects" / slug / "memory"


def derive_from_env(environ: dict, home: Path | None = None) -> Path | None:
    project_dir = environ.get("CLAUDE_PROJECT_DIR")
    if not project_dir:
        return None
    return memory_dir_for(project_dir, home=home)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_paths.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit (test, then code — separate commits)**

```bash
git add tests/test_paths.py
git commit -m "Test: derive per-project memory dir from CLAUDE_PROJECT_DIR"
git add src/qhaway/paths.py
git commit -m "Add paths.memory_dir_for: CLAUDE_PROJECT_DIR -> memory dir"
```

---

### Task 2: "has memory" gate — topic files present, not MEMORY.md present

**Files:**
- Modify: `src/qhaway/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Consumes: `memory_dir_for` (Task 1).
- Produces: `has_memory(memory_dir: Path) -> bool` — True iff the dir exists AND
  contains at least one topic `.md` file (excluding `MEMORY.*`). A dir that is
  absent, empty, or holds only a `MEMORY.md` returns False.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_paths.py
def test_has_memory_false_when_absent(tmp_path):
    assert paths.has_memory(tmp_path / "nope") is False

def test_has_memory_false_when_empty(tmp_path):
    (tmp_path).mkdir(exist_ok=True)
    assert paths.has_memory(tmp_path) is False

def test_has_memory_false_with_only_memory_md(tmp_path):
    (tmp_path / "MEMORY.md").write_text("hand written, no topics\n")
    assert paths.has_memory(tmp_path) is False

def test_has_memory_true_with_a_topic_file(tmp_path):
    (tmp_path / "a-topic.md").write_text("---\nname: a\n---\nbody\n")
    assert paths.has_memory(tmp_path) is True

def test_has_memory_ignores_memory_artifacts(tmp_path):
    (tmp_path / "MEMORY.md").write_text("x")
    (tmp_path / "MEMORY.preinstall.md").write_text("y")
    assert paths.has_memory(tmp_path) is False
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/test_paths.py -k has_memory -v`
Expected: FAIL — `AttributeError: module 'qhaway.paths' has no attribute 'has_memory'`

- [ ] **Step 3: Implement**

```python
# add to src/qhaway/paths.py
def has_memory(memory_dir: Path) -> bool:
    if not memory_dir.is_dir():
        return False
    for entry in memory_dir.glob("*.md"):
        if entry.is_file() and not entry.name.startswith("MEMORY"):
            return True
    return False
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_paths.py -k has_memory -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/test_paths.py
git commit -m "Test: has_memory gates on topic files, not MEMORY.md"
git add src/qhaway/paths.py
git commit -m "Add paths.has_memory: gate on topic-file presence"
```

---

### Task 3: session-start / session-end subcommands (self-gating)

**Files:**
- Modify: `src/qhaway/cli.py` (register two new subcommands + handlers)
- Test: `tests/test_cli_session.py`

**Interfaces:**
- Consumes: `paths.derive_from_env`, `paths.has_memory` (Tasks 1-2);
  `reconcile.reconcile`, `_exit` (existing in cli.py).
- Produces: CLI subcommands `session-start` and `session-end`. Both read
  `os.environ` for `CLAUDE_PROJECT_DIR`, derive the memory dir, and:
  no var → exit 0 no-op; dir lacks topic files → exit 0 no-op; else
  `session-start` runs `reconcile` + emits the projection, `session-end` runs
  the existing exit path. Returns process exit code (0 on no-op and success).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_session.py
import os
from pathlib import Path
from qhaway import cli

def _run(args, env):
    old = dict(os.environ)
    os.environ.clear(); os.environ.update(env)
    try:
        return cli.main(args)
    finally:
        os.environ.clear(); os.environ.update(old)

def test_session_start_noop_when_no_project_dir(tmp_path, capsys):
    assert _run(["session-start"], {}) == 0  # no CLAUDE_PROJECT_DIR

def test_session_start_noop_when_dir_has_no_topics(tmp_path):
    # CLAUDE_PROJECT_DIR points somewhere whose derived memory dir is empty
    proj = tmp_path / "proj"; proj.mkdir()
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path)}
    assert _run(["session-start"], env) == 0
    # derived memory dir does not exist / no MEMORY.md written
    derived = tmp_path / ".claude/projects" / str(proj).replace("/", "-") / "memory"
    assert not (derived / "MEMORY.md").exists()

def test_session_start_activates_with_topics(tmp_path):
    proj = tmp_path / "proj"; proj.mkdir()
    derived = tmp_path / ".claude/projects" / str(proj).replace("/", "-") / "memory"
    derived.mkdir(parents=True)
    (derived / "t.md").write_text("---\nname: T\ndescription: hook\nmetadata:\n  type: project\n---\nbody\n")
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path)}
    assert _run(["session-start"], env) == 0
    assert (derived / "MEMORY.md").exists()

def test_session_end_writes_signed_index_when_active(tmp_path):
    proj = tmp_path / "proj"; proj.mkdir()
    derived = tmp_path / ".claude/projects" / str(proj).replace("/", "-") / "memory"
    derived.mkdir(parents=True)
    (derived / "t.md").write_text("---\nname: T\ndescription: hook\nmetadata:\n  type: project\n---\nbody\n")
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path)}
    assert _run(["session-end"], env) == 0
    text = (derived / "MEMORY.md").read_text()
    assert "qhaway:v1:" in text  # signed index
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/test_cli_session.py -v`
Expected: FAIL — argparse rejects `session-start` (invalid choice).

- [ ] **Step 3: Implement — register subcommands and handlers**

In `src/qhaway/cli.py`, after the existing `for name in (...)` loop that adds
parsers (around line 20-29), add the two no-flag subcommands:

```python
    sub.add_parser("session-start")
    sub.add_parser("session-end")
```

Add an import near the top:

```python
from qhaway import paths
```

Add dispatch BEFORE `directory = _resolve_dir(ns)` is used for these (early in
`main`, right after `ns = parser.parse_args(args)`):

```python
    if ns.command in ("session-start", "session-end"):
        return _session(ns.command)
```

Add the handler function:

```python
def _session(which: str) -> int:
    """Self-gating SessionStart/SessionEnd entry. Derives the per-project memory
    dir from CLAUDE_PROJECT_DIR and no-ops cleanly when the project has no memory
    (no var, or dir without topic files). One user-scope install thus serves all
    projects without firing where there is nothing to do."""
    memory_dir = paths.derive_from_env(os.environ)
    if memory_dir is None or not paths.has_memory(memory_dir):
        return 0  # dormant — touch nothing
    directory = str(memory_dir)
    if which == "session-start":
        reconcile(directory)
        conn = model.get_connection(directory)
        try:
            sys.stdout.write(project.project_slice(conn, budget=project.DEFAULT_BUDGET))
        finally:
            conn.close()
        return 0
    return _exit(directory, project.DEFAULT_BUDGET)
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_cli_session.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run full suite (no regressions)**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all prior + new)

- [ ] **Step 6: Commit**

```bash
git add tests/test_cli_session.py
git commit -m "Test: session-start/end self-gate on topic-file presence"
git add src/qhaway/cli.py
git commit -m "Add session-start/session-end self-gating subcommands"
```

---

### Task 4: Settings surgery — write/remove a tagged qhaway block

**Files:**
- Create: `src/qhaway/setup.py`
- Test: `tests/test_setup.py`

**Interfaces:**
- Produces: `MARKER = "qhaway-managed"` (the tag identifying qhaway's block).
- Produces: `install(settings_path: Path) -> str` — ensures the qhaway hook
  block is present in the JSON at `settings_path` (creating the file/parents if
  absent), non-destructively. Returns `"installed"` if it wrote the block, or
  `"already"` if a qhaway block was already present (no change). Atomic write.
- Produces: `uninstall(settings_path: Path) -> str` — removes the qhaway block
  if present (preserving all other content); returns `"removed"` or `"absent"`.
- Produces: `is_installed(settings: dict) -> bool` — True iff a qhaway-managed
  SessionStart hook block is present.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_setup.py
import json
from pathlib import Path
from qhaway import setup

def _read(p): return json.loads(Path(p).read_text())

def test_install_into_absent_file(tmp_path):
    s = tmp_path / "settings.json"
    assert setup.install(s) == "installed"
    d = _read(s)
    assert setup.is_installed(d)
    # both hooks present, invoking uvx qhaway session-*
    flat = json.dumps(d)
    assert "session-start" in flat and "session-end" in flat
    assert setup.MARKER in flat

def test_install_is_idempotent(tmp_path):
    s = tmp_path / "settings.json"
    setup.install(s)
    before = s.read_text()
    assert setup.install(s) == "already"
    assert s.read_text() == before  # byte-identical, no rewrite

def test_install_preserves_unrelated_settings(tmp_path):
    s = tmp_path / "settings.json"
    s.write_text(json.dumps({"theme": "dark", "hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": "echo other"}]}]}}))
    setup.install(s)
    d = _read(s)
    assert d["theme"] == "dark"
    # the pre-existing non-qhaway hook survives alongside ours
    cmds = [h["command"] for blk in d["hooks"]["SessionStart"] for h in blk["hooks"]]
    assert "echo other" in cmds
    assert any("qhaway session-start" in c for c in cmds)

def test_uninstall_removes_only_qhaway(tmp_path):
    s = tmp_path / "settings.json"
    s.write_text(json.dumps({"theme": "dark", "hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": "echo other"}]}]}}))
    setup.install(s)
    assert setup.uninstall(s) == "removed"
    d = _read(s)
    assert d["theme"] == "dark"
    cmds = [h["command"] for blk in d["hooks"].get("SessionStart", []) for h in blk["hooks"]]
    assert "echo other" in cmds
    assert not any("qhaway" in c for c in cmds)
    assert not setup.is_installed(d)

def test_uninstall_when_absent(tmp_path):
    s = tmp_path / "settings.json"
    s.write_text(json.dumps({"theme": "dark"}))
    assert setup.uninstall(s) == "absent"
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/test_setup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qhaway.setup'`

- [ ] **Step 3: Implement**

```python
# src/qhaway/setup.py
"""Idempotent, non-destructive install/uninstall of qhaway's user-scope
SessionStart/SessionEnd hook block in ~/.claude/settings.json. The block is
tagged with MARKER so uninstall removes exactly it and nothing else."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

MARKER = "qhaway-managed"

def _block(command: str) -> dict:
    return {"//": MARKER, "hooks": [{"type": "command", "command": command}]}

_START = "uvx qhaway session-start"
_END = "uvx qhaway session-end"

def is_installed(settings: dict) -> bool:
    for blk in settings.get("hooks", {}).get("SessionStart", []):
        if isinstance(blk, dict) and blk.get("//") == MARKER:
            return True
    return False

def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2) + "\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def install(settings_path: Path) -> str:
    settings = _load(settings_path)
    if is_installed(settings):
        return "already"
    hooks = settings.setdefault("hooks", {})
    hooks.setdefault("SessionStart", []).append(_block(_START))
    hooks.setdefault("SessionEnd", []).append(_block(_END))
    _atomic_write(settings_path, settings)
    return "installed"

def uninstall(settings_path: Path) -> str:
    settings = _load(settings_path)
    if not is_installed(settings):
        return "absent"
    for event in ("SessionStart", "SessionEnd"):
        blocks = settings.get("hooks", {}).get(event, [])
        settings["hooks"][event] = [
            b for b in blocks
            if not (isinstance(b, dict) and b.get("//") == MARKER)
        ]
        if not settings["hooks"][event]:
            del settings["hooks"][event]
    if not settings.get("hooks"):
        settings.pop("hooks", None)
    _atomic_write(settings_path, settings)
    return "removed"
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_setup.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/test_setup.py
git commit -m "Test: idempotent non-destructive settings install/uninstall"
git add src/qhaway/setup.py
git commit -m "Add setup.py: tagged-block install/uninstall in user settings"
```

---

### Task 5: Wire init / uninstall CLI subcommands

**Files:**
- Modify: `src/qhaway/cli.py`
- Test: `tests/test_cli_init.py`

**Interfaces:**
- Consumes: `setup.install`, `setup.uninstall` (Task 4).
- Produces: CLI subcommands `init` and `uninstall`. Both resolve the settings
  path as `Path.home() / ".claude" / "settings.json"` (override via `HOME` env
  in tests). `init` prints "already installed, nothing to do." or an installed
  message; `uninstall` prints "not installed, nothing to do." or a removed
  message. Both return 0.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_init.py
import os, json
from pathlib import Path
from qhaway import cli

def _run(args, home):
    old = dict(os.environ)
    os.environ["HOME"] = str(home)
    try:
        return cli.main(args)
    finally:
        os.environ.clear(); os.environ.update(old)

def test_init_writes_settings(tmp_path, capsys):
    assert _run(["init"], tmp_path) == 0
    s = tmp_path / ".claude/settings.json"
    assert s.exists()
    assert "qhaway session-start" in s.read_text()
    assert "installed" in capsys.readouterr().out.lower()

def test_init_idempotent(tmp_path, capsys):
    _run(["init"], tmp_path); capsys.readouterr()
    assert _run(["init"], tmp_path) == 0
    assert "already" in capsys.readouterr().out.lower()

def test_uninstall_removes(tmp_path, capsys):
    _run(["init"], tmp_path); capsys.readouterr()
    assert _run(["uninstall"], tmp_path) == 0
    s = tmp_path / ".claude/settings.json"
    assert "qhaway" not in s.read_text()
    assert "removed" in capsys.readouterr().out.lower()

def test_uninstall_when_absent(tmp_path, capsys):
    assert _run(["uninstall"], tmp_path) == 0
    assert "not installed" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/test_cli_init.py -v`
Expected: FAIL — argparse rejects `init` (invalid choice).

- [ ] **Step 3: Implement**

In `src/qhaway/cli.py` add the subparsers (next to Task 3's additions):

```python
    sub.add_parser("init")
    sub.add_parser("uninstall")
```

Add import:

```python
from qhaway import setup as setup_mod
```

Add dispatch right after the `session-start/session-end` dispatch:

```python
    if ns.command in ("init", "uninstall"):
        return _setup_cmd(ns.command)
```

Add handler:

```python
def _setup_cmd(which: str) -> int:
    settings_path = Path.home() / ".claude" / "settings.json"
    if which == "init":
        result = setup_mod.install(settings_path)
        if result == "already":
            sys.stdout.write("qhaway: already installed, nothing to do.\n")
        else:
            sys.stdout.write(
                "qhaway: installed. It activates in any project that has memory;\n"
                "        projects without memory are untouched.\n"
                "        Remove with: uvx qhaway uninstall\n"
            )
        return 0
    result = setup_mod.uninstall(settings_path)
    if result == "absent":
        sys.stdout.write("qhaway: not installed, nothing to do.\n")
    else:
        sys.stdout.write("qhaway: uninstalled. Your MEMORY.md files are left in place.\n")
    return 0
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_cli_init.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add tests/test_cli_init.py
git commit -m "Test: init/uninstall CLI commands, idempotent + messaged"
git add src/qhaway/cli.py
git commit -m "Wire init/uninstall CLI subcommands"
```

---

### Task 6: Malformed-settings safety (fail loud, touch nothing)

**Files:**
- Modify: `src/qhaway/setup.py`
- Test: `tests/test_setup.py`

**Interfaces:**
- Modifies `install`/`uninstall` so that an unparseable settings file raises a
  clear error and leaves the file untouched (no partial/corrupt write).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_setup.py
import pytest

def test_install_on_malformed_settings_raises_and_preserves(tmp_path):
    s = tmp_path / "settings.json"
    s.write_text("{ not valid json ")
    with pytest.raises(ValueError):
        setup.install(s)
    assert s.read_text() == "{ not valid json "  # untouched
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/test_setup.py -k malformed -v`
Expected: FAIL — raises `json.JSONDecodeError` (a subclass of ValueError, but
message unclear) OR test passes accidentally; confirm the file-untouched
assertion holds. If `_load` lets the raw decode error through, wrap it.

- [ ] **Step 3: Implement — clear error in `_load`**

```python
# replace _load in src/qhaway/setup.py
def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path} is not valid JSON ({exc}); qhaway left it untouched."
        ) from exc
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_setup.py -k malformed -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_setup.py
git commit -m "Test: malformed settings.json fails loud, file untouched"
git add src/qhaway/setup.py
git commit -m "setup: clear error on malformed settings, never partial-write"
```

---

### Task 7: Dormant→active lifecycle integration test

**Files:**
- Test: `tests/test_lifecycle_integration.py`

**Interfaces:**
- Consumes: `cli.main` with `session-start` (Task 3), `paths` (Tasks 1-2).
  Pure test task — no production code; verifies the transition end-to-end.

- [ ] **Step 1: Write the failing/then-passing integration test**

```python
# tests/test_lifecycle_integration.py
import os
from pathlib import Path
from qhaway import cli

def _run(args, env):
    old = dict(os.environ)
    os.environ.clear(); os.environ.update(env)
    try:
        return cli.main(args)
    finally:
        os.environ.clear(); os.environ.update(old)

def test_dormant_then_active_via_topic_file(tmp_path):
    proj = tmp_path / "proj"; proj.mkdir()
    derived = tmp_path / ".claude/projects" / str(proj).replace("/", "-") / "memory"
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path)}
    # 1) dormant: no memory dir at all -> no-op, nothing written
    assert _run(["session-start"], env) == 0
    assert not (derived / "MEMORY.md").exists()
    # 2) memory appears (a topic file is written)
    derived.mkdir(parents=True)
    (derived / "first.md").write_text("---\nname: First\ndescription: hook\nmetadata:\n  type: project\n---\nbody\n")
    # 3) next session activates
    assert _run(["session-start"], env) == 0
    assert (derived / "MEMORY.md").exists()
    assert "First" in (derived / "MEMORY.md").read_text()

def test_lone_handwritten_memory_md_stays_dormant(tmp_path):
    proj = tmp_path / "proj"; proj.mkdir()
    derived = tmp_path / ".claude/projects" / str(proj).replace("/", "-") / "memory"
    derived.mkdir(parents=True)
    (derived / "MEMORY.md").write_text("# hand written, no topics\n")
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path)}
    before = (derived / "MEMORY.md").read_text()
    # a lone MEMORY.md is NOT "has memory" -> dormant, file untouched
    assert _run(["session-start"], env) == 0
    assert (derived / "MEMORY.md").read_text() == before
```

- [ ] **Step 2: Run**

Run: `.venv/bin/python -m pytest tests/test_lifecycle_integration.py -v`
Expected: PASS (both — exercises Tasks 1-3 together)

- [ ] **Step 3: Full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all)

- [ ] **Step 4: Commit**

```bash
git add tests/test_lifecycle_integration.py
git commit -m "Test: dormant->active lifecycle; lone MEMORY.md stays dormant"
```

---

### Task 8: README — document `uvx qhaway init`

**Files:**
- Modify: `README.md` (Install section)
- Modify: `qhaway-plugin/README.md` (note init as the recommended path)

**Interfaces:** docs only.

- [ ] **Step 1: Update the top-level README Install section**

Replace the clone + `--plugin-dir` recipe with:

```markdown
## Install

```sh
uvx qhaway init
```

That's it. qhaway wires itself into Claude Code at user scope and activates in
any project that already has memory; projects without memory are untouched. No
clone, no per-project setup. To remove it: `uvx qhaway uninstall`.

(Requires [`uv`](https://docs.astral.sh/uv/) — `uvx` fetches qhaway and a
managed Python on first use.)
```

- [ ] **Step 2: Verify the example resolves**

Run: `uvx qhaway --help` and confirm `init` and `uninstall` appear in the
subcommand list.
Expected: both present.

- [ ] **Step 3: Commit**

```bash
git add README.md qhaway-plugin/README.md
git commit -m "README: lead with uvx qhaway init"
```

---

## Notes for the implementer

- The plugin (`qhaway-plugin/`) and this `init` path are two distinct delivery
  mechanisms. This plan does NOT remove the plugin — it adds the simpler `init`
  path alongside it. Whether to retire the plugin is a later decision.
- After all tasks: bump version and publish a new release so `uvx qhaway init`
  is reachable from PyPI (the init subcommand does not exist in published
  0.1.1). Follow the tag-then-publish discipline: bump pyproject + __init__ +
  plugin.json, build, verify the wheel has `init`, publish, tag.
- `--dir` override on session-start/end is OUT of this plan (MVP). A stranger
  can PR it.
