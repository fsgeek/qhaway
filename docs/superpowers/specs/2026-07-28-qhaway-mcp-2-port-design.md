# qhaway MCP 2.0 Port

**Date:** 2026-07-28
**Status:** Proposed
**Scope:** `src/qhaway/server.py`, two tests, the `mcp` dependency bound, the
public README's accuracy ahead of publishing, and the sequenced release step that
retires the emergency launcher pin

## Problem

The `mcp` SDK published 2.0.0, which removes `mcp.server.fastmcp`. qhaway's
dependency spec was `mcp[cli]>=1.28.0` with no upper bound, so any fresh resolve
accepted 2.0.0 and the server died at import — surfacing to the client as JSON-RPC
`-32000`, "connection closed", with the real traceback only in the MCP logs.

Two mitigations are already in place and neither is the fix:

- `~/.claude.json` starts qhaway with `--with 'mcp<2'` (backup at
  `~/.claude.json.bak-qhaway-*`). This keeps the deployed server running.
- `pyproject.toml` carries an uncommitted `mcp[cli]>=1.28.0,<2` ceiling, which
  documents the constraint at the source but only takes effect on the next
  published release.

Both buy time against the 1.x API. Neither moves qhaway onto the API that exists.

## Decision summary

Port to the 2.0 API and require it: `mcp[cli]>=2,<3`. One code path, no
compatibility shim.

The 2.0 replacement for `FastMCP` is `mcp.server.mcpserver.MCPServer`, re-exported
as `mcp.server.MCPServer`. The tool decorator and `run()` are unchanged, and stdio
remains the default transport, so the binding layer in `build_server` survives
intact.

All API claims below were verified against an installed `mcp 2.0.0` in a scratch
virtualenv, not recalled from training data.

## The change

### Production — `src/qhaway/server.py`

| Site | Now | After |
| --- | --- | --- |
| `server.py:132` | `from mcp.server.fastmcp import FastMCP` | `from mcp.server import MCPServer` |
| `server.py:134` | `FastMCP("qhaway", instructions=…)` | `MCPServer("qhaway", instructions=…, version=__version__)` |
| `server.py:139` | `mcp._mcp_server.version = __version__` | *deleted* |

The deletion is the substantive part. `build_server`'s docstring
(`server.py:127-129`) records why the assignment existed: *"FastMCP's constructor
exposes no version pass-through, so set it on the wrapped low-level server."* 2.0
adds `version` as a constructor parameter. The workaround is not translated
forward — it is removed, along with the paragraph explaining it. Reaching into a
private attribute to correct a reported version stops being necessary.

### Tests

Two seams reach into internals that 2.0 renamed or promoted. Both move in the
direction of less private access.

- `tests/test_version.py:35` — `mcp._mcp_server` is renamed `_lowlevel_server`.
  The assertion still reads `create_initialization_options().server_version`,
  because that is the value a client actually receives in the handshake; asserting
  the public `MCPServer.version` attribute instead would test the constructor
  rather than the wire. The companion assertion `!= "1.28.0"` is retained as
  written — it is a regression guard against reporting *the SDK's* version, and
  the specific string is the historical value that made the bug visible.
- `tests/test_serve_regrounds_claim.py:52` — `mcp._tool_manager.call_tool(name,
  args)` becomes the public `mcp.call_tool(name, args)`. The return type changes
  from a bare string to `CallToolResult`, so the `_deployed_recall` helper unwraps
  `result.content[0].text` and returns that. The helper's signature and every
  caller stay unchanged.

One new test is added, because a coverage gap makes the port unverifiable
otherwise. `test_serve_regrounds_claim.py` skips unless
`~/.yanantin/config/db.ini` exists, and CI's own comment records that these
live-store tests "skip cleanly." It is the only test that invokes a tool through
`build_server`, so in CI and on any box without a yanantin config, **nothing
exercises the tool-invocation path at all**. Porting the `call_tool` seam under
that condition would produce a green suite that proves nothing about the seam
being ported.

`tests/test_serve_recall_tool.py` closes the gap: build a server over a temporary
memory directory, invoke `recall` through the public `call_tool`, and assert the
projection text comes back. It needs no ArangoDB — `reground.default_provider()`
returns `None` on a base install and recall stays byte-identical — so it runs
everywhere, including CI.

It is written and passing against mcp 1.x *before* the port, so it functions as a
regression guard across the migration rather than as a post-hoc justification.
Its result-unwrapping line changes with the port, along with the one in
`_deployed_recall`; both shapes are given in the plan.

No other tests are added. With this one in place, the suite covers the handshake
version and a live tool invocation — exactly the two behaviors the port can
break.

### Dependency

`pyproject.toml:17` becomes `mcp[cli]>=2,<3`, replacing the uncommitted `<2`
ceiling. The `cli` extra still exists in 2.0. `requires-python = ">=3.14"` is
unaffected.

`uv.lock` is regenerated in the same commit. CI runs `uv sync --locked`, which
fails when the lock disagrees with `pyproject.toml`, so a dependency change that
skips the lock fails the build rather than the tests — a confusing signal for
anyone bisecting later.

## Release sequencing

The pin that is currently keeping the deployed server alive becomes a resolution
conflict the moment a `>=2` qhaway is published. These steps are ordered and the
order matters:

1. Land the port; CI green.
2. Publish a release. `pyproject.toml` is at `0.4.0` and PyPI's latest is
   `0.3.0`, so `0.4.0` is unpublished and the port rides it without a bump. If
   `0.4.0` ships for other reasons before the port lands, the port needs its own
   version. Until *some* release carrying the new bound exists, `uvx` keeps
   serving `0.3.0` from the registry and nothing changes for the deployed server.
