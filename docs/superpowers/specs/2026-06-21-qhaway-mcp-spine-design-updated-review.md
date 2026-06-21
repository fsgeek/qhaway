# Rigorous Design Review: Updated Qhaway MCP Spine Design

**Date:** 2026-06-21  
**Target Spec:** [2026-06-21-qhaway-mcp-spine-design.md](file:///home/tony/projects/qhaway/docs/superpowers/specs/2026-06-21-qhaway-mcp-spine-design.md)  
**Reviewer:** Gemini (Antigravity)  
**Status:** Completed Review  

This document evaluates the updated Qhaway MCP Spine Design. The spec now integrates the fourth-round review feedback (findings **G-1** through **G-8**). This final assessment reviews the refined/declined architectural tradeoffs and maps out four detailed runtime considerations to prevent edge-case loops, locks, and security vulnerabilities.

---

## Executive Summary of Findings

| ID | Category | Severity | Description | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **U-1** | Error Handling | **Major** | Rebuilding the database on query failures (`OperationalError`) risks infinite rebuild loops if the query has a syntax or structural bug. | Enforce a one-attempt flag per connection session. If a query fails after a rebuild, crash/fail loud instead of attempting another rebuild. |
| **U-2** | Concurrency | **Medium** | The spec lacks a concrete timeout threshold for database lock waiting, risking immediate failures on concurrent edits. | Pin `PRAGMA busy_timeout = 5000` (5 seconds) as the default configuration on all connections to allow concurrent readers/writers to serialize cleanly. |
| **U-3** | Portability | **Minor** | Atomic replacement of a `0444` read-only target file behaves differently on Windows than Linux, which affects future redistribution (Step 3). | Document that `os.replace` on Windows raises a `PermissionError` over a `0444` file, requiring temporary removal of the read-only attribute on that platform. |
| **U-4** | Security | **Minor** | Hostile metadata strings parsed from Markdown could crash or compromise database queries if raw string interpolation is used. | Mandate parameterized SQL queries (`?` bindings) for all SQLite commands in the model and reconciliation layers. |

---

## Evaluation of Refined Design Decisions

### 1. G-2: WAL Required, Fail Loud
The decision to make WAL mode mandatory and fail loud (rather than falling back to `TRUNCATE` or `DELETE` journal modes) is highly sound. By preventing silent mode degradation, the system ensures consistent concurrent read/write semantics across all environments. 
- *Impact on Tests:* The test case `test_unit_reconcile_sqlite_fallback` in `test_qhaway.py` must be updated to expect a loud initialization failure (a raised exception or error code) when WAL initialization is blocked, instead of verifying fallback behavior.

### 2. G-4: Deduplication without Foreign Key Cascade
Declining the `FOREIGN KEY` cascade constraint is a reasonable optimization. Because `reconcile` already performs explicit node and edge cleanup during stat comparisons, database-level cascade triggers are redundant. Avoiding global foreign key validation limits insertion constraint complexity.

---

## Detailed Findings & Recommendations

### U-1: Rebuild-on-drift Infinite Loop Risk

> [!CAUTION]
> **Issue**: The spec states: *"A schema-drift `OperationalError` is treated the same way (rebuild, don't crash)"*.
> 
> If a developer introduces a bug (e.g., a SQL syntax error, a typo in a column name, or a missing table in a query), the query execution will throw an `OperationalError`. If the connection layer catches this and blindly deletes the database and rebuilds it, the subsequent retry will execute the same buggy query, throw the same error, delete the database again, and loop infinitely.

#### Recommendation
The connection/query wrapper must protect against infinite self-healing loops. Implement a retry threshold (max 1 rebuild attempt per query invocation or session):
```python
def execute_query(conn, query, params=None):
    try:
        return conn.execute(query, params or [])
    except sqlite3.OperationalError as exc:
        if getattr(conn, "_rebuilt", False):
            # Already rebuilt once, crash to prevent infinite loop
            raise exc
        conn.close()
        rebuild_database()
        new_conn = get_connection()
        new_conn._rebuilt = True
        return new_conn.execute(query, params or [])
```

---

### U-2: Pinned Default for `busy_timeout`

> [!NOTE]
> **Issue**: In SQLite WAL mode, readers do not block writers, and writers do not block readers. However, only one writer can update the database at a time. If two writes (e.g., an MCP `remember` write and a manual CLI `reconcile` sync) execute concurrently, one will immediately raise `SQLITE_BUSY` unless a waiting timeout is configured.

#### Recommendation
Establish a default `busy_timeout` of `5000` milliseconds (5 seconds) on every connection. This allows concurrent writing processes to yield and serialize automatically without throwing immediate timeout errors:
```python
conn.execute("PRAGMA busy_timeout = 5000;")
```

---

### U-3: Windows Portability Considerations for the `0444` Fence

> [!WARNING]
> **Issue**: The `0444` read-only template replacement mechanism relies on POSIX filesystem behavior where directories govern file renaming. On Windows, renaming a file over an existing read-only file will raise a `PermissionError`, even if the containing folder is writable. This will block Step 3 (packaging for redistribution) when developers on Windows attempt to run the tool.

#### Recommendation
Add an architectural note for future Step 3 redistribution: on non-POSIX platforms, the atomic write utility should check for the target's existence and remove its read-only attribute (`os.chmod(..., stat.S_IWRITE)`) before calling `os.replace` or `shutil.move`.

---

### U-4: Parameterization Baseline in Model Layer

> [!IMPORTANT]
> **Issue**: Since topic files are edited by LLMs and humans, fields like `name`, `type`, `description`, and `body` are untrusted strings. While we use YAML parsing for isolation, executing SQLite statements using raw string concatenation (e.g., `f"INSERT INTO nodes VALUES ('{node['name']}')"`) opens the application to SQL formatting failures, escapes, and projection crashes.

#### Recommendation
Enforce a coding standard requiring parameterized placeholders (`?` markers) for all queries interacting with parsed data:
```python
conn.execute(
    "INSERT INTO nodes (file, name, body) VALUES (?, ?, ?)",
    [node["file"], node["name"], node["body"]]
)
```

---

## Verdict

The **Qhaway MCP Spine Design** has reached an exceptionally high standard of specification maturity. Once the infinite-loop rebuild safeguard (U-1) and the `busy_timeout` default (U-2) are added to the implementation plan, development can proceed with a high degree of confidence.
