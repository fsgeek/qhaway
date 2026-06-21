# Fourth Follow-Up Review: Qhaway MCP Spine Design

**Date:** 2026-06-21
**Target spec:** `2026-06-21-qhaway-mcp-spine-design.md`
**Reviewer:** Codex
**Status:** Follow-up after fourth spec update

The latest update resolves the prior TFUP-2 concern: the server row now correctly
splits stdout discipline by phase. Startup failures go to stderr and exit
non-zero; accepted tool-call failures return in-band structured MCP errors on the
JSON-RPC stream.

TFUP-1 is partly addressed, but the destructive rebuild coordination still has a
hole.

## Findings

### FFUP-1: The reset lock must be observed by normal DB users, not only resetters

**Severity:** High

The spec now adds `.qhaway.db.reset.lock` for the destructive
delete-all-three-and-rebuild path. That serializes two concurrent resetters, but
it does not prevent the original TFUP-1 failure mode by itself: a normal
`serve`/`recall`/`reconcile` process can still have an ordinary SQLite connection
open while another process acquires the reset lock, deletes the DB files, and
creates a fresh database.

If normal DB users do not participate in the lifecycle lock, the reset lock is
only a resetter mutex. It does not stop an existing process from continuing to use
an unlinked old SQLite database while the resetter creates the new one.

**Recommendation:** Make the reset guard a DB lifecycle lock, not just a reset
mutex:

- ordinary DB operations acquire a shared/read lock while opening and using a DB
  connection;
- destructive rebuild acquires an exclusive/write lock before deleting any DB
  artifact;
- all waits are bounded and fail loud on timeout.

If the implementation chooses strictly short-lived per-operation connections,
that lock can be held only for the operation duration. The important invariant is:
no process may delete/recreate `.qhaway.db*` while another qhaway process is using
an open connection to the old files.

### FFUP-2: Rebuild-on-`OperationalError` should be narrowly classified

**Severity:** Medium

The spec now bounds rebuild-on-drift to one attempt, which prevents infinite
loops. But the text still risks treating broad `sqlite3.OperationalError`
failures as schema drift. Some `OperationalError`s are not schema drift:
`database is locked`, permissions, disk I/O failures, malformed SQL, and other
runtime bugs. Rebuilding the derived DB once is not data loss, but it can mask the
real failure and introduce avoidable destructive file churn.

**Recommendation:** Rebuild automatically only on explicit drift signals:

- `PRAGMA user_version` mismatch;
- known SQLite schema errors such as missing expected table/column.

For `SQLITE_BUSY`, permission errors, I/O errors, and SQL syntax/query bugs, fail
loud without deleting DB files. Keep the once-only rebuild guard as a backstop,
but do not use it as the primary classifier.

## Minor Cleanup

The older "Fourth review (Gemini)" G-5 bullet still says all errors go to stderr
and exit non-zero. The later fifth-round TFUP-2 text corrects it, and the
architecture row is right, so this is not a blocking design issue. It would still
be cleaner to edit that historical bullet to say it was superseded by TFUP-2.
