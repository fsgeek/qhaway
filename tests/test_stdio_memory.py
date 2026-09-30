"""Local MCP clients can use curated memory without Claude hooks or cwd discovery."""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_curated_memory_round_trip(tmp_path):
    # Regression targets: losing explicit --dir precedence, dropping MCP
    # bindings, loading bodies into the survey, or losing supersession on restart.
    root = tmp_path / "curated"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "qhaway.cli", "serve", "--dir", str(root), "--inline-index"],
        cwd=str(tmp_path),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path / "decoy")},
    )

    async def exercise(create):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                assert {"recall", "remember"} <= {tool.name for tool in listing.tools}

                async def call(name, **arguments):
                    result = await session.call_tool(name, arguments)
                    assert not result.is_error, result
                    return "\n".join(c.text for c in result.content if c.type == "text")

                if create:
                    assert "No matching memories" in await call("recall")
                    old = await call(
                        "remember", type="project", title="Old decision",
                        description="original marker", body="Context: synthetic. Value: alpha.",
                    )
                    await call(
                        "remember", type="project", title="Other observation",
                        description="unrelated marker", body="Context: synthetic. Value: beta.",
                    )
                    assert "Value: alpha." in (root / old).read_text(encoding="utf-8")
                    survey = await call("recall", limit=0)
                    assert "2 matching memories" in survey and "showing 0" in survey
                    assert "](" not in survey and "Value:" not in survey
                    limited = await call("recall", limit=1)
                    assert "showing 1" in limited and "not shown" in limited
                    selected = await call("recall", query="original marker")
                    assert "Old decision" in selected and "Other observation" not in selected
                    await call(
                        "remember", type="project", title="Revised decision",
                        description="revised marker", body="Context: later evidence. Value: gamma.",
                        supersedes=old,
                    )
                    assert (root / old).is_file()

                current = await call("recall")
                assert "Revised decision" in current and "Other observation" in current
                assert "Old decision" not in current and "superseded" in current
                assert "Revised decision" in (root / "MEMORY.md").read_text(encoding="utf-8")

    async def run():
        async with asyncio.timeout(30):
            await exercise(create=True)
            await exercise(create=False)

    asyncio.run(run())
