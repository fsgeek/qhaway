import os
from pathlib import Path
from qhaway import reconcile


def _heal(tmp_path: Path) -> Path:
    reconcile._heal_redirect(tmp_path)
    return tmp_path / "MEMORY.md"


def test_absent_writes_signed_redirect(tmp_path):
    mem = _heal(tmp_path)
    text = mem.read_text()
    assert reconcile.read_signature(text) is not None
    assert "recall()" in text  # redirect content present


def test_user_original_is_snapshotted_then_replaced(tmp_path):
    original = "# My hand-written memory\n\nimportant human notes\n"
    (tmp_path / "MEMORY.md").write_text(original)
    _heal(tmp_path)
    backups = list(tmp_path.glob("MEMORY-*.md"))
    assert len(backups) == 1
    assert backups[0].read_text() == original  # original preserved verbatim
    assert reconcile.read_signature((tmp_path / "MEMORY.md").read_text()) is not None


def test_our_unchanged_output_rebuilds_without_backup(tmp_path):
    _heal(tmp_path)  # write ours once
    _heal(tmp_path)  # heal again, unchanged
    assert list(tmp_path.glob("MEMORY-*.md")) == []  # no spurious backup
    assert reconcile.read_signature((tmp_path / "MEMORY.md").read_text()) is not None


def test_hand_edit_to_our_file_is_preserved(tmp_path):
    _heal(tmp_path)
    mem = tmp_path / "MEMORY.md"
    # human edits our signed file but leaves the signature line
    edited = mem.read_text().replace("recall()", "recall()  # MY NOTE")
    os.chmod(mem, 0o644)  # heal writes 0444; restore write to simulate a hand-edit
    mem.write_text(edited)
    _heal(tmp_path)
    backups = list(tmp_path.glob("MEMORY-*.md"))
    assert len(backups) == 1
    assert "MY NOTE" in backups[0].read_text()  # the edit was preserved
