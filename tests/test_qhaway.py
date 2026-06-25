import os
import sys
import json
import time
import glob
import hashlib
import sqlite3
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import target package modules.
# In TDD, these will fail/raise import errors until the application skeleton is written.
try:
    import qhaway.parse as parse
    import qhaway.model as model
    import qhaway.project as project
    import qhaway.cli as cli
    import qhaway.server as server
    import qhaway.reconcile as reconcile
except ImportError:
    parse = None
    model = None
    project = None
    cli = None
    server = None
    reconcile = None


def check_modules_loaded():
    if any(m is None for m in (parse, model, project, cli, server)):
        pytest.fail(
            "qhaway modules are not implemented yet. "
            "Implement parse, model, project, cli, and server to run unit tests."
        )


# ==============================================================================
# Pytest Fixtures & Shared Helpers
# ==============================================================================

@pytest.fixture
def temp_memory_dir(tmp_path):
    """Fixture to create a clean temporary memory directory path."""
    return tmp_path


def create_topic_file(dir_path: Path, filename: str, content: str, mtime_ns: int = None):
    """Helper to create a topic file with optional manual modification time in nanoseconds."""
    file_path = dir_path / filename
    file_path.write_text(content, encoding="utf-8")
    if mtime_ns is not None:
        os.utime(file_path, ns=(mtime_ns, mtime_ns))
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


def test_unit_parse_tombstone_real_prefix_form(temp_memory_dir):
    """
    Unit Test (regression): real tombstone `name` fields are PREFIX-form redirect
    strings, e.g. "SUPERSEDED — see other.md", not the bare word "SUPERSEDED".
    """
    check_modules_loaded()

    # The REAL shape from the corpus (the whole redirect string is the name).
    superseded = create_topic_file(
        temp_memory_dir,
        "instructions_for_next_20260327.md",
        "---\n"
        "name: SUPERSEDED — see instructions_for_next_20260330.md\n"
        "type: project\n"
        "---\n"
        "Old consolidated handoff, superseded.\n",
    )
    deleted = create_topic_file(
        temp_memory_dir,
        "obsolete_note.md",
        "---\nname: DELETED — folded into project_x.md\ntype: project\n---\nGone.\n",
    )

    superseded_result = parse.parse_memory_file(str(superseded))
    deleted_result = parse.parse_memory_file(str(deleted))

    assert superseded_result["status"] == "superseded", (
        "prefix-form 'SUPERSEDED — see ...' must be detected as superseded"
    )
    assert deleted_result["status"] == "superseded", (
        "prefix-form 'DELETED — ...' must be detected as superseded"
    )


def test_unit_parse_fallback_and_tolerance(temp_memory_dir):
    """
    Unit Test: Verifies tolerance to malformed/unquoted colon frontmatter.
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
    assert "Prose content stays intact." in result["body"]
    assert result["status"] == "live"


def test_unit_model_build_index(temp_memory_dir):
    """
    Unit Test: Verifies qhaway.model.build_index (or the initial schema setup)
    generates SQLite nodes and edges schemas and populates them correctly.
    (DuckDB -> SQLite WAL migration).
    """
    check_modules_loaded()

    # Write source topic files with explicit modification times
    mtime_ns = 1753990000000000000
    create_topic_file(
        temp_memory_dir,
        "project_a.md",
        "---\ntype: project\nname: Project A\n---\nRefers to [[reference_b]]",
        mtime_ns=mtime_ns
    )
    create_topic_file(
        temp_memory_dir,
        "reference_b.md",
        "---\ntype: reference\nname: SUPERSEDED\n---\nSuperseded body",
        mtime_ns=mtime_ns
    )

    # In SQLite WAL mode, the persistent db lives at <dir>/.qhaway.db
    db_path = temp_memory_dir / ".qhaway.db"
    
    # Initialize the SQLite db via model layer helper
    conn = model.get_connection(str(temp_memory_dir))
    
    # Use fetch_nodes helper (C-2) to inspect nodes
    nodes = model.fetch_nodes(conn)
    assert len(nodes) == 2
    
    # Verify sorted nodes details
    nodes = sorted(nodes, key=lambda n: n["file"])
    
    # Node A assertions
    assert nodes[0]["file"] == "project_a.md"
    assert nodes[0]["content_type"] == "project"
    assert nodes[0]["role"] == "project"
    assert nodes[0]["status"] == "live"
    assert nodes[0]["mtime_ns"] == mtime_ns
    assert nodes[0]["size"] > 0
    
    # Node B assertions
    assert nodes[1]["file"] == "reference_b.md"
    assert nodes[1]["content_type"] == "reference"
    assert nodes[1]["status"] == "superseded"
    assert nodes[1]["mtime_ns"] == mtime_ns
    assert nodes[1]["size"] > 0
    
    # Check edges schema and content
    edges = conn.execute("SELECT src_file, dst_slug, kind FROM edges").fetchall()
    assert len(edges) == 1
    assert edges[0][0] == "project_a.md"
    assert edges[0][1] == "reference_b"
    assert edges[0][2] == "REFERENCES"
    
    # Check that indexes are created (G-4)
    indexes = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    index_names = [idx[0] for idx in indexes]
    assert any("idx_edges_dst" in name for name in index_names)
    
    conn.close()


def test_unit_project_sort_tiebreak():
    """
    Unit Test: Verifies that when all recency sorting tiers tie,
    the sorting resolves alphabetically by filename (ascending) in SQLite.
    """
    check_modules_loaded()

    # Establish an in-memory SQLite connection for testing
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE nodes (
            file TEXT PRIMARY KEY,
            name TEXT,
            content_type TEXT,
            description TEXT,
            role TEXT,
            status TEXT,
            origin_session TEXT,
            date_hint TEXT,
            body TEXT,
            mtime_ns INTEGER,
            size INTEGER
        )
        """
    )
    
    # Insert two nodes that tie on all potential recency signals:
    # Same date_hint, same origin_session, same mtime_ns
    conn.execute(
        """
        INSERT INTO nodes VALUES (
            'file_b.md', 'Node B', 'project', 'Desc', 'proj', 'live', 
            'session_1', '2026-06-20', 'Body', 1700000000000000000, 10
        )
        """
    )
    conn.execute(
        """
        INSERT INTO nodes VALUES (
            'file_a.md', 'Node A', 'project', 'Desc', 'proj', 'live', 
            'session_1', '2026-06-20', 'Body', 1700000000000000000, 10
        )
        """
    )

    # project_slice must sort alphabetically. 'file_a.md' must be listed before 'file_b.md'
    output = project.project_slice(conn, budget=1000, status="live")
    
    idx_a = output.find("file_a.md")
    idx_b = output.find("file_b.md")
    
    assert idx_a != -1 and idx_b != -1
    assert idx_a < idx_b
    conn.close()


