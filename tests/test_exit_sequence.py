"""SessionStart -> SessionEnd sequence on an originally-unsigned MEMORY.md.

This is the gap the per-branch unit tests missed and the yanantin live trial
caught: after a first-touch snapshot, `exit` used to restore the stale original
instead of writing the current index. These tests pin the corrected behavior.
"""
from qhaway import cli, reconcile
from qhaway import project


def _seed_corpus(tmp_path, n=3):
    for i in range(n):
        title = f"memory number {i}"
        (tmp_path / f"{reconcile.slugify(title)}.md").write_text(
            reconcile.compose_topic_file("project", title, f"body {i}", None, None)
        )


def test_sessionstart_then_exit_leaves_current_index_not_original(tmp_path):
    # An originally-unsigned, hand-authored MEMORY.md (the yanantin shape).
    original = "# Tony's pre-install notes\n\n" + ("padding line\n" * 200)
    (tmp_path / "MEMORY.md").write_text(original)
    _seed_corpus(tmp_path)

    # SessionStart (the hook): reconcile + deliver. Snapshots the original.
    cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])
    # SessionEnd (the hook): write the current index.
    cli.main(["exit", "--dir", str(tmp_path)])

    final = (tmp_path / "MEMORY.md").read_text()
    # NOT the stale original...
    assert "pre-install notes" not in final
    assert final != original
    # ...but a current, signed, self-sufficient index of what was learned.
    assert reconcile.read_signature(final) is not None
    assert "qhaway exit index" in final
    assert "memory number 0" in final  # current corpus content is present


def test_exit_preserves_preinstall_original_under_distinguished_name(tmp_path):
    original = "# Tony's pre-install notes\n\nirreplaceable\n"
    (tmp_path / "MEMORY.md").write_text(original)
    _seed_corpus(tmp_path)

    cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])
    cli.main(["exit", "--dir", str(tmp_path)])

    # The pre-install original is preserved verbatim under its distinguished name.
    preinstall = tmp_path / reconcile.PREINSTALL_NAME
    assert preinstall.exists()
    assert preinstall.read_text() == original


def test_exit_index_stays_within_budget(tmp_path):
    original = "# unsigned original\n\nx\n"
    (tmp_path / "MEMORY.md").write_text(original)
    _seed_corpus(tmp_path, n=8)

    cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])
    cli.main(["exit", "--dir", str(tmp_path)])

    final = (tmp_path / "MEMORY.md").read_text()
    # The signed, footer-bearing exit file must stay under the projection budget.
    assert len(final.encode("utf-8")) <= project.DEFAULT_BUDGET


def test_exit_index_has_no_recall_instructions(tmp_path):
    # Self-sufficient: the hooks won't fire once disabled, so no "call recall()".
    (tmp_path / "MEMORY.md").write_text("# unsigned\n\nx\n")
    _seed_corpus(tmp_path)

    cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])
    cli.main(["exit", "--dir", str(tmp_path)])

    final = (tmp_path / "MEMORY.md").read_text()
    assert "recall()" not in final
    assert "remember(" not in final
