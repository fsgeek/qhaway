import os
from pathlib import Path
from qhaway import cli


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
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path)}
    assert _run(["session-start"], env) == 0
    # derived memory dir does not exist / no MEMORY.md written
    derived = tmp_path / ".claude/projects" / str(proj).replace("/", "-") / "memory"
    assert not (derived / "MEMORY.md").exists()


def test_session_start_activates_with_topics(tmp_path):
    proj = tmp_path / "proj"; proj.mkdir()
    derived = tmp_path / ".claude/projects" / str(proj).replace("/", "-") / "memory"
    derived.mkdir(parents=True)
    (derived / "t.md").write_text("---\nname: T\ndescription: hook\nmetadata:\n  type: project\n---\nbody\n")
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path)}
    assert _run(["session-start"], env) == 0
    assert (derived / "MEMORY.md").exists()


def test_session_end_writes_signed_index_when_active(tmp_path):
    proj = tmp_path / "proj"; proj.mkdir()
    derived = tmp_path / ".claude/projects" / str(proj).replace("/", "-") / "memory"
    derived.mkdir(parents=True)
    (derived / "t.md").write_text("---\nname: T\ndescription: hook\nmetadata:\n  type: project\n---\nbody\n")
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path)}
    assert _run(["session-end"], env) == 0
    text = (derived / "MEMORY.md").read_text()
    assert "qhaway:v1:" in text  # signed index
