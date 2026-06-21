# Follow-Up Review: Qhaway MCP Spine Design

**Date:** 2026-06-21
**Target spec:** `2026-06-21-qhaway-mcp-spine-design.md`
**Reviewer:** Codex
**Status:** Follow-up after spec update

The update addresses the prior Codex findings C-1 through C-11 in substance. The
important fixes are now pinned: `project_slice(...) -> str` remains stable,
SQLite `DESCRIBE` is removed, `serve` reconciles once at startup, concurrent
topic creation uses exclusive create, reconcile is transactional, the 0444 fence
is honestly scoped, empty-dir init succeeds, WAL sidecars are named, valid
redirects repair missing sidecars, MCP failures are structured, and `links` are
normalized.

Two concerns remain after the update.

## Findings

### FUP-1: `qhaway index` as a redirect alias conflicts with the unchanged regression suite

**Severity:** High

The updated spec resolves OQ-3 by making `qhaway index` a deprecated alias for
`reconcile`, meaning `index` now writes the small redirect rather than the full
budgeted projection. That creates a new contradiction with the regression guard,
which still says the existing `tests/test_qhaway.py` suite must pass unchanged.

The current tests call `qhaway index` and assert full-projection behavior: budgeted
entries, declared omissions, `--type`/`--role`/`--status` slices, `--dry-run`,
and `--check` behavior. If `index` writes only the redirect, those tests cannot
pass unchanged, and several existing CLI flags lose their clear meaning.

**Recommendation:** Choose one contract explicitly:

- Keep `qhaway index` as the legacy full-projection command for regression
  compatibility, and add `qhaway reconcile`/`init` for redirect-writing.
- Or retire the full-projection CLI behavior intentionally, but amend the
  regression guard to say the existing suite will be updated because the CLI
  contract changed. In that case, list the replacement behavior for `--dry-run`,
  `--budget`, `--type`, `--role`, and `--status`.

The current text tries to keep "tests unchanged" and "index no longer projects";
those are incompatible.

### FUP-2: The error-handling section still says MCP failures return error strings

**Severity:** Medium

The C-10 resolution correctly says MCP tool errors must be structured failures,
not successful string results. However, the earlier Error handling section still
says `remember` should "return an error string" on slug collision, unreadable
memory dir, or DB build failure.

That stale sentence will steer implementation toward the rejected behavior.

**Recommendation:** Update the Error handling section to match C-10: MCP tools
raise or return structured tool errors on failure; strings are only successful
outputs. Keep CLI errors as stderr plus non-zero exit.

## Minor Cleanup

The architecture table still describes `server.py` as calling
`reconcile`/`project_slice` and "returns strings." Since the data flow now routes
`recall` through `project_slice_with_overflow(...)`, consider updating that row to
avoid reintroducing the old API ambiguity.
