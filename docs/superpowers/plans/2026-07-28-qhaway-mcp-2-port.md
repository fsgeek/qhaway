# qhaway MCP 2.0 Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move qhaway's MCP server off the removed `mcp.server.fastmcp` API onto the `mcp 2.0` `MCPServer` API, and correct the public README before the release that carries the change.

**Architecture:** `mcp.server.mcpserver.MCPServer` (re-exported as `mcp.server.MCPServer`) is FastMCP's successor. The tool decorator, the run loop, and stdio-as-default are unchanged, so `build_server`'s binding layer survives intact — three lines move. One of the three is a deletion: 2.0 accepts `version` as a constructor argument, retiring the private-attribute assignment that `server.py:127-129` exists to apologize for. A new test lands *first*, on 1.x, because the only existing test that invokes a tool through `build_server` skips without an ArangoDB and therefore guards nothing in CI.

**Tech Stack:** Python 3.14, `mcp[cli]` 2.x, pytest 9, uv (lock + sync + run), ArangoDB (optional, re-grounding tests only).

**Spec:** [`docs/superpowers/specs/2026-07-28-qhaway-mcp-2-port-design.md`](../specs/2026-07-28-qhaway-mcp-2-port-design.md)

## Global Constraints

- `requires-python = ">=3.14"`. Unchanged; do not touch.
- The dependency bound becomes exactly `mcp[cli]>=2,<3`. No shim, no `try`/`except ImportError`, no dual-version support.
- Adopt no mcp 2.0 capability qhaway does not already use: no middleware, extensions, elicitation, structured-output declarations, lifespan hook, or transport beyond stdio. The port changes which API the two verbs bind through. It does not change what they do.
- `main` is protected and merges only via PR with green CI (`CONTRIBUTING.md`). All work happens on a branch.
- Every dependency edit is followed by `uv lock` in the **same commit**. CI runs `uv sync --locked`, which fails on a drifted lock — that surfaces as a build failure, not a test failure, and misleads anyone bisecting.
- Do not modify `qhaway-plugin/.claude-plugin/plugin.json` (version `0.1.7`) or `README.md:106`'s `qhaway index --check`. Both are open questions for the maintainer, not defects to fix here.
- Publishing to PyPI and editing `~/.claude.json` are maintainer actions. Task 4 documents them; no agent performs them.

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `tests/test_serve_recall_tool.py` | Proves `recall` is reachable through the built server's tool interface, with no live store required | **Create** (Task 1) |
| `pyproject.toml` | Declares the mcp bound | Modify line 17 (Task 2) |
| `uv.lock` | Pins the resolved graph CI installs | Regenerate (Task 2) |
| `src/qhaway/server.py` | Binds the two verbs to an MCP server | Modify lines 123-139 (Task 2) |
| `tests/test_version.py` | Asserts the handshake reports qhaway's version | Modify line 35 (Task 2) |
| `tests/test_serve_regrounds_claim.py` | Asserts deployed recall re-grounds claims live | Modify line 52 (Task 2) |
| `README.md` | The public description of the shipped package | Modify lines 128, 179 (Task 3) |

---

### Task 1: Guard the tool-invocation seam before touching it

**Files:**
- Test: `tests/test_serve_recall_tool.py` (create)

**Interfaces:**
- Consumes: `server.initialize_server(memory_dir: str) -> None` and `server.build_server(memory_dir: str)` from `src/qhaway/server.py`.
- Produces: a test that Task 2 edits in exactly one place — the result-unwrapping line.

**Why this task exists:** `tests/test_serve_regrounds_claim.py` calls `pytest.skip` unless `~/.yanantin/config/db.ini` exists. It is the only test that invokes a tool through `build_server`. On CI and on any machine without a yanantin config, the tool-invocation path is untested. Porting that seam without this guard produces a green suite that says nothing about the thing being ported.

