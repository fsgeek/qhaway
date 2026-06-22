# qhaway as a Claude Code plugin — design spec

Status: design converged 2026-06-22 (session with Tony). All three lifecycle
gates verified (see Verifications). Ready to turn into an execution plan.

**This spec supersedes `docs/install-subcommand-behavior.md`.** That document
described a hand-built `qhaway install`/`uninstall` that mutates the user's
Claude config (`.mcp.json`, `settings.local.json`) with surgical merges, a
marker, and reversible edits. That entire apparatus is RETIRED: the Claude Code
plugin system already owns install/enable/disable/uninstall lifecycle safely.
See [[install-uninstall-is-one-reversible-unit-the-respect-ethic]] for what was
retired and why.

## Why a plugin (the "F" decision)

The product's customer is Claude Code. The job is "deliver the must-not-re-learn
memory set reliably at boot" — verified unreliable as a model-driven pull (~50%,
see [[hook-is-mandatory-not-optional-pull-is-unreliable-enough-to-coerce]]), so a
SessionStart hook force-pushes it. A plugin is the right vehicle because it ships
ALL the wiring as harness-managed components instead of as config we mutate by
hand:

- `hooks/hooks.json` — SessionStart (push) + SessionEnd (exit), same format as
  settings.json hooks.
- `.mcp.json` (plugin root) — the recall/remember MCP server.
- `bin/qhaway` — the binary the hooks call; on PATH while the plugin is enabled.
  Resolves the no-separate-pip-install, no-uvx-cold-start problem.

Enable → all active. Disable/uninstall → all removed, by the harness, via
`/plugin` or `claude plugin disable|uninstall`. `defaultEnabled: false` ships it
OFF so the user opts into the auto-executing hook (the doc's own example use case
for that flag is "plugins that add cost/scope a user should opt into").

The memory directory is per-project, derived at runtime from
`${CLAUDE_PROJECT_DIR}` (verified available to plugin hooks as both a
substitution var and an env var). Convention: `${CLAUDE_PROJECT_DIR}/.claude/
qhaway-memory/`. One plugin, installed once, works in every project — no
hardcoded paths, no per-project config step.

## What remains "by hand" / residual

