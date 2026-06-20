# qhaway Test Assumptions & Design Clarifications

**Date:** 2026-06-20  
**Status:** Settled for Test Authoring  
**Companion to:** [2026-06-20-qhaway-mvp-design.md](file:///home/tony/projects/qhaway/docs/superpowers/specs/2026-06-20-qhaway-mvp-design.md) and [2026-06-20-qhaway-corpus-findings.md](file:///home/tony/projects/qhaway/docs/superpowers/specs/2026-06-20-qhaway-corpus-findings.md)

This document captures the specific design assumptions, module APIs, CLI options, database schemas, and sorting logic used to author the test suite in the absence of the application code. These decisions resolve specs ambiguities to allow independent test execution and validation.

---

## 1. Python Module API Contracts

To enable modular TDD/unit testing, the implementation is assumed to expose the following python interfaces:

### A. `qhaway.parse`
* **`parse_memory_file(filepath: str) -> dict`**
  * Parses a single topic `.md` file.
  * **Returns** a dictionary with the following keys:
    * `file` (str): The filename stem plus extension (e.g., `"project_harness.md"`). Acts as the primary key.
    * `name` (str or None): The value of frontmatter `name` if present.
    * `content_type` (str or None): The value of frontmatter `type`. Expected values include: `"project"`, `"reference"`, `"user"`, `"feedback"`.
    * `role` (str or None): Derived from the prefix of the filename (before the first underscore). For example, a file named `feedback_check.md` has `role="feedback"`. If no prefix is present or matched, defaults to `None`.
    * `status` (str): `'superseded'` if frontmatter `name` matches `"SUPERSEDED"` or `"DELETED"` (case-insensitive); otherwise, `'live'`.
    * `origin_session` (str or None): The value of frontmatter `originSessionId` or `metadata.originSessionId` if nested.
    * `date_hint` (str or None): Extracted date in `YYYYMMDD` format from filename suffix (e.g. `_20260620`) or from frontmatter if present.
    * `body` (str): The markdown body content (prose).
    * `links` (list[str]): List of target stems/slugs extracted from `[[wikilinks]]` in the body.

### B. `qhaway.model`
* **`build_index(memory_dir: str, db_path: str = ":memory:") -> duckdb.DuckDBPyConnection`**
  * Scans the `memory_dir`, processes all files, and populates a DuckDB database.
  * **Database Schema:**
    * **`nodes` table:**
      * `file` VARCHAR PRIMARY KEY
      * `name` VARCHAR
      * `content_type` VARCHAR
      * `role` VARCHAR
      * `status` VARCHAR
      * `origin_session` VARCHAR
      * `date_hint` VARCHAR
      * `body` VARCHAR
      * `mtime` DOUBLE
    * **`edges` table:**
      * `src_file` VARCHAR (FK to `nodes.file`)
      * `dst_slug` VARCHAR
      * `kind` VARCHAR (defaults to `'REFERENCES'`)
  * **Returns** the connection.

### C. `qhaway.project`
* **`project_slice(db_conn, budget: int, content_type: str = None, role: str = None, status: str = "live") -> str`**
  * Queries the database connection and returns the projected `MEMORY.md` content matching the filters under the specified `budget` (in bytes).

### D. `qhaway.cli`
* **`main(args: list[str] = None) -> int`**
  * Parses arguments and runs the commands, returning the exit code.

---

## 2. CLI Invocation Contracts

The CLI entrypoint `qhaway` is invoked as a command with subcommands and options:

* **`qhaway index [options]`**
  * Default behavior: scans the current working directory (or directory specified), builds the index, and writes/updates `MEMORY.md` and `.qhaway.json`.
  * **Options:**
    * `--budget <bytes>`: Overrides the default budget (defaults to `24000` bytes).
    * `--type <type>`: Slices/filters the index by the given content type.
    * `--role <role>`: Slices/filters the index by the given role.
    * `--status <status>`: Slices/filters the index by status (e.g. `superseded`).
    * `--check`: Run checks without modifying any files on disk. Returns `0` if all check validations pass, and a non-zero exit code (e.g., `1`) if dangling wikilinks, budget overflow, or 0 topic files are found.
    * `--dry-run`: Performs the projection and prints the output to stdout instead of writing to `MEMORY.md`.
    * `--dir <path>`: Specifies a target memory directory to run on (defaults to current directory).

---

## 3. Sorting and Totality Rules (Idempotence)

As amended by the latest design spec changes:
* **Deferred Recency Lead Tiers:** The specific precedence order of the leading recency tiers (`date_hint`, `origin_session`, `mtime`) is deferred to the build phase and is not constrained by this contract.
* **Pinned Terminal Tiebreak:** To guarantee that the sort is total and run-invariant (preventing silent (D) renames on ties), the sorting sequence must conclude with a final terminal tiebreak on `filename` ASC (lexicographical PK tiebreak).

To support testing:
* The test suite inserts files that tie on all potential recency signals (identical `date_hint`, `origin_session`, and `mtime`) and asserts that they are sorted alphabetically by filename ascending.

---

## 4. Omission Declarations and Footer Formats

The footer tracks omissions strictly and reserves space (estimated at worst-case size) *before* filling.
* **Footer formatting rules:**
  * For each omitted content type (checked against types: `project`, `reference`, `user`, `feedback`):
    `+{count} {type} memories not shown; qhaway index --type {type}`
  * For superseded/tombstone exclusions (always declared):
    `+{count} superseded memories hidden; qhaway index --status superseded`

---

## 5. Non-Destructive Edit Handling (D) & Sidecar Schema

* **Sidecar File:** `.qhaway.json`
* **Schema:**
  ```json
  {
    "version": 1,
    "last_output_hash": "sha256-hash-of-last-written-memory-md"
  }
  ```
* **Rename Rules:**
  * If `MEMORY.md` exists and `.qhaway.json` is missing (first run), or if `MEMORY.md`'s content hash does not match `last_output_hash`, it is treated as a hand-edit.
  * Before writing a new `MEMORY.md`, the old file is renamed to `MEMORY-<UTC_timestamp>.md`.
  * The timestamp format is `YYYYMMDDTHHMMSS` (e.g., `MEMORY-20260620T143000.md`).
  * If a file with that name already exists, it appends a hyphenated integer sequence, e.g., `MEMORY-20260620T143000-01.md`, checking up to `99` to prevent collision/silent overwrite.

---

## 6. Guards on Low/Zero Topic Files

* **Zero files:** If the target directory contains `0` files ending in `.md` (excluding `MEMORY.md`, `MEMORY-*.md` backups, and `.qhaway.json`), `qhaway index` will refuse to run, print a loud warning/error to stderr, and exit with code `1` without modifying the workspace.
* **Low files:** If the target directory has `1` or `2` topic `.md` files, `qhaway index --check` will succeed but output a warning indicating a low-count workspace.
