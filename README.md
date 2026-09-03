# qhaway

[![CI](https://github.com/fsgeek/qhaway/actions/workflows/ci.yml/badge.svg)](https://github.com/fsgeek/qhaway/actions/workflows/ci.yml)

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
uvx qhaway init        # `uvx qhaway install` works too
```

Then **restart Claude Code.** qhaway wires itself in at user scope — both the
boot hooks (which deliver your memory at session start) and the `recall` /
`remember` MCP tools — and activates in any project that already has memory;
projects without memory are untouched. No clone, no per-project setup. To remove
it: `uvx qhaway uninstall` (your `MEMORY.md` files are left in place).

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

After `init` and a restart, a Claude Code instance reaches its memory through two
MCP tools instead of hand-writing files. `MEMORY.md` becomes a managed,
read-only **redirect** into the SQLite-derived index; the topic files stay the
source of truth.

Two verbs are exposed to the model:

- `recall(type?, role?, status?)` — pure read; returns the budgeted projection
  (omit args for the working set).
- `remember(type, title, body, description?, links?, supersedes?)` — writes a
  topic file then reconciles. Pass `supersedes` naming the memory this one
  retires, and recall demotes the loser. Files stay truth; the DB is a derived,
  rebuildable view.

You don't run the server yourself — `init` wires it. Under the hood the MCP
server derives its memory directory from `CLAUDE_PROJECT_DIR` and provisions it
on first use, so a brand-new project starts ready for its first `remember()`.
(The internal commands — `qhaway serve`, `qhaway reconcile`, `qhaway check` —
exist for debugging; a normal install never invokes them by hand.)

`MEMORY.md` is written born-read-only (`0o444`) as a friction signal — not a hard
barrier — so the reflexive hand-edit is deflected toward the tools. qhaway's own
writer updates it via atomic temp-file + replace.

## Hookless hosts (Claude Desktop / Cowork)

Claude Desktop's Cowork keeps a per-space memory store in the same shape — topic
`.md` files plus a `MEMORY.md` index — but it runs **no session hooks**, and it
loads `MEMORY.md` straight through a reader that truncates far earlier than
Claude Code's (a Cowork session itself reported ~3.5KB when asked; not
independently measured — treat `--budget` as something to verify on your host). The redirect design above assumes a
hook will deliver the projection; on a host with no hooks, a session that never
calls `recall()` would boot with a stub and nothing else.

For those hosts, run the server in **inline-index mode**:

```sh
qhaway serve --dir <space memory dir> --inline-index --budget 3400
```

`MEMORY.md` then *is* the budgeted index — rewritten when the server starts and
again after every `remember()`, signed, and with a footer that points at
`recall()` for everything it had to set aside. The host keeps loading the file
exactly as before; it just never loads a truncated one.

Wire it in `claude_desktop_config.json` (macOS: `~/Library/Application
Support/Claude/`; Windows: `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "qhaway": {
      "command": "uvx",
      "args": ["--python", "3.14", "qhaway", "serve",
               "--dir", "/path/to/the/space/memory",
               "--inline-index", "--budget", "3400"]
    }
  }
}
```

The space's memory directory is the folder holding its `MEMORY.md`, under the
Claude app-data directory (on Windows,
`%APPDATA%\Claude\local-agent-mode-sessions\<session>\<agent>\spaces\<space>\memory`);
searching that tree for `MEMORY.md` is the quickest way to find it. Set
`--budget` to your host's observed limit with a little headroom.

qhaway runs natively on Windows (the test suite runs there in CI), so the
entry above works as-is with `uv` installed on Windows. Running Claude Desktop
on Windows with qhaway installed inside WSL works too —
`uv tool install qhaway` in WSL, then use `"command": "wsl"` with
`"args": ["-e", "/home/<you>/.local/bin/qhaway", "serve", "--dir", "/mnt/c/Users/<you>/AppData/Roaming/Claude/.../memory", "--inline-index", "--budget", "3400"]`.

What to expect:

- On first start, the host's own index is preserved as `MEMORY.preinstall.md`
  before qhaway's takes its place; nothing is deleted.
- If the host rewrites `MEMORY.md` itself, qhaway treats that like any hand
  edit (see "What's preserved" below): the host's version is kept under a
  timestamped name and the index is rebuilt on the next start.
- Topic files the host writes during a session enter the index at the next
  server start or the next `remember()`; `recall()` always reads the current
  files.

This mode has been verified against a copy of a live Cowork space store (46
memories: a 12KB native index became a 3,150-byte index declaring 33 set
aside). It has not yet been run against a live space — if you try it, the
outcome is worth an issue either way.

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

Early (`v0.5.2`). The design is specified in
[`docs/superpowers/specs/2026-06-20-qhaway-mvp-design.md`](docs/superpowers/specs/2026-06-20-qhaway-mvp-design.md).

## Contributing

Changes go through pull requests; `main` is protected and merges only when CI is
green. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup and the test-first,
separate-commits conventions the project expects. Licensed [MIT](LICENSE).
