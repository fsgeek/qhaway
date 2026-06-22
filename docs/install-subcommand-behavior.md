# `qhaway install` behavior sketch

> **SUPERSEDED 2026-06-22 by `docs/qhaway-as-plugin-design.md`.** qhaway ships as
> a Claude Code PLUGIN; the harness owns install/enable/disable/uninstall. The
> config-mutating `install`/`uninstall` CLI verbs below (surgical merge into
> settings.local.json/.mcp.json, marker, reversible MEMORY.md exit driven by our
> own code) are RETIRED. The SAFE core here (create memory dir, reconcile, heal
> redirect) survives, folded into the plugin's SessionStart first-touch path.
> Read the plugin design first; this remains only for the rationale of the safe
> core.

Status: pre-code review sketch (superseded). The current CLI has no `install`
subcommand; this defined behavior to check before implementing it.

## Scope

`qhaway install [--dir <memory_dir>] [--yes] [--no-gitignore]`

`install` prepares one local memory directory for `serve`, `reconcile`, `recall`,
and `remember`. It is not a package installer and does not edit external
Claude/MCP client configuration.

Resolve the directory the same way as the current human-facing CLI:

1. `--dir <memory_dir>`
2. `QHAWAY_MEMORY_DIR`
3. `.`

If the path is missing, ask whether to create it. If it exists but is not a
directory, fail without writing.

## Ordered Steps

1. Read current state:
   - topic files: `*.md` except `MEMORY.md` and `MEMORY-*.md`
   - optional `REDIRECT.md`
   - `MEMORY.md`
   - `.qhaway.json`
   - `.qhaway.db`
   - optional `.gitignore`
2. Build a mutation preview: directory creation, DB/schema creation or rebuild,
   redirect write/repair, sidecar write/repair, possible `MEMORY-<timestamp>.md`
   preservation, and optional `.gitignore` update.
3. Ask for consent before the first mutation unless `--yes` was passed. A no
   answer exits `2` and writes nothing.
4. Reconcile using the existing pipeline:
   - open SQLite in WAL mode
   - create the current schema if absent
   - rebuild on detected schema drift
   - parse topic files into `nodes` and wikilinks into `edges`
   - delete DB rows for topic files no longer present
   - commit DB changes before touching `MEMORY.md`
5. Heal `MEMORY.md` using existing redirect rules:
   - if it already equals the desired redirect, keep it and repair `.qhaway.json`
   - if it differs from both the recorded hash and desired redirect, rename it to
     `MEMORY-<timestamp>.md`
   - atomically replace it with a read-only (`0444`) managed redirect
   - write `.qhaway.json` with version `1` and the redirect hash
6. Ask separately before editing `.gitignore`, unless `--yes` or
   `--no-gitignore` was passed. Add `.qhaway.db`, `.qhaway.db-wal`,
   `.qhaway.db-shm`, and `.qhaway.db.reset.lock`. A no answer skips only this
   step.
7. Run post-install checks: low topic count warning, orphan backup report,
   dangling wikilink failure, and projection budget overflow failure.
8. Exit `0` only if initialization/reconcile completed and post-install checks
   have no failures. Warnings do not change the exit code.

## Writes

Depending on current state, `install` may write:

- `.qhaway.db`
- `.qhaway.db-wal`
- `.qhaway.db-shm`
- `.qhaway.json`
- `MEMORY.md`
- `MEMORY-<timestamp>.md`
- `.qhaway.db.reset.lock` during schema drift recovery
- `.gitignore`, only with separate consent and not with `--no-gitignore`

`install` must not write topic memory files, delete topic memory files, merge
manual `MEMORY.md` edits into topic files, or modify external MCP/client config.

## Output

Warnings and progress go to stderr. The final stdout line is a concise success
summary with the resolved directory and topic count. Failures use stderr plus a
non-zero exit, matching the existing CLI style.
