"""Entry point for the `qhaway` command."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from qhaway import __version__, model, parse, paths, project, server
from qhaway import reconcile as reconcile_mod
from qhaway import setup as setup_mod
from qhaway.reconcile import reconcile

MEMORY_NAME = "MEMORY.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qhaway")
    parser.add_argument("--version", action="version", version=f"qhaway {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("reconcile", "check", "serve", "index", "exit"):
        p = sub.add_parser(name)
        p.add_argument("--dir")
        p.add_argument("--budget", type=int)  # default: DEFAULT_BUDGET; HOOK_BUDGET for --emit
        p.add_argument("--type", dest="content_type")
        p.add_argument("--role")
        # default None, NOT "live": the index dispatch must see whether the user
        # actually passed a filter — a truthy default routed EVERY bare `index`
        # to the print-only path (the e2f297e regression). Consumers normalize.
        p.add_argument("--status", default=None)
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--check", action="store_true")  # deprecated alias on index
        p.add_argument("--emit", action="store_true")
        # serve only: keep MEMORY.md the always-current budgeted index (at
        # --budget) instead of the redirect — for hookless hosts (Cowork/Desktop)
        # that load MEMORY.md directly through a truncating reader.
        p.add_argument("--inline-index", action="store_true")
    sub.add_parser("session-start")
    sub.add_parser("session-end")
    diagnose = sub.add_parser("diagnose", help="read-only: does Claude Code cut this MEMORY.md?")
    diagnose.add_argument("--dir", help="memory directory (or its MEMORY.md); default: this "
                          "project's, as Claude Code names it from the current directory")
    diagnose.add_argument("--lines", type=int, help="line limit (default: Claude Code's)")
    diagnose.add_argument("--bytes", type=int, help="byte limit (default: Claude Code's)")
    for command, aliases in (("init", ["install"]), ("uninstall", [])):
        p = sub.add_parser(command, aliases=aliases)
        p.add_argument("--host", choices=("claude", "codex"), default="claude")
        p.add_argument("--project", help="Codex project directory (default: current directory)")
        if command == "init":
            p.add_argument("--dir", help="Codex curated-memory directory (default: ~/.qhaway/projects/...)")
    return parser


def main(args: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(args)
    explicit_budget = getattr(ns, "budget", None)
    if explicit_budget is None and hasattr(ns, "budget"):
        ns.budget = project.DEFAULT_BUDGET

    if ns.command in ("session-start", "session-end"):
        return _session(ns.command)

    if ns.command in ("init", "install", "uninstall"):
        if ns.host == "codex":
            return _codex_setup_cmd(ns.command, ns.project, getattr(ns, "dir", None))
        if ns.project is not None or getattr(ns, "dir", None) is not None:
            parser.error("--project and --dir require --host codex")
        return _setup_cmd(ns.command)

    if ns.command == "diagnose":
        return _diagnose(ns.dir, ns.lines or LOADER_LINES, ns.bytes or LOADER_BYTES)

    directory = _resolve_dir(ns)
    if directory is None:
        sys.stderr.write("no memory directory: pass --dir /path/to/memory "
                         "(there is no ~/.claude to derive one from)\n")
        return 2

    if ns.command == "serve":
        return _serve(directory, ns.budget if ns.inline_index else None)
    if ns.command == "exit":
        return _exit(directory, ns.budget)
    if ns.command == "check" or (ns.command == "index" and ns.check):
        return _check(directory, ns.budget)
    # A filtered index (--type/--role/--status) is an INSPECTION command — the
    # omissions footer points users here to SEE what the default index set aside.
    # It prints the slice and must not overwrite the balanced MEMORY.md. --dry-run
    # is the explicit form of the same print-only path.
    if ns.command == "index" and (
        ns.dry_run or ns.content_type or ns.role or ns.status is not None
    ):
        return _dry_run(directory, ns)

    # Bare `index` — the README's main command: regenerate MEMORY.md as the
    # budgeted, self-sufficient index (omissions declared), for the standalone
    # user whose loader reads the file directly. Not the redirect stub: that is
    # serve/session territory, where a hook or the server delivers the memory.
    if ns.command == "index":
        try:
            reconcile_mod.reconcile(directory, heal=False)
            write_index(directory, ns.budget, style="exit")
        except FileNotFoundError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1
        return 0

    # reconcile (and its --emit debugging form)
    try:
        reconcile(directory)
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    if getattr(ns, "emit", False):
        conn = model.get_connection(directory)
        try:
            budget = project.HOOK_BUDGET if explicit_budget is None else explicit_budget
            result = project.project_slice_with_overflow(
                conn, budget=budget, frontier=project.HOOK_FRONTIER)
        finally:
            conn.close()
        sys.stdout.write(result.markdown)
        # The plugin's SessionStart hook delivers through here.
        server._emit(Path(directory), {"verb": "session-start", "chars": len(result.markdown),
                                       "budget": budget, "omitted": result.overflow.omitted_counts})
    return 0


def _codex_setup_cmd(which: str, project_dir: str | None, memory_dir: str | None) -> int:
    from qhaway import codex_setup

    project_root = Path(project_dir) if project_dir else Path.cwd()
    codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    if which != "uninstall" and not codex_home.is_dir():
        sys.stderr.write(
            f"qhaway: note: no ~/.codex (or $CODEX_HOME) at {codex_home}, so Codex hasn't run on this machine.\n"
            "        Writing the project configuration anyway; it takes effect once Codex is installed.\n"
        )
    try:
        result, store = codex_setup.configure(
            project_root, Path(memory_dir) if memory_dir else None,
            remove=which == "uninstall",
        )
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"qhaway: {exc}\n")
        return 1
    label = {"already": "already installed", "absent": "not installed"}.get(result, result)
    sys.stdout.write(f"qhaway: Codex {label} for {project_root.expanduser().resolve()}.\n")
    if store is not None:
        sys.stdout.write(
            f"        Curated memory: {store}\n"
            "        Restart Codex in this trusted project; check /mcp, then recall(limit=0).\n"
            "        Remove here with: uvx --isolated qhaway uninstall --host codex\n"
            "        This writes machine-local .codex/config.toml; keep personal paths out of commits.\n"
        )
    else:
        sys.stdout.write("        Memory files are preserved. Restart Codex to disconnect.\n")
    return 0


def _setup_cmd(which: str) -> int:
    home = Path.home()
    settings_path = home / ".claude" / "settings.json"  # hooks (PUSH)
    mcp_config_path = home / ".claude.json"             # MCP server (PULL)
    if which in ("init", "install"):
        if not (home / ".claude").is_dir():
            sys.stderr.write(
                "qhaway: note: no ~/.claude here, so Claude Code hasn't run on this machine.\n"
                "        Writing the configuration anyway; it takes effect once Claude Code is installed.\n"
            )
        result = setup_mod.install(settings_path, mcp_config_path=mcp_config_path)
        if result == "already":
            sys.stdout.write("qhaway: already installed, nothing to do.\n")
        elif result == "updated":
            sys.stdout.write(
                "qhaway: updated qhaway's commands to run with uvx --isolated.\n"
                "        Restart Claude Code to load the change.\n"
            )
        else:
            sys.stdout.write(
                "qhaway: installed (boot hooks + recall/remember MCP server).\n"
                "        It activates in any project that has memory;\n"
                "        projects without memory are untouched.\n"
                "        Restart Claude Code for the MCP server to load.\n"
                "        Remove with: uvx --isolated qhaway uninstall\n"
            )
        return 0
    result = setup_mod.uninstall(settings_path, mcp_config_path=mcp_config_path)
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
            result = project.project_slice_with_overflow(
                conn, budget=project.HOOK_BUDGET, hint="tool", frontier=project.HOOK_FRONTIER)
        finally:
            conn.close()
        sys.stdout.write(result.markdown)
        # What reached the hook channel, against its budget: the record #46 lacked.
        server._emit(memory_dir, {"verb": "session-start", "chars": len(result.markdown),
                                  "budget": project.HOOK_BUDGET,
                                  "omitted": result.overflow.omitted_counts})
        return 0
    return _exit(directory, project.DEFAULT_BUDGET)


# Claude Code's MEMORY.md load caps: the first 200 lines, and at most 25,000
# bytes cut at the last newline within the limit. Read from Claude Code 2.1.304's
# own code on 2026-10-20 (`cp="MEMORY.md",mF=200,Ule=25000`);
# scripts/check_cc_limits.py re-checks an installed build.
LOADER_LINES = 200
LOADER_BYTES = 25_000
_ENTRY = re.compile(r"^\s*- \[(.+?)\]\(")


def _diagnose(explicit_dir: str | None, max_lines: int, max_bytes: int) -> int:
    """Report whether Claude Code's loader cuts MEMORY.md, and which entries it
    loses. Reads only: no reconcile, no database, and no store adoption (the
    pure memory_dir_for, not paths.resolve), so it is safe on any store."""
    if explicit_dir:
        memory_dir = Path(explicit_dir)
    elif os.environ.get("QHAWAY_MEMORY_DIR"):
        memory_dir = Path(os.environ["QHAWAY_MEMORY_DIR"])
    else:
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        memory_dir = paths.memory_dir_for(str(Path(project_dir).resolve()))
    memory_file = memory_dir if memory_dir.name == MEMORY_NAME else memory_dir / MEMORY_NAME
    if not memory_file.is_file():
        sys.stdout.write(f"No MEMORY.md at {memory_file}. Pass --dir to point at a memory directory.\n")
        return 1

    lines = memory_file.read_bytes().splitlines(keepends=True)
    total_bytes = sum(len(line) for line in lines)
    by_bytes, used = 0, 0
    for line in lines:
        if used + len(line) > max_bytes:
            break
        used += len(line)
        by_bytes += 1
    loaded = min(len(lines), max_lines, by_bytes)
    out = [
        f"{memory_file}",
        f"MEMORY.md: {total_bytes:,} bytes, {len(lines)} lines.",
    ]
    if (max_lines, max_bytes) == (LOADER_LINES, LOADER_BYTES):
        out.append(f"Claude Code loads the first {max_lines} lines, up to {max_bytes:,} bytes "
                   "(Claude Code 2.1.304's limits, as recorded by qhaway). Claude Desktop "
                   "reads less; pass --bytes to check against another limit.")
    else:
        out.append(f"Checking against the first {max_lines} lines, up to {max_bytes:,} bytes.")
    if loaded == len(lines):
        out.append("Within both limits: nothing is cut.")
    else:
        limit = "byte" if by_bytes < min(len(lines), max_lines) else "line"
        lost = [m.group(1) for raw in lines[loaded:]
                if (m := _ENTRY.match(raw.decode("utf-8", "replace")))]
        out.append(f"{len(lines) - loaded} of {len(lines)} lines are not loaded "
                   f"(cut by the {limit} limit after line {loaded}).")
        if lost:
            out.append(f"{len(lost)} entries are past the cut. If new entries are added at "
                       "the bottom, these are the newest:")
            out += [f"  - {title}" for title in lost[:10]]
            if len(lost) > 10:
                out.append(f"  +{len(lost) - 10} more")
        out.append("To keep the index within the limit and the rest one call away: "
                   "uvx qhaway init (see the README).")
    out.append("(diagnose only reads; nothing was changed.)")
    sys.stdout.write("\n".join(out) + "\n")
    return 0


def _resolve_dir(ns, environ=None, home=None, cwd=None) -> str | None:
    """Resolve the memory dir. Explicit --dir wins, then QHAWAY_MEMORY_DIR, then
    the slug dir derived from CLAUDE_PROJECT_DIR (so serve, session-start, and
    session-end all land on the same per-project dir), then the slug dir derived
    from the cwd — an interactive `qhaway index` run inside a project must reach
    that project's store, never index the project's own markdown as memories.
    None when only the cwd fallback is left and there is no ~/.claude: that user
    doesn't run Claude Code, so there is no store to derive."""
    environ = os.environ if environ is None else environ
    if ns.dir:
        return ns.dir
    if environ.get("QHAWAY_MEMORY_DIR"):
        return environ["QHAWAY_MEMORY_DIR"]
    derived = paths.derive_from_env(environ, home=home)
    if derived is not None:
        return str(derived)
    home = Path.home() if home is None else home
    if not (home / ".claude").is_dir():
        return None
    cwd = os.getcwd() if cwd is None else cwd
    return str(paths.resolve(cwd, home=home))


