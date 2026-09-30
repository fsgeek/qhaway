"""An older qhaway leaves a newer qhaway's index alone (#37).

The index is derived and rebuildable, so a schema mismatch used to mean
"delete and rebuild" in both directions. Two versions sharing a store then
destroyed each other's index in turn. A newer-than-known schema is now left
untouched: this process reads the topic files into an in-memory index instead.
"""
import sqlite3

from qhaway import model, server


def _write(root, stem):
    (root / f"{stem}.md").write_text(
        f"---\nname: {stem}\ntype: project\ndescription: d {stem}\n---\nbody\n", encoding="utf-8"
    )


def _stamp_newer(root):
    conn = sqlite3.connect(str(model.db_path(root)))
    conn.execute("CREATE TABLE future_marker (x INTEGER)")
    conn.execute(f"PRAGMA user_version = {model.SCHEMA_VERSION + 1}")
    conn.commit()
    conn.close()


def _disk_state(root):
    conn = sqlite3.connect(str(model.db_path(root)))
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return version, tables
    finally:
        conn.close()


def test_newer_index_is_left_untouched_and_the_files_are_read(tmp_path, capsys):
    _write(tmp_path, "alpha")
    _write(tmp_path, "beta")
    _stamp_newer(tmp_path)

    conn = model.get_connection(str(tmp_path))
    try:
        files = sorted(r["file"] for r in model.fetch_nodes(conn))
    finally:
        conn.close()

    assert files == ["alpha.md", "beta.md"]
    version, tables = _disk_state(tmp_path)
    assert version == model.SCHEMA_VERSION + 1 and "future_marker" in tables
    assert "newer qhaway" in capsys.readouterr().err


def test_recall_works_over_a_newer_index(tmp_path):
    _write(tmp_path, "alpha")
    _stamp_newer(tmp_path)

    text = server.recall(memory_dir=str(tmp_path))

    assert "alpha" in text
    assert _disk_state(tmp_path)[0] == model.SCHEMA_VERSION + 1


def test_an_older_index_is_still_rebuilt(tmp_path):
    _write(tmp_path, "alpha")
    conn = sqlite3.connect(str(model.db_path(tmp_path)))
    conn.execute("CREATE TABLE nodes (file TEXT PRIMARY KEY)")
    conn.execute(f"PRAGMA user_version = {model.SCHEMA_VERSION - 1}")
    conn.commit()
    conn.close()

    model.get_connection(str(tmp_path)).close()

    assert _disk_state(tmp_path)[0] == model.SCHEMA_VERSION
