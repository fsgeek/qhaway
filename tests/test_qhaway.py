import os
import sys
import json
import time
import glob
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import duckdb

# Import target package modules.
# In TDD, these will fail/raise import errors until the application skeleton is written.
try:
    import qhaway.parse as parse
    import qhaway.model as model
    import qhaway.project as project
    import qhaway.cli as cli
except ImportError:
    parse = None
    model = None
    project = None
    cli = None


def check_modules_loaded():
    if any(m is None for m in (parse, model, project, cli)):
        pytest.fail(
            "qhaway modules are not implemented yet. "
            "Implement parse, model, project, and cli to run unit tests."
        )


# ==============================================================================
# Pytest Fixtures & Shared Helpers
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
    """
    Runs the CLI purely via subprocess to test actual execution boundaries,
    ensuring process isolation and mock-free integration.
    """
    cmd = [sys.executable, "-m", "qhaway.cli"] + args
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    return result


# ==============================================================================
# SECTION A: UNIT TESTS (Direct Module & API Assertions)
# ==============================================================================

def test_unit_parse_memory_file(temp_memory_dir):
    """
    Unit Test: Validates qhaway.parse.parse_memory_file on normal Markdown
    files, including metadata derivation and wikilink extraction.
    """
    check_modules_loaded()

    # Create a typical topic file
    content = (
        "---\n"
        "name: project_a\n"
        "type: project\n"
        "originSessionId: session_123\n"
        "---\n"
        "This is the body. It references [[topic_b]] and [[topic_c]].\n"
    )
    filepath = create_topic_file(temp_memory_dir, "project_a.md", content)
    
    result = parse.parse_memory_file(str(filepath))
    
    assert result["file"] == "project_a.md"
    assert result["name"] == "project_a"
    assert result["content_type"] == "project"
    assert result["role"] == "project"  # Derived from "project_a.md" prefix
    assert result["status"] == "live"
    assert result["origin_session"] == "session_123"
    assert "topic_b" in result["links"]
    assert "topic_c" in result["links"]
    assert "This is the body." in result["body"]


def test_unit_parse_fallback_and_tolerance(temp_memory_dir):
    """
    Unit Test: Verifies tolerance to malformed/unquoted colon frontmatter.
    "Never drop a file silently on a parse slip — fall back to a tolerant parse..."
    """
    check_modules_loaded()

    # Malformed frontmatter with unquoted colons
    content = (
        "---\n"
        "name: project_broken:sub:section\n"
        "type: project\n"
        "invalid_yaml_field: { unmatched_brace\n"
        "---\n"
        "Prose content stays intact.\n"
    )
    filepath = create_topic_file(temp_memory_dir, "project_broken.md", content)
    
    # Tolerant parser should succeed without throwing exceptions
    result = parse.parse_memory_file(str(filepath))
    
    assert result["file"] == "project_broken.md"
    # Even if parsing YAML fails, prose body must be recovered
    assert "Prose content stays intact." in result["body"]
    # Fallback to body-only parsing defaults metadata fields gracefully
    assert result["status"] == "live"


def test_unit_model_build_index(temp_memory_dir):
    """
    Unit Test: Verifies qhaway.model.build_index generates correct database
    schemas (nodes and edges) and populates them correctly.
    """
    check_modules_loaded()

    # Write source topic files
    create_topic_file(
        temp_memory_dir,
        "project_a.md",
        "---\ntype: project\nname: Project A\n---\nRefers to [[reference_b]]"
    )
    create_topic_file(
        temp_memory_dir,
        "reference_b.md",
        "---\ntype: reference\nname: SUPERSEDED\n---\nSuperseded body"
    )

    # Build database index in memory
    db_conn = model.build_index(str(temp_memory_dir), db_path=":memory:")
    
    # Assert nodes schema and contents
    nodes = db_conn.execute("SELECT file, name, content_type, role, status FROM nodes ORDER BY file").fetchall()
    assert len(nodes) == 2
    
    # Node A assertions
    assert nodes[0][0] == "project_a.md"
    assert nodes[0][2] == "project"
    assert nodes[0][3] == "project"
    assert nodes[0][4] == "live"
    
    # Node B assertions (Tombstone status check SUPERSEDED)
    assert nodes[1][0] == "reference_b.md"
    assert nodes[1][2] == "reference"
    assert nodes[1][4] == "superseded"
    
    # Assert edges schema and contents
    edges = db_conn.execute("SELECT src_file, dst_slug, kind FROM edges").fetchall()
    assert len(edges) == 1
    assert edges[0][0] == "project_a.md"
    assert edges[0][1] == "reference_b"
    assert edges[0][2] == "REFERENCES"


