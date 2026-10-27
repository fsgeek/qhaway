"""Compare query recalls under qhaway 0.8.0+ with the miss-fix registration.

See docs/miss-fix-preregistration-2026-10.md. The definitions here are part of
that registration; don't change them after data arrives.

    uv run python scripts/miss_report.py [memory_dir ...]
"""
import glob
import os
import sys
from collections import defaultdict

from usage_report import DEFAULT_GLOBS, load, share

MISS = "No matching memories. Bodies were searched too."
IN_BODY = "in body text only"


def at_least_080(e):
    try:
        return tuple(int(p) for p in str(e.get("version", "")).split(".")[:2]) >= (0, 8)
    except ValueError:
        return False


def report(recalls):
    recalls = [e for e in recalls if at_least_080(e)]
    queried = [e for e in recalls if e.get("query")]
    missed = [e for e in queried if e.get("header") == MISS]
    in_body = [e for e in queried if IN_BODY in (e.get("header") or "")]
    sessions = defaultdict(list)
    for e in recalls:
        sessions[e.get("session_id")].append(e)
    after_miss = []
    for s in sessions.values():
        for a, b in zip(s, s[1:]):
            if a.get("query") and a.get("header") == MISS:
                after_miss.append(b)
    rephrased = [e for e in after_miss if e.get("query")]

    rows = [
        ("N1 query misses", share(missed, queried), lambda v: v <= 0.35, "<= 0.35"),
        ("N2 answered in body text only", share(in_body, queried), lambda v: v >= 0.10, ">= 0.10"),
        ("N3 rephrase after a miss", share(rephrased, after_miss), lambda v: v <= 0.60, "<= 0.60"),
    ]
    print(f"0.8.0+ recall events: {len(recalls)}, query recalls: {len(queried)}, sessions: {len(sessions)}")
    for name, (value, n), holds, expected in rows:
        verdict = "n/a" if value is None else ("as expected" if holds(value) else "DIFFERS")
        shown = "-" if value is None else f"{value:.2f}"
        print(f"{name:32} actual {shown:>5} ({n:>8})  expected {expected:8} {verdict}")


if __name__ == "__main__":
    dirs = sys.argv[1:] or [d for g in DEFAULT_GLOBS for d in glob.glob(os.path.expanduser(g))]
    report(load(dirs)[0])