def test_unit_reconcile_incremental_skip(temp_memory_dir):
    """
    TDD 12: Reconcile incremental skip. Given an already indexed corpus,
    a second reconcile with no file changes parses zero files.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic1.md", "---\ntype: project\nname: T1\n---\nBody 1")
    create_topic_file(temp_memory_dir, "topic2.md", "---\ntype: project\nname: T2\n---\nBody 2")
    
    # Run initial reconcile to build index
    cli.reconcile(str(temp_memory_dir))
    
    # Spy on parse_memory_file to count calls
    with patch("qhaway.parse.parse_memory_file", side_effect=parse.parse_memory_file) as mock_parse:
        cli.reconcile(str(temp_memory_dir))
        # Zero topic files should be re-parsed since they didn't change
        assert mock_parse.call_count == 0


def test_unit_reconcile_changed_file(temp_memory_dir):
    """
    TDD 13: Reconcile catches a changed topic file, and drops deleted files.
    """
    check_modules_loaded()
    
    f1 = create_topic_file(temp_memory_dir, "topic1.md", "---\ntype: project\nname: T1\n---\nBody 1")
    f2 = create_topic_file(temp_memory_dir, "topic2.md", "---\ntype: project\nname: T2\n---\nBody 2")
    
    cli.reconcile(str(temp_memory_dir))
    
    # Update topic1.md content and modification time
    time.sleep(0.01) # ensure time progression
    f1.write_text("---\ntype: project\nname: T1 New\n---\nBody 1 modified", encoding="utf-8")
    # Delete topic2.md
    f2.unlink()
    
    cli.reconcile(str(temp_memory_dir))
    
    # Connect and assert update
    conn = model.get_connection(str(temp_memory_dir))
    nodes = model.fetch_nodes(conn)
    conn.close()
    
    files = {n["file"] for n in nodes}
    assert "topic1.md" in files
    assert "topic2.md" not in files
    
    t1_node = next(n for n in nodes if n["file"] == "topic1.md")
    assert t1_node["name"] == "T1 New"
    assert "modified" in t1_node["body"]


def test_unit_reconcile_idempotence(temp_memory_dir):
    """
    TDD 14: Reconcile is idempotent on its own output (zero new backups on consecutive runs).
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: Topic\n---\nBody")
    
    # Run once to initialize redirect and sidecar
    cli.reconcile(str(temp_memory_dir))
    
    # Verify no backup created
    backups_1 = glob.glob(str(temp_memory_dir / "MEMORY-*.md"))
    assert len(backups_1) == 0
    
    # Run again without changes
    cli.reconcile(str(temp_memory_dir))
    
    backups_2 = glob.glob(str(temp_memory_dir / "MEMORY-*.md"))
    assert len(backups_2) == 0


def test_unit_reconcile_no_orphaned_edges(temp_memory_dir):
    """
    TDD 17: Node deletion leaves no orphaned edges.
    """
    check_modules_loaded()
    
    f1 = create_topic_file(temp_memory_dir, "topic_a.md", "---\ntype: project\nname: A\n---\nLinks [[topic_b]]")
    create_topic_file(temp_memory_dir, "topic_b.md", "---\ntype: project\nname: B\n---\nBody B")
    
    cli.reconcile(str(temp_memory_dir))
    
    conn = model.get_connection(str(temp_memory_dir))
    edges = conn.execute("SELECT src_file, dst_slug FROM edges").fetchall()
    assert len(edges) == 1
    assert edges[0] == ("topic_a.md", "topic_b")
    conn.close()
    
    # Delete topic_a
    f1.unlink()
    cli.reconcile(str(temp_memory_dir))
    
    conn = model.get_connection(str(temp_memory_dir))
    edges = conn.execute("SELECT src_file, dst_slug FROM edges").fetchall()
    assert len(edges) == 0
    conn.close()


