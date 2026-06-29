# Design: the write-side of link-supersession (`supersedes:`)

**Date:** 2026-06-29
**Status:** approved, ready for implementation plan
**Predecessor:** 0.1.8 shipped the *read-side* — parse surfaces a `supersedes`
slug list, `model.upsert_file` emits `SUPERSEDES` edges, and the projection
demotes any live node that is a `SUPERSEDES` target. That fix is **dormant**:
nothing in the system *writes* a `supersedes:` key yet. This spec closes the loop.

## The decision (spine)

Supersession is **edge-only, winner-asserted.** When memory B supersedes
memory A, B's file gains a `supersedes: [[A]]` frontmatter key. **A's file is
never touched** — it keeps `status: live` on disk; its effective superseded-ness
lives in the `SUPERSEDES` edge.

**Why edge-only, not mutate-the-loser:** the only writer in the system,
`server._exclusive_write`, opens with `O_CREAT | O_EXCL` — it can create-or-fail,
never mutate an existing file. Edge-only preserves that single-writer /
append-only invariant (see memory `single-writer-summons-consensus`). Mutating
A's file to flip its status would require a second, mutating writer and collides
with the same constraint that defers edit-in-place. Edge-only is not the
expedient choice; it is the choice the architecture's writer already dictates.

**Truth model:** a memory's effective status is the union of (its own `status`
declaration) and (what points a `SUPERSEDES` edge at it).

## Known, accepted seam (deliberate deferral)

A's *file* says `live` while A is *effectively* superseded. A human reading A's
file directly, or any future tool that does not consult the edge graph, sees
`live` and is wrong. This is accepted for now:

- It benefits the *ayllu* — every Claude Code instance on this system writes to
  this shared memory; link-expressed supersession leaking is a leak in *our*
  memory, and edge-only closes it through the projection (the path that matters).
- The file/edge split is an artifact of the append-only file backend. When this
  functionality is reimplemented in **yanantin** (a real store, no append-only
  constraint), effective status can be carried directly and the split dissolves.
  This is a seam to hand forward, not a defect to fix here.

## Two pieces (one capability, one release)

The two pieces share one fact — the `SUPERSEDES` edge — which 0.1.8 already
builds and the projection already reads. The write-side is only: *produce the
edge from `remember()`, and teach the one remaining edge-blind reader (`check`)
to consult it.* Neither piece is useful alone (edges nobody audits / an audit of
edges nobody writes), so **no release until both are done.** They may be staged
and committed separately (the pre-commit hook forces code/test separation
regardless); they ship together.

### Piece A — `remember()` writes the signal

- `server.remember(...)` gains a `supersedes` parameter, mirroring `links`:
  accepts a single slug/title or a list, `None` default.
- `reconcile.compose_frontmatter` emits a `supersedes:` key into the YAML
  frontmatter when present (it owns the YAML block; `compose_topic_file` threads
  the parameter through to it, as it already does for `description`).
  Normalized the same way links are, so `[[Title]]` and `bare-slug` both
  round-trip into the parser's existing `_supersedes` reader.
- The existing post-write `reconcile()` call indexes the new file, and the
  already-built `upsert_file` emits the `SUPERSEDES` edge. **No new edge
  machinery.**
- The MCP-exposed `remember` wrapper (server.py) also gains the parameter, with a
  docstring that tells instances *when* to use it: when this memory replaces an
  earlier one, name the loser.

### Piece B — `check` reads the signal

- `cli._stale_drift` today scrapes a node's *body* for a tombstone word on its
  own line (conservative, false-positive-prone — see its docstring). That prose
  scrape exists *because supersession had no structured signal to key on.*
- It gains a second, **precise** source: any live node that is the `dst_slug` of
  a `SUPERSEDES` edge is drift — no guessing.
- The prose scrape **stays** (it still catches the older hand-annotated form);
  the edge lookup becomes the high-confidence path. `check` reports both, and
  SHOULD distinguish edge-declared drift from prose-guessed drift in its output.

## Components touched

| File | Change |
|---|---|
| `src/qhaway/server.py` | `remember` + MCP `remember` gain `supersedes` param |
| `src/qhaway/reconcile.py` | `compose_*` emit the `supersedes:` frontmatter key |
| `src/qhaway/cli.py` | `_stale_drift` consults `SUPERSEDES` edges (precise path) |
| `tests/` | new tests, authored separately per the code/test hook |

Already done in 0.1.8 and **not** re-touched: `parse._supersedes`,
`model.upsert_file` edge emission, `project.*` edge-aware demotion.

## Testing

1. **`remember` writes the key** — call `remember(..., supersedes="a-slug")`;
   assert the new file's frontmatter contains a normalized `supersedes:` key and
   that, after reconcile, a `SUPERSEDES` edge row exists.
2. **Round-trip forms** — `[[Title]]`, bare slug, and a list all produce the
   right normalized edge target(s).
3. **Absent param** — `remember(...)` with no `supersedes` writes no key and no
   `SUPERSEDES` edge (no regression to existing remember tests).
4. **`check` flags edge-superseded drift** — a live A with a `SUPERSEDES` edge
   pointing at it is reported by `check`; a live A with no such edge and no prose
   marker is not.
5. **`check` still flags prose drift** — the existing body-scrape path is
   unbroken.
6. **End-to-end** — `remember(B, supersedes=A)` then `recall()` omits A from the
   live body and counts it in the superseded footer (the 0.1.8 read-side firing
   on a `remember`-produced edge, proving the loop is closed).
7. **No regression** — full suite green except the known
   `test_cli_concurrent_remember_no_lost_body` flake; arango tests skip on a base
   install / pass with the `reground` extra.

## Out of scope

- Mutating the loser's file / any second writer (rejected above).
- Dynamic faceting, `hide`, edit-in-place.
- The yanantin reimplementation (the seam is handed forward, not built here).
