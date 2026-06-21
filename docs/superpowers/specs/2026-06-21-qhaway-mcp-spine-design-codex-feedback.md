# Review Feedback: Qhaway MCP Spine Design

**Date:** 2026-06-21
**Target spec:** `2026-06-21-qhaway-mcp-spine-design.md`
**Reviewer:** Codex
**Status:** Completed review

This is a second-pass review. The existing Gemini feedback file appears to have
been incorporated into the design as F-1 through F-7, so this review focuses on
remaining implementation hazards, internal contradictions, and missing acceptance
criteria.

## Findings

### C-1: `project_slice` return type conflicts with the regression guard

**Severity:** High

The spec says the internal `project_slice` API changes from returning `str` to
returning `(markdown: str, overflow: OverflowMeta)`. The same spec later says the
existing `tests/test_qhaway.py` suite must pass unchanged after the SQLite port.
Those cannot both be true: existing tests and CLI code treat `project_slice(...)`
as a string.

**Recommendation:** Preserve `project_slice(...) -> str` as the stable public
Python API and add a sibling API such as `project_slice_with_overflow(...) ->
ProjectionResult`, or explicitly amend the regression guard to allow API-test
updates for this one intentional signature change. The lower-risk path is the
sibling API because it keeps the MVP contract intact while still carrying overflow
metadata for MCP internals.

### C-2: The SQLite port still names `DESCRIBE`, which SQLite does not support

**Severity:** High

The design says to port `project.py` to SQLite using "plain `SELECT`/`DESCRIBE`,
no DuckDB-specific syntax." `DESCRIBE nodes` is DuckDB syntax, not SQLite syntax.
The current `project.py` depends on it to discover columns.

**Recommendation:** Specify the SQLite introspection mechanism now: either use
`PRAGMA table_info(nodes)` or execute a `SELECT ... FROM nodes` and use
`cursor.description`. If the backend is meant to stay swappable, hide this behind
one model-layer helper such as `fetch_nodes(conn) -> list[dict]` so projection is
not coupled to backend-specific schema inspection.

### C-3: `recall` can start stale or empty unless `serve` reconciles on startup

**Severity:** High

The design makes `recall` a pure read and says it trusts the startup hook and
`remember`. That is correct per-call behavior, but the architecture table only
says `qhaway serve` launches the MCP server; it does not say the server performs
an initial `reconcile(memory_dir)`. A user can start the MCP server with no prior
hook run, after deleting `.qhaway.db`, or after editing topic files by hand. In
those cases the first `recall` reads a missing or stale index even though the tool
appears available.

**Recommendation:** Add a server-lifecycle rule: `qhaway serve` runs exactly one
`reconcile(memory_dir)` before registering or accepting MCP tool calls. Keep the
`recall` tool itself pure after startup. Add an acceptance test where `.qhaway.db`
does not exist, `qhaway serve` starts, and the first `recall` returns the current
corpus.

### C-4: Concurrent `remember` calls can race on slug allocation and DB reconcile

**Severity:** High

The spec says slug collision produces a numeric suffix and never overwrites an
existing topic file, but it does not define an atomic allocation mechanism. Two
MCP `remember` calls with the same title can both observe that `foo.md` or
`foo-2.md` is free and then race to write it. Similarly, multiple `reconcile`
callers can overlap across server, hook, and manual CLI processes.

**Recommendation:** Require atomic topic creation with `O_CREAT|O_EXCL` (or
equivalent exclusive create) inside the suffix loop. For the database, set
`PRAGMA busy_timeout`, run reconcile in a transaction, and define whether
overlapping reconcile calls serialize, retry, or fail with a clear error. Add a
process-level test that launches two same-title `remember` calls and asserts that
two distinct files are created with no lost body.

### C-5: Incremental reconcile needs a transaction boundary

**Severity:** High

Reconcile is specified as a sequence of node upserts, edge delete/insert
refreshes, node deletions, and redirect maintenance. Without a transaction,
`recall` can observe a half-updated index, and a crash can leave nodes refreshed
without their edges or deleted files without the full cleanup. WAL improves
reader/writer behavior, but it does not by itself make a multi-statement reconcile
atomic.

**Recommendation:** Specify `BEGIN IMMEDIATE` or an equivalent write transaction
around the database portion of reconcile, with commit only after all node/edge
changes succeed. Keep the MEMORY.md redirect write outside or after the DB commit,
because the redirect is derived and can be healed on the next run. Add a failure
injection test that raises between edge delete and edge insert, then verifies the
prior committed index remains readable.

### C-6: The read-only fence is weaker than the design claims

**Severity:** Medium

The fence section says defeating a 0444 `MEMORY.md` requires `chmod`. That is true
for direct `open(..., "w")`, but any process that can write the directory can
replace the file via temp-file-plus-rename, exactly the same mechanism qhaway uses.
Many editors and file-writing helpers use atomic replacement by default. So 0444
is a useful friction signal, but it is not a reliable barrier against generic file
write tooling.

