# qhaway threat model

*2026-09-03. Written against 0.5.1. Revisit when a trust boundary changes —
a new write surface, a network connection, a new host.*

## What qhaway is, adversarially

A local tool that turns a directory of Markdown files into an SQLite index and
a budgeted `MEMORY.md` projection, and serves `recall`/`remember` over stdio
MCP. No network listener, no credentials of its own, no state outside the
memory directory except the two Claude Code config files `init` manages.

The interesting risk is not code execution — it is that **qhaway's output
becomes model context**. Memory is an instruction channel to a future session.

## Trust boundaries

### 1. Topic files (the write surface) — untrusted input
Written by models via `remember()`, by hand, by other tools (Cowork writes
here). The parser treats them as data: `yaml.safe_load` only (no object
construction), tolerant fallback on malformed frontmatter, parse failures
degrade to warnings, never crashes that block boot. A hostile file cannot make
the parser execute anything; it can only put text into the index.

### 2. The projection → model context — the real attack surface
`MEMORY.md` and `recall()` output are injected into an agent's context at boot
or on request. **A memory is a durable prompt injection with a delay timer**: a
poisoned `remember()` today shapes an instance weeks later, long after the
session that wrote it is gone. qhaway deliberately does not try to detect
"malicious" content — it cannot, and pretending would be worse than the honest
position:

- qhaway **preserves provenance** (files are truth, git history where the
  store is a repo, `origin_session` frontmatter, the events log) so poisoning
  is auditable after the fact;
- **supersession demotes, never deletes** — a poisoned correction can itself
  be corrected, and the loser stays on disk;
- the write path is **append-only with exclusive creation** (`O_EXCL`):
  `remember()` cannot silently overwrite an existing memory.

Residual risk accepted: a model with `remember()` can write memories that
mislead its successors. The mitigation is the reviewability of the store, not
input filtering. Operators who need more should put the memory directory under
git and review diffs.

### 3. The MCP boundary
`serve` speaks stdio to the host that spawned it; there is no socket, so the
attack surface is "whoever can already run processes as you." The memory
directory is derived from `CLAUDE_PROJECT_DIR`/cwd through the slug rule, or
set explicitly by the operator via `--dir`; `remember()` titles cannot steer
file placement — `slugify` strips every character outside `[\w-]`, so
path-shaped titles (`../../x`) cannot escape the store. Protocol errors go to
stderr, never stdout (a corrupted stdout frame is a host-side failure mode).

### 4. The installer — highest privilege operation
`init`/`uninstall` edit `~/.claude/settings.json` (hooks) and `~/.claude.json`
(MCP servers): the hook line it installs runs at every session start, so this
is the one place qhaway could persist arbitrary command execution. Mitigations:
the installed command is built from `shutil.which("uvx")` at install time (no
PATH lookup at run time), blocks are marker-tagged (`qhaway-managed`) and only
those blocks are ever removed, writes are atomic (temp + rename), invalid JSON
aborts the edit untouched, and install/uninstall are a documented reversible
pair. Residual risk: anything that can edit those files can do this without
qhaway's help.

### 5. Local artifacts
The SQLite db is derived and rebuildable — deleting it loses nothing; drift
triggers a from-files rebuild. `events.jsonl` records **metadata only, never
the body** (verb, type, title, sizes, session id) — by design, so observability
does not become a second copy of the corpus. `MEMORY.md` is written `0o444` as
a friction signal, documented as a signal and not a barrier.

### 6. Supply chain
Two runtime dependencies (`mcp`, `pyyaml`), locked; CI audits the lock
(pip-audit), the source (bandit), and the workflows (zizmor) on every PR, on
pinned tool versions. Actions are pinned to commit SHAs; release builds refuse
caches; publishing to real PyPI is manual by decision (see
`.github/workflows/release.yml` for the controls required before that changes).

### 7. The `[reground]` extra
Optional ArangoDB client for claim re-grounding. qhaway never imports the DB
layer in core; the provider is discovered at serve time from an operator-owned
`db.ini`. Credentials are the operator's, stored outside this project.

## Non-goals
qhaway does not authenticate callers (the host does), does not encrypt at rest
(the store is the operator's plaintext by design — files-as-truth), and does
not classify memory content. Each would add a trust story qhaway cannot keep.
