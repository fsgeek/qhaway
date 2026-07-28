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
