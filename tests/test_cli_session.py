import os
from pathlib import Path
from qhaway import cli, paths, project


def _run(args, env):
    old = dict(os.environ)
    os.environ.clear(); os.environ.update(env)
    try:
        return cli.main(args)
    finally:
        os.environ.clear(); os.environ.update(old)


def test_session_start_noop_when_no_project_dir(tmp_path, capsys):
    assert _run(["session-start"], {}) == 0  # no CLAUDE_PROJECT_DIR


def test_session_start_noop_when_dir_has_no_topics(tmp_path):
    # CLAUDE_PROJECT_DIR points somewhere whose derived memory dir is empty
    proj = tmp_path / "proj"; proj.mkdir()
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}
    assert _run(["session-start"], env) == 0
    # derived memory dir does not exist / no MEMORY.md written
    derived = paths.memory_dir_for(str(proj), home=tmp_path)
    assert not (derived / "MEMORY.md").exists()


def test_session_start_activates_with_topics(tmp_path):
    proj = tmp_path / "proj"; proj.mkdir()
    derived = paths.memory_dir_for(str(proj), home=tmp_path)
    derived.mkdir(parents=True)
    (derived / "t.md").write_text("---\nname: T\ndescription: hook\nmetadata:\n  type: project\n---\nbody\n")
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}
    assert _run(["session-start"], env) == 0
    assert (derived / "MEMORY.md").exists()


def test_session_end_writes_signed_index_when_active(tmp_path):
    proj = tmp_path / "proj"; proj.mkdir()
    derived = paths.memory_dir_for(str(proj), home=tmp_path)
    derived.mkdir(parents=True)
    (derived / "t.md").write_text("---\nname: T\ndescription: hook\nmetadata:\n  type: project\n---\nbody\n")
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}
    assert _run(["session-end"], env) == 0
    text = (derived / "MEMORY.md").read_text()
    assert "qhaway:v1:" in text  # signed index


def test_session_start_hints_name_recall_not_the_cli(tmp_path, capsys):
    # Session-start stdout is read by a model holding the recall tool; the shell
    # hint (which lacks --dir) is not an instruction it can follow.
    proj = tmp_path / "proj"; proj.mkdir()
    derived = paths.memory_dir_for(str(proj), home=tmp_path)
    derived.mkdir(parents=True)
    for i in range(200):
        (derived / f"t{i:03d}.md").write_text(
            f"---\nname: T{i:03d}\ndescription: {'d' * 150}\nmetadata:\n  type: project\n---\nbody\n"
        )
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}
    assert _run(["session-start"], env) == 0
    out = capsys.readouterr().out
    assert 'recall(type="project")' in out
    assert "qhaway index" not in out


def _overflowing_store(tmp_path):
    proj = tmp_path / "proj"; proj.mkdir()
    derived = paths.memory_dir_for(str(proj), home=tmp_path)
    derived.mkdir(parents=True)
    for i in range(200):
        (derived / f"t{i:03d}.md").write_text(
            f"---\nname: T{i:03d}\ndescription: {'d' * 150}\nmetadata:\n  type: project\n---\nbody\n"
        )
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}
    return derived, env


def test_session_start_fits_the_hook_channel_with_its_footer(tmp_path, capsys):
    # Claude Code puts hook output in context only up to a limit; above it the
    # model gets a short preview of the beginning, and the omissions footer is
    # lost (#46). The whole projection, footer included, must fit.
    _, env = _overflowing_store(tmp_path)
    assert _run(["session-start"], env) == 0
    out = capsys.readouterr().out
    assert len(out) <= project.HOOK_BUDGET
    assert "not shown" in out and 'recall(type="project")' in out


def test_reconcile_emit_defaults_to_the_hook_budget(tmp_path, capsys):
    # The plugin's SessionStart hook runs `reconcile --emit` with no --budget.
    derived, _ = _overflowing_store(tmp_path)
    assert _run(["reconcile", "--emit", "--dir", str(derived)], {}) == 0
    out = capsys.readouterr().out
    assert len(out) <= project.HOOK_BUDGET and "not shown" in out


def test_reconcile_emit_honors_an_explicit_budget(tmp_path, capsys):
    derived, _ = _overflowing_store(tmp_path)
    assert _run(["reconcile", "--emit", "--budget", "20000", "--dir", str(derived)], {}) == 0
    assert len(capsys.readouterr().out) > project.HOOK_BUDGET


def _events(derived):
    import json
    return [json.loads(l) for l in (derived / "events.jsonl").read_text().splitlines()]


def test_session_start_logs_what_it_delivered(tmp_path, capsys):
    # Without this, a delivery over the hook cap was invisible (#46).
    derived, env = _overflowing_store(tmp_path)
    assert _run(["session-start"], env) == 0
    out = capsys.readouterr().out
    [event] = [e for e in _events(derived) if e["verb"] == "session-start"]
    assert event["chars"] == len(out)
    assert event["budget"] == project.HOOK_BUDGET
    assert event["omitted"]["project"] > 0


def test_session_start_keeps_the_newest_project_memories_when_guidance_fills_it(tmp_path, capsys):
    # Standing guidance (user/feedback) first used to take the whole hook budget,
    # crowding out the newest project memories (the handoff a session needs).
    proj = tmp_path / "proj"; proj.mkdir()
    derived = paths.memory_dir_for(str(proj), home=tmp_path)
    derived.mkdir(parents=True)
    for i in range(60):
        (derived / f"f{i:03d}.md").write_text(
            f"---\nname: F{i:03d}\ndescription: {'g' * 150}\nmetadata:\n  type: feedback\n---\nb\n")
    for day in range(1, 21):
        (derived / f"p-2026-09-{day:02d}.md").write_text(
            f"---\nname: P 2026-09-{day:02d}\ndescription: {'w' * 150}\nmetadata:\n  type: project\n---\nb\n")
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}
    assert _run(["session-start"], env) == 0
    out = capsys.readouterr().out
    shown = {d for d in range(1, 21) if f"P 2026-09-{d:02d}" in out}
    assert project.HOOK_FRONTIER > 0 and 20 in shown
    assert set(range(21 - project.HOOK_FRONTIER, 21)) <= shown
    assert "feedback memories not shown" in out
