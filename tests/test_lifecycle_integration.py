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


def test_dormant_then_active_via_topic_file(tmp_path, capsys):
    proj = tmp_path / "proj"; proj.mkdir()
    derived = tmp_path / ".claude/projects" / str(proj).replace("/", "-") / "memory"
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path)}
    # 1) dormant: no memory dir at all -> no-op, nothing written
    assert _run(["session-start"], env) == 0
    assert not (derived / "MEMORY.md").exists()
    capsys.readouterr()
    # 2) memory appears (a topic file is written)
    derived.mkdir(parents=True)
    (derived / "first.md").write_text("---\nname: First\ndescription: hook\nmetadata:\n  type: project\n---\nbody\n")
    # 3) next session activates: MEMORY.md is reconciled and the projection is emitted
    assert _run(["session-start"], env) == 0
    assert (derived / "MEMORY.md").exists()
    assert "First" in capsys.readouterr().out


def test_lone_handwritten_memory_md_stays_dormant(tmp_path):
    proj = tmp_path / "proj"; proj.mkdir()
    derived = tmp_path / ".claude/projects" / str(proj).replace("/", "-") / "memory"
    derived.mkdir(parents=True)
    (derived / "MEMORY.md").write_text("# hand written, no topics\n")
    env = {"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(tmp_path)}
    before = (derived / "MEMORY.md").read_text()
    # a lone MEMORY.md is NOT "has memory" -> dormant, file untouched
    assert _run(["session-start"], env) == 0
    assert (derived / "MEMORY.md").read_text() == before
