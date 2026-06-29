"""Build the embedded qhaway SQLite index from topic files."""

from __future__ import annotations

import fcntl
import json
import sqlite3
import sys
import time
from pathlib import Path

from qhaway import parse

SCHEMA_VERSION = 2
DB_NAME = ".qhaway.db"
LOCK_NAME = ".qhaway.db.reset.lock"
_DB_SUFFIXES = ("", "-wal", "-shm")
_DRIFT_MARKERS = ("no such column", "no such table")

_CREATE_NODES = """
CREATE TABLE IF NOT EXISTS nodes (
    file TEXT PRIMARY KEY,
    name TEXT,
    content_type TEXT,
    description TEXT,
    role TEXT,
    status TEXT,
    origin_session TEXT,
    date_hint TEXT,
    body TEXT,
    mtime_ns INTEGER,
    size INTEGER,
    claim TEXT
)
"""

_CREATE_EDGES = """
CREATE TABLE IF NOT EXISTS edges (
    src_file TEXT NOT NULL,
    dst_slug TEXT NOT NULL,
    kind TEXT NOT NULL,
    PRIMARY KEY (src_file, dst_slug, kind)
)
"""

_CREATE_EDGE_INDEX = "CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges (dst_slug)"

_NODE_COLUMNS = (
    "file", "name", "content_type", "description", "role",
    "status", "origin_session", "date_hint", "body", "mtime_ns", "size",
    "claim",
)


def db_path(memory_dir: str | Path) -> Path:
    return Path(memory_dir) / DB_NAME


def get_connection(memory_dir: str) -> sqlite3.Connection:
    root = Path(memory_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"memory directory is not readable: {memory_dir}")

    if _drifted_on_disk(db_path(root)):
        rebuild_database(str(root))
        return _open_wal(db_path(root))

    conn = _open_wal(db_path(root))
    _ensure_populated(conn, root)
    return conn


def _open_wal(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    except sqlite3.OperationalError as exc:
        conn.close()
        raise RuntimeError(
            "qhaway requires SQLite WAL mode, which this filesystem does not "
            f"support (move the memory dir to local storage): {exc}"
        ) from exc
    if mode is not None and str(mode[0]).lower() != "wal":
        conn.close()
        raise RuntimeError(
            "qhaway requires SQLite WAL mode; the filesystem refused it "
            "(move the memory dir to local storage)"
        )
    preexisting = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='nodes'"
    ).fetchone()
    conn.execute(_CREATE_NODES)
    conn.execute(_CREATE_EDGES)
    conn.execute(_CREATE_EDGE_INDEX)
    # Only stamp the schema version on a db we actually created. Re-stamping a
    # pre-existing db would silently mask a user_version mismatch (split-brain:
    # a replica claiming a version its schema does not match). Drift on an
    # existing db is caught by _drifted_on_disk before we ever reach here.
    if preexisting is None:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    return conn


def _drifted_on_disk(path: Path) -> bool:
    """Detect old-schema drift on a pre-existing db before we open/normalize it."""
    if not path.exists():
        return False
    conn = sqlite3.connect(str(path))
    try:
        return _schema_drifted(conn)
    finally:
        conn.close()


def _schema_drifted(conn: sqlite3.Connection) -> bool:
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='nodes'"
    ).fetchone()
    if existing is None:
        return False  # no table yet = fresh db, not drift
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    # ANY user_version mismatch on an existing db is drift — older OR newer.
    # A newer-than-expected stamp means a future qhaway wrote it; rebuild from
    # the authoritative files rather than trusting/re-stamping the replica.
    if version != SCHEMA_VERSION:
        return True
    # Defensive: version matches but columns are missing (hand-corrupted db).
    cols = {row[1] for row in conn.execute("PRAGMA table_info(nodes)")}
    if not {"mtime_ns", "size"}.issubset(cols):
        return True
    return False


def _ensure_populated(conn: sqlite3.Connection, root: Path) -> None:
    count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    if count == 0:
        _full_load(conn, root)


