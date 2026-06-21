# Qhaway MCP spine — Design

**Date:** 2026-06-21
**Status:** Drafted for review (brainstormed collaboratively with Tony)
**Builds on:** `2026-06-20-qhaway-mvp-design.md` (the truncation cure) and
`docs/architecture-note-2026-06-20-db-is-truth-tools-are-product.md` (the
inversion: the instance lives in the database through MCP verbs).

## The goal (the only success criterion)

A package someone installs after which **Claude Code benefits from a better
MEMORY.md management system** — its memory stops being silently truncated, and the
instance has a low-friction way to read and write memory. The deliverable is not
"the verbs exist"; it is "a Claude Code instance reaches its memory through tools
instead of by hand-writing files, and boots a complete self."

## Sequence (Tony's dependency order — this spec is step 1 only)

1. **Get the MCP working** — the verbs exist and function over the existing
   pipeline. *(This spec.)*
2. **Confirm we can incent Claude to use it** — measured, not asserted. A gate,
   not a checkbox: it can fail. *(Later.)*
3. **Package for redistribution** — only once 1 and 2 are real. *(Later.)*

Building 2 or 3 now would repeat the inversion the architecture note caught:
ranking the basement above the front door. Step 1 is the front door.

## What already exists (do not rebuild)

The truncation cure is built and verified: `parse.py` → `model.py` (the index
`nodes`/`edges`) → `project.py` (`project_slice`: budgeted, faceted, declared
omissions, idempotent) → `cli.py` (`qhaway index` with (D) edit-preservation,
`--check`, `--dry-run`, `--budget`, facet flags). The package builds (`uv_build`,
entry point wired). **The new work is: a thin MCP layer (two verbs), one shared
`reconcile` operation (incremental index sync + self-healing read-only redirect),
two new `nodes` columns (`mtime_ns`, `size`) to make reconcile cheap, and a
backend swap from DuckDB to stdlib SQLite (WAL) — not a new source of truth.**
`parse.py` and `project.py` are reused (port `project.py`'s SQL to SQLite —
plain `SELECT` + a `fetch_nodes` introspection helper, not DuckDB's `DESCRIBE` —
see C-2); `model.py` is reworked for
SQLite + incremental upsert; `cli.py` is extended.

### Backend: DuckDB → SQLite (WAL), persistent and co-located

The MVP used embedded DuckDB with an ephemeral `:memory:` db rebuilt each run. The
spine's incremental reconcile needs the index to **persist between invocations**
(startup hook, MCP server, manual CLI are separate processes), which surfaced two
decisions:

- **SQLite, not DuckDB.** The workload is tiny, read-mostly, single-row writes —
  SQLite's home turf, not DuckDB's (we use none of DuckDB's columnar/analytic
  strengths; the MVP defers FTS). SQLite is **stdlib** (drops a dependency —
  on-thesis for "propagates because it's small") and **WAL mode** gives concurrent
  readers + one writer without readers blocking, which fits "MCP `recall` reads
  while a hook/CLI writes" far better than DuckDB's single-writer model. This is
  the swappable-backend seam (above) exercised early and toward stdlib.