def test_unit_reconcile_database_persistence(temp_memory_dir):
    """
    TDD 18: Persistent db survives across processes and rebuilds by deletion.
    G-1: Ensures WAL sidecar files are also correctly deleted during reset/deletion.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: T\n---\nBody")
    
    # Build database in one run/process connection
    conn = model.get_connection(str(temp_memory_dir))
    conn.execute("INSERT INTO nodes (file, name) VALUES ('forced.md', 'Forced')")
    conn.commit()
    conn.close()
    
    # Connect in another "process" connection session and verify it persists
    conn2 = model.get_connection(str(temp_memory_dir))
    rows = conn2.execute("SELECT name FROM nodes WHERE file='forced.md'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "Forced"
    conn2.close()
    
    # Rebuild by deletion: delete .db, .db-wal, and .db-shm (G-1)
    for ext in ("", "-wal", "-shm"):
        db_file = temp_memory_dir / f".qhaway.db{ext}"
        if db_file.exists():
            db_file.unlink()
            
    # Running reconcile must rebuild from files
    cli.reconcile(str(temp_memory_dir))
    
    conn3 = model.get_connection(str(temp_memory_dir))
    nodes = model.fetch_nodes(conn3)
    conn3.close()
    
    files = {n["file"] for n in nodes}
    assert "topic.md" in files
    assert "forced.md" not in files # Extraneous row is gone, database was rebuilt


def test_unit_remember_slug_and_role(temp_memory_dir):
    """
    TDD 15: remember slugifies title with hyphens, not underscores, and never auto-derives role.
    """
    check_modules_loaded()
    
    # Simulate remember tool execution
    # Title: "Review feedback" -> Slug stem: "review-feedback" -> Filename: "review-feedback.md"
    filename = server.remember(
        type="feedback",
        title="Review feedback",
        body="Details here",
        description=None,
        links=None,
        memory_dir=str(temp_memory_dir)
    )
    assert "review-feedback.md" in filename
    
    # Reparse the written file to check role
    node = parse.parse_memory_file(str(temp_memory_dir / "review-feedback.md"))
    assert node["role"] is None # Hyphen means no underscore role extraction prefix


def test_unit_remember_hostile_frontmatter(temp_memory_dir):
    """
    TDD 16: Frontmatter survives hostile strings via yaml.safe_dump.
    """
    check_modules_loaded()
    
    hostile_title = "Title: With Colon, \"Double Quotes\", 'Single Quotes', and\nNewline"
    hostile_desc = "Desc: With Colon and {unmatched: brace}"
    
    filename = server.remember(
        type="project",
        title=hostile_title,
        body="Hostile body",
        description=hostile_desc,
        links=None,
        memory_dir=str(temp_memory_dir)
    )
    
    # Reparse and assert values are perfectly restored
    node = parse.parse_memory_file(str(temp_memory_dir / filename))
    assert node["name"] == hostile_title
    assert node["description"] == hostile_desc


def test_unit_remember_links_normalization(temp_memory_dir):
    """
    TDD 25: remember links normalize to canonical stems.
    G-6: Spacing/formatting appends links nicely (with double newline).
    """
    check_modules_loaded()
    
    filename = server.remember(
        type="reference",
        title="Reference A",
        body="Ref body text",
        description=None,
        links=["Foo Bar", "foo-bar.md", "[[foo-bar]]"],
        memory_dir=str(temp_memory_dir)
    )
    
    file_path = temp_memory_dir / filename
    raw_content = file_path.read_text(encoding="utf-8")
    
    # Normalized links should resolve to a single canonical [[foo-bar]]
    node = parse.parse_memory_file(str(file_path))
    assert node["links"] == ["foo-bar"]
    
    # Assert double newline padding before links (G-6)
    assert "\n\n[[foo-bar]]" in raw_content or "\n\n- [[foo-bar]]" in raw_content


def test_unit_remember_links_single_string_not_exploded(temp_memory_dir):
    """
    Defect (2026-06-21, found by dogfooding via MCP): a bare-string `links` arg
    is iterated character-by-character (string-is-iterable), producing
    [[s]][[e]][[r]][[v]]... instead of one [[serve-foo]]. All prior links tests
    passed lists, so the string path the MCP boundary actually sends was uncovered.
    """
    check_modules_loaded()

    filename = server.remember(
        type="reference",
        title="String Links A",
        body="Body text",
        description=None,
        links="serve-is-wired",
        memory_dir=str(temp_memory_dir),
    )

    node = parse.parse_memory_file(str(temp_memory_dir / filename))
    # The whole string is ONE link, not one link per character.
    assert node["links"] == ["serve-is-wired"]


def test_unit_reconcile_sqlite_fallback(temp_memory_dir):
    """
    G-2: Connection establishment fails loud (raises error) if WAL journal_mode is not supported.
    """
    check_modules_loaded()
    
    # We patch sqlite3 connection execution of PRAGMA journal_mode=WAL; to fail
    class FallbackConnection(sqlite3.Connection):
        def execute(self, sql, *exec_args, **kwargs):
            if "journal_mode=WAL" in sql:
                raise sqlite3.OperationalError("Mock WAL error (e.g. filesystem shared memory unsupported)")
            return super().execute(sql, *exec_args, **kwargs)

    original_connect = sqlite3.connect
    
    def mock_connect(*args, **kwargs):
        kwargs["factory"] = FallbackConnection
        return original_connect(*args, **kwargs)
        
    with patch("sqlite3.connect", side_effect=mock_connect):
        with pytest.raises(Exception) as excinfo:
            model.get_connection(str(temp_memory_dir))
        assert "WAL" in str(excinfo.value)



def test_unit_reconcile_schema_auto_rebuild(temp_memory_dir):
    """
    G-3: Verify automatic database schema rebuild if user_version is outdated or columns drift.
    """
    check_modules_loaded()
    
    # Create outdated database with old columns
    db_path = temp_memory_dir / ".qhaway.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA user_version = 0") # old version
    conn.execute("CREATE TABLE nodes (file TEXT PRIMARY KEY, name TEXT)") # missing columns
    conn.commit()
    conn.close()
    
    # Re-connecting via model layer must trigger auto-rebuild
    conn = model.get_connection(str(temp_memory_dir))
    
    # Check that schema matches updated columns
    cursor = conn.execute("SELECT * FROM nodes")
    column_names = [col[0] for col in cursor.description]
    assert "mtime_ns" in column_names
    assert "size" in column_names
    
    user_version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert user_version > 0
    conn.close()


# ==============================================================================
# SECTION B: INTEGRATION & CLI TESTS (Process-Isolated Subprocess Runs)
# ==============================================================================

def test_cli_budget_overflow_handling(temp_memory_dir):
    """
    Test 1 / TDD 5 / TDD 8: recall (and project_slice_with_overflow) handles budget overflow gracefully.
    """
    check_modules_loaded()
    
    for i in range(10):
        content = (
            f"---\n"
            f"name: Project {i}\n"
            f"type: project\n"
            f"---\n"
            f"This is project memory number {i} containing some descriptive text.\n"
        )
        create_topic_file(temp_memory_dir, f"project_topic_{i}.md", content)
        
    # Reconcile directory first
    cli.reconcile(str(temp_memory_dir))
    
    budget = 500
    conn = model.get_connection(str(temp_memory_dir))
    
    # project_slice_with_overflow sibling check (TDD 8)
    proj_result = project.project_slice_with_overflow(conn, budget=budget)
    
    assert len(proj_result.markdown.encode("utf-8")) <= budget
    assert "not shown" in proj_result.markdown
    assert proj_result.overflow.omitted_counts["project"] > 0
    
    # Test through recall CLI query
    res = run_qhaway_cli(["serve"]) # serve starts MCP server, but we can call project slice directly
    conn.close()


def test_cli_no_silent_omissions(temp_memory_dir):
    """
    Test 2: Nothing is omitted silently — project_slice returns correct totals.
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
    # Tombstone
    create_topic_file(
        temp_memory_dir,
        "superseded_topic.md",
        "---\ntype: project\nname: SUPERSEDED\n---\nThis was superseded.\n"
    )
    
    cli.reconcile(str(temp_memory_dir))
    
    budget = 300
    conn = model.get_connection(str(temp_memory_dir))
    proj_result = project.project_slice_with_overflow(conn, budget=budget)
    content = proj_result.markdown
    conn.close()
    
    shown_projects = content.count("](project_")
    shown_references = content.count("](reference_")
    
    omitted_projects = proj_result.overflow.omitted_counts.get("project", 0)
    omitted_references = proj_result.overflow.omitted_counts.get("reference", 0)
    superseded_declared = proj_result.overflow.superseded_count
    
    assert (shown_projects + omitted_projects) == 5
    assert (shown_references + omitted_references) == 3
    assert superseded_declared == 1


def test_cli_wikilink_rot_checking(temp_memory_dir):
    """
    Test 3 / SFUP-1: qhaway check reports [[wikilinks]] pointing to missing files.
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
    create_topic_file(
        temp_memory_dir,
        "broken_one.md",
        "---\ntype: project\nname: Broken One\n---\nLinks to [[missing_target_file]]\n"
    )
    
    # Reconcile first
    cli.reconcile(str(temp_memory_dir))
    
    # Execute check subcommand (SFUP-1)
    res = run_qhaway_cli(["check", "--dir", str(temp_memory_dir)])
    
    assert res.returncode != 0
    full_output = res.stdout + res.stderr
    assert "missing_target_file" in full_output
    assert "broken_one.md" in full_output


def test_cli_tombstone_handling(temp_memory_dir):
    """
    Test 4 / TDD 6: Tombstoned nodes are excluded by default, visible in status=superseded.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "live_topic.md", "---\ntype: project\nname: Active Project\n---\nBody here\n")
    create_topic_file(temp_memory_dir, "old_project.md", "---\ntype: project\nname: SUPERSEDED\n---\nOld project body\n")
    create_topic_file(temp_memory_dir, "deleted_project.md", "---\ntype: project\nname: DELETED\n---\nDeleted project body\n")
    
    cli.reconcile(str(temp_memory_dir))
    
    conn = model.get_connection(str(temp_memory_dir))
    
    # Default slice (status=live)
    default_slice = project.project_slice(conn, budget=1000, status="live")
    assert "live_topic.md" in default_slice
    assert "old_project.md" not in default_slice
    assert "deleted_project.md" not in default_slice
    assert "2 superseded memories hidden" in default_slice
    
    # Superseded slice (status=superseded) (TDD 6)
    superseded_slice = project.project_slice(conn, budget=1000, status="superseded")
    assert "old_project.md" in superseded_slice
    assert "deleted_project.md" in superseded_slice
    assert "live_topic.md" not in superseded_slice

    conn.close()


def test_unit_stale_drift_detector_precision(temp_memory_dir):
    """A memory whose BODY announces supersession but whose `name:` was never
    rewritten to the redirect form stays status=live and silently leaks into the
    working set. _stale_drift must flag exactly those, and ONLY those: not a
    correctly-retired node (name already redirected), nor a genuinely-live node
    that merely mentions the word in passing.
    """
    check_modules_loaded()

    # The real failure shape: prior instance wrote the supersession into the body
    # (even a careful in-body header) but left name: as the live title.
    create_topic_file(
        temp_memory_dir,
        "drifted.md",
        "---\ntype: project\nname: Spine On The Goal Line\n---\n"
        "**SUPERSEDED 2026-06-21: merged into main; this body is historical.**\n",
    )
    # Correctly retired: name: already carries the redirect. Must NOT be flagged
    # (it's not drift — record and intent already agree).
    create_topic_file(
        temp_memory_dir,
        "retired.md",
        "---\ntype: project\nname: SUPERSEDED — see drifted.md\n---\n"
        "SUPERSEDED: folded elsewhere.\n",
    )
    # Genuinely live, passing mention of the concept in prose. Must NOT be flagged.
    create_topic_file(
        temp_memory_dir,
        "live.md",
        "---\ntype: project\nname: How Supersession Works\n---\n"
        "When you retire a memory the projector hides superseded nodes.\n",
    )

    cli.reconcile(str(temp_memory_dir))
    conn = model.get_connection(str(temp_memory_dir))
    try:
        drifted = {f for f, _ in cli._stale_drift(conn)}
    finally:
        conn.close()

    assert drifted == {"drifted.md"}, (
        f"detector must flag only the live-but-prose-superseded node, got {drifted}"
    )


def test_cli_stale_drift_reported_by_check(temp_memory_dir):
    """`qhaway check` must surface the live-but-prose-superseded drift loudly
    (non-zero exit, names the file), the same way it surfaces dangling links —
    turning a silent staleness leak into a visible one.
    """
    check_modules_loaded()

    create_topic_file(temp_memory_dir, "good_one.md", "---\ntype: project\nname: Good One\n---\nActive.\n")
    create_topic_file(temp_memory_dir, "filler.md", "---\ntype: project\nname: Filler\n---\nActive.\n")
    create_topic_file(
        temp_memory_dir,
        "leaky.md",
        "---\ntype: project\nname: Leaky Handoff\n---\n"
        "**SUPERSEDED 2026-06-21: this was merged; kept for history only.**\n",
    )

    cli.reconcile(str(temp_memory_dir))
    res = run_qhaway_cli(["check", "--dir", str(temp_memory_dir)])

    assert res.returncode != 0
    full_output = res.stdout + res.stderr
    assert "leaky.md" in full_output
    assert "good_one.md" not in full_output.replace("good_one.md backups", "")


def test_cli_role_filtering(temp_memory_dir):
    """
    Verifies role filtering on project projection.
    """
    check_modules_loaded()
    
    # Prefixes define roles if underscores are used: feedback_topic -> role='feedback'
    create_topic_file(temp_memory_dir, "feedback_topic.md", "---\ntype: feedback\nname: Feedback Topic\n---\nBody")
    create_topic_file(temp_memory_dir, "project_topic.md", "---\ntype: project\nname: Project Topic\n---\nBody")
    
    cli.reconcile(str(temp_memory_dir))
    
    conn = model.get_connection(str(temp_memory_dir))
    role_slice = project.project_slice(conn, budget=1000, role="feedback")
    
    assert "feedback_topic.md" in role_slice
    assert "project_topic.md" not in role_slice
    conn.close()


def test_cli_dry_run_action(temp_memory_dir):
    """
    Verifies index CLI has dry-run mode (does not alter redirect template).
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: Project Title\n---\nBody content")
    
    # index alias for reconcile runs (OQ-3). Try dry run index
    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir), "--dry-run"])
    assert res.returncode == 0
    
    # Redirect MEMORY.md should NOT exist
    assert not (temp_memory_dir / "MEMORY.md").exists()


def test_cli_filtered_index_prints_slice_without_writing(temp_memory_dir):
    """
    The omissions footer instructs `qhaway index --type <t>` to SEE memories the
    default index set aside. That command must PRINT the filtered slice to stdout
    and must NOT overwrite MEMORY.md — it is an inspection command, not a write.
    Regression: it previously fell through to the reconcile alias, ignored --type,
    printed nothing, and silently rebuilt MEMORY.md.
    """
    check_modules_loaded()

    create_topic_file(temp_memory_dir, "proj.md", "---\ntype: project\nname: Proj One\ndescription: a project hook\n---\nBody")
    create_topic_file(temp_memory_dir, "usr.md", "---\ntype: user\nname: User One\ndescription: a user hook\n---\nBody")

    res = run_qhaway_cli(["index", "--dir", str(temp_memory_dir), "--type", "project"])
    assert res.returncode == 0
    # prints the project slice
    assert "Proj One" in res.stdout
    # filtered: the user memory is not in a project-typed slice
    assert "User One" not in res.stdout
    # does NOT write/overwrite MEMORY.md (inspection, not mutation)
    assert not (temp_memory_dir / "MEMORY.md").exists()


def test_cli_machine_contract_format(temp_memory_dir):
    """
    Test 5: Emitted project slices conform to - [Title](file) — Hook pattern.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic_a.md", "---\ntype: project\nname: Title A\ndescription: Hook description A\n---\nBody A")
    
    cli.reconcile(str(temp_memory_dir))
    
    conn = model.get_connection(str(temp_memory_dir))
    content = project.project_slice(conn, budget=1000)
    conn.close()
    
    line = next(l for l in content.splitlines() if l.strip().startswith("- "))
    assert " — " in line
    prefix, hook = line.split(" — ", 1)
    assert prefix.startswith("- [Title A](topic_a.md)")
    assert hook == "Hook description A"


