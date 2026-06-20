# Qhaway MVP — Design

**Date:** 2026-06-20
**Status:** Drafted for review (Tony delegated; brainstormed collaboratively)
**Name:** `qhaway` — Quechua "to see / to watch over." The name states the cure:
make the whole memory record *visible* instead of silently truncated. (The
Quechua naming is intentional — it carries meaning to the maintainer that a
stranger reads as a clean handle.)

## The one pain

**Truncation.** An instance's curated memory index (`MEMORY.md`) grows past the
harness load limit (~24.4KB) and is **silently cut**. The instance boots a
*partial self* and does not know it. Observed live in the hamutay corpus: the
index is 36.8KB / 137 entries; everything past ~line 123 — including the entire
handoff/bequest lineage and the "LATEST" pointer — is invisible to a new ghola.
The "LATEST" pointer even references a file that does not exist on disk, and the
flat file carried the dangling link silently.

This is the project's through-line wound in its memory costume: the honest record
cut without an error raised (cf. the `max_tokens` guillotine, manufactured
silence, search-reads-state). Qhaway fixes *this* face of it. Nothing else in v1.

## Thesis being proved (microcosm)

The **Indaleko thesis**: a structured index built *over* the existing flat-file
mess — without replacing the mess — makes the system measurably work better. Here
the subject is a Claude Code instance (a clean, reproducible instrument), the mess
is the memory directory, and "better" = boots a complete self instead of a
truncated one. The files stay the write surface; qhaway is the derived read layer.

## Non-negotiable constraints (these keep it small AND adoptable)

1. **Files stay the write surface.** The instance/human keeps writing topic `.md`
   files exactly as today. Qhaway never asks anyone to write schema, call a "save"
   API, or change how they record a memory. Requiring behavior change is the
   adoption-killer that would void the measurement.
2. **Drop-in read path (approach A, fully derived — "i").** Qhaway *regenerates
   `MEMORY.md` itself* as a truncation-proof projection. The harness keeps loading
   `MEMORY.md` as always. **MEMORY.md is fully derived — no hand-maintained
   regions.** This is deliberate over the sentinel/preserve-regions alternative:
   preserving hand-edited regions would leave hand-editing *working*, which
   removes the model's incentive to use the tool at all. The derived index must be
   the *only* index, so the path to a good index runs through the files + qhaway.
   - **Section headers are derived** from facets (`content_type`/`role`), not
     hand-curated. Today's `## Architecture & direction` etc. are reconstructed by
     grouping, not preserved.
   - **Stray hand-written prose** in today's MEMORY.md (e.g. the collapsed-handoffs
     note) is content that lives *only* in the index. On first derivation it is not
     lost — see constraint 3 + the edit-handling rule below — but it is no longer a
     hand-maintained region going forward; durable notes move into a topic file.
