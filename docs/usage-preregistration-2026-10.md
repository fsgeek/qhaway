# Pre-registered expectations: how instances use recall (October 2026)

Written 2026-10-02, before any data with the fields below existed. The commit
that adds this file is the timestamp. The analysis is `scripts/usage_report.py`
(committed with this file); its metric definitions are part of the
registration and must not change after data arrives. A changed definition
needs a new, dated registration.

Why: understanding how the tools are used shows where qhaway helps and where it
doesn't. Expectations written in advance turn that into a test, because the
interesting findings are likely to be in the gap between expected and actual.

## Data

- **Source:** `events.jsonl` in every memory directory on Tony's WSL machine
  (`~/.claude/projects/*/memory`, `~/.qhaway/projects/*/memory`).
- **Events counted:** events carrying a `version` field (written by qhaway
  0.7.3 and later): `recall` events with a `header` field, and `session-start`
  events. Older events are excluded. (Amended 2026-10-02, before any 0.7.3
  event existed: the first draft let session-start events from development
  builds into the cohort. Found in an independent review.)
- **Session:** a `recall` event's `session_id`, one per MCP server process.
  Claude Code starts one server per session. Session-start runs in the hook's
  own process, so it can't be joined to a server session by id. P1 therefore
  compares counts.
- **When to evaluate:** once there are at least 30 session-start events and
  50 recall events, or on 2026-10-31, whichever comes first. Report n with
  every result.
- **Disclosure:** before writing this, the author had seen three old recall
  events (`type` unset, 340–540 characters each) and knew that the session
  writing this made no recall calls at all.

## Predictions

| # | Prediction | Threshold | Reasoning |
|---|---|---|---|
| P1 | Pulling is rare: few sessions call `recall` at all. | distinct recall sessions ÷ session-start events ≤ 0.30 | The index plus file paths carried this whole session. Instances read files directly. |
| P2 | The footer's exact calls are imitated: most recalls filter by type, with no query. | ≥ 50% of recalls have `type` set and no `query` | The footer prints `recall(type="…")` verbatim, and copying is cheaper than composing. |
| P3 | Free-text search is a minority but real. | recalls with `query`: 15–45% | The footer also names `recall(query="...")`, but a query has to be composed. |
| P4 | `limit` is rarely used, despite the instructions teaching it. | `limit` set in ≤ 10% of recalls; `limit=0` in ≤ 5% | Instructions are read once; the footer, which is in view, never shows `limit`. |
| P5 | Queries often miss. | ≥ 25% of query recalls return "No matching memories." | Queries match every term (AND) against titles and descriptions only, while agents write natural phrases. |
| P6 | Instances repeat themselves. | ≥ 10% of sessions with ≥ 2 recalls contain an exact repeat (same type, role, status, query, limit) | Context compaction and long sessions lose earlier results. |
| P7 | A miss leads to rephrasing, not giving up. | after a zero-result query, the session's next recall is another query in ≥ 60% of cases (n = misses followed by any recall) | A miss is cheap and the tool is already in hand. |
| P8 | Fetches go where the omissions are. | among type-filtered recalls, `type="project"` ≥ 60% | Project is the largest omitted type, and session-start now shows only the newest few. |
| P9 | Session-start fits the hook cap. | 100% of session-start events have `chars` ≤ 10,000 | A sanity check on #47. Any miss is a bug. |

A miss on any prediction is a result, not a failure, and gets written up with
the actual value. Results go in a dated section below; this table is not
edited.

## Results

(none yet)
