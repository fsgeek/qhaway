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


def test_index_bytes_on_disk_are_the_bytes_budgeted(tmp_path):
    # Text-mode writes turn "\n" into "\r\n" on Windows, so a file budgeted at N
    # bytes ships larger than N — and the host's truncating reader counts bytes.
    target = tmp_path / "MEMORY.md"
    text = "line one\nline two\n"
    reconcile.write_readonly(target, text)

    assert target.read_bytes() == text.encode("utf-8")


def test_write_readonly_survives_concurrent_writers_and_readers(tmp_path):
    # Two remember() calls reconcile at once, and a host's truncating reader may
    # hold MEMORY.md open at any moment. On Windows a rename over a file that is
    # read-only, or open in another handle, fails — the writer must ride that
    # out, not raise. (CI windows-latest failed test_cli_concurrent_remember on
    # exactly this; a fast local box never hit the window.)
    import threading

    target = tmp_path / "MEMORY.md"
    errors: list[BaseException] = []
    stop = False

    def writer(i: int) -> None:
        for n in range(60):
            try:
                reconcile.write_readonly(target, f"writer {i} round {n}\n" * 40)
            except BaseException as exc:  # noqa: BLE001 - collect, then assert
                errors.append(exc)

    def reader() -> None:
        while not stop:
            try:
                target.read_text(encoding="utf-8")
            except FileNotFoundError:
                pass  # between the very first temp+replace only

    writers = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    readers = [threading.Thread(target=reader) for _ in range(2)]
    for t in writers + readers:
        t.start()
    for t in writers:
        t.join()
    stop = True
    for t in readers:
        t.join()

    assert errors == []
    assert target.read_text(encoding="utf-8").startswith("writer ")
