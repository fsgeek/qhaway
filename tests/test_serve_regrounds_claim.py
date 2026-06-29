"""Deployed MCP recall re-grounds stale claims against the live store."""

from __future__ import annotations

import asyncio
import configparser
from pathlib import Path
from uuid import uuid4

import pytest

from qhaway import reground, server


def _admin_db(db_name: str):
    ini = Path.home() / ".yanantin" / "config" / "db.ini"
    if not ini.exists():
        pytest.skip("no ~/.yanantin/config/db.ini - live store unavailable")

    from arango import ArangoClient

    cfg = configparser.ConfigParser()
    cfg.read(ini)
    db = cfg["database"]
    scheme = "https" if db.get("ssl", "false") == "true" else "http"
    host = f"{scheme}://{db['host']}:{db['port']}"
    client = ArangoClient(hosts=host)
    return client.db(db_name, username=db["admin_user"], password=db["admin_passwd"])


def _write_memory(root: Path, stem: str, frontmatter: str, body: str) -> Path:
    path = root / f"{stem}.md"
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


def _claim_fm(name: str, collection: str, value: int) -> str:
    return (
        f"name: {name}\n"
        "type: project\n"
        "claim:\n"
        "  kind: collection_count\n"
        "  db: apacheta_test\n"
        f"  collection: {collection}\n"
        f"  value: {value}\n"
        "  as_of: 2026-06-28\n"
    )


def _deployed_recall(memory_dir: Path, **args) -> str:
    mcp = server.build_server(str(memory_dir))
    return asyncio.run(mcp._tool_manager.call_tool("recall", args))


def test_deployed_recall_regrounds_claim_against_live_store(tmp_path, monkeypatch):
    collection_name = f"test_serve_rg_{uuid4().hex}"
    db = _admin_db("apacheta_test")
    try:
        coll = db.create_collection(collection_name)
        for i in range(3):
            coll.insert({"_key": f"d{i}"})

        _write_memory(
            tmp_path,
            "stale-serve-claim",
            _claim_fm("stale-serve-claim", collection_name, 1),
            "A deployed memory whose count drifts.\n",
        )

        seen = []

        def deployed_reground(claim: dict) -> str:
            seen.append(claim)
            live = _admin_db(claim["db"]).collection(claim["collection"]).count()
            return f"{live} (live; stored claim {claim['value']}, as of {claim['as_of']})"

        monkeypatch.setattr(reground, "default_provider", lambda: deployed_reground)

        out = _deployed_recall(tmp_path, type="project")

        assert seen == [
            {
                "kind": "collection_count",
                "db": "apacheta_test",
                "collection": collection_name,
                "value": 1,
                "as_of": "2026-06-28",
            }
        ]
        assert out.count("## Re-grounded claims") == 1
        assert (
            "- [stale-serve-claim](stale-serve-claim.md): "
            "3 (live; stored claim 1, as of 2026-06-28)"
        ) in out
    finally:
        if db.has_collection(collection_name):
            db.delete_collection(collection_name)


def test_deployed_recall_claimless_memory_has_no_regrounded_section(tmp_path, monkeypatch):
    _write_memory(
        tmp_path,
        "plain-serve-memory",
        "name: plain-serve-memory\ntype: project\n",
        "No claim.\n",
    )

    def deployed_reground(claim: dict) -> str:  # pragma: no cover - must never be called
        raise AssertionError(f"reground called for claimless memory: {claim!r}")

    monkeypatch.setattr(reground, "default_provider", lambda: deployed_reground)

    out = _deployed_recall(tmp_path, type="project")

    assert "## Re-grounded claims" not in out
