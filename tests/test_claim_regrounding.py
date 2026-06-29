"""Red-bar tests for claim re-grounding at recall.

A memory may carry a structured `claim:` block. Today qhaway drops it at the
index. The feature: parse the claim, store it, and re-ground it at recall via an
injected callable — so a stale frozen value self-corrects to the live one in the
recall output, with both visible.

Builder-authored (the Codex thread stalled mid-write); to be handed to Codex for
adversarial review after green. Live DB, no mocks (project rule). Connects by
reading ~/.yanantin/config/db.ini directly — NO yanantin import, which would
invert the dependency the design forbids.
"""

from __future__ import annotations

import configparser
from pathlib import Path
from uuid import uuid4

import pytest

from qhaway import model, parse, server


# ── live DB access without importing yanantin ─────────────────────────────

def _admin_db(db_name: str):
    ini = Path.home() / ".yanantin" / "config" / "db.ini"
    if not ini.exists():
        pytest.skip("no ~/.yanantin/config/db.ini — live store unavailable")
    cfg = configparser.ConfigParser()
    cfg.read(ini)
    db = cfg["database"]
    scheme = "https" if db.get("ssl", "false") == "true" else "http"
    host = f"{scheme}://{db['host']}:{db['port']}"
    from arango import ArangoClient

    client = ArangoClient(hosts=host)
    return client.db(db_name, username=db["admin_user"], password=db["admin_passwd"])


def _write_memory(root: Path, stem: str, frontmatter: str, body: str) -> Path:
    path = root / f"{stem}.md"
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


CLAIM_FM = (
    "name: stale-episode-claim\n"
    "type: project\n"
    "claim:\n"
    "  kind: collection_count\n"
    "  db: apacheta_test\n"
    "  collection: {collection}\n"
    "  value: 1\n"
    "  as_of: 2026-06-28\n"
)


# ── Test A: parse surfaces the claim ──────────────────────────────────────

def test_parse_surfaces_claim(tmp_path):
    path = _write_memory(
        tmp_path, "stale-episode-claim",
        CLAIM_FM.format(collection="dummy"),
        "A memory whose count drifts.\n",
    )
    node = parse.parse_memory_file(str(path))
    assert node["claim"] == {
        "kind": "collection_count",
        "db": "apacheta_test",
        "collection": "dummy",
        "value": 1,
        "as_of": "2026-06-28",
    }


# ── Test B: index round-trips the claim ───────────────────────────────────

def test_index_round_trips_claim(tmp_path):
    _write_memory(
        tmp_path, "stale-episode-claim",
        CLAIM_FM.format(collection="dummy"),
        "A memory whose count drifts.\n",
    )
    conn = model.get_connection(str(tmp_path))
    try:
        nodes = {n["file"]: n for n in model.fetch_nodes(conn)}
    finally:
        conn.close()
    node = nodes["stale-episode-claim.md"]
    assert node["claim"] == {
        "kind": "collection_count",
        "db": "apacheta_test",
        "collection": "dummy",
        "value": 1,
        "as_of": "2026-06-28",
    }


# ── Test C: recall re-grounds via injected callable (the heart) ───────────

def test_recall_regrounds_claim_against_live_store(tmp_path):
    collection_name = f"test_claim_rg_{uuid4().hex}"
    db = _admin_db("apacheta_test")
    coll = db.create_collection(collection_name)
    try:
        for i in range(3):
            coll.insert({"_key": f"d{i}"})

        _write_memory(
            tmp_path, "stale-episode-claim",
            CLAIM_FM.format(collection=collection_name),
            "A memory whose count drifts.\n",
        )

        def reground(claim: dict) -> str:
            live = _admin_db(claim["db"]).collection(claim["collection"]).count()
            return (
                f"{live} (live; stored claim {claim['value']}, "
                f"as of {claim['as_of']})"
            )

        out = server.recall(memory_dir=str(tmp_path), reground=reground)

        assert "3" in out          # live value present
        assert "1" in out          # frozen value preserved (before/after both)
        assert "live" in out
    finally:
        if db.has_collection(collection_name):
            db.delete_collection(collection_name)


# ── Test D: additivity — claimless memory unchanged by injection ──────────

def test_claimless_memory_identical_with_or_without_reground(tmp_path):
    _write_memory(
        tmp_path, "plain-memory",
        "name: plain-memory\ntype: project\n",
        "No claim here.\n",
    )

    def reground(claim: dict) -> str:  # pragma: no cover - must never be called
        raise AssertionError("reground called for a claimless memory")

    without = server.recall(memory_dir=str(tmp_path))
    with_inj = server.recall(memory_dir=str(tmp_path), reground=reground)
    assert without == with_inj
