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


def default_store(project: Path) -> Path:
    key = hashlib.sha256(os.fsencode(str(project.resolve()))).hexdigest()
    return Path.home() / '.qhaway' / 'projects' / key / 'memory'


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


def _payload(store: Path) -> bytes:
    # JSON basic strings/arrays are valid TOML for these string-only values.
    args = ['--python', '3.14', 'qhaway', 'serve', '--dir', str(store), '--inline-index']
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
def _locked(directory: Path):
    # Reuse the existing POSIX/Windows file-lock primitive. Never unlink the
    # lock: waiting installers must continue locking the same inode.
    with (directory / '.qhaway-install.lock').open('a+b') as handle:
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
    selected = (store.expanduser().resolve() if store is not None else default_store(project))
    if not remove and selected.exists() and not selected.is_dir():
        raise ValueError(f'Memory directory is not a directory: {selected}')
    native_roots = [Path.home() / '.codex' / 'memories']
    if os.environ.get('CODEX_HOME'):
        native_roots.append(Path(os.environ['CODEX_HOME']) / 'memories')
    if not remove and (selected == project or selected == path.parent or
                       any(selected.is_relative_to(root.resolve()) for root in native_roots)):
        raise ValueError('Choose a dedicated curated store, not the project root or native Codex memory')
    if path.is_symlink():
        raise ValueError('Codex config is a symlink; left untouched')
    if remove and not path.exists():
        return 'absent', None
    path.parent.mkdir(parents=True, exist_ok=True)
    with _locked(path.parent):
        if path.is_symlink():
            raise ValueError('Codex config is a symlink; left untouched')
        raw = path.read_bytes() if path.exists() else b''
        rest, owned = _split(raw)
        if remove:
            if owned is None:
                return 'absent', None
            _write(path, rest)
            return 'removed', None
        payload = _payload(selected)
        if owned is not None:
            if _parse(owned) != _parse(payload):
                raise ValueError('qhaway is installed with different settings; uninstall it first to change stores')
            return 'already', selected
        digest = hashlib.sha256(payload).hexdigest().encode()
        block = b'\n\n' + _START + digest + b' >>>\n' + payload + _END
        updated = raw + block
        _parse(updated)  # Reject conflicts with inline/sealed tables before writing.
        _write(path, updated)
        return 'installed', selected
