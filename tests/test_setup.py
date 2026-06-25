import json
from pathlib import Path
from qhaway import setup


def _read(p): return json.loads(Path(p).read_text())


def test_install_into_absent_file(tmp_path):
    s = tmp_path / "settings.json"
    assert setup.install(s) == "installed"
    d = _read(s)
    assert setup.is_installed(d)
    # both hooks present, invoking uvx qhaway session-*
    flat = json.dumps(d)
    assert "session-start" in flat and "session-end" in flat
    assert setup.MARKER in flat


def test_install_is_idempotent(tmp_path):
    s = tmp_path / "settings.json"
    setup.install(s)
    before = s.read_text()
    assert setup.install(s) == "already"
    assert s.read_text() == before  # byte-identical, no rewrite


def test_install_preserves_unrelated_settings(tmp_path):
    s = tmp_path / "settings.json"
    s.write_text(json.dumps({"theme": "dark", "hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": "echo other"}]}]}}))
    setup.install(s)
    d = _read(s)
    assert d["theme"] == "dark"
    # the pre-existing non-qhaway hook survives alongside ours
    cmds = [h["command"] for blk in d["hooks"]["SessionStart"] for h in blk["hooks"]]
    assert "echo other" in cmds
    assert any("qhaway session-start" in c for c in cmds)


def test_uninstall_removes_only_qhaway(tmp_path):
    s = tmp_path / "settings.json"
    s.write_text(json.dumps({"theme": "dark", "hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": "echo other"}]}]}}))
    setup.install(s)
    assert setup.uninstall(s) == "removed"
    d = _read(s)
    assert d["theme"] == "dark"
    cmds = [h["command"] for blk in d["hooks"].get("SessionStart", []) for h in blk["hooks"]]
    assert "echo other" in cmds
    assert not any("qhaway" in c for c in cmds)
    assert not setup.is_installed(d)


def test_uninstall_when_absent(tmp_path):
    s = tmp_path / "settings.json"
    s.write_text(json.dumps({"theme": "dark"}))
    assert setup.uninstall(s) == "absent"


import pytest


def test_install_on_malformed_settings_raises_and_preserves(tmp_path):
    s = tmp_path / "settings.json"
    s.write_text("{ not valid json ")
    with pytest.raises(ValueError):
        setup.install(s)
    assert s.read_text() == "{ not valid json "  # untouched


# --- MCP server registration (the second half of a complete install) ---


def test_install_registers_mcp_server(tmp_path):
    s = tmp_path / "settings.json"
    m = tmp_path / ".claude.json"
    setup.install(s, mcp_config_path=m)
    d = _read(m)
    assert "qhaway" in d["mcpServers"]
    server = d["mcpServers"]["qhaway"]
    # command is uvx, resolved to an absolute path when on PATH (CC spawns with a
    # minimal PATH); bare "uvx" only as the unresolvable fallback.
    assert server["command"].endswith("uvx")
    assert "serve" in server["args"]
    # no hardcoded --dir: serve derives the slug dir from CLAUDE_PROJECT_DIR
    assert "--dir" not in server["args"]


def test_mcp_install_preserves_other_servers_and_keys(tmp_path):
    s = tmp_path / "settings.json"
    m = tmp_path / ".claude.json"
    m.write_text(json.dumps({
        "mcpServers": {"serena": {"command": "serena-mcp"}},
        "projects": {"/some/proj": {"history": ["x"]}},
        "numStartups": 42,
    }))
    setup.install(s, mcp_config_path=m)
    d = _read(m)
    assert d["mcpServers"]["serena"] == {"command": "serena-mcp"}  # untouched
    assert d["projects"] == {"/some/proj": {"history": ["x"]}}      # untouched
    assert d["numStartups"] == 42                                  # untouched
    assert "qhaway" in d["mcpServers"]                              # added


def test_is_installed_requires_both_hooks_and_mcp(tmp_path):
    s = tmp_path / "settings.json"
    m = tmp_path / ".claude.json"
    # hooks only (the shipped-0.1.2 state): NOT fully installed
    setup.install(s)  # hooks-only, no mcp path
    assert setup.is_installed(_read(s), _read(m) if m.exists() else {}) is False
    # now add mcp: fully installed
    setup.install(s, mcp_config_path=m)
    assert setup.is_installed(_read(s), _read(m)) is True


def test_install_completes_mcp_when_hooks_already_present(tmp_path):
    # The real-machine case: hooks installed by 0.1.2, mcp missing.
    # Re-running init must COMPLETE the mcp half, not no-op.
    s = tmp_path / "settings.json"
    m = tmp_path / ".claude.json"
    setup.install(s)                          # hooks only (simulates 0.1.2)
    assert "qhaway" not in _read(m).get("mcpServers", {}) if m.exists() else True
    result = setup.install(s, mcp_config_path=m)
    assert result == "installed"              # did work, not "already"
    assert "qhaway" in _read(m)["mcpServers"]


def test_uninstall_removes_mcp_server_too(tmp_path):
    s = tmp_path / "settings.json"
    m = tmp_path / ".claude.json"
    m.write_text(json.dumps({"mcpServers": {"serena": {"command": "x"}}}))
    setup.install(s, mcp_config_path=m)
    assert setup.uninstall(s, mcp_config_path=m) == "removed"
    d = _read(m)
    assert "qhaway" not in d["mcpServers"]
    assert d["mcpServers"]["serena"] == {"command": "x"}  # other server kept


# --- PATH resolution: CC spawns hooks/MCP with a minimal PATH that may lack
# ~/.local/bin, so a bare "uvx" command fails to resolve. install must write the
# absolute path resolved at install time (when qhaway's own PATH is correct). ---


def test_mcp_command_is_absolute_uvx_path(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda cmd: "/home/u/.local/bin/uvx")
    s = tmp_path / "settings.json"
    m = tmp_path / ".claude.json"
    setup.install(s, mcp_config_path=m)
    server = _read(m)["mcpServers"]["qhaway"]
    assert server["command"] == "/home/u/.local/bin/uvx"


def test_hook_commands_use_absolute_uvx_path(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda cmd: "/home/u/.local/bin/uvx")
    s = tmp_path / "settings.json"
    setup.install(s)
    flat = json.dumps(_read(s))
    assert "/home/u/.local/bin/uvx qhaway session-start" in flat
    assert "/home/u/.local/bin/uvx qhaway session-end" in flat


def test_falls_back_to_bare_uvx_when_unresolvable(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda cmd: None)
    s = tmp_path / "settings.json"
    m = tmp_path / ".claude.json"
    setup.install(s, mcp_config_path=m)
    assert _read(m)["mcpServers"]["qhaway"]["command"] == "uvx"
    assert "uvx qhaway session-start" in json.dumps(_read(s))
