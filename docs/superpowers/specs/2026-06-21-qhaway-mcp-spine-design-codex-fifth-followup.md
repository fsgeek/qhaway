# Fifth Follow-Up Review: Qhaway MCP Spine Design

**Date:** 2026-06-21
**Target spec:** `2026-06-21-qhaway-mcp-spine-design.md`
**Reviewer:** Codex
**Status:** Follow-up after fifth spec update

The latest update resolves FFUP-2 substantively: rebuild now fires only on true
schema drift (`user_version` mismatch or missing expected table/column), and
non-drift `OperationalError`s fail loud without deleting DB files.

FFUP-1 is not fully fixed, but it is now explicitly accepted as an MVP residual
race with the future DB-lifecycle-lock fix named. That is a clear product
decision rather than a hidden design hole.

One stale test criterion remains.

## Finding

### FIFUP-1: Rebuild-loop test contradicts the narrowed rebuild trigger

**Severity:** Medium

Testing criterion 31 still says:

> an operation that raises `OperationalError` from a persistent code bug (not
> schema drift) triggers **at most one** rebuild, then fails loud

That conflicts with the updated backend rule and criterion 26, which correctly
say non-drift `OperationalError`s, including malformed queries and code bugs,
fail loud and **do not delete/rebuild** the DB.

With FFUP-2 accepted, a persistent query bug should trigger zero rebuilds, not one.
The once-per-session guard should apply only after a true-drift rebuild has
already been selected by the classifier.

**Recommendation:** Rewrite criterion 31 to test the once-only guard using a true
drift signal whose rebuild still fails, for example:

- stale `user_version` triggers one rebuild attempt;
- the rebuilt DB still lacks an expected schema element or the same drift check
  fails again;
- qhaway fails loud after exactly one rebuild attempt and does not loop.

Keep criterion 26 as the test for non-drift `OperationalError`s causing zero
rebuilds.
