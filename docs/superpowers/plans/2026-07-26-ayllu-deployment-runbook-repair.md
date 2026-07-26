# Ayllu Deployment Runbook Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the documented Ayllu deployment rollback safe under cooperative concurrency and incapable of overwriting unknown live bytes.

**Architecture:** Replace check-then-rename recovery with a cooperatively locked critical section. Track each attempted mutation independently and permit restoration only when the current target still has the exact hash installed by this deployment; otherwise preserve the unknown bytes and rollback evidence for manual recovery.

**Tech Stack:** Bash with `set -Eeuo pipefail`, util-linux `flock`, same-filesystem `mv`, SHA-256 ownership checks, temporary-directory failure-injection harness, qhaway documentation.

## Global Constraints

- Do not mutate `/var/www/wamason.com`, the public website, or either retained backup.
- Lock file: `/home/tony/.wamason-ayllu-deploy.lock`, outside the public document root.
- Hold one non-blocking exclusive `flock` across snapshot, guards, replacement, validation, rollback or cleanup.
- A target may be restored or removed only if this deployment attempted its replacement and its current bytes equal this deployment's installed SHA-256.
- Unknown or absent current bytes after a mutation attempt must never be overwritten; retain the corresponding rollback snapshot and exit nonzero.
- A target whose mutation was never attempted must never be restored.
- The live-state snapshot and guard occur only after the cooperative lock is acquired.
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
$case_root/pending/index.html            replacement index
$case_root/pending/page.html             replacement page
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

Each case asserts exit status, exact live hashes, presence or absence of exact rollback paths, and absence of broad/glob cleanup. The fixture must be below a `mktemp -d` directory and must never reference `/var/www`.

Run:

```bash
bash .superpowers/sdd/2026-07-26-ayllu-deployment-runbook-repair/test-runbook.sh
```

Expected RED: at least `lock-contention`, `unknown-page`, or `unknown-index` fails against the current runbook, demonstrating the reported defect.

- [ ] **Step 2: Implement cooperative locking and ownership-safe rollback**

Use `apply_patch` to replace the embedded remote body. The body must follow this state machine:

```bash
set -Eeuo pipefail

exec 9>"$lock_path"
flock -n 9 || {
  printf 'deployment lock busy: %s\n' "$lock_path" >&2
  exit 75
}

page_attempted=0
index_attempted=0
ownership_conflict=0

owns_installed_bytes() {
  target=$1
  installed_sha=$2
  test -f "$target" || return 1
  test "$(sha256sum "$target" | awk '{print $1}')" = "$installed_sha"
}

rollback() {
  status=$?
  trap - ERR INT TERM HUP
  set +e

  if test "$index_attempted" = 1; then
    if owns_installed_bytes "$index_live" "$expected_index_after_sha"; then
      mv -f -- "$index_rollback" "$index_live"
    else
      ownership_conflict=1
      printf 'rollback refused unknown index bytes; evidence retained: %s\n' "$index_rollback" >&2
    fi
  fi

  if test "$page_attempted" = 1; then
    if owns_installed_bytes "$page_live" "$expected_page_sha"; then
      if test "$page_before_state" = absent; then
        rm -f -- "$page_live"
      else
        mv -f -- "$page_rollback" "$page_live"
      fi
    else
      ownership_conflict=1
      printf 'rollback refused unknown page bytes; evidence retained: %s\n' "$page_rollback" >&2
    fi
  fi

  # Remove only deployment-owned pending/check files. Preserve rollback
  # snapshots for any ownership conflict; remove a snapshot only after its
  # target was restored or when that target was never attempted.
  cleanup_owned_nonrollback_artifacts
  test "$ownership_conflict" = 0 || status=76
  test "$status" -ne 0 || status=1
  exit "$status"
}
trap rollback ERR INT TERM HUP
```

The completed body must additionally:

- accept explicit fixture-overridable `site_dir`, `lock_path`, page/index URLs, and a test failpoint argument; the production invocation supplies the exact live paths, live URLs, and `none`;
- reject any non-`none` failpoint when `site_dir=/var/www/wamason.com/ayllu`;
- validate pending files before live snapshot;
- snapshot and guard live state only after acquiring the lock;
- create rollback copies only after guards pass;
- set `page_attempted=1` immediately before the page rename and `index_attempted=1` immediately before the index rename;
- provide test-only failpoints `before-mutation`, `after-page`, `after-both`, `unknown-page`, and `unknown-index` for non-production fixture paths;
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

Expected: syntax check exits 0; all nine named cases print `PASS`; final output reports `9 passed, 0 failed`.

- [ ] **Step 4: Verify the documented production invocation without executing it**

Run a static assertion script over `docs/superpowers/plans/2026-07-26-ayllu-codex-stone.md` that requires:

```text
/home/tony/.wamason-ayllu-deploy.lock
flock -n
page_attempted=0
index_attempted=0
owns_installed_bytes
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

Stage only:

```text
docs/superpowers/plans/2026-07-26-ayllu-codex-stone.md
docs/superpowers/plans/2026-07-26-ayllu-deployment-runbook-repair.md
```

Commit with the configured signing policy:

```bash
git add docs/superpowers/plans/2026-07-26-ayllu-codex-stone.md docs/superpowers/plans/2026-07-26-ayllu-deployment-runbook-repair.md
git commit -m "docs: make Ayllu rollback ownership-safe"
git verify-commit HEAD
```

Expected: signed commit verifies; temporary harness and reports remain ignored; no remote push and no live-site mutation occurs.
