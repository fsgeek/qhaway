"""Installed commands use `uvx --isolated`, and re-running init upgrades old ones (#31).

uvx prefers an installed tool over resolving from the index, so a user who ran
`uv tool install qhaway` (as the README suggests for the CLI) would otherwise run
the hooks and server at that tool's version forever. `--isolated` ignores
installed tools. init updates only values qhaway itself wrote in their old exact
form; anything customized is left alone, with a notice on stderr.
"""
import json
from pathlib import Path
import tomllib

import pytest

from qhaway import cli, setup

UVX = "/home/u/.local/bin/uvx"
OLD_MCP = {"command": UVX, "args": ["--python", "3.14", "qhaway", "serve"]}


def _read(p):
    return json.loads(Path(p).read_text())


def _old_settings(uvx=UVX):
    return {"theme": "dark", "hooks": {
        "SessionStart": [{"//": setup.MARKER, "hooks": [{"type": "command", "command": f"{uvx} qhaway session-start"}]}],
        "SessionEnd": [{"//": setup.MARKER, "hooks": [{"type": "command", "command": f"{uvx} qhaway session-end"}]}],
    }}


@pytest.fixture
def which(monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda cmd: UVX)


def test_fresh_install_uses_isolated(tmp_path, which):
    s, m = tmp_path / "settings.json", tmp_path / ".claude.json"
    setup.install(s, mcp_config_path=m)
    flat = json.dumps(_read(s))
    assert f"{UVX} --isolated qhaway session-start" in flat
    assert f"{UVX} --isolated qhaway session-end" in flat
    assert _read(m)["mcpServers"]["qhaway"]["args"] == ["--isolated", "--python", "3.14", "qhaway", "serve"]


def test_init_upgrades_old_commands_and_keeps_their_uvx_path(tmp_path, which):
    old_uvx = "/opt/elsewhere/uvx"
    s, m = tmp_path / "settings.json", tmp_path / ".claude.json"
    s.write_text(json.dumps(_old_settings(old_uvx)))
    m.write_text(json.dumps({"projects": {"x": 1}, "mcpServers": {
        "qhaway": {"command": old_uvx, "args": ["--python", "3.14", "qhaway", "serve"]}, "other": {"command": "o"}}}))

    assert setup.install(s, mcp_config_path=m) == "updated"

    d = _read(s)
    assert d["theme"] == "dark"
    assert d["hooks"]["SessionStart"][0]["hooks"][0]["command"] == f"{old_uvx} --isolated qhaway session-start"
    assert d["hooks"]["SessionEnd"][0]["hooks"][0]["command"] == f"{old_uvx} --isolated qhaway session-end"
    mc = _read(m)
    assert mc["mcpServers"]["qhaway"] == {"command": old_uvx, "args": ["--isolated", "--python", "3.14", "qhaway", "serve"]}
    assert mc["mcpServers"]["other"] == {"command": "o"} and mc["projects"] == {"x": 1}
    assert setup.install(s, mcp_config_path=m) == "already"


def test_customized_mcp_entry_is_left_alone_with_a_notice(tmp_path, which, capsys):
    s, m = tmp_path / "settings.json", tmp_path / ".claude.json"
    s.write_text(json.dumps(_old_settings()))
    custom = {"command": UVX, "args": ["--python", "3.14", "qhaway[reground]", "serve"]}
    m.write_text(json.dumps({"mcpServers": {"qhaway": custom}}))

    setup.install(s, mcp_config_path=m)

    assert _read(m)["mcpServers"]["qhaway"] == custom
    assert "--isolated" in capsys.readouterr().err


def test_customized_hook_command_is_left_alone_with_a_notice(tmp_path, which, capsys):
    s = tmp_path / "settings.json"
    settings = _old_settings()
    settings["hooks"]["SessionStart"][0]["hooks"][0]["command"] = f"{UVX} qhaway==0.5.0 session-start"
    s.write_text(json.dumps(settings))

    setup.install(s)

    d = _read(s)
    assert d["hooks"]["SessionStart"][0]["hooks"][0]["command"] == f"{UVX} qhaway==0.5.0 session-start"
    assert d["hooks"]["SessionEnd"][0]["hooks"][0]["command"] == f"{UVX} --isolated qhaway session-end"
    assert "--isolated" in capsys.readouterr().err


