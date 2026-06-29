"""Version honesty: one source of truth, surfaced through the MCP handshake.

qhaway had THREE disagreeing version numbers — pyproject (true),
__init__.__version__ (hand-maintained, drifted), and MCP serverInfo (the SDK's,
misreported). These tests pin __version__ to the installed package metadata and
the MCP serverInfo to __version__, so a client/model reads qhaway's real version.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import qhaway


def _pyproject_version() -> str:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_version_matches_pyproject():
    """__version__ derives from package metadata — no hand-edit, never drifts."""
    assert qhaway.__version__ == _pyproject_version()


def test_mcp_serverinfo_reports_qhaway_version():
    """The MCP handshake must report qhaway's version, not the SDK's (1.28.0).
    build_server wires __version__ into the wrapped low-level server so a client
    reading serverInfo.version gets the truth."""
    from qhaway import server

    mcp = server.build_server(".")
    opts = mcp._mcp_server.create_initialization_options()
    assert opts.server_version == qhaway.__version__
    assert opts.server_version != "1.28.0"  # the SDK version it used to misreport
