"""`qhaway diagnose` answers one question, read-only: does Claude Code cut this
MEMORY.md, and which entries are past the cut? Claude Code loads the first 200
lines and at most 25,000 bytes, cut at the last newline within the limit."""
import os

from qhaway import cli


def _run(args, capsys):
    rc = cli.main(args)
    return rc, capsys.readouterr().out


def _memory(tmp_path, n, width=40):
    lines = ["# Memory", ""] + [
        f"- [Entry {i:03d}](entry-{i:03d}.md) — " + "x" * width for i in range(n)
    ]
    (tmp_path / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_within_limits_says_nothing_is_cut(tmp_path, capsys):
    _memory(tmp_path, 10)
    rc, out = _run(["diagnose", "--dir", str(tmp_path)], capsys)
    assert rc == 0
    assert "nothing is cut" in out


def test_line_cap_names_the_entries_past_the_cut(tmp_path, capsys):
    _memory(tmp_path, 250, width=10)  # 252 lines, well under 25,000 bytes
    rc, out = _run(["diagnose", "--dir", str(tmp_path)], capsys)
    assert rc == 0
    assert "52 of 252 lines are not loaded" in out
    assert "line limit" in out
    assert "Entry 198" in out          # first entry past line 200
    assert "Entry 197" not in out      # line 200 is still loaded
    assert "52 entries are past the cut" in out  # lines 201-252 = entries 198-249


def test_byte_cap_cuts_before_the_line_cap(tmp_path, capsys):
    _memory(tmp_path, 190, width=200)  # 192 lines, ~44KB
    rc, out = _run(["diagnose", "--dir", str(tmp_path)], capsys)
    assert "byte limit" in out
    assert "not loaded" in out


def test_diagnose_writes_nothing(tmp_path, capsys):
    _memory(tmp_path, 300)
    before = sorted(os.listdir(tmp_path))
    _run(["diagnose", "--dir", str(tmp_path)], capsys)
    assert sorted(os.listdir(tmp_path)) == before


def test_missing_memory_file(tmp_path, capsys):
    rc, out = _run(["diagnose", "--dir", str(tmp_path)], capsys)
    assert rc == 1
    assert "No MEMORY.md" in out


def test_limits_can_be_overridden_for_other_hosts(tmp_path, capsys):
    _memory(tmp_path, 100)  # ~6KB: fine for Claude Code, too big for a 3,500-byte reader
    rc, out = _run(["diagnose", "--dir", str(tmp_path), "--bytes", "3500"], capsys)
    assert "up to 3,500 bytes" in out
    assert "cut by the byte limit" in out


def test_default_limits_name_their_source(tmp_path, capsys):
    _memory(tmp_path, 10)
    _, out = _run(["diagnose", "--dir", str(tmp_path)], capsys)
    assert "Claude Code 2.1.304" in out


def test_dir_may_name_the_memory_file_itself(tmp_path, capsys):
    _memory(tmp_path, 10)
    rc, out = _run(["diagnose", "--dir", str(tmp_path / "MEMORY.md")], capsys)
    assert rc == 0
    assert "nothing is cut" in out


def test_a_cut_index_points_at_the_fix(tmp_path, capsys):
    _memory(tmp_path, 250, width=10)
    _, out = _run(["diagnose", "--dir", str(tmp_path)], capsys)
    assert "qhaway init" in out


def test_limits_line_says_they_are_recorded_not_read_from_your_install(tmp_path, capsys):
    _memory(tmp_path, 10)
    _, out = _run(["diagnose", "--dir", str(tmp_path)], capsys)
    assert "as recorded by qhaway" in out
