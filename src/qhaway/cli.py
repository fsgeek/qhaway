"""Entry point for the `qhaway` command."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from qhaway import model, parse, paths, project, server
from qhaway import reconcile as reconcile_mod
from qhaway import setup as setup_mod
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
    sub.add_parser("session-start")
    sub.add_parser("session-end")
    sub.add_parser("init")
    sub.add_parser("uninstall")

    ns = parser.parse_args(args)

    if ns.command in ("session-start", "session-end"):
        return _session(ns.command)

    if ns.command in ("init", "uninstall"):
        return _setup_cmd(ns.command)

    directory = _resolve_dir(ns)

    if ns.command == "serve":
        return _serve(directory)
    if ns.command == "exit":
        return _exit(directory, ns.budget)
    if ns.command == "check" or (ns.command == "index" and ns.check):
        return _check(directory, ns.budget)
    # A filtered index (--type/--role/--status) is an INSPECTION command — the
    # omissions footer points users here to SEE what the default index set aside.
    # It prints the slice and must not overwrite the balanced MEMORY.md. --dry-run
    # is the explicit form of the same print-only path.
    if ns.command == "index" and (
        ns.dry_run or ns.content_type or ns.role or ns.status
    ):
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


def _setup_cmd(which: str) -> int:
    settings_path = Path.home() / ".claude" / "settings.json"
    if which == "init":
        result = setup_mod.install(settings_path)
        if result == "already":
            sys.stdout.write("qhaway: already installed, nothing to do.\n")
        else:
            sys.stdout.write(
                "qhaway: installed. It activates in any project that has memory;\n"
                "        projects without memory are untouched.\n"
                "        Remove with: uvx qhaway uninstall\n"
            )
        return 0
    result = setup_mod.uninstall(settings_path)
    if result == "absent":
        sys.stdout.write("qhaway: not installed, nothing to do.\n")
    else:
        sys.stdout.write("qhaway: removed. Your MEMORY.md files are left in place.\n")
    return 0


def _session(which: str) -> int:
    """Self-gating SessionStart/SessionEnd entry. Derives the per-project memory
    dir from CLAUDE_PROJECT_DIR and no-ops cleanly when the project has no memory
    (no var, or dir without topic files). One user-scope install thus serves all
    projects without firing where there is nothing to do."""
    memory_dir = paths.derive_from_env(os.environ)
    if memory_dir is None or not paths.has_memory(memory_dir):
        return 0  # dormant — touch nothing
    directory = str(memory_dir)
    if which == "session-start":
        reconcile(directory)
        conn = model.get_connection(directory)
        try:
            sys.stdout.write(project.project_slice(conn, budget=project.DEFAULT_BUDGET))
        finally:
            conn.close()
        return 0
    return _exit(directory, project.DEFAULT_BUDGET)


def _resolve_dir(ns, environ=None, home=None) -> str:
    """Resolve the memory dir. Explicit --dir wins, then QHAWAY_MEMORY_DIR, then
    the slug dir derived from CLAUDE_PROJECT_DIR (so serve, session-start, and
    session-end all land on the same per-project dir), then the cwd."""
    environ = os.environ if environ is None else environ
    if ns.dir:
        return ns.dir
    if environ.get("QHAWAY_MEMORY_DIR"):
        return environ["QHAWAY_MEMORY_DIR"]
    derived = paths.derive_from_env(environ, home=home)
    if derived is not None:
        return str(derived)
    return "."


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
    """SessionEnd: leave a current, self-sufficient, truncation-proof index in
    place — NOT the pre-install original. qhaway borrows MEMORY.md while enabled
    and returns a current honest index when it leaves; the original is preserved
    under its distinguished name (MEMORY.preinstall.md) for an explicit uninstall,
    never handed back here. Worst case (a future loader truncates the file), the
    index degrades gracefully and declares what it set aside; the raw original
    would truncate into silent staleness — the exact failure qhaway prevents.

    The index is budgeted (the footer's bytes are reserved within the budget, not
    appended past it) and carries no recall()/remember() instructions, since the
    hooks are not guaranteed to run once the plugin is disabled.
    """
    memory_dir = Path(directory)
    if not memory_dir.is_dir():
        sys.stderr.write(f"memory directory is not readable: {memory_dir}\n")
        return 1

    reconcile(directory)
    conn = model.get_connection(directory)
    try:
        total = len(model.topic_files(memory_dir))

        def compose_footer(omitted: int) -> str:
            return (
                f"\n\n---\n_qhaway exit index — {total} memories under {budget} "
                f"bytes; {omitted} set aside. Self-sufficient static index "
                "(qhaway disabled)._\n"
            )

        # Probe at full budget only to SIZE the reserve (footer + signature bytes);
        # the displayed "set aside" count comes from the FINAL reduced-budget
        # projection, so the footer reports what the shipped file actually omits —
        # honest declaration is the whole point. The count's digit width is bounded
        # (a few hundred memories at most), so any drift between probe and final
        # count is sub-byte against the reserve and never pushes over budget.
        probe = project.project_slice_with_overflow(conn, budget=budget)
        reserve = (
            len(compose_footer(sum(probe.overflow.omitted_counts.values())).encode("utf-8"))
            + len(reconcile_mod.signature_line(""))
            + 2
        )
        result = project.project_slice_with_overflow(conn, budget=max(0, budget - reserve))
        footer = compose_footer(sum(result.overflow.omitted_counts.values()))
    finally:
        conn.close()
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
