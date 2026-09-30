"""Codex wiring preserves operator configuration and never depends on Claude."""
import concurrent.futures
from pathlib import Path
import tomllib

import pytest

from qhaway import cli


def install(project, *extra):
    return cli.main(['init', '--host', 'codex', '--project', str(project), *extra])


def uninstall(project):
    return cli.main(['uninstall', '--host', 'codex', '--project', str(project)])


@pytest.fixture
def environment(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    monkeypatch.delenv('CODEX_HOME', raising=False)
    project = tmp_path / 'project'
    project.mkdir()
    return home, project


def test_default_store_is_independent_and_uninstall_preserves_files(environment):
    home, project = environment
    assert install(project) == 0
    config = project / '.codex/config.toml'
    original = config.read_bytes()
    server = tomllib.loads(original.decode())['mcp_servers']['qhaway']
    args = server['args']
    store = Path(args[args.index('--dir') + 1])
    assert store.is_absolute() and store.is_relative_to(home / '.qhaway')
    assert '--inline-index' in args
    assert not (home / '.claude').exists()
    assert not (home / '.codex').exists()
    assert install(project) == 0
    assert config.read_bytes() == original
    store.mkdir(parents=True)
    (store / 'lesson.md').write_text('keep this')
    assert uninstall(project) == 0
    assert 'qhaway' not in tomllib.loads(config.read_text()).get('mcp_servers', {})
    assert (store / 'lesson.md').read_text() == 'keep this'
    assert uninstall(project) == 0


@pytest.mark.parametrize('original', [b'# personal\r\nmodel = "example"\r\n', b'model = "example"', b''])
def test_preserves_unrelated_bytes_and_custom_store(environment, original):
    home, project = environment
    config = project / '.codex/config.toml'
    config.parent.mkdir()
    config.write_bytes(original)
    store = home / 'shared "quoted" memories'
    assert install(project, '--dir', str(store)) == 0
    data = tomllib.loads(config.read_text())
    assert str(store) in data['mcp_servers']['qhaway']['args']
    assert config.read_bytes().startswith(original)
    assert install(project, '--dir', str(store)) == 0
    assert uninstall(project) == 0
    assert config.read_bytes() == original


@pytest.mark.parametrize('original', [b'not valid TOML !', b'[mcp_servers.qhaway]\ncommand="mine"\n'])
def test_refuses_invalid_or_unmanaged_config(environment, original):
    _, project = environment
    config = project / '.codex/config.toml'
    config.parent.mkdir()
    config.write_bytes(original)
    assert install(project) == 1
    assert uninstall(project) == 1
    assert config.read_bytes() == original


def test_modified_block_is_not_overwritten_or_removed(environment):
    _, project = environment
    assert install(project) == 0
    config = project / '.codex/config.toml'
    edited = config.read_bytes().replace(b'startup_timeout_sec = 30', b'startup_timeout_sec = 60')
    config.write_bytes(edited)
    assert install(project) == 1
    assert uninstall(project) == 1
    assert config.read_bytes() == edited


def test_changed_store_requires_deliberate_removal(environment):
    home, project = environment
    assert install(project) == 0
    config = project / '.codex/config.toml'
    original = config.read_bytes()
    assert install(project, '--dir', str(home / 'other')) == 1
    assert config.read_bytes() == original


def test_project_scopes_do_not_share_default_store(environment):
    home, project = environment
    other = project.parent / 'other'
    other.mkdir()
    assert install(project) == install(other) == 0
    def args(p):
        return tomllib.loads((p / '.codex/config.toml').read_text())['mcp_servers']['qhaway']['args']
    assert args(project) != args(other)


def test_codex_installer_does_not_replace_existing_guidance(environment):
    _, project = environment
    (project / 'AGENTS.md').write_text('existing guidance')
    (project / 'AGENTS.override.md').write_text('existing local guidance')
    assert install(project) == 0
    assert (project / 'AGENTS.md').read_text() == 'existing guidance'
    assert (project / 'AGENTS.override.md').read_text() == 'existing local guidance'


def test_concurrent_installs_are_idempotent(environment):
    _, project = environment
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(lambda _: install(project), range(4))) == [0]*4
    config = project / '.codex/config.toml'
    assert list(tomllib.loads(config.read_text())['mcp_servers']) == ['qhaway']
    assert uninstall(project) == 0


def test_uninstall_absent_does_not_create_project_files(environment):
    _, project = environment
    assert uninstall(project) == 0
    assert not (project / '.codex').exists()


def test_rejects_native_memory_and_project_root(environment):
    home, project = environment
    assert install(project, '--dir', str(home / '.codex/memories')) == 1
    assert install(project, '--dir', str(project)) == 1
    assert not (project / '.codex/config.toml').exists()


