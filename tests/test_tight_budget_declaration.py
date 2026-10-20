"""The written index always declares what it left out (#55).

A bare `qhaway index` reused the session-end trailer, which said "(qhaway
disabled)" and counted superseded files that the header did not. At small
budgets the per-type omissions footer could not fit, and the projection kept
the header alone, so a reader saw "showing 0" with no idea what was missing.
"""
import re

from qhaway import cli, model, project


def _store(root):
    for stem, kind, desc, extra in [
        ("u", "user", "likes tea", ""),
        ("f", "feedback", "test first", ""),
        ("p1", "project", "old plan", ""),
        ("p2", "project", "new plan", "supersedes: [p1]\n"),
    ]:
        (root / f"{stem}.md").write_text(
            f"---\nname: {stem}\ntype: {kind}\ndescription: {desc}\n{extra}---\nb\n")


def test_bare_index_trailer_agrees_with_header_and_does_not_claim_disabled(tmp_path):
    _store(tmp_path)
    assert cli.main(["index", "--dir", str(tmp_path)]) == 0
    text = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")  # not the locale: cp1252 on Windows
    assert text.splitlines()[0] == "3 matching memories; all shown."
    assert re.search(r"— 3 memories under \d+ bytes; 0 set aside", text)
    assert "qhaway disabled" not in text


def test_tight_budget_keeps_a_count_of_what_was_left_out(tmp_path):
    _store(tmp_path)
    model.rebuild_database(str(tmp_path))
    conn = model.get_connection(str(tmp_path))
    try:
        out = project.project_slice(conn, budget=100)
    finally:
        conn.close()
    assert len(out.encode()) <= 100
    assert out.splitlines()[0].endswith("showing 0.")
    assert "+3 not shown: 1 user, 1 feedback, 1 project." in out


def test_small_written_index_still_declares_omissions(tmp_path):
    _store(tmp_path)
    assert cli.main(["index", "--dir", str(tmp_path), "--budget", "300"]) == 0
    text = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")  # not the locale: cp1252 on Windows
    assert len(text.encode()) <= 300
    assert text.startswith("3 matching memories")
    assert "not shown" in text