3. **No silent loss — ever, including the index file itself.** Two faces:
   - *Slice omissions are declared:* when a slice omits entries to fit the budget,
     it states it ("+47 project memories not shown; `qhaway index --type project`").
     Truncation becomes *visible selection* — declared-losses applied to my memory.
   - *The prior index is never destroyed (edit-handling, "D"):* before writing a
     fresh MEMORY.md, if the existing one was edited since qhaway last derived it
     (content hash differs from the recorded last-output hash), qhaway **renames it
     to `MEMORY-<UTC-timestamp>.md`** and writes clean. The timestamp is
     **microsecond-resolution, and if that name still collides with an existing
     orphan, a `-NN` suffix is appended** — the preservation mechanism must never
     overwrite a previously-preserved file (that would be silent loss *inside* the
     anti-silent-loss mechanism). No diffing, no interpretation, no promotion of
     orphan lines — preservation *is* the handling. A hand-edit is never a conflict
     and never lost; it is preserved verbatim and superseded. This makes a stray
     hand-edit (an instance ignoring the constraint-8 instruction) *safe* rather
     than racing the regenerator — the hand
     edit survives in the timestamped file; the index rebuilds from the topic files.
     **Accretion is residue from ignored-instruction edits — the leak is stopped
     at the source (constraint 8), and (D) only catches what slips past.** With the
     memory instruction changed to "write a topic file, run `qhaway index`, don't
     hand-edit MEMORY.md," the expected steady-state hand-edit rate is ~zero; a
     `MEMORY-<ts>.md` appears only when something ignores the instruction (the
     residue (D) exists to preserve, not lose). Belt-and-suspenders: (a) `--check`
     **counts and lists** orphan timestamped files so any residue is *visible*;
     (b) constraint 7 (idempotence) guarantees qhaway's own output never triggers a
     rename. Recovery (folding an orphan's content back into a topic file) is the
     deferred opt-in `qhaway reconcile`. The point: the leak is *closed*, not merely
     *counted* — counting is the backstop, not the strategy.
   - *Lived-experience caveat (named, not smoothed):* "no silent loss" is true
     **on disk** but, for index-only prose (e.g. a hand-written note that lives
     only in MEMORY.md, never in a topic file), **false from the booting
     instance's point of view** on first derivation: it survives in
     `MEMORY-<ts>.md` (which the harness never loads) but vanishes from the loaded
     working set. This is accepted for MVP — the cure is truncation, not orphan-prose
     migration — but it is stated outright: *first derivation may drop index-only
     prose from the loaded self; it is preserved on disk; folding it back is
     `reconcile`'s job.* Durable notes should live in a topic file, not the index.
4. **One pain only.** Full-text search and deep audit are later iterations, not
   v1. v1 is truncation.
5. **Pip-installable, embedded, zero-infra.** `uv tool install qhaway` /
   `pipx install qhaway`. DuckDB embedded (single file, no server) so it installs
   across platforms. (FTS limitation is irrelevant to v1; the prose/search tier
   stays yanantin's, later.)
6. **Budget is in TOKENS, measured, and test-pinned.** The harness limit is a
   token budget; qhaway projects under a **byte budget as a conservative proxy**
   for it (bytes ≥ tokens for typical text, so a byte budget under the token limit
   cannot overflow it). The default budget number is **measured against the live
   harness limit and asserted in the test suite**, so a harness change fails the
   tests loudly rather than silently re-truncating — hardcoding the number
   un-pinned would be the exact disease we are curing. Budget is configurable
   (`--budget`), default = measured-limit-minus-headroom.
7. **The derived MEMORY.md is a PURE FUNCTION of the topic files (idempotence) —
   the invariant the whole (D) scheme rests on.** The output must contain **no
   run-varying content**: no generation timestamp, no clock, no ordering that
   depends on anything but the files. If it did, the derived file's hash would
   never match the recorded last-output hash, so (D) would rename-on-every-run and
   the per-session content leak (constraint 3) would become **per-run** —
   catastrophic. Therefore: same topic files in → byte-identical MEMORY.md out,
   every time. Any timestamp lives in the sidecar (`.qhaway.json`), never in the
   derived index. Enforced by test 8. (This also *simplifies* (D): rename happens
   only on a genuine human edit, never on qhaway's own output.)
   - **How determinism is achieved (the clause idempotence actually rests on):**
     DuckDB does not guarantee row order without an explicit `ORDER BY`, and **any**
     recency sort key is not by itself total — whatever recency tiers lead (the
     lead order is deferred; see projection rule step 4), any of them can tie (two
     files written in the same second; two undated files), and a tie that isn't
     broken deterministically could swap between runs and break byte-identity.
     Therefore **every ordering ends in a final tiebreak on `filename`** (the PK,
     unique by construction), so the sort is total and run-invariant. Without this, idempotence fails silently in
     exactly the way (D) punishes hardest (rename-every-run).
8. **Stop the leak at the source: the harness memory instruction changes.** The
   accretion leak (constraint 3) exists *only because* the live memory instruction
   tells instances to "add a pointer line to MEMORY.md by hand." That instruction
   is not the write surface — the **topic files** are — so changing it does not
   violate constraint 1; it *completes* it. The instruction becomes: **"to record
   a memory, write a topic `.md` file; run `qhaway index` to refresh MEMORY.md;
   do not hand-edit MEMORY.md."** This kills the leak at the source rather than
   mopping it up. (D) remains as the *safety net* for when the instruction is
   ignored — which it will sometimes be — but it is no longer the primary
   mechanism. This is a one-line instruction change, not code; it ships with v1.
   *Choosing to merely document the leak while this cheap source-fix sat unused
   would be declared-loss substituting for fixing — the failure mode this project
   most needs to avoid.*

## Measurement (anti-Goodhart)

No proxy metric is baked in. The test is use: Tony installs it across his
machines and uses it; the next Claude instance boots through it. It ships as a
tool iff it fixes felt pain for these two skeptical users (who will abandon it the
moment it is more friction than value), and spreads iff it fixes the same pain for
strangers feeling the sprawl. Propagation *is* the proof.

## Architecture

Three small, independently-testable units + a CLI. Mirrors the proven prototype
(`llm-memory/proto/memory_model.py`), promoted to a real package.

| Unit | Purpose | Depends on |
|---|---|---|
| `parse.py` | One memory file → a node dict. Tolerant frontmatter (real corpus has unquoted colons); filename is the id; derives `content_type` (frontmatter `type`), `role` (filename prefix), `status` (live/superseded via tombstone `name`), `origin_session`, `date_hint`, body, `[[links]]`. | pyyaml |
| `model.py` | Build the DuckDB index from a memory dir: `nodes` + `edges` tables. Idempotent (rebuild from scratch each run — the files are the source of truth). | duckdb, parse |
| `project.py` | Render an index slice as Markdown that **fits a byte budget** and **declares omissions**. The core of the cure. Slice by facet (type/role/status), order by a simple salience rule, truncate-with-declaration never silently. | model |
| `cli.py` | `qhaway` entry point. `index` (regenerate MEMORY.md, with (D) edit-handling), `index --type/--role/--status/--budget`, `--check` (no write; see below), `--dry-run` (print, don't write). | model, project |

**What `--check` scans (pinned — its original target moved).** Because the derived
MEMORY.md is a pure function of existing topic files (constraint 7) and every
emitted link resolves to a file on disk (test 5), qhaway **structurally cannot
emit a dangling MEMORY.md pointer** — so checking the derived index for dangling
pointers would be testing a file qhaway just guaranteed clean (vacuous). The
original motivating symptom (the "LATEST" pointer to a nonexistent file) was a
property of the *hand-maintained* index, which no longer exists. `--check`'s real,
still-valuable jobs in v1 are therefore: (1) report **`[[wikilinks]]` in topic-file
bodies that point at missing files** (real rot in the source, not the index);
(2) report whether the current corpus **would overflow** the budget (and by how
much); (3) count and list **orphan `MEMORY-<ts>.md` files** (accretion residue,
constraint 3). It does *not* re-scan the derived index for dangling pointers.

State qhaway records (single small sidecar, `.qhaway.json` in the memory dir):
the **content hash of the last MEMORY.md it wrote**, plus a **`"version": 1`
field** (cheap insurance — the first time the sidecar shape changes, new code can
detect old-format state instead of misreading it). (D) compares the current
MEMORY.md's hash to the recorded one; a mismatch means a hand-edit happened →
rename to timestamped file before regenerating. First run (no sidecar) treats any
existing MEMORY.md as a hand-edit and preserves it. This sidecar is the *only*
state qhaway keeps outside the derived index; the topic files remain the source of
truth. Any timestamp the tool needs lives here, never in the derived MEMORY.md
(constraint 7).

### Data model (derived from the real corpus — see llm-memory/proto/MODEL.md)

`nodes`: `file` (PK — the true stable id; frontmatter `name` is unreliable, 14/137
are tombstones), `name`, `content_type`, `role`, `description` (the index hook),
`status`, `origin_session`, `date_hint`, `body`.
`edges`: `(src_file, dst_slug, kind=REFERENCES)` from `[[wikilinks]]`, ids
reconciled to one canonical slug (= filename stem) so the graph actually connects.

## Data flow

`qhaway index` →
  scan memory dir → `parse` each file → build `nodes`/`edges` in DuckDB →
  `project` the working-set slice (default: the "how to act" + recent set) under
  the byte budget, appending a declared-omissions footer for anything set aside →
  write `MEMORY.md`.

The harness then loads `MEMORY.md` as it always has — now complete-for-what-it-
claims and guaranteed under budget.

### The projection rule (v1, deliberately simple)

Order of operations (footer space is reserved BEFORE filling, so the declaration
can never itself overflow the budget):

1. Select `status=live` nodes (tombstoned/superseded excluded — see below).
2. **Reserve footer budget:** subtract the worst-case footer up front, then fill
   the remainder. The footer denominator is a **fixed, bounded set** — one line
   per omittable `content_type` (`project`, `reference`; `user`+`feedback` are
   prioritized, see step 3) **plus one line for superseded** — i.e. ~3 lines, NOT
   a per-`(type, role)` combinatorial. `content_type` is the documented schema set
   {`user`, `feedback`, `project`, `reference`}. Handoffs are **not a fifth type**:
   they are `content_type=project` with `role=instructions` (the corpus types them
   `project`; `instructions` is a *filename-prefix role*, not a content type — see
   MODEL.md finding #1). `role` is available for `--role` filtering but is not a
   footer/sort bucket in v1. **The reserved footer is exactly these three candidate
   lines: `project`, `reference`, `superseded`** (assembled in one place, not three
   — steps 5 and the tombstone block below emit from this same fixed set). Bounded
   and cheap regardless of corpus richness.
3. **Prioritize `user` + `feedback` (how-to-act) — but they are NOT budget-exempt.**
   They are placed first because they are most load-bearing. If even the
   prioritized set exceeds budget (a `feedback` corpus grown huge), it ALSO yields
   to declared omission — *truncation-with-declaration is the universal rule, no
   exceptions.* "The always-include set can't overflow" is exactly the faith-based
   assumption this project refuses to make (it is the original bug in a new place).
   When the prioritized set itself must be trimmed, it uses the **same recency sort
   as step 4** (applied within the prioritized set first), with the same filename
   final tiebreak — so even this rare path has a total, defined order.
   Test 10 pins this: a corpus whose `user`+`feedback` alone exceed budget still
   yields a MEMORY.md under budget, with the omission declared.
4. Fill remaining budget with `project`/`reference` by **recency**.
   - **What is PINNED (idempotence-critical, do not defer):** `filename` is the
     **final, terminal tiebreak**. `filename` is the PK — unique and run-invariant
     by construction — so whatever recency tiers precede it, appending `filename`
     last makes the sort **total, not total-if-no-ties.** This is the clause
     idempotence (constraint 7 / test 8) actually rests on: any recency signal
     (`date_hint`, `origin_session`, `mtime`) can produce ties (two files written in
     the same second; two undated files), and DuckDB does not guarantee row order
     without a total `ORDER BY`, so a tie that isn't broken deterministically swaps
     between runs → byte-different MEMORY.md → (D) renames on a no-change run (the
     per-run leak constraint 7 calls catastrophic). `filename`-last closes that.
   - **What is OPEN (the recency-tier order — deliberately deferred):** which
     recency signal *leads* (`date_hint`-first vs. `origin_session`-first vs.
     `mtime`-first) is **not yet decided**, and the spec does not force it. The
     corpus sweep (corpus-findings **S1**) measured the signals — `date_hint` 7%,
     `origin_session` 56%, `mtime` 100% — but that measurement does **not** by
     itself prescribe an order: a sparse signal (`date_hint`) may still be the
     *best* lead precisely because it is *deliberately* set (dated handoffs are
     high-salience), whereas `mtime` is incidental and transfer-fragile (S1's
     scp/rsync boundary). This is a salience question, and per the project's
     anti-premature-collapse principle, **salience tuning is deferred** (see the end
     of this section). The implementer/tester resolve the lead-tier order during
     the build — ideally empirically (run candidate orders over the real corpora;
     the corpus is the referee), not by argument. Until then, only `filename`-last
     is contractual. **NOTE:** earlier drafts and corpus-findings S1 gestured at a
     specific lead order; treat those as *proposals*, not as the pinned contract —
     the pinned contract is `filename`-terminal + recency-lead-TBD.
5. Emit the reserved footer: one declared line per omitted `content_type`
   ("+N project memories not shown; `qhaway index --type project`").

**Footer line format (PINNED — this is a machine contract, exact).** Each declared
footer line is exactly:
`+<N> <facet> memories <verb>; \`qhaway index --<flag> <value>\``
where `<N>` carries a **leading `+`** (it is a count-of-additional, not a total),
`<verb>` is `not shown` for budget-omitted content_types and `hidden` for
design-excluded tombstones, and the trailing backticked command is the exact
recovery invocation. Examples:
`+47 project memories not shown; \`qhaway index --type project\`` /
`+2 superseded memories hidden; \`qhaway index --status superseded\``.
The `+` is part of the contract: any parser counting omissions strips a leading
`+`, so emitting the bare count would break the (shown + declared-omitted) ==
total accounting (test 2). Pinned here because the format was previously only
shown-by-example, leaving a cold author free to emit `N` or `+N` inconsistently.

**Tombstones are excluded by design, not by budget — and that exclusion is itself
declared.** Superseded nodes are live-on-disk files, so omitting them silently
would brush constraint 3. The footer therefore always states "+N superseded
memories hidden; `qhaway index --status superseded`." Design-exclusion, declared.

Salience beyond recency (e.g. reference-count via the edge graph) is explicitly
deferred — start simple, use it, refine only when a real miss appears
(anti-premature-collapse).

## Error handling

Fail-loud on: memory dir unreadable, DuckDB write failure. **Never** drop a file
silently on a parse slip — fall back to a tolerant parse and, if even that fails,
include the file as a body-only node and report it. A file that cannot be indexed
is surfaced, not swallowed (swallowing is the disease).

## Testing

TDD. Tests encode the cure as falsifiable criteria (authored per the project's
code/test separation — implementation by Claude, validating tests authored
separately):
1. A corpus that overflows the budget yields a `MEMORY.md` **under** the budget,
   including the reserved footer (footer space reserved before filling).
2. Nothing omitted is omitted **silently** — every omission has a declared footer
   line, and `(shown + declared-omitted) == total live nodes`. Tombstones excluded
   are *also* declared (their count appears in the footer).
3. **`--check` reports `[[wikilinks]]` in topic-file BODIES that point at missing
   files** (real rot in the source), not carried silently. (It does NOT check the
   derived index for dangling pointers — constraint 7 + test 5 make that vacuous;
   see "What --check scans.")
4. Tombstoned (superseded) nodes are excluded from the default slice but remain
   queryable by `--status superseded`, and their exclusion is declared (test 2).
5. **Machine-contract, not "format":** every emitted line matches the harness
   pattern `- [Title](file.md) — hook`, and every link target resolves to a file
   on disk. (Not "reproduces the hand-written corpus format" — that corpus is not
   format-consistent and the assertion would be unfalsifiable. The harness only
   requires the line pattern + resolvable links.)
6. **Edit-handling (D) is non-destructive:** given a MEMORY.md whose hash differs
   from the recorded last-output hash, `qhaway index` renames it to
   `MEMORY-<timestamp>.md` (byte-identical to the pre-run file) before writing the
   fresh one; the prior bytes are recoverable and nothing is interpreted or dropped.
7. **Budget is token-pinned:** the default budget constant is asserted against the
   measured harness limit, so a limit change fails this test rather than silently
   re-truncating.
8. **Idempotence (the cornerstone of (D) — must-pass):** two consecutive
   `qhaway index` runs with no topic-file changes produce a **byte-identical**
   MEMORY.md and create **zero** new `MEMORY-<ts>.md` files. This proves the
   derived index is a pure function of the topic files (constraint 7) and that (D)
   does not rename on qhaway's own output. Without this test passing, the whole
   scheme degenerates into rename-every-run.
   - **Fixture requirement (non-negotiable):** the idempotence corpus MUST include
     at least one pair of nodes with **identical `date_hint` AND identical `mtime`**,
     so the filename final tiebreak (step 4) is actually exercised. Without a tie in
     the fixture, this test passes green while the tiebreak is untested and the bug
     sits live — a guarantee tested-but-not-pinned, the worst kind. The tie is the
     point of the test, not an edge case.
9. **Orphan visibility:** `--check` reports the count and names of existing
   `MEMORY-<ts>.md` orphan files, so any accretion residue is surfaced, not silent.
10. **Prioritized set is not budget-exempt:** a corpus whose `user`+`feedback`
    nodes ALONE exceed the budget still yields a MEMORY.md under budget, with the
    omission declared (constraint/projection step 3). No always-include set can
    silently overflow.
11. **Preservation can't self-destruct (F):** two (D) renames forced to the same
    timestamp resolution produce **two** distinct `MEMORY-<ts>[-NN].md` files —
    the second never overwrites the first. The anti-silent-loss mechanism cannot
    itself lose a previously-preserved file.

## Out of scope (YAGNI / anti-sprawl)

Full-text/prose search (yanantin's tier); W5H facet store beyond the few facets
already in the files; multi-human/multi-principal; the `recuerdalo` write tool and
directory watcher (later — v1 doesn't change the write path); the read-tool MCP
surface; cross-tool capture (Desktop/Cowork); salience/ranking sophistication.
Every one of these is a real later idea; none is v1's one pain.
