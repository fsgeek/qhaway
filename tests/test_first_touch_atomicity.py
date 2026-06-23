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
    # ...therefore the original MUST be recoverable on disk, under its
    # distinguished pre-install name.
    preinstall = tmp_path / reconcile.PREINSTALL_NAME
    assert preinstall.exists()
    assert preinstall.read_text() == original


def test_second_boot_is_idempotent_no_duplicate_backup(tmp_path):
    original = "# human original\n\nx\n"
    (tmp_path / "MEMORY.md").write_text(original)
    (tmp_path / "seed.md").write_text(
        reconcile.compose_topic_file("project", "seed", "b", None, None)
    )
    cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])
    cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])  # reboot
    # exactly one pre-install snapshot — the second boot recognized our signature
    # and did NOT re-snapshot; the original is captured once and only once.
    assert (tmp_path / reconcile.PREINSTALL_NAME).read_text() == original
    assert list(tmp_path.glob("MEMORY-*.md")) == []  # no timestamped backups either
