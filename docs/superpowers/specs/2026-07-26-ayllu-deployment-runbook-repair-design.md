# Ayllu Deployment Runbook Repair Design

Date: 2026-07-26

## Purpose

Repair the reusable Ayllu publication runbook without changing the successfully deployed stone. The current runbook detects some concurrent index changes but can then overwrite the detected change during rollback. Recovery must never erase bytes whose ownership is unknown.

This repair serves the ayllu by making operational authority explicit: a deployment may restore only state it demonstrably replaced.

## Chosen Approach

Use a cooperative exclusive `flock` plus per-target mutation tracking and byte-ownership checks. The lock is held across snapshot, precondition checks, staging, live replacement, validation, rollback or cleanup. It lives outside the public document root and is shared by every future invocation of this runbook.

Two alternatives are rejected for this focused repair:

- A versioned release tree and single symlink swap would provide a cleaner whole-release atomic boundary, but it changes the architecture and deployment model of the entire static site.
- Check-then-write without a lock retains a race between comparison and rename and cannot safely claim concurrency protection.

The cooperative lock cannot constrain a writer that ignores it. Ownership checks therefore remain required even while the lock is held.

## Lock and Snapshot Boundary

The remote deployment opens `/home/tony/.wamason-ayllu-deploy.lock` on a dedicated file descriptor and acquires it with non-blocking `flock`. Failure to acquire the lock makes no mutation and exits nonzero.

Only after acquiring the lock may the runbook:

1. verify exact pending-file hashes;
2. verify the expected live index and page state;
3. create adjacent rollback snapshots;
4. replace live targets;
5. validate server-local and public bytes; and
6. remove deployment-owned temporary files and release the lock.

The live-state guard and snapshot occur inside the same cooperative critical section.

## Mutation Ownership

Track page and index mutations separately. A target becomes deployment-owned only after its atomic rename succeeds.

Rollback considers a target only when its mutation flag is set. Before restoring its snapshot, rollback compares the current live bytes with the exact bytes installed by this deployment:

- If they match, restoration is permitted.
- If they do not match, the runbook must not overwrite or remove them. It retains the rollback snapshot and reports an ownership conflict requiring manual recovery.
- If the deployment never replaced the target, rollback leaves it untouched.

For an originally absent page, removal is permitted only when the page mutation flag is set and the current page hash still matches the deployment's installed hash.

Rollback exits nonzero in all cases. An ownership conflict takes precedence over automatic cleanup so evidence remains available.

## Atomicity Claim

Each same-filesystem rename is atomic; the page/index pair is not. The runbook is a staged, recoverable, cooperatively serialized deployment, not a true two-file transaction. A small visibility window remains between the two renames. Eliminating it requires the rejected versioned-release/single-pointer architecture.

## Verification

The repair is documentation and executable-runbook work. Verification must include:

- shell syntax validation of the extracted remote script;
- a temporary-directory harness that exercises success, lock contention, failure before mutation, failure after page mutation, failure after both mutations, and an injected unknown-byte conflict;
- assertions that pre-mutation failures never restore, owned bytes restore, and unknown bytes survive unchanged with rollback evidence retained;
- the existing qhaway test suite;
- signed tracked commits;
- independent review of the exact fix diff.

The test harness must not touch `/var/www/wamason.com` or the public site.

## Scope

This repair changes only the tracked design/runbook documents and their validation evidence. It does not republish the stone, change the live index, alter server configuration, or remediate the separately observed public `.claude/settings.local.json` exposure.