Almost nothing. The plugin subsumes install/uninstall/enable/disable. The only
per-project action is the FIRST reconcile of a project's memory dir, and that is
folded into the SessionStart hook (reconcile-then-deliver), so enabling the
plugin is the whole setup. (Open perf question — see Open issues #1.)

## The MEMORY.md state machine

`MEMORY.md` is a DERIVED artifact. Topic files are truth. Any derived artifact
must be reproducible from the files; re-deriving must be idempotent (this is
qhaway's founding invariant, now extended across enable/disable boundaries).

qhaway BORROWS `MEMORY.md` while enabled and RETURNS a current honest index when
it leaves. It must always be able to tell ITS OWN output apart from a user's
file. That identity test is an **in-file signature** (see Verification 1 —
currently sidecar-only; moving it in-file is a build item).

### SessionStart hook (load-bearing; guaranteed to run while enabled)

Classify `MEMORY.md` by its in-file signature, then:

1. **No signature → it's an original.** Atomically (backup-FIRST, then write):
   snapshot it to a durable backup as the restore source, then generate the
   signed projection/redirect. Ordering is mandatory: never write the signed
   file until the snapshot is durably on disk, so "signed file exists" always
   implies "backup exists."
2. **Signature present, content matches last output → ours, unchanged.** Rebuild
   from the DB (reconcile). Backup untouched.
3. **Signature present, content differs → ours, hand-edited.** Preserve the edit
   as a timestamped `MEMORY-<ts>.md` (existing `_heal_redirect` behavior), then
   regenerate. Never silently clobber a human's edit to our file.

Then deliver the projection to context via the hook's STDOUT (verified: plugin
SessionStart stdout injects into context). reconcile-then-deliver in one hook.

### SessionEnd hook (the disable-restore path)

On clean session end, write the **current** signed static index — a projection
of the CURRENT database (the old "index option", resurrected in its correct
role). NOT a restore of the stale install-time original. Rationale: between
install and disable, the agent accumulated memory via remember(); restoring the
stale snapshot would silently discard everything learned — the exact
lie-by-omission qhaway exists to prevent. The exit file is current + honest
(declared-omissions footer) + self-sufficient (no running qhaway needed) +
signed (so a re-enable recognizes it as ours, not an original to snapshot).

This is what makes DISABLE restore correctly: SessionStart stops firing after
disable, so the disable path can only be guarded at SessionEnd. Verified
(Verification 2) that SessionEnd STILL FIRES after a mid-session disable (plugin
hook state is read at session start and held for the session's life; disabling
mid-session does not tear down already-loaded hooks). So SessionEnd-restore
covers both quit-then-disable AND disable-mid-session.

**Conditional exit (values call, default below):** if the snapshotted original
was genuinely HAND-AUTHORED (a human's record, no prior qhaway/auto-memory
signature), restore IT rather than overwriting with our projection — ours is not
a human's record. If the original was machine-generated or absent, write the
current projection. Same did-it-pre-exist-and-whose signal the snapshot carries,
extended one notch.

### Crash resilience

SessionEnd may not fire (kill -9 / OOM / power loss). That is fine: correctness
does NOT depend on SessionEnd. The next SessionStart sees its own signature
(case 2/3), knows the backup is the true original, and rebuilds. Self-correcting
forward at the next start. The ONLY irreducible corner is crash-then-disable-
without-re-enabling: nothing of ours runs. Covered by the clearly-named backup
sitting recoverable on disk next to the redirect.

### Disable → edit → enable

Just reconcile-at-both-edges. Enable does NOT trust the DB or the MEMORY.md it
finds; it reconciles against the TOPIC FILES. reconcile is already idempotent
(upsert keyed on (mtime_ns, size); delete vanished; preserve hand-edits), so the
DB is resilient to the same material reloaded — DO NOT clean-then-rebuild
(destructive, buys nothing over upsert). The one case needing a true rebuild —
schema drift across a version bump during the disable window — is already handled
separately by existing schema-drift detection.

## Verifications (all passed, 2026-06-22)

1. **Signature in-file vs sidecar.** CURRENT CODE: sidecar-only
   (`.qhaway.json` `last_output_hash`); `REDIRECT_TEMPLATE` has NO in-file
   marker. DECISION: move signature IN-FILE (Tony's argument: two files makes the
   crash-atomicity the signature exists to provide harder; one atomic write =
   file self-describes; lost sidecar + surviving MEMORY.md currently
   misclassifies our output as an original). This is a BUILD ITEM, not a
   move — add an in-file signature to redirect + exit-projection, and rework
   classify/heal to read it from the file. Sidecar may remain as a secondary
   record but no longer sole identity.
2. **SessionEnd after mid-session disable.** PASSES — see SessionEnd section.
   (plugins-reference: "Disabling a plugin mid-session does not stop monitors
   already running; they stop when the session ends"; hook/component changes need
   /reload-plugins or restart to take effect — session holds startup state.)
3. **Plugin SessionStart stdout injects into context.** PASSES. Plugin hooks
   "respond to the same lifecycle events as user-defined hooks", same format,
   same execution; SessionStart raw stdout → context (verified on the hooks page
   earlier this session). No carve-out for plugin hooks.

## Design-shaping discoveries (from verification, fold into execution plan)

- **`InstructionsLoaded` hook event exists** — "fires when a CLAUDE.md or
  `.claude/rules/*.md` is loaded into context, at session start and on lazy load."
  POSSIBLE better/additional delivery point than SessionStart stdout, and bears
  on whether pushed memory lands as ambient context vs instruction-tier. Evaluate
  in execution planning; do not assume.
- **A plugin CANNOT ship a CLAUDE.md** — "A CLAUDE.md at the plugin root is NOT
  loaded as project context; ship instructions via a SKILL." So the
  "instruction-tier reinforcement is stronger than the redirect" lever, if
  wanted, comes via a bundled SKILL, not a CLAUDE.md. The CLAUDE.md path is dead.

## Retired by this spec

- `qhaway install` / `uninstall` as config-mutating CLI verbs (the surgical merge
  into settings.local.json/.mcp.json, the self-identifying marker for excision,
  the reversible MEMORY.md exit logic driven by our own uninstall code). The
  harness owns this now. `docs/install-subcommand-behavior.md`'s SAFE core
  (create memory dir, reconcile, heal redirect) survives — folded into the
  SessionStart hook's first-touch path. Its config-wiring half is gone.

## Open issues (for execution planning, not blocking the spec)

1. **reconcile-on-every-SessionStart cost** on a governance-sized corpus (110+
   files). Cheap at 12 memories; maybe not at 110+. Needs measurement before
   "reconcile every boot" is treated as settled — may need incremental/cached.
2. **`InstructionsLoaded` vs SessionStart** as the delivery point (above).
3. **Exit-default when original was hand-authored** — restore-original vs
   write-current-projection. Leaning: restore a HUMAN's hand-crafted file;
   project for machine/absent. Confirm with Tony.

## Test target

Governance — the PRIMARY motivating corpus (110 files, 37KB, currently
overflowing, pure auto-memory). It is qhaway's acceptance criterion, not a
fixture: the real test is whether the budgeted projection keeps the EXPENSIVE
negative-result memories resident (governance is 0%-dated → ranking falls to
origin/mtime → recency, NOT cost-of-rediscovery — the unproven heart). Deploy via
`claude --plugin-dir ./qhaway-plugin` for a one-session, flag-removable trial;
back up governance's memory dir AND its MEMORY.md (the file uninstall must be able
to return) before running. Separate the two verdicts: "did it deploy/restore
safely" (mechanical) vs "did it keep the RIGHT memories" (the ranking question,
possibly yanantin's domain — see below).

## Boundary with yanantin

When the must-not-re-learn set EXCEEDS the budget (more learned dead-ends than fit
in ~24.4KB), that is a different problem — queryable access to non-resident
knowledge (ranked retrieval, BM25). That belongs in YANANTIN, not qhaway. qhaway
= the budget FLOOR (truthful, under-budget, declares omissions). BM25 in qhaway
is premature AND mis-homed; record it as yanantin's job.