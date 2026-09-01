"""Hookless hosts (Claude Cowork/Desktop) read MEMORY.md directly through a
truncating loader and run no session hooks: serve's inline-index mode must keep
MEMORY.md an always-current budgeted index — at boot and after every
remember() — never the redirect stub, so a session that calls no tool still
wakes with memory-within-budget instead of amnesia. Default serve behavior
(redirect + hook-delivered projection) is pinned unchanged.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from qhaway import cli, reconcile as reconcile_mod, server


def _write_memory(root: Path, stem: str, type_: str, description: str, body: str) -> None:
    (root / f"{stem}.md").write_text(
        f"---\nname: {stem}\ntype: {type_}\ndescription: {description}\n---\n{body}\n",
        encoding="utf-8",
    )


def test_write_index_composes_signed_budgeted_index_with_live_footer(tmp_path):
    _write_memory(tmp_path, "a-live-topic", "project", "visible in the live index", "body")
    reconcile_mod.reconcile(str(tmp_path))

    cli.write_index(str(tmp_path), budget=4000, style="live")

    text = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert "a-live-topic" in text  # an index, not the redirect stub
    assert "recall()" in text  # live footer points at the running server
    assert reconcile_mod.read_signature(text) is not None


def test_reconcile_heal_false_does_not_touch_memory_md(tmp_path):
    _write_memory(tmp_path, "quiet-topic", "project", "described", "body")
    reconcile_mod.reconcile(str(tmp_path))
    cli.write_index(str(tmp_path), budget=4000, style="live")
    before = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")

    reconcile_mod.reconcile(str(tmp_path), heal=False)

    assert (tmp_path / "MEMORY.md").read_text(encoding="utf-8") == before


def test_initialize_server_inline_boots_to_current_index(tmp_path):
    _write_memory(tmp_path, "boot-topic", "project", "present from boot", "body")

    server.initialize_server(str(tmp_path), inline_budget=4000)

    text = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert "boot-topic" in text


def test_remember_inline_updates_index_immediately(tmp_path):
    server.initialize_server(str(tmp_path), inline_budget=4000)
    mcp = server.build_server(str(tmp_path), inline_budget=4000)

    asyncio.run(
        mcp.call_tool(
            "remember",
            {
                "type": "project",
                "title": "Written mid-session",
                "body": "body",
                "description": "must land in the index without any hook",
            },
        )
    )

    text = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert "must land in the index without any hook" in text


def test_inline_boot_snapshots_a_native_unsigned_memory_md(tmp_path):
    # First adoption of a host-native store (e.g. Cowork's own index): the
    # unsigned original is the human's restore source — preserve it under the
    # distinguished pre-install name before the index takes its place.
    (tmp_path / "MEMORY.md").write_text("host-native index, precious\n", encoding="utf-8")
    _write_memory(tmp_path, "adopted-topic", "project", "described", "body")

    server.initialize_server(str(tmp_path), inline_budget=4000)

    preserved = (tmp_path / "MEMORY.preinstall.md").read_text(encoding="utf-8")
    assert preserved == "host-native index, precious\n"
    assert "adopted-topic" in (tmp_path / "MEMORY.md").read_text(encoding="utf-8")


def test_default_serve_boot_still_heals_redirect(tmp_path):
    _write_memory(tmp_path, "classic-topic", "project", "described", "body")

    server.initialize_server(str(tmp_path))

    text = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert "classic-topic" not in text  # redirect stub, not an index


def test_serve_cli_wires_inline_index_budget(monkeypatch, tmp_path):
    started = {}
    monkeypatch.setattr(
        cli.server,
        "run",
        lambda d, inline_budget=None: started.update(dir=d, budget=inline_budget),
    )

    rc = cli.main(["serve", "--dir", str(tmp_path), "--inline-index", "--budget", "3400"])

    assert rc == 0
    assert started == {"dir": str(tmp_path), "budget": 3400}


def test_serve_cli_default_keeps_redirect_mode(monkeypatch, tmp_path):
    started = {}
    monkeypatch.setattr(
        cli.server,
        "run",
        lambda d, inline_budget=None: started.update(dir=d, budget=inline_budget),
    )

    cli.main(["serve", "--dir", str(tmp_path)])

    assert started["budget"] is None


def _fill(root: Path, count: int) -> None:
    for i in range(count):
        _write_memory(root, f"topic-{i:02d}", "project", "x" * 150, "body")


def test_live_index_omission_hint_names_recall_not_the_cli(tmp_path):
    # A hookless host has no shell into the store: the only way to see what
    # was set aside is the running server's recall(), so the footer must say so.
    _fill(tmp_path, 12)
    reconcile_mod.reconcile(str(tmp_path))

    cli.write_index(str(tmp_path), budget=800, style="live")

    text = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert "memories not shown" in text
    assert 'recall(type="project")' in text
    assert "qhaway index" not in text


def test_exit_index_omission_hint_keeps_the_cli(tmp_path):
    # Exit index = qhaway disabled, no server: the shell command is the right hint.
    _fill(tmp_path, 12)
    reconcile_mod.reconcile(str(tmp_path))

    cli.write_index(str(tmp_path), budget=800, style="exit")

    text = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert "memories not shown" in text
    assert "`qhaway index --type project`" in text
    assert "recall(" not in text.split("---")[0]
