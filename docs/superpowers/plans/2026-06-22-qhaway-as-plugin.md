# qhaway-as-a-Claude-Code-Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the existing qhaway tool as a Claude Code plugin so the harness owns install/enable/disable/uninstall, the SessionStart hook force-delivers the budgeted memory projection at every boot, and MEMORY.md is borrowed-while-enabled / returned-as-a-current-signed-index on exit.

**Architecture:** qhaway's spine (remember/recall/reconcile/serve) already exists and is merged to main. This plan adds the *plugin shell* around it: a plugin manifest + `hooks/hooks.json` (SessionStart + SessionEnd) + `.mcp.json` + `bin/qhaway`, plus three code build-items inside the existing package — (a) an in-file signature on the redirect/exit artifacts so a lost sidecar can't misclassify our output as a user original, (b) a `reconcile --emit` composite that reconciles then writes the projection to stdout for the hook, and (c) a SessionEnd `exit` command that writes the current signed static index. The MEMORY.md borrow/return state machine is mostly the existing `reconcile._heal_redirect` heal-logic re-triggered by hooks.

**Tech Stack:** Python 3.10+ (existing package, `src/qhaway/`), `mcp[cli]` (already a dependency), Claude Code plugin system (manifest + hooks.json + .mcp.json), bash (hook glue). Tests: pytest, run with `.venv/bin/python -m pytest` (NOT `uv run` — the 3.10 trap, see Global Constraints).

## Global Constraints