**Recommendation:** Downgrade the guarantee in the spec from "must run chmod" to
"direct writes fail; atomic replacement may still bypass the fence." Expand the
spike to test both direct open and temp-file rename from an unprivileged process.
If stronger enforcement is needed later, it belongs in step 2's observability or
intercept layer, not in chmod alone.

### C-7: New installs and empty memory directories are underspecified

**Severity:** Medium

The current CLI refuses to index a directory with zero topic files. The spine,
however, introduces `init` as first `reconcile`, a persistent empty DB, a redirect
MEMORY.md, and `recall` where an empty result is valid. Those are product-critical
for a fresh install before the first `remember`.

**Recommendation:** Specify that `qhaway reconcile`/`init` succeeds on an empty
memory directory: it creates an empty schema, writes the redirect, writes sidecar
state, and returns success. Keep the old "low topic count" warning for `--check`
if desired, but do not block init. Add a test for `init` on an empty dir followed
by `remember` and then `recall`.

### C-8: WAL creates sidecar files that also need explicit exclusion

**Severity:** Medium

The spec says `.qhaway.db` is gitignored and excluded from `topic_files`.
SQLite WAL mode also creates `.qhaway.db-wal` and `.qhaway.db-shm`. They will not
be picked up by the current `*.md` topic scan, but they still need to be kept out
of git, packaging examples, cleanup commands, and any future broader file scan.

**Recommendation:** Name all SQLite artifacts in the spec and templates:
`.qhaway.db`, `.qhaway.db-wal`, and `.qhaway.db-shm`. Add them to the generated or
documented `.gitignore` guidance. If qhaway ever offers a reset command, it should
remove all three.

### C-9: Sidecar hash behavior for a matching redirect but missing sidecar is not defined

**Severity:** Medium

Reconcile skips the redirect write when MEMORY.md already matches the template,
and (D) compares MEMORY.md against the hash recorded in `.qhaway.json`. The spec
does not define what happens when MEMORY.md already equals the redirect but the
sidecar is missing, corrupt, or from an old version. A naive implementation would
see "no recorded hash" and preserve the perfectly valid redirect as a
`MEMORY-<ts>.md` orphan.

**Recommendation:** Add an idempotence rule: if MEMORY.md bytes equal the current
redirect template, reconcile updates or repairs `.qhaway.json` without preserving
MEMORY.md as a hand edit. Preserve only when MEMORY.md differs from both the
recorded last output and the current template.

### C-10: MCP error handling should not return successful error strings

**Severity:** Medium

The error-handling section says `remember` should "return an error string" on
failures. For an MCP tool, a returned string is normally successful tool output;
it can be mistaken for a confirmation by the model. That weakens the "fail loud"
rule.

**Recommendation:** Specify structured MCP failures for tool errors and reserve
string returns for successful confirmations or rendered markdown. The CLI should
still use stderr plus non-zero exit codes. Tests should assert that invalid type,
unreadable directory, DB failure, and write failure are surfaced as tool errors,
not success strings containing error prose.

### C-11: `links` normalization is too loose for a low-friction write path

**Severity:** Low

`remember(links=[...])` is described as accepting wikilink slugs and appending
`[[slug]]` text, but the accepted input shape is not pinned. Models will likely
send a mix of stems, filenames, titles with spaces, and already-bracketed
wikilinks. If those are written verbatim, the derived edges can be inconsistent
or fail `--check` even though the target exists.

**Recommendation:** Define a small normalization contract for `links`: strip
`[[...]]`, strip `.md`, reject path separators, slugify spaces to hyphens using
the same slug rules as `title`, and preserve only canonical stems in the emitted
wikilinks. Add tests for `links=["Foo Bar", "foo-bar.md", "[[foo-bar]]"]`.

## Open Questions

1. Is the architecture note's "database is the source of truth" intentionally
   superseded by this spec's "files stay the source of truth"? The current spec
   says it builds on that note, but the write-path truth model is different.
   A short "supersedes the db-truth part of the note" paragraph would prevent
   future implementers from reopening the argument.
2. What is the memory directory discovery mechanism for MCP? The tool signatures
   omit `memory_dir`, but `reconcile(memory_dir)` requires it. The design should
   pin whether `qhaway serve --dir ...`, an environment variable, or config file
   supplies the directory.
3. Should `qhaway index` remain as "write a full projected MEMORY.md" for
   backward compatibility, or become an alias for redirect-writing reconcile?
   The design says existing `index` keeps working while also saying MEMORY.md
   becomes only a redirect. Those modes need distinct names or an explicit
   compatibility story.

## Summary

The core design is coherent: files remain authoritative, SQLite WAL is a better
fit than DuckDB for this workload, and the MCP surface is appropriately small.
The main changes needed before implementation are API compatibility around
`project_slice`, startup freshness for `serve`, SQLite-specific introspection,
transaction/concurrency rules, and a more precise statement of what the read-only
fence can and cannot enforce.
