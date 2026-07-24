"""Tests for claim re-grounding at recall.

A memory may carry a structured `claim:` block. Today qhaway drops it at the
index. The feature: parse the claim, store it, and re-ground it at recall via an
injected callable — so a stale frozen value self-corrects to the live one in the
recall output, with both visible.

Builder-authored, then hardened against Codex's adversarial review (the three
High gaps it found: schema-drift claim preservation, the v2-but-missing-claim
drift blind spot, and filtered-recall scope). Live DB, no mocks; connects by
reading ~/.yanantin/config/db.ini directly — NO yanantin import, which would
invert the dependency the design forbids.
"""

from __future__ import annotations

import configparser
import datetime
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from qhaway import model, parse, server


# ── live DB access without importing yanantin ─────────────────────────────

def _admin_db(db_name: str):
    ini = Path.home() / ".yanantin" / "config" / "db.ini"
    if not ini.exists():
        pytest.skip("no ~/.yanantin/config/db.ini — live store unavailable")
    # `python-arango` is the optional `reground` extra, not a base dependency —
    # skip the live-store tests cleanly on a base install rather than erroring.
    ArangoClient = pytest.importorskip("arango").ArangoClient
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


def _expected_claim(collection: str, value: int) -> dict:
    return {
        "kind": "collection_count",
        "db": "apacheta_test",
        "collection": collection,
        "value": value,
        "as_of": "2026-06-28",
    }


# ── Test A: parse surfaces the claim ──────────────────────────────────────

def test_parse_surfaces_claim(tmp_path):
    path = _write_memory(
        tmp_path, "stale-episode-claim", _claim_fm("stale-episode-claim", "dummy", 1),
        "A memory whose count drifts.\n",
    )
    node = parse.parse_memory_file(str(path))
    assert node["claim"] == _expected_claim("dummy", 1)


def test_parse_ignores_prose_claim(tmp_path):
    """A non-mapping claim is not machine-checkable, so it is not a claim."""
    path = _write_memory(
        tmp_path, "prose-claim",
        "name: prose-claim\ntype: project\nclaim: just some prose, not a mapping\n",
        "Body.\n",
    )
    assert parse.parse_memory_file(str(path))["claim"] is None


def test_json_safe_stringifies_dates():
    """YAML coerces bare dates; _json_safe must normalize to ISO strings."""
    assert parse._json_safe(datetime.date(2026, 6, 28)) == "2026-06-28"
    assert parse._json_safe(datetime.datetime(2026, 6, 28, 9, 0)).startswith("2026-06-28")
    assert parse._json_safe("already a string") == "already a string"
    assert parse._json_safe(1221) == 1221


# ── Test B: index round-trips the claim ───────────────────────────────────

def test_index_round_trips_claim(tmp_path):
    _write_memory(
        tmp_path, "stale-episode-claim", _claim_fm("stale-episode-claim", "dummy", 1),
        "A memory whose count drifts.\n",
    )
    conn = model.get_connection(str(tmp_path))
    try:
        nodes = {n["file"]: n for n in model.fetch_nodes(conn)}
    finally:
        conn.close()
    assert nodes["stale-episode-claim.md"]["claim"] == _expected_claim("dummy", 1)


def test_claimless_node_stores_none(tmp_path):
    _write_memory(tmp_path, "plain", "name: plain\ntype: project\n", "No claim.\n")
    conn = model.get_connection(str(tmp_path))
    try:
        node = {n["file"]: n for n in model.fetch_nodes(conn)}["plain.md"]
    finally:
        conn.close()
    assert node["claim"] is None


# ── Schema drift: claims survive a SCHEMA_VERSION bump (Codex High #2) ─────

def test_drift_rebuild_preserves_claim(tmp_path):
    """A pre-bump db (no claim column) must rebuild from disk WITH the claim."""
    db_file = model.db_path(tmp_path)
    old = sqlite3.connect(str(db_file))
    old.execute(
        "CREATE TABLE nodes (file TEXT PRIMARY KEY, name TEXT, content_type TEXT, "
        "description TEXT, role TEXT, status TEXT, origin_session TEXT, "
        "date_hint TEXT, body TEXT, mtime_ns INTEGER, size INTEGER)"
    )
    old.execute("PRAGMA user_version = 1")  # the pre-claim schema version
    old.commit()
    old.close()

    _write_memory(
        tmp_path, "stale-episode-claim", _claim_fm("stale-episode-claim", "dummy", 7),
        "Drifts.\n",
    )
    conn = model.get_connection(str(tmp_path))  # detects drift, rebuilds from disk
    try:
        node = {n["file"]: n for n in model.fetch_nodes(conn)}["stale-episode-claim.md"]
    finally:
        conn.close()
    assert node["claim"] == _expected_claim("dummy", 7)


def test_drift_caught_when_version_current_but_claim_missing(tmp_path):
    """v2-stamped db missing the claim column is still drift (Codex High #3)."""
    db_file = model.db_path(tmp_path)
    bad = sqlite3.connect(str(db_file))
    bad.execute(
        "CREATE TABLE nodes (file TEXT PRIMARY KEY, name TEXT, content_type TEXT, "
        "description TEXT, role TEXT, status TEXT, origin_session TEXT, "
        "date_hint TEXT, body TEXT, mtime_ns INTEGER, size INTEGER)"  # no claim
    )
    bad.execute(f"PRAGMA user_version = {model.SCHEMA_VERSION}")  # claims to be current
    bad.commit()
    bad.close()

    _write_memory(tmp_path, "m", _claim_fm("m", "dummy", 1), "Body.\n")
    conn = model.get_connection(str(tmp_path))
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(nodes)")}
        assert "claim" in cols  # rebuilt despite the lying version stamp
    finally:
        conn.close()


