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
