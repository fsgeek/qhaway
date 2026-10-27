# Pre-registered expectations: what memory costs a session, before and after qhaway (#76, design A)

Written 2026-10-27, before any of the data below has been extracted or seen.
The commit that adds this file is the timestamp. The analysis is
`scripts/memory_cost_report.py`, committed with this file. Its definitions are
part of the registration, and changing them after the data arrives needs a new,
dated registration.

Why: one user reported that sharing a qhaway store between Claude Code and
Codex roughly halved their API cost (#76). This design can't test that claim.
It tests the mechanism qhaway's README describes: that getting a memory back
when it's needed costs less than carrying everything, or than hunting for it
through the files. It measures bytes of memory entering a session's context,
not dollars or total tokens.

## Data

- **Source:** khipumaq's `raw` collection, the Claude Code transcripts kept
  verbatim on every host it covers. khipumaq runs the extraction (plaza seq
  148, 187), and only per-session numbers leave it, never message text.
- **Unit:** one transcript file with `isSidechain` false (a main session).
  Subagent transcripts are extracted with their parent's id and excluded from
  every prediction below.
- **Rows:** one JSON object per session, in the fields read by
  `scripts/memory_cost_report.py`:
  `session_id, parent_session_id, host, project, model, version, start, end,
  input, cache_read, cache_write_1h, cache_write_5m, output, thinking,
  qhaway_hook, instructions_logged, carry_native, carry_hook, read_bytes,
  recall_bytes`.
- **Exposure:** `qhaway_hook` is true when the transcript contains a
  `SessionStart` hook attachment (`hook_success`) whose `command` contains
  `qhaway` and whose `exitCode` is 0. The exposure is decided by the hook
  having run, not by the session's date.
- **Carry** (memory loaded at session start): `carry_native` is the UTF-8 byte
  length of the `content` of each `instructions` attachment's file entries of
  type `AutoMem` (Claude Code's own MEMORY.md load). `carry_hook` is the UTF-8
  byte length of the qhaway hook's `content`. `instructions_logged` records
  whether the transcript has any `instructions` attachment at all. Where it
  has none, the native load can't be seen, and `carry_native` is null, not 0.
- **Retrieval** (memory fetched during the session): `read_bytes` is the byte
  length of tool results from `Read` calls, or from `Bash` calls whose command
  contains the path, for any path containing `/memory/`.
  `recall_bytes` is the byte length of tool results from tools whose name ends
  in `__recall` and belongs to qhaway (`mcp__qhaway__recall` or
  `mcp__plugin_qhaway_qhaway__recall`). Retrieval is `R = read_bytes +
  recall_bytes`.
- **In scope:** sessions in projects that have memory, meaning sessions where
  `carry_native > 0`, `carry_hook > 0`, or `R > 0`. A session in a project
  with no memory says nothing about this mechanism.
- **Arms:** exposed (`qhaway_hook` true) and unexposed (false).
- **When to evaluate:** once, when khipumaq delivers the extraction. No partial
  look by anyone beforehand. Report n for every result.

## Predictions

| # | Prediction | Threshold | Reasoning |
|---|---|---|---|
| Q1 | Exposed sessions retrieve more often. | share of sessions with R > 0: exposed ≥ unexposed | qhaway's footer says what was left out and names the call that gets it, so a gap is visible. Without qhaway, a cut index fails without telling the reader what's missing. |
| Q2 | When a session retrieves, it costs less. | among sessions with R > 0, median R exposed ≤ 0.5 × median R unexposed | A recall returns index lines, a few hundred bytes each. Hunting reads whole files: one store's single-topic hunt read 43–46 KB (README). |
| Q3 | Carry fits the caps. | 100% of exposed sessions with `instructions_logged` have carry_native + carry_hook ≤ 35,000 bytes | MEMORY.md is regenerated within 25,000 bytes, and the hook is capped at 10,000 bytes (#47). A miss is a bug. |
| Q4 | Total memory cost is lower. | median (carry_native + carry_hook + R) exposed < unexposed, over sessions with `instructions_logged` in both arms | This is the claim itself: carrying less and fetching cheaply beats carrying (or hunting for) everything. |

If either arm has fewer than 20 sessions for a prediction, that prediction
is reported as "not evaluable" with its n, not as a result. Q4 is not
evaluable if the unexposed arm's transcripts don't log `instructions`, which
is likely, since the earliest such attachment seen on this machine is from
Claude Code 2.1.265 (2026-09-09). Q1 and Q2 don't depend on it.

A miss on any prediction is a result. Results go in a dated section below;
this table is not edited.

## Confounds, stated in advance

- **Store growth.** Stores were larger after qhaway than before, so there was
  more to retrieve. This biases R against the exposed arm.
- **Time.** In practice almost every unexposed session predates 2026-06-21, so
  the models, Claude Code versions, task mix and the instances' habits all
  changed alongside the exposure. Results are reported pooled and per host. A
  difference in this design is consistent with the mechanism, but it doesn't
  show qhaway caused it.
- **Survival.** The older transcripts survived only where retention or backup
  kept them (khipumaq, seq 148: 53 Claude Code files on WAM-THREADRIPPER, 479
  in the ubuntu-vm-snapshot backfill).
- **pichay excluded.** pichay's gateway trimmed context, so its sessions are no
  baseline (plaza seq 150, 187).

## Disclosures

Before writing this, the author:
- had read the README's example (43–46 KB for one topic hunt on one store),
  which set Q2's threshold;
- had looked at transcripts on this machine (all from 2026-09-09 or later, so
  all exposed) to learn their format: which attachment types exist, that
  `instructions` carries `AutoMem` entries since 2.1.265, and the qhaway hook's
  `command` string. It counted attachments by type and computed no
  distributions of carry or retrieval bytes;
- had read the text around 54 recall calls since 2026-10-01 (see the usage
  study's results) and the usage study's results themselves.

## Results

(none yet)
