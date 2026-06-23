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
    assert "${CLAUDE_PROJECT_DIR}" in flat             # per-project memory dir


def test_mcp_json_registers_server():
    j = json.loads((ROOT / ".mcp.json").read_text())
    server = j["mcpServers"]["qhaway"]
    assert server["command"] == "${CLAUDE_PLUGIN_ROOT}/bin/qhaway"
    assert "serve" in server["args"]
    assert "${CLAUDE_PROJECT_DIR}/.claude/qhaway-memory" in server["args"]
