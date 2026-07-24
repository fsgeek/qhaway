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


def test_install_is_an_alias_for_init(tmp_path, capsys):
    # install/uninstall are the complementary pair users reach for; install
    # must do exactly what init does.
    assert _run(["install"], tmp_path) == 0
    s = tmp_path / ".claude/settings.json"
    assert s.exists()
    assert "qhaway session-start" in s.read_text()
    assert "installed" in capsys.readouterr().out.lower()


def test_install_alias_is_idempotent_with_init(tmp_path, capsys):
    _run(["install"], tmp_path); capsys.readouterr()
    # init sees the install-alias's work as already done — same install path
    assert _run(["init"], tmp_path) == 0
    assert "already" in capsys.readouterr().out.lower()