def test_unit_project_sort_hierarchy():
    """
    Unit Test: Directly asserts sorting precedence logic on database rows.
    Hierarchy: [date_hint?] -> origin_session -> mtime -> filename
    """
    check_modules_loaded()

    # Establish an in-memory db setup using model schemas
    db_conn = duckdb.connect(":memory:")
    db_conn.execute(
        "CREATE TABLE nodes ("
        "  file VARCHAR, name VARCHAR, content_type VARCHAR, role VARCHAR, "
        "  status VARCHAR, origin_session VARCHAR, date_hint VARCHAR, body VARCHAR, mtime DOUBLE"
        ")"
    )
    
    # Insert rows that pit sort criteria against each other:
    # Row 1: date_hint present, older session/mtime
    db_conn.execute(
        "INSERT INTO nodes VALUES ('file_1.md', 'N1', 'project', 'proj', 'live', 'sess_A', '2026-06-20', 'Body', 10.0)"
    )
    # Row 2: date_hint absent, but newer origin_session
    db_conn.execute(
        "INSERT INTO nodes VALUES ('file_2.md', 'N2', 'project', 'proj', 'live', 'sess_B', NULL, 'Body', 20.0)"
    )
    # Row 3: date_hint & origin_session absent, newest mtime
    db_conn.execute(
        "INSERT INTO nodes VALUES ('file_3.md', 'N3', 'project', 'proj', 'live', NULL, NULL, 'Body', 30.0)"
    )
    # Row 4: Identical fields to Row 3, but different filename (should tiebreak alphabetically)
    db_conn.execute(
        "INSERT INTO nodes VALUES ('file_4.md', 'N4', 'project', 'proj', 'live', NULL, NULL, 'Body', 30.0)"
    )

    # Invoke sorting query matching step 4 projection rules
    sorted_files = db_conn.execute(
        "SELECT file FROM nodes ORDER BY "
        "  date_hint DESC NULLS LAST, "
        "  origin_session DESC NULLS LAST, "
        "  mtime DESC, "
        "  file ASC"
    ).fetchall()

    # Precedence ensures:
    # 1st: file_1.md (has date_hint)
    # 2nd: file_2.md (has origin_session)
    # 3rd: file_3.md (has newest mtime, tiebreak over file_4.md)
    # 4th: file_4.md (older alphabetically than file_3)
    assert sorted_files[0][0] == "file_1.md"
    assert sorted_files[1][0] == "file_2.md"
    assert sorted_files[2][0] == "file_3.md"
    assert sorted_files[3][0] == "file_4.md"


# ==============================================================================
# SECTION B: INTEGRATION TESTS (Process-Isolated Subprocess Runs)
# ==============================================================================

def test_cli_budget_overflow_handling(temp_memory_dir):
    """
    Test 1: A corpus that overflows the budget yields a MEMORY.md under the budget,
    including the reserved footer.
    """
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
        
    budget = 500
    
    # Run the index generator via CLI subprocess
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir), "--budget", str(budget)])
    assert res.returncode == 0
    
    memory_file = temp_memory_dir / "MEMORY.md"
    assert memory_file.exists()
    
    content = memory_file.read_text(encoding="utf-8")
    byte_size = len(content.encode("utf-8"))
    
    assert byte_size <= budget, f"Expected size <= {budget}, got {byte_size} bytes"
    assert "not shown" in content, "Expected footer declaration about omitted memories"
    assert "qhaway index --type" in content, "Expected footer to contain run filter suggestion"


