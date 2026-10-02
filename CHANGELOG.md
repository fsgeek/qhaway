# Changelog

All notable changes to qhaway are listed here; every version is published on [PyPI](https://pypi.org/project/qhaway/).

## [Unreleased]

### Added

- The local event log (`events.jsonl` in the memory directory, metadata only) now records each session-start delivery (characters, budget, and the memories left out, by type), and records `recall`'s `query`, `limit`, left-out counts and first line (so a recall that found nothing is visible). Events from one MCP server process share a session id, so repeated questions within a session can be seen. These are the measurements that would have shown [#46](https://github.com/fsgeek/qhaway/issues/46), and that should guide what session-start carries. Nothing leaves the machine.

### Changed

- Session-start picks the five newest project (non-guidance) memories before user and feedback memories, so standing guidance can no longer fill the 9,000-character hook budget and crowd out the latest handoff ([#46](https://github.com/fsgeek/qhaway/issues/46)). The display order is unchanged, and whatever doesn't fit is still counted in the footer.
- Without `--dir`, `QHAWAY_MEMORY_DIR` or Claude Code's `CLAUDE_PROJECT_DIR`, commands such as `serve` used to derive a store under `~/.claude` from the current directory, creating it if needed. When there is no `~/.claude` (the user doesn't run Claude Code, e.g. `serve` under OpenCode), they now exit with status 2 and ask for `--dir` instead of putting memory inside another tool's directory.

### Fixed

- Memories whose `type` is nested under `metadata:` (the frontmatter Claude Code writes) are now typed correctly. qhaway read only a top-level `type:`, so these feedback, user and reference memories were indexed as project memories: they lost their section and their priority, and were the first to be dropped when the index overflowed. On one real store, 17 of 29 feedback memories had been misfiled. The index version is now 4, so existing indexes are rebuilt once to reclassify unchanged files.
- The session-start index now fits Claude Code's 10,000-character limit on hook output ([#46](https://github.com/fsgeek/qhaway/issues/46)). It was sized for the ~24KB `MEMORY.md` loader, so on any store that overflowed, Claude Code saved it to a file and showed the model a 2,000-character preview without the omissions footer or the `recall` pointers. Session-start and `reconcile --emit` (the plugin's hook) now use a 9,000-byte budget; `--budget` still overrides `--emit`. Both log their deliveries.
- The uninstall command `init` prints, and the README's, now include `--isolated`. Without it, `uvx` runs an installed qhaway tool's own (possibly older) `uninstall`, which may not recognize the commands a newer `init` wrote.
- An older qhaway no longer deletes the index a newer qhaway wrote ([#37](https://github.com/fsgeek/qhaway/issues/37)). A schema mismatch used to mean "delete and rebuild" in both directions, so two versions sharing a store took turns destroying each other's index. Now a newer-than-known index is left untouched: the older version reads the topic files into an in-memory index for that call and prints a one-time notice suggesting an upgrade. An older index is still rebuilt. This protects indexes written by releases after this one. A rebuild also re-checks under its lock, so an index upgraded by another process after this one decided to rebuild is left alone too.

## [0.7.2] - 2026-09-30

### Fixed

- `init` and `uninstall` recognize qhaway's hooks by their command, not only by the `"//": "qhaway-managed"` marker. Something can rewrite `~/.claude/settings.json` and drop that marker (seen on a real machine). When it had, re-running `init` (as the 0.7.1 upgrade instructions say to) appended a second pair of hooks, loading memory twice per session, and `uninstall` left the old pair behind. Now an unmarked old-form hook is upgraded in place, and `uninstall` removes qhaway's commands while keeping other hooks in the same block. If you ran `init` on 0.7.1 and have duplicate qhaway hooks, run `uvx --isolated qhaway@latest uninstall`, then `uvx --isolated qhaway@latest init`.

## [0.7.1] - 2026-09-30

### Fixed

- The hooks, the Claude MCP server entry and the Codex server entry now run `uvx --isolated` ([#31](https://github.com/fsgeek/qhaway/issues/31)). Without it, uvx prefers an installed qhaway tool (`uv tool install qhaway`, the README's route for the CLI) over the package index, so anyone with the tool installed kept running the integration at that tool's version. Re-running `init` upgrades commands qhaway itself wrote in their original form and leaves customized entries unchanged, with a notice. To upgrade: `uvx --isolated qhaway@latest init` (and `--host codex` for Codex projects).

## [0.7.0] - 2026-09-30

### Added

- `init` / `install --host codex` connects one local Codex project to curated
  memory, independently of Claude. `--project` selects the project and `--dir`
  selects a shared or separate store; the default lives under `~/.qhaway`.
  `uninstall --host codex` removes only unchanged managed configuration and
  leaves memories and unrelated settings intact. Empty generated configuration
  is removed on uninstall; locks live outside the project.
- CI checks Codex configuration and real MCP read/write using the installed
  wheel on Linux, macOS, and Windows, without model API credentials.
- Retractions ([#27](https://github.com/fsgeek/qhaway/issues/27)). A memory with `retracts:` (a slug, `[[wikilink]]` or list, like `supersedes:`) marks an earlier memory's claim as wrong without hiding it. The earlier memory keeps its line in every projection, with `[retracted](<retraction file>)` appended, and an optional `retracted_claim:` quoted exactly is struck through in its title and description. `remember()` accepts `retracts` and `retracted_claim`, and the MCP instructions tell instances when to retract rather than supersede. Use `supersedes` when understanding moved on; use `retracts` when a claim was wrong and later readers need to see that it was believed.

### Changed

- Updated the locked PyJWT dependency from 2.13.0 to 2.15.1 to clear the
  dependency security audit.
- MCP instructions now give the full-topic directory and describe bounded
  retrieval and revisable judgments, replacing the assertion that recalled
  memory is always "the latest word," while recognizing feedback memories as
  standing user guidance subject to current instructions. Codex uses the same
  redirect mode as Claude, avoiding an extra inline index in a shared store.
- The index database schema is now version 3. An existing index rebuilds from the memory files automatically on first use.

## [0.6.0] - 2026-09-29

### Added

- Every projection (the session-start index, `recall()`, `qhaway index`) opens with one line giving the slice's size: `72 matching memories; all shown.`, or `72 matching memories, 24,150 bytes in full; showing 70.` A complete index now says it is complete, instead of being recognizable only by a missing footer.
- `recall(query="...")` keeps memories whose title, description or filename contains every term, case-insensitively. Bodies are not searched. When a slice overflows, its footer mentions `query`; a slice that fits does not.
- `recall(limit=N)` caps the entries returned, and the footer still declares the rest. `recall(limit=0)` returns only the counts: on a 72-memory store, 340 bytes instead of about 23KB.

### Changed

- The index delivered at session start now names `recall(...)` for what it sets aside, instead of a `qhaway index` command the model reading it cannot run as written. The index written at session end, which Claude Code loads when qhaway is not running, keeps the shell command.
- The README and the PyPI summary describe the problem as it stands with current Claude Code, which now warns when it cuts an index instead of cutting silently, and state qhaway's aim: keep the index within budget and make what it sets aside cheap to get back.
- PyPI now classifies qhaway as Beta (`Development Status :: 4 - Beta`), not Pre-Alpha, and links to the repository, this changelog and the issue tracker.

## [0.5.3] - 2026-09-28

### Fixed

- qhaway now derives a project's memory directory with the same rule Claude Code uses: every non-alphanumeric character becomes `-`, and names over 200 characters are cut and suffixed with a hash (ported from Claude Code 2.1.283). Earlier versions replaced only `/`. For any project path containing `_`, `.`, a space, or non-ASCII characters, qhaway was therefore reading and writing a different directory from the one Claude Code uses.
- The first time qhaway resolves such a project, it moves any store found under the old qhaway-rule directory into the correct one. It never overwrites or deletes a file: if a name exists in both directories, the old copy stays in place and qhaway lists it on stderr.

### Known issues

- Claude Code's `autoMemoryDirectory` setting is not honored yet ([#15](https://github.com/fsgeek/qhaway/issues/15)).

## [0.5.2] - 2026-09-03

### Fixed

- When a memory declares that it supersedes one whose filename was written before the 0.5.0 slug cap (or after it), the older memory is now correctly demoted. Before this fix the edge and the filename could normalize differently and fail to match.
- The hash suffix on capped slugs is now computed from the cleaned title, so different spellings of the same long title get the same filename. As a result, a long title can produce a different filename than it did under 0.5.0 or 0.5.1.
- Filenames with month-name dates (for example `sep-3-2026`) now set the date used for ordering, so the index lists them by recency instead of alphabetically.
- On Windows, a database rebuild now waits for a short-lived open connection to close instead of failing.

## [0.5.1] - 2026-09-03

### Fixed

- `qhaway index` with no filter writes the budgeted index to `MEMORY.md` again, including the footer that declares omitted memories. Since 0.1.1 it had only printed the projection and written nothing, because the default `--status live` counted as a filter. Claude Code users did not see this, because the hooks and `serve` write the index; standalone CLI use was affected. An explicit `--type`, `--role` or `--status` filter still only prints.

## [0.5.0] - 2026-09-03

### Added

- `qhaway serve --inline-index --budget N` is for hosts that run no session hooks, such as Claude Desktop's Cowork. In this mode `MEMORY.md` is always the current budgeted index, not the redirect stub. qhaway rewrites it when the server starts and after every `remember()`. On first start the host's existing index is kept as `MEMORY.preinstall.md`. The README explains how to set it up.
- qhaway runs natively on Windows. Changes for Windows: file locking without `fcntl`, atomic replacement of the read-only index while readers have it open, and LF-only writes so the size on disk matches the byte budget.

### Changed

- **Breaking:** a CLI command run with no `--dir`, no `QHAWAY_MEMORY_DIR` and no `CLAUDE_PROJECT_DIR` no longer uses the current directory as the memory store. It uses the Claude Code memory directory for the current directory instead. If you ran `qhaway index` from inside a memory directory, pass `--dir` or set `QHAWAY_MEMORY_DIR` instead.
- Output that a model reads (the live index and `recall()` results) now tells it to call `recall(type="...")` to see omitted memories. The CLI and the session-end index still show the `qhaway index --type ...` command.

### Fixed

- `remember()` no longer fails with `ENAMETOOLONG` on very long titles. Slugs are capped at 180 bytes plus a short hash, and a trailing date is kept.

## [0.4.1] - 2026-08-10

### Fixed

- Dates in dashed kebab-case filenames (for example `2026-08-09-notes.md`) now set the date used for ordering, so those memories sort by recency.

## [0.4.0] - 2026-07-28

### Changed

- **Breaking:** qhaway now requires `mcp[cli]>=2,<3` and uses the mcp 2.0 server API. Versions 0.3.0 and earlier declared `mcp[cli]>=1.28.0` with no upper bound, so an install that pulled in mcp 2.0 could not start `serve`: mcp 2.0 removed the `FastMCP` module they import.
- The README now documents the `supersedes` parameter of `remember()`.

## [0.3.0] - 2026-06-29

### Added

- Structured `claim:` blocks in a memory can now be re-checked live when you call `recall()`. The results appear under a "Re-grounded claims" section. This requires the optional `reground` extra (`qhaway[reground]`) and a `~/.yanantin/config/db.ini`. Without either, `recall()` output is unchanged.

### Fixed

- Two processes opening a new memory database at the same moment no longer fail with a spurious "filesystem does not support WAL" error. qhaway now retries the transient lock.

The sdist now includes the MIT `LICENSE` file.

## [0.2.1] - 2026-06-29

### Fixed

- `qhaway.__version__` and the version the MCP server reports to clients now match the installed package. Before this, `__version__` was stuck at 0.1.7 in 0.1.8 through 0.2.0, and the MCP handshake reported the version of the mcp SDK.

### Added

- The MCP server sends a short instruction at connect time. It gives the qhaway version and tells the model to call `recall()` first.

## [0.2.0] - 2026-06-29

### Fixed

- `remember()` now handles several `supersedes` or `links` targets passed through MCP as a JSON array string (`'["a","b"]'`). Before this fix they were merged into one invalid target. A value that looks like a JSON array but does not parse now raises an error.

## [0.1.9] - 2026-06-29

### Added

- `remember()` accepts a `supersedes` argument (a slug, a `[[wikilink]]`, or a list of them). It writes a `supersedes:` key into the new memory's frontmatter, and `recall()` then demotes the older memory. The older memory's file is not modified.
- `qhaway check` reports live memories that another memory declares it supersedes, and exits with status 1 when it finds any.

### Changed

- `python-arango` is no longer required. It moved to the optional `reground` extra.

## [0.1.8] - 2026-06-29

### Added

- A memory can retire another by listing it under a `supersedes:` frontmatter key. `recall()` and the index then treat the retired memory like one marked `status: superseded`: it is counted in the footer, not shown.
- qhaway reads `claim:` frontmatter blocks and stores them. They had no visible effect through the CLI or the MCP tools until 0.3.0.

### Changed

- `python-arango>=8.3.3` became a required dependency. 0.1.9 made it optional again.
- The database schema moved to version 2. Existing databases are rebuilt from the memory files automatically.

## [0.1.7] - 2026-06-26

### Changed

- README only: install instructions now say to restart Claude Code after `init`, and explain that `init` also sets up the `recall`/`remember` MCP tools.

## [0.1.6] - 2026-06-26

### Added

- `qhaway install` works as an alias for `qhaway init`.

## [0.1.5] - 2026-06-25

### Fixed

- `qhaway serve` creates the memory directory if it does not exist, rather than exiting. In a new project the MCP server now starts, and the first `remember()` works.

## [0.1.4] - 2026-06-25

### Fixed

- `init` writes the absolute path to `uvx` into the hook and MCP server entries. Claude Code starts these with a minimal `PATH`, so a bare `uvx` could fail to launch.

## [0.1.3] - 2026-06-25

### Added

- `init` also registers the `recall`/`remember` MCP server in `~/.claude.json`, alongside the hooks, and `uninstall` removes it. Running `init` again on a machine that already has the hooks adds the MCP server entry. Restart Claude Code after `init` so the server loads.

## [0.1.2] - 2026-06-25

### Added

- `uvx qhaway init` installs qhaway's SessionStart/SessionEnd hooks into `~/.claude/settings.json` for all projects, and `uvx qhaway uninstall` removes them. Both can safely be run more than once and touch only qhaway's own entries. If `settings.json` is malformed, they stop with an error and leave the file unchanged.
- New `session-start` and `session-end` commands for those hooks. They find the project's memory directory from `CLAUDE_PROJECT_DIR` and do nothing in projects that have no topic files.

### Changed

- When `--dir` and `QHAWAY_MEMORY_DIR` are both unset, commands now use the memory directory derived from `CLAUDE_PROJECT_DIR`, if that variable is set.

## [0.1.1] - 2026-06-25

### Changed

- `qhaway index --type/--role/--status` now only prints the filtered slice and no longer overwrites `MEMORY.md`. The same change also stopped a bare `qhaway index` from writing anything, because the default `--status` counted as a filter. That regression lasted until 0.5.1.
- README: added instructions for running qhaway as a Claude Code plugin via `uvx`.

## [0.1.0] - 2026-06-25

Initial release. Requires Python 3.14 or later.

- `qhaway index` rebuilds `MEMORY.md` from a directory of Markdown topic files so that it always fits the loader's byte budget. Memories that do not fit are listed in a footer with the command that shows them (`--type`, `--role`, `--status`, `--budget`, `--dry-run`, `--check`).
- The index is stored in a local SQLite file (WAL mode) and rebuilt from the topic files on every run. The same files always produce the same index, byte for byte. If `MEMORY.md` was edited by hand, qhaway keeps the edited copy under a timestamped name before writing a new one.
- `qhaway serve` runs an MCP server with two tools: `recall` (read the budgeted projection) and `remember` (write a topic file, then reconcile). In this mode `MEMORY.md` becomes a read-only redirect.
- Other commands: `reconcile`, `check` (broken links, orphaned backups, overflow) and `exit`.

[0.7.2]: https://github.com/fsgeek/qhaway/releases/tag/v0.7.2
[0.7.1]: https://github.com/fsgeek/qhaway/releases/tag/v0.7.1
[0.7.0]: https://github.com/fsgeek/qhaway/releases/tag/v0.7.0
[0.6.0]: https://github.com/fsgeek/qhaway/releases/tag/v0.6.0
[0.5.3]: https://github.com/fsgeek/qhaway/releases/tag/v0.5.3
[0.5.2]: https://github.com/fsgeek/qhaway/releases/tag/v0.5.2
[0.5.1]: https://github.com/fsgeek/qhaway/releases/tag/v0.5.1
[0.5.0]: https://github.com/fsgeek/qhaway/releases/tag/v0.5.0
[0.4.1]: https://pypi.org/project/qhaway/0.4.1/
[0.4.0]: https://github.com/fsgeek/qhaway/releases/tag/v0.4.0
[0.3.0]: https://pypi.org/project/qhaway/0.3.0/
[0.2.1]: https://pypi.org/project/qhaway/0.2.1/
[0.2.0]: https://pypi.org/project/qhaway/0.2.0/
[0.1.9]: https://pypi.org/project/qhaway/0.1.9/
[0.1.8]: https://pypi.org/project/qhaway/0.1.8/
[0.1.7]: https://github.com/fsgeek/qhaway/releases/tag/v0.1.7
[0.1.6]: https://github.com/fsgeek/qhaway/releases/tag/v0.1.6
[0.1.5]: https://github.com/fsgeek/qhaway/releases/tag/v0.1.5
[0.1.4]: https://github.com/fsgeek/qhaway/releases/tag/v0.1.4
[0.1.3]: https://github.com/fsgeek/qhaway/releases/tag/v0.1.3
[0.1.2]: https://github.com/fsgeek/qhaway/releases/tag/v0.1.2
[0.1.1]: https://github.com/fsgeek/qhaway/releases/tag/v0.1.1
[0.1.0]: https://pypi.org/project/qhaway/0.1.0/