# ── Test C: recall re-grounds via injected callable (the heart) ───────────

def test_recall_regrounds_claim_against_live_store(tmp_path):
    collection_name = f"test_claim_rg_{uuid4().hex}"
    db = _admin_db("apacheta_test")
    try:
        coll = db.create_collection(collection_name)
        for i in range(3):
            coll.insert({"_key": f"d{i}"})

        _write_memory(
            tmp_path, "stale-episode-claim",
            _claim_fm("stale-episode-claim", collection_name, 1),
            "A memory whose count drifts.\n",
        )

        seen = []

        def reground(claim: dict) -> str:
            seen.append(claim)
            live = _admin_db(claim["db"]).collection(claim["collection"]).count()
            return f"{live} (live; stored claim {claim['value']}, as of {claim['as_of']})"

        out = server.recall(memory_dir=str(tmp_path), reground=reground)

        # exact claim passed, exactly once
        assert seen == [_expected_claim(collection_name, 1)]
        # exact rendered line in the re-grounded section (strong assertion)
        assert out.count("## Re-grounded claims") == 1
        assert (
            "- [stale-episode-claim](stale-episode-claim.md): "
            "3 (live; stored claim 1, as of 2026-06-28)"
        ) in out
    finally:
        if db.has_collection(collection_name):
            db.delete_collection(collection_name)


def test_recall_regrounds_fresh_claim_too(tmp_path):
    """A non-stale claim (stored == live) is still re-grounded and shown."""
    collection_name = f"test_claim_fresh_{uuid4().hex}"
    db = _admin_db("apacheta_test")
    try:
        coll = db.create_collection(collection_name)
        for i in range(2):
            coll.insert({"_key": f"d{i}"})

        _write_memory(
            tmp_path, "fresh-claim", _claim_fm("fresh-claim", collection_name, 2),
            "Matches live.\n",
        )

        def reground(claim: dict) -> str:
            live = _admin_db(claim["db"]).collection(claim["collection"]).count()
            return f"{live} (live; stored claim {claim['value']})"

        out = server.recall(memory_dir=str(tmp_path), reground=reground)
        assert "## Re-grounded claims" in out
        assert "2 (live; stored claim 2)" in out
    finally:
        if db.has_collection(collection_name):
            db.delete_collection(collection_name)


def test_recall_regrounds_multiple_memories(tmp_path):
    """One re-grounded line per claim-bearing memory."""
    _write_memory(tmp_path, "claim-a", _claim_fm("claim-a", "ca", 1), "A.\n")
    _write_memory(tmp_path, "claim-b", _claim_fm("claim-b", "cb", 1), "B.\n")

    def reground(claim: dict) -> str:
        return f"SENTINEL[{claim['collection']}]"

    out = server.recall(memory_dir=str(tmp_path), reground=reground)
    assert "SENTINEL[ca]" in out
    assert "SENTINEL[cb]" in out
    assert out.count("## Re-grounded claims") == 1


def test_recall_respects_type_filter_for_claims(tmp_path):
    """Re-grounding must respect the recall filter, not leak claims from outside
    the projected slice (Codex High #1 — filtered-recall scope)."""
    _write_memory(tmp_path, "proj-claim", _claim_fm("proj-claim", "pc", 1), "P.\n")
    _write_memory(tmp_path, "user-plain", "name: user-plain\ntype: user\n", "U.\n")

    calls = []

    def reground(claim: dict) -> str:
        calls.append(claim)
        return "X"

    out = server.recall(type="user", memory_dir=str(tmp_path), reground=reground)
    assert calls == []                       # project claim not re-grounded
    assert "## Re-grounded claims" not in out


def test_recall_claim_with_nested_type_defaults_to_project(tmp_path):
    """A memory whose `type` lives in nested metadata: parses content_type=None;
    the projection defaults it to 'project', so claim re-grounding must too —
    recall(type='project') must include it (the real federation-memory shape)."""
    _write_memory(
        tmp_path, "nested-type-claim",
        "name: nested-type-claim\nmetadata:\n  type: project\n"
        "claim:\n  kind: collection_count\n  db: apacheta_test\n"
        "  collection: nc\n  value: 1\n  as_of: 2026-06-28\n",
        "Nested type.\n",
    )

    def reground(claim: dict) -> str:
        return "HIT"

    out = server.recall(type="project", memory_dir=str(tmp_path), reground=reground)
    assert "HIT" in out


# ── Additivity: claimless corpus identical AND no claim section ────────────

def test_claimless_memory_identical_with_or_without_reground(tmp_path):
    _write_memory(tmp_path, "plain-memory", "name: plain-memory\ntype: project\n", "No claim.\n")

    def reground(claim: dict) -> str:  # pragma: no cover - must never be called
        raise AssertionError("reground called for a claimless memory")

    without = server.recall(memory_dir=str(tmp_path))
    with_inj = server.recall(memory_dir=str(tmp_path), reground=reground)
    assert without == with_inj
    assert "## Re-grounded claims" not in without
    assert "## Re-grounded claims" not in with_inj
