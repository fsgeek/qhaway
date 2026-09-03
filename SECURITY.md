# Security policy

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: **Security → Report a
vulnerability** on this repository. Reports go to the maintainer without a
public issue. Expect an acknowledgment within a week.

Please include the platform and filesystem (several past bugs lived exactly
there) and the smallest reproduction you can manage.

## Supported versions

Pre-1.0: only the latest release published to PyPI receives fixes.

## What qhaway touches

So you can judge exposure without reading the source: qhaway reads and writes
Markdown files and an SQLite database inside a per-project memory directory,
serves two MCP tools (`recall`/`remember`) over stdio to a host that spawns it,
and — only during explicit `init`/`uninstall` — edits `~/.claude/settings.json`
and `~/.claude.json` (marker-tagged blocks, atomic writes, everything else
preserved). It makes no network connections. The optional `[reground]` extra
connects to an ArangoDB you configure. The full analysis is in
[`docs/threat-model.md`](docs/threat-model.md).
