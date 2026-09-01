"""qhaway must run on native Windows (Claude Desktop's majority host), not only
POSIX. Two things broke there, found by running the suite under Windows Python
on NTFS (2026-09-01): `import fcntl` fails at collection, and os.replace() over
the born-read-only MEMORY.md raises PermissionError — so every second write of
the index crashed. These pass on POSIX already; the Windows CI runner is what
makes them bite.
"""

from __future__ import annotations

from pathlib import Path

from qhaway import model, reconcile


def test_write_readonly_can_replace_its_own_previous_output(tmp_path):
    target = tmp_path / "MEMORY.md"
    reconcile.write_readonly(target, "first\n")

    reconcile.write_readonly(target, "second\n")

    assert target.read_text(encoding="utf-8") == "second\n"


def test_rebuild_database_takes_its_lock_on_every_platform(tmp_path):
    (tmp_path / "one.md").write_text(
        "---\nname: one\ntype: project\ndescription: d\n---\nbody\n", encoding="utf-8"
    )
    model.rebuild_database(str(tmp_path))
    conn = model.get_connection(str(tmp_path))
    try:
        assert [n["file"] for n in model.fetch_nodes(conn)] == ["one.md"]
    finally:
        conn.close()