This test needs no ArangoDB: `reground.default_provider()` returns `None` on a base install, so `recall` projects byte-identically and the test runs everywhere.

- [ ] **Step 1: Create the branch**

```bash
cd /home/tony/projects/qhaway
git checkout -b mcp-2-port
```

- [ ] **Step 2: Write the test**

Create `tests/test_serve_recall_tool.py`:

```python
"""The recall verb is reachable through the built server's tool interface.

Guards the MCP binding seam in build_server. Unlike the re-grounding tests this
needs no live store: reground.default_provider() returns None on a base install,
so recall projects byte-identically and this runs everywhere, CI included.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from qhaway import server


def _write_memory(root: Path, stem: str, frontmatter: str, body: str) -> Path:
    path = root / f"{stem}.md"
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


def test_recall_tool_returns_the_projection(tmp_path):
    _write_memory(
        tmp_path,
        "reachable-memory",
        "name: reachable-memory\ntype: project\ndescription: proves the tool path is wired\n",
        "The binding seam is reachable.\n",
    )
    server.initialize_server(str(tmp_path))

    mcp = server.build_server(str(tmp_path))
    result = asyncio.run(mcp.call_tool("recall", {}))
    text = result[0][0].text

    assert "reachable-memory" in text
    assert "proves the tool path is wired" in text
```

Note the unwrap: mcp 1.x's public `call_tool` returns a `(content_blocks, structured)` **tuple**, so the text is at `result[0][0].text`. This was confirmed by running it, not read off the type signature — the annotation says `Sequence[ContentBlock] | dict[str, Any]`, which is misleading.

- [ ] **Step 3: Run it and confirm it passes on the current dependency**

Run: `uv run pytest tests/test_serve_recall_tool.py -q -rs`
Expected: `1 passed`. It must **not** appear in the skip list — that is the whole point of the task. If it skips, the test picked up a live-store dependency it should not have.

- [ ] **Step 4: Confirm the whole suite is still green before any port work**

Run: `uv run pytest -q`
Expected: all pass, with the `test_serve_regrounds_claim.py` and `test_claim_regrounding.py` live-store tests skipping. Record this as the baseline.

- [ ] **Step 5: Commit**

```bash
git add tests/test_serve_recall_tool.py
git commit -m "test: guard the MCP tool-invocation seam without a live store"
```

---

### Task 2: Port to the mcp 2.0 API

**Files:**
- Modify: `pyproject.toml:17`
- Modify: `uv.lock` (regenerated, not hand-edited)
- Modify: `src/qhaway/server.py:123-139`
- Modify: `tests/test_version.py:35`
- Modify: `tests/test_serve_regrounds_claim.py:52`
- Modify: `tests/test_serve_recall_tool.py` (the unwrap line from Task 1)

**Interfaces:**
- Consumes: `MCPServer(name: str, ..., instructions: str | None = None, version: str = "")` from `mcp.server`; its `.tool()` decorator and `.run()` are signature-compatible with FastMCP's.
- Produces: `build_server(memory_dir: str) -> MCPServer`. Its private low-level handle is `_lowlevel_server` (was `_mcp_server`). Its public `call_tool(name, arguments)` returns `CallToolResult`, whose text is at `.content[0].text`.

This task is atomic. The dependency bound and the code that depends on it cannot be split without leaving the repository in a state where the suite cannot pass.

- [ ] **Step 1: Move the dependency bound**

In `pyproject.toml`, line 17:

```toml
    "mcp[cli]>=2,<3",
```

replacing `"mcp[cli]>=1.28.0,<2",`.

That `<2` ceiling is currently an **uncommitted** working-tree edit, made during the
outage triage and never committed. It is superseded here rather than committed
first: the emergency ceiling and the port are two answers to the same question,
and only one of them ships. `git status` will have shown `M pyproject.toml` since
before Task 1 — that is expected, not a dirty tree to clean up.

- [ ] **Step 2: Regenerate the lock and sync**