- **Source of truth is the spec:** `docs/qhaway-as-plugin-design.md`. This plan implements it; do not re-derive the architecture.
- **Run tests with `.venv/bin/python -m pytest`** — never `uv run pytest` (resolves a 3.10 interpreter that breaks the suite).
- **reconcile is idempotent and incremental** — upsert keyed on `(mtime_ns, size)`, delete vanished, preserve hand-edits. NEVER clean-then-rebuild. Measured cost: ~2ms warm / ~120ms cold-first-boot on a 112–137 file corpus, so the hook reconciles unconditionally every boot — no cache/incremental path (Open Issue #1, resolved).
- **Delivery point is SessionStart stdout** (raw stdout → ambient context). `InstructionsLoaded` is observability-only (no decision control, ambient tier) and is NOT the delivery mechanism (Open Issue #2, resolved).
- **Atomicity ordering is mandatory:** on first touch, the durable backup must be on disk BEFORE the signed file is written, so "signed file exists" always implies "backup exists."
- **Never silently destroy a record** — the surviving ethic from the retired installer. A hand-edit to our file is preserved as a timestamped `MEMORY-<ts>.md`, never clobbered.
- **Memory dir convention:** `${CLAUDE_PROJECT_DIR}/.claude/qhaway-memory/`. `${CLAUDE_PROJECT_DIR}` is available to plugin hooks as both a substitution var and an env var (verified).
- **Plugin ships OFF:** `defaultEnabled: false` — the user opts into the auto-executing hook.
- **Acceptance test runs against a git-backed corpus FIRST** (yanantin or hamutay — both now in local git repos, so deploy/restore is git-reversible). governance is the untouched testbed with NO git backup — touch it only after the mechanical path is proven elsewhere.

---

### Task 1: In-file signature on the redirect template

**Why first:** every later task (classify-on-SessionStart, exit-index, heal) reads the signature. It currently lives only in the sidecar `.qhaway.json` (`last_output_hash`); the spec's Verification 1 decision is to move it IN-FILE so a lost sidecar + surviving MEMORY.md can't misclassify our output as a user original. This is the load-bearing identity primitive — build and test it before anything consumes it.

**Files:**
- Modify: `src/qhaway/reconcile.py` — add signature constants + `read_signature()` / `embed_signature()` / `strip_signature()`; rework `_heal_redirect` to classify by in-file signature.
- Test: `tests/test_signature.py` (create)

**Interfaces:**
- Produces:
  - `SIGNATURE_PREFIX: str` = `"<!-- qhaway:v1:"` and a closing `"-->"`; the signature line is `f"{SIGNATURE_PREFIX}{sha256_of_payload}-->"` as the FINAL line of the file.
  - `embed_signature(body: str) -> str` — returns `body` (rstripped) + `"\n" + signature_line(body) + "\n"`, where the hash is computed over `body` WITHOUT any signature line (so it's reproducible).
  - `read_signature(text: str) -> str | None` — returns the embedded hash if the last non-empty line matches `SIGNATURE_PREFIX...-->`, else `None`.
  - `strip_signature(text: str) -> str` — returns `text` with a trailing signature line removed (rstripped), so callers can recompute and compare.
- Consumes: `hashlib` (already imported), existing `_sha256`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_signature.py
from qhaway import reconcile


def test_embed_then_read_roundtrips():
    body = "# Memory\n\nsome redirect text\n"
    signed = reconcile.embed_signature(body)
    assert reconcile.read_signature(signed) is not None
    # signature is the last line
    assert signed.rstrip().splitlines()[-1].startswith(reconcile.SIGNATURE_PREFIX)


def test_read_signature_none_on_unsigned():
    assert reconcile.read_signature("# Memory\n\nplain user file\n") is None


def test_signature_hash_is_over_unsigned_body():
    body = "# Memory\n\ncontent\n"
    signed = reconcile.embed_signature(body)
    embedded = reconcile.read_signature(signed)
    # recomputing over the stripped body must match the embedded hash
    assert embedded == reconcile._sha256(reconcile.strip_signature(signed))


def test_strip_signature_is_inverse_of_embed():
    body = "# Memory\n\ncontent\n"
    signed = reconcile.embed_signature(body)
    assert reconcile.strip_signature(signed) == body.rstrip()


def test_tampered_body_detected():
    body = "# Memory\n\noriginal\n"
    signed = reconcile.embed_signature(body)
    tampered = signed.replace("original", "hand-edited by a human")
    # signature still present, but no longer matches the (now different) body
    assert reconcile.read_signature(tampered) is not None
    assert reconcile.read_signature(tampered) != reconcile._sha256(
        reconcile.strip_signature(tampered)
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_signature.py -v`
Expected: FAIL with `AttributeError: module 'qhaway.reconcile' has no attribute 'embed_signature'`

- [ ] **Step 3: Implement signature helpers in `reconcile.py`**

Add near the top of `src/qhaway/reconcile.py`, after the existing constants:

```python
SIGNATURE_PREFIX = "<!-- qhaway:v1:"
SIGNATURE_SUFFIX = "-->"


def signature_line(unsigned_body: str) -> str:
    return f"{SIGNATURE_PREFIX}{_sha256(unsigned_body.rstrip())}{SIGNATURE_SUFFIX}"


def embed_signature(body: str) -> str:
    stripped = body.rstrip()
    return stripped + "\n" + signature_line(stripped) + "\n"


def read_signature(text: str) -> str | None:
    lines = text.rstrip().splitlines()
    if not lines:
        return None
    last = lines[-1].strip()
    if last.startswith(SIGNATURE_PREFIX) and last.endswith(SIGNATURE_SUFFIX):
        return last[len(SIGNATURE_PREFIX):-len(SIGNATURE_SUFFIX)]
    return None


def strip_signature(text: str) -> str:
    lines = text.rstrip().splitlines()
    if lines and read_signature(text) is not None:
        lines = lines[:-1]
    return "\n".join(lines).rstrip()
```

(`_sha256` already takes a str and is defined later in the file; Python resolves it at call time, so order is fine.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_signature.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/qhaway/reconcile.py tests/test_signature.py
git commit -m "Add in-file signature primitives for MEMORY.md identity"
```

---

### Task 2: Rework `_heal_redirect` to classify by in-file signature

**Why:** the SessionStart state machine (spec §"SessionStart hook") needs the three-way classify — no-signature → snapshot-then-write; signature+matches → rebuild; signature+differs → preserve-hand-edit-then-regen. Currently `_heal_redirect` keys on the sidecar hash. Move it to read the in-file signature (Task 1), keeping the sidecar as a secondary record only.

**Files:**
- Modify: `src/qhaway/reconcile.py` — `REDIRECT_TEMPLATE` is now embedded-signed when written; `_heal_redirect` reads the in-file signature.
- Test: `tests/test_heal_redirect_signature.py` (create); existing `tests/` heal tests must still pass.

**Interfaces:**
- Consumes: `embed_signature`, `read_signature`, `strip_signature`, `_backup_path`, `write_readonly` (all existing or from Task 1).
- Produces: `_heal_redirect(root: Path)` with new classification:
  1. MEMORY.md absent → write `embed_signature(desired)`, after snapshotting nothing (no original to preserve).
  2. MEMORY.md present, `read_signature(current) is None` → it's a USER ORIGINAL: snapshot to backup FIRST (`current` → `MEMORY-<ts>.md`), THEN write `embed_signature(desired)`.
  3. present, signature present AND `read_signature(current) == _sha256(strip_signature(current))` → ours, unchanged → rewrite `embed_signature(desired)` (idempotent rebuild). No backup.
  4. present, signature present but hash mismatches → ours, hand-edited → preserve as `MEMORY-<ts>.md`, then write `embed_signature(desired)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_heal_redirect_signature.py
from pathlib import Path
from qhaway import reconcile


def _heal(tmp_path: Path) -> Path:
    reconcile._heal_redirect(tmp_path)
    return tmp_path / "MEMORY.md"


def test_absent_writes_signed_redirect(tmp_path):
    mem = _heal(tmp_path)
    text = mem.read_text()
    assert reconcile.read_signature(text) is not None
    assert "recall()" in text  # redirect content present


def test_user_original_is_snapshotted_then_replaced(tmp_path):
    original = "# My hand-written memory\n\nimportant human notes\n"
    (tmp_path / "MEMORY.md").write_text(original)
    _heal(tmp_path)
    backups = list(tmp_path.glob("MEMORY-*.md"))
    assert len(backups) == 1
    assert backups[0].read_text() == original  # original preserved verbatim
    assert reconcile.read_signature((tmp_path / "MEMORY.md").read_text()) is not None


def test_our_unchanged_output_rebuilds_without_backup(tmp_path):
    _heal(tmp_path)  # write ours once
    _heal(tmp_path)  # heal again, unchanged
    assert list(tmp_path.glob("MEMORY-*.md")) == []  # no spurious backup
    assert reconcile.read_signature((tmp_path / "MEMORY.md").read_text()) is not None


def test_hand_edit_to_our_file_is_preserved(tmp_path):
    _heal(tmp_path)
    mem = tmp_path / "MEMORY.md"
    # human edits our signed file but leaves the signature line
    edited = mem.read_text().replace("recall()", "recall()  # MY NOTE")
    mem.write_text(edited)
    _heal(tmp_path)
    backups = list(tmp_path.glob("MEMORY-*.md"))
    assert len(backups) == 1
    assert "MY NOTE" in backups[0].read_text()  # the edit was preserved
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_heal_redirect_signature.py -v`
Expected: FAIL — current `_heal_redirect` writes via sidecar logic, so `test_our_unchanged_output_rebuilds_without_backup` or the signature assertions fail.

- [ ] **Step 3: Rewrite `_heal_redirect`**

Replace the body of `_heal_redirect` in `src/qhaway/reconcile.py` (lines ~139–156) with:

```python
def _heal_redirect(root: Path) -> None:
    memory_file = root / MEMORY_NAME
    sidecar_file = root / SIDECAR_NAME
    override = root / "REDIRECT.md"
    desired_body = override.read_text(encoding="utf-8") if override.exists() else REDIRECT_TEMPLATE
    desired = embed_signature(desired_body)

    if memory_file.exists():
        current = memory_file.read_text(encoding="utf-8")
        sig = read_signature(current)
        if sig is None:
            # (2) user original — snapshot FIRST, then replace
            memory_file.rename(_backup_path(memory_file))
        elif sig != _sha256(strip_signature(current)):
            # (4) our file, hand-edited — preserve the edit, then regenerate
            memory_file.rename(_backup_path(memory_file))
        else:
            # (3) ours, unchanged — fall through to idempotent rewrite, no backup
            pass

    write_readonly(memory_file, desired)
    _write_sidecar(sidecar_file, _sha256(strip_signature(desired)))
```

Note: `_sha256(strip_signature(desired))` keeps the sidecar in sync as a secondary record; the in-file signature is now authoritative.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_heal_redirect_signature.py tests/ -v`
Expected: PASS for the new tests AND the full existing suite still green (re-run the whole `tests/` dir — older heal/redirect tests may assert sidecar behavior and need confirmation they still hold).

- [ ] **Step 5: Commit**

```bash
git add src/qhaway/reconcile.py tests/test_heal_redirect_signature.py
git commit -m "Classify MEMORY.md by in-file signature in heal_redirect"
```

---

### Task 3: `reconcile --emit` — reconcile then project to stdout

**Why:** the SessionStart hook must do reconcile-then-deliver in one invocation: reconcile the corpus, heal/sign the redirect, AND write the budgeted projection to stdout (which Claude Code injects as ambient context). `cli.py` today has `reconcile` (no stdout projection) and `index --dry-run` (projection to stdout, no heal). The hook needs both. Add an `--emit` flag to the `reconcile` subcommand.

**Files:**
- Modify: `src/qhaway/cli.py` — add `--emit` to the parser loop; in the reconcile branch, after `reconcile(directory)`, if `--emit`, open a connection and write `project.project_slice(...)` to stdout.
- Test: `tests/test_cli_reconcile_emit.py` (create)

**Interfaces:**
- Consumes: `reconcile(directory)` (existing), `model.get_connection`, `project.project_slice` (used the same way `_dry_run` uses it, `cli.py:64-74`).
- Produces: `qhaway reconcile --dir <d> --emit` → exit 0, stdout = budgeted projection (the SessionStart payload). Without `--emit`, behavior is unchanged (reconcile only, no stdout).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_reconcile_emit.py
from qhaway import cli, reconcile


def _seed(tmp_path):
    text = reconcile.compose_topic_file(
        "project", "a real memory", "body text here", None, None
    )
    (tmp_path / "a-real-memory.md").write_text(text)


def test_reconcile_emit_writes_projection_to_stdout(tmp_path, capsys):
    _seed(tmp_path)
    rc = cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "a real memory" in out  # the projection includes the seeded memory


def test_reconcile_without_emit_is_silent(tmp_path, capsys):
    _seed(tmp_path)
    rc = cli.main(["reconcile", "--dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == ""  # reconcile-only writes nothing to stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli_reconcile_emit.py -v`
Expected: FAIL — `--emit` is not a recognized argument (argparse error) or the reconcile branch ignores it.

- [ ] **Step 3: Add `--emit` to the parser and the reconcile branch**

In `src/qhaway/cli.py`, inside the `for name in (...)` parser loop (after line 27), add:

```python
        p.add_argument("--emit", action="store_true")
```

Then replace the reconcile fall-through block (lines 39–45) with:

```python
    # reconcile, and index-as-reconcile-alias
    try:
        reconcile(directory)
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    if getattr(ns, "emit", False):
        conn = model.get_connection(directory)
        try:
            sys.stdout.write(project.project_slice(conn, budget=ns.budget))
        finally:
            conn.close()
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_cli_reconcile_emit.py tests/ -v`
Expected: PASS for new tests AND full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/qhaway/cli.py tests/test_cli_reconcile_emit.py
git commit -m "Add reconcile --emit for SessionStart reconcile-then-deliver"
```

---

### Task 4: `qhaway exit` — write the current signed static index on SessionEnd

**Why:** the SessionEnd hook (the disable-restore path, spec §"SessionEnd hook") must write the CURRENT signed static index — a projection of the current DB, self-sufficient (no running qhaway needed), signed (so a re-enable recognizes it as ours), with a declared-omissions footer. NOT a restore of the stale install-time snapshot (that would discard everything `remember()` captured). Conditional exit: if the snapshotted ORIGINAL was genuinely hand-authored (a backup `MEMORY-*.md` whose content has NO signature), restore IT instead — ours is not a human's record.

**Files:**
- Modify: `src/qhaway/cli.py` — add `exit` to the subcommand list; add `_exit(directory, budget)`.
- Test: `tests/test_cli_exit.py` (create)

**Interfaces:**
- Consumes: `reconcile(directory)` (refresh DB first), `model.get_connection`, `project.project_slice`, `reconcile.embed_signature`, `reconcile.read_signature`, `_orphan_files` (existing, `cli.py:171` — returns sorted `MEMORY-*.md`).
- Produces: `qhaway exit --dir <d>` → exit 0; writes `MEMORY.md` =
  - **If a hand-authored original backup exists** (the OLDEST `MEMORY-*.md` whose content has `read_signature() is None`): restore that file's content verbatim to `MEMORY.md` (the human's record).
  - **Else:** `embed_signature(projection + omissions_footer)` — the current signed index.
  - Footer format: `"\n\n---\n_qhaway exit index — N memories, projected under <budget> bytes. Omitted: <count> (run `recall()` after re-enable for the full working set)._\n"`. Use `project_slice_with_overflow` to get the omitted count.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_exit.py
from qhaway import cli, reconcile


def _seed(tmp_path, title="a memory", body="body"):
    (tmp_path / f"{reconcile.slugify(title)}.md").write_text(
        reconcile.compose_topic_file("project", title, body, None, None)
    )


def test_exit_writes_signed_current_index(tmp_path):
    _seed(tmp_path)
    rc = cli.main(["exit", "--dir", str(tmp_path)])
    text = (tmp_path / "MEMORY.md").read_text()
    assert rc == 0
    assert reconcile.read_signature(text) is not None
    assert "a memory" in text          # current content, not a stale redirect
    assert "qhaway exit index" in text  # declared-omissions footer present


def test_exit_restores_hand_authored_original(tmp_path):
    _seed(tmp_path)
    original = "# Tony's hand-written notes\n\nkeep these\n"
    (tmp_path / "MEMORY-20260622T000000000000.md").write_text(original)  # unsigned backup
    rc = cli.main(["exit", "--dir", str(tmp_path)])
    assert rc == 0
    # the human's record is restored verbatim, NOT our projection
    assert (tmp_path / "MEMORY.md").read_text() == original


def test_exit_ignores_signed_backup_as_not_hand_authored(tmp_path):
    _seed(tmp_path)
    signed_backup = reconcile.embed_signature("# old qhaway output\n\nstale\n")
    (tmp_path / "MEMORY-20260622T000000000000.md").write_text(signed_backup)
    rc = cli.main(["exit", "--dir", str(tmp_path)])
    text = (tmp_path / "MEMORY.md").read_text()
    assert rc == 0
    # signed backup is OURS, not a human original → write current index, not restore
    assert "qhaway exit index" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli_exit.py -v`
Expected: FAIL — `exit` is not a registered subcommand (argparse: invalid choice).

- [ ] **Step 3: Implement `exit`**

In `src/qhaway/cli.py`: add `"exit"` to the subcommand tuple (line 19): `for name in ("reconcile", "check", "serve", "index", "exit"):`. Add the dispatch after the `serve` branch (line 33):

```python
    if ns.command == "exit":
        return _exit(directory, ns.budget)
```

Add the function:

```python
def _exit(directory: str, budget: int) -> int:
    memory_dir = Path(directory)
    if not memory_dir.is_dir():
        sys.stderr.write(f"memory directory is not readable: {memory_dir}\n")
        return 1

    # If a hand-authored original was snapshotted (unsigned backup), restore it.
    for backup in _orphan_files(memory_dir):  # oldest first (sorted by name)
        if reconcile.read_signature(backup.read_text(encoding="utf-8")) is None:
            from qhaway.reconcile import write_readonly
            write_readonly(memory_dir / MEMORY_NAME, backup.read_text(encoding="utf-8"))
            return 0

    reconcile.reconcile(directory)
    conn = model.get_connection(directory)
    try:
        result = project.project_slice_with_overflow(conn, budget=budget)
        total = len(model.topic_files(memory_dir))
    finally:
        conn.close()
    footer = (
        f"\n\n---\n_qhaway exit index — {total} memories, projected under "
        f"{budget} bytes. Omitted: {result.overflow_count} "
        "(run `recall()` after re-enable for the full working set)._\n"
    )
    from qhaway.reconcile import write_readonly, embed_signature
    write_readonly(memory_dir / MEMORY_NAME, embed_signature(result.markdown + footer))
    return 0
```

Add `reconcile` to the existing import (`cli.py:11` already does `from qhaway.reconcile import reconcile`; also need the module — change to `from qhaway import model, parse, project, reconcile, server` and use `reconcile.reconcile(...)`, OR keep the function import and reference helpers as `from qhaway.reconcile import ...` inline as shown). Pick one and keep it consistent.

Note: confirm `project_slice_with_overflow` returns an object with `.markdown` and `.overflow_count` (it's used in `server.recall`, `server.py:73-80`, with `.markdown`). Grep `project.py` for the overflow field name and match it exactly — if it's named differently (e.g. `.omitted`), use that.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_cli_exit.py tests/ -v`
Expected: PASS for new tests AND full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/qhaway/cli.py tests/test_cli_exit.py
git commit -m "Add qhaway exit: write current signed index on SessionEnd"
```

---

### Task 5: `bin/qhaway` launcher

**Why:** the hooks call a `qhaway` binary that must be on PATH while the plugin is enabled, with no separate pip install and no uvx cold-start. A small wrapper script that invokes the package's `cli.main` via the project's interpreter.

**Files:**
- Create: `qhaway-plugin/bin/qhaway` (executable shell script)
- Test: `tests/test_bin_launcher.py` (create) — invokes the script in a subprocess against a temp dir.

**Interfaces:**
- Produces: an executable `bin/qhaway` that runs `python -m qhaway.cli "$@"` with the plugin's bundled `src/` on `PYTHONPATH`, resolving the interpreter robustly (prefer a bundled `.venv`, else `python3`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bin_launcher.py
import os
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "qhaway-plugin" / "bin" / "qhaway"


def test_bin_reconcile_runs(tmp_path):
    (tmp_path / "m.md").write_text("---\nname: m\ntype: project\n---\nbody\n")
    env = dict(os.environ)
    result = subprocess.run(
        [str(BIN), "reconcile", "--dir", str(tmp_path)],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_bin_launcher.py -v`
Expected: FAIL — `qhaway-plugin/bin/qhaway` does not exist (FileNotFoundError on the subprocess).

- [ ] **Step 3: Write the launcher**

Create `qhaway-plugin/bin/qhaway`:

```bash
#!/usr/bin/env bash
# qhaway plugin launcher — runs the bundled package with no separate install.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugin_root="$(dirname "$here")"
src="$plugin_root/src"

# Prefer a bundled venv interpreter if present; else the system python3.
if [ -x "$plugin_root/.venv/bin/python" ]; then
  py="$plugin_root/.venv/bin/python"
else
  py="$(command -v python3)"
fi

PYTHONPATH="$src${PYTHONPATH:+:$PYTHONPATH}" exec "$py" -m qhaway.cli "$@"
```

Then make it executable and provide the bundled `src/`:

```bash
chmod +x qhaway-plugin/bin/qhaway
mkdir -p qhaway-plugin/src
cp -r src/qhaway qhaway-plugin/src/qhaway
```

(For the repo-local test, the launcher resolves `src/` under `qhaway-plugin/`; the copy above wires that. Later packaging may symlink or build instead — see Task 8's open item.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_bin_launcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qhaway-plugin/bin/qhaway qhaway-plugin/src tests/test_bin_launcher.py
git commit -m "Add bin/qhaway plugin launcher"
```

---

### Task 6: Plugin manifest, hooks.json, and .mcp.json

**Why:** these are the harness-facing wiring. The manifest declares the plugin (off by default); `hooks/hooks.json` registers SessionStart (reconcile-then-emit) + SessionEnd (exit); `.mcp.json` registers the recall/remember server. No new Python — this is the plugin shell that makes the previous tasks load-bearing.

**Files:**
- Create: `qhaway-plugin/.claude-plugin/plugin.json` (manifest)
- Create: `qhaway-plugin/hooks/hooks.json`
- Create: `qhaway-plugin/.mcp.json`
- Test: `tests/test_plugin_manifest.py` (create) — JSON-validates the three files and asserts key fields.

**Interfaces:**
- Consumes: `bin/qhaway` (Task 5), `qhaway reconcile --emit` (Task 3), `qhaway exit` (Task 4), `qhaway serve` (existing).
- Produces: valid plugin JSON the harness loads. Memory dir = `${CLAUDE_PROJECT_DIR}/.claude/qhaway-memory`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_plugin_manifest.py
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "qhaway-plugin"


def test_manifest_ships_off():
    m = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert m["name"] == "qhaway"
    assert m.get("defaultEnabled") is False


def test_hooks_register_sessionstart_and_sessionend():
    h = json.loads((ROOT / "hooks" / "hooks.json").read_text())
    events = h["hooks"]
    assert "SessionStart" in events and "SessionEnd" in events
    flat = json.dumps(h)
    assert "reconcile" in flat and "--emit" in flat  # start delivers
    assert "exit" in flat                              # end writes index
    assert "${CLAUDE_PROJECT_DIR}" in flat             # per-project memory dir


def test_mcp_json_registers_server():
    j = json.loads((ROOT / ".mcp.json").read_text())
    assert "qhaway" in j["mcpServers"]
    assert "${CLAUDE_PROJECT_DIR}" in json.dumps(j)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_plugin_manifest.py -v`
Expected: FAIL — the three JSON files don't exist.

- [ ] **Step 3: Write the three files**

`qhaway-plugin/.claude-plugin/plugin.json`:

```json
{
  "name": "qhaway",
  "version": "0.1.0",
  "description": "Borrowed-while-enabled memory: delivers the must-not-re-learn set at every session start, returns a current signed index on exit.",
  "defaultEnabled": false
}
```

`qhaway-plugin/hooks/hooks.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/bin/qhaway reconcile --dir \"${CLAUDE_PROJECT_DIR}/.claude/qhaway-memory\" --emit"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/bin/qhaway exit --dir \"${CLAUDE_PROJECT_DIR}/.claude/qhaway-memory\""
          }
        ]
      }
    ]
  }
}
```

`qhaway-plugin/.mcp.json`:

```json
{
  "mcpServers": {
    "qhaway": {
      "command": "${CLAUDE_PLUGIN_ROOT}/bin/qhaway",
      "args": ["serve", "--dir", "${CLAUDE_PROJECT_DIR}/.claude/qhaway-memory"]
    }
  }
}
```

(Confirm the exact manifest schema and hooks.json shape against `docs/qhaway-as-plugin-design.md` and the live plugins-reference doc before finalizing — `${CLAUDE_PLUGIN_ROOT}` is the documented plugin-root substitution var; verify it resolves in `.mcp.json` `command`, which may need an absolute or `${CLAUDE_PLUGIN_ROOT}`-prefixed path.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_plugin_manifest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qhaway-plugin/.claude-plugin qhaway-plugin/hooks qhaway-plugin/.mcp.json tests/test_plugin_manifest.py
git commit -m "Add plugin manifest, hooks.json, and .mcp.json"
```

---

### Task 7: Snapshot-on-first-touch atomicity test (integration)

**Why:** the spec's hard invariant — "signed file exists ⇒ backup exists." Tasks 2 and 4 implement the ordering; this task proves it end-to-end through the CLI surface the hook actually calls, and proves crash-resilience (next SessionStart self-corrects). This is the safety property the whole borrow/return contract rests on.

**Files:**
- Test: `tests/test_first_touch_atomicity.py` (create)

**Interfaces:**
- Consumes: `qhaway reconcile --emit` (Task 3, which calls `_heal_redirect`), `reconcile.read_signature`.

- [ ] **Step 1: Write the test**

```python
# tests/test_first_touch_atomicity.py
from qhaway import cli, reconcile


def test_signed_file_implies_backup_exists_for_user_original(tmp_path):
    original = "# human original\n\nirreplaceable\n"
    (tmp_path / "MEMORY.md").write_text(original)
    (tmp_path / "seed.md").write_text(
        reconcile.compose_topic_file("project", "seed", "b", None, None)
    )
    cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])
    mem = (tmp_path / "MEMORY.md").read_text()
    # signed file now exists...
    assert reconcile.read_signature(mem) is not None
    # ...therefore the original MUST be recoverable on disk
    backups = [p.read_text() for p in tmp_path.glob("MEMORY-*.md")]
    assert original in backups


def test_second_boot_is_idempotent_no_duplicate_backup(tmp_path):
    (tmp_path / "MEMORY.md").write_text("# human original\n\nx\n")
    (tmp_path / "seed.md").write_text(
        reconcile.compose_topic_file("project", "seed", "b", None, None)
    )
    cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])
    cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])  # reboot
    # exactly one backup — the second boot recognized our signature, didn't re-snapshot
    assert len(list(tmp_path.glob("MEMORY-*.md"))) == 1
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `.venv/bin/python -m pytest tests/test_first_touch_atomicity.py -v`
Expected: PASS if Tasks 2–3 are correct. If `test_second_boot...` FAILS with 2 backups, the classify in Task 2 is mis-detecting our own signed output as a user original — fix Task 2 before proceeding.

- [ ] **Step 3: Commit**

```bash
git add tests/test_first_touch_atomicity.py
git commit -m "Prove first-touch atomicity: signed file implies recoverable backup"
```

---

### Task 8: Acceptance trial against a git-backed corpus

**Why:** the spec's two-verdict acceptance test — did-it-deploy/restore-safely (mechanical) vs did-it-keep-the-RIGHT-memories (ranking). Run against **yanantin or hamutay** (git-backed → reversible), NEVER governance first (no git backup, it's the untouched testbed).

**Files:** none (operational). Produces a written verdict recorded as a `remember()` memory.

**Interfaces:** Consumes the whole plugin (Tasks 1–7) + `claude --plugin-dir ./qhaway-plugin`.

- [ ] **Step 1: Pick a git-backed target and confirm its git state is clean**

Run: `cd /home/tony/.claude/projects/-home-tony-projects-yanantin/memory && git status` (or the hamutay path).
Expected: a git repo, clean working tree (so any qhaway mutation is `git diff`-visible and `git checkout`-reversible).

- [ ] **Step 2: Back up MEMORY.md and the memory dir out-of-band too**

Run: `cp -r <target>/memory /tmp/qhaway-accept-backup-<corpus>`
(Belt-and-suspenders beyond git.)

- [ ] **Step 3: Deploy for one session via the flag**

Run: `claude --plugin-dir ./qhaway-plugin` in the target project; enable qhaway via `/plugin`; start a session.
Verify (mechanical): SessionStart injected a projection (visible in context); `.claude/qhaway-memory/MEMORY.md` is now signed; a backup of the original exists.

- [ ] **Step 4: End the session; verify the exit index**

Verify: SessionEnd wrote a current signed `MEMORY.md` (or restored the hand-authored original if one was snapshotted). `git diff` shows exactly the expected delta and nothing else.

- [ ] **Step 5: Restore and record the verdict**

Run: `git checkout .` (or restore from `/tmp` backup) to return the corpus.
Then `remember(type="project", ...)` a verdict separating the two questions: (a) did deploy/restore stay safe, (b) did the projection keep the cost-of-rediscovery memories resident (the ranking question — possibly yanantin's BM25 domain, not qhaway's). Link `[[open-issue-1-answered-reconcile-every-boot-is-fine-no-cache-needed]]` and the deploy-safety-map memory.

- [ ] **Step 6: Final full-suite green check**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: all green. Note any pre-existing flake (`test_cli_concurrent_remember_no_lost_body`) explicitly — it's a known timing flake, not a regression.

---

## Self-Review notes

- **Spec coverage:** SessionStart push (Tasks 3+6), SessionEnd current-index exit (Tasks 4+6), in-file signature (Task 1), three-way classify + snapshot-first ordering (Tasks 2+7), plugin manifest/hooks/.mcp.json/bin (Tasks 5+6), `defaultEnabled:false` (Task 6), `${CLAUDE_PROJECT_DIR}` memory dir (Task 6), acceptance test against git-backed corpus first (Task 8). Crash-resilience is covered by Task 7's idempotency test (next boot self-corrects via signature). Disable→edit→enable is reconcile-at-both-edges, already idempotent — no separate task needed.
- **Deferred / out of scope (flag, don't build):** `InstructionsLoaded` observability hook (resolved as not-the-delivery-mechanism); BM25 / ranked retrieval (yanantin's domain per spec boundary); dynamic temporal faceting (deferred past v1).
- **Open items to confirm during execution, not blocking the plan:** exact manifest schema + whether `${CLAUDE_PLUGIN_ROOT}` resolves inside `.mcp.json` `command` (Task 6 Step 3 note); the overflow-count field name on `project_slice_with_overflow` (Task 4 Step 3 note); how the bundled `src/` ships in the real plugin vs the repo-local copy (Task 5 Step 3 note).
