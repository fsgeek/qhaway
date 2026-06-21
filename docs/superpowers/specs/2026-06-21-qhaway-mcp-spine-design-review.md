# Rigorous Design Review: Qhaway MCP Spine Design

**Date:** 2026-06-21  
**Target Spec:** [2026-06-21-qhaway-mcp-spine-design.md](file:///home/tony/projects/qhaway/docs/superpowers/specs/2026-06-21-qhaway-mcp-spine-design.md)  
**Reviewer:** Gemini (Antigravity)  
**Status:** Completed Review  

This review provides a rigorous evaluation of the updated Qhaway MCP Spine Design. The specification does an excellent job of consolidating prior feedback (F-1 to F-7, C-1 to C-11, FUP-1, FUP-2, and SFUP-1). This analysis focuses on the remaining edge cases, concurrency hazards, filesystem compatibility, and structural implementation details that must be pinned before development begins.

---

## Executive Summary of Findings

| ID | Category | Severity | Description | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **G-1** | Database Lifecycle | **Major** | Rebuilding the database by deleting `.qhaway.db` leaves stale WAL sidecar files (`-wal` / `-shm`), risking recovery corruption or locks. | Ensure database cleanup routines (manual or automatic) delete `.qhaway.db`, `.qhaway.db-wal`, and `.qhaway.db-shm` together. |
| **G-2** | Concurrency & Compatibility | **Major** | SQLite WAL mode requires shared memory (`shm`), which fails on certain VM shared folders, Docker mounts, or network filesystems. | Implement a graceful fallback to a traditional journal mode (e.g., `TRUNCATE`) if WAL mode initialization fails. |
| **G-3** | Schema Evolution | **Medium** | Upgrades or schema changes will cause runtime `OperationalError` queries on stale, persistent databases. | Read database schema or `PRAGMA user_version` at connection startup and automatically trigger a clean rebuild if mismatch occurs. |
| **G-4** | Indexing & Performance | **Medium** | The `edges` table lacks indexes and primary keys, leading to $O(N)$ lookup scans during `reconcile` and `check` commands. | Define a compound primary key or explicit indexes on `edges(src_file)` and `edges(dst_slug)`. |
| **G-5** | MCP Protocol Safety | **Medium** | Severe protocol violations if `qhaway serve` fails loud by writing arbitrary text or stack traces to `stdout` instead of `stderr`. | Mandate that all non-protocol errors, initialization issues, and directory discovery failures are printed only to `stderr` and exit non-zero. |
| **G-6** | Link Formatting & Appending | **Minor** | Appending `links` raw to the topic file body without proper newline padding can lead to text formatting corruption. | Define a clean formatting boundary (e.g., double newline padding) before appending `[[slug]]` references. |
| **G-7** | Suffix Loop Termination | **Minor** | The slug collision loop lacks a hard termination condition, risking infinite execution if directories are locked or full. | Enforce a hard loop limit (e.g., 100 attempts) on the exclusive topic file creation suffix loop, raising a tool error if exceeded. |
| **G-8** | Encoding Guard | **Minor** | Implicit OS encoding defaults on file reads/writes can lead to encoding/decoding crashes or silent data corruption. | Enforce `encoding="utf-8"` explicitly across all reading, writing, and parsing operations. |

---

## Detailed Findings & Recommendations

### G-1: WAL Sidecar Leftovers on Database Rebuilds

> [!IMPORTANT]
> **Issue**: The spec states: *"Rebuildable by deletion: `rm .qhaway.db` and the next reconcile rebuilds it from the files"*.
> 
> When SQLite runs in WAL (Write-Ahead Logging) mode, it creates two auxiliary files: `.qhaway.db-wal` and `.qhaway.db-shm`. If a user or script deletes only the primary `.qhaway.db` file, the next time SQLite opens a connection, it may attempt to recover using the stale `-wal` file, leading to potential database corruption, lock failures, or silent errors.

#### Recommendation
Update the database teardown and reset specifications to ensure that **all three database files** are deleted together:
```bash
rm -f .qhaway.db .qhaway.db-wal .qhaway.db-shm
```
Any Python cleanup helper or CLI command implementing a reset must use a pattern that cleans up these sidecar paths.

---

### G-2: Concurrency & File System Compatibility (WAL Failures)

> [!WARNING]
> **Issue**: SQLite's WAL mode utilizes a shared-memory file (`.db-shm`) to coordinate concurrent access between readers and writers. This shared memory requires support for memory-mapped files (`mmap`). 
> 
> Many developer environments run inside Docker, virtual machines (Vagrant, VirtualBox, WSL), or use network mount directories (NFS, SMB, CIFS). On these platforms, `mmap` operations on shared folders often fail with a `disk I/O error`, `database is locked`, or `operation not supported` exception, rendering WAL mode unusable.

#### Recommendation
When establishing the SQLite database connection, attempt to enable WAL mode, but provide a graceful fallback to a traditional rollback journal (e.g., `TRUNCATE` or `DELETE`) if WAL mode raises an exception or fails:
```python
try:
    conn.execute("PRAGMA journal_mode=WAL;")
except sqlite3.OperationalError:
    # Fallback for filesystems that do not support shared-memory mapping
    conn.execute("PRAGMA journal_mode=TRUNCATE;")
```
This ensures developers working in containerized or shared folder environments do not experience sudden initialization failures.

---

### G-3: Schema Evolution & Self-Healing Migration

> [!NOTE]
> **Issue**: Unlike the MVP's ephemeral `:memory:` DuckDB instance, the spine uses a persistent database file. If column definitions are modified in future releases (e.g., adding facets, custom metadata, or search tokens), existing persistent databases will cause `sqlite3.OperationalError: no such column` errors during queries.

#### Recommendation
Avoid complex migration tooling by leveraging the fact that the database is a purely derived view:
1. Store a schema version in the database using `PRAGMA user_version`.
2. Upon connection, check the `user_version`.
3. If the version is outdated (or database initialization fails due to column drift), automatically close the connection, delete the `.db` files, and re-initialize a fresh schema.

---

### G-4: Indexing and Primary Keys for Edge Relationships

> [!TIP]
> **Issue**: In the original DuckDB schema, the `edges` table was defined without primary keys or indexes:
> ```sql
> CREATE TABLE edges (
>     src_file VARCHAR,
>     dst_slug VARCHAR,
>     kind VARCHAR
> )
> ```
> While this is sufficient for small lists, incremental reconciles and dangling link inspections will perform frequent lookup scans (e.g., `DELETE FROM edges WHERE src_file = ?` and `SELECT src_file, dst_slug FROM edges`). On a growing corpus, this leads to $O(N)$ tables scans for every modified file.

#### Recommendation
Optimize lookups and prevent duplicate references by introducing a composite primary key or explicit indexes in SQLite:
```sql
CREATE TABLE edges (
    src_file TEXT NOT NULL,
    dst_slug TEXT NOT NULL,
    kind TEXT NOT NULL,
    PRIMARY KEY (src_file, dst_slug, kind),
    FOREIGN KEY (src_file) REFERENCES nodes (file) ON DELETE CASCADE
);
CREATE INDEX idx_edges_dst ON edges (dst_slug);
```
*Note: If foreign keys are used, ensure `PRAGMA foreign_keys = ON;` is executed on every database connection, as SQLite disables foreign key enforcement by default.*

---

### G-5: MCP Protocol Safety on Startup Failures

> [!IMPORTANT]
> **Issue**: The spec states: *"serve requires explicit resolution and fails loud if the chain is empty"*.
> 
> In the Model Context Protocol (MCP), the client communicates with the server via standard input (`stdin`) and standard output (`stdout`). If the server experiences an initialization failure (such as failure to find the memory directory) and prints errors, traces, or warning strings directly to `stdout`, it will corrupt the JSON-RPC stream, causing the client IDE (like Claude Code) to crash or report an unhelpful connection error.

#### Recommendation
The server initialization routine must enforce strict partition of output streams:
1. Any error message, directory resolution failure, or stack trace must be written exclusively to `sys.stderr`.
2. The process must exit with a non-zero code.
3. `sys.stdout` must be reserved strictly for JSON-RPC messages and must not be touched during initialization.

---

### G-6: Spacing and Formatting of Appended Links in `remember`

> [!NOTE]
> **Issue**: The `remember` tool accepts an optional array of `links` and appends them as `[[slug]]` text. If the user-supplied `body` does not end with a trailing newline, appending the links raw will join them directly onto the last line of prose (e.g., `...this is the final sentence[[my-linked-node]]`), causing formatting issues and potential parsing failures.

#### Recommendation
Define a clean append contract. Before appending links, ensure there is adequate spacing:
1. Rstrip the body content to remove trailing spaces/newlines.
2. Append a double newline `\n\n` followed by the links, each formatted on its own line (or formatted as list items, if preferred). For example:
   ```python
   formatted_links = "\n".join(f"[[{link}]]" for link in normalized_links)
   full_body = f"{body.rstrip()}\n\n{formatted_links}\n"
   ```

---

### G-7: Suffix Loop Guard on Title Collision

> [!WARNING]
> **Issue**: To prevent overwriting files during slug collisions, `remember` uses an exclusive create (`O_CREAT|O_EXCL`) inside a suffix loop. If there are write permission errors, filesystem loops, or an unexpected collision loop bug, a simple `while True:` loop can hang the process indefinitely.

#### Recommendation
Limit the search space for name collision suffixes. Set a strict limit (e.g., 100 attempts) and fail loud if a unique filename cannot be found:
```python
for suffix in range(1, 100):
    candidate = f"{base}-{suffix}.md"
    # Attempt atomic creation
    ...
else:
    raise RuntimeError("Could not allocate a unique topic filename after 100 attempts.")
```

---

### G-8: Enforcing UTF-8 Encoding Globally

> [!TIP]
> **Issue**: File write and read operations in Python default to the system locale encoding (e.g., `cp1252` on Windows or variable encodings on POSIX). Since memory topic files contain LLM-generated text (including emojis, smart quotes, and non-ASCII punctuation), relying on implicit system defaults will result in intermittent `UnicodeDecodeError` or `UnicodeEncodeError` exceptions.

#### Recommendation
Mandate that all file I/O operations (reading topic files, writing `MEMORY.md`, writing the sidecar, and loading backups) explicitly set `encoding="utf-8"`:
```python
with open(filepath, 'w', encoding='utf-8') as f:
    ...
```

---

## Verdict & Action Plan

The **Qhaway MCP Spine Design** is highly sound, pragmatically scoped, and ready for implementation once these guidelines are addressed. 

### Recommended Next Steps:
1. Run the **Spike** to confirm Linux behavior of atomic replaces on `0444` files.
2. Incorporate the fallback transaction rules (G-2) and the WAL cleanup checklist (G-1) into `reconcile.py` / `model.py`.
3. Proceed with building the SQLite transition and the two MCP endpoints.
