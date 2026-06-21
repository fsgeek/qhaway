# Third Follow-Up Review: Qhaway MCP Spine Design

**Date:** 2026-06-21
**Target spec:** `2026-06-21-qhaway-mcp-spine-design.md`
**Reviewer:** Codex
**Status:** Follow-up after third spec update

The latest update addresses the previous SFUP-1 finding: `qhaway check --dir ...`
is now the explicit read-only inspection command, and `qhaway index --check` is a
temporary deprecated alias. The stray final Markdown fence is also gone.

The new Gemini-resolution additions are useful, but they introduce two fresh
implementation concerns.

## Findings

### TFUP-1: Schema-drift rebuild needs cross-process coordination

**Severity:** High

The new G-3 rule says that on `PRAGMA user_version` mismatch or schema-drift
`OperationalError`, qhaway closes the connection, deletes all three SQLite files,
and rebuilds from topic files. That is correct for a derived index in a single
process, but unsafe across the process model this spec already has: startup hook,
MCP server, and manual CLI can all touch the same co-located DB.

On Unix-like systems, deleting/recreating the DB files while another process has
an open SQLite connection can fork reality: the old process may continue using an
unlinked DB file while the new process creates a fresh `.qhaway.db`. That yields
two live derived indexes until the old process exits, exactly the kind of hidden
two-mode divergence the design is trying to eliminate.

**Recommendation:** Add a narrow cross-process reset lock for schema rebuilds and
WAL-file teardown. Normal reconcile can keep relying on SQLite `BEGIN IMMEDIATE`
plus `busy_timeout`, but destructive DB-file replacement needs a file-level guard
such as `.qhaway.db.reset.lock` acquired before deleting any DB artifact. If the
lock cannot be acquired, fail loud or wait with a bounded timeout. Also require
long-running `serve` to notice schema-version mismatch on startup and after failed
DB operations, then restart/reopen through the same reset path rather than holding
an obsolete connection indefinitely.

### TFUP-2: MCP stdout discipline must separate startup failures from tool-call failures

**Severity:** Medium

The new G-5 rule correctly says stdout must be reserved for JSON-RPC and that
startup/init/resolution diagnostics must go to stderr. But the architecture row
and G-5 resolution also say "all errors/traces/resolution-failures -> stderr,
exit non-zero." That is too broad once the MCP server is running.

For an accepted MCP request, a tool failure must be returned as a structured
JSON-RPC/MCP error on stdout, not only logged to stderr and not by killing the
server. This is the same C-10 point at the transport layer: a bad `remember` call
or DB write failure during a tool invocation should be an in-band tool error, not
a protocol crash.

**Recommendation:** Split the rule explicitly:

- Before JSON-RPC serving starts: all diagnostics to stderr; exit non-zero on
  fatal startup failures.
- After serving starts: stdout contains only JSON-RPC frames, including structured
  error responses for tool-call failures; stderr is for logs/traces only and must
  not replace the in-band error response.

## Minor Cleanup

Several older lines still say dangling links are surfaced by `--check`. Since the
canonical command is now `qhaway check`, consider changing those to "`qhaway
check`" and reserving "`index --check`" only for the explicitly deprecated alias.
