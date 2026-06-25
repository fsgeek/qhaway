# qhaway init — one-command setup design

**Date:** 2026-06-25
**Status:** design, pending sandbox validation of the dir-derivation risk (§6)

## Problem

Installing qhaway as a Claude Code plugin requires too many steps: clone the
repo, know where Claude Code stores per-project memory (a non-obvious internal
path), discover that the shipped plugin hardcodes the *wrong* path
(`${CLAUDE_PROJECT_DIR}/.claude/qhaway-memory`, which does not match where real
corpora live), hand-patch a per-project plugin copy, launch with `--plugin-dir`,
then enable inside the session. Seven steps and a workaround. The owner hit this
live as a naive first-time user and the verdict was "wtf?".

The goal is **one-command, idempotent setup that passes the "my mom installs it"
test (ayni / no-RTFM)**. This is an alpha MVP: build the smallest thing that
works; anything beyond is a PR opportunity.

## User-facing contract (the mom test)

**Install, once ever:**
```sh
uvx qhaway init
```
Prints:
```
qhaway: installed. It activates in any project that has memory;
        projects without memory are untouched.
        Remove with: uvx qhaway uninstall
```

**Use:** open Claude Code in a project as normal. If the project has memory,
qhaway delivers it at session start and writes a signed index at session end.
If not, qhaway stays silent and invisible. No `/plugin enable`, no flags, no
concept to learn.

**Uninstall, one command:**
```sh
uvx qhaway uninstall
```
Removes exactly what `init` wrote; leaves all other `~/.claude/settings.json`
content untouched; leaves each project's `MEMORY.md` as a readable static index.

**Idempotent:**
- `init` when already installed → `qhaway: already installed, nothing to do.` exit 0.
- `uninstall` when not installed → `qhaway: not installed, nothing to do.` exit 0.
- Neither ever damages existing state. The most `init` ever does on re-run is a
  no-op report; it never overwrites or invalidates.

The naive user touches two commands over the tool's whole lifecycle. The savvy
user knows the config lives in `~/.claude/settings.json` and can read it.

## Architecture

### What `init` writes

A single **tagged block** in user-scope `~/.claude/settings.json` — SessionStart
and SessionEnd hooks, plus a user-scope MCP server registration, all invoking
`uvx qhaway`. The block is tagged with a recognizable marker so `uninstall`
removes exactly it and nothing else:

```json
"hooks": {
  "SessionStart": [{ "//": "qhaway-managed — edit via qhaway init/uninstall",
    "hooks": [{ "type": "command", "command": "uvx qhaway session-start" }] }],
  "SessionEnd":   [{ "//": "qhaway-managed",
    "hooks": [{ "type": "command", "command": "uvx qhaway session-end" }] }]
}
```

The MCP registration is written to the user-scope location Claude Code reads
(exact file/key validated in the sandbox — see §6).

### Self-gating subcommands (the load-bearing decision)

The hooks call **new thin subcommands** `session-start` / `session-end`, NOT
`reconcile --dir <path>`. Each subcommand, at runtime:

1. derives the memory dir from `$CLAUDE_PROJECT_DIR` (Claude Code's per-project
   memory path — see §6),
2. checks whether that dir exists and contains topic files,
3. **no-ops cleanly (exit 0, touch nothing) if not**; otherwise runs
   reconcile/exit/serve against it.

Consequences:
- **Dormancy is free.** The user-scope hook fires in every project but does
  nothing unless that project has memory. "Does the memory dir exist with topic
  files" IS the per-project opt-in marker — no new concept, no enable step.
- **The written JSON is identical for every user** — no per-project paths baked
  into settings — which is why one user-scope install serves all projects.
- **The relic class cannot recur.** There is no hardcoded path in the config to
  go stale; `uninstall` owns removal. (Contrast: today's hand-install era left
  dead `bin/qhaway` paths scattered across four project configs.)

### Install home / removability

Shareable artifacts (if any beyond the settings block) live under
`~/.claude/qhaway/` — a tidy, self-documenting, `rm -rf`-able location that goes
away naturally if the user removes `~/.claude`. The MVP may need nothing here
beyond the uvx cache (which uv owns); the directory is reserved for cleanliness,
not pre-built speculatively.

## Idempotency mechanics

`init`:
1. Read `~/.claude/settings.json` (create if absent, preserving any existing
   content).
