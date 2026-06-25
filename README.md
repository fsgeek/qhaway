# qhaway

*Quechua: "to see / to watch over."* The name states the cure — make the whole
memory record **visible** instead of silently truncated.

`qhaway` keeps a Markdown memory index from being silently cut off when it grows
past the size limit of the system that loads it.

## The problem

Some agents and tools maintain memory as a directory of small Markdown files plus
a single curated index (`MEMORY.md`) that points at them. The index is loaded into
context on startup so the agent boots with a map of what it knows.

That index grows. When it grows past the loader's size limit, it is **silently
truncated** — cut off with no error raised. The agent boots a *partial self* and
doesn't know it: everything past the cut is invisible, and a pointer to a file
that no longer exists rides along just as silently. The honest record is there on
disk; the loaded view of it is a lie of omission.

This was observed live: a 36.8KB / 137-entry index against a ~24.4KB load limit,
with the entire latest section — including the pointer to the most recent state —
falling past the cut.

## The fix

qhaway regenerates `MEMORY.md` itself as a **truncation-proof projection** of the
memory files:

- **Files stay the write surface.** You keep writing topic `.md` files exactly as
  you do today. There is no schema to learn and no "save" API to call. qhaway only
  changes *who writes the index* — a machine, not a hand.
- **It fits the budget.** The regenerated index is guaranteed to come in under the
  loader's limit, so it is never silently cut.
- **No silent loss — ever.** When the index can't fit everything, it doesn't drop
  entries quietly. It **declares the omission**:

  ```
  +47 project memories not shown — run: qhaway index --type project
  ```

  Truncation becomes *visible selection*. You always know what was set aside and
  how to see it.

The loader keeps reading `MEMORY.md` exactly as before — now complete-for-what-it-
claims and guaranteed under budget. Nothing downstream changes.

## Install

```sh
uvx qhaway init
```

That's it. qhaway wires itself into Claude Code at user scope and activates in
any project that already has memory; projects without memory are untouched. No
clone, no per-project setup. To remove it: `uvx qhaway uninstall` (your
`MEMORY.md` files are left in place).

(Requires [`uv`](https://docs.astral.sh/uv/) — `uvx` fetches qhaway and a
managed Python on first use.)

### As a Claude Code plugin

If you'd rather load qhaway per-session from a checkout instead of installing it
at user scope, point Claude Code at the bundled plugin:

```sh
git clone https://github.com/fsgeek/qhaway
claude --plugin-dir qhaway/qhaway-plugin
#    the plugin ships disabled — enable it from /plugin to opt in
```

Disable it from `/plugin` and the hooks stop firing; your `MEMORY.md` is left as
a plain, readable, self-sufficient index — nothing broken, nothing to clean up.

### As a standalone CLI

If you just want the index tool by hand (no Claude Code), install it directly:

```sh
uv tool install qhaway
# or
pipx install qhaway
```

Embedded and zero-infra either way: it uses stdlib SQLite (WAL mode) as a single
local file. No server, no database to provision, no credentials.

## Usage

```sh
# Regenerate MEMORY.md from the memory directory (the main command)
qhaway index

# See a specific slice — including entries the default index declared as omitted
qhaway index --type project
qhaway index --role <role>
qhaway index --status superseded

# Set a custom budget
qhaway index --budget <bytes>

# Inspect without writing: would it overflow? any broken links? any leftover files?
qhaway index --check

# Print the projection without writing the file
qhaway index --dry-run
```

To record a memory: **write a topic `.md` file, then run `qhaway index`.** Don't
hand-edit `MEMORY.md` — it is fully derived, and any hand edit is preserved (see
below) but won't survive into the index unless it lives in a topic file.

## MCP spine (remember / recall)

The spine lets a Claude Code instance reach its memory through MCP tools instead
of hand-writing files. `MEMORY.md` becomes a managed, read-only **redirect** into
the SQLite-derived index; the topic files stay the source of truth.

```sh
# Run the MCP server over a memory directory (reconciles once at startup)
qhaway serve --dir <memory_dir>

# Sync the index from the files (alias: qhaway index)
qhaway reconcile --dir <memory_dir>

# Inspect: broken wikilinks, orphan backups, low topic count, would-overflow
qhaway check --dir <memory_dir>
```

Two verbs are exposed to the model:

- `recall(type?, role?, status?)` — pure read; returns the budgeted projection
  (omit args for the working set).
- `remember(type, title, body, description?, links?)` — writes a topic file then
  reconciles. Files stay truth; the DB is a derived, rebuildable view.

`MEMORY.md` is written born-read-only (`0o444`) as a friction signal — not a hard
barrier — so the reflexive hand-edit is deflected toward the tools. qhaway's own
writer updates it via atomic temp-file + replace.

## How it works

```
qhaway index
  → scan the memory directory
  → parse each file into a node (frontmatter type, filename role, links, body)
  → build an index of nodes + links in SQLite
  → project the working set under the byte budget,
    appending a declared-omissions footer for anything set aside
  → write MEMORY.md
```

The memory files are the single source of truth. The index is rebuilt from scratch
on every run, so it can never drift from the files. The same files always produce
a byte-identical index.

### What's preserved

`MEMORY.md` is fully machine-derived — there are no hand-maintained regions. If
qhaway ever finds that the index was edited by hand since it last wrote it, it does
**not** overwrite the edit: it renames the existing file to a timestamped
`MEMORY-<timestamp>.md` and writes a fresh index. Your edit is preserved verbatim;
the index rebuilds from the files. Nothing is interpreted, merged, or lost.

## Design philosophy

One pain, fixed completely: **truncation**. Full-text search, deep audit, write
tooling, and ranking sophistication are deliberately *not* in this version — each
is a real later idea, none is this version's job.

The wager is simple: a structured index built *over* an existing pile of files —
without replacing the pile — makes the whole thing measurably work better. The
proof is use. If it removes felt pain for skeptical users who'll drop it the moment
it's more friction than value, it ships; if it removes the same pain for strangers
feeling the same sprawl, it spreads. Propagation is the measurement.

## Status

Early (`v0.1.0`). The design is specified in
[`docs/superpowers/specs/2026-06-20-qhaway-mvp-design.md`](docs/superpowers/specs/2026-06-20-qhaway-mvp-design.md).