- **WAL is required, not best-effort (G-2 — MVP filesystem limitation).** WAL needs
  a shared-memory file (`-shm`/`mmap`), which fails on some network mounts (NFS/SMB),
  certain Docker/VM shared folders, and similar. qhaway **requires WAL and fails loud
  with a clear message** if it cannot initialize ("memory dir is on a filesystem that
  doesn't support SQLite WAL; move it to local storage") — it does **not** silently
  fall back to a rollback journal. A silent fallback would give *different concurrency
  semantics per filesystem*, invisible until a concurrency bug bit only on the
  fallback platform — the exact hidden-two-modes divergence this project kills
  everywhere. One mode, one named limitation. Wider filesystem support is a deliberate
  future-version expansion, not an MVP silent-degrade.
- **Persistent, co-located:** the index lives at `<memory_dir>/.qhaway.db`
  (gitignored; excluded from `topic_files` alongside `MEMORY.md`/`MEMORY-*`/
  `.qhaway.json`/`.qhaway.db-wal`/`.qhaway.db-shm`/`.qhaway.db.reset.lock` — U2-1).
  The index belongs *with* what it indexes: each project's memory
  dir is a self-contained unit (files + index + redirect + sidecar), so the
  multi-project reality (governance, yanantin, hamutay each have separate memory)
  Just Works — separate dirs, separate co-located indexes, no global
  project→db registry to drift. **Rebuildable by deletion — but delete all three WAL
  files together (G-1):** `rm -f .qhaway.db .qhaway.db-wal .qhaway.db-shm`, then the
  next reconcile rebuilds from the files (files remain the source of truth). Deleting
  only `.qhaway.db` can leave a stale `-wal` that SQLite recovers from on next open →
  corruption/lock. Any reset helper qhaway ships must remove all three.
- **Schema drift self-heals from files — rebuild ONLY on true drift, AT MOST ONCE
  (G-3 + U-1 + FFUP-2).** The schema carries a `PRAGMA user_version`. The destructive
  rebuild (close, delete all three db files, rebuild from topic files — no migration
  tooling, because the db is a derived view) fires **only on explicit drift signals:**
  a `user_version` mismatch, or a known schema error (missing expected table/column).
  **All other `OperationalError`s — `database is locked`, permission, disk I/O, malformed
  SQL, query bugs — fail loud WITHOUT deleting anything** (FFUP-2): they are not drift,
  and rebuilding on them would mask the real fault and churn files destructively. Even
  on a true-drift rebuild, the attempt is **once per session** (`_rebuilt` flag); a
  second failure of the *same* op after a rebuild is a code bug → fail loud, no second
  rebuild (U-1). Net: rebuild is rare and narrowly triggered, never a disk-thrashing
  loop, never a mask for an ordinary error.
- **Destructive rebuild takes a resetter lock (TFUP-1).** Because the destructive path
  deletes/recreates files, two concurrent *resetters* would race; it acquires
  `.qhaway.db.reset.lock` via `fcntl.flock(LOCK_EX|LOCK_NB)` in a bounded retry loop
  (≈5 s, fail loud on timeout; do not delete the lock file after release — that races
  other openers) — U2-2. This is NOT a general mutex (declined in C-4); only the rare,
  now-drift-only reset is guarded. A long-running `serve` that detects drift reopens
  through this path rather than holding an obsolete connection.
- **Residual race — named, deferred, not an MVP problem (FFUP-1).** The resetter lock
  serializes two resetters but does not, by itself, stop an ordinary process with an
  *open* connection from reading an unlinked old db while a resetter rebuilds. Closing
  that fully needs a **DB-lifecycle lock** (ordinary ops take a shared lock, rebuild
  takes exclusive). We **deliberately do not build that for the MVP:** with transient
  short-lived connections (F-1/C-4), per-project single-user memory dirs, and rebuild
  now firing *only* on a schema-version upgrade (FFUP-2 — approximately never during
  normal use), the conditions to hit this race effectively cannot co-occur. Paying a
  shared-lock cost on every `recall`/`reconcile` to guard an upgrade-during-concurrent-
  access window is premature-collapse in concurrency-control form. The lifecycle lock is
  the **named future fix** if real multi-process contention ever appears; until then the
  residual race is a documented limitation, not a silent one.

### FTS escalation ladder (rationale — do not skip a rung the wrong way)

If prose search ever appears: **SQLite FTS5** is the no-dependency next step
(mediocre but stdlib — good enough to avoid a premature tier jump). **BM25-class
ranked retrieval is deliberately NOT a reason to move to Postgres** — because the
corpus that needs ranked retrieval also needs graph traversal, and that is the
**yanantin / ArangoDB fold** (ArangoSearch gives BM25-class ranking *and* graph in
one engine), reached via the swappable-backend seam, not a SQL-server upgrade.
Postgres is a rung this lineage likely *skips*. SQLite is the correct floor
*because* the ceiling is a different system, not a beefier SQL server. A future
chair tempted to "upgrade to Postgres for search" should reach for the Arango fold
instead.

## What qhaway is (rationale — keep this seam clean)

qhaway is the **index-service factoring of MEMORY.md**: the service the flat file
was always pretending to be. The duality — files author memories; an embedded SQL
index *derives* a queryable view; `[[wikilinks]]` live as text in files and become
edges only on rebuild — is **not a compromise to undo.** It is the normal shape of an index over
authoritative documents (every search engine has it; an index is *supposed* to be
derived and rebuildable).

Because files are truth and the index is derived, **the backend is swappable.**
DuckDB is a deliberate floor — sufficient for the one pain (truncation + facet
slice), weak at graph structuring. The day yanantin re-indexes this corpus in
ArangoDB, nothing in qhaway's contract breaks: same topic files, same `parse`, a
different `model`/`project` backend; links that are throwaway derived edges in
DuckDB become first-class AQL relations in Arango. **Therefore:** do not go
db-first in qhaway (it inverts source-of-truth and reinvents the Arango tier
badly); do not torture DuckDB into graph traversal. The way up is to swap the
backend, not thicken this one.

## Non-negotiable constraints (inherited + new)

1. **Files stay the source of truth.** Topic `.md` files are authoritative; the
   SQL index is *derived* from them and rebuildable at any time (the MVP rebuilt it
   from scratch each run; this spine reconciles it incrementally — same guarantee,
   cheaper path). `remember` writes a *file*; it never writes the db directly.
   (Inherits MVP constraint 1.)
2. **The judgment stays with the writing instance.** `remember` is **thin
   plumbing**: it removes mechanical ceremony (path, frontmatter syntax, slug,
   index step), NOT the classification decision (what `type`, what hook). A "fat"
   `remember` that infers type/title would offload the high-value act to a dumber
   layer — backwards. Rejected.
3. **No new write path to the db.** `[[links]]` are inter-file references stored as
   text in the topic file; the db derives edges on rebuild. The `links` argument
   only writes wikilink text. Forward-declared links (target file not yet written)
   are not errors — they are dangling links, surfaced by `qhaway check`.
4. **MEMORY.md is fenced read-only.** It is fully derived; nobody should hand-edit
   it. Fencing it channels the write reflex toward `remember`. Topic files stay
   writable (they are the write surface; a stray hand-written topic file is a
   *caught* event for step 2, not a blocked one).
5. **Two verbs only on the MCP surface.** `remember`, `recall`. No `search` (prose
   match is yanantin's tier); read-only inspection (`check`) and sync (`reconcile`)
   stay **CLI**, not MCP tools (SFUP-1). Every extra verb is friction before the
   tool feels usable.

## The MCP surface (the product)

Two tools. The *shape of the call* is the adoption thesis: one structured call vs.
path + frontmatter + index-edit.

```
remember(
  type:        "user" | "feedback" | "project" | "reference"   # required — the one judgment
  title:       str         # headline; becomes the slug → filename
  body:        str         # the memory itself
  description: str | None   # optional one-line hook; if omitted, derived from body's first line
  links:       [str] | None # optional [[wikilink]] slugs to related memories
) -> str    # confirmation: path written + topic count

recall(
  type:   "user"|"feedback"|"project"|"reference" | None   # omit = whole working set
  role:   str | None
  status: "live" | "superseded"  = "live"
) -> str    # the rendered, budgeted projection slice (same engine as the MVP projection)
```

### `remember` — write path

1. Compose a topic file from the args:
   - **Slugify `title` → filename stem using HYPHENS for spaces, never underscores**
     (F-2). `parse.py`'s `_role()` extracts `role` from the stem prefix before the
     first `_`, so `"Review feedback"` → `review_feedback.md` would silently set
     `role="review"` and pollute the role namespace. Hyphens (`review-feedback.md`)
     yield `role=None`; an explicit role is opt-in only by prepending `role_`
     (e.g. `instructions_review-feedback.md`). Lowercase, strip non-`[a-z0-9-]`,
     collapse repeats. Collision → `O_CREAT|O_EXCL` exclusive create with a numeric
     suffix; never overwrite an existing topic file. **The suffix loop is hard-capped
     (e.g. 100 attempts) and fails loud** if it can't allocate a unique name (G-7) —
     no `while True` that could hang on a locked/full directory. (Mirrors the existing
     `_backup_path` cap in `cli.py`.)
   - **Emit frontmatter via `yaml.safe_dump`, not string concatenation** (F-4).
     `title`/`description` are model-generated freeform strings; a colon, quote, or
     newline would corrupt raw-concatenated frontmatter (and `parse.py` would fall
     to its tolerant parser and mangle it). Safe-dump `{name, type, description?}`
     so any special characters are correctly quoted/escaped.
   - Write `body`, then append `links` with a **clean boundary (G-6):**
     `body.rstrip()` + `"\n\n"` + one `[[slug]]` per line + a trailing newline — never
     joined onto the body's last sentence. All writes use explicit `encoding="utf-8"`
     (G-8).
2. Write the topic file (normal mode — topic files are the writable surface).
3. Call the shared `reconcile()` (see below) so the index reflects the new file
   within-session. Reconcile is incremental and cheap, so this is one changed
   file, not a full rebuild.
4. **Does NOT itself rewrite MEMORY.md content** beyond what `reconcile`'s
   self-healing template step does (which, for a near-static redirect, is a no-op
   most calls).
5. Return a confirmation string (path + current topic count).

### `recall` — read path

1. **No reconcile, no rebuild — a pure read.** It trusts the index left fresh by
   the startup hook and by `remember` (both of which call `reconcile`).
2. `project_slice(facets)` — the *existing* engine, unchanged. `recall()` with no
   facet returns the whole budgeted working set (the same projection the MVP would
   have written to MEMORY.md); with a facet, the drill-down slice.
3. Return the rendered markdown. **Writes nothing.** No file, no fence, no (D).

This is where `project_slice` now lives: `recall` is the projection engine exposed
as a verb. When MEMORY.md became a redirect, the projection did not become
orphaned — it moved from "what writes MEMORY.md at boot" to "what `recall` returns
on demand."

### `recall` overflow — structured now, dynamic-banding later

**API contract (F-7 + C-1) — separate the Python API from the MCP tool.** The
existing `project_slice(...) -> str` is **unchanged** (stable MVP API; the
regression suite keeps treating it as a string). A **sibling**
`project_slice_with_overflow(...) -> ProjectionResult` returns a structured pair
`(markdown: str, overflow: OverflowMeta)`, where `overflow` carries
per-dynamic-facet counts (`origin_session`, `date_hint`) of the omitted set; it is
what the MCP path calls. The **MCP `recall` tool returns only the markdown string**
(the rendered slice, including the flat "+N not shown" footer); it discards
`overflow` in v1. This computes and carries the band data at the Python layer so
the **designed-in first enhancement** (dynamic temporal banding) changes only how
`recall` *renders* `overflow`, not whether it is *available*. (YAGNI-clean: the
omission counts are already computed to render the footer; returning them as a
structured value alongside the string is near-free, not speculative machinery.)
The string return keeps the tool surface simple; the structured value lives one
layer down, ready.
Dynamic banding itself is **deferred** — it is a good idea wearing the costume of
a now idea, and shipping it in v1 would betray the thesis that the small slice
propagates *because* it is small. Not in the spine; not before shipping v1.

## MEMORY.md is a redirect (the truncation cure, completed)

The MVP cured truncation by *projecting the index under budget*. This spine cures
it more fundamentally: **MEMORY.md stops being the index.** It becomes a small,
stable **redirect** — "your memory lives in a database; read it with `recall`,
write it with `remember`" (plus an optional tiny always-loaded bequest). Because
it is small and bounded by construction, it cannot truncate. Because it is
near-static, (D) almost never fires and orphan-accretion nearly vanishes.

- **We own MEMORY.md.** It is the artifact qhaway authors, fences, and injects the
  redirect into. That ownership is the reason MEMORY.md is treated differently from
  topic files everywhere in this design (see `reconcile`'s hash-vs-stat asymmetry).
- Its content is the redirect template, born **read-only** (see the fence + spike)
  and swapped in atomically.
- It is maintained by `reconcile` (below), which **self-heals** it: every reconcile
  ensures MEMORY.md *is* the template — if it drifted, was corrupted, or was hand
  edited, reconcile preserves the prior bytes via (D) and rewrites the template.
  `qhaway init` is simply the first `reconcile`; there is no separate init-only
  write path.

## `reconcile()` — the one shared sync operation (deterministic, no LLM)

The startup hook and the MCP need the *same* "bring the index in line with disk and
ensure MEMORY.md is correct" operation. Two implementations would drift — "is my
index correct?" would depend on which path last ran, which is the exact
silent-divergence disease this project exists to cure, reappearing in our own
plumbing. **Therefore there is one function, `reconcile(memory_dir)`, and every
caller uses it. Never two ways to do the one operation.**

`reconcile` is **incremental and cheap** so it can run on every startup and after
every `remember` without thought:

1. **Topic files — stat, don't checksum.** The `nodes` table stores each file's
   `(mtime_ns, size)`. Reconcile does **one** query — `SELECT file, mtime_ns, size
   FROM nodes` — into a Python dict, then stats every topic file and compares
   **in-memory** (F-5: O(1) per file, not a DB roundtrip per file). Per file:
   `(mtime_ns, size)` unchanged → skip (trust the existing row); changed or new →
   re-parse and upsert the node *and* refresh its edges (delete-then-insert its
   `edges` rows); in-db-but-gone-from-disk → drop the node **and** `DELETE FROM
   edges WHERE src_file = ?` (F-6: never leave orphaned edges, which would corrupt
   `qhaway check`'s dangling-link detection). Most session-starts change nothing, so
   reconcile is a stat sweep + one small query — near-instant.
   - **Timestamps are integer nanoseconds** (`path.stat().st_mtime_ns`, stored
     `INTEGER`/`BIGINT`), not float seconds (F-3): the skip test is an *equality*
     check, and float round-trip risks spurious re-parses across OS/filesystems.
   - **Deliberate limit (declared, not hidden):** `(mtime_ns, size)` cannot detect a
     content edit that preserves *both* (e.g. a same-length in-place swap, or a tool
     that restores mtime). Detecting it would require reading + hashing every file
     every reconcile, defeating cheapness. We **accept this corner on purpose** and
     reserve the escalation — checksums, and/or async/background re-hashing — for
     *if it becomes a real observed problem*, not a speculative one. This is the
     project's anti-premature-collapse principle applied to its own plumbing.
2. **MEMORY.md — hash, because we own it.** MEMORY.md keeps the content-hash (D)
   check (hash ≠ recorded → preserve to `MEMORY-<ts>.md`). The asymmetry is
   intentional and ownership-based: **hash the one file we own and author; stat the
   many we don't.** Hashing one derived file is cheap; the no-checksum rule is about
   the *corpus scan*, not this single artifact.
3. **Ensure the redirect.** Write MEMORY.md as the redirect template, born
   read-only, atomic-swapped (the self-healing step above). A no-op write is
   skipped when the on-disk redirect already matches the template (idempotence —
   keeps (D) from firing on our own output).

**Callers:** startup hook = `reconcile(dir)` (a four-line script — cross-session
disk→index reconciliation; catches direct file edits and a hand-edited MEMORY.md,
and heals the template). `remember` = write topic file, then `reconcile(dir)`.
`recall` = **no reconcile** (pure read; trusts the hook + `remember` to have kept
the index fresh). Topic-file hand-edits need *no* special handling beyond the stat
sweep — editing a topic file is legitimate (files are the write surface); only
MEMORY.md, which we own, gets preserve-before-overwrite.

## The read-only fence (and the spike that must precede it)

The fence makes the *reflexive* hand-edit of MEMORY.md fail: a direct
`open(MEMORY.md, 'w')` / `Edit` on a 0444 file raises PermissionError, so the
cheap reach for the file is blocked and `remember` sits right there offering one
call instead. **Honest scope (C-6): 0444 is a friction signal, not a barrier.**
qhaway's own writer uses temp-file + `rename` (write on the *directory*, not the
file), so any atomic-replacement tool can bypass the fence *without* `chmod` — the
guarantee is "direct writes fail; atomic replacement may still bypass," not "must
run chmod." That is sufficient for the adoption thesis (it removes the *reflexive*
easy path), and real enforcement — if step 2's measurement shows it is needed —
belongs in the observe/intercept layer, not in chmod. The fence handles the
stubborn *write* reflex; the redirect
handles the *read* (to know what it knows, the instance must call `recall`), and
the read is what builds the habit through use.

**Mechanism — atomic replace of a born-read-only file:**
- Write the new content to a temp file *created read-only*: open with
  `O_CREAT|O_WRONLY` mode `0o444` (or `open('w')` then `fchmod(fd, 0o444)`) — the
  open file description already holds write permission, so writes through the
  existing fd succeed even though the on-disk mode is read-only (POSIX: mode is
  checked at `open()`, not per-`write()`).
- `os.replace`/`shutil.move` the temp over `MEMORY.md` — `rename` is the atomic op
  and needs write on the *directory*, not the target, so it lands cleanly. No
  writable window ever exists for a reader or torn write to catch.

**SPIKE (must run before building on this):** a short script confirming, on this
Linux box, that (a) writing through an fd to a 0444-mode file succeeds, and (b)
`os.replace` of a 0444 temp over an existing 0444 `MEMORY.md` succeeds — **and**
(c, per C-6) characterizing the bypass: that a temp-file + `rename` from an
unprivileged process *does* replace the 0444 file (confirming the fence is a
friction signal, not a barrier) while a direct `open(...,'w')` *fails*. (a)/(b) are
filesystem-edge assumptions — verify, do not trust. If (a) or (b) fails, fall back
to write-temp-0644 → replace → `chmod 0444` (a tiny writable window, acceptable
because MEMORY.md is regenerable). The (D) edit-preservation logic is reused
unchanged; only the final write becomes the read-only swap. The write helper lives
in `reconcile`, so fence + (D) behave identically for every caller (startup hook,
MCP, CLI).

## Architecture

| Unit | Purpose | Depends on |
|---|---|---|
| `server.py` (new) | MCP server exposing `remember` + `recall`. Thin: validates/composes args; `remember` writes a file then `reconcile`; `recall` calls `project_slice_with_overflow` and returns the markdown. Success → string; failure → **structured MCP error** (C-10). **stdout discipline, split by phase (G-5 + TFUP-2):** *Before* serving starts (init, dir resolution) — all diagnostics → `stderr`, exit non-zero on fatal failure; stdout untouched. *After* serving starts — stdout carries **only** JSON-RPC frames, and a tool-call failure is returned as an **in-band structured MCP error on stdout** (C-10), never a stderr-only log and never a server crash; stderr is for logs/traces that must not replace the in-band error. | reconcile, project, parse |
| `reconcile.py` (new) | The one shared sync op: incremental `(mtime_ns,size)` topic reconcile (bulk-load db state, in-memory compare, upsert+edge-refresh changed, cascade-delete gone) + (D)-checked, born-read-only, self-healing MEMORY.md redirect. Houses the born-read-only atomic-replace helper and the `remember` hyphen-slugify / safe-YAML composer. | model, parse, project |
| `cli.py` (extend) | Add `qhaway reconcile` (startup-hook entry; `init` is the same op on an empty dir), `qhaway serve` (launch MCP server; **reconciles once at startup**, C-3; resolves the memory dir via the tiered chain, OQ-2), and **`qhaway check`** (read-only inspection: dangling links, would-overflow, orphan `MEMORY-<ts>.md` count — SFUP-1). `index` becomes a **deprecated alias for reconcile** (OQ-3); `index --check` becomes a thin deprecated alias for `check` (one release, then removed). One write path; MEMORY.md always the redirect. | reconcile, server |
| `model.py` (rework) | **DuckDB → SQLite (WAL, required — G-2).** Add `mtime_ns` + `size` columns to `nodes`; `PRAGMA user_version` + rebuild-on-drift (G-3). `edges` gets `PRIMARY KEY (src_file, dst_slug, kind)` + `INDEX(dst_slug)` (G-4 — dedups edges, O(log N) lookup for the C-6 delete and `check` scan; **no FK cascade** — redundant with reconcile's explicit edge delete and guards an architecturally-impossible path). Incremental upsert/delete in a `BEGIN IMMEDIATE` transaction (C-5), `PRAGMA busy_timeout = 5000` on every connection (C-4/U-2), `fetch_nodes(conn)` introspection (C-2), persistent connection factory for `<memory_dir>/.qhaway.db`. All SQL uses `?` parameter bindings, never string interpolation (U-4 — matches existing `model.py`). All file I/O explicit `encoding="utf-8"` (G-8). | sqlite3 (stdlib), parse |
| `project.py` (port) | SQL ported to SQLite via `fetch_nodes` (no `DESCRIBE`, C-2). `project_slice(...) -> str` **unchanged** (stable MVP API, C-1); new sibling `project_slice_with_overflow(...) -> ProjectionResult` carries `(markdown, overflow)` (F-7) for the MCP path. | sqlite3 (stdlib) |
| `parse.py` | **Unchanged.** Reused wholesale. | — |

## Data flow

```
startup hook  →  reconcile(dir)
  open <dir>/.qhaway.db (WAL) → one query: load {file: (mtime_ns,size)} →
  stat topic files, compare in-memory → upsert+edge-refresh changed/new,
    cascade-delete gone → (D)-check + self-heal MEMORY.md redirect (born RO, atomic)

remember(type,title,body,...) →
  compose topic file (hyphen-slug, safe-YAML frontmatter, links) → write topic .md →
  reconcile(dir) → return confirmation

recall(facets?) →
  project_slice_with_overflow(facets) -> (markdown, overflow) → return markdown  [pure read]
```

## Error handling

Fail loud, never silently — and (C-10) **MCP tool failures are structured tool
errors, never success strings.** A returned string from an MCP tool is normal
*successful* output; an error returned as a string can be mistaken for a
confirmation, defeating "fail loud." So `remember`/`recall` **raise/return a
structured MCP error** on: slug collision that can't be resolved, unreadable memory
dir, DB failure, write failure. Invalid `type` (not in the four) is rejected at the
tool boundary (the schema enum), not coerced. String returns are reserved for
*success* (a `remember` confirmation, a `recall` rendered slice). An empty `recall`
result is a valid empty slice, not an error. The CLI surface uses stderr + non-zero
exit (not tool errors). The fence: if the read-only swap fails, surface it — atomic
replace guarantees all-or-nothing, so MEMORY.md is never left half-written.

## Testing (TDD — falsifiable criteria)

1. **`remember` writes a well-formed topic file** parseable by `parse.py` into a
   node with the given `type`, title-derived name, and body; the file lands in the
   memory dir; the slug is filesystem-safe.
2. **Slug collision never overwrites:** two `remember` calls with the same title
   produce two distinct topic files; neither is lost.
3. **`remember` does not rewrite MEMORY.md content:** across a `remember` call
   MEMORY.md stays the redirect template (reconcile's template step is a no-op when
   it already matches); the topic file and db index are what change.
4. **`remember` links become edges:** a `remember(links=[...])` call writes
   `[[slug]]` text such that a subsequent `reconcile` produces the corresponding
   edges; a link to a nonexistent slug is surfaced by `qhaway check`, not swallowed.
5. **`recall()` returns the budgeted working set** — byte-identical to what
   `project_slice` produces for the same corpus; under budget; declared omissions
   present.
6. **`recall(facet)` returns the drill-down slice** for each of `type`/`role`/
   `status`, matching `project_slice` with the same arguments.
7. **`recall` writes nothing and does not reconcile:** no file in the memory dir is
   created or modified by a `recall` call; it is a pure read of the current index.
8. **`recall` overflow carries structured band info:** when a slice overflows,
   `project_slice_with_overflow` returns `(markdown, overflow)` where `overflow`
   includes per-`origin_session`/`date_hint` counts of the omitted set; the MCP
   `recall` returns the markdown string and the footer is present (F-7/C-1).
9. **Born-read-only swap (gated on the spike):** after `qhaway reconcile`/`init`,
   MEMORY.md is mode 0444 and contains the redirect; a hand `open('w')` on it raises
   PermissionError; reconcile run again still succeeds (the tool is the one writer
   that gets through, via atomic replace).
10. **Redirect cannot truncate:** the redirect is well under budget by construction
    (assert its size against the budget with wide margin).
11. **Shared write path preserves (D):** a `reconcile` over a hand-edited MEMORY.md
    preserves the prior bytes to `MEMORY-<ts>.md` before writing the redirect —
    identical behavior to `cli.py`'s existing preservation.
12. **Incremental reconcile skips unchanged files:** given a corpus already indexed,
    a second `reconcile` with no file changes re-parses **zero** topic files (assert
    via a parse spy/counter), proving the `(mtime_ns, size)` skip works — and still
    produces a correct, byte-identical index.
13. **Reconcile catches a changed topic file:** touching one topic file's content
    (changing its `(mtime_ns, size)`) causes exactly that node to be re-parsed and
    its new content to appear in a subsequent `recall`; deleting a file drops its
    node.
14. **Reconcile is idempotent on its own output:** two consecutive `reconcile` runs
    with no changes create **zero** new `MEMORY-<ts>.md` files (the template write is
    skipped when already matching) — the (D)/idempotence guarantee the MVP pins,
    preserved through the shared path.
15. **Hyphen slug never auto-derives a role (F-2):** `remember(title="Review
    feedback")` writes a stem with no `_`, so `parse.py` yields `role=None` — not
    `role="review"`. A multi-word title cannot pollute the role namespace.
16. **Frontmatter survives hostile strings (F-4):** `remember` with a `title`/
    `description` containing `:`, quotes, and a newline produces a file that
    `parse.py` reads back with those exact values intact (safe-YAML round-trip), not
    a tolerant-parser mangle.
17. **Node deletion leaves no orphaned edges (F-6):** after a linked topic file is
    deleted and reconciled, `edges` has zero rows with that `src_file`; `qhaway check`
    reports no spurious dangling links from the removed node.
18. **Persistent db survives across processes & rebuilds by deletion:** an index
    built in one process is read by a separate process via `recall` (persistence);
    `rm` of **all three** WAL files (G-1) followed by `reconcile` reproduces an
    equivalent index from the files (files remain truth). `.qhaway.db`/`-wal`/`-shm`
    are excluded from `topic_files` and gitignored.
19. **`serve` reconciles once at startup (C-3):** starting `qhaway serve` with no
    pre-existing `.qhaway.db` and then calling `recall` returns the current corpus —
    the server runs exactly one `reconcile` before accepting tool calls; `recall`
    stays pure thereafter.
20. **Concurrent same-title `remember` never loses a body (C-4):** two same-title
    `remember` calls produce two distinct files via `O_CREAT|O_EXCL` exclusive
    create; neither body is lost or overwritten.
21. **Reconcile is atomic under failure (C-5):** an injected failure between edge
    delete and edge insert leaves the *prior committed* index fully readable (the
    DB portion runs in one `BEGIN IMMEDIATE` transaction; partial state never
    commits).
22. **Valid redirect + missing sidecar is NOT preserved as an orphan (C-9):** when
    MEMORY.md bytes equal the current redirect template but `.qhaway.json` is
    missing/corrupt, reconcile repairs the sidecar and creates **zero**
    `MEMORY-<ts>.md` files.
23. **Empty-dir init succeeds (C-7):** `qhaway reconcile`/`init` on a directory with
    zero topic files creates the schema, writes the redirect, writes the sidecar,
    and returns success; a subsequent `remember` then `recall` round-trips.
24. **MCP failures are structured, not success-strings (C-10):** invalid `type`,
    unreadable dir, DB failure, and write failure surface as MCP tool *errors*, not
    as success results containing error prose.
25. **`links` normalize to canonical stems (C-11):** `links=["Foo Bar",
    "foo-bar.md", "[[foo-bar]]"]` all emit `[[foo-bar]]`; the resulting edges
    resolve under `qhaway check` when the target exists.
26. **Rebuild fires ONLY on true drift, not on any error (G-3 + FFUP-2):** a
    `.qhaway.db` with a stale `user_version` (or missing expected column) is detected
    and transparently rebuilt from topic files, matching a fresh build. Conversely, a
    non-drift `OperationalError` (e.g. `database is locked`, a malformed query) **fails
    loud and does NOT delete the db** — assert the db files survive and the error
    propagates.
27. **`edges` rejects duplicate references (G-4):** indexing a file that declares the
    same `[[slug]]` twice yields a single `edges` row (the compound PK dedups), and a
    node-drop + reconcile leaves zero edges for that `src_file` via the explicit C-6
    delete (no FK needed).
28. **Link append never joins onto prose (G-6):** `remember(body="last sentence",
    links=["x"])` produces a file whose body ends `last sentence\n\n[[x]]\n` — the
    link is on its own line, not concatenated to the sentence.
29. **Suffix loop is bounded (G-7):** with the unique-name space artificially
    exhausted, `remember` fails loud (tool error) after the hard cap rather than
    hanging.
30. **WAL-unavailable fails loud (G-2):** when WAL cannot initialize, qhaway exits
    with a clear stderr message and does **not** silently run on a rollback journal.
    *(Test as feasible — may be a unit test stubbing the PRAGMA failure rather than a
    real exotic filesystem.)*
31. **Rebuild-on-drift is bounded to once (U-1):** an operation that raises
    `OperationalError` from a *persistent code bug* (not schema drift) triggers **at
    most one** rebuild, then fails loud — it does not loop deleting/recreating the db.
    (Assert via a forced-failing query + a rebuild spy: exactly one rebuild, then the
    error propagates.)
32. **Destructive rebuild is serialized (TFUP-1):** the delete-all-three + rebuild path
    acquires `.qhaway.db.reset.lock`; a second process attempting a concurrent reset
    waits (bounded) or fails loud rather than forking a second live index. Normal
    (non-destructive) reconcile does **not** take this lock.

## Second review (Codex) — resolutions

A second adversarial pass (`...-codex-feedback.md`) found contradictions the first
missed. All findings accepted; resolutions pinned here (tests above):

- **C-1 — `project_slice` signature vs. regression guard (was self-contradictory).**
  `project_slice(...) -> str` stays the **stable engine API** — the retargeted cure
  tests (see "Regression guard", FUP-1) call it directly as a string. A **sibling**
  `project_slice_with_overflow(...) -> ProjectionResult` carries `(markdown,
  overflow)` for the MCP path. F-7's overflow metadata lives in the sibling; the
  string API is untouched. (Supersedes the earlier "amend the tests" wording. Note:
  the *CLI* `index` no longer calls projection-to-MEMORY.md — it is the reconcile
  alias, OQ-3 — so "stable API" here means the Python signature the tests target,
  not a CLI contract.)
- **C-2 — `DESCRIBE` is DuckDB-only.** `project.py` currently calls `DESCRIBE
  nodes`; SQLite has no `DESCRIBE`. Introspection moves behind one model-layer
  helper `fetch_nodes(conn) -> list[dict]` (using `PRAGMA table_info(nodes)` /
  `cursor.description`), so projection is decoupled from backend schema inspection —
  serving the swappable-backend goal directly.
- **C-3 — `serve` startup freshness.** `qhaway serve` runs **exactly one**
  `reconcile(memory_dir)` before registering/accepting tool calls. `recall` remains
  pure after startup.
- **C-4 — concurrent write safety.** Topic creation uses `O_CREAT|O_EXCL` inside the
  suffix loop (atomic exclusive create — no two callers can claim the same name).
  Overlapping reconciles serialize via SQLite's single-writer + `PRAGMA
  busy_timeout` + the C-5 transaction (second writer waits, then proceeds; or fails
  loud on timeout). **No separate cross-process lock** — this is a low-contention
  path (the hook runs once at boot; concurrent `remember`s are rare under the
  single-threaded MCP call model), and the redirect write is idempotent/self-healing
  (C-9), so there is nothing a mutex would protect that the transaction + repair rule
  does not.
- **C-5 — reconcile transaction boundary.** The DB portion of reconcile (node
  upserts, edge delete/insert, node deletes) runs inside one `BEGIN IMMEDIATE`
  transaction, committed only after all changes succeed. The MEMORY.md redirect
  write happens **after** the DB commit (it is derived and healable on the next run).
- **C-6 — fence guarantee, honestly downgraded.** 0444 makes a direct
  `open(...,'w')` fail, but qhaway's *own* write mechanism — temp-file + `rename` —
  needs write on the *directory*, not the file, so any atomic-replacement tool
  (many editors, `Write`-style helpers) bypasses the fence **without** `chmod`. The
  fence is therefore a **friction signal, not a barrier**: "direct writes fail;
  atomic replacement may still bypass." Real enforcement, if ever needed, is step 2's
  observe/intercept layer, not chmod. The spike must test **both** the direct-open
  and the temp-file-rename paths. *(This corrects an overclaim in the fence section:
  the adoption thesis must not lean on a guarantee the fence does not provide.)*
- **C-7 — empty-dir init.** `reconcile`/`init` succeeds on a zero-topic directory
  (fresh install before the first `remember`): create empty schema, write redirect,
  write sidecar, return success. The "low topic count" signal is a `qhaway check`
  *warning* only — it never blocks init/reconcile.
- **C-8 — WAL sidecar files.** WAL mode creates `.qhaway.db-wal` and `.qhaway.db-shm`
  beside `.qhaway.db`. All three are named in the generated `.gitignore` guidance and
  in any future reset/cleanup command. (They are not `*.md`, so `topic_files` already
  ignores them; this is about git/packaging/reset, not the scan.)
- **C-9 — matching-redirect-but-missing-sidecar.** Idempotence rule: **if MEMORY.md
  bytes equal the current redirect template, reconcile repairs `.qhaway.json`
  without preserving MEMORY.md.** Preserve as `MEMORY-<ts>.md` *only* when MEMORY.md
  differs from **both** the recorded last-output hash **and** the current template.
  (Closes a real bug: a valid redirect + lost sidecar would otherwise be orphaned.)
- **C-10 — MCP error surface.** Tool errors surface as **structured MCP failures**
  (raised/error results), never as success strings containing error prose (a model
  could mistake those for confirmations). String returns are reserved for success
  (confirmation / rendered markdown). The CLI still uses stderr + non-zero exit.
- **C-11 — `links` normalization contract.** `remember` normalizes each link
  through the **same hyphen-slug rules as `title`**: strip `[[...]]`, strip `.md`,
  reject path separators, slugify spaces → hyphens, emit only canonical stems. A
  forward-declared link (target not yet on disk) remains legal (surfaced by
  `qhaway check`), but it is a *canonical* stem, not raw model text.

### Open questions — resolved

- **OQ-1 — supersession.** This spec **supersedes the "database is the source of
  truth" framing** of `architecture-note-2026-06-20`. For qhaway: **files are the
  source of truth; the SQLite index is a derived, rebuildable view.** The note's
  db-truth language is aspirational for the *family* (the yanantin/ArangoDB tier);
  it does not govern this slice. Implementers should not reopen this — going db-first
  in qhaway reinvents the Arango tier badly (see "What qhaway is").
- **OQ-2 — memory-dir discovery (tiered chain).** The dir resolves by precedence:
  **(1)** `--dir <path>` flag → **(2)** `QHAWAY_MEMORY_DIR` env var → **(3)** config
  file default → **(4) fail loud.** Asymmetry by command: the human-facing CLI
  (`index`/`reconcile`) may keep `.`/cwd as the bottom rung (you are standing in the
  dir); **`serve` requires explicit resolution and fails loud if the chain is empty**
  — a server defaulting to cwd could index the wrong project's memory, the worst
  silent error for a memory tool. Never guess silently.
- **OQ-3 — `qhaway index` compatibility.** `index` becomes a **deprecated alias for
  reconcile** (redirect-writing). There is **one write path to MEMORY.md** and
  MEMORY.md is **always the redirect** — no second full-projection-into-MEMORY.md
  mode (two write paths is the divergence disease). The full-projection *logic* does
  not die: it is exactly what `recall` returns on demand. Only the
  MEMORY.md-as-full-index *output* is retired.

### Third follow-up (Codex) — resolved

- **SFUP-1 — `--check`'s CLI home after `index` became an alias.** `--check` is a
  **read-only inspection** (writes nothing: dangling links in topic bodies,
  would-overflow-before-projection, orphan `MEMORY-<ts>.md` count). It gets its own
  dedicated command: **`qhaway check --dir ...`** — keeping a clean line between
  *write* commands (`reconcile`) and *inspect* commands (`check`), and not tying a
  living feature to the dying `index` alias. `qhaway index --check` remains a thin
  **deprecated alias** for one release (script kindness), then is removed. **Test
  homes:** the dangling-link, overflow-before-projection, and orphan-visibility tests
  retarget from `index --check` to `qhaway check` (they assert the same invariants on
  the new command; cf. the regression-guard retargeting, FUP-1).

### Fourth review (Gemini) — resolved

Gemini's pass targeted SQLite/filesystem/protocol *realities* (a different class
than Codex's logical contradictions). All eight accepted; two refined:

- **G-1 — WAL sidecar teardown.** Rebuild-by-deletion removes **all three** files
  (`.qhaway.db`, `-wal`, `-shm`) together; deleting only the main db can leave a
  stale `-wal` SQLite recovers from → corruption. Folded into the backend section and
  any reset helper.
- **G-2 — WAL required, fail loud (Tony's call, MVP limitation).** No silent fallback
  to a rollback journal: that would give per-filesystem concurrency semantics
  (hidden two-modes divergence). If WAL can't init, refuse with a clear "move the
  memory dir to local storage" message. Wider filesystem support is a deliberate
  future expansion. (Folded into backend section.)
- **G-3 — schema-drift self-heal.** `PRAGMA user_version`; on a drift signal, delete
  the db files and rebuild from the topic files. Free because the db is a derived view —
  no migration tooling. *(Refined by FFUP-2 below: rebuild fires only on **true drift**
  — `user_version` mismatch / missing table-column — NOT on any `OperationalError`;
  non-drift errors fail loud without deleting. See the backend G-3 bullet.)*
- **G-4 — `edges` PK + index, no FK (refined).** `PRIMARY KEY (src_file, dst_slug,
  kind)` (dedups) + `INDEX(dst_slug)` (fast `check`/cleanup). **Declined** the
  suggested `FOREIGN KEY ... ON DELETE CASCADE`: reconcile already deletes edges
  explicitly on node-drop (C-6), so the FK is redundant, costs a `PRAGMA
  foreign_keys=ON` on every connection, and imposes an insert-ordering constraint —
  it would guard a path the single-shared-reconcile design forbids. (model.py row.)
- **G-5 — MCP stdout discipline.** `serve` reserves stdout strictly for JSON-RPC.
  *(Refined by TFUP-2 below — this bullet's "all errors → stderr, exit non-zero" holds
  only **before** serving starts; after, tool-call failures are in-band MCP errors on
  stdout. See the server.py row and TFUP-2 for the phase-split rule.)*
- **G-6 — link-append boundary.** `body.rstrip()` + `"\n\n"` + one `[[slug]]` per
  line + trailing newline; never joined onto the body's last sentence. (`remember`
  write path.)
- **G-7 — suffix loop hard cap.** `O_CREAT|O_EXCL` suffix loop is bounded (≈100) and
  fails loud, no `while True`. Mirrors the existing `_backup_path` cap. (`remember`
  write path.)
- **G-8 — explicit utf-8.** All new file I/O sets `encoding="utf-8"` (matches the
  existing code's discipline; LLM text carries emoji/smart-quotes/non-ASCII).

### Fifth round (Codex TFUP + Gemini U) — resolved

Both reviewers endorsed the prior round's decisions (Gemini: G-2 "highly sound,"
G-4 "reasonable"; Codex: SFUP-1 landed). The new findings are **consequences of the
G-3 schema-rebuild rule I added last round** — the convergent tail, not new design
holes. Two adversaries independently caught the same rebuild-loop hazard (U-1 ≈
the safety half of TFUP-1), which is the strongest signal it is real.

- **U-1 — infinite rebuild loop.** G-3's "rebuild on `OperationalError`" loops forever
  if the error is a *code bug* (the rebuilt db hits the same bug). Fixed: **rebuild at
  most once per session, then crash loud** (`_rebuilt` flag). (Folded into backend
  G-3 bullet.)
- **TFUP-1 — cross-process safety of the destructive rebuild.** Deleting/recreating db
  files while another process holds a connection forks reality. Fixed: the
  **destructive path only** takes a narrow `.qhaway.db.reset.lock` (bounded-wait, fail
  loud) — not a general mutex (declined in C-4). `serve` reopens through the reset path
  on mismatch. (Folded into backend G-3 bullet.)
- **TFUP-2 — stdout discipline, startup vs. tool-call.** G-5's "all errors → stderr,
  exit non-zero" is right *before* serving but wrong *after*: an accepted tool call's
  failure must be an **in-band structured MCP error on stdout** (C-10), not a crash.
  Split the rule by phase. (Folded into server.py row.)
- **U-2 — pin `busy_timeout = 5000`.** The C-4 timeout gets a concrete default (5 s) on
  every connection so concurrent writers serialize instead of immediately raising
  `SQLITE_BUSY`. (model.py row.)
- **U-4 — parameterized SQL.** All queries use `?` bindings, never string interpolation
  of parsed (untrusted) fields. Already how `model.py` is written; stated as a standard.
  (model.py row.)
- **U-3 — Windows `os.replace` over a 0444 file — DEFERRED to step 3, not folded.**
  On Windows, `os.replace` over a read-only target raises `PermissionError` (POSIX lets
  it through via directory write). Correct, but **out of scope for step 1** (Linux/WSL,
  single machine); Gemini itself tags it "future Step 3 redistribution." The step-3
  atomic-write helper will, on non-POSIX, clear the read-only attribute before replace.
  Folding Windows portability into a step-1 spec would be the scope creep this project
  guards against. **Named here so it is not lost; deliberately not built now.**

### Sixth round (Codex FFUP + Gemini U2) — resolved

Gemini's pass verdict: "complete, robust, fully prepared." Codex caught one real
correctness gap in the TFUP-1 fix I had folded — the round you authorized
specifically to catch fold-induced holes earned its keep here.

- **FFUP-2 — narrow the rebuild trigger (the keystone).** Rebuild fires **only on true
  drift** (`user_version` mismatch / missing table-column); every other
  `OperationalError` (locked, permission, I/O, SQL bug) **fails loud without deleting**.
  This is both correctness (stop masking real faults) and the thing that shrinks the
  destructive path to "an upgrade happened." (Folded into the backend G-3 bullet.)
- **FFUP-1 — the reset lock was a resetter mutex, not a lifecycle lock.** Codex is
  right: serializing two resetters does not stop an ordinary open connection from
  reading an unlinked db during a rebuild. The full fix is a DB-lifecycle lock
  (ordinary ops shared, rebuild exclusive). **Deliberately deferred for the MVP**
  (Tony's call: "is this a real problem for an MVP?" — it isn't): transient short-lived
  connections + per-project single-user dirs + FFUP-2 making rebuild fire only on a
  version upgrade mean the race effectively cannot co-occur; a shared lock on every
  read would be premature-collapse. Named as the future fix, documented as a residual
  limitation — not closed, not silent. (Folded into the backend residual-race bullet.)
- **U2-1 — lock file excluded/gitignored.** `.qhaway.db.reset.lock` joins the db/WAL
  files in `topic_files` exclusion, `.gitignore`, and reset cleanup. (Backend section.)
- **U2-2 — lock mechanism pinned.** `fcntl.flock(LOCK_EX|LOCK_NB)` in a bounded retry
  loop (~5 s, fail loud on timeout; don't delete the lock file after release). POSIX —
  consistent with step 1's Linux/WSL scope. (Backend section.)
- **Cleanup.** The historical G-5 bullet is annotated as refined-by-TFUP-2 (the
  phase-split is the operative rule).

## Out of scope (YAGNI / anti-sprawl — named, not silently dropped)

- **`search`** (prose/fuzzy match) — yanantin's tier; would collapse the crisp
  recall=navigate-facets / search=match-prose line and reinvent ArangoSearch.
- **Dynamic temporal banding** of overflow — the designed-in *first* enhancement,
  structured data carried but not rendered; built only after step 2 confirms
  `recall` is used.
- **Steps 2 (incent/measure) and 3 (package/redistribute)** — real, sequenced,
  later.
- **The file-write observability backstop** (record where the tool lost when the
  instance writes a file anyway) — belongs to step 2's measurement, not step 1.
- **db-first writes; graph traversal; open-vocabulary facets; BM25/Postgres** —
  all yanantin's (ArangoDB) tier, reachable by swapping the backend, not by
  thickening this one. SQLite FTS5 is the only in-qhaway search escalation
  considered, and only if prose search actually appears.

## Regression guard — preserve the cure invariants, retarget the tests (FUP-1)

**What is protected is the cure's *invariants*, not the test file verbatim.** The
first draft promised "`tests/test_qhaway.py` passes unchanged," but that predated
two design decisions that necessarily move the tests:

- **The backend swap** (DuckDB → SQLite) updates any test asserting a *DuckDB-specific
  behavior* (vs. a cure invariant) to its SQLite equivalent.
- **`index` → reconcile alias (OQ-3)** retires `index`'s full-projection *CLI
  surface*. The ~15 existing `qhaway index` tests assert *projection-engine*
  invariants (budget overflow, declared omissions, `--type`/`--role`/`--status`
  slices, `--dry-run`, (D) preservation, idempotence, tombstone exclusion, orphan
  visibility) — but they reach the engine *through* the old `index` CLI. Those
  invariants **still hold and still matter**: they are exactly what `recall` (via
  `project_slice` / `project_slice_with_overflow`) must guarantee, since `recall` is
  now the engine's consumer. So they are **retargeted** from `qhaway index` to
  `recall`/`project_slice` (and, where they test the redirect/(D)/orphan paths, to
  `reconcile`), not deleted.

The line that does NOT move: **no cure invariant is weakened.** Budget-fit,
declared-omission accounting, idempotence/(D), and tombstone exclusion must pass on
the new surfaces exactly as they did on `index`. If a port or retarget *changes a
cure invariant's meaning* (not just its call site), that is a stop-and-review
signal, not a license to soften the assertion. The design changed; the tests follow
the design; the cure's guarantees are the thing held fixed across the change.