def test_cli_non_destructive_edit_handling(temp_memory_dir):
    """
    Test 6 & Gaps Fix Edit Backup: Non-destructive edit handling.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: user\nname: User Topic\n---\nBody")
    
    # Reconcile writes the initial template redirect to MEMORY.md
    cli.reconcile(str(temp_memory_dir))
    
    memory_file = temp_memory_dir / "MEMORY.md"
    original_content = memory_file.read_text(encoding="utf-8")
    
    # Hand-edit the redirect
    edited_content = original_content + "\nStray manual changes\n"
    os.chmod(memory_file, 0o644)
    memory_file.write_text(edited_content, encoding="utf-8")
    
    # Reconcile again -> triggers preserve
    cli.reconcile(str(temp_memory_dir))

    # The edit appended past the signature line, so the file reads as unsigned and
    # is captured (verbatim, never destroyed) under the distinguished pre-install
    # name. The record is preserved — which is the property this test guards.
    preserved = sorted(glob.glob(str(temp_memory_dir / "MEMORY-*.md"))) + (
        [str(temp_memory_dir / reconcile.PREINSTALL_NAME)]
        if (temp_memory_dir / reconcile.PREINSTALL_NAME).exists()
        else []
    )
    contents = [Path(p).read_text(encoding="utf-8") for p in preserved]
    assert edited_content in contents


def test_cli_budget_is_token_pinned():
    """
    Test 7: Default budget constant pinned to 24000.
    """
    check_modules_loaded()
    assert project.DEFAULT_BUDGET == 24000


def test_cli_idempotence_tiebreak(temp_memory_dir):
    """
    Test 8: Idempotence check with same modification times.
    """
    check_modules_loaded()
    
    fixed_mtime = 1753990000000000000
    create_topic_file(temp_memory_dir, "project_node_a.md", "---\ntype: project\nname: A\n---\nBody A", mtime_ns=fixed_mtime)
    create_topic_file(temp_memory_dir, "project_node_b.md", "---\ntype: project\nname: B\n---\nBody B", mtime_ns=fixed_mtime)
    
    cli.reconcile(str(temp_memory_dir))
    
    memory_file = temp_memory_dir / "MEMORY.md"
    first_bytes = memory_file.read_bytes()
    
    cli.reconcile(str(temp_memory_dir))
    second_bytes = memory_file.read_bytes()
    assert first_bytes == second_bytes
    
    backups = glob.glob(str(temp_memory_dir / "MEMORY-*.md"))
    assert len(backups) == 0


def test_cli_idempotence_is_pure_function_of_content_not_mtime(temp_memory_dir):
    """
    Test 8b: Derived projection slice is pure function of topic content, not mtime.
    """
    check_modules_loaded()
    
    content_a = "---\ntype: project\nname: Node A\n---\nBody A\n"
    content_b = "---\ntype: project\nname: Node B\n---\nBody B\n"

    # Save files with mtime(a) < mtime(b)
    create_topic_file(temp_memory_dir, "project_node_a.md", content_a, mtime_ns=1700000000000000000)
    create_topic_file(temp_memory_dir, "project_node_b.md", content_b, mtime_ns=1700000500000000000)

    cli.reconcile(str(temp_memory_dir))
    
    conn1 = model.get_connection(str(temp_memory_dir))
    first_projection = project.project_slice(conn1, budget=1000)
    conn1.close()

    # Update modification times in reverse order, keeping content identical
    os.utime(temp_memory_dir / "project_node_a.md", ns=(1800000500000000000, 1800000500000000000))
    os.utime(temp_memory_dir / "project_node_b.md", ns=(1800000000000000000, 1800000000000000000))

    cli.reconcile(str(temp_memory_dir))
    
    conn2 = model.get_connection(str(temp_memory_dir))
    second_projection = project.project_slice(conn2, budget=1000)
    conn2.close()

    assert first_projection == second_projection
    backups = glob.glob(str(temp_memory_dir / "MEMORY-*.md"))
    assert len(backups) == 0


def test_cli_orphan_visibility(temp_memory_dir):
    """
    Test 9 / SFUP-1: check reports orphan backups.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: P\n---\nBody")
    cli.reconcile(str(temp_memory_dir))
    
    # Create fake backups
    (temp_memory_dir / "MEMORY-20260620T120000.md").write_text("Backup 1", encoding="utf-8")
    
    res = run_qhaway_cli(["check", "--dir", str(temp_memory_dir)])
    assert res.returncode == 0
    assert "MEMORY-20260620T120000.md" in res.stdout


def test_cli_prioritized_set_not_exempt(temp_memory_dir):
    """
    Test 10: Prioritized files are also subject to budget restrictions.
    """
    check_modules_loaded()
    
    for i in range(5):
        create_topic_file(temp_memory_dir, f"user_{i}.md", f"---\ntype: user\nname: User {i}\n---\nUser body {i}")
    for i in range(5):
        create_topic_file(temp_memory_dir, f"feedback_{i}.md", f"---\ntype: feedback\nname: Feed {i}\n---\nFeed body {i}")
        
    cli.reconcile(str(temp_memory_dir))
    
    budget = 300
    conn = model.get_connection(str(temp_memory_dir))
    output = project.project_slice(conn, budget=budget)
    conn.close()
    
    assert len(output.encode("utf-8")) <= budget
    assert "user memories not shown" in output or "feedback memories not shown" in output