```bash
uv lock
uv sync --group dev
```

Expected: `uv.lock` shows `mcp` at a 2.x version. Confirm with `uv pip show mcp`.

- [ ] **Step 3: Run the suite and watch it fail**

Run: `uv run --no-sync pytest -q`
Expected: FAIL. `tests/test_version.py` and `tests/test_serve_recall_tool.py` both error out of `build_server` with `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`. This is the failing state the rest of the task resolves; do not skip it.

- [ ] **Step 4: Port `build_server`**

In `src/qhaway/server.py`, replace lines 123-139 — from the `def build_server` line through the `mcp._mcp_server.version = __version__` assignment — with:

```python
def build_server(memory_dir: str):
    """Construct the configured MCPServer (tools bound, version surfaced)
    WITHOUT running the blocking loop — the testable seam for the handshake.

    `version` is what a client reads as serverInfo.version; passing it here keeps
    the SDK's own version from being misreported.
    """
    from qhaway import __version__, reground as reground_mod
    from mcp.server import MCPServer

    mcp = MCPServer(
        "qhaway",
        instructions=f"qhaway memory server v{__version__}. Call recall() first; "
        "your context is stale and recall() is the latest word.",
        version=__version__,
    )
```

Three things happened: the import moved, `FastMCP` became `MCPServer` with `version=` passed in, and the `mcp._mcp_server.version = __version__` line is **gone**. The docstring paragraph that explained the workaround goes with it — the constructor no longer lacks a version pass-through, so an explanation of why it must be patched afterward would be false.

Everything below this point in the function — the `_reground` discovery, both `@mcp.tool()` blocks, and `return mcp` — is unchanged. Do not touch it.

- [ ] **Step 5: Update the handshake test**

In `tests/test_version.py`, line 35:

```python
    opts = mcp._lowlevel_server.create_initialization_options()
```

replacing `mcp._mcp_server.create_initialization_options()`.

Leave the two assertions below it exactly as they are, including `assert opts.server_version != "1.28.0"`. That is not a version check that has gone stale — it is a regression guard against reporting *the SDK's* version instead of qhaway's, and `1.28.0` is the specific string that made the original bug visible.

- [ ] **Step 6: Update the two unwrap sites**

In `tests/test_serve_regrounds_claim.py`, replace the body of `_deployed_recall` (line 52):

```python
def _deployed_recall(memory_dir: Path, **args) -> str:
    mcp = server.build_server(str(memory_dir))
    result = asyncio.run(mcp.call_tool("recall", args))
    return result.content[0].text
```

The helper still returns `str`, so both callers and every assertion downstream (`out.count(...)`, `... in out`) are unchanged.

In `tests/test_serve_recall_tool.py`, the unwrap line becomes:

```python
    text = result.content[0].text
```

mcp 2.0's `call_tool` returns a `CallToolResult` rather than 1.x's tuple. Note the attribute is `is_error`, not `isError`, if you ever need it — pydantic will raise `AttributeError` on the camelCase spelling.

- [ ] **Step 7: Run the suite and confirm it passes**

Run: `uv run --no-sync pytest -q -rs`
Expected: all pass. `test_serve_recall_tool.py` passes and is **not** in the skip list. The live-store tests still skip.

- [ ] **Step 8: Confirm no 1.x API references survive**

Run: `grep -rn "fastmcp\|_mcp_server" src/ tests/`
Expected: no output. A hit in a comment or docstring counts as a failure — the words describe an API that no longer exists.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock src/qhaway/server.py tests/test_version.py \
        tests/test_serve_regrounds_claim.py tests/test_serve_recall_tool.py
