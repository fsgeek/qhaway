# Pre-registered expectations: does searching bodies on a miss help? (October 2026)

Written 2026-10-27, before qhaway 0.8.0 (the first version with the change)
was released. The commit that adds this file is the timestamp. The analysis is
`scripts/miss_report.py`, committed with this file. Its definitions are part
of the registration, and changing them after the data arrives needs a new,
dated registration.

## The change

Until 0.7.6, `recall(query=...)` matched every term against titles,
descriptions and filenames only. From 0.8.0, a query that matches nothing
there is run again over bodies too, and the result is still a list of index
lines. Its header says `N memories match in body text only`. If that also
matches nothing, the header is `No matching memories. Bodies were searched
too.`

## Why, and what was already seen

The usage study (docs/usage-preregistration-2026-10.md) found that 14 of 29
query recalls missed, and that every miss was followed by another query. The
author then replayed the 14 distinct missed queries against each store as it
stood at the time, dating undated memories by file modification time:

- 7 named a word that no memory contained anywhere, not even in a body.
- 4 matched in bodies, with 1 to 5 hits each.
- Any-word matching would have returned 11, 29 and 54 memories for the
  multi-word queries, which is noise rather than an answer, so it was
  rejected.
- 1 (`apacheta`) should have matched titles under the old rule as well. That
  is unexplained.

The predictions below were set from that replay. That makes them easier to
meet than predictions set blind, and this is stated here rather than hidden.

## Data

- **Source:** `events.jsonl` in every memory directory on Tony's WSL machine,
  as in the usage study, read with that study's `load()`.
- **Events counted:** `recall` events with a `header` field written by qhaway
  0.8.0 or later (`version` ≥ 0.8). A query recall is one with `query` set.
- **When to evaluate:** once there are 40 query recalls from 0.8.0+, or on
  2026-12-31, whichever comes first. Report n for every result. No interim
  looks; if one is taken, it is disclosed.

## Predictions

| # | Prediction | Threshold | Reasoning |
|---|---|---|---|
| N1 | Fewer queries come back empty. | header exactly `No matching memories. Bodies were searched too.` in ≤ 35% of query recalls (was 48%) | The replay recovered 4 of 14 misses through bodies, which gives 0.48 × 10/14 ≈ 0.34. |
| N2 | Bodies answer some queries. | header contains `in body text only` in ≥ 10% of query recalls | The same replay: 4 of 29 ≈ 14%. |
| N3 | A miss that is final is believed. | after such a miss, the session's next recall is another query in ≤ 60% of cases (was 11/11) | The old header couldn't tell "not in the titles" from "not anywhere". The new one says which, so rephrasing has less reason to happen. |

A miss on any prediction is a result. N3 is the one the replay can't inform,
and the one most likely to miss: rephrasing with a synonym is still
reasonable when a word is absent. Results go in a dated section below; this
table is not edited.

## Results

(none yet)
