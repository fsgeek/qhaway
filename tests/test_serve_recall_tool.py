"""The recall verb is reachable through the built server's tool interface.

Guards the MCP binding seam in build_server. Unlike the re-grounding tests this
needs no live store: reground.default_provider() returns None on a base install,
so recall projects byte-identically and this runs everywhere, CI included.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from qhaway import server


def _write_memory(root: Path, stem: str, frontmatter: str, body: str) -> Path:
    path = root / f"{stem}.md"
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


def test_recall_tool_returns_the_projection(tmp_path):
    _write_memory(
        tmp_path,
        "reachable-memory",
        "name: reachable-memory\ntype: project\ndescription: proves the tool path is wired\n",
        "The binding seam is reachable.\n",
    )
    server.initialize_server(str(tmp_path))

    mcp = server.build_server(str(tmp_path))
    result = asyncio.run(mcp.call_tool("recall", {}))
    text = result.content[0].text

    assert "reachable-memory" in text
    assert "proves the tool path is wired" in text


def test_recall_overflow_hint_names_recall_not_the_cli(tmp_path):
    # The reader of recall()'s output is a model holding the recall tool, on
    # any host; a shell command (without even the --dir it would need) is not
    # an instruction it can follow. The declared omission must point at the verb.
    for i in range(200):
        _write_memory(
            tmp_path,
            f"bulk-{i:03d}",
            f"name: bulk-{i:03d}\ntype: project\ndescription: {'d' * 150}\n",
            "body\n",
        )
    server.initialize_server(str(tmp_path))

    text = server.recall(memory_dir=str(tmp_path))

    assert "project memories not shown" in text
    assert 'recall(type="project")' in text
    assert "qhaway index" not in text


def test_recall_superseded_hint_names_recall(tmp_path):
    _write_memory(
        tmp_path,
        "old-handoff",
        "name: SUPERSEDED — see new-handoff.md\ntype: project\n",
        "old\n",
    )
    _write_memory(tmp_path, "new-handoff", "name: new-handoff\ntype: project\n", "new\n")
    server.initialize_server(str(tmp_path))

    text = server.recall(memory_dir=str(tmp_path))

    assert "superseded memories hidden" in text
    assert 'recall(status="superseded")' in text
    assert "qhaway index" not in text


def test_recall_logs_its_query_limit_and_omissions(tmp_path):
    import json
    from qhaway import server
    for i in range(3):
        (tmp_path / f"t{i}.md").write_text(f"---\nname: arango {i}\nmetadata:\n  type: project\n---\nb\n")
    server.recall(query="arango", limit=1, memory_dir=str(tmp_path))
    [event] = [json.loads(l) for l in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert (event["query"], event["limit"]) == ("arango", 1)
    assert event["omitted"] == {"project": 2}


def test_recall_events_share_a_per_process_session_and_record_the_header(tmp_path, monkeypatch):
    # Without a session identity, repeated questions within one session can't be
    # seen; without the header, neither can zero-result recalls.
    import json
    from qhaway import server
    monkeypatch.delenv("QHAWAY_SESSION_ID", raising=False)
    (tmp_path / "a.md").write_text("---\nname: arango\ntype: project\n---\nb\n")
    server.recall(query="arango", memory_dir=str(tmp_path))
    server.recall(query="nothing-matches", memory_dir=str(tmp_path))
    first, second = [json.loads(l) for l in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert first["session_id"] and first["session_id"] == second["session_id"]
    assert first["header"] == "1 matching memory; all shown."
    assert second["header"] == "No matching memories."


def test_remember_stamps_the_date_it_was_written(tmp_path):
    # Recency is the cheapest filter, but a memory without a date in its title
    # had no date at all and sorted after every dated one (73% of one machine's
    # memories).
    import datetime, re
    from qhaway import parse, server
    name = server.remember(type="project", title="no date in this title", body="b",
                           memory_dir=str(tmp_path))
    text = (tmp_path / name).read_text()
    assert re.search(r"^date: '?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z'?$", text, re.M)  # UTC, explicit zone
    hint = parse.parse_memory_file(str(tmp_path / name))["date_hint"]
    assert hint.startswith(datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d"))
