# qhaway (Claude Code plugin)

Borrowed-while-enabled memory. While enabled, qhaway delivers your
must-not-re-learn memory set at every session start and returns a current,
signed `MEMORY.md` index when the session ends.

## Requirement

[`uv`](https://docs.astral.sh/uv/) must be on your `PATH`. That is the only
prerequisite — you do **not** install qhaway, Python, or any dependencies
yourself.

The plugin invokes qhaway with `uvx`, which fetches the published `qhaway`
package and a managed Python 3.14 into an isolated, cached environment on first
use. There is no `pip install`, no venv to manage, and no system Python version
to match. If `uvx` is not found, the hooks fail loudly (and touch nothing) until
you install uv.

## Install

```sh
claude plugin install --plugin-dir /path/to/qhaway-plugin
```

The plugin ships **disabled by default** (`defaultEnabled: false`), so you opt
into the auto-running hooks by enabling it. On the first session start, `uvx`
resolves qhaway (a few seconds, once); every session afterward hits the uvx
cache and is instant.

## How resolution works

Every entry point runs through the same invocation:

```
uvx --python 3.14 qhaway <subcommand> --dir <project>/.claude/qhaway-memory
```

uvx owns interpreter and dependency resolution, so all three entry points
(`serve`, `reconcile`, `exit`) agree on one environment with no machine-specific
configuration. If qhaway or a dependency can't be resolved, the command exits
non-zero **without touching your memory directory** — it never writes a partial
`MEMORY.md`.

## Components

- `hooks/hooks.json` — SessionStart (reconcile + deliver projection) and
  SessionEnd (write the current signed index).
- `.mcp.json` — registers the `recall` / `remember` MCP server.
- `.claude-plugin/plugin.json` — manifest; ships **disabled by default**
  (`defaultEnabled: false`) so you opt into the auto-running hooks.
