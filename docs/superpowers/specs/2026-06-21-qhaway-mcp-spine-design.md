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

The truncation cure is built and verified: `parse.py` → `model.py` (DuckDB
`nodes`/`edges`) → `project.py` (`project_slice`: budgeted, faceted, declared
omissions, idempotent) → `cli.py` (`qhaway index` with (D) edit-preservation,
`--check`, `--dry-run`, `--budget`, facet flags). The package builds (`uv_build`,
entry point wired). **The new work is: a thin MCP layer (two verbs), one shared
`reconcile` operation (incremental index sync + self-healing read-only redirect),
and two new `nodes` columns (`mtime`, `size`) to make reconcile cheap — not a new
engine and not a new source of truth.** `parse.py` and `project.py` are reused
unchanged; `model.py` gains two columns; `cli.py` is extended.

## What qhaway is (rationale — keep this seam clean)

qhaway is the **index-service factoring of MEMORY.md**: the service the flat file
was always pretending to be. The duality — files author memories; DuckDB *derives*
a queryable index; `[[wikilinks]]` live as text in files and become edges only on
rebuild — is **not a compromise to undo.** It is the normal shape of an index over
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
   DuckDB index is *derived* from them and rebuildable at any time (the MVP rebuilt
   it from scratch each run; this spine reconciles it incrementally — same guarantee,
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
   are not errors — they are dangling links, surfaced by `--check`.
4. **MEMORY.md is fenced read-only.** It is fully derived; nobody should hand-edit
   it. Fencing it channels the write reflex toward `remember`. Topic files stay
   writable (they are the write surface; a stray hand-written topic file is a
   *caught* event for step 2, not a blocked one).
5. **Two verbs only on the MCP surface.** `remember`, `recall`. No `search` (prose
   match is yanantin's tier), no `index`/`--check` verb (those stay CLI). Every
   extra verb is friction before the tool feels usable.

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

1. Compose a topic file from the args: slugify `title` → filename stem (collision →
   numeric suffix, never overwrite an existing topic file); emit minimal
   frontmatter (`name: <title>`, `type: <type>`, `description:` if given) in the
   shape `parse.py` already tolerates; write `body`; append any `links` as
   `[[slug]]` text.
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

`recall`'s omission handling returns *structured* overflow info (counts per
dynamic facet — `origin_session`, `date_hint` — of the omitted set), even though
v1 renders it as the existing flat "+N not shown" footer. This computes and
carries the band data so the **designed-in first enhancement** (dynamic temporal
banding of overflowing slices) changes only *presentation*, not *availability*.
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
   `(mtime, size)`. Reconcile stats every topic file: `(mtime, size)` unchanged →
   skip (trust the existing row); changed or new → re-parse and update the node;
   in-db-but-gone-from-disk → drop the node. Most session-starts change nothing, so
   reconcile is a stat sweep — near-instant.
   - **Deliberate limit (declared, not hidden):** `(mtime, size)` cannot detect a
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

The fence makes hand-editing MEMORY.md harder than calling `remember`: to defeat a
0444 file the instance must run `chmod` in bash — more work, more conspicuous, more
obviously vandalism against a managed artifact — while `remember` sits right there
offering one call. The fence handles the stubborn *write* reflex; the redirect
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

**SPIKE (must run before building on this):** a ~10-line script confirming, on this
Linux box, that (a) writing through an fd to a 0444-mode file succeeds, and (b)
`os.replace` of a 0444 temp over an existing 0444 `MEMORY.md` succeeds. This is a
filesystem-edge assumption, not a fact — verify it, do not trust it. If (a) or (b)
fails, fall back to write-temp-0644 → replace → `chmod 0444` (a tiny writable
window, acceptable because MEMORY.md is regenerable). The (D) edit-preservation
logic in `cli.py` is reused unchanged; only the final write becomes the
read-only swap. The same write helper lives in `reconcile`, so fence + (D) behave
identically for every caller (startup hook, MCP, CLI).

## Architecture

| Unit | Purpose | Depends on |
|---|---|---|
| `server.py` (new) | MCP server exposing `remember` + `recall`. Thin: composes/validates args, calls `reconcile`/`project_slice`, returns strings. | reconcile, project, parse |
| `reconcile.py` (new) | The one shared sync op: incremental `(mtime,size)` topic reconcile + (D)-checked, born-read-only, self-healing MEMORY.md redirect. Also houses the born-read-only atomic-replace helper and the `remember` slugify/frontmatter composer. | model, parse, project |
| `cli.py` (extend) | Add `qhaway reconcile` (the startup-hook entry; also = `init`) and `qhaway serve` (launch the MCP server). The existing `index` keeps working; its write path is migrated onto `reconcile`'s shared helper so there is one write path. | reconcile, server |
| `model.py` (extend) | Add `mtime` + `size` columns to `nodes` so `reconcile` can stat-compare. Otherwise unchanged. | duckdb, parse |
| `parse.py`, `project.py` | **Unchanged.** Reused wholesale. | — |

## Data flow

```
startup hook  →  reconcile(dir)
  stat topic files vs (mtime,size) in db → re-parse only changed/new, drop deleted →
  (D)-check + self-heal MEMORY.md redirect (born read-only, atomic replace)

remember(type,title,body,...) →
  compose topic file (slug, frontmatter, links) → write topic .md →
  reconcile(dir) → return confirmation

recall(facets?) →
  project_slice(facets) → return markdown        [no reconcile, no write — pure read]
```

## Error handling

Fail loud, never silently. `remember`: refuse on slug collision that can't be
resolved, on unreadable memory dir, on db build failure — return an error string,
never a false success. Invalid `type` (not in the four) is rejected at the tool
boundary (the schema enum), not coerced. `recall`: a db build failure surfaces;
an empty result is a valid empty slice, not an error. The fence: if the
read-only swap fails, report it — do not leave MEMORY.md in a half-written state
(atomic replace guarantees all-or-nothing).

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
   edges; a link to a nonexistent slug is surfaced by `--check`, not swallowed.
5. **`recall()` returns the budgeted working set** — byte-identical to what
   `project_slice` produces for the same corpus; under budget; declared omissions
   present.
6. **`recall(facet)` returns the drill-down slice** for each of `type`/`role`/
   `status`, matching `project_slice` with the same arguments.
7. **`recall` writes nothing and does not reconcile:** no file in the memory dir is
   created or modified by a `recall` call; it is a pure read of the current index.
8. **`recall` overflow carries structured band info:** when a slice overflows, the
   returned omission data includes per-`origin_session`/`date_hint` counts of the
   omitted set (even though rendered as the flat footer in v1).
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
    via a parse spy/counter), proving the `(mtime, size)` skip works — and still
    produces a correct, byte-identical index.
13. **Reconcile catches a changed topic file:** touching one topic file's content
    (changing its `(mtime, size)`) causes exactly that node to be re-parsed and its
    new content to appear in a subsequent `recall`; deleting a file drops its node.
14. **Reconcile is idempotent on its own output:** two consecutive `reconcile` runs
    with no changes create **zero** new `MEMORY-<ts>.md` files (the template write is
    skipped when already matching) — the (D)/idempotence guarantee the MVP pins,
    preserved through the shared path.

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
- **db-first writes; graph traversal in DuckDB; open-vocabulary facets** — all
  yanantin's, reachable by swapping the backend, not by thickening this one.
```
