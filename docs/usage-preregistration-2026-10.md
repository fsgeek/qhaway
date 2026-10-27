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

### 2026-10-27: evaluated at the registered stopping point, six days late

**When.** The rule ("at least 30 session-start events and 50 recall events")
was met at 2026-10-21T05:35:38Z, when the 50th recall arrived. The 30th
session-start had come on 10-09. No instance was working on qhaway between 10-20
and 10-26, so nobody evaluated it at the time. These results use only events up
to and including that 50th recall. The extra 18 recalls that arrived later are
reported separately below and don't count as results.

**Reproduce.** The metric code in `scripts/usage_report.py` is unchanged. The
cut is made outside it, by keeping recalls and session-starts with
`ts <= recalls[49]["ts"]` after sorting both by `ts`, then calling
`report(recalls, starts)` on what's left.

| # | Actual (n) | Threshold | Verdict |
|---|---|---|---|
| P1 | 0.35 (28 sessions / 80 starts) | ≤ 0.30 | differs |
| P2 | 0.12 (6/50) | ≥ 0.50 | differs |
| P3 | 0.58 (29/50) | 0.15–0.45 | differs |
| P4a | 0.68 (34/50) | ≤ 0.10 | differs |
| P4b | 0.04 (2/50) | ≤ 0.05 | as expected |
| P5 | 0.48 (14/29) | ≥ 0.25 | as expected |
| P6 | 0.10 (1/10) | ≥ 0.10 | as expected (on the threshold, n = 10) |
| P7 | 1.00 (11/11) | ≥ 0.60 | as expected |
| P8 | 0.83 (5/6) | ≥ 0.60 | as expected (n = 6) |
| P9 | 1.00 (80/80) | = 1.00 | as expected |

**What it says.** Instances don't copy the footer. Only 12% of recalls used
the `recall(type="…")` call the footer prints, while 58% wrote a query and 68%
set a `limit`, which the footer never shows. P4a's reasoning, that instructions
are read once and forgotten, was wrong: the server instructions taught `limit`
and it got used. P2's reasoning, that copying is cheaper than composing, fails
because instances arrive already holding a word to look up. Queries miss about
half the time (P5), and every miss was followed by another query (P7, 11/11).
The miss is cheap, but it isn't free. The P1 ratio is close to the threshold
and is the weakest result: it compares counts, because session-start events
can't be joined to MCP sessions.

**Not results: the full log at 2026-10-27 (68 recalls, 118 starts).** P1 is
0.30, which would read as "as expected". P2 0.10, P3 0.62, P4a 0.72 and P5
0.43 (18/42) point the same way as at the stopping point. P1 moving across its
threshold depending on when the data was cut is the reason the stopping rule
exists.

**Disclosures.**
- Three looks came before the stopping point was evaluated: 2026-10-15 at n = 35
  (P5 9/20; written to qhaway's memory, nothing changed); 2026-10-20 at n = 46
  (the session handoff); and 2026-10-26 at n = 68, by the instance writing
  this, before it applied the cut.
- Before writing this, that instance had also read the text around each
  recall call in Claude Code transcripts since 10-01 (54 calls). That is
  exploratory and was not registered. Most calls came right after the user
  invited the instance to look around, or corrected it, or right after a
  specific word appeared in the task (`P-M3`, `TurboQuant`, `PyPI`). It counts
  as a hypothesis for the next registration, not a result. Some transcripts
  appear under two project folders, so those counts include duplicates.
- Some recalls in the window came from qhaway's own development sessions.

**Consequence.** P5 holds, so the next build makes misses cheaper, measured
against a new registration written before that build ships.
