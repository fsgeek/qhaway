import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "qhaway-plugin"


def test_manifest_ships_off():
    m = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert m["name"] == "qhaway"
    assert m.get("defaultEnabled") is False


def test_hooks_register_sessionstart_and_sessionend():
    h = json.loads((ROOT / "hooks" / "hooks.json").read_text())
    events = h["hooks"]
    assert "SessionStart" in events and "SessionEnd" in events
    flat = json.dumps(h)
    assert "reconcile" in flat and "--emit" in flat  # start delivers
    assert "exit" in flat                              # end writes index
    assert "uvx" in flat                               # resolved via uvx
    assert "--python" in flat and "3.14" in flat       # pinned interpreter
    # No hardcoded --dir: the commands derive the slug dir from CLAUDE_PROJECT_DIR
    # themselves, so hooks and the MCP server can never point at different dirs.
    assert "qhaway-memory" not in flat
    assert "--dir" not in flat


def test_mcp_json_registers_server():
    j = json.loads((ROOT / ".mcp.json").read_text())
    server = j["mcpServers"]["qhaway"]
    assert server["command"] == "uvx"
    args = server["args"]
    # The deployed server pulls the [reground] extra so a claim re-grounds live on
    # recall (python-arango is the only thing the extra adds; default_provider
    # self-gates on db.ini, so a storeless box still recalls byte-identically).
    assert args[:4] == ["--python", "3.14", "qhaway[reground]", "serve"]
    # No hardcoded --dir: serve derives the slug dir from CLAUDE_PROJECT_DIR.
    assert "--dir" not in args
    assert not any("qhaway-memory" in a for a in args)
