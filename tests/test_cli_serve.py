"""serve must provision a not-yet-existing memory dir, not exit.

The real failure on the test box: CC launched `qhaway serve` for a project whose
slug memory dir did not exist yet (no memory ever written there). _serve's
`if not isdir: return 1` made the process exit, which CC reported as a failed
MCP connection ("✗ failed"). A fresh project must be able to start the server so
the first remember() can create its first memory — requiring memory to exist
before you can write the first memory is a dead end.
"""

from qhaway import cli, server


def test_serve_creates_missing_memory_dir_and_starts(tmp_path, monkeypatch):
    started = {}
    monkeypatch.setattr(server, "run", lambda d: started.setdefault("dir", d))
    target = tmp_path / "projects" / "-fresh-proj" / "memory"
    assert not target.exists()
    rc = cli._serve(str(target))
    assert rc == 0
    assert target.is_dir()            # provisioned, not rejected
    assert started["dir"] == str(target)  # server.run actually invoked


def test_serve_still_works_when_dir_already_exists(tmp_path, monkeypatch):
    started = {}
    monkeypatch.setattr(server, "run", lambda d: started.setdefault("dir", d))
    target = tmp_path / "memory"
    target.mkdir()
    rc = cli._serve(str(target))
    assert rc == 0
    assert started["dir"] == str(target)
