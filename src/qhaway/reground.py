"""Default re-ground provider for the deployed server (Approach B).

The injected-callable contract (server.recall's `reground=`) is satisfied at test
time by a closure that reaches the live store directly. The DEPLOYED server —
`uvx qhaway serve`, an env that cannot import yanantin — has no such closure, so
a claim renders frozen-only. This module is that closure promoted to a shipped
provider: it reads ~/.yanantin/config/db.ini and counts a collection via
python-arango (the optional `[reground]` extra), returning the live rendered
string. qhaway never imports yanantin; the dependency inversion holds.

`default_provider()` returns None when the extra is absent or db.ini is missing,
so a base install (or a box with no store) recalls exactly as before — additive.
The wording matches yanantin's Regrounding.render() so the deployed output is
indistinguishable from the in-process path.
"""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Callable

_DB_INI = Path.home() / ".yanantin" / "config" / "db.ini"


def _render(stored: int, live: int, as_of: str) -> str:
    """Match yanantin Regrounding.render() exactly — one wording, two paths."""
    if stored != live:
        return f"{live} (live; stored claim {stored}, as of {as_of})"
    return f"{live} (live; matches stored claim, as of {as_of})"


def _live_count(db_name: str, collection: str, user: str, password: str):
    """Count one collection with the given (read-only) credentials.

    python-arango is the `[reground]` extra; importing it here (not at module
    load) keeps a base install importable.
    """
    from arango import ArangoClient

    cfg = configparser.ConfigParser()
    cfg.read(_DB_INI)
    db = cfg["database"]
    scheme = "https" if db.get("ssl", "false") == "true" else "http"
    host = f"{scheme}://{db['host']}:{db['port']}"
    client = ArangoClient(hosts=host)
    handle = client.db(db_name, username=user, password=password)
    return handle.collection(collection).count()


def _reader_credentials():
    """yanantin's read-only tier from db.ini, or None. Never the admin tier:
    a count needs no more than read access."""
    cfg = configparser.ConfigParser()
    cfg.read(_DB_INI)
    db = cfg["database"] if cfg.has_section("database") else {}
    user, password = db.get("reader_user"), db.get("reader_password")
    return (user, password) if user and password else None


def _provider(claim: dict) -> str:
    """The injected callable: claim dict -> live rendered string.

    Only `collection_count` is grounded today (the one claim kind yanantin's
    reground supports); any other kind renders frozen-with-as_of, honest about
    not being live rather than guessing.
    """
    if claim.get("kind") != "collection_count":
        value = claim.get("value")
        as_of = claim.get("as_of")
        return f"{value} (frozen; as of {as_of} — kind {claim.get('kind')!r} not live-checkable)"
    stored = int(claim["value"])
    frozen = f"{claim['value']} (frozen; as of {claim['as_of']} — "
    creds = _reader_credentials()
    if creds is None:
        return frozen + "no read-only credentials in db.ini)"
    try:
        live = _live_count(claim["db"], claim["collection"], *creds)
    except Exception as exc:  # an unreachable store must not break recall
        return frozen + f"live check failed: {type(exc).__name__})"
    return _render(stored, live, claim["as_of"])


def default_provider() -> Callable[[dict], str] | None:
    """The reground callable to inject at serve time, or None to stay frozen.

    None when the `[reground]` extra is not installed (python-arango absent) or
    no db.ini exists — a base/storeless install then recalls byte-identically.
    """
    try:
        import arango  # noqa: F401 — presence probe for the optional extra
    except ImportError:
        return None
    if not _DB_INI.exists():
        return None
    return _provider
