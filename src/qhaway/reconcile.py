"""The one shared reconcile operation + atomic read-only writer + remember composer."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
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


def slugify(title: str) -> str:
    lowered = title.strip().lower().replace(" ", "-")
    cleaned = _SLUG_STRIP.sub("", lowered).replace("_", "-")
    cleaned = _SLUG_COLLAPSE.sub("-", cleaned).strip("-")
    if cleaned:
        return cleaned
    # Nothing survived (whitespace/punctuation-only). Fall back to a stable
    # hash of the original so distinct titles stay distinct, never the shared
    # constant "memory".
    digest = hashlib.sha256(title.encode("utf-8")).hexdigest()[:8]
    return f"memory-{digest}"


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


def _dedupe_normalized(values: str | list[str]) -> list[str]:
    """Normalize each value via normalize_link, preserving order, dropping dups."""
    if isinstance(values, str):
        values = [values]
    seen: dict[str, None] = {}
    for value in values:
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
    """
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=".qhaway-tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp_name, 0o444)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def reconcile(memory_dir: str) -> None:
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

    if memory_file.exists():
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

    write_readonly(memory_file, desired)
    _write_sidecar(sidecar_file, _sha256(strip_signature(desired)))


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