def _full_load(conn: sqlite3.Connection, root: Path) -> None:
    conn.execute("DELETE FROM edges")
    conn.execute("DELETE FROM nodes")
    for path in topic_files(root):
        upsert_file(conn, path)
    conn.commit()


def upsert_file(conn: sqlite3.Connection, path: Path) -> None:
    node = parse.parse_memory_file(str(path))
    if node.get("parse_warning"):
        sys.stderr.write(f"warning: {path.name}: {node['parse_warning']}\n")
    stat = path.stat()
    conn.execute("DELETE FROM edges WHERE src_file = ?", [node["file"]])
    conn.execute(
        f"INSERT OR REPLACE INTO nodes ({', '.join(_NODE_COLUMNS)}) "
        f"VALUES ({', '.join('?' for _ in _NODE_COLUMNS)})",
        [
            node["file"], node["name"], node["content_type"], node.get("description"),
            node["role"], node["status"], node["origin_session"], node["date_hint"],
            node["body"], stat.st_mtime_ns, stat.st_size,
            json.dumps(node["claim"]) if node.get("claim") else None,
        ],
    )
    for dst_slug in node["links"]:
        conn.execute(
            "INSERT OR IGNORE INTO edges (src_file, dst_slug, kind) VALUES (?, ?, 'REFERENCES')",
            [node["file"], dst_slug],
        )


def delete_node(conn: sqlite3.Connection, file_name: str) -> None:
    conn.execute("DELETE FROM edges WHERE src_file = ?", [file_name])
    conn.execute("DELETE FROM nodes WHERE file = ?", [file_name])


def fetch_nodes(conn: sqlite3.Connection) -> list[dict]:
    cursor = conn.execute(f"SELECT {', '.join(_NODE_COLUMNS)} FROM nodes")
    columns = [col[0] for col in cursor.description]
    nodes = [dict(zip(columns, row)) for row in cursor.fetchall()]
    for node in nodes:
        node["claim"] = json.loads(node["claim"]) if node.get("claim") else None
    return nodes


def rebuild_database(memory_dir: str) -> None:
    """Destructively delete all db files and rebuild from topic files (drift recovery)."""
    root = Path(memory_dir)
    lock_path = root / LOCK_NAME
    lock_fd = open(lock_path, "a+", encoding="utf-8")
    deadline = time.monotonic() + 5.0
    try:
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"could not acquire reset lock {LOCK_NAME} (another rebuild in progress)"
                    )
                time.sleep(0.1)
        for suffix in _DB_SUFFIXES:
            target = root / f"{DB_NAME}{suffix}"
            if target.exists():
                target.unlink()
        conn = _open_wal(db_path(root))
        try:
            _full_load(conn, root)
        finally:
            conn.close()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        # Do not delete the lock file (avoids deletion races, U2-2).


def execute_query_with_retry(conn, query, memory_dir, params=None, _already_rebuilt=False):
    try:
        return conn.execute(query, params or [])
    except sqlite3.OperationalError as exc:
        message = str(exc).lower()
        is_drift = any(marker in message for marker in _DRIFT_MARKERS)
        if not is_drift or _already_rebuilt:
            raise
        rebuild_database(memory_dir)
        new_conn = get_connection(memory_dir)
        try:
            return execute_query_with_retry(
                new_conn, query, memory_dir, params, _already_rebuilt=True
            )
        finally:
            new_conn.close()


def topic_files(memory_dir: str | Path) -> list[Path]:
    """Return source topic Markdown files, excluding derived indexes and backups."""
    root = Path(memory_dir)
    files: list[Path] = []
    for path in root.glob("*.md"):
        # Exclude qhaway's own MEMORY.md artifacts: the derived index/redirect,
        # timestamped hand-edit backups (MEMORY-<ts>.md), and the pre-install
        # snapshot (MEMORY.preinstall.md). They are not source topic memories.
        if path.name == "MEMORY.md" or path.name.startswith(("MEMORY-", "MEMORY.")):
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.name)
