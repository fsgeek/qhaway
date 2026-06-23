"""Entry point for the `qhaway` command."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from qhaway import model, parse, project, server
from qhaway import reconcile as reconcile_mod
from qhaway.reconcile import reconcile

MEMORY_NAME = "MEMORY.md"


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qhaway")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("reconcile", "check", "serve", "index", "exit"):
        p = sub.add_parser(name)
        p.add_argument("--dir")
        p.add_argument("--budget", type=int, default=project.DEFAULT_BUDGET)
        p.add_argument("--type", dest="content_type")
        p.add_argument("--role")
        p.add_argument("--status", default="live")
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--check", action="store_true")  # deprecated alias on index
        p.add_argument("--emit", action="store_true")

    ns = parser.parse_args(args)
    directory = _resolve_dir(ns)

    if ns.command == "serve":
        return _serve(directory)
    if ns.command == "exit":
        return _exit(directory, ns.budget)
    if ns.command == "check" or (ns.command == "index" and ns.check):
        return _check(directory, ns.budget)
    if ns.command == "index" and ns.dry_run:
        return _dry_run(directory, ns)

    # reconcile, and index-as-reconcile-alias
    try:
        reconcile(directory)
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    if getattr(ns, "emit", False):
        conn = model.get_connection(directory)
        try:
            sys.stdout.write(project.project_slice(conn, budget=ns.budget))
        finally:
            conn.close()
    return 0


def _resolve_dir(ns) -> str:
    return ns.dir or os.environ.get("QHAWAY_MEMORY_DIR") or "."


def _serve(directory: str) -> int:
    if not os.path.isdir(directory):
        sys.stderr.write(f"memory directory is not readable: {directory}\n")
        return 1
    server.run(directory)
    return 0


def _dry_run(directory: str, ns) -> int:
    if not os.path.isdir(directory):
        sys.stderr.write(f"memory directory is not readable: {directory}\n")
        return 1
    conn = model.get_connection(directory)
    try:
        output = project.project_slice(
            conn,
            budget=ns.budget,
            content_type=ns.content_type,
            role=ns.role,
            status=ns.status,
        )
    finally:
        conn.close()
    sys.stdout.write(output)
    return 0


def _exit(directory: str, budget: int) -> int:
    memory_dir = Path(directory)
    if not memory_dir.is_dir():
        sys.stderr.write(f"memory directory is not readable: {memory_dir}\n")
        return 1

    # If a hand-authored original was snapshotted (unsigned backup), restore it.
    for backup in _orphan_files(memory_dir):  # oldest first (sorted by name)
        if reconcile_mod.read_signature(backup.read_text(encoding="utf-8")) is None:
            reconcile_mod.write_readonly(
                memory_dir / MEMORY_NAME, backup.read_text(encoding="utf-8")
            )
            return 0

    reconcile(directory)
    conn = model.get_connection(directory)
    try:
        result = project.project_slice_with_overflow(conn, budget=budget)
        total = len(model.topic_files(memory_dir))
        omitted = sum(result.overflow.omitted_counts.values())
    finally:
        conn.close()
    footer = (
        f"\n\n---\n_qhaway exit index — {total} memories, projected under "
        f"{budget} bytes. Omitted: {omitted} "
        "(run `recall()` after re-enable for the full working set)._\n"
    )
    reconcile_mod.write_readonly(
        memory_dir / MEMORY_NAME, reconcile_mod.embed_signature(result.markdown + footer)
    )
    return 0


def _check(directory: str, budget: int) -> int:
    memory_dir = Path(directory)
    if not memory_dir.is_dir():
        sys.stderr.write(f"memory directory is not readable: {memory_dir}\n")
        return 1

    exit_code = 0
    topic_count = len(model.topic_files(memory_dir))
    if topic_count <= 2:
        sys.stderr.write(f"warning: low topic file count ({topic_count}) in {memory_dir}\n")

    orphans = _orphan_files(memory_dir)
    if orphans:
        sys.stdout.write(f"{len(orphans)} orphan MEMORY backups found:\n")
        for orphan in orphans:
            sys.stdout.write(f"- {orphan.name}\n")

    conn = model.get_connection(directory)
    try:
        dangling = _dangling_links(conn)
        stale_drift = _stale_drift(conn)
        full_projection = project.project_slice(conn, budget=10**12)
    finally:
        conn.close()

    if dangling:
        exit_code = 1
        sys.stdout.write("dangling topic wikilinks found:\n")
        for src_file, dst_slug in dangling:
            sys.stdout.write(f"- {src_file} -> [[{dst_slug}]]\n")

    if stale_drift:
        exit_code = 1
        sys.stdout.write(
            "live memories whose body announces supersession but whose name: was "
            "never redirected (they leak into the working set):\n"
        )
        for file_name, marker in stale_drift:
            sys.stdout.write(f"- {file_name} (body says {marker}; retire it: set name: 'SUPERSEDED — see ...')\n")

    if len(full_projection.encode("utf-8")) > budget:
        overflow = len(full_projection.encode("utf-8")) - budget
        exit_code = 1
        sys.stderr.write(f"corpus exceeds budget by {overflow} bytes before projection\n")

    if exit_code == 0 and not orphans and topic_count > 2:
        sys.stdout.write("qhaway check passed\n")
    return exit_code


def _stale_drift(conn) -> list[tuple[str, str]]:
    """Find live nodes whose body announces supersession but whose name: was
    never rewritten to the redirect form — so parse left status=live and the
    projector serves them as current. This is the silent-staleness leak: the
    conscientious in-body 'SUPERSEDED' annotation never reaches the one field
    the retire path keys on. Conservative by design (a tombstone word as a
    leading/emphasized token on its own line, not a passing mention) so a
    correctly-live memory that merely discusses supersession is not nagged.
    """
    drift: list[tuple[str, str]] = []
    for file_name, status, body in conn.execute(
        "SELECT file, status, body FROM nodes ORDER BY file"
    ).fetchall():
        if status != "live":
            continue
        marker = _body_supersession_marker(body or "")
        if marker:
            drift.append((file_name, marker))
    return drift


def _body_supersession_marker(body: str) -> str | None:
    for raw in body.splitlines():
        line = raw.strip().lstrip("*_# ").strip()
        upper = line.upper()
        for word in parse.TOMBSTONE_NAMES:
            if upper.startswith(word):
                return word
    return None


def _dangling_links(conn) -> list[tuple[str, str]]:
    stems = {row[0].removesuffix(".md") for row in conn.execute("SELECT file FROM nodes").fetchall()}
    dangling: list[tuple[str, str]] = []
    for src_file, dst_slug in conn.execute(
        "SELECT src_file, dst_slug FROM edges ORDER BY src_file, dst_slug"
    ).fetchall():
        if dst_slug not in stems:
            dangling.append((src_file, dst_slug))
    return dangling


def _orphan_files(memory_dir: Path) -> list[Path]:
    return sorted(memory_dir.glob("MEMORY-*.md"), key=lambda path: path.name)


if __name__ == "__main__":
    raise SystemExit(main())
