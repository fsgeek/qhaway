# qhaway (Claude Code plugin)

Borrowed-while-enabled memory. While enabled, qhaway delivers your
must-not-re-learn memory set at every session start and returns a current,
signed `MEMORY.md` index when the session ends.

## Install requirement (MVP)

This plugin does **not** bundle a copy of the qhaway source. Its launcher
(`bin/qhaway`) runs the **installed** `qhaway` Python package, so that package
must be importable by the interpreter the launcher resolves.

Resolution order:

1. A venv at `${CLAUDE_PLUGIN_ROOT}/.venv` (if present) — its `python` is used.
2. Otherwise, `python3` on `PATH`.

The resolved interpreter must be able to `import qhaway` (and its dependencies
`pyyaml` and `mcp`). Install qhaway into that interpreter's environment:

```sh
pip install qhaway
```

If the package or its dependencies are not importable, the launcher prints an
error and exits non-zero **without touching your memory directory** — it never
writes a partial `MEMORY.md`. The hook will visibly fail; fix the install and
re-run.

> Requires Python ≥ 3.14 (per qhaway's `pyproject.toml`).

## Post-MVP hardening (planned)

Ship a self-contained venv with pinned dependencies at
`${CLAUDE_PLUGIN_ROOT}/.venv` so the plugin has zero external install
requirement. Until then, the install step above is required.

## Components

- `bin/qhaway` — launcher the hooks and MCP server invoke.
- `hooks/hooks.json` — SessionStart (reconcile + deliver projection) and
  SessionEnd (write the current signed index).
- `.mcp.json` — registers the `recall` / `remember` MCP server.
- `.claude-plugin/plugin.json` — manifest; ships **disabled by default**
  (`defaultEnabled: false`) so you opt into the auto-running hooks.
