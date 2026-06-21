# qhaway MCP spine — adversarial review findings (2026-06-21)

After the suite went 41/41 green, a multi-agent adversarial review (3 dimensions:
green-but-wrong tests, spec violations, correctness edges) surfaced 9 confirmed
findings (each verified by mutation testing or end-to-end reproduction, not
assertion). Triaged by the **ayni rule**: *does the finding degrade the QoL of a
Claude Code instance using this tool?* If yes → fixed now. If no → logged here.

## Fixed (hurt a using instance)

- **HIGH — future-version DB silently mis-stamped (model.py).** A db with
  `user_version > SCHEMA_VERSION` was not detected as drift, was silently
  re-stamped to 1, then crashed with a raw `OperationalError` on first query.
  Fix: `_schema_drifted` now treats ANY `user_version` mismatch on an existing
  nodes table as drift; `_open_wal` only stamps `user_version` on a db it
  actually created. Proven: a `user_version=5` db now rebuilds to full schema.
- **MEDIUM — slugify collapsed all non-ASCII/empty titles to "memory", silently
  dropping distinct links (reconcile.py).** `compose_topic_file` dedups on the
  slug, so distinct unicode link targets merged into one `[[memory]]` line —
  silent loss, the exact thing qhaway exists to prevent. Fix: slug keeps unicode
  word chars (`[^\w-]+` UNICODE) so distinct titles stay distinct; empty slugs
  fall back to `memory-<sha8>` not the shared constant. Proven: 日本語/中文 →
  distinct slugs, 3 distinct links survive.
- **LOW — write/read slug asymmetry (parse.py).** `reconcile.slugify`
  lowercase-hyphenated but `parse._normalize_link` did not, so hand-authored
  `[[My Cool Topic]]` was falsely reported dangling by `check`. Fix:
  `_normalize_link` now lowercases + space→hyphen (underscores preserved to keep
  the hand-authored `reference_b.md` convention). Proven.

## Deferred (do not hurt a using instance — protect future developers, not the instance)

These are real debt. Logging them so they are not silently forgotten; none blocks
the MVP because none degrades the instance's experience.

- **Test gap: `test_cli_dry_run_action` passes against a no-op `_dry_run`.** Only
  asserts returncode==0 and MEMORY.md absent; never checks stdout has a
  projection. A gutted `_dry_run` survives. Fix: assert the projected slice line
  (e.g. `[Project Title](topic.md)`) is in stdout.
- **Test gap: `test_unit_reconcile_changed_file` masked by lazy full-load.** Reads
  the DB only via `get_connection`, which rebuilds from disk when empty — so a
  fully no-op `reconcile` passes. Fix: read the db raw (not via get_connection),
  or spy on `upsert_file`/`delete_node`.
- **Test gap: `test_cli_no_silent_omissions` is a tautology.** Both shown and
  omitted counts derive from the same markdown, so their sum is always the total
  regardless of what `project_slice` renders; a `return ""` mutant passes. Fix:
  assert specific entries are actually present in the rendered markdown.
- **`execute_query_with_retry` is dead code (model.py).** The FFUP-2/U-1
  query-time drift classifier is called by nothing but its own tests; live paths
  use `conn.execute` directly. Open-time `_drifted_on_disk` is the only live
  drift handling. Decide: wire it into the query paths, or delete it +
  `_DRIFT_MARKERS` and reconcile the spec to "open-time-only drift".
- **Auto-populate commits outside reconcile's transaction (model.py/reconcile.py).**
  `get_connection`'s `_full_load` commits before `reconcile`'s `BEGIN IMMEDIATE`,
  so C-5's single-transaction invariant is violated on the first reconcile of a
  non-empty corpus. The committed state is *consistent* (same files re-read), so
  no corruption is observable — invariant debt, not data debt. Fix: open without
  auto-populate in reconcile and let `_reconcile_nodes` handle the empty db
  inside the transaction.
- **Regression tests for the 3 fixes above are not yet written.** The fixes are
  proven by throwaway reproduction; add regression tests (future-version rebuild,
  unicode slug distinctness + link survival, hand-authored spaced wikilink not
  dangling) so a future change can't silently reintroduce them.
