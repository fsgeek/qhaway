"""Derive Claude Code's per-project memory dir from CLAUDE_PROJECT_DIR.

Single source of truth for WHERE memory lives. Every command that needs the
memory dir without an explicit --dir (serve, the session-start reconcile, the
session-end exit) routes through here, so the hooks and the MCP server can never
point at different directories — the split brain the init plan would otherwise
introduce. See the project memory
init-resolves-split-brain-serve-must-derive-the-slug-dir-not-accept-a-hardcoded-dir.

Slug rule, read from the Claude Code 2.1.283 binary (2026-09-27): every
character outside [a-zA-Z0-9] — counted in UTF-16 code units, as JavaScript
does — becomes "-"; a slug over 200 units is cut to 200 and suffixed with "-"
plus base36(|hash|) of the original path. CC does not hand hooks or MCP servers
the memory dir (only CLAUDE_PROJECT_DIR), so matching the rule exactly is the
interface. Known limit: a user-scope `autoMemoryDirectory` setting relocates
CC's auto-memory and is not followed here.

qhaway's rule before 0.5.3 replaced only "/", so paths containing "_", ".",
spaces, or any Windows path derived a directory CC does not use. resolve()
adopts such legacy-rule stores into CC's directory on first touch.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_SLUG_MAX = 200
_NON_ALNUM = re.compile(r"[^a-zA-Z0-9]")


def _utf16_units(text: str) -> list[str]:
    raw = text.encode("utf-16-le", "surrogatepass")
    return [raw[i:i + 2].decode("utf-16-le", "surrogatepass") for i in range(0, len(raw), 2)]


def _js_hash(text: str) -> int:
    h = 0
    for unit in _utf16_units(text):
        h = ((h << 5) - h + ord(unit)) & 0xFFFFFFFF
    return h - (1 << 32) if h >= 1 << 31 else h


def _base36(n: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        n, r = divmod(n, 36)
        out = digits[r] + out
        if n == 0:
            return out


def cc_slug(project_dir: str) -> str:
    """Claude Code's project-directory name for an absolute project path."""
    slug = "".join(_NON_ALNUM.sub("-", u) for u in _utf16_units(project_dir))
    if len(slug) <= _SLUG_MAX:
        return slug
    return f"{slug[:_SLUG_MAX]}-{_base36(abs(_js_hash(project_dir)))}"


def memory_dir_for(project_dir: str, home: Path | None = None) -> Path:
    """Map an absolute project path to its Claude Code memory dir."""
    home = home if home is not None else Path.home()
    return home / ".claude" / "projects" / cc_slug(project_dir) / "memory"


def resolve(project_dir: str, home: Path | None = None) -> Path:
    """memory_dir_for, after adopting any store the pre-0.5.3 rule left behind."""
    current = memory_dir_for(project_dir, home=home)
    legacy = current.parent.parent / project_dir.replace("/", "-") / "memory"
    if legacy != current and legacy.is_dir():
        _adopt(legacy, current)
    return current


def _adopt(legacy: Path, current: Path) -> None:
    """Move every legacy entry whose name is free in the current dir. Never
    overwrites, never deletes a file: collisions stay behind and are declared
    on stderr (never stdout — that is hook context / the MCP stream)."""
    current.mkdir(parents=True, exist_ok=True)
    for entry in legacy.iterdir():
        target = current / entry.name
        if target.exists():
            continue
        try:
            os.rename(entry, target)
        except FileNotFoundError:
            pass  # a concurrent resolve() moved it first
    left = sorted(e.name for e in legacy.iterdir())
    if left:
        sys.stderr.write(
            f"qhaway: {len(left)} file(s) in {legacy} collide with {current} "
            f"and were left in place: {', '.join(left)}\n"
        )
        return
    for d in (legacy, legacy.parent):
        try:
            d.rmdir()
        except OSError:
            break  # not empty (CC's own files) or already gone


def derive_from_env(environ, home: Path | None = None) -> Path | None:
    """Return the memory dir from CLAUDE_PROJECT_DIR, or None if it is unset."""
    project_dir = environ.get("CLAUDE_PROJECT_DIR")
    if not project_dir:
        return None
    return resolve(project_dir, home=home)


def has_memory(memory_dir: Path) -> bool:
    """True iff the dir exists and holds at least one topic .md file. A lone
    MEMORY.md (or MEMORY.* artifact) with no topic files is NOT "has memory"."""
    if not memory_dir.is_dir():
        return False
    for entry in memory_dir.glob("*.md"):
        if entry.is_file() and not entry.name.startswith("MEMORY"):
            return True
    return False
