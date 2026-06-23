from qhaway import cli, reconcile


def _seed(tmp_path, title="a memory", body="body"):
    (tmp_path / f"{reconcile.slugify(title)}.md").write_text(
        reconcile.compose_topic_file("project", title, body, None, None)
    )


def test_exit_writes_signed_current_index(tmp_path):
    _seed(tmp_path)
    rc = cli.main(["exit", "--dir", str(tmp_path)])
    text = (tmp_path / "MEMORY.md").read_text()
    assert rc == 0
    assert reconcile.read_signature(text) is not None
    assert "a memory" in text          # current content, not a stale redirect
    assert "qhaway exit index" in text  # declared-omissions footer present


def test_exit_does_not_restore_original_writes_current_index(tmp_path):
    # Updated contract (was test_exit_restores_hand_authored_original): a normal
    # SessionEnd NEVER restores the original — it always leaves the current,
    # truncation-proof index in place. Restoring the original is the explicit
    # uninstall path, not SessionEnd. See [[live-trial-found-the-sessionend-bug]].
    _seed(tmp_path)
    original = "# Tony's hand-written notes\n\nkeep these\n"
    (tmp_path / "MEMORY-20260622T000000000000.md").write_text(original)  # unsigned backup
    rc = cli.main(["exit", "--dir", str(tmp_path)])
    text = (tmp_path / "MEMORY.md").read_text()
    assert rc == 0
    # current signed index, NOT the restored original
    assert reconcile.read_signature(text) is not None
    assert "qhaway exit index" in text
    assert "hand-written notes" not in text


def test_exit_ignores_signed_backup_as_not_hand_authored(tmp_path):
    _seed(tmp_path)
    signed_backup = reconcile.embed_signature("# old qhaway output\n\nstale\n")
    (tmp_path / "MEMORY-20260622T000000000000.md").write_text(signed_backup)
    rc = cli.main(["exit", "--dir", str(tmp_path)])
    text = (tmp_path / "MEMORY.md").read_text()
    assert rc == 0
    # signed backup is OURS, not a human original → write current index, not restore
    assert "qhaway exit index" in text