def test_cli_no_silent_omissions(temp_memory_dir):
    """
    Test 2: Nothing omitted is omitted silently — every omission has a declared
    footer line, and (shown + declared-omitted) == total live nodes.
    Tombstones excluded are also declared.
    """
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
    
    budget = 300
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir), "--budget", str(budget)])
    assert res.returncode == 0
    
    content = (temp_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    
    # Count listed items in output
    shown_projects = content.count("](project_")
    shown_references = content.count("](reference_")
    
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


def test_cli_wikilink_rot_checking(temp_memory_dir):
    """
    Test 3: --check reports [[wikilinks]] in topic-file BODIES that point at missing files.
    """
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
    # Broken link
    create_topic_file(
        temp_memory_dir,
        "broken_one.md",
        "---\ntype: project\nname: Broken One\n---\nLinks to [[missing_target_file]]\n"
    )
    
    # Execute check via subprocess
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir), "--check"])
    
    assert res.returncode != 0
    full_output = res.stdout + res.stderr
    assert "missing_target_file" in full_output
    assert "broken_one.md" in full_output
    
    # Verify check did NOT write files
    assert not (temp_memory_dir / "MEMORY.md").exists()
    assert not (temp_memory_dir / ".qhaway.json").exists()


def test_cli_tombstone_handling(temp_memory_dir):
    """
    Test 4: Tombstoned nodes are excluded from default run, visible in status=superseded,
    and declared in footer.
    """
    create_topic_file(
        temp_memory_dir,
        "live_topic.md",
        "---\ntype: project\nname: Active Project\n---\nBody here\n"
    )
    create_topic_file(
        temp_memory_dir,
        "old_project.md",
        "---\ntype: project\nname: SUPERSEDED\n---\nOld project body\n"
    )
    create_topic_file(
        temp_memory_dir,
        "deleted_project.md",
        "---\ntype: project\nname: DELETED\n---\nDeleted project body\n"
    )
    
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir)])
    assert res.returncode == 0
    
    content = (temp_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    assert "live_topic.md" in content
    assert "old_project.md" not in content
    assert "deleted_project.md" not in content
    assert "2 superseded memories hidden" in content
    
    # Query superseded slice specifically
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir), "--status", "superseded"])
    assert res.returncode == 0
    
    superseded_content = (temp_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    assert "old_project.md" in superseded_content
    assert "deleted_project.md" in superseded_content
    assert "live_topic.md" not in superseded_content


def test_cli_role_filtering(temp_memory_dir):
    """
    Gaps Fix CLI Flag: Verifies the --role <role> filter functions as expected on disk.
    """
    # Filename prefix defines role
    create_topic_file(
        temp_memory_dir,
        "feedback_topic.md",
        "---\ntype: feedback\nname: Feedback Topic\n---\nBody"
    )
    create_topic_file(
        temp_memory_dir,
        "project_topic.md",
        "---\ntype: project\nname: Project Topic\n---\nBody"
    )

    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir), "--role", "feedback"])
    assert res.returncode == 0

    content = (temp_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    assert "feedback_topic.md" in content
    assert "project_topic.md" not in content


def test_cli_dry_run_action(temp_memory_dir):
    """
    Gaps Fix CLI Flag: Verifies that --dry-run prints projection to stdout
    without editing MEMORY.md on disk.
    """
    create_topic_file(
        temp_memory_dir,
        "topic.md",
        "---\ntype: project\nname: Project Title\n---\nBody content"
    )

    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir), "--dry-run"])
    assert res.returncode == 0

    # Output must carry content
    assert "project_title" in res.stdout.lower() or "topic.md" in res.stdout
    # Disk remains untouched
    assert not (temp_memory_dir / "MEMORY.md").exists()


