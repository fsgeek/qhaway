from qhaway import cli, reconcile


def test_signed_file_implies_backup_exists_for_user_original(tmp_path):
    original = "# human original\n\nirreplaceable\n"
    (tmp_path / "MEMORY.md").write_text(original)
    (tmp_path / "seed.md").write_text(
        reconcile.compose_topic_file("project", "seed", "b", None, None)
    )
    cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])
    mem = (tmp_path / "MEMORY.md").read_text()
    # signed file now exists...
    assert reconcile.read_signature(mem) is not None
    # ...therefore the original MUST be recoverable on disk
    backups = [p.read_text() for p in tmp_path.glob("MEMORY-*.md")]
    assert original in backups


def test_second_boot_is_idempotent_no_duplicate_backup(tmp_path):
    (tmp_path / "MEMORY.md").write_text("# human original\n\nx\n")
    (tmp_path / "seed.md").write_text(
        reconcile.compose_topic_file("project", "seed", "b", None, None)
    )
    cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])
    cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])  # reboot
    # exactly one backup — the second boot recognized our signature, didn't re-snapshot
    assert len(list(tmp_path.glob("MEMORY-*.md"))) == 1
