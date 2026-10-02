"""Compare recall usage with the pre-registered expectations.

See docs/usage-preregistration-2026-10.md. The metric definitions here are part
of that registration; don't change them after data arrives.

    uv run python scripts/usage_report.py [memory_dir ...]
"""
import glob
import json
import os
import sys
from collections import defaultdict

DEFAULT_GLOBS = ["~/.claude/projects/*/memory", "~/.qhaway/projects/*/memory"]
MISS = "No matching memories."


def load(dirs):
    recalls, starts = [], []
    for d in dirs:
        path = os.path.join(d, "events.jsonl")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("verb") == "recall" and "header" in e:
                    recalls.append(e)
                elif e.get("verb") == "session-start":
                    starts.append(e)
    recalls.sort(key=lambda e: e.get("ts", 0))
    return recalls, starts


def share(part, whole):
    return (len(part) / len(whole), f"{len(part)}/{len(whole)}") if whole else (None, "0/0")


def report(recalls, starts):
    sessions = defaultdict(list)
    for e in recalls:
        sessions[e.get("session_id")].append(e)
    typed = [e for e in recalls if e.get("type") and not e.get("query")]
    queried = [e for e in recalls if e.get("query")]
    limited = [e for e in recalls if e.get("limit") is not None]
    survey = [e for e in recalls if e.get("limit") == 0]
    missed = [e for e in queried if e.get("header") == MISS]
    multi = [s for s in sessions.values() if len(s) >= 2]
    key = lambda e: (e.get("type"), e.get("role"), e.get("status"), e.get("query"), e.get("limit"))
    repeating = [s for s in multi if len({key(e) for e in s}) < len(s)]
    after_miss = []
    for s in sessions.values():
        for a, b in zip(s, s[1:]):
            if a.get("query") and a.get("header") == MISS:
                after_miss.append(b)
    rephrased = [e for e in after_miss if e.get("query")]
    type_filtered = [e for e in recalls if e.get("type")]
    project = [e for e in type_filtered if e.get("type") == "project"]
    fits = [e for e in starts if e.get("chars", 0) <= 10_000]

    p1 = (len(sessions) / len(starts), f"{len(sessions)} sessions/{len(starts)} starts") if starts else (None, "0 starts")
    rows = [
        ("P1 recall sessions / session-starts", p1, lambda v: v <= 0.30, "<= 0.30"),
        ("P2 type-only recalls", share(typed, recalls), lambda v: v >= 0.50, ">= 0.50"),
        ("P3 query recalls", share(queried, recalls), lambda v: 0.15 <= v <= 0.45, "0.15-0.45"),
        ("P4a limit set", share(limited, recalls), lambda v: v <= 0.10, "<= 0.10"),
        ("P4b limit=0", share(survey, recalls), lambda v: v <= 0.05, "<= 0.05"),
        ("P5 query misses", share(missed, queried), lambda v: v >= 0.25, ">= 0.25"),
        ("P6 sessions with an exact repeat", share(repeating, multi), lambda v: v >= 0.10, ">= 0.10"),
        ("P7 rephrase after a miss", share(rephrased, after_miss), lambda v: v >= 0.60, ">= 0.60"),
        ("P8 project among type-filtered", share(project, type_filtered), lambda v: v >= 0.60, ">= 0.60"),
        ("P9 session-starts within 10,000", share(fits, starts), lambda v: v == 1.0, "== 1.00"),
    ]
    print(f"recall events: {len(recalls)}, sessions: {len(sessions)}, session-start events: {len(starts)}")
    for name, (value, n), holds, expected in rows:
        verdict = "n/a" if value is None else ("as expected" if holds(value) else "DIFFERS")
        shown = "-" if value is None else f"{value:.2f}"
        print(f"{name:38} actual {shown:>5} ({n:>12})  expected {expected:10} {verdict}")


if __name__ == "__main__":
    dirs = sys.argv[1:] or [d for g in DEFAULT_GLOBS for d in glob.glob(os.path.expanduser(g))]
    report(*load(dirs))
