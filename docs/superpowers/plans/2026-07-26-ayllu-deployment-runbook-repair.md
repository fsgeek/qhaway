# Ayllu Deployment Runbook Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the documented Ayllu deployment rollback ownership-safe for cooperative lock participants, detect noncooperative interference where the Bash/filesystem boundary permits, and state the remaining time-of-check/time-of-use limit honestly.

**Architecture:** Replace check-then-rename recovery with a cooperatively locked critical section. Track every created entry and attempted mutation independently. For cooperative participants, permit restoration only when the current target still has the exact hash installed by this deployment; preserve detected unknown bytes and rollback evidence for manual recovery, while documenting the noncooperative check/rename race.

**Tech Stack:** Bash with `set -Eeuo pipefail`, util-linux `flock`, same-filesystem `mv`, SHA-256 ownership checks, temporary-directory failure-injection harness, qhaway documentation.

## Global Constraints

- Do not mutate `/var/www/wamason.com`, the public website, or either retained backup.
- Lock file: `/home/tony/.wamason-ayllu-deploy.lock`, outside the public document root.
- Hold one non-blocking exclusive `flock` across snapshot, guards, replacement, validation, rollback or cleanup.
- A cooperative target may be restored or removed only if this deployment attempted its replacement and its current bytes equal this deployment's installed SHA-256.
- Detected unknown or absent current bytes after a mutation attempt are not overwritten; retain the corresponding rollback snapshot and exit nonzero. These checks are best-effort for a writer that ignores `flock` because the hash check and later `mv`/`rm` are not one atomic primitive.
- A target whose mutation was never attempted must never be restored.
- Pre-lock transport spooling may occur only in a server-created unique directory outside the document root. Every live-adjacent stage, snapshot, guard, validation output, mutation, rollback, and cleanup occurs only after the cooperative lock is acquired.
- Continue to describe the page/index pair as staged, recoverable, and cooperatively serialized—not transactional or pair-atomic.
- Preserve the exact public stone and index bytes already deployed.
- The separately observed public `.claude/settings.local.json` exposure remains out of scope.

---

### Task 1: Repair and Prove the Reusable Runbook

**Files:**
- Modify: `docs/superpowers/plans/2026-07-26-ayllu-codex-stone.md`
- Create temporarily: `.superpowers/sdd/2026-07-26-ayllu-deployment-runbook-repair/runbook-under-test.sh`
- Create temporarily: `.superpowers/sdd/2026-07-26-ayllu-deployment-runbook-repair/test-runbook.sh`

**Interfaces:**
- Consumes: the unsafe remote Bash body currently embedded in the Ayllu stone publication plan.
- Produces: a documented remote deployment body with cooperative locking, per-target mutation ownership, safe rollback, and executable failure-path evidence.

- [ ] **Step 1: Extract the current remote body and write RED failure tests**

Create the plan-specific ignored SDD workspace. Extract the code between the publication plan's `REMOTE` heredoc markers into `runbook-under-test.sh`.

Use `apply_patch` to create `test-runbook.sh`. Its isolated fixture must create:

```text
$case_root/site/index.html              original index
$case_root/site/stone/index.html        original page, when the case requires one
$case_root/.wamason-ayllu-transport.*/   server-created transport spool
$case_root/lock                           cooperative lock
```

The harness supplies fixture paths and expected hashes to the extracted body and replaces network validation with a fixture-local `curl` shim. It runs these cases in separate directories:

1. `success`: both targets become replacement bytes; no pending or rollback artifacts remain.
2. `lock-contention`: another process holds the lock; command exits nonzero and every target/hash remains original.
3. `fail-before-mutation`: injected failure before either rename; both targets remain original and no restore is attempted.
4. `fail-after-page`: failure after page replacement but before index attempt; page restores, index is untouched.
5. `fail-after-both`: failure after both replacements; both restore.
6. `unknown-page`: after page replacement, inject different page bytes before failure; unknown page survives, original page rollback snapshot remains, index is untouched.
7. `unknown-index`: after both replacements, inject different index bytes before failure; unknown index survives, its rollback snapshot remains; page restores only if its live bytes still equal this deployment's installed page hash.
8. `originally-absent-page`: after installing into an absent page path, failure removes it only while its bytes equal the installed page hash.
9. `unknown-originally-absent-page`: after installing into an absent path, inject unknown bytes; failure preserves the page and evidence.

Each case asserts exit status, exact live hashes, presence or absence of exact rollback paths, and absence of broad/glob cleanup. Add deterministic coverage for canonical production aliases/descendants, inherited `SHELLOPTS=errtrace`, signal rollback, full lock lifetime through success and rollback cleanup, regular and dangling collisions for every transport/pending/guard/rollback/public-check/HTTP-code path, dangling absent-page state, validation ordering, missing current targets, cleanup failure status 77, and mixed conflict/recovery-failure precedence. Fixtures stay below `mktemp -d`; production-alias tests use only canonicalization and never create or mutate `/var/www`.

Run:

```bash
bash .superpowers/sdd/2026-07-26-ayllu-deployment-runbook-repair/test-runbook.sh
```

Expected RED: at least `lock-contention`, `unknown-page`, or `unknown-index` fails against the current runbook, demonstrating the reported defect.

- [ ] **Step 2: Implement cooperative locking and ownership-safe rollback**

