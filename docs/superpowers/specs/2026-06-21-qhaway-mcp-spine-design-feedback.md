# Review Feedback: Qhaway MCP Spine Design

**Date:** 2026-06-21  
**Target Spec:** [2026-06-21-qhaway-mcp-spine-design.md](file:///home/tony/projects/qhaway/docs/superpowers/specs/2026-06-21-qhaway-mcp-spine-design.md)  
**Reviewer:** Gemini (Antigravity)  
**Status:** Completed Review  

This document provides a rigorous, architectural, and implementation-oriented review of the proposed Qhaway MCP Spine Design. It identifies seven key design gaps, race conditions, or optimization opportunities and offers concrete solutions for each.

---

## Executive Summary of Findings

| ID | Category | Severity | Description | Proposed Resolution |
| :--- | :--- | :--- | :--- | :--- |
| **F-1** | Concurrency & Database Lifecycle | **Critical** | Paradox between incremental reconcile and database locking / ephemeral in-memory state. | Use a persistent `.qhaway.db` and dynamic (short-lived) connection sessions. |
| **F-2** | Schema & Naming Conflicts | **Major** | Slugification will trigger accidental automatic `role` extraction for multi-word titles. | Use hyphens for spaces in slugified titles, reserving underscores for explicit roles. |
| **F-3** | Precision & Portability | **Minor** | Float-based `mtime` check (`DOUBLE`) is prone to precision issues during comparisons. | Use integer nanosecond timestamps (`st_mtime_ns` / `BIGINT`). |
| **F-4** | Security & Input Safety | **Major** | Raw serialization of frontmatter in `remember` is vulnerable to special character corruption. | Use proper YAML serialization/quoting libraries. |
| **F-5** | Performance | **Major** | File-by-file database lookups during sweep lead to $O(N)$ database roundtrips. | Bulk-load database metadata into an in-memory dictionary for $O(1)$ lookups. |
| **F-6** | Data Integrity | **Minor** | Dropping nodes from disk deletes them from `nodes` but leaves orphaned outgoing edges. | Add a cascading delete or clear matching rows in the `edges` table. |
| **F-7** | API Signature | **Minor** | Ambiguity in how `recall` "carries" structured overflow data with `str` return type. | Define the internal python API return types vs. the external MCP string representation. |

---

## Detailed Findings & Recommendations

### F-1: The Concurrency and Database Lifecycle Paradox

> [!IMPORTANT]
> **Issue**: The current MVP uses a `:memory:` DuckDB database. The MCP Spine design wants `reconcile` to run incrementally on startup (as a CLI hook) and during `remember` (MCP).
> 
> * If the database remains `:memory:`, the database is completely lost when the CLI/startup hook exits. The MCP server must rebuild it from scratch, meaning the "startup hook" is a no-op for database sync and the MCP server cannot run an incremental stat sweep.
> * If the database is persisted to disk, DuckDB's strict concurrency model allows **only one write connection at a time**. While a process (like the running MCP server) holds the database file open for writing, other processes (like the CLI startup hook or manual commands) will fail with database lock errors.

#### Recommendation
1. **Durable File**: Store the database in a persistent file, e.g., `.qhaway.db` in the memory directory. Ensure this file is added to `.gitignore` and explicitly skipped in [topic_files](file:///home/tony/projects/qhaway/src/qhaway/model.py#L81-L92).
2. **Transient Connections**: The MCP server should not hold an exclusive, long-running connection to the database file. Instead, it should open the connection on demand, perform its query or write, and close it immediately.

---

### F-2: The Slugification and Automatic Role Derivation Conflict

> [!WARNING]
> **Issue**: The spec states: `remember` slugifies `title` → filename stem (e.g. `My Title` becomes `my_title.md`). Meanwhile, `parse.py` extracts the `role` by splitting the stem on the first underscore (`_`).
> 
> If we slugify "Review feedback" to `review_feedback.md`, the parser will automatically extract the role as `review`. For a title like "Today is Sunday", the role becomes `today`. This causes massive pollution of the `role` namespace.

#### Recommendation
Use hyphens for space replacement when slugifying titles (e.g., "Review feedback" -> `review-feedback.md`, which results in `role=None` since there is no underscore).
If a role prefix is desired, it must be explicitly prepended via an underscore prefix (e.g., `instructions_review-feedback.md`).

---

### F-3: Floating-Point Precision of `mtime` Check

> [!NOTE]
> **Issue**: The spec recommends storing `mtime` as a `DOUBLE`. Comparing floats for exact equality (`==`) across different OS/filesystem architectures can lead to subtle precision errors, causing files to be re-parsed unnecessarily.

#### Recommendation
Use integer nanoseconds (Python's `path.stat().st_mtime_ns`, stored as a `BIGINT` in DuckDB) rather than float-based epoch seconds to make the sync check robust.

---

### F-4: Frontmatter Serialization Safety in `remember`

> [!WARNING]
> **Issue**: The `remember` tool takes unstructured strings from the LLM for `title` and `description`. Concatenating them raw into markdown files will cause yaml parsing errors if they contain colons (`:`), quotes (`"` or `'`), or newlines.

#### Recommendation
Ensure that `remember` uses a safe YAML-generation utility or a robust quoting function when producing the frontmatter block, rather than writing raw strings.

---

### F-5: $O(N)$ Database Roundtrips in `reconcile` Sweep

> [!TIP]
> **Issue**: Stating every file on disk is cheap, but querying DuckDB one-by-one to look up `(mtime, size)` for each file yields $O(N)$ database roundtrips.

#### Recommendation
Perform a single query `SELECT file, mtime, size FROM nodes` to load the current DB index state into a python `dict`. Then, execute disk-to-db comparison in-memory in Python. This reduces database queries to $O(1)$ for files that didn't change.

---

### F-6: Orphaned Edges on Deleted Nodes

> [!IMPORTANT]
> **Issue**: The spec states that deleted files should result in "in-db-but-gone-from-disk -> drop the node." If we only delete from `nodes`, stale outgoing reference lines in `edges` where `src_file = ?` will persist.

#### Recommendation
Explicitly perform a cascading delete or manually run `DELETE FROM edges WHERE src_file = ?` alongside node deletion during the sync loop.

---

### F-7: `recall` Overflow Data Contract

> [!NOTE]
> **Issue**: The spec states that `recall(...) -> str` returns markdown but also "carries structured band data" for temporal dynamic banding in the future. It is unclear where this structured data is held if the return type is a flat string.

#### Recommendation
Clarify that the core `project_slice` Python function returns a structured tuple/object containing `(markdown_string, overflow_metadata)`, whereas the external MCP tool extracts the string representation.
