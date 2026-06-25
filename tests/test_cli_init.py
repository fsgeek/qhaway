import os, json
from pathlib import Path
from qhaway import cli


def _run(args, home):
    old = dict(os.environ)
    os.environ["HOME"] = str(home)
    try:
        return cli.main(args)
    finally:
        os.environ.clear(); os.environ.update(old)


def test_init_writes_settings(tmp_path, capsys):
    assert _run(["init"], tmp_path) == 0
    s = tmp_path / ".claude/settings.json"
    assert s.exists()
    assert "qhaway session-start" in s.read_text()
    assert "installed" in capsys.readouterr().out.lower()


def test_init_idempotent(tmp_path, capsys):
    _run(["init"], tmp_path); capsys.readouterr()
    assert _run(["init"], tmp_path) == 0
    assert "already" in capsys.readouterr().out.lower()


def test_uninstall_removes(tmp_path, capsys):
    _run(["init"], tmp_path); capsys.readouterr()
    assert _run(["uninstall"], tmp_path) == 0
    s = tmp_path / ".claude/settings.json"
    assert "qhaway" not in s.read_text()
    assert "removed" in capsys.readouterr().out.lower()


def test_uninstall_when_absent(tmp_path, capsys):
    assert _run(["uninstall"], tmp_path) == 0
    assert "not installed" in capsys.readouterr().out.lower()
