"""Derive Claude Code's per-project memory dir from CLAUDE_PROJECT_DIR.

Single source of truth for WHERE memory lives. Every command that needs the
memory dir without an explicit --dir (serve, the session-start reconcile, the
session-end exit) routes through here, so the hooks and the MCP server can never
point at different directories — the split brain the init plan would otherwise
introduce. See the project memory
init-resolves-split-brain-serve-must-derive-the-slug-dir-not-accept-a-hardcoded-dir.

Verified slug rule (hamutay, governance, probe-proj): Claude Code names the
per-project dir by replacing every "/" in the project's absolute path with "-".
Only verified for plain alphanumeric path components; dots/spaces/exotic chars
untested — alpha-acceptable, PR-able.
"""

from __future__ import annotations

from pathlib import Path


def memory_dir_for(project_dir: str, home: Path | None = None) -> Path:
    """Map an absolute project path to its Claude Code memory dir."""
    home = home if home is not None else Path.home()
    slug = project_dir.replace("/", "-")
    return home / ".claude" / "projects" / slug / "memory"


def derive_from_env(environ, home: Path | None = None) -> Path | None:
    """Return the memory dir from CLAUDE_PROJECT_DIR, or None if it is unset."""
    project_dir = environ.get("CLAUDE_PROJECT_DIR")
    if not project_dir:
        return None
    return memory_dir_for(project_dir, home=home)