def test_cli_preservation_cant_self_destruct(temp_memory_dir):
    """
    Test 11: Non-destructive overwrite prevention writes sequential suffixes.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: Topic\n---\nBody")
    cli.reconcile(str(temp_memory_dir))
    
    memory_file = temp_memory_dir / "MEMORY.md"
    
    # 1. Edit manually
    edit_1 = memory_file.read_text(encoding="utf-8") + "\n- Edit 1\n"
    os.chmod(memory_file, 0o644)
    memory_file.write_text(edit_1, encoding="utf-8")
    cli.reconcile(str(temp_memory_dir))
    
    # 2. Edit manually again
    edit_2 = memory_file.read_text(encoding="utf-8") + "\n- Edit 2\n"
    os.chmod(memory_file, 0o644)
    memory_file.write_text(edit_2, encoding="utf-8")
    cli.reconcile(str(temp_memory_dir))
    
    # Both edits appended past the signature, so each reads as unsigned. The first
    # is captured under the distinguished pre-install name; the second (preinstall
    # already taken) falls back to a timestamped backup. Neither record is lost —
    # the anti-self-destruct property holds across both name patterns.
    preserved = sorted(glob.glob(str(temp_memory_dir / "MEMORY-*.md")))
    if (temp_memory_dir / reconcile.PREINSTALL_NAME).exists():
        preserved.append(str(temp_memory_dir / reconcile.PREINSTALL_NAME))
    contents = [Path(b).read_text(encoding="utf-8") for b in preserved]
    assert edit_1 in contents
    assert edit_2 in contents


def test_cli_zero_topic_files_guard(temp_memory_dir):
    """
    Test 12 / C-7: Empty-dir reconcile succeeds, check warns on low topic count.
    """
    check_modules_loaded()
    
    # Empty dir init must succeed (C-7)
    res = run_qhaway_cli(["reconcile", "--dir", str(temp_memory_dir)])
    assert res.returncode == 0
    
    # Template MEMORY.md redirect exists
    memory_file = temp_memory_dir / "MEMORY.md"
    assert memory_file.exists()
    assert "recall" in memory_file.read_text(encoding="utf-8")
    
    # qhaway check must warning about low count
    res_check = run_qhaway_cli(["check", "--dir", str(temp_memory_dir)])
    assert res_check.returncode == 0
    assert "low topic" in res_check.stderr.lower()


def test_cli_read_only_fence(temp_memory_dir):
    """
    TDD 9 / C-6: MEMORY.md read-only fence. Direct write fails; atomic replace succeeds.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: Topic\n---\nBody")
    cli.reconcile(str(temp_memory_dir))
    
    memory_file = temp_memory_dir / "MEMORY.md"
    
    # Check permissions is 0444 (read-only)
    mode = memory_file.stat().st_mode & 0o777
    assert mode == 0o444
    
    # Direct write open('w') must raise PermissionError
    with pytest.raises(PermissionError):
        with open(memory_file, 'w', encoding="utf-8") as f:
            f.write("direct edit")
            
    # Reconcile (which uses atomic replacement) must succeed and update without raising PermissionError
    # (By creating a temp file, writing it, and replacing it over MEMORY.md)
    cli.reconcile(str(temp_memory_dir))
    assert memory_file.exists()


def test_cli_redirect_cannot_truncate(temp_memory_dir):
    """
    TDD 10: Assert redirect size is well under budget.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: Topic\n---\nBody")
    cli.reconcile(str(temp_memory_dir))
    
    memory_file = temp_memory_dir / "MEMORY.md"
    content = memory_file.read_text(encoding="utf-8")
    
    # Pinned budget is 24000, template must be tiny (<700 bytes; +~83 for the in-file signature)
    assert len(content.encode("utf-8")) < 700
    assert len(content.encode("utf-8")) < project.DEFAULT_BUDGET


def test_cli_matching_redirect_but_missing_sidecar(temp_memory_dir):
    """
    TDD 22 / C-9: Matching redirect but missing sidecar.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: Topic\n---\nBody")
    cli.reconcile(str(temp_memory_dir))
    
    sidecar_file = temp_memory_dir / ".qhaway.json"
    assert sidecar_file.exists()
    
    # Delete sidecar file
    sidecar_file.unlink()
    
    # Run reconcile again. It should repair the sidecar and create ZERO backups
    cli.reconcile(str(temp_memory_dir))
    
    assert sidecar_file.exists()
    backups = glob.glob(str(temp_memory_dir / "MEMORY-*.md"))
    assert len(backups) == 0


def test_cli_serve_reconciles_once(temp_memory_dir):
    """
    TDD 19 / C-3: qhaway serve performs exactly one reconcile at startup before tools registration.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: Topic\n---\nBody")
    
    # Patch reconcile to count calls during server initialization
    with patch("qhaway.cli.reconcile", side_effect=cli.reconcile) as mock_reconcile:
        # Mock/simulate server startup
        server.initialize_server(str(temp_memory_dir))
        assert mock_reconcile.call_count == 1
        
        # Subsequent tool reads (recall) should be pure reads (no reconcile)
        server.recall(type=None, role=None, status="live", memory_dir=str(temp_memory_dir))
        assert mock_reconcile.call_count == 1


def test_cli_concurrent_remember_no_lost_body(temp_memory_dir):
    """
    TDD 20 / C-4: Concurrent same-title remember calls write distinct files (O_CREAT|O_EXCL check).
    """
    check_modules_loaded()
    
    # Define a target name to simulate concurrent requests
    title = "Concurrency test"
    
    def run_remember(thread_id, results_list):
        try:
            filename = server.remember(
                type="project",
                title=title,
                body=f"Body from thread {thread_id}",
                description=None,
                links=None,
                memory_dir=str(temp_memory_dir)
            )
            results_list.append(filename)
        except Exception as exc:
            results_list.append(exc)

    results = []
    threads = []
    
    # Spawn two concurrent threads invoking remember
    for i in range(2):
        t = threading.Thread(target=run_remember, args=(i, results))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    # Check results: both must succeed, generating two distinct files
    assert len(results) == 2
    assert all(isinstance(r, str) for r in results)
    assert results[0] != results[1]
    
    # Verify bodies in both files
    b0 = (temp_memory_dir / results[0]).read_text(encoding="utf-8")
    b1 = (temp_memory_dir / results[1]).read_text(encoding="utf-8")
    assert "Body from thread 0" in b0 or "Body from thread 1" in b0
    assert "Body from thread 0" in b1 or "Body from thread 1" in b1


def test_cli_reconcile_atomic_failure(temp_memory_dir):
    """
    TDD 21 / C-5: Reconcile commits database changes atomically inside a transaction.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic_a.md", "---\ntype: project\nname: A\n---\nBody A")
    cli.reconcile(str(temp_memory_dir))
    
    # Get initial db connection and fetch current states
    conn = model.get_connection(str(temp_memory_dir))
    initial_nodes = model.fetch_nodes(conn)
    conn.close()
    
    # Mutate files and force exception mid-update inside parse_memory_file
    create_topic_file(temp_memory_dir, "topic_a.md", "---\ntype: project\nname: A Modified\n---\nBody A modified")
    create_topic_file(temp_memory_dir, "topic_b.md", "---\ntype: project\nname: B\n---\nBody B")
    
    # Inject error during topic_b parse/upsert
    def parse_with_failure(filepath):
        if "topic_b" in filepath:
            raise RuntimeError("Simulated mid-transaction failure")
        return parse.parse_memory_file(filepath)
        
    with patch("qhaway.parse.parse_memory_file", side_effect=parse_with_failure):
        with pytest.raises(RuntimeError):
            cli.reconcile(str(temp_memory_dir))
            
    # Verify that the database rolled back completely to initial nodes state (no partial update)
    conn = model.get_connection(str(temp_memory_dir))
    current_nodes = model.fetch_nodes(conn)
    conn.close()
    
    assert len(current_nodes) == len(initial_nodes)
    assert current_nodes[0]["name"] == "A" # A was not modified partially