def test_claude_rejects_codex_only_options(environment):
    home, project = environment
    with pytest.raises(SystemExit):
        cli.main(['init', '--project', str(project)])
    assert not (home / '.claude.json').exists()


def test_unrelated_settings_added_after_install_survive_removal(environment):
    _, project = environment
    assert install(project) == 0
    config = project / '.codex/config.toml'
    with config.open('ab') as handle:
        handle.write(b'\n[mcp_servers.other]\ncommand = "other"\n')
    assert uninstall(project) == 0
    assert tomllib.loads(config.read_text())['mcp_servers']['other']['command'] == 'other'


def test_additional_qhaway_settings_outside_owned_block_are_preserved(environment):
    _, project = environment
    assert install(project) == 0
    config = project / '.codex/config.toml'
    with config.open('ab') as handle:
        handle.write(b'\n[mcp_servers.qhaway.env]\nMY_SETTING = "keep"\n')
    original = config.read_bytes()
    assert uninstall(project) == 1
    assert config.read_bytes() == original


def test_sealed_toml_table_conflict_leaves_original(environment):
    _, project = environment
    config = project / '.codex/config.toml'
    config.parent.mkdir()
    original = b'mcp_servers = { other = { command = "other" } }\n'
    config.write_bytes(original)
    assert install(project) == 1
    assert config.read_bytes() == original


def test_install_alias_and_explicit_claude_keep_existing_contract(environment, monkeypatch):
    home, project = environment
    assert cli.main(['install', '--host', 'codex', '--project', str(project)]) == 0
    assert cli.main(['init', '--host', 'claude']) == 0
    assert (home / '.claude.json').exists()
    assert cli.main(['uninstall', '--host', 'claude']) == 0
    assert 'qhaway' in tomllib.loads((project / '.codex/config.toml').read_text())['mcp_servers']


def test_missing_project_fails_without_creating_it(environment):
    _, project = environment
    missing = project / 'missing'
    assert install(missing) == 1
    assert not missing.exists()


def test_config_symlink_is_not_replaced(environment):
    home, project = environment
    target = home / 'elsewhere.toml'
    target.write_text('model = "keep"\n')
    config = project / '.codex/config.toml'
    config.parent.mkdir()
    try:
        config.symlink_to(target)
    except OSError:
        pytest.skip('symlinks unavailable to this Windows account')
    assert install(project) == 1
    assert uninstall(project) == 1
    assert config.is_symlink()
    assert target.read_text() == 'model = "keep"\n'


def test_rejects_existing_file_as_memory_directory(environment):
    home, project = environment
    file = home / 'file'
    file.write_text('not a directory')
    assert install(project, '--dir', str(file)) == 1
    assert not (project / '.codex/config.toml').exists()


def test_custom_codex_home_native_memory_is_protected(environment, monkeypatch):
    home, project = environment
    monkeypatch.setenv('CODEX_HOME', str(home / 'custom-codex'))
    assert install(project, '--dir', str(home / 'custom-codex/memories/nested')) == 1


def test_home_project_cannot_modify_global_config(environment):
    home, _ = environment
    config = home / '.codex/config.toml'
    config.parent.mkdir()
    original = b'model = "keep"\n'
    config.write_bytes(original)
    assert install(home) == 1
    assert uninstall(home) == 1
    assert config.read_bytes() == original


def test_custom_codex_home_cannot_be_selected_as_project_config(environment, monkeypatch):
    home, project = environment
    monkeypatch.setenv('CODEX_HOME', str(project / '.codex'))
    assert install(project) == 1
    assert not (project / '.codex/config.toml').exists()


def test_codex_directory_symlink_cannot_redirect_installer(environment):
    home, project = environment
    elsewhere = home / 'global-settings'
    elsewhere.mkdir()
    config = elsewhere / 'config.toml'
    original = b'model = "keep"\n'
    config.write_bytes(original)
    try:
        (project / '.codex').symlink_to(elsewhere, target_is_directory=True)
    except OSError:
        pytest.skip('symlinks unavailable to this Windows account')
    assert install(project) == 1
    assert uninstall(project) == 1
    assert config.read_bytes() == original


def test_default_store_alias_cannot_enter_native_memory(environment):
    home, project = environment
    native = home / '.codex/memories'
    native.mkdir(parents=True)
    try:
        (home / '.qhaway').symlink_to(native, target_is_directory=True)
    except OSError:
        pytest.skip('symlinks unavailable to this Windows account')
    assert install(project) == 1
    assert not (project / '.codex/config.toml').exists()
    assert list(native.iterdir()) == []