def test_cli_reports_an_update(tmp_path, which, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(_old_settings()))
    (tmp_path / ".claude.json").write_text(json.dumps({"mcpServers": {"qhaway": OLD_MCP}}))

    assert cli.main(["init"]) == 0

    assert "updated" in capsys.readouterr().out


# --- Codex --------------------------------------------------------------------


@pytest.fixture
def codex_env(tmp_path, monkeypatch, which):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    return home, project


def _codex_args(project):
    return tomllib.loads((project / ".codex/config.toml").read_text())["mcp_servers"]["qhaway"]["args"]


def test_codex_payload_uses_isolated(codex_env):
    _, project = codex_env
    assert cli.main(["init", "--host", "codex", "--project", str(project)]) == 0
    assert _codex_args(project)[0] == "--isolated"


def _write_old_codex_block(project, store, prefix=b""):
    import hashlib
    from qhaway import codex_setup
    args = ["--python", "3.14", "qhaway", "serve", "--dir", str(store)]
    payload = ("[mcp_servers.qhaway]\n"
               f"command = {json.dumps(UVX)}\n"
               f"args = {json.dumps(args)}\n"
               "startup_timeout_sec = 30\n").encode()
    digest = hashlib.sha256(payload).hexdigest().encode()
    config = project / ".codex/config.toml"
    config.parent.mkdir(exist_ok=True)
    config.write_bytes(prefix + b"\n\n" + codex_setup._START + digest + b" >>>\n" + payload + codex_setup._END)
    return config


def test_codex_init_upgrades_an_intact_old_block_for_the_same_store(codex_env):
    home, project = codex_env
    store = home / "store"
    prefix = b'model = "keep"\n'
    config = _write_old_codex_block(project, store, prefix)

    assert cli.main(["init", "--host", "codex", "--project", str(project), "--dir", str(store)]) == 0

    assert _codex_args(project) == ["--isolated", "--python", "3.14", "qhaway", "serve", "--dir", str(store.resolve())]
    assert config.read_bytes().startswith(prefix)
    assert cli.main(["uninstall", "--host", "codex", "--project", str(project)]) == 0
    assert config.read_bytes() == prefix


def test_codex_init_still_refuses_a_different_store(codex_env):
    home, project = codex_env
    config = _write_old_codex_block(project, home / "store")
    before = config.read_bytes()

    assert cli.main(["init", "--host", "codex", "--project", str(project), "--dir", str(home / "other")]) == 1
    assert config.read_bytes() == before


@pytest.mark.parametrize("custom", [
    "python -m qhaway session-start",
    "env QH=1 qhaway session-start",
    "uvx --from qhaway==0.5.0 qhaway session-start",
])
def test_only_a_uvx_executable_prefix_counts_as_the_old_form(tmp_path, which, capsys, custom):
    s = tmp_path / "settings.json"
    settings = _old_settings()
    settings["hooks"]["SessionStart"][0]["hooks"][0]["command"] = custom
    s.write_text(json.dumps(settings))

    setup.install(s)

    assert _read(s)["hooks"]["SessionStart"][0]["hooks"][0]["command"] == custom
    assert "--isolated" in capsys.readouterr().err


@pytest.mark.parametrize("uvx", ["uvx", r"C:\Users\John Smith\.local\bin\uvx.EXE", "/home/u/.local/bin/uvx"])
def test_old_forms_with_bare_windows_and_absolute_uvx_are_upgraded(tmp_path, which, uvx):
    s = tmp_path / "settings.json"
    s.write_text(json.dumps(_old_settings(uvx)))

    assert setup.install(s) == "updated"

    assert _read(s)["hooks"]["SessionStart"][0]["hooks"][0]["command"] == f"{uvx} --isolated qhaway session-start"


def test_cli_update_message_does_not_claim_an_unchanged_half(tmp_path, which, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(_old_settings()))
    custom = {"command": UVX, "args": ["--python", "3.13", "qhaway", "serve"]}
    (tmp_path / ".claude.json").write_text(json.dumps({"mcpServers": {"qhaway": custom}}))

    assert cli.main(["init"]) == 0

    out = capsys.readouterr().out
    assert "updated" in out and "MCP server" not in out
