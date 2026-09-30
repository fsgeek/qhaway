# Codex installation implementation plan

Execute inline, per user's standing authorization.

- [x] Add failing setup/CLI tests for init --host codex --project/--dir,
  independent defaults, ownership refusal, exact preservation, and removal.
- [x] Add isolated codex_setup module using tomllib, checksummed block,
  atomic replacement, and project lock. Wire flags without changing Claude defaults.
- [x] Test then improve MCP instructions with absolute topic root and bounded,
  evidence-conscious use guidance, without editing agent instructions files.
- [x] Run full suite and installed-wheel smoke test without API credentials.
- [x] Document setup/removal, limitations, threat boundary, and changelog.
- [x] Independent review; fix important findings; commit tests separately from
  source. Preserve branch for review; do not merge or release.

Review focus: user-edit preservation, no native-memory/Claude config writes,
store selection across projects, serialized config updates, TOML namespace
conflicts and line endings, platform compatibility, no model API credentials.

## Execution evidence

- Initial CLI tests: 13 failed, one passed before adding the host flags; then
  14 passed. Extended preservation/path tests brought the feature suite to 22.
- Handshake root regression failed against the old instructions, then passed
  with the configured absolute root in initialization instructions.
- Independent review found two important isolation gaps: project aliases could
  target global Codex config; a default-store symlink could enter native memory.
  Four new regressions failed, then passed after resolving both destinations
  and rejecting global-config aliases and aliased .codex directories.
- The review's manual-removal documentation ambiguity was clarified in the
  same documentation pass. No findings remain deferred.
- Final full suite: 213 passed, 3 optional live-store skips.
- Installed-wheel init/repeat init/MCP read-write/uninstall/preservation smoke
  passed locally. CI runs that check on Linux, macOS, and Windows without model
  credentials. Native Codex CLI recognized generated config under trusted
  repository ancestry; uninstall restored its prior discovery result. An
  external temporary project was not trusted merely by a CLI config override;
  no persistent trust settings were changed.
- Ruling: the existing locked PyJWT 2.13.0 failed the required security audit
  with ten advisories. Updated only that transitive lock entry to 2.15.1; audit
  then reported no known vulnerabilities and the suite passed. This necessary
  CI repair is a separate commit; cost is testing a newer compatible dependency.
- Bandit and zizmor passed. No model API keys were created or used.
- Review limits retained: a fresh model's long-term behavior and concurrent
  external config editors are not established by these checks. qhaway's lock
  coordinates its own installers, not unrelated editors.
- Integration decision: open a draft PR to run platform CI and provide the
  planned Claude review surface. Do not merge, release, or replace the user's
  active manual pilot configuration while they are away.
- Platform CI caught a smoke-test assertion comparing a Windows short TEMP
  path against the server's resolved path. The product's path normalization was
  correct; the smoke assertion now uses Path.resolve(), like the stdio test.
  Initial CI: six jobs passed, Windows wheel failed at that assertion.

## Claude review, 2026-09-30

- Removed inline-index from Codex configuration. The stdio test now consumes
  managed launch arguments and verifies Claude's redirect survives Codex
  startup, writes, and restart; it failed with the previous payload.
- Uninstall removes zero-byte config and empty .codex directories, preserving
  other files. Locks persist under ~/.qhaway/locks, outside the project.
  Directory creation/removal is inside that lock to avoid races.
- A previously empty config is treated as absent, as proposed in the review.
  External-lock aliases into native memory are refused even with a custom store.
- Handshake recognizes feedback as standing user guidance while asking for
  attribution/evidence checks and respecting current instruction priority.
- Five regression cases failed before these changes; the targeted suite now
  passes 29 tests. Full suite: 215 passed, 3 skipped. Installed-wheel smoke
  and Bandit pass locally.
