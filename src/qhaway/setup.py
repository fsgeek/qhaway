"""Idempotent, non-destructive install/uninstall of qhaway's user-scope wiring.

Two files, because Claude Code reads hooks and MCP servers from different places:
- the SessionStart/SessionEnd hook block goes in ~/.claude/settings.json (the
  PUSH path — delivers the projection at boot), tagged with MARKER.
- the recall/remember MCP server goes in ~/.claude.json's top-level mcpServers
  (the PULL path — live tools), keyed "qhaway" (the key IS its identifier).
Both are user-scope so one install serves every project. Writes are atomic and
non-destructive: ~/.claude.json holds all of CC's state, so we touch only our
own key and preserve everything else."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

MARKER = "qhaway-managed"
MCP_NAME = "qhaway"


def _uvx() -> str:
    """Resolve uvx to an absolute path at install time. Claude Code spawns hooks
    and MCP servers with a minimal PATH that may lack ~/.local/bin, so a bare
    "uvx" fails to resolve under CC even though it works in an interactive shell.
    Fall back to bare "uvx" only when unresolvable (no worse than before)."""
    return shutil.which("uvx") or "uvx"


def _block(command: str) -> dict:
    return {"//": MARKER, "hooks": [{"type": "command", "command": command}]}


def _start_cmd() -> str:
    return f"{_uvx()} qhaway session-start"


def _end_cmd() -> str:
    return f"{_uvx()} qhaway session-end"


def _mcp_server() -> dict:
    # serve derives its memory dir from CLAUDE_PROJECT_DIR — no hardcoded --dir.
    return {"command": _uvx(), "args": ["--python", "3.14", "qhaway", "serve"]}


def _hooks_installed(settings: dict) -> bool:
    for blk in settings.get("hooks", {}).get("SessionStart", []):
        if isinstance(blk, dict) and blk.get("//") == MARKER:
            return True
    return False


def _mcp_installed(mcp_config: dict) -> bool:
    return MCP_NAME in mcp_config.get("mcpServers", {})


def is_installed(settings: dict, mcp_config: dict | None = None) -> bool:
    """Fully installed = hooks present AND, when an MCP config is given, the MCP
    server present. Called with only `settings` (the hooks file), reports the
    hooks half — preserving the original single-arg contract."""
    if not _hooks_installed(settings):
        return False
    if mcp_config is None:
        return True
    return _mcp_installed(mcp_config)


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path} is not valid JSON ({exc}); qhaway left it untouched."
        ) from exc


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


def install(settings_path: Path, mcp_config_path: Path | None = None) -> str:
    """Wire the hooks (settings_path) and, when mcp_config_path is given, the MCP
    server. Each half writes only if missing, so a machine with hooks already
    present still gets the MCP completed (returns "installed", not "already").
    Returns "already" only when every requested half was already present."""
    did_work = False

    settings = _load(settings_path)
    if not _hooks_installed(settings):
        hooks = settings.setdefault("hooks", {})
        hooks.setdefault("SessionStart", []).append(_block(_start_cmd()))
        hooks.setdefault("SessionEnd", []).append(_block(_end_cmd()))
        _atomic_write(settings_path, settings)
        did_work = True

    if mcp_config_path is not None:
        mcp_config = _load(mcp_config_path)
        if not _mcp_installed(mcp_config):
            mcp_config.setdefault("mcpServers", {})[MCP_NAME] = _mcp_server()
            _atomic_write(mcp_config_path, mcp_config)
            did_work = True

    return "installed" if did_work else "already"


def uninstall(settings_path: Path, mcp_config_path: Path | None = None) -> str:
    """Remove both halves. Returns "removed" if anything was removed, "absent"
    if neither half was present."""
    did_work = False

    settings = _load(settings_path)
    if _hooks_installed(settings):
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
        did_work = True

    if mcp_config_path is not None:
        mcp_config = _load(mcp_config_path)
        if _mcp_installed(mcp_config):
            del mcp_config["mcpServers"][MCP_NAME]
            _atomic_write(mcp_config_path, mcp_config)
            did_work = True

    return "removed" if did_work else "absent"
