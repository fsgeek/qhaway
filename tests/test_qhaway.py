import os
import sys
import json
import time
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import duckdb

# Import the target package modules. Under TDD, these will fail/raise import errors
# until the application skeleton is implemented. This is the expected red bar.
try:
    import qhaway.parse as parse
    import qhaway.model as model
    import qhaway.project as project
    import qhaway.cli as cli
except ImportError:
    # Under test collection, we allow collection to proceed so we can run the test suite.
    # We will raise errors inside tests if modules are missing.
    parse = None
    model = None
    project = None
    cli = None


def check_modules_loaded():
    if any(m is None for m in (parse, model, project, cli)):
        pytest.fail(
            "qhaway modules are not implemented yet. "
            "Implement parse, model, project, and cli to run these tests."
        )


# ==============================================================================
# Pytest Fixtures & Helpers
# ==============================================================================

@pytest.fixture
def temp_memory_dir(tmp_path):
    """Fixture to create a clean temporary memory directory path."""
    return tmp_path


def create_topic_file(dir_path: Path, filename: str, content: str, mtime: float = None):
    """Helper to create a topic file with optional manual modification time (mtime)."""
    file_path = dir_path / filename
    file_path.write_text(content, encoding="utf-8")
    if mtime is not None:
        os.utime(file_path, (mtime, mtime))
    return file_path


def run_qhaway_cli(args, cwd=None):
    """Helper to run the CLI via subprocess using the installed virtualenv command."""
    # We run the command via the current python executable to guarantee correct virtualenv
    cmd = [sys.executable, "-m", "qhaway.cli"] + args
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    return result


# ==============================================================================
# Requirement 1: Budget Overflow Handling
# ==============================================================================

def test_budget_overflow_handling(temp_memory_dir):
    """
    Test 1: A corpus that overflows the budget yields a MEMORY.md under the budget,
    including the reserved footer.
    """
    check_modules_loaded()
    
    # Create 10 topic files of type project
    for i in range(10):
        content = (
            f"---\n"
            f"name: Project {i}\n"
            f"type: project\n"
            f"---\n"
            f"This is project memory number {i} containing some descriptive text.\n"
        )
        create_topic_file(temp_memory_dir, f"project_topic_{i}.md", content)
        
    # We run qhaway index with a tight budget (e.g. 500 bytes)
    # The output MEMORY.md must be strictly under 500 bytes and contain the footer.
    budget = 500
    
    # Run the index generator
    exit_code = cli.main(["index", "--dir", str(temp_memory_dir), "--budget", str(budget)])
    assert exit_code == 0
    
    memory_file = temp_memory_dir / "MEMORY.md"
    assert memory_file.exists()
    
    content = memory_file.read_text(encoding="utf-8")
    byte_size = len(content.encode("utf-8"))
    
    assert byte_size <= budget, f"Expected size <= {budget}, got {byte_size} bytes"
    assert "not shown" in content, "Expected footer declaration about omitted memories"
    assert "qhaway index --type" in content, "Expected footer to contain run filter suggestion"


# ==============================================================================
# Requirement 2: No Silent Omissions
# ==============================================================================

