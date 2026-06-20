"""Build the embedded qhaway DuckDB index from topic files."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

from qhaway.parse import parse_memory_file


def build_index(memory_dir: str, db_path: str = ":memory:") -> duckdb.DuckDBPyConnection:
    """Scan a memory directory and return a DuckDB index connection."""

    root = Path(memory_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"memory directory is not readable: {memory_dir}")

    conn = duckdb.connect(db_path)
    conn.execute("DROP TABLE IF EXISTS edges")
    conn.execute("DROP TABLE IF EXISTS nodes")
    conn.execute(
        """
        CREATE TABLE nodes (
            file VARCHAR PRIMARY KEY,
            name VARCHAR,
            content_type VARCHAR,
            description VARCHAR,
            role VARCHAR,
            status VARCHAR,
            origin_session VARCHAR,
            date_hint VARCHAR,
            body VARCHAR,
            mtime DOUBLE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE edges (
            src_file VARCHAR,
            dst_slug VARCHAR,
            kind VARCHAR
        )
        """
    )

    for path in topic_files(root):
        node = parse_memory_file(str(path))
        if node.get("parse_warning"):
            sys.stderr.write(f"warning: {path.name}: {node['parse_warning']}\n")
        conn.execute(
            """
            INSERT INTO nodes
            (file, name, content_type, description, role, status, origin_session, date_hint, body, mtime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                node["file"],
                node["name"],
                node["content_type"],
                node.get("description"),
                node["role"],
                node["status"],
                node["origin_session"],
                node["date_hint"],
                node["body"],
                path.stat().st_mtime,
            ],
        )
        for dst_slug in node["links"]:
            conn.execute(
                "INSERT INTO edges (src_file, dst_slug, kind) VALUES (?, ?, 'REFERENCES')",
                [node["file"], dst_slug],
            )

    return conn


def topic_files(memory_dir: str | Path) -> list[Path]:
    """Return source topic Markdown files, excluding derived indexes and backups."""

    root = Path(memory_dir)
    files: list[Path] = []
    for path in root.glob("*.md"):
        if path.name == "MEMORY.md":
            continue
        if path.name.startswith("MEMORY-"):
            continue
        files.append(path)
    return sorted(files, key=lambda path: path.name)
