"""Entry point for the `qhaway` command."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from qhaway.model import build_index, topic_files
from qhaway.project import DEFAULT_BUDGET, project_slice


SIDECAR_NAME = ".qhaway.json"
MEMORY_NAME = "MEMORY.md"


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qhaway")
    subparsers = parser.add_subparsers(dest="command", required=True)
    index_parser = subparsers.add_parser("index")
    index_parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    index_parser.add_argument("--type", dest="content_type")
    index_parser.add_argument("--role")
    index_parser.add_argument("--status", default="live")
    index_parser.add_argument("--check", action="store_true")
    index_parser.add_argument("--dry-run", action="store_true")
    index_parser.add_argument("--dir", default=".")

    namespace = parser.parse_args(args)
    if namespace.command == "index":
        return _index(namespace)
    return 1


def _index(args: argparse.Namespace) -> int:
    memory_dir = Path(args.dir)
    if not memory_dir.is_dir():
        sys.stderr.write(f"memory directory is not readable: {memory_dir}\n")
        return 1

    topics = topic_files(memory_dir)
    if not topics:
        sys.stderr.write(f"refusing to index {memory_dir}: found 0 topic .md files\n")
        return 1

    try:
        db_conn = build_index(str(memory_dir), db_path=":memory:")
    except Exception as exc:
        sys.stderr.write(f"failed to build qhaway index: {exc}\n")
        return 1

    if args.check:
        return _check(memory_dir, db_conn, args.budget, len(topics))

    output = project_slice(
        db_conn,
        budget=args.budget,
        content_type=args.content_type,
        role=args.role,
        status=args.status,
    )
    if args.dry_run:
        sys.stdout.write(output)
        return 0

    memory_file = memory_dir / MEMORY_NAME
    sidecar_file = memory_dir / SIDECAR_NAME
    try:
        _preserve_if_hand_edited(memory_file, sidecar_file)
        memory_file.write_text(output, encoding="utf-8")
        sidecar_file.write_text(
            json.dumps({"version": 1, "last_output_hash": _sha256(output)}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        sys.stderr.write(f"failed to write qhaway index: {exc}\n")
        return 1
    return 0


def _check(memory_dir: Path, db_conn: object, budget: int, topic_count: int) -> int:
    exit_code = 0
    if topic_count <= 2:
        sys.stderr.write(f"warning: low topic file count ({topic_count}) in {memory_dir}\n")

    orphans = _orphan_files(memory_dir)
    if orphans:
        sys.stdout.write(f"{len(orphans)} orphan MEMORY backups found:\n")
        for orphan in orphans:
            sys.stdout.write(f"- {orphan.name}\n")

    dangling = _dangling_links(db_conn)
    if dangling:
        exit_code = 1
        sys.stderr.write("dangling topic wikilinks found:\n")
        for src_file, dst_slug in dangling:
            sys.stderr.write(f"- {src_file} -> [[{dst_slug}]]\n")

    full_projection = project_slice(db_conn, budget=10**12)
    if len(full_projection.encode("utf-8")) > budget:
        overflow = len(full_projection.encode("utf-8")) - budget
        exit_code = 1
        sys.stderr.write(f"corpus exceeds budget by {overflow} bytes before projection\n")

    if exit_code == 0 and not orphans and topic_count > 2:
        sys.stdout.write("qhaway check passed\n")
    return exit_code


def _dangling_links(db_conn: object) -> list[tuple[str, str]]:
    stems = {row[0].removesuffix(".md") for row in db_conn.execute("SELECT file FROM nodes").fetchall()}
    dangling: list[tuple[str, str]] = []
    for src_file, dst_slug in db_conn.execute("SELECT src_file, dst_slug FROM edges ORDER BY src_file, dst_slug").fetchall():
        if dst_slug not in stems:
            dangling.append((src_file, dst_slug))
    return dangling


def _preserve_if_hand_edited(memory_file: Path, sidecar_file: Path) -> None:
    if not memory_file.exists():
        return
    current_hash = _sha256(memory_file.read_text(encoding="utf-8"))
    recorded_hash = _recorded_hash(sidecar_file)
    if current_hash == recorded_hash:
        return
    memory_file.rename(_backup_path(memory_file))


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


def _backup_path(memory_file: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    base = memory_file.with_name(f"MEMORY-{timestamp}.md")
    if not base.exists():
        return base
    for index in range(1, 100):
        candidate = memory_file.with_name(f"MEMORY-{timestamp}-{index:02d}.md")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"could not allocate non-colliding backup name for {memory_file}")


def _orphan_files(memory_dir: Path) -> list[Path]:
    return sorted(memory_dir.glob("MEMORY-*.md"), key=lambda path: path.name)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