def test_no_silent_omissions(temp_memory_dir):
    """
    Test 2: Nothing omitted is omitted silently — every omission has a declared
    footer line, and (shown + declared-omitted) == total live nodes.
    Tombstones excluded are also declared.
    """
    check_modules_loaded()
    
    # Create 5 projects and 3 references
    for i in range(5):
        create_topic_file(
            temp_memory_dir,
            f"project_{i}.md",
            f"---\ntype: project\nname: Project {i}\n---\nProject body {i}\n"
        )
    for i in range(3):
        create_topic_file(
            temp_memory_dir,
            f"reference_{i}.md",
            f"---\ntype: reference\nname: Ref {i}\n---\nRef body {i}\n"
        )
        
    # Also create a tombstoned file
    create_topic_file(
        temp_memory_dir,
        "superseded_topic.md",
        "---\ntype: project\nname: SUPERSEDED\n---\nThis was superseded.\n"
    )
    
    # Run qhaway index with a budget that forces omission of some projects/references
    # Let's check with dry-run/index under a low budget
    budget = 300
    exit_code = cli.main(["index", "--dir", str(temp_memory_dir), "--budget", str(budget)])
    assert exit_code == 0
    
    content = (temp_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    
    # Let's count how many projects and references are listed in MEMORY.md.
    # Lines match: - [Title](file.md) — hook
    shown_projects = content.count("](project_")
    shown_references = content.count("](reference_")
    
    # Parse the footer lines.
    # Output matches: +N project memories not shown; qhaway index --type project
    # Output matches: +N reference memories not shown; qhaway index --type reference
    # Output matches: +N superseded memories hidden; qhaway index --status superseded
    omitted_projects = 0
    omitted_references = 0
    superseded_declared = 0
    
    for line in content.splitlines():
        if "project memories not shown" in line:
            omitted_projects = int(line.split()[0].replace("+", ""))
        elif "reference memories not shown" in line:
            omitted_references = int(line.split()[0].replace("+", ""))
        elif "superseded memories hidden" in line:
            superseded_declared = int(line.split()[0].replace("+", ""))
            
    assert (shown_projects + omitted_projects) == 5, "Mismatch in total projects"
    assert (shown_references + omitted_references) == 3, "Mismatch in total references"
    assert superseded_declared == 1, "Expected 1 superseded node declared"


# ==============================================================================
# Requirement 3: Wiki-link Rot Checking (--check)
# ==============================================================================

def test_wikilink_rot_checking(temp_memory_dir):
    """
    Test 3: --check reports [[wikilinks]] in topic-file BODIES that point at missing files.
    """
    check_modules_loaded()
    
    # Create valid files
    create_topic_file(
        temp_memory_dir,
        "valid_one.md",
        "---\ntype: project\nname: Valid One\n---\nLinks to [[valid_two]]\n"
    )
    create_topic_file(
        temp_memory_dir,
        "valid_two.md",
        "---\ntype: project\nname: Valid Two\n---\nI exist.\n"
    )
    # Create file with broken link
    create_topic_file(
        temp_memory_dir,
        "broken_one.md",
        "---\ntype: project\nname: Broken One\n---\nLinks to [[missing_target_file]]\n"
    )
    
    # Run cli with --check. It should detect "missing_target_file" as rot and exit with error.
    # We redirect output to capture the warnings.
    with patch("sys.stdout", new_callable=MagicMock) as mock_stdout, \
         patch("sys.stderr", new_callable=MagicMock) as mock_stderr:
        exit_code = cli.main(["index", "--dir", str(temp_memory_dir), "--check"])
        
        # Verify exit_code is non-zero (since there is rot)
        assert exit_code != 0
        
        # Get stdout / stderr content
        stdout_calls = "".join([call[0][0] for call in mock_stdout.write.call_args_list])
        stderr_calls = "".join([call[0][0] for call in mock_stderr.write.call_args_list])
        full_output = stdout_calls + stderr_calls
        
        # Verify the warning is present and specifies the missing slug
        assert "missing_target_file" in full_output
        assert "broken_one.md" in full_output
        
    # Verify that --check did NOT write MEMORY.md or .qhaway.json
    assert not (temp_memory_dir / "MEMORY.md").exists()
    assert not (temp_memory_dir / ".qhaway.json").exists()


# ==============================================================================
# Requirement 4: Tombstone Handling
# ==============================================================================

def test_tombstone_handling(temp_memory_dir):
    """
    Test 4: Tombstoned nodes (SUPERSEDED / DELETED name field) are excluded from the
    default slice, but queryable by --status superseded, and declared in footer.
    """
    check_modules_loaded()
    
    # Create live topic
    create_topic_file(
        temp_memory_dir,
        "live_topic.md",
        "---\ntype: project\nname: Active Project\n---\nBody here\n"
    )
    # Create SUPERSEDED tombstone
    create_topic_file(
        temp_memory_dir,
        "old_project.md",
        "---\ntype: project\nname: SUPERSEDED\n---\nOld project body\n"
    )
    # Create DELETED tombstone (Finding S3: DELETED-marked file)
    create_topic_file(
        temp_memory_dir,
        "deleted_project.md",
        "---\ntype: project\nname: DELETED\n---\nDeleted project body\n"
    )
    
    # Default index run
    exit_code = cli.main(["index", "--dir", str(temp_memory_dir)])
    assert exit_code == 0
    
    content = (temp_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    
    # Tombstones must be excluded from listing
    assert "live_topic.md" in content
    assert "old_project.md" not in content
    assert "deleted_project.md" not in content
    
    # Footer must declare 2 superseded memories hidden
    assert "2 superseded memories hidden" in content
    
    # Now query specifically by --status superseded.
    # This should regenerate MEMORY.md with ONLY superseded files.
    exit_code = cli.main(["index", "--dir", str(temp_memory_dir), "--status", "superseded"])
    assert exit_code == 0
    
    superseded_content = (temp_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    assert "old_project.md" in superseded_content
    assert "deleted_project.md" in superseded_content
    assert "live_topic.md" not in superseded_content


# ==============================================================================
# Requirement 5: Machine Contract (Pattern + Resolvable Links)
# ==============================================================================

def test_machine_contract_format(temp_memory_dir):
    """
    Test 5: Machine-contract, not "format": every emitted line matches the harness pattern
    `- [Title](file.md) — hook`, and every link target resolves to a file on disk.
    """
    check_modules_loaded()
    
    # Create multiple topics with varying hooks (frontmatter description or similar)
    # Note: Hook is the frontmatter description or index hook.
    create_topic_file(
        temp_memory_dir,
        "topic_a.md",
        "---\ntype: project\nname: Title A\ndescription: Actionable hook description A\n---\nBody A"
    )
    create_topic_file(
        temp_memory_dir,
        "topic_b.md",
        "---\ntype: reference\nname: Title B\ndescription: Resource hook B\n---\nBody B"
    )
    
    exit_code = cli.main(["index", "--dir", str(temp_memory_dir)])
    assert exit_code == 0
    
    content = (temp_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    lines = content.splitlines()
    
    # Check that entries match the pattern: - [Title](file.md) — hook
    list_lines = [line for line in lines if line.strip().startswith("- ")]
    assert len(list_lines) >= 2
    
    for line in list_lines:
        # Pattern: - [Title](file.md) — hook
        assert " — " in line
        prefix, hook = line.split(" — ", 1)
        assert prefix.startswith("- [")
        assert "]" in prefix
        assert "(" in prefix and prefix.endswith(")")
        
        # Extract filename
        filename = prefix.split("(")[-1][:-1]
        # Verify filename resolves to a file on disk
        target_path = temp_memory_dir / filename
        assert target_path.exists(), f"Emitted link target {filename} does not exist"


# ==============================================================================
# Requirement 6: Non-Destructive Edit-Handling (D)
# ==============================================================================

def test_non_destructive_edit_handling(temp_memory_dir):
    """
    Test 6: Given a MEMORY.md whose hash differs from the recorded last-output hash,
    qhaway index renames it to MEMORY-<timestamp>.md before writing the fresh one.
    """
    check_modules_loaded()
    
    # Write a topic file
    create_topic_file(
        temp_memory_dir,
        "topic.md",
        "---\ntype: user\nname: User Topic\n---\nSome user profile details.\n"
    )
    
    # 1. Run index to initialize MEMORY.md and .qhaway.json
    exit_code = cli.main(["index", "--dir", str(temp_memory_dir)])
    assert exit_code == 0
    
    memory_file = temp_memory_dir / "MEMORY.md"
    sidecar_file = temp_memory_dir / ".qhaway.json"
    
    assert memory_file.exists()
    assert sidecar_file.exists()
    
    original_memory_content = memory_file.read_text(encoding="utf-8")
    
    # 2. Simulate manual hand-edit of MEMORY.md (change hash)
    edited_memory_content = original_memory_content + "\n- [Stray Hand-Edit](stray.md) — Some manually added prose\n"
    memory_file.write_text(edited_memory_content, encoding="utf-8")
    
    # 3. Run qhaway index again. It must detect change, preserve MEMORY.md, and write fresh.
    # We patch time to have a known timestamp.
    mock_now = datetime(2026, 6, 20, 14, 30, 0, tzinfo=timezone.utc)
    with patch("qhaway.cli.datetime") as mock_datetime:
        # Support both datetime.now(timezone.utc) and datetime.utcnow() or similar
        mock_datetime.now.return_value = mock_now
        mock_datetime.utcnow.return_value = mock_now
        mock_datetime.fromtimestamp.side_effect = lambda t, tz=None: datetime.fromtimestamp(t, tz)
        
        exit_code = cli.main(["index", "--dir", str(temp_memory_dir)])
        assert exit_code == 0
        
    # Verify that the backup file is written with correct microsecond/timestamp resolution
    # Standard format: MEMORY-20260620T143000.md or similar.
    # Let's search for files matching MEMORY-*.md
    backup_files = list(temp_memory_dir.glob("MEMORY-*.md"))
    assert len(backup_files) == 1
    
    backup_file = backup_files[0]
    # Check that backup content matches the edited content exactly
    assert backup_file.read_text(encoding="utf-8") == edited_memory_content
    
    # Check that MEMORY.md is regenerated back to fresh content
    assert memory_file.read_text(encoding="utf-8") == original_memory_content


# ==============================================================================
# Requirement 7: Budget is Token-Pinned
# ==============================================================================

def test_budget_is_token_pinned():
    """
    Test 7: The default budget constant is asserted against the measured harness limit,
    so a limit change fails this test rather than silently re-truncating.
    Verified live harness limit is 25000 bytes.
    """
    check_modules_loaded()
    
    # We check that the default budget defined in our CLI/project modules is strictly
    # less than 25000 bytes (e.g. 24000 or 24400 bytes, representing measured limit - headroom).
    # It must also be pinned in code so a developer cannot change it without changing the test.
    default_budget = getattr(cli, "DEFAULT_BUDGET", None) or getattr(project, "DEFAULT_BUDGET", None)
    assert default_budget is not None, "DEFAULT_BUDGET constant not defined in cli or project modules"
    
    # Verified live harness limit: 25000 bytes
    HARNESS_LIMIT_BYTES = 25000
    assert default_budget <= HARNESS_LIMIT_BYTES, f"Default budget {default_budget} exceeds live harness limit {HARNESS_LIMIT_BYTES}"
    
    # Pin the exact default value to prevent silent deviation
    EXPECTED_PINNED_BUDGET = 24000
    assert default_budget == EXPECTED_PINNED_BUDGET, f"Default budget changed from pinned {EXPECTED_PINNED_BUDGET} to {default_budget}"


# ==============================================================================
# Requirement 8: Idempotence (Cornerstone of D)
# ==============================================================================

def test_idempotence_tiebreak(temp_memory_dir):
    """
    Test 8: Two consecutive qhaway index runs with no topic-file changes produce a
    byte-identical MEMORY.md and create zero new MEMORY-<ts>.md files.
    Fixture requirement: The idempotence corpus MUST include at least one pair of nodes
    with identical date_hint AND identical mtime, so the filename final tiebreak
    is actually exercised.
    """
    check_modules_loaded()
    
    # Set up tie-break nodes with identical date_hint and identical mtime (as per S2 / Test 8 fixture rule).
    # Files: node_a.md and node_b.md
    # Same date_hint, same mtime (e.g., 1753990000.0)
    fixed_mtime = 1753990000.0
    
    # We put them in the prioritized set (or normal project set) so they are sorted together.
    # Note: Findings S2 specifies model on aider/tinkuy (tiebreak-dominant).
    content_a = (
        "---\n"
        "type: project\n"
        "name: Node A\n"
        "date_hint: 2026-06-20\n"
        "---\n"
        "Body A\n"
    )
    content_b = (
        "---\n"
        "type: project\n"
        "name: Node B\n"
        "date_hint: 2026-06-20\n"
        "---\n"
        "Body B\n"
    )
    
    create_topic_file(temp_memory_dir, "project_node_a.md", content_a, mtime=fixed_mtime)
    create_topic_file(temp_memory_dir, "project_node_b.md", content_b, mtime=fixed_mtime)
    
    # 1. First Run: Generates MEMORY.md
    exit_code = cli.main(["index", "--dir", str(temp_memory_dir)])
    assert exit_code == 0
    
    memory_file = temp_memory_dir / "MEMORY.md"
    assert memory_file.exists()
    first_run_content = memory_file.read_bytes()
    
    # Ensure backups do not exist
    backup_files_1 = list(temp_memory_dir.glob("MEMORY-*.md"))
    assert len(backup_files_1) == 0
    
    # 2. Second Run: With absolutely no changes.
    # Must produce byte-identical MEMORY.md and no renames.
    exit_code = cli.main(["index", "--dir", str(temp_memory_dir)])
    assert exit_code == 0
    
    second_run_content = memory_file.read_bytes()
    assert first_run_content == second_run_content, "MEMORY.md content changed between runs!"
    
    backup_files_2 = list(temp_memory_dir.glob("MEMORY-*.md"))
    assert len(backup_files_2) == 0, "Idempotent run triggered a non-destructive rename!"


# ==============================================================================
# Requirement 9: Orphan Visibility (--check)
# ==============================================================================

def test_orphan_visibility(temp_memory_dir):
    """
    Test 9: --check reports the count and names of existing MEMORY-<ts>.md orphan files.
    """
    check_modules_loaded()
    
    # Create topic file to allow check to proceed
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: Project\n---\nBody")
    
    # Create dummy orphan backup files
    orphan_1 = temp_memory_dir / "MEMORY-20260620T120000.md"
    orphan_1.write_text("Old preserved index 1", encoding="utf-8")
    orphan_2 = temp_memory_dir / "MEMORY-20260620T120100.md"
    orphan_2.write_text("Old preserved index 2", encoding="utf-8")
    
    with patch("sys.stdout", new_callable=MagicMock) as mock_stdout:
        # Run check
        exit_code = cli.main(["index", "--dir", str(temp_memory_dir), "--check"])
        
        # Verify success exit code (assuming no rot exist)
        assert exit_code == 0
        
        stdout_calls = "".join([call[0][0] for call in mock_stdout.write.call_args_list])
        
        # Output must report 2 orphan files and list their names
        assert "2" in stdout_calls
        assert "MEMORY-20260620T120000.md" in stdout_calls
        assert "MEMORY-20260620T120100.md" in stdout_calls


# ==============================================================================
# Requirement 10: Prioritized Set is Not Budget-Exempt
# ==============================================================================

def test_prioritized_set_not_exempt(temp_memory_dir):
    """
    Test 10: A corpus whose user+feedback nodes ALONE exceed the budget still yields
    a MEMORY.md under budget, with the omission declared.
    """
    check_modules_loaded()
    
    # Create multiple user and feedback topics
    for i in range(5):
        create_topic_file(
            temp_memory_dir,
            f"user_{i}.md",
            f"---\ntype: user\nname: User {i}\n---\nUser settings info {i}\n"
        )
    for i in range(5):
        create_topic_file(
            temp_memory_dir,
            f"feedback_{i}.md",
            f"---\ntype: feedback\nname: Feedback {i}\n---\nFeedback loop info {i}\n"
        )
        
    # Run with a very low budget (e.g. 300 bytes)
    budget = 300
    exit_code = cli.main(["index", "--dir", str(temp_memory_dir), "--budget", str(budget)])
    assert exit_code == 0
    
    memory_file = temp_memory_dir / "MEMORY.md"
    content = memory_file.read_text(encoding="utf-8")
    byte_size = len(content.encode("utf-8"))
    
    assert byte_size <= budget
    # The prioritized set must have yielded to declared omission
    assert "user memories not shown" in content or "feedback memories not shown" in content


# ==============================================================================
# Requirement 11: Preservation Can't Self-Destruct
# ==============================================================================

def test_preservation_cant_self_destruct(temp_memory_dir):
    """
    Test 11: Two renames forced to the same timestamp resolution produce two
    distinct MEMORY-<ts>[-NN].md files — the second never overwrites the first.
    """
    check_modules_loaded()
    
    # Create topic file
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: Topic\n---\nBody")
    
    # Run index to initialize
    cli.main(["index", "--dir", str(temp_memory_dir)])
    
    memory_file = temp_memory_dir / "MEMORY.md"
    sidecar_file = temp_memory_dir / ".qhaway.json"
    
    # 1. Edit MEMORY.md manually to trigger first rename
    edit_1 = memory_file.read_text(encoding="utf-8") + "\n- Edit 1\n"
    memory_file.write_text(edit_1, encoding="utf-8")
    
    # Force mock time to a fixed timestamp
    mock_now = datetime(2026, 6, 20, 14, 30, 0, tzinfo=timezone.utc)
    
    with patch("qhaway.cli.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_now
        mock_datetime.utcnow.return_value = mock_now
        mock_datetime.fromtimestamp.side_effect = lambda t, tz=None: datetime.fromtimestamp(t, tz)
        
        # First rename run
        cli.main(["index", "--dir", str(temp_memory_dir)])
        
    # Check that first backup file exists
    backup_1 = temp_memory_dir / "MEMORY-20260620T143000.md"
    assert backup_1.exists()
    assert backup_1.read_text(encoding="utf-8") == edit_1
    
    # 2. Edit MEMORY.md manually again to trigger second rename
    edit_2 = memory_file.read_text(encoding="utf-8") + "\n- Edit 2\n"
    memory_file.write_text(edit_2, encoding="utf-8")
    
    # Run second rename, still mocking to the same exact timestamp
    with patch("qhaway.cli.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_now
        mock_datetime.utcnow.return_value = mock_now
        mock_datetime.fromtimestamp.side_effect = lambda t, tz=None: datetime.fromtimestamp(t, tz)
        
        cli.main(["index", "--dir", str(temp_memory_dir)])
        
    # Both backup files must exist. Second must have a sequence suffix like -01 or -1.
    backup_2 = temp_memory_dir / "MEMORY-20260620T143000-01.md"
    # Fallback to verify a hyphenated numeric suffix
    if not backup_2.exists():
        backup_2 = temp_memory_dir / "MEMORY-20260620T143000-1.md"
        
    assert backup_1.exists(), "First backup was overwritten!"
    assert backup_2.exists(), "Second backup was not created or sequence suffix was not appended!"
    
    assert backup_1.read_text(encoding="utf-8") == edit_1
    assert backup_2.read_text(encoding="utf-8") == edit_2


# ==============================================================================
# Requirement 12: Low/Zero Topic Files Guard (Finding S4 Amendment)
# ==============================================================================

def test_zero_topic_files_guard(temp_memory_dir):
    """
    Test 12: given a 0-topic-file dir, qhaway index declines/warns rather than
    producing an empty index and superseding any existing file.
    Also tests that --check flags low-count directories.
    """
    check_modules_loaded()
    
    # --- Part A: Zero topic files refusal ---
    # We place a pre-existing hand-written MEMORY.md
    original_memory_content = "# Preserved Memory Index\n- [Topic](topic.md) — Old topic hook\n"
    memory_file = temp_memory_dir / "MEMORY.md"
    memory_file.write_text(original_memory_content, encoding="utf-8")
    
    # No topic files are in the temp_memory_dir.
    # Run index. It must exit with error, refuse to overwrite or rename.
    exit_code = cli.main(["index", "--dir", str(temp_memory_dir)])
    assert exit_code != 0
    
    # Verify MEMORY.md is untouched and no backups are created
    assert memory_file.read_text(encoding="utf-8") == original_memory_content
    backup_files = list(temp_memory_dir.glob("MEMORY-*.md"))
    assert len(backup_files) == 0
    
    # --- Part B: Low topic files warning ---
    # Create 1 topic file (low count, >= 1 and < 3)
    create_topic_file(temp_memory_dir, "topic_one.md", "---\ntype: project\nname: Project 1\n---\nBody")
    
    # Run --check. It should succeed but flag the low-count directory in output.
    with patch("sys.stdout", new_callable=MagicMock) as mock_stdout, \
         patch("sys.stderr", new_callable=MagicMock) as mock_stderr:
        exit_code = cli.main(["index", "--dir", str(temp_memory_dir), "--check"])
        
        # S4 specifies: Proceed but --check flags low-count dirs (returns 0 but logs warning)
        assert exit_code == 0
        
        stdout_calls = "".join([call[0][0] for call in mock_stdout.write.call_args_list])
        stderr_calls = "".join([call[0][0] for call in mock_stderr.write.call_args_list])
        full_output = stdout_calls + stderr_calls
        
        # Check that it warns about low-count
        assert any(word in full_output.lower() for word in ["low", "few", "count", "topic"])