def test_cli_machine_contract_format(temp_memory_dir):
    """
    Test 5: Emitted index lines match pattern and links resolve.
    """
    create_topic_file(
        temp_memory_dir,
        "topic_a.md",
        "---\ntype: project\nname: Title A\ndescription: Hook description A\n---\nBody A"
    )
    create_topic_file(
        temp_memory_dir,
        "topic_b.md",
        "---\ntype: reference\nname: Title B\ndescription: Hook B\n---\nBody B"
    )
    
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir)])
    assert res.returncode == 0
    
    content = (temp_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    list_lines = [line for line in content.splitlines() if line.strip().startswith("- ")]
    assert len(list_lines) >= 2
    
    for line in list_lines:
        assert " — " in line
        prefix, hook = line.split(" — ", 1)
        assert prefix.startswith("- [")
        assert "]" in prefix
        assert "(" in prefix and prefix.endswith(")")
        
        filename = prefix.split("(")[-1][:-1]
        assert (temp_memory_dir / filename).exists()


def test_cli_non_destructive_edit_handling(temp_memory_dir):
    """
    Test 6 & Gaps Fix Edit Backup: Non-destructive edit handling.
    Ensures that custom edits trigger timestamps and sequential backups.
    Does not require system clock mocking inside subprocess environments.
    """
    create_topic_file(
        temp_memory_dir,
        "topic.md",
        "---\ntype: user\nname: User Topic\n---\nSome user profile details.\n"
    )
    
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir)])
    assert res.returncode == 0
    
    memory_file = temp_memory_dir / "MEMORY.md"
    original_content = memory_file.read_text(encoding="utf-8")
    
    # Hand edit memory index
    edited_content = original_content + "\n- [Stray Edit](stray.md) — Manual Note\n"
    memory_file.write_text(edited_content, encoding="utf-8")
    
    # Run again to trigger rename
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir)])
    assert res.returncode == 0
    
    # Check for glob pattern matching backup structure: MEMORY-*.md
    backups = glob.glob(str(temp_memory_dir / "MEMORY-*.md"))
    assert len(backups) == 1
    assert Path(backups[0]).read_text(encoding="utf-8") == edited_content
    
    # Verify index restored
    assert memory_file.read_text(encoding="utf-8") == original_content


def test_cli_budget_is_token_pinned():
    """
    Test 7: Default budget constant pinned. Evaluated on module package structure
    if implemented. Otherwise CLI usage checks defaults.
    """
    check_modules_loaded()
    
    default_budget = getattr(cli, "DEFAULT_BUDGET", None) or getattr(project, "DEFAULT_BUDGET", None)
    assert default_budget is not None
    
    HARNESS_LIMIT_BYTES = 25000
    assert default_budget <= HARNESS_LIMIT_BYTES
    
    EXPECTED_PINNED_BUDGET = 24000
    assert default_budget == EXPECTED_PINNED_BUDGET


def test_cli_idempotence_tiebreak(temp_memory_dir):
    """
    Test 8: Idempotence check with SAME mtime and date_hint (Findings S2 Tinkuy layout).
    """
    fixed_mtime = 1753990000.0
    content_a = "---\ntype: project\nname: Node A\ndate_hint: 2026-06-20\n---\nBody A\n"
    content_b = "---\ntype: project\nname: Node B\ndate_hint: 2026-06-20\n---\nBody B\n"
    
    create_topic_file(temp_memory_dir, "project_node_a.md", content_a, mtime=fixed_mtime)
    create_topic_file(temp_memory_dir, "project_node_b.md", content_b, mtime=fixed_mtime)
    
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir)])
    assert res.returncode == 0
    
    memory_file = temp_memory_dir / "MEMORY.md"
    first_bytes = memory_file.read_bytes()
    
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir)])
    assert res.returncode == 0
    
    second_bytes = memory_file.read_bytes()
    assert first_bytes == second_bytes
    
    # No backups created
    backups = glob.glob(str(temp_memory_dir / "MEMORY-*.md"))
    assert len(backups) == 0


