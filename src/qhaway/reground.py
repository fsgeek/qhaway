"""Default re-ground provider for the deployed server (Approach B).

The injected-callable contract (server.recall's `reground=`) is satisfied at test
time by a closure that reaches the live store directly. The DEPLOYED server —
`uvx qhaway serve`, an env that cannot import yanantin — has no such closure, so
a claim renders frozen-only. This module is that closure promoted to a shipped
provider: it reads yanantin's read-only account from ~/.yanantin/config/reader.ini
and counts a collection via python-arango (the optional `[reground]` extra),
returning the live rendered string. It never opens db.ini, which holds the
admin password. qhaway never imports yanantin; the dependency inversion holds.

`default_provider()` returns None when the extra is absent or there is no
~/.yanantin/config, so a base install (or a box with no store) recalls exactly
as before — additive.
The wording matches yanantin's Regrounding.render() so the deployed output is
indistinguishable from the in-process path.
"""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Callable

_CONFIG_DIR = Path.home() / ".yanantin" / "config"
_READER_INI = _CONFIG_DIR / "reader.ini"
_READER_KEYS = ("host", "port", "user", "password")


def _render(stored: int, live: int, as_of: str) -> str:
    """Match yanantin Regrounding.render() exactly — one wording, two paths."""
    if stored != live:
        return f"{live} (live; stored claim {stored}, as of {as_of})"
    return f"{live} (live; matches stored claim, as of {as_of})"


def _live_count(db_name: str, collection: str, creds) -> int:
    """Count one collection with the read-only account.

    python-arango is the `[reground]` extra; importing it here (not at module
    load) keeps a base install importable.
    """
    from arango import ArangoClient

    scheme = "https" if creds.get("ssl", "false") == "true" else "http"
    client = ArangoClient(hosts=f"{scheme}://{creds['host']}:{creds['port']}")
    handle = client.db(db_name, username=creds["user"], password=creds["password"])
    return handle.collection(collection).count()


def _reader_credentials():
    """yanantin's read-only account from reader.ini, or None if the file or a
    key is missing. A count needs no more than read access."""
    cfg = configparser.ConfigParser()
    cfg.read(_READER_INI)
    if not cfg.has_section("database"):
        return None
    creds = dict(cfg["database"])
    return creds if all(creds.get(k) for k in _READER_KEYS) else None


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
        return frozen + "no read-only credentials in reader.ini)"
    try:
        live = _live_count(claim["db"], claim["collection"], creds)
    except Exception as exc:  # an unreachable store must not break recall
        return frozen + f"live check failed: {type(exc).__name__})"
    return _render(stored, live, claim["as_of"])


def default_provider() -> Callable[[dict], str] | None:
    """The reground callable to inject at serve time, or None to stay frozen.

    None when the `[reground]` extra is not installed (python-arango absent) or
    there is no yanantin config directory — a base/storeless install then
    recalls byte-identically.
    """
    try:
        import arango  # noqa: F401 — presence probe for the optional extra
    except ImportError:
        return None
    if not _CONFIG_DIR.is_dir():
        return None
    return _provider
