"""The one shared reconcile operation + atomic read-only writer + remember composer."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from qhaway import model

REDIRECT_TEMPLATE = (
    "# Memory\n\n"
    "**Before acting on any belief about this project, call `recall()` first** "
    "— your context is stale; `recall()` is the latest word.\n\n"
    "Your memory lives in a database, not this file. Use the MCP tools:\n\n"
    "- `recall(type?, role?, status?)` — read your memory (omit args for the working set)\n"
    "- `remember(type, title, body, ...)` — write a memory\n\n"
    "Do not hand-edit this file; it is managed by qhaway and is read-only.\n"
)

SIDECAR_NAME = ".qhaway.json"
MEMORY_NAME = "MEMORY.md"

SIGNATURE_PREFIX = "<!-- qhaway:v1:"
SIGNATURE_SUFFIX = "-->"


def signature_line(unsigned_body: str) -> str:
    return f"{SIGNATURE_PREFIX}{_sha256(unsigned_body.rstrip())}{SIGNATURE_SUFFIX}"


def embed_signature(body: str) -> str:
    stripped = body.rstrip()
    return stripped + "\n" + signature_line(stripped) + "\n"


def read_signature(text: str) -> str | None:
    lines = text.rstrip().splitlines()
    if not lines:
        return None
    last = lines[-1].strip()
    if last.startswith(SIGNATURE_PREFIX) and last.endswith(SIGNATURE_SUFFIX):
        return last[len(SIGNATURE_PREFIX):-len(SIGNATURE_SUFFIX)]
    return None


def strip_signature(text: str) -> str:
    lines = text.rstrip().splitlines()
    if lines and read_signature(text) is not None:
        lines = lines[:-1]
    return "\n".join(lines).rstrip()

# Keep unicode word chars so distinct non-ASCII titles get distinct slugs
# (collapsing every non-ASCII title to one slug silently merges unrelated
# memories — and silently drops links that normalize identically).
_SLUG_STRIP = re.compile(r"[^\w-]+", re.UNICODE)
_SLUG_COLLAPSE = re.compile(r"-{2,}")
# Cap the slug so the filename stays well under the common 255-byte NAME_MAX,
# leaving room for a "-N" collision suffix and the ".md" extension. Titles this
# long are descriptions, not names; the cap keeps the leading words readable and
# appends a hash of the full title so two long titles never collide.
_SLUG_MAX = 180
_TRAILING_DATE = re.compile(r"-(\d{4}-\d{2}-\d{2})$")


def slugify(title: str) -> str:
    lowered = title.strip().lower().replace(" ", "-")
    cleaned = _SLUG_STRIP.sub("", lowered).replace("_", "-")
    cleaned = _SLUG_COLLAPSE.sub("-", cleaned).strip("-")
    if not cleaned:
        # Nothing survived (whitespace/punctuation-only). Fall back to a stable
        # hash of the original so distinct titles stay distinct, never the shared
        # constant "memory".
        digest = hashlib.sha256(title.encode("utf-8")).hexdigest()[:8]
        return f"memory-{digest}"
    if len(cleaned.encode("utf-8")) <= _SLUG_MAX:
        return cleaned
    # Too long for the filesystem. Preserve a trailing ISO date (the parse layer
    # reads date_hint off the stem), append a hash so distinct long titles stay
    # distinct, and truncate the head on a word boundary to fit. The hash is of
    # the CLEANED form, not the raw title: every spelling that cleans to the
    # same slug ("My Title", "my-title", a pre-cap stem read off disk) must cap
    # to the same slug, or supersedes/links written from one spelling dangle
    # against files written from another (the 2026-09-03 field failure).
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:8]
    date_match = _TRAILING_DATE.search(cleaned)
    tail = f"-{date_match.group(1)}" if date_match else ""
    head = cleaned[: date_match.start()] if date_match else cleaned
    budget = _SLUG_MAX - len((digest + tail).encode("utf-8")) - 1  # 1 for the "-" before digest
    truncated = head.encode("utf-8")[:budget].decode("utf-8", "ignore").rstrip("-")
    truncated = truncated.rsplit("-", 1)[0] if "-" in truncated else truncated
    return f"{truncated}-{digest}{tail}"


def normalize_link(raw: str) -> str:
    text = raw.strip()
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2]
    if text.endswith(".md"):
        text = text[:-3]
    if "/" in text or "\\" in text:
        raise ValueError(f"link must not contain a path separator: {raw!r}")
    return slugify(text)


def compose_frontmatter(type: str, title: str, description: str | None,
                        supersedes: list[str] | None = None) -> str:
    data = {"name": title, "type": type}
    if description is not None:
        data["description"] = description
    if supersedes:
        # Stored as [[wikilink]] strings so the on-disk key reads naturally and
        # round-trips through parse._supersedes (which accepts [[A]] or bare).
        data["supersedes"] = [f"[[{slug}]]" for slug in supersedes]
    dumped = yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False, default_flow_style=False
    )
    return f"---\n{dumped}---\n"


def _coerce_targets(raw: str | list[str]) -> list[str]:
    """Turn an incoming supersedes/links value into a list of target strings.

    The MCP boundary types these args as `str`, so a multi-target call arrives as
    a stringified JSON array — `'["a","b"]'`. A single target arrives as a bare
    string (`'a-slug'` or `'[[a]]'`). The Python API may pass a real list.

    Intent detection, NOT a blanket try/except: only a value that looks like a
    JSON array (`[` but not the `[[` of a wikilink) is parsed as JSON. If that
    parse fails, the caller *meant* a list and malformed it — raise loudly rather
    than fall back to [raw], which would silently fuse the targets into one slug
    (the exact bug this fixes). Everything else is a single target.
    """
    if isinstance(raw, list):
        return raw
    text = raw.strip()
    if text.startswith("[") and not text.startswith("[["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"value looked like a JSON array but did not parse: {raw!r} ({exc})"
            ) from exc
        if not isinstance(parsed, list):
            raise ValueError(f"expected a JSON array, got {type(parsed).__name__}: {raw!r}")
        return parsed
    return [raw]


def _dedupe_normalized(values: str | list[str]) -> list[str]:
    """Coerce to a target list, normalize via normalize_link, dedupe, keep order."""
    seen: dict[str, None] = {}
    for value in _coerce_targets(values):
        seen.setdefault(normalize_link(value), None)
    return list(seen)


def compose_topic_file(type, title, body, description, links, supersedes=None) -> str:
    normalized_supersedes = _dedupe_normalized(supersedes) if supersedes else None
    text = compose_frontmatter(type, title, description, normalized_supersedes) + body
    if links:
        slugs = _dedupe_normalized(links)
        text = text.rstrip() + "\n\n" + "\n".join(f"[[{slug}]]" for slug in slugs) + "\n"
    return text


def write_readonly(path: Path, text: str) -> None:
    """Write text to a temp file created read-only, then atomically replace path.

    SPIKE 2026-06-21 (ext4/WSL2): replace-over-0444 confirmed OK — os.replace of a
    0444 temp over an existing 0444 file succeeds via directory write; direct
    open('w') on the 0444 target raises PermissionError. No chmod-before-replace
    fallback needed on POSIX filesystems.

    NTFS (Windows Python 3.14, 2026-09-01): os.replace raises PermissionError
    over a read-only target — Windows refuses to replace or delete one — so
    Windows goes through _replace() below. The friction signal is unchanged:
    direct open('w') still fails there too.
    """
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=".qhaway-tmp-")
    try:
        # newline="\n": the budget was computed on LF bytes; text-mode CRLF on
        # Windows would ship a file larger than the budget it declares.
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.chmod(tmp_name, 0o444)
        _replace(tmp_name, str(path))
    except BaseException:
        if os.path.exists(tmp_name):
            if os.name == "nt":
                os.chmod(tmp_name, 0o644)  # Windows refuses to unlink a read-only file
            os.unlink(tmp_name)
        raise


def _replace(src: str, dst: str) -> None:
    """Atomically move src over dst. POSIX: os.replace, done. Windows: MoveFileEx
    (what os.replace uses) refuses a read-only target, refuses a target another
    handle has open, and is not atomic for a concurrent reader — measured
    2026-09-01: 802/900 writer failures and 122 reader not-founds under a race.
    So on Windows: a handle-based rename with POSIX semantics (atomic for
    readers, ignores the read-only attribute), retried briefly while a reader
    without FILE_SHARE_DELETE (any Python open()) holds the target."""
    if os.name != "nt":
        os.replace(src, dst)
        return
    deadline = time.monotonic() + 2.0
    delay = 0.001
    while True:
        try:
            _nt_posix_rename(src, dst)
            return
        except OSError as exc:
            # 5 access denied, 32 sharing violation: a reader has it open, or the
            # attribute race lost — transient by construction, so wait it out.
            if getattr(exc, "winerror", None) not in (5, 32) or time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.05)


def _nt_posix_rename(src: str, dst: str) -> None:
    """SetFileInformationByHandle(FileRenameInfoEx) with REPLACE_IF_EXISTS |
    POSIX_SEMANTICS | IGNORE_READONLY_ATTRIBUTE. Falls back to clearing the
    read-only bit + os.replace where the Ex call is unsupported (pre-1607
    Windows, non-NTFS volumes)."""
    import ctypes
    import ctypes.wintypes as wt

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wt.HANDLE
    k32.SetFileInformationByHandle.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
    DELETE, SHARE_ALL, OPEN_EXISTING, ATTR_NORMAL = 0x00010000, 0x7, 3, 0x80
    FILE_RENAME_INFO_EX = 22
    FLAGS = 0x1 | 0x2 | 0x40  # REPLACE_IF_EXISTS | POSIX_SEMANTICS | IGNORE_READONLY_ATTRIBUTE
    INVALID = wt.HANDLE(-1).value

    handle = k32.CreateFileW(src, DELETE, SHARE_ALL, None, OPEN_EXISTING, ATTR_NORMAL, None)
    if handle == INVALID:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        name = os.path.abspath(dst).encode("utf-16-le")
        # FILE_RENAME_INFO: DWORD Flags (padded to 8); HANDLE RootDirectory;
        # DWORD FileNameLength; WCHAR FileName[]  — x64 layout, offsets 0/8/16/20.
        size = 20 + len(name) + 2
        buf = ctypes.create_string_buffer(size)
        ctypes.memmove(buf, bytes(ctypes.c_uint32(FLAGS)), 4)
        ctypes.memmove(ctypes.addressof(buf) + 16, bytes(ctypes.c_uint32(len(name))), 4)
        ctypes.memmove(ctypes.addressof(buf) + 20, name, len(name))
        if k32.SetFileInformationByHandle(handle, FILE_RENAME_INFO_EX, buf, size):
            return
        err = ctypes.get_last_error()
    finally:
        k32.CloseHandle(handle)
    if err not in (50, 87):  # ERROR_NOT_SUPPORTED, ERROR_INVALID_PARAMETER → fallback
        raise ctypes.WinError(err)
    if os.path.exists(dst):
        os.chmod(dst, 0o644)
    os.replace(src, dst)


def reconcile(memory_dir: str, heal: bool = True) -> None:
    """Sync the db to the topic files, then (by default) heal MEMORY.md to the
    redirect stub. heal=False is for inline-index serve mode, where MEMORY.md is
    the always-current budgeted index and must never transit through the
    redirect — the caller writes the index instead."""
    root = Path(memory_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"memory directory is not readable: {memory_dir}")

    conn = model.get_connection(memory_dir)
    try:
        conn.execute("BEGIN IMMEDIATE")
        _reconcile_nodes(conn, root)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

    if heal:
        _heal_redirect(root)


def _reconcile_nodes(conn, root: Path) -> None:
    db_state = {
        file: (mtime_ns, size)
        for file, mtime_ns, size in conn.execute("SELECT file, mtime_ns, size FROM nodes")
    }
    on_disk = {}
    for path in model.topic_files(root):
        stat = path.stat()
        on_disk[path.name] = path
        prior = db_state.get(path.name)
        if prior is None or prior != (stat.st_mtime_ns, stat.st_size):
            model.upsert_file(conn, path)
    for gone in set(db_state) - set(on_disk):
        model.delete_node(conn, gone)


def _heal_redirect(root: Path) -> None:
    memory_file = root / MEMORY_NAME
    sidecar_file = root / SIDECAR_NAME
    override = root / "REDIRECT.md"
    desired_body = override.read_text(encoding="utf-8") if override.exists() else REDIRECT_TEMPLATE
    desired = embed_signature(desired_body)

    snapshot_unowned(memory_file)
    write_readonly(memory_file, desired)
    _write_sidecar(sidecar_file, _sha256(strip_signature(desired)))


def snapshot_unowned(memory_file: Path) -> None:
    """Before any qhaway write over MEMORY.md, preserve content we do not own.
    Shared by the redirect heal and the inline/exit index writers, so adopting a
    host-native store can never clobber the human's original."""
    if not memory_file.exists():
        return
    current = memory_file.read_text(encoding="utf-8")
    sig = read_signature(current)
    if sig is None:
        # (2) user original — snapshot FIRST, then replace. Use a distinguished,
        # durable name: this is the PRE-INSTALL original, the restore source for
        # an explicit uninstall. Captured once; if it already exists (a prior
        # boot took it), this original is itself a later hand-authored file, so
        # fall back to a timestamped backup rather than clobbering the first.
        preinstall = _preinstall_path(memory_file)
        memory_file.rename(preinstall if not preinstall.exists() else _backup_path(memory_file))
    elif sig != _sha256(strip_signature(current)):
        # (4) our file, hand-edited — preserve the edit, then regenerate
        memory_file.rename(_backup_path(memory_file))
    else:
        # (3) ours, unchanged — fall through to idempotent rewrite, no backup
        pass


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _recorded_hash(sidecar_file: Path) -> str | None:
    if not sidecar_file.exists():
        return None
    try:
        data = json.loads(sidecar_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if data.get("version") != 1:
        return None
    value = data.get("last_output_hash")
    return value if isinstance(value, str) else None


def _write_sidecar(sidecar_file: Path, output_hash: str) -> None:
    sidecar_file.write_text(
        json.dumps({"version": 1, "last_output_hash": output_hash}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


PREINSTALL_NAME = "MEMORY.preinstall.md"


def _preinstall_path(memory_file: Path) -> Path:
    """The distinguished, stable name for the pre-install original — the restore
    source for an explicit uninstall. Distinct from routine timestamped hand-edit
    backups so 'the human's original' is always unambiguous."""
    return memory_file.with_name(PREINSTALL_NAME)


def _backup_path(memory_file: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    base = memory_file.with_name(f"MEMORY-{timestamp}.md")
    if not base.exists():
        return base
    for index in range(1, 100):
        candidate = memory_file.with_name(f"MEMORY-{timestamp}-{index:02d}.md")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"could not allocate backup name for {memory_file}")
