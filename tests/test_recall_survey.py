"""recall() states the slice's size before its content, and can be capped.

Issue #20: a caller should learn how big an answer is — and whether it already
holds everything — before paying for it. Every projection opens with one line:
the match count, and either "all shown" or the full size and how many are shown.
`limit` caps the entries; limit=0 is a count-only survey (header + footer).
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from qhaway import cli, project, server


def _write_memory(root: Path, stem: str, mtype: str = "project", description: str = "d") -> None:
    (root / f"{stem}.md").write_text(
        f"---\nname: {stem}\ntype: {mtype}\ndescription: {description}\n---\nbody\n",
        encoding="utf-8",
    )


def _bulk(root: Path, n: int) -> None:
    for i in range(n):
        _write_memory(root, f"bulk-{i:03d}", description="d" * 150)


def _entries(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("- [")]


def test_complete_slice_declares_all_shown_on_its_first_line(tmp_path):
    _write_memory(tmp_path, "alpha")
    _write_memory(tmp_path, "beta", mtype="feedback")
    server.initialize_server(str(tmp_path))

    text = server.recall(memory_dir=str(tmp_path))

    assert text.splitlines()[0] == "2 matching memories; all shown."


def test_overflowing_slice_states_full_size_and_shown_count_first(tmp_path):
    _bulk(tmp_path, 200)
    server.initialize_server(str(tmp_path))

    text = server.recall(memory_dir=str(tmp_path))

    m = re.fullmatch(r"200 matching memories, ([\d,]+) bytes in full; showing (\d+)\.", text.splitlines()[0])
    assert m, text.splitlines()[0]
    full_bytes = int(m.group(1).replace(",", ""))
    assert full_bytes > project.DEFAULT_BUDGET
    assert int(m.group(2)) == len(_entries(text)) < 200


def test_header_counts_against_the_budget(tmp_path):
    _bulk(tmp_path, 200)
    server.initialize_server(str(tmp_path))

    text = server.recall(memory_dir=str(tmp_path))

    assert len(text.encode("utf-8")) <= project.DEFAULT_BUDGET


def test_limit_caps_entries_and_declares_the_rest(tmp_path):
    _bulk(tmp_path, 20)
    server.initialize_server(str(tmp_path))

    text = server.recall(memory_dir=str(tmp_path), limit=3)

    assert len(_entries(text)) == 3
    assert text.splitlines()[0].endswith("; showing 3.")
    assert "+17 project memories not shown" in text


def test_limit_zero_is_a_count_only_survey(tmp_path):
    _bulk(tmp_path, 20)
    _write_memory(tmp_path, "a-rule", mtype="feedback")
    server.initialize_server(str(tmp_path))

    text = server.recall(memory_dir=str(tmp_path), limit=0)

    assert _entries(text) == []
    assert text.splitlines()[0].startswith("21 matching memories, ")
    assert "+1 feedback memories not shown" in text
    assert "+20 project memories not shown" in text


def test_empty_slice_says_so(tmp_path):
    _write_memory(tmp_path, "alpha")
    server.initialize_server(str(tmp_path))

    text = server.recall(type="reference", memory_dir=str(tmp_path))

    assert text.splitlines()[0] == "No matching memories."


def test_recall_tool_accepts_limit(tmp_path):
    _bulk(tmp_path, 5)
    server.initialize_server(str(tmp_path))

    mcp = server.build_server(str(tmp_path))
    result = asyncio.run(mcp.call_tool("recall", {"limit": 0}))

    assert _entries(result.content[0].text) == []


def test_written_index_declares_completeness(tmp_path):
    # The session-start index is where an instance decides whether to search at
    # all; the absence of an omissions footer is not a strong enough signal.
    _write_memory(tmp_path, "alpha")
    _write_memory(tmp_path, "beta")

    cli.write_index(str(tmp_path), project.DEFAULT_BUDGET, style="live")

    index = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert "2 matching memories; all shown." in index