git commit -m "feat: port the MCP spine to the mcp 2.0 MCPServer API"
```

---

### Task 3: Correct the README before release

**Files:**
- Modify: `README.md:128`, `README.md:179`

**Interfaces:**
- Consumes: the `remember` signature at `src/qhaway/server.py:154` — `remember(type, title, body, description=None, links=None, supersedes=None)`.
- Produces: nothing consumed by later tasks.

`qhaway` is a live PyPI package; the README is what a stranger reads before deciding whether to trust it. Two statements in it are false about the shipped package. Correct exactly those two. The prose, structure, and claims elsewhere stay as written.

- [ ] **Step 1: Correct the `remember` signature**

`README.md:128-129` currently reads:

```markdown
- `remember(type, title, body, description?, links?)` — writes a topic file then
  reconciles. Files stay truth; the DB is a derived, rebuildable view.
```

Replace with:

```markdown
- `remember(type, title, body, description?, links?, supersedes?)` — writes a
  topic file then reconciles. Pass `supersedes` naming the memory this one
  retires, and recall demotes the loser. Files stay truth; the DB is a derived,
  rebuildable view.
```

This is the substantive correction. The published docs describe a narrower tool than the one that ships: a reader cannot discover the retirement mechanism from them at all.

- [ ] **Step 2: Correct the status version**

`README.md:179` currently reads:

```markdown
Early (`v0.2.1`). The design is specified in
```

Replace `v0.2.1` with `v0.4.0`, leaving the rest of the sentence and the spec link untouched.

- [ ] **Step 3: Verify both corrections**

```bash
grep -n "supersedes" README.md
grep -n "v0\.4\.0" README.md
grep -rn "v0\.2\.1" README.md
```

Expected: the first two match; the third returns nothing.

- [ ] **Step 4: Confirm the signature matches the code**

Run: `grep -n "def remember" src/qhaway/server.py`
Expected: the parameter list matches what the README now claims, `supersedes` included.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: correct the README's remember signature and status version"
```

---

### Task 4: Release runbook (maintainer-operated)

**Files:** none in this repository.

This task is not executed by an implementing agent. Publishing to PyPI is outward-facing and irreversible, and `~/.claude.json` is the maintainer's live configuration. The steps are recorded here so the sequence is not reconstructed from memory later.

The ordering is load-bearing. The pin currently keeping the deployed server alive becomes a resolution conflict the moment a `>=2` qhaway is published.

- [ ] **Step 1: Open the PR and merge on green**

```bash
git push -u origin mcp-2-port
gh pr create --fill
```

`main` is protected; merge only with CI green.

- [ ] **Step 2: Publish**

`pyproject.toml` is at `0.4.0` and PyPI's latest is `0.3.0`, so `0.4.0` is unpublished and the port rides it with no version bump. If `0.4.0` ships for another reason before this merges, the port needs its own version.

- [ ] **Step 3: Remove the emergency pin**

Delete `--with 'mcp<2'` from the qhaway server entry in `~/.claude.json`.

Do **not** restore `~/.claude.json.bak-qhaway-*` wholesale. That backup predates the pin, but it also predates any later edits to the file, and restoring it would silently revert them.

- [ ] **Step 4: Restart and confirm the handshake**

Restart Claude Code, then check that the qhaway MCP server connects and that `recall()` returns a projection.

Expected failure mode if Step 3 is skipped: `uvx` is asked for `mcp<2` and `mcp>=2` simultaneously and refuses to resolve. This fails loudly at launch rather than silently at import — a strict improvement on the original incident, but only for someone who knows to look, which is why it is a numbered step and not a remark.

---

## Verification Summary

The spec's success criteria, and the step that discharges each:

| Criterion | Discharged by |
| --- | --- |
| Suite passes under mcp 2.x | Task 2, Steps 2 and 7 |
| Handshake reports qhaway's version | Task 2, Steps 5 and 7 |
| Live `recall` through the built server returns its projection, without skipping | Task 1 Step 3, re-run at Task 2 Step 7 |
| No `fastmcp` or `_mcp_server` references remain | Task 2, Step 8 |
| README describes the shipped package | Task 3, Steps 3 and 4 |
