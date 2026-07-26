# Ayllu Deployment Runbook Repair Design

Date: 2026-07-26

## Purpose

Repair the reusable Ayllu publication runbook without changing the successfully deployed stone. The current runbook detects some concurrent index changes but can then overwrite the detected change during rollback. For cooperative participants, recovery may erase only entries created or live bytes installed by the lock holder. Hash checks also detect many noncooperative changes, but they are best-effort detection rather than an atomic ownership primitive.

This repair serves the ayllu by making operational authority explicit: a deployment may restore only state it demonstrably replaced.

## Chosen Approach

Use a cooperative exclusive `flock` plus per-entry creation tracking, per-target mutation tracking, and byte-ownership checks. Uploads first spool into a server-created, mode-0700 unique transport directory outside the document root. The lock is then held across transport validation, live-state guards, creation of every live-adjacent staging/check/snapshot entry, live replacement, validation, rollback, and cleanup. It lives outside the public document root and is shared by every future invocation of this runbook.

Two alternatives are rejected for this focused repair:

- A versioned release tree and single symlink swap would provide a cleaner whole-release atomic boundary, but it changes the architecture and deployment model of the entire static site.
- Check-then-write without a lock retains a race between comparison and rename and cannot safely claim concurrency protection.

The cooperative lock cannot constrain a writer that ignores it. Ownership hashes and entry identities therefore remain useful detection in depth, but a hash-check followed by `mv` or `rm` has an unavoidable time-of-check/time-of-use interval. The runbook makes no absolute preservation claim for writers that ignore the lock; eliminating that race requires a different atomic publication architecture.

## Lock and Snapshot Boundary

The remote deployment opens `/home/tony/.wamason-ayllu-deploy.lock` on a dedicated file descriptor and acquires it with non-blocking `flock`. Failure to acquire the lock makes no mutation and exits nonzero.

Before acquiring the lock, the workflow may only create its unique transport directory outside the document root and spool the three immutable inputs into it. It creates no adjacent pending, guard, snapshot, public-check, or HTTP-code path.

Only after acquiring the lock may the runbook:

1. verify the exact transport entries and hashes;
2. verify the expected live index and page state;
3. reject regular-file and dangling-symlink collisions for every exact live-adjacent path;
4. create adjacent pending files, guards, rollback snapshots, public checks, and HTTP-code outputs while recording creation ownership;
5. replace live targets;
6. validate server-local and public bytes; and
7. remove only deployment-owned entries and release the lock.

The live-state guard and snapshot occur inside the same cooperative critical section. The requested `site_dir` is canonicalized with `realpath`; test failpoints are rejected for the canonical production tree and all descendants, including alternate spellings and symlink aliases.

## Mutation Ownership

Track page and index mutations separately. A target becomes deployment-owned only after its atomic rename succeeds. Track creation of every transport, pending, guard, rollback, public-check, and HTTP-code entry separately; cleanup may name an entry only while its creation flag and recorded identity still establish this invocation's ownership. Any pre-existing directory entry, including a dangling symlink, is a collision. A symlink at an expected-absent live-page path is not absence and stops the deployment.

Rollback considers a target only when its mutation flag is set. Before restoring its snapshot, rollback compares the current live bytes with the exact bytes installed by this deployment:

- If they match, restoration is permitted.
- If they do not match, the runbook must not overwrite or remove them. It retains the rollback snapshot and reports an ownership conflict requiring manual recovery.
- If the deployment never replaced the target, rollback leaves it untouched.

For an originally absent page, removal is permitted only when the page mutation flag is set and the current page hash still matches the deployment's installed hash.

Rollback exits nonzero in all cases. An ownership conflict takes precedence over ordinary cleanup so evidence remains available; a restore, removal, or owned-artifact cleanup failure takes the distinct higher-priority recovery status 77 and also retains evidence.

## Atomicity Claim

Each same-filesystem rename is atomic; the page/index pair is not. The runbook is a staged, recoverable, cooperatively serialized deployment, not a true two-file transaction. A small visibility window remains between the two renames. The same architecture cannot provide an atomic compare-and-restore against an uncooperative writer. Eliminating both limitations requires the rejected versioned-release/single-pointer architecture or another genuine atomic publication primitive.

## Verification

The repair is documentation and executable-runbook work. Verification must include:

- shell syntax validation of the extracted remote script;
- a temporary-directory harness that exercises success, lock contention, failure before mutation, failure after page mutation, failure after both mutations, injected unknown or missing live bytes, signals, cleanup failures, and mixed recovery outcomes;
- assertions that transport stays outside the document root, no live-adjacent path exists before lock acquisition, the lock spans staging through success or rollback cleanup, pre-mutation failures never restore, owned bytes restore, and detected unknown bytes survive with rollback evidence retained;
- canonical production-alias rejection, inherited-`errtrace` single-rollback coverage, regular/dangling collision coverage for every exact artifact class, and explicit ordering/diagnostic assertions;
- the existing qhaway test suite;
- signed tracked commits;
- independent review of the exact fix diff.

The test harness must not touch `/var/www/wamason.com` or the public site.

## Scope

This repair changes only the tracked design/runbook documents and their validation evidence. It does not republish the stone, change the live index, alter server configuration, or remediate the separately observed public `.claude/settings.local.json` exposure.
