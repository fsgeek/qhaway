"""qhaway must land in the SAME directory Claude Code uses for a project.

CC's rule, read from the 2.1.283 binary (2026-09-27):
    k(e)  = e.replace(/[^a-zA-Z0-9]/g, "-")
    qx(e) = len(k(e)) <= 200 ? k(e) : k(e)[:200] + "-" + base36(|KJ(e)|)
    KJ(t) = 32-bit Java-style string hash over UTF-16 code units
qhaway replaced only "/", so any project path with "_", ".", " " — or any
native-Windows path ("C:\\...") — derived a directory CC had abandoned or never
used (field report: levadura_salvaje vs levadura-salvaje). Expected values
below were computed by node, not by the port under test.
"""

from __future__ import annotations

from pathlib import Path

from qhaway import paths

HOME = Path("/h")
PROJ = HOME / ".claude/projects"


def test_every_non_alphanumeric_becomes_a_dash():
    assert paths.memory_dir_for("/home/tony/projects/levadura_salvaje", home=HOME) == (
        PROJ / "-home-tony-projects-levadura-salvaje/memory"
    )
    assert paths.memory_dir_for("/home/tony/projects/wamason.com", home=HOME) == (
        PROJ / "-home-tony-projects-wamason-com/memory"
    )


def test_native_windows_paths_match_cc():
    assert paths.memory_dir_for(r"C:\Users\TonyMason\source\repos\pablo", home=HOME) == (
        PROJ / "C--Users-TonyMason-source-repos-pablo/memory"
    )


def test_non_bmp_characters_count_as_two_utf16_units():
    assert paths.memory_dir_for("/home/tony/p/a\N{GRINNING FACE}b", home=HOME) == (
        PROJ / "-home-tony-p-a--b/memory"
    )


def test_long_paths_truncate_with_cc_hash():
    long_path = "/home/tony/projects/very_long.dir-namevery_long.dir-namevery_long.dir-namevery_long.dir-namevery_long.dir-namevery_long.dir-namevery_long.dir-namevery_long.dir-namevery_long.dir-namevery_long.dir-namevery_long.dir-namevery_long.dir-namevery_long.dir-namevery_long.dir-name/leaf"
    assert paths.memory_dir_for(long_path, home=HOME).parent.name == (
        "-home-tony-projects-" + "very-long-dir-name" * 10 + "-pd5s8"
    )


def _topic(d: Path, name: str, text: str = "x") -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(f"---\nname: {name}\ntype: project\n---\n{text}\n", encoding="utf-8")


def test_legacy_rule_store_is_adopted_into_the_cc_dir(tmp_path):
    legacy = tmp_path / ".claude/projects/-p-levadura_salvaje/memory"
    _topic(legacy, "a.md")
    _topic(legacy, "b.md")
    (legacy / "MEMORY.md").write_text("index\n", encoding="utf-8")

    got = paths.derive_from_env({"CLAUDE_PROJECT_DIR": "/p/levadura_salvaje"}, home=tmp_path)

    assert got == tmp_path / ".claude/projects/-p-levadura-salvaje/memory"
    assert sorted(p.name for p in got.iterdir()) == ["MEMORY.md", "a.md", "b.md"]
    assert not legacy.parent.exists()  # emptied legacy project dir is removed


def test_adoption_never_overwrites_and_leaves_collisions_in_place(tmp_path, capsys):
    legacy = tmp_path / ".claude/projects/-p-a_b/memory"
    current = tmp_path / ".claude/projects/-p-a-b/memory"
    _topic(legacy, "same.md", "legacy body")
    _topic(legacy, "only-legacy.md")
    _topic(current, "same.md", "current body")

    got = paths.derive_from_env({"CLAUDE_PROJECT_DIR": "/p/a_b"}, home=tmp_path)

    assert got == current
    assert "current body" in (current / "same.md").read_text(encoding="utf-8")
    assert (current / "only-legacy.md").exists()
    assert "legacy body" in (legacy / "same.md").read_text(encoding="utf-8")  # kept, not lost
    assert str(legacy) in capsys.readouterr().err  # and declared


def test_paths_the_old_rule_already_matched_are_untouched(tmp_path):
    d = tmp_path / ".claude/projects/-p-qhaway/memory"
    _topic(d, "a.md")
    assert paths.derive_from_env({"CLAUDE_PROJECT_DIR": "/p/qhaway"}, home=tmp_path) == d
    assert (d / "a.md").exists()
