"""Idempotent, non-destructive install/uninstall of qhaway's user-scope
SessionStart/SessionEnd hook block in ~/.claude/settings.json. The block is
tagged with MARKER so uninstall removes exactly it and nothing else."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

MARKER = "qhaway-managed"


def _block(command: str) -> dict:
    return {"//": MARKER, "hooks": [{"type": "command", "command": command}]}


_START = "uvx qhaway session-start"
_END = "uvx qhaway session-end"


def is_installed(settings: dict) -> bool:
    for blk in settings.get("hooks", {}).get("SessionStart", []):
        if isinstance(blk, dict) and blk.get("//") == MARKER:
            return True
    return False


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2) + "\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def install(settings_path: Path) -> str:
    settings = _load(settings_path)
    if is_installed(settings):
        return "already"
    hooks = settings.setdefault("hooks", {})
    hooks.setdefault("SessionStart", []).append(_block(_START))
    hooks.setdefault("SessionEnd", []).append(_block(_END))
    _atomic_write(settings_path, settings)
    return "installed"


def uninstall(settings_path: Path) -> str:
    settings = _load(settings_path)
    if not is_installed(settings):
        return "absent"
    for event in ("SessionStart", "SessionEnd"):
        blocks = settings.get("hooks", {}).get(event, [])
        settings["hooks"][event] = [
            b for b in blocks
            if not (isinstance(b, dict) and b.get("//") == MARKER)
        ]
        if not settings["hooks"][event]:
            del settings["hooks"][event]
    if not settings.get("hooks"):
        settings.pop("hooks", None)
    _atomic_write(settings_path, settings)
    return "removed"
