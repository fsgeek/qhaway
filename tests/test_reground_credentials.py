"""Re-grounding runs a count, so it uses yanantin's read-only account from its
own file (`reader.ini`) and never opens `db.ini`, which holds the admin
password. Without reader credentials, or when the live check fails, the claim
renders frozen with its date instead of breaking recall."""
import sys
import types

from qhaway import reground

CLAIM = {"kind": "collection_count", "db": "llm_memory", "collection": "episodes",
         "value": 1221, "as_of": "2026-06-19"}
ADMIN = "[database]\nhost = h\nport = 8529\nadmin_user = root\nadmin_passwd = secret\n"
READER = ("[database]\nhost = h\nport = 8529\nssl = false\nuser = yanantin_reader\n"
          "password = ro\ndatabases = llm_memory\n")


def _setup(tmp_path, monkeypatch, reader_text=None, live=None):
    (tmp_path / "db.ini").write_text(ADMIN)
    reader = tmp_path / "reader.ini"
    if reader_text is not None:
        reader.write_text(reader_text)
    monkeypatch.setattr(reground, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(reground, "_READER_INI", reader)
    calls = []

    def fake_live_count(db_name, collection, creds):
        calls.append((db_name, collection, creds["user"], creds["password"]))
        if isinstance(live, Exception):
            raise live
        return live

    monkeypatch.setattr(reground, "_live_count", fake_live_count)
    return calls


def test_without_reader_ini_never_connects_even_beside_admin_db_ini(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, reader_text=None, live=5)
    out = reground._provider(CLAIM)
    assert calls == []
    assert out == "1221 (frozen; as of 2026-06-19 — no read-only credentials in reader.ini)"


def test_reader_ini_missing_a_key_renders_frozen(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch,
                   reader_text=READER.replace("password = ro\n", ""), live=5)
    assert reground._provider(CLAIM).endswith("no read-only credentials in reader.ini)")
    assert calls == []


def test_reader_credentials_are_used(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, reader_text=READER, live=1300)
    out = reground._provider(CLAIM)
    assert calls == [("llm_memory", "episodes", "yanantin_reader", "ro")]
    assert out == "1300 (live; stored claim 1221, as of 2026-06-19)"


def test_failed_live_check_renders_frozen_instead_of_raising(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, reader_text=READER,
           live=ConnectionError("store unreachable"))
    out = reground._provider(CLAIM)
    assert out == "1221 (frozen; as of 2026-06-19 — live check failed: ConnectionError)"


def test_provider_is_on_only_where_yanantin_config_exists(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "arango", types.ModuleType("arango"))
    monkeypatch.setattr(reground, "_CONFIG_DIR", tmp_path / "absent")
    assert reground.default_provider() is None
    monkeypatch.setattr(reground, "_CONFIG_DIR", tmp_path)
    assert reground.default_provider() is reground._provider
