"""Compare memory cost per session with and without qhaway against the registration.

See docs/memory-cost-preregistration-2026-10.md. The definitions here are part
of that registration; don't change them after data arrives.

    python scripts/memory_cost_report.py sessions.jsonl
"""
import json
import statistics
import sys

MIN_N = 20
CARRY_CAP = 35_000


def load(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def retrieval(r):
    return (r.get("read_bytes") or 0) + (r.get("recall_bytes") or 0)


def in_scope(r):
    if r.get("parent_session_id"):
        return False
    return (r.get("carry_native") or 0) > 0 or (r.get("carry_hook") or 0) > 0 or retrieval(r) > 0


def carry(r):
    return (r.get("carry_native") or 0) + (r.get("carry_hook") or 0)


def report(rows):
    rows = [r for r in rows if in_scope(r)]
    arms = {True: [r for r in rows if r.get("qhaway_hook")], False: [r for r in rows if not r.get("qhaway_hook")]}
    exp, unexp = arms[True], arms[False]
    print(f"in-scope sessions: exposed {len(exp)}, unexposed {len(unexp)}")
    results = []

    # Q1: share of sessions with R > 0, exposed >= unexposed
    if min(len(exp), len(unexp)) < MIN_N:
        results.append(("Q1 share retrieving", None, f"n {len(exp)}/{len(unexp)}"))
    else:
        se = sum(retrieval(r) > 0 for r in exp) / len(exp)
        su = sum(retrieval(r) > 0 for r in unexp) / len(unexp)
        results.append(("Q1 share retrieving", se >= su, f"exposed {se:.2f} (n {len(exp)}), unexposed {su:.2f} (n {len(unexp)})"))

    # Q2: among R > 0, median exposed <= 0.5 * median unexposed
    re = [retrieval(r) for r in exp if retrieval(r) > 0]
    ru = [retrieval(r) for r in unexp if retrieval(r) > 0]
    if min(len(re), len(ru)) < MIN_N:
        results.append(("Q2 retrieval bytes", None, f"n {len(re)}/{len(ru)}"))
    else:
        me, mu = statistics.median(re), statistics.median(ru)
        results.append(("Q2 retrieval bytes", me <= 0.5 * mu, f"median exposed {me:,.0f} (n {len(re)}), unexposed {mu:,.0f} (n {len(ru)})"))

    # Q3: every exposed session with instructions logged carries <= 35,000 bytes
    logged = [r for r in exp if r.get("instructions_logged")]
    if len(logged) < MIN_N:
        results.append(("Q3 carry within caps", None, f"n {len(logged)}"))
    else:
        over = [r for r in logged if carry(r) > CARRY_CAP]
        results.append(("Q3 carry within caps", not over, f"{len(logged) - len(over)}/{len(logged)} within {CARRY_CAP:,}"))

    # Q4: median carry + R, exposed < unexposed, instructions logged in both arms
    te = [carry(r) + retrieval(r) for r in exp if r.get("instructions_logged")]
    tu = [carry(r) + retrieval(r) for r in unexp if r.get("instructions_logged")]
    if min(len(te), len(tu)) < MIN_N:
        results.append(("Q4 total memory bytes", None, f"n {len(te)}/{len(tu)}"))
    else:
        me, mu = statistics.median(te), statistics.median(tu)
        results.append(("Q4 total memory bytes", me < mu, f"median exposed {me:,.0f} (n {len(te)}), unexposed {mu:,.0f} (n {len(tu)})"))

    for name, holds, detail in results:
        verdict = "not evaluable" if holds is None else ("as expected" if holds else "DIFFERS")
        print(f"{name:24} {verdict:14} {detail}")


if __name__ == "__main__":
    rows = load(sys.argv[1])
    report(rows)
    for host in sorted({r.get("host") for r in rows}):
        print(f"\n-- host {host}")
        report([r for r in rows if r.get("host") == host])
