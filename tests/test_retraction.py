"""A retraction keeps the dead claim visible and marked, instead of hiding it (#27).

`supersedes` hides a revised memory. A retraction is different: the claim was
wrong, and later readers need to see that it was believed and that it died. The
retracted memory's line stays in the projection with a marker pointing at the
retraction; a quoted `retracted_claim` found in its description is struck.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from qhaway import model, project, reconcile, server


def _write(root: Path, stem: str, description: str, extra: str = "", body: str = "body\n") -> None:
    (root / f"{stem}.md").write_text(
        f"---\nname: {stem}\ntype: project\ndescription: {description}\n{extra}---\n{body}",
        encoding="utf-8",
    )


def _line(text: str, stem: str) -> str:
    return next(line for line in text.splitlines() if line.startswith(f"- [{stem}]("))


def test_retracted_memory_stays_visible_with_a_marker(tmp_path):
    _write(tmp_path, "users-claim", "the community uses qhaway extensively")
    _write(tmp_path, "no-outside-users", "the community meant Tony's instances", extra="retracts: [[users-claim]]\n")
    server.initialize_server(str(tmp_path))

    text = server.recall(memory_dir=str(tmp_path))

    line = _line(text, "users-claim")
    assert line.endswith(" [retracted: no-outside-users](no-outside-users.md)")
    assert text.splitlines()[0] == "2 matching memories; all shown."


def test_quoted_claim_is_struck_in_the_description(tmp_path):
    _write(tmp_path, "users-claim", "Tony reports the community uses qhaway extensively")
    _write(
        tmp_path, "no-outside-users", "no outside users",
        extra="retracts: users-claim\nretracted_claim: the community uses qhaway extensively\n",
    )
    server.initialize_server(str(tmp_path))

    line = _line(server.recall(memory_dir=str(tmp_path)), "users-claim")

    assert "Tony reports ~~the community uses qhaway extensively~~" in line


def test_claim_not_in_description_leaves_only_the_marker(tmp_path):
    _write(tmp_path, "users-claim", "adoption reads positive")
    _write(
        tmp_path, "no-outside-users", "no outside users",
        extra="retracts: users-claim\nretracted_claim: something only the body said\n",
    )
    server.initialize_server(str(tmp_path))

    line = _line(server.recall(memory_dir=str(tmp_path)), "users-claim")

    assert "~~" not in line
    assert "[retracted: no-outside-users](no-outside-users.md)" in line


def test_remember_records_a_retraction(tmp_path):
    _write(tmp_path, "users-claim", "the community uses qhaway extensively")
    server.initialize_server(str(tmp_path))

    server.remember(
        "project", "no outside users", "evidence here\n",
        description="community meant instances",
        retracts="users-claim", retracted_claim="uses qhaway extensively",
        memory_dir=str(tmp_path),
    )

    line = _line(server.recall(memory_dir=str(tmp_path)), "users-claim")
    assert "~~uses qhaway extensively~~" in line
    assert "[retracted: no outside users](no-outside-users.md)" in line


def test_recall_tool_remember_accepts_retracts(tmp_path):
    _write(tmp_path, "users-claim", "the community uses qhaway extensively")
    server.initialize_server(str(tmp_path))

    mcp = server.build_server(str(tmp_path))
    asyncio.run(mcp.call_tool("remember", {
        "type": "project", "title": "no outside users", "body": "evidence\n",
        "retracts": "users-claim",
    }))

    assert "[retracted: no outside users]" in server.recall(memory_dir=str(tmp_path))


def test_a_marker_link_does_not_count_its_target_as_shown(tmp_path):
    # Overflow accounting finds shown memories by their links; a marker links
    # to the retraction, which must still count as omitted when its own line is.
    _write(tmp_path, "users-claim", "the community uses qhaway extensively")
    _write(tmp_path, "no-outside-users", "x" * 100, extra="retracts: users-claim\n")
    reconcile.reconcile(str(tmp_path))
    conn = model.get_connection(str(tmp_path))
    try:
        result = project.project_slice_with_overflow(conn, budget=10**6, limit=1)
    finally:
        conn.close()

    shown = [l for l in result.markdown.splitlines() if l.startswith("- [")]
    assert len(shown) == 1
    assert sum(result.overflow.omitted_counts.values()) == 1
