"""MCP spine: the remember/recall verbs over the existing pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from qhaway import cli, model, project, reconcile

VALID_TYPES = {"user", "feedback", "project", "reference"}
_MAX_SUFFIX = 100


def remember(type, title, body, description=None, links=None, memory_dir=".") -> str:
    if type not in VALID_TYPES:
        raise ValueError(f"invalid type {type!r}; must be one of {sorted(VALID_TYPES)}")
    root = Path(memory_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"memory directory is not readable: {memory_dir}")

    text = reconcile.compose_topic_file(type, title, body, description, links)
    stem = reconcile.slugify(title)
    filename = _exclusive_write(root, stem, text)
    reconcile.reconcile(str(root))
    return filename


def _exclusive_write(root: Path, stem: str, text: str) -> str:
    for suffix in range(0, _MAX_SUFFIX):
        name = f"{stem}.md" if suffix == 0 else f"{stem}-{suffix}.md"
        path = root / name
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        return name
    raise RuntimeError(
        f"could not allocate a unique topic filename for {stem!r} after {_MAX_SUFFIX} attempts"
    )


def recall(type=None, role=None, status="live", memory_dir=".") -> str:
    root = Path(memory_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"memory directory is not readable: {memory_dir}")
    conn = model.get_connection(str(root))
    try:
        result = project.project_slice_with_overflow(
            conn, budget=project.DEFAULT_BUDGET, content_type=type, role=role, status=status
        )
    finally:
        conn.close()
    return result.markdown


def initialize_server(memory_dir: str) -> None:
    """Run exactly one reconcile at startup, before accepting tool calls (C-3)."""
    cli.reconcile(memory_dir)
