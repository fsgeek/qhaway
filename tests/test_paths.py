"""The init split-brain fix: every command derives ONE memory dir.

`serve`, `reconcile` (session-start), and `exit` (session-end) must all resolve
to the SAME per-project memory dir — Claude Code's own slug dir
`~/.claude/projects/<CLAUDE_PROJECT_DIR with / -> ->/memory` — when no explicit
--dir is given. A hardcoded project-local --dir in the plugin manifest is what
splits the brain; this pins the single source of truth.
"""

from pathlib import Path

from qhaway import cli, paths


HOME = Path("/home/tony")


def test_paths_derives_slug_dir():
    got = paths.memory_dir_for("/home/tony/projects/qhaway", home=HOME)
    assert got == HOME / ".claude/projects/-home-tony-projects-qhaway/memory"


def test_paths_from_env_returns_none_without_project_dir():
    assert paths.derive_from_env({}, home=HOME) is None
    assert paths.derive_from_env({"CLAUDE_PROJECT_DIR": ""}, home=HOME) is None


def test_paths_from_env_derives_slug_dir():
    env = {"CLAUDE_PROJECT_DIR": "/home/tony/projects/qhaway"}
    got = paths.derive_from_env(env, home=HOME)
    assert got == HOME / ".claude/projects/-home-tony-projects-qhaway/memory"


def _resolve(argv, environ):
    # Parse args the way main() does, then resolve, without running the command.
    import argparse

    parser = argparse.ArgumentParser(prog="qhaway")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("reconcile", "check", "serve", "index", "exit"):
        p = sub.add_parser(name)
        p.add_argument("--dir")
        p.add_argument("--budget", type=int, default=24_000)
        p.add_argument("--type", dest="content_type")
        p.add_argument("--role")
        p.add_argument("--status", default="live")
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--check", action="store_true")
        p.add_argument("--emit", action="store_true")
    parsed = parser.parse_args(argv)
    return cli._resolve_dir(parsed, environ=environ, home=HOME)


def test_serve_with_no_dir_resolves_to_slug_dir():
    env = {"CLAUDE_PROJECT_DIR": "/home/tony/projects/qhaway"}
    got = _resolve(["serve"], env)
    assert got == str(HOME / ".claude/projects/-home-tony-projects-qhaway/memory")


def test_reconcile_and_exit_resolve_to_same_dir_as_serve():
    env = {"CLAUDE_PROJECT_DIR": "/home/tony/projects/qhaway"}
    serve_dir = _resolve(["serve"], env)
    start_dir = _resolve(["reconcile", "--emit"], env)
    end_dir = _resolve(["exit"], env)
    assert serve_dir == start_dir == end_dir


def test_explicit_dir_still_wins_over_derivation():
    env = {"CLAUDE_PROJECT_DIR": "/home/tony/projects/qhaway"}
    got = _resolve(["serve", "--dir", "/tmp/explicit"], env)
    assert got == "/tmp/explicit"
