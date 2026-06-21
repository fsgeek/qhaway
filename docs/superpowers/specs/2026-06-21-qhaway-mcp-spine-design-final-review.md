# Rigorous Design Review: Final Qhaway MCP Spine Design

**Date:** 2026-06-21  
**Target Spec:** [2026-06-21-qhaway-mcp-spine-design.md](file:///home/tony/projects/qhaway/docs/superpowers/specs/2026-06-21-qhaway-mcp-spine-design.md)  
**Reviewer:** Gemini (Antigravity)  
**Status:** Completed Final Review  

This final review evaluates the fifth-round updates to the Qhaway MCP Spine Design. The specification has successfully incorporated the resolutions for **U-1** (infinite rebuild loop), **U-2** (busy_timeout), **U-4** (parameterized SQL), **TFUP-1** (destructive reset lock), and **TFUP-2** (stdout split discipline). The design is now exceptionally solid. 

This review highlights two detailed implementation parameters for the newly added rebuild lock and Git/topic exclusions.

---

## Executive Summary of Findings

| ID | Category | Severity | Description | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **U2-1** | Concurrency & Atomicity | **Medium** | The lock file `.qhaway.db.reset.lock` is missing from the list of gitignored and excluded files. | Explicitly add `.qhaway.db.reset.lock` to the generated `.gitignore` template and the `topic_files` exclusion list alongside `.qhaway.db` and its WAL sidecars. |
| **U2-2** | Implementation Detail | **Minor** | The mechanism for acquiring the cross-process lock `.qhaway.db.reset.lock` is not pinned, risking race-prone file checks. | Mandate the use of Unix standard library `fcntl.flock` (exclusive, non-blocking lock inside a retry loop with a 5-second timeout) to ensure cross-process atomicity. |

---

## Evaluation of Resolved Design Additions

### 1. U-1: Rebuild-on-drift Bounded to Once
The specification of a single-rebuild attempt constraint using a per-session `_rebuilt` flag (TDD 31) successfully mitigates the risk of infinite disk-thrashing loops caused by persistent database query bugs. This maintains the "self-healing derived view" benefit without compromising runtime stability.

### 2. TFUP-1: Destructive Rebuild Lock
Acquiring `.qhaway.db.reset.lock` (TDD 32) exclusively for the destructive rebuild path (and not during standard incremental reconciles) is an excellent compromise. It prevents the "forked reality" hazard where concurrent processes interact with unlinked files, while keeping the standard read/write paths highly concurrent and lock-free.

---

## Detailed Implementation Guidance

### U2-1: Lock File Exclusion and Gitignore

> [!IMPORTANT]
> **Issue**: The spec now lists `.qhaway.db.reset.lock` as the lock file for destructive resets. However, the files section only states: *"`.qhaway.db`/`-wal`/`-shm` are excluded from `topic_files` and gitignored"*. 
> 
> If `.qhaway.db.reset.lock` is not explicitly added to the `topic_files` scan filter, it will be skipped (because it doesn't end in `.md`), but it could still leak into packaging, index scan logs, or git commits.

#### Recommendation
Update the gitignore templates and the topic scanning filter to explicitly cover `.qhaway.db.reset.lock`:
- **Gitignore:** Add `.qhaway.db.reset.lock` to the project's default `.gitignore` configuration.
- **Exclusion:** Ensure any reset or clean-up command removes the lock file along with the database and WAL files.

---

### U2-2: Locking Mechanism Pinning (POSIX flock)

> [!NOTE]
> **Issue**: Python's standard library does not provide a cross-platform lock file primitive by default. Implementing locking via manual file checking (e.g. checking if the file exists, then writing) is vulnerable to race conditions if two processes attempt a destructive reset simultaneously.

#### Recommendation
Since Step 1 is targeted at POSIX (Linux/macOS), use standard Unix file locking via the built-in `fcntl` module:
1. Open the file `.qhaway.db.reset.lock` in append mode (`a+`).
2. Attempt to acquire an exclusive, non-blocking lock using `fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)`.
3. If it fails, sleep briefly (e.g. 0.1 seconds) and retry until a 5-second timeout is reached.
4. Keep the file descriptor open for the duration of the reset/rebuild operation, and close it when done to release the lock.
5. Do not attempt to delete the lock file after release to avoid deletion races with other processes opening it.

---

## Final Verdict

With the inclusion of the rebuild guard (U-1), the split stdout discipline (TFUP-2), and the cross-process reset serialization (TFUP-1), the **Qhaway MCP Spine Design** is complete, robust, and fully prepared for implementation.