def test_cli_mcp_failures_structured(temp_memory_dir):
    """
    TDD 24 / C-10: Tool errors are raised as structured exceptions, not success strings.
    """
    check_modules_loaded()
    
    # Invalid type tool call must raise structured ValueError/Exception
    with pytest.raises(Exception) as excinfo:
        server.remember(
            type="invalid_type",
            title="Title",
            body="Body",
            description=None,
            links=None,
            memory_dir=str(temp_memory_dir)
        )
        
    # Unreadable directory must raise structured Exception
    with pytest.raises(Exception):
        server.recall(
            type=None,
            role=None,
            status="live",
            memory_dir="/nonexistent/directory/path/here"
        )


def test_cli_server_stderr_safety(temp_memory_dir):
    """
    G-5: Server discovery or startup failures route only to stderr, leaving stdout clean.
    """
    check_modules_loaded()
    
    # Start server CLI on an empty/nonexistent path to trigger directory discovery failure
    # Ensure stdout remains completely clean (zero protocol frames) while stderr carries failure log.
    res = run_qhaway_cli(["serve", "--dir", "/nonexistent/path/here"])
    assert res.returncode != 0
    assert len(res.stdout.strip()) == 0
    assert "memory directory is not readable" in res.stderr


def test_unit_rebuild_on_drift_bounded(temp_memory_dir):
    """
    TDD 31 / U-1: Rebuild-on-drift is bounded to at most once per operation, then fails.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: T\n---\nBody")
    cli.reconcile(str(temp_memory_dir))
    
    conn = model.get_connection(str(temp_memory_dir))
    
    # We patch model.rebuild_database (or the connection's rebuild routine)
    # to count its invocations and assert that the exception is propagated on second failure.
    with patch("qhaway.model.rebuild_database", side_effect=model.rebuild_database) as mock_rebuild:
        # Executing a query with a non-existent column should fail, trigger one rebuild,
        # try again, fail again, and raise the exception.
        with pytest.raises(sqlite3.OperationalError):
            # A query wrapper or helper that handles OperationalError
            model.execute_query_with_retry(conn, "SELECT nonexistent_column FROM nodes", str(temp_memory_dir))
        
        # Verify it attempted to rebuild exactly once, then propagated the error
        assert mock_rebuild.call_count == 1
    conn.close()


def test_cli_destructive_rebuild_serialized(temp_memory_dir):
    """
    TDD 32 / TFUP-1: Destructive rebuild is serialized via .qhaway.db.reset.lock.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: T\n---\nBody")
    cli.reconcile(str(temp_memory_dir))
    
    # We acquire the lock manually to simulate another process rebuilding
    lock_file = temp_memory_dir / ".qhaway.db.reset.lock"
    
    import fcntl
    lock_fd = open(lock_file, "a+", encoding="utf-8")
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    
    try:
        # A concurrent destructive rebuild (e.g. from version mismatch or explicit command)
        # must fail loud or timeout because it cannot acquire the lock.
        with pytest.raises(Exception) as excinfo:
            model.rebuild_database(str(temp_memory_dir))
        assert "lock" in str(excinfo.value).lower()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def test_unit_rebuild_only_on_true_drift(temp_memory_dir):
    """
    TDD 26 / FFUP-2: Rebuild fires ONLY on true drift, not on any error.
    """
    check_modules_loaded()
    
    create_topic_file(temp_memory_dir, "topic.md", "---\ntype: project\nname: T\n---\nBody")
    cli.reconcile(str(temp_memory_dir))
    
    conn = model.get_connection(str(temp_memory_dir))
    db_path = temp_memory_dir / ".qhaway.db"
    
    with patch("qhaway.model.rebuild_database", side_effect=model.rebuild_database) as mock_rebuild:
        # A syntax error is a non-drift query error. It must fail loud immediately and NOT delete/rebuild the db.
        with pytest.raises(sqlite3.OperationalError):
            model.execute_query_with_retry(conn, "SELECT * FROM nonexistent_table_syntax_error WHERE", str(temp_memory_dir))
        
        # Rebuild count should be 0, and the database file must survive on disk
        assert mock_rebuild.call_count == 0
        assert db_path.exists()
    conn.close()


