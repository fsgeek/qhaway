"""Project-local Codex wiring with explicit ownership and byte-preserving removal."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import tomllib

from qhaway import model, setup

_START = b'# >>> qhaway codex '
_END = b'# <<< qhaway codex <<<\n'
_HEADER = re.compile(rb'# >>> qhaway codex ([0-9a-f]{64}) >>>\n')


def _project_key(project: Path) -> str:
    return hashlib.sha256(os.fsencode(str(project.resolve()))).hexdigest()


def default_store(project: Path) -> Path:
    return Path.home() / '.qhaway' / 'projects' / _project_key(project) / 'memory'


def _parse(raw: bytes) -> dict:
    try:
        return tomllib.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError('Codex config is not valid UTF-8 TOML; left untouched') from exc


def _server(data: dict):
    servers = data.get('mcp_servers', {})
    if not isinstance(servers, dict):
        raise ValueError('mcp_servers is not a TOML table; left untouched')
    return servers.get('qhaway')


def _split(raw: bytes) -> tuple[bytes, bytes | None]:
    """Return unrelated bytes and an intact owned payload, or refuse edits."""
    data = _parse(raw)
    if _START not in raw and _END not in raw:
        if _server(data) is not None:
            raise ValueError('Unmanaged qhaway entry: remove it explicitly before installation/removal')
        return raw, None
    if raw.count(_START) != 1 or raw.count(_END) != 1:
        raise ValueError('Damaged qhaway ownership markers; left untouched')
    start = raw.index(_START)
    match = _HEADER.match(raw, start)
    if match is None or start < 2 or raw[start-2:start] != b'\n\n':
        raise ValueError('Modified qhaway block; left untouched')
    end = raw.index(_END)
    if end < match.end():
        raise ValueError('Damaged qhaway ownership markers; left untouched')
    payload = raw[match.end():end]
    if hashlib.sha256(payload).hexdigest().encode() != match[1]:
        raise ValueError('Modified qhaway block; left untouched (restore it or remove it manually)')
    rest = raw[:start-2] + raw[end+len(_END):]
    if _server(_parse(rest)) is not None:
        raise ValueError('qhaway settings outside the managed block; left untouched')
    if _server(data) != _server(_parse(payload)):
        raise ValueError('Modified qhaway settings; left untouched')
    return rest, payload


def _owned_store(owned: bytes) -> Path | None:
    args = _server(_parse(owned)).get('args', [])
    if '--dir' in args and args.index('--dir') + 1 < len(args):
        return Path(args[args.index('--dir') + 1]).expanduser().resolve()
    return None


def _payload(store: Path) -> bytes:
    # JSON basic strings/arrays are valid TOML for these string-only values.
    # --isolated: ignore an installed qhaway tool, which uvx would otherwise
    # prefer, pinning the server to that tool's version (#31).
    args = ['--isolated', '--python', '3.14', 'qhaway', 'serve', '--dir', str(store)]
    return ('[mcp_servers.qhaway]\n'
            f'command = {json.dumps(setup._uvx(), ensure_ascii=False)}\n'
            f'args = {json.dumps(args, ensure_ascii=False)}\n'
            'startup_timeout_sec = 30\n').encode('utf-8')


def _write(path: Path, raw: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.qhaway-config-')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def _locked(path: Path):
    # Reuse the existing POSIX/Windows file-lock primitive. Never unlink the
    # lock: waiting installers must continue locking the same inode.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0)
        deadline = time.monotonic() + 5
        while True:
            try:
                model._try_lock(handle)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Another qhaway installer holds the Codex config lock')
                time.sleep(0.02)
        try:
            yield
        finally:
            model._unlock(handle)


def configure(project: Path, store: Path | None = None, *, remove: bool = False) -> tuple[str, Path | None]:
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f'Project directory does not exist: {project}')
    path = project / '.codex' / 'config.toml'
    codex_homes = [Path.home() / '.codex']
    if os.environ.get('CODEX_HOME'):
        codex_homes.append(Path(os.environ['CODEX_HOME']).expanduser())
    if path.parent.is_symlink() or path.parent.is_junction():
        raise ValueError('Project .codex directory is an alias; left untouched')
    if any(path.resolve() == (home / 'config.toml').resolve() for home in codex_homes):
        raise ValueError('Project selection targets global Codex configuration; left untouched')
    selected = (store.expanduser() if store is not None else default_store(project)).resolve()
    if not remove and selected.exists() and not selected.is_dir():
        raise ValueError(f'Memory directory is not a directory: {selected}')
    native_roots = [home / 'memories' for home in codex_homes]
    if not remove and (selected == project or selected == path.parent or
                       any(selected.is_relative_to(root.resolve()) for root in native_roots)):
        raise ValueError('Choose a dedicated curated store, not the project root or native Codex memory')
    if path.is_symlink():
        raise ValueError('Codex config is a symlink; left untouched')
    if remove and not path.exists():
        return 'absent', None
    lock = (Path.home() / '.qhaway' / 'locks' / f'{_project_key(project)}.lock').resolve()
    if any(lock.is_relative_to(root.resolve()) for root in native_roots):
        raise ValueError('Installer lock aliases native Codex memory; left untouched')
    with _locked(lock):
        if path.parent.is_symlink() or path.parent.is_junction():
            raise ValueError('Project .codex directory is an alias; left untouched')
        if path.is_symlink():
            raise ValueError('Codex config is a symlink; left untouched')
        raw = path.read_bytes() if path.exists() else b''
        rest, owned = _split(raw)
        if remove:
            if owned is None:
                return 'absent', None
            if rest:
                _write(path, rest)
            else:
                path.unlink()
                try:
                    path.parent.rmdir()
                except OSError:
                    pass  # Nonempty (other Codex files) or concurrently changed.
            return 'removed', None
        payload = _payload(selected)
        digest = hashlib.sha256(payload).hexdigest().encode()
        block = b'\n\n' + _START + digest + b' >>>\n' + payload + _END
        if owned is not None:
            if _parse(owned) == _parse(payload):
                return 'already', selected
            if _owned_store(owned) != selected:
                raise ValueError('qhaway is installed with different settings; uninstall it first to change stores')
            # Our intact block from an older qhaway, same store: replace it where
            # it stands, so settings written after it keep their order (#31).
            old = b'\n\n' + _START + hashlib.sha256(owned).hexdigest().encode() + b' >>>\n' + owned + _END
            updated = raw.replace(old, block, 1)
            _parse(updated)
            _write(path, updated)
            return 'updated', selected
        updated = raw + block
        _parse(updated)  # Reject conflicts with inline/sealed tables before writing.
        path.parent.mkdir(parents=True, exist_ok=True)
        _write(path, updated)
        return 'installed', selected