Use `apply_patch` to replace the embedded remote body. The body must follow this state machine:

```bash
set -Eeuo pipefail
set +E

site_dir=$(realpath -m -- "$site_dir_input")
reject_failpoint_for_canonical_production_tree

exec 9>"$lock_path"
flock -n 9 || {
  printf 'deployment lock busy; transport retained at %s\n' "$transport_dir_input" >&2
  exit 75
}

page_attempted=0
index_attempted=0
ownership_conflict=0
recovery_failure=0
page_pending_created=0
index_pending_created=0
index_guard_created=0
page_rollback_created=0
index_rollback_created=0
page_public_check_created=0
index_public_check_created=0
page_code_output_created=0
index_code_output_created=0

owns_installed_bytes() {
  require_owned_regular_hash "$1" "$2"
}

cleanup_owned_file() {
  remove_only_if_created_and_same_identity "$@"
}

rollback() {
  status=$1
  trap - ERR INT TERM HUP
  set +e

  restore_only_attempted_targets_with_matching_installed_hashes
  cleanup_owned_nonrollback_artifacts
  remove_only_owned_and_no-longer-needed_rollback_evidence
  if test "$recovery_failure" = 1; then status=77
  elif test "$ownership_conflict" = 1; then status=76
  fi
  test "$status" -ne 0 || status=1
  exit "$status"
}
trap 'rollback "$?"' ERR
trap 'signal_rollback HUP 129' HUP
trap 'signal_rollback INT 130' INT
trap 'signal_rollback TERM 143' TERM

validate_owned_transport_entries
guard_live_index_and_page
reject_all_regular_and_dangling_artifact_collisions
create_and_record_live_adjacent_stages_checks_codes_and_snapshots
repeat_index_and_page_guards_immediately_before_mutation
```

The completed body must additionally:

- accept explicit fixture-overridable `site_dir`, `lock_path`, page/index URLs, and a test failpoint argument; the production invocation supplies the exact live paths, live URLs, and `none`;
- canonicalize `site_dir` with `realpath` and reject any non-`none` failpoint for the canonical production tree or a descendant;
- validate the three exact regular, non-symlink transport entries before live snapshot;
- create every live-adjacent path only after locking, reject both regular and dangling collisions, and record a creation flag plus entry identity for exact cleanup;
- snapshot and guard live state only after acquiring the lock;
- create rollback copies only after guards pass;
- set `page_attempted=1` immediately before the page rename and `index_attempted=1` immediately before the index rename;
- provide fixture-only failure/signal points for the named matrix; all are forbidden for canonical production paths;
- invoke both public `curl` calls directly in the parent shell and write HTTP codes to owned exact paths rather than fallible command substitutions;
- remove a rollback snapshot after successful restoration, or after successful deployment validation and cleanup;
- retain exact rollback snapshots involved in an ownership conflict;
- release the lock automatically when the process exits.

Do not use unresolved globs, recursive deletion, or restore operations based only on an “exists” check.

- [ ] **Step 3: Run the failure matrix to GREEN**

Run:

```bash
bash -n .superpowers/sdd/2026-07-26-ayllu-deployment-runbook-repair/runbook-under-test.sh
bash .superpowers/sdd/2026-07-26-ayllu-deployment-runbook-repair/test-runbook.sh
```

Expected: syntax checks exit 0; all 53 focused cases print `PASS`; final output reports `53 passed, 0 failed`.

- [ ] **Step 4: Verify the documented production invocation without executing it**

Run a static assertion script over `docs/superpowers/plans/2026-07-26-ayllu-codex-stone.md` that requires:

```text
/home/tony/.wamason-ayllu-deploy.lock
flock -n
page_attempted=0
index_attempted=0
owns_installed_bytes
set +E
realpath -m
rollback refused unknown page bytes
rollback refused unknown index bytes
```

It must also assert the production invocation passes `none` as its failpoint and that no command in the remote body contains `rm -rf`, an unexpanded `*`, or the word `transactional`.

Expected: `production runbook structure valid`.

- [ ] **Step 5: Run repository verification**

Run:

```bash
git diff --check
uv sync --locked --group dev
uv run --no-sync pytest -q
curl --fail --silent --show-error --location --output /dev/null --write-out '%{http_code}\n' https://wamason.com/ayllu/
curl --fail --silent --show-error --location --output /dev/null --write-out '%{http_code}\n' https://wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/
```

Expected: clean diff; locked sync succeeds; `134 passed, 3 skipped`; two `200` responses. These public requests are read-only and prove the repair did not alter availability.

- [ ] **Step 6: Commit the tracked repair**

Stage only the tracked spec and plans changed by the final repair:

```text
docs/superpowers/plans/2026-07-26-ayllu-codex-stone.md
docs/superpowers/plans/2026-07-26-ayllu-deployment-runbook-repair.md
docs/superpowers/specs/2026-07-26-ayllu-deployment-runbook-repair-design.md
```

Commit with the configured signing policy:

```bash
git add docs/superpowers/plans/2026-07-26-ayllu-codex-stone.md docs/superpowers/plans/2026-07-26-ayllu-deployment-runbook-repair.md
git commit -m "docs: make Ayllu rollback ownership-safe"
git verify-commit HEAD
```

Expected: signed commit verifies; temporary harness and reports remain ignored; no remote push and no live-site mutation occurs.
