# qhaway

[![CI](https://github.com/fsgeek/qhaway/actions/workflows/ci.yml/badge.svg)](https://github.com/fsgeek/qhaway/actions/workflows/ci.yml)

*Quechua: "to see / to watch over."* The name states the job: watch over what an
agent carries into each session, and keep everything else in sight.

`qhaway` decides what an agent's memory index spends of its context window, and
makes whatever it leaves out cheap to get back.

## The problem

Agents like Claude Code keep memory as a directory of small Markdown files plus
an index, `MEMORY.md`, that points at them. The index is loaded into context at
startup, so each session begins with a map of what the agent knows.

The index grows, and the loader has a limit. Current Claude Code cuts an index
past about 25KB and appends a warning saying how many lines were lost. Earlier
versions cut it silently, which is how qhaway began: a 36.8KB, 137-entry index
against a ~24.4KB limit, with the newest section, including the pointer to the
latest state, past the cut. Claude Desktop's Cowork reads far less; a Cowork
session reported about 3.5KB.

A warning doesn't bring back what was cut. The cut is positional: whatever comes
first is kept, and in an index that grows at the bottom, the newest entries are
the ones lost. The agent can go looking, but with only the files that means
searching and reading them, and whatever a search pulls in stays in context for
the rest of the session. On one real store (85 memories, 239KB), reading the
files that mention a single topic cost 43–46KB, about twice the whole budgeted
index.

## The approach

Memory is a trade between forgetting and recall. qhaway deletes nothing; the aim
is to make getting something back, when it's needed, cheaper than carrying it
all session. qhaway works both sides of that trade:

- **It chooses what to carry.** qhaway regenerates `MEMORY.md` from the memory
  files, within the loader's budget. User and feedback memories come first, then
  the rest by recency. A memory that another has superseded is set aside instead
  of taking space.
- **It says what it holds.** The first line gives the size of what's loaded:
  `72 matching memories; all shown.` or
  `72 matching memories, 24,150 bytes in full; showing 70.` A complete index says
  so, rather than leaving the reader to infer it from a missing warning.
- **It makes a miss cheap.** The footer counts the memories left out, by type,
  and names the call that shows them:

  ```
  +60 project memories not shown; `recall(type="project")`
  Or search titles and descriptions: `recall(query="...")`
  ```

  On the store above, `recall(query="arango")` returns the one memory about it
  in 521 bytes, and `recall(limit=0)` returns only the counts, in a few hundred.
- **Files stay the write surface.** You keep writing topic `.md` files as you do
  today; there is no schema to learn. qhaway changes who writes the index (a
  machine, not a hand), and the loader reads `MEMORY.md` as before.

The figures come from one store, checked against Claude Code 2.1.284. Treat them
as an example, not a benchmark.

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

**Upgrading an install from 0.7.0 or earlier:** run
`uvx --isolated qhaway@latest init`, then restart Claude Code. Those versions
wrote hook and server commands without `--isolated`, so an installed qhaway tool
(`uv tool install`, below) kept them on that tool's version. `init` rewrites
only commands it wrote itself in their original form, and leaves a customized
entry alone with a notice. The `--isolated` in the command above matters: plain
`uvx qhaway` would run the installed tool's old `init`.

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

The Claude Code and Codex integrations run `uvx --isolated`, so an installed CLI
doesn't change which version they use.

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

- `recall(type?, role?, status?, limit?, query?)` — pure read; returns the
  budgeted projection (omit args for the working set). `query` keeps memories
  whose title, description or filename contains every term (case-insensitive;
  bodies are not searched). Its first line gives the slice's
  size: `72 matching memories; all shown.`, or the full size in bytes and how
  many are shown. `limit` caps the entries; `limit=0` returns only the counts,
  so a caller can see what a slice would cost before loading it.
- `remember(type, title, body, description?, links?, supersedes?, retracts?, retracted_claim?)`
  — writes a topic file then reconciles. Pass `supersedes` naming the memory
  this one retires, and recall demotes the loser. When an earlier memory's claim
  was *wrong*, pass `retracts` instead: the earlier memory stays visible, its
  line marked `[retracted](<this file>)`, and a `retracted_claim` quoted exactly
  is struck through wherever it appears in that line. Files stay truth; the DB
  is a derived, rebuildable view.

You don't run the server yourself — `init` wires it. Under the hood the MCP
server derives its memory directory from `CLAUDE_PROJECT_DIR` and provisions it
on first use, so a brand-new project starts ready for its first `remember()`.
(The internal commands — `qhaway serve`, `qhaway reconcile`, `qhaway check` —
exist for debugging; a normal install never invokes them by hand.)

`MEMORY.md` is written born-read-only (`0o444`) as a friction signal — not a hard
barrier — so the reflexive hand-edit is deflected toward the tools. qhaway's own
writer updates it via atomic temp-file + replace.

## Local Codex

Codex support is available on this branch for the next release:

```sh
qhaway init --host codex       # project-local connection, independent memory store
qhaway uninstall --host codex  # disconnect; preserve memories
```

Use `--dir /path/to/memory` to share an existing curated store, and `--project`
to select a project other than the current directory. Restart Codex after setup.
See [Codex setup and pilot findings](docs/codex-memory.md) for details and the
manual configuration that already works with published 0.6.0. Native Codex
memory and Claude are not required; plain `qhaway init` still targets Claude.

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

One pain, fixed completely: **an index too big for its loader**. qhaway keeps the index within budget
and makes what it sets aside cheap to get back, which is why `recall` can search
titles and descriptions. Searching bodies, deep audit, write tooling, and ranking
sophistication are deliberately *not* in this version — each is a real later
idea, none is this version's job.

The wager is simple: a structured index built *over* an existing pile of files —
without replacing the pile — makes the whole thing measurably work better. The
proof is use. If it removes felt pain for skeptical users who'll drop it the moment
it's more friction than value, it ships; if it removes the same pain for strangers
feeling the same sprawl, it spreads. Propagation is the measurement.

## Status

Beta (`v0.7.0`). The design is specified in
[`docs/superpowers/specs/2026-06-20-qhaway-mvp-design.md`](docs/superpowers/specs/2026-06-20-qhaway-mvp-design.md).

## Contributing

Changes go through pull requests; `main` is protected and merges only when CI is
green. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup and the test-first,
separate-commits conventions the project expects. Licensed [MIT](LICENSE).
