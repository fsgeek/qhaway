"""`qhaway index` is the README's main command: regenerate MEMORY.md as the
budgeted, self-sufficient index. Since e2f297e it silently did NOTHING to disk —
the print-only condition tested `ns.status`, whose argparse default ("live") is
always truthy, so every invocation was routed to inspection. Masked for Claude
Code users because hooks and serve do their writes; fatal for the standalone-CLI
story the README sells.
"""

from __future__ import annotations

from pathlib import Path

from qhaway import cli, reconcile


def _write_memory(root: Path, stem: str) -> None:
    (root / f"{stem}.md").write_text(
        f"---\nname: {stem}\ntype: project\ndescription: about {stem}\n---\nbody\n",
        encoding="utf-8",
    )


def test_bare_index_writes_the_budgeted_index(tmp_path, capsys):
    _write_memory(tmp_path, "alpha")

    rc = cli.main(["index", "--dir", str(tmp_path)])

    assert rc == 0
    text = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert "alpha" in text  # the index, not the redirect stub, not nothing
    assert reconcile.read_signature(text) is not None


def test_explicit_status_live_is_still_an_inspection(tmp_path, capsys):
    _write_memory(tmp_path, "beta")

    rc = cli.main(["index", "--dir", str(tmp_path), "--status", "live"])

    assert rc == 0
    assert "beta" in capsys.readouterr().out
    assert not (tmp_path / "MEMORY.md").exists()  # printed, wrote nothing


def test_bare_index_reports_omissions_in_the_file(tmp_path, capsys):
    for i in range(60):
        (tmp_path / f"bulk-{i:02d}.md").write_text(
            f"---\nname: bulk-{i:02d}\ntype: project\ndescription: {'d' * 200}\n---\nbody\n",
            encoding="utf-8",
        )

    rc = cli.main(["index", "--dir", str(tmp_path), "--budget", "1200"])

    assert rc == 0
    text = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) <= 1200
    assert "memories not shown" in text