def _serve(directory: str, inline_budget: int | None = None) -> int:
    # A fresh project has no memory dir yet. serve must PROVISION it, not reject
    # it — otherwise CC sees the process exit and reports a failed MCP connection,
    # and the first remember() could never create the first memory. Create the
    # dir (parents included) so the server starts ready to write. A genuinely
    # unwritable path still fails — cleanly, to stderr, never to stdout (G-5).
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.stderr.write(f"cannot create memory directory {directory}: {exc}\n")
        return 1
    server.run(directory, inline_budget=inline_budget)
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
            status=ns.status or "live",
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
    write_index(directory, budget, style="exit")
    return 0


def write_index(directory: str, budget: int, style: str = "exit") -> None:
    """Compose and write the budgeted, signed index into MEMORY.md. Styles:
    "exit" — the session-end static index, no tool instructions since neither
    hooks nor server are guaranteed once written; "live" — inline-index serve
    mode for hookless hosts, where the server is by definition running, so the
    footer points at recall()/remember() for the full store.

    Callers reconcile first; this composes from the db as it stands.
    """
    memory_dir = Path(directory)
    conn = model.get_connection(directory)
    try:
        # Live memories, as the header counts them; superseded ones are declared
        # in the footer, not here (#55).
        survey = project.project_slice_with_overflow(conn, budget=budget, limit=0)
        total = sum(survey.overflow.omitted_counts.values())

        def compose_footer(omitted: int) -> str:
            if style == "live":
                return (
                    f"\n\n---\n_qhaway live index — {total} memories under {budget} "
                    f"bytes; {omitted} set aside. Call recall() for the full "
                    "working set; remember() writes._\n"
                )
            return (
                f"\n\n---\n_qhaway exit index — {total} memories under {budget} "
                f"bytes; {omitted} set aside. A static index; it does not "
                "update itself._\n"
            )

        # Probe at full budget only to SIZE the reserve (footer + signature bytes);
        # the displayed "set aside" count comes from the FINAL reduced-budget
        # projection, so the footer reports what the shipped file actually omits —
        # honest declaration is the whole point. The count's digit width is bounded
        # (a few hundred memories at most), so any drift between probe and final
        # count is sub-byte against the reserve and never pushes over budget.
        hint = "tool" if style == "live" else "cli"
        probe = project.project_slice_with_overflow(conn, budget=budget, hint=hint)
        reserve = (
            len(compose_footer(sum(probe.overflow.omitted_counts.values())).encode("utf-8"))
            + len(reconcile_mod.signature_line(""))
            + 2
        )
        result = project.project_slice_with_overflow(
            conn, budget=max(0, budget - reserve), hint=hint
        )
        footer = compose_footer(sum(result.overflow.omitted_counts.values()))
    finally:
        conn.close()
    memory_file = memory_dir / MEMORY_NAME
    reconcile_mod.snapshot_unowned(memory_file)
    reconcile_mod.write_readonly(
        memory_file, reconcile_mod.embed_signature(result.markdown + footer)
    )


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
        edge_superseded = _edge_superseded(conn)
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

    if edge_superseded:
        exit_code = 1
        sys.stdout.write(
            "live memories a winner declared it supersedes (recall demotes them, "
            "but the file still reads status: live):\n"
        )
        for file_name in edge_superseded:
            sys.stdout.write(f"- {file_name} (target of a supersedes: edge)\n")

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


def _edge_superseded(conn) -> list[str]:
    """The PRECISE staleness path: live nodes that are the target of a SUPERSEDES
    edge (a winner declared `supersedes: [[loser]]`). Unlike _stale_drift's body
    scrape, this is an exact lookup — the structured signal the prose heuristic
    was a stand-in for. A node explicitly tombstoned (status != live) is already
    handled by the projector and not re-reported here.
    """
    rows = conn.execute(
        """
        SELECT n.file FROM nodes n
        JOIN edges e ON e.dst_slug = substr(n.file, 1, length(n.file) - 3)
        WHERE e.kind = 'SUPERSEDES' AND n.status = 'live'
        ORDER BY n.file
        """
    ).fetchall()
    return [row[0] for row in rows]


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