3. Remove `--with 'mcp<2'` from `~/.claude.json`. The backup at
   `~/.claude.json.bak-qhaway-*` predates the pin and should not be restored
   wholesale, since it also predates any later edits.
4. Restart the session and confirm the handshake.

Failure mode if step 3 is skipped: `uvx` is asked for `mcp<2` and `mcp>=2` at
once and refuses to resolve. This fails loudly at launch rather than silently at
import, which is a strict improvement over the original incident — but only if
someone knows to look, which is why it is a numbered step here rather than a
remark.

## Pre-release documentation accuracy

`qhaway` is a live PyPI package. The README is what a stranger reads before
deciding whether to trust the thing, so it is corrected *before* the release that
carries the port, not after. Two drifts are in scope:

- `README.md:179` states `Status: Early (v0.2.1)`. PyPI's latest is `0.3.0` and
  this release is `0.4.0`. The version becomes `0.4.0`.
- `README.md:128` documents `remember(type, title, body, description?, links?)`.
  The shipped verb also accepts `supersedes` (`server.py:154`), which is how a
  memory retires an earlier one. The signature gains `supersedes?` and one clause
  describing it, matching the language already in the tool's own docstring. This
  is the substantive correction: the public documentation currently describes a
  narrower tool than the one that ships, so a reader cannot discover the
  retirement mechanism from the docs at all.

Nothing else in the README is rewritten. The prose, structure, and claims stay as
they are; only statements that are factually false about the shipped package
change.

Two adjacent items are deliberately **not** changed here, both pending a call from
the maintainer:

- `qhaway-plugin/.claude-plugin/plugin.json` declares `version: 0.1.7` against
  `pyproject.toml`'s `0.4.0`. This may be intentional independent versioning of
  the plugin rather than drift, and guessing wrong writes a false version into a
  published manifest.
- `README.md:106` documents `qhaway index --check`, which `cli.py:29` marks as a
  deprecated alias for `qhaway check`. Leading with the deprecated spelling is
  wrong-footing but not false, and which spelling the docs should teach is a
  documentation-policy decision, not a correctness fix.

## Decision accounting

**Decision:** Require `mcp[cli]>=2,<3` and maintain a single code path against the
2.0 API.

**Evidence:** The 2.0 surface qhaway uses is nearly identical to 1.x — the
decorator, the transport default, and the run loop are unchanged. The only
behavioral difference in qhaway's favor is that version reporting became a
supported constructor argument. The production diff is three lines.

**What it preserves:** one code path; the existing test suite as the verification
surface; qhaway's small dependency footprint; the removal of a private-attribute
workaround.

**What it gives up:** installability against mcp 1.x. Anyone holding a 1.x-pinned
environment gets a hard requirement change on upgrade, with no graceful
degradation and no fallback path.

**What remains visible:** the version bound in `pyproject.toml`, the launcher pin
until step 3 retires it, and CI resolving a single mcp major.

**Failure behavior:** a resolution conflict at launch — loud, immediate, and
attributable — rather than an ImportError surfacing as an opaque transport
closure.

**Reversibility:** three lines and a bound. The 1.x code is one `git revert` away
and is not deleted from history.

**Revisit condition:** a user reports a real constraint holding them on mcp 1.x,
or mcp 3.0 appears.

## Alternatives considered

**Dual support via an import shim.** `try: from mcp.server import MCPServer /
except ImportError: from mcp.server.fastmcp import FastMCP`, with branched
version plumbing and branched test helpers. Rejected on three grounds. The
compatibility window has no identified occupant: fresh resolves get 2.x under
either option, and cached 1.x environments keep working precisely because they do
not re-resolve. CI has no mcp version matrix, so the 1.x branch would be an
untested compatibility claim — a declared standing with no evidence behind it,
which is the failure class this project exists to refuse. And it is asymmetrically
hard to remove: deleting the legacy branch later requires establishing that nobody
depends on 1.x, a fact nobody is positioned to collect.

**Hold at `<2` and defer.** Commit the ceiling, keep the launcher pin, port later.
This is the current state, and it is stable rather than safe: it freezes qhaway on
a removed API while the ecosystem moves, and it leaves the pin in place with no
record of why. Rejected because the port is smaller than the deferral is
expensive.

## Out of scope

No adoption of 2.0 capabilities qhaway does not currently need — no middleware, no
extensions, no elicitation, no structured output declarations, no transport beyond
stdio, no lifespan hook. The port changes which API the existing two verbs are
bound through. It does not change what they do.

## Success criteria

1. `mcp[cli]>=2,<3` resolves and the full test suite passes under mcp 2.0.
   → verify: `uv run pytest` green, and `uv pip show mcp` reports a 2.x version.
2. The handshake reports qhaway's version, not the SDK's.
   → verify: `test_mcp_serverinfo_reports_qhaway_version` passes against
   `_lowlevel_server`.
3. A live `recall` through the built server still returns its projection.
   → verify: `test_serve_recall_tool.py` passes **without skipping** on a box
   with no `~/.yanantin/config/db.ini`. `pytest -q -rs` must not list it among
   the skips.
4. `grep -rn "fastmcp\|_mcp_server" src/ tests/` returns nothing.
5. The README describes the shipped package.
   → verify: its status line reads `0.4.0`, and its `remember` signature lists
   `supersedes` — matching `server.py:154`.