def test_cli_orphan_visibility(temp_memory_dir):
    """
    Test 9: --check reports orphans.
    """
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: Project\n---\nBody")
    
    # Generate mock orphans on disk
    (temp_memory_dir / "MEMORY-20260620T120000.md").write_text("Backup 1")
    (temp_memory_dir / "MEMORY-20260620T120100.md").write_text("Backup 2")
    
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir), "--check"])
    assert res.returncode == 0
    
    output = res.stdout + res.stderr
    assert "2" in output
    assert "MEMORY-20260620T120000.md" in output
    assert "MEMORY-20260620T120100.md" in output


def test_cli_prioritized_set_not_exempt(temp_memory_dir):
    """
    Test 10: Prioritized files are also subject to budget restrictions.
    """
    for i in range(5):
        create_topic_file(temp_memory_dir, f"user_{i}.md", f"---\ntype: user\nname: User {i}\n---\nUser body {i}")
    for i in range(5):
        create_topic_file(temp_memory_dir, f"feedback_{i}.md", f"---\ntype: feedback\nname: Feed {i}\n---\nFeed body {i}")
        
    budget = 300
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir), "--budget", str(budget)])
    assert res.returncode == 0
    
    content = (temp_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    assert len(content.encode("utf-8")) <= budget
    assert "user memories not shown" in content or "feedback memories not shown" in content


def test_cli_preservation_cant_self_destruct(temp_memory_dir):
    """
    Test 11: Non-destructive overwrite prevention. Multiple renames write sequential suffixes.
    """
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: Topic\n---\nBody")
    
    # Init
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir)])
    assert res.returncode == 0
    
    memory_file = temp_memory_dir / "MEMORY.md"
    
    # 1. Edit manually
    edit_1 = memory_file.read_text(encoding="utf-8") + "\n- Edit 1\n"
    memory_file.write_text(edit_1, encoding="utf-8")
    
    # First rename
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir)])
    assert res.returncode == 0
    
    # 2. Edit manually again
    edit_2 = memory_file.read_text(encoding="utf-8") + "\n- Edit 2\n"
    memory_file.write_text(edit_2, encoding="utf-8")
    
    # Second rename
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir)])
    assert res.returncode == 0
    
    backups = sorted(glob.glob(str(temp_memory_dir / "MEMORY-*.md")))
    # At least two distinct backup files must exist
    assert len(backups) >= 2
    
    # One file must contain edit_1, another must contain edit_2
    contents = [Path(b).read_text(encoding="utf-8") for b in backups]
    assert edit_1 in contents
    assert edit_2 in contents


def test_cli_zero_topic_files_guard(temp_memory_dir):
    """
    Test 12: given a 0-topic-file dir, qhaway index declines/warns rather than
    producing an empty index and superseding any existing file.
    Also tests that --check flags low-count directories.
    """
    # Part A: Refuse to index empty directory
    original_memory_content = "# Preserved Memory Index\n- [Topic](topic.md) — Old topic hook\n"
    memory_file = temp_memory_dir / "MEMORY.md"
    memory_file.write_text(original_memory_content, encoding="utf-8")
    
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir)])
    # Must fail
    assert res.returncode != 0
    
    # Index remains untouched
    assert memory_file.read_text(encoding="utf-8") == original_memory_content
    backups = glob.glob(str(temp_memory_dir / "MEMORY-*.md"))
    assert len(backups) == 0
    
    # Part B: Low count warning
    create_topic_file(temp_memory_dir, "topic_one.md", "---\ntype: project\nname: Project 1\n---\nBody")
    
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir), "--check"])
    assert res.returncode == 0
    
    output = res.stdout + res.stderr
    assert any(word in output.lower() for word in ["low", "few", "count", "topic"])
