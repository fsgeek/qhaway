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

> **Recommended:** for most users, `uvx qhaway init` is the simpler path — it
> wires qhaway into Claude Code at user scope (no clone, no per-session flag) and
> activates in any project that has memory. This plugin is the per-session,
> load-from-a-checkout alternative.

You don't install the plugin to a location — you point Claude Code at the
directory where it already lives. Clone the repo, then launch with
`--plugin-dir`:

```sh
git clone https://github.com/fsgeek/qhaway
claude --plugin-dir qhaway/qhaway-plugin
```

`--plugin-dir` loads the plugin **for that session** from the given directory
(it does not copy or register it anywhere). The plugin ships **disabled by
default** (`defaultEnabled: false`), so enable it from `/plugin` to opt into the
auto-running hooks. On the first session start, `uvx` resolves qhaway (a few
seconds, once); every session afterward hits the uvx cache and is instant.

To turn it off, disable it from `/plugin` — the hooks stop firing and your
`MEMORY.md` is left as a plain, self-sufficient index.

## How resolution works

Every entry point runs through the same invocation:

```
uvx --python 3.14 qhaway <subcommand>
```

Each entry point derives its memory dir from `CLAUDE_PROJECT_DIR` at runtime, so
`serve`, `reconcile`, and `exit` always agree on one directory with no hardcoded
path to go stale.

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
