# Rigorous Design Review: Updated (again) Qhaway MCP Spine Design

**Date:** 2026-06-21  
**Target Spec:** [2026-06-21-qhaway-mcp-spine-design.md](file:///home/tony/projects/qhaway/docs/superpowers/specs/2026-06-21-qhaway-mcp-spine-design.md)  
**Reviewer:** Gemini (Antigravity)  
**Status:** Completed Review  

This document provides a rigorous review of the sixth-round updates to the Qhaway MCP Spine Design. The spec now integrates the Sixth Round resolutions (**FFUP-2**, **FFUP-1**, **U2-1**, and **U2-2**), resolving the remaining schema recovery logic and lock file lifecycle details. The design is now fully complete and production-ready.

---

## Executive Summary of Findings

| ID | Category | Severity | Description | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **U3-1** | Test Coverage | **Minor** | The test suite needs to be expanded to test the newly added **FFUP-2** constraint (rebuild only on true drift). | Implement a test case asserting that a non-drift `OperationalError` (e.g., malformed syntax) propagates directly and does NOT trigger a database file deletion/rebuild. |

---

## Analysis of Sixth Round Resolutions

### 1. FFUP-2: Narrow Rebuild Trigger (True Drift Only)
This is the keystone of the schema recovery logic. Limiting destructive rebuilds to true schema-version drift or missing columns/tables prevents masking query bugs, permission issues, or database locks (`SQLITE_BUSY`).
- *Impact on Implementation:* The `sqlite3.OperationalError` handler must inspect the exception message (or error code) to check if the failure is a drift signal (e.g. `"no such column"`, `"no such table"`) or use schema introspection. Any other database error must fail loud immediately.

### 2. FFUP-1: Named and Deferred Residual Race
The decision to document and defer the reader/writer upgrade-during-access race is pragmatically sound for an MVP. Given the single-user local filesystem nature of the memory directory and the fact that database upgrades only happen when the code itself is updated, the likelihood of a collision is negligible. Avoiding the overhead of a global shared/exclusive DB-lifecycle lock keeps the read-only and write paths fast and clean.

### 3. U2-1 and U2-2: Lock File and POSIX lock
The lock file `.qhaway.db.reset.lock` is now correctly listed in exclusions and gitignores. Specifying POSIX standard library `fcntl.flock` in a retry loop guarantees atomic serialization of destructive resets without introducing external dependencies.

---

## Verdict & Implementation Action Plan

The design specification has successfully addressed all theoretical and structural edge cases. We are ready to implement the SQLite transition and MCP server with full confidence.

### Recommended Next Steps for Tests:
1. Update [tests/test_qhaway.py](file:///home/tony/projects/qhaway/tests/test_qhaway.py) to assert both drift query failures (rebuilds once) and non-drift query failures (fails loud without deleting) as specified in **TDD 26**.
