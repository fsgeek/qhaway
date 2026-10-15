"""Re-grounding runs a count, so it connects with the read-only tier
(`reader_user` / `reader_password` in yanantin's db.ini), never the admin one.
Without reader credentials, or when the live check fails, the claim renders
frozen with its date instead of breaking recall."""
from qhaway import reground

CLAIM = {"kind": "collection_count", "db": "llm_memory", "collection": "episodes",
         "value": 1221, "as_of": "2026-06-19"}
ADMIN = "[database]\nhost = h\nport = 8529\nadmin_user = root\nadmin_passwd = secret\n"


def _setup(tmp_path, monkeypatch, ini_text, live=None):
    ini = tmp_path / "db.ini"
    ini.write_text(ini_text)
    monkeypatch.setattr(reground, "_DB_INI", ini)
    calls = []

    def fake_live_count(db_name, collection, user, password):
        calls.append((db_name, collection, user, password))
        if isinstance(live, Exception):
            raise live
        return live

    monkeypatch.setattr(reground, "_live_count", fake_live_count)
    return calls


def test_admin_only_config_never_connects_and_renders_frozen(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, ADMIN, live=5)
    out = reground._provider(CLAIM)
    assert calls == []
    assert out == "1221 (frozen; as of 2026-06-19 — no read-only credentials in db.ini)"


def test_reader_credentials_are_used_not_admin(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch,
                   ADMIN + "reader_user = qhaway_reader\nreader_password = ro\n", live=1300)
    out = reground._provider(CLAIM)
    assert calls == [("llm_memory", "episodes", "qhaway_reader", "ro")]
    assert out == "1300 (live; stored claim 1221, as of 2026-06-19)"


def test_failed_live_check_renders_frozen_instead_of_raising(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch,
           ADMIN + "reader_user = qhaway_reader\nreader_password = ro\n",
           live=ConnectionError("store unreachable"))
    out = reground._provider(CLAIM)
    assert out == "1221 (frozen; as of 2026-06-19 — live check failed: ConnectionError)"
