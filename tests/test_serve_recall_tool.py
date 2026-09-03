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