2. If a qhaway-managed block is already present → print "already installed",
   exit 0. **No rewrite** (unconditional overwrite was rejected as risky).
3. Else, merge the qhaway block into the existing settings non-destructively
   (preserve all other keys/hooks/servers), write atomically (temp + replace),
   print success.

`uninstall`:
1. Read settings; locate the qhaway-managed block by its marker.
2. If absent → "not installed", exit 0.
3. Else remove exactly that block, preserve everything else, write atomically,
   report what was removed. Per-project `MEMORY.md` files are left in place as
   readable static indexes (qhaway borrows, returns; never strands a broken
   redirect).

`init` and `uninstall` are one matched, reversible unit
(install-uninstall-is-one-reversible-unit ethic). The surgical settings-removal
logic ships *with* the tool rather than being a manual cleanup users discover
later — exactly the work done by hand four times on 2026-06-25.

## Error handling

- `~/.claude/settings.json` malformed/unparseable → fail loudly, touch nothing,
  tell the user the file is invalid. Never write a partial/corrupt settings file.
- `$CLAUDE_PROJECT_DIR` unset (hook invoked outside a project) → no-op exit 0.
- Derived memory dir absent or empty → no-op exit 0 (the dormancy path).
- uvx/qhaway not resolvable in a hook → the hook fails loudly per existing
  do-no-harm behavior; never writes a partial `MEMORY.md`.

## Testing

- `init` into a clean `~/.claude` → writes the tagged block; settings valid JSON.
- `init` twice → second run is a no-op, exit 0, block unchanged.
- `init` preserving pre-existing unrelated settings (other hooks/servers/keys
  survive verbatim).
- `uninstall` removes only the tagged block; unrelated settings survive.
- `uninstall` when not installed → no-op, exit 0.
- `session-start`/`session-end` with no memory dir → no-op, touch nothing.
- `session-start` with a populated memory dir → produces the expected index.
- **Dormant→active transition (the lifecycle case):** a project starts with no
  memory dir → `session-start` no-ops. Memory then appears (a topic file is
  written, or `remember()` creates the dir). The *next* `session-start` activates
  and projects correctly. Tests both ways the dir can come into being:
  - via a topic `.md` file (the tool's intended path), and
  - via a directly-written `MEMORY.md` with no topic files yet — qhaway must NOT
    treat a lone hand-written `MEMORY.md` as "populated"; the gate is *topic
    files present*, not *MEMORY.md present*. (A user/Claude writing `MEMORY.md`
    by hand in a dormant project must be snapshotted-and-preserved on first real
    activation, per the existing
    `test_user_original_is_snapshotted_then_replaced` behavior — confirm that
    path still holds when reached through `session-start` rather than `reconcile`.)
- **Gate contract divergence from existing CLI:** the current CLI treats a
  missing dir as an *error* (`cli.py`: "memory directory is not readable",
  non-zero). `session-start`/`session-end` must instead treat missing/empty as a
  clean no-op (exit 0). Test that the new subcommands do NOT inherit the
  error-on-missing behavior.
- malformed settings.json → fail loud, no write.
- Code and tests land in separate commits (authorship-separation discipline).

## Open risk (resolve in the sandbox, do not assume)

**§6 — the dir-derivation contract.** `session-start/end` must compute Claude
Code's per-project memory path from `$CLAUDE_PROJECT_DIR` the same way Claude
Code itself does (observed form:
`~/.claude/projects/<slugified-project-path>/memory`). The slug rule is CC's,
not ours, and replicating it wrong means qhaway targets the wrong/empty dir.
Two things to confirm live in the sandbox before relying on it:
1. the exact slugification CC uses (and whether CC exposes the path via an env
   var we can read instead of re-deriving), and
2. the exact user-scope file/key CC reads for an MCP server registration.

If CC exposes the memory path directly (env var or otherwise), prefer reading it
over re-deriving the slug — re-derivation is the fragile part of this design.

## Scope (MVP discipline)

In: `init`, `uninstall`, `session-start`, `session-end`, auto-derived dir,
idempotency, non-destructive settings merge.

Out (PR opportunities): `--dir` override (keep only if near-free during
implementation), per-project enable UI, marketplace distribution, migrating
existing `.claude/qhaway-memory`-style corpora.
