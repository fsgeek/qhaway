# Codex curated-memory pilot implementation plan

> Execute inline using superpowers:executing-plans. User delegated routine
> decisions and explicitly requested no approval check-ins.

**Goal:** Provide this project with tested access to qhaway's curated memory
from local Codex, alongside khipumaq's episodic memory.

**Architecture:** Existing stdio server, explicit store, project-scoped Codex
configuration. No new persistence or native-memory integration.

**Tech stack:** Python 3.14, MCP SDK 2, uv, Codex CLI 0.159.2, TOML.

## Global constraints

Do not write synthetic memories to the live store. Preserve existing tools,
topic files, and native Codex memory. No merge or publication. Machine-specific
paths stay in local configuration and local evidence artifacts.

## Tasks

- [x] Run baseline: `uv run --group dev pytest -q`.
- [x] Exercise the real `qhaway serve --dir <temporary-store>` stdio process
  with MCP ClientSession. Check tool discovery, empty recall, two remembered
  topics, limit=0 counts, limit=1 omissions, query selection, file body access,
  supersession, and persistence after process restart. Use a decoy
  CLAUDE_PROJECT_DIR to prove the explicit store wins.
- [x] Inspect live store by calling recall through the same transport. Hash
  authoritative topic files before and after; require unchanged hashes.
- [x] Create a project-local `.codex/config.toml` entry in the original checkout
  pointing to the released qhaway server and explicit store. Use inline-index
  mode to preserve a self-contained index on this hookless client. Confirm
  discovery using `codex mcp get qhaway --json`; verify adjacent khipumaq
  configuration remains available.
- [x] Document setup, body-reading guidance, removability, findings, and limits
  in `docs/codex-memory.md`; link it from README.
- [x] Review the final changes and evidence. Commit portable documentation on
  the experiment branch; leave the main branch and releases untouched.

## Review focus

Distinguish protocol checks from actual Codex model tool use. Check the explicit
store survives cwd and environment differences; guidance preserves counts and
omissions, treats memory as revisable, and explains full-body access. Avoid
shipping personal paths. Verify installation does not activate native memories
or modify global MCP entries.

## Ledger

- Decision: share this project's existing curated store for the pilot, because
  cross-wrapper participation is the capability under examination. Cost if
  wrong: later Codex-authored memories would need review or relocation.
- Decision: no product-code change unless the pilot demonstrates a gap.

- Baseline: 186 passed, 3 skipped (optional live-store tests).
- Protocol probes: checkout and released 0.6.0 passed synthetic round trip;
  released live survey found 76 active and 12 superseded, 88 topic hashes unchanged.
- Local setup: Codex 0.159.2 recognizes qhaway; khipumaq enabled; global config
  SHA-256 unchanged. Local AGENTS.override.md supplies the store path and
  retrieval guidance; both local files are excluded via .git/info/exclude.
- Ruling: retain a portable protocol regression in tests/test_stdio_memory.py
  rather than only a throwaway probe; this makes the tested boundary repeatable.
  Cost: approximately four seconds in the test suite. No product code changed.
- Probe corrections: SDK v2 uses is_error/server_info; topic bodies preserve
  input newline formatting. Both initial failures were in the probe assumptions,
  not server failures.
- Full suite including protocol regression: 187 passed, 3 skipped in 20.00s.
- Threat-model addendum records the additional local host's access to the
  shared store and distinguishes MCP process permissions from shell sandboxing.
- Final independent review: no critical, important, or minor findings.
- Final ruling on review limits: model tool exposure/adherence, concurrent
  cross-client writes, actual removal/reinstallation, and improved outcomes
  remain untested. They are explicit pilot limits, not inferred successes;
  cost if these assumptions fail is a follow-up integration correction.
- Integration decision: preserve experiment/codex-memory-pilot and its worktree;
  no merge or push. The original checkout's local MCP configuration is active
  for discovery by a fresh Codex session. No product-code expansion was needed.
