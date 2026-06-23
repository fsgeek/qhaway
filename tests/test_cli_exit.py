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


def test_exit_restores_hand_authored_original(tmp_path):
    _seed(tmp_path)
    original = "# Tony's hand-written notes\n\nkeep these\n"
    (tmp_path / "MEMORY-20260622T000000000000.md").write_text(original)  # unsigned backup
    rc = cli.main(["exit", "--dir", str(tmp_path)])
    assert rc == 0
    # the human's record is restored verbatim, NOT our projection
    assert (tmp_path / "MEMORY.md").read_text() == original


def test_exit_ignores_signed_backup_as_not_hand_authored(tmp_path):
    _seed(tmp_path)
    signed_backup = reconcile.embed_signature("# old qhaway output\n\nstale\n")
    (tmp_path / "MEMORY-20260622T000000000000.md").write_text(signed_backup)
    rc = cli.main(["exit", "--dir", str(tmp_path)])
    text = (tmp_path / "MEMORY.md").read_text()
    assert rc == 0
    # signed backup is OURS, not a human original → write current index, not restore
    assert "qhaway exit index" in text
