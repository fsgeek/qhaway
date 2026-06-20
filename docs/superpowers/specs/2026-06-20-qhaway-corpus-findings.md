# Qhaway — Corpus Findings & Test Rationale

**Date:** 2026-06-20
**Status:** Grounding layer (neither implementation nor validating tests — the
measured facts both reference).
**Companion to:** [`2026-06-20-qhaway-mvp-design.md`](2026-06-20-qhaway-mvp-design.md)

## What this document is

The design spec was reverse-engineered from **one** corpus (hamutay, 137 files —
see `llm-memory/proto/MODEL.md`). This document records what a **read-only sweep of
all 23 `MEMORY.md`-anchored corpora** under `~/.claude/projects` actually contains
(604 topic files across 17 real corpora), and what each measured fact *does* to the
spec and to the test fixtures.

It exists because **tests-first forces an interpretation of the interface**, and
that interpretation must be grounded in what the data *is*, not what one corpus
suggested. Each finding below carries three parts:

1. **Fact** — the measured number (and how measured).
2. **Change** — what it revises in the spec and/or the tests.
3. **Seam** — where implementer↔tester pushback is expected, and what that pushback
   *reopens*. The arrow runs both ways: friction here can flow corrections back *up*
   into the spec, not only down into the tests.

A finding marked **SETTLED** will not be overturned by more corpora (more data adds
examples, not structure). A finding marked **OPEN** is measured but unexplained and
*will* revise — it is written provisionally on purpose. Declaring that distinction
is the point; a rationale doc that claims "final" everywhere lies the same way a
silently-truncated index lies.

### Method (so the numbers are checkable)

Ephemeral read-only script over `~/.claude/projects/**/MEMORY.md`; reports
shapes/counts/histograms, never raw memory content. Anchors with 0 topic files →
NOT-PATTERN; 1–2 files → SUSPECT; ≥3 → analyzed. `memory.bak/` excluded. The script
was test-side scaffolding (gitignored, not preserved); its outputs are folded here.

---

## SETTLED findings

### S1 — `date_hint` is a niche signal; **mtime is the spine, with `origin_session` the content-intrinsic refinement**

**Fact.** Across 604 files: filename `_YYYYMMDD` date present on **7%** (44);
`metadata.originSessionId` on **56%** (340); **~44% have neither** → ordered by
mtime → filename. 11 of 17 corpora have **0%** filename dates, including the two
largest live corpora (governance 110 files 0%/100%, yanantin 95 files 0%/90%).
`date_hint` is meaningfully present only in hamutay (13%) and ai-honesty (48%).

**Change.** The spec's sort key led with `date_hint` (a hamutay artifact). It should
lead with the signals reality actually carries. Two intertwined facts:
- **mtime is the only signal on 100% of files** and, for locally-written files, is
  a true recency proxy — so it is the *spine*, not a last-resort fallback.
- **mtime is NOT content-intrinsic** — it changes under `git checkout`, `cp` (vs
  `cp -p`), `touch`, and crucially **`scp -r` without `-p`** (plain scp does not
  preserve mtime; `rsync -a` does). So mtime ordering is **stable per-machine and
  across mtime-preserving transfer, but a non-preserving transfer reorders the
  whole corpus** → different MEMORY.md → a one-time (D) rename on next index. This
  is real for this project's actual workflow (corpora are scp/rsync'd between
  machines). It is a **known, declared boundary**, not silent: state it in the spec.
- `origin_session` (56%) is **content-intrinsic** (survives any transfer) and is the
  better recency signal *where present* — argues for `origin_session → mtime →
  filename`, with `date_hint` as an optional earlier tier only where it exists.
- **Within a same-mtime batch, order is filename-alphabetical, NOT chronological.**
  With 44% of files relying on the tiebreak, this is the common case, not an edge.
  Accepted for v1 (stable > accurate; salience-tuning is deferred) — but *say so*,
  don't imply mtime yields true recency when half the corpus ties.

**Seam.** Implementer may argue "mtime breaks idempotence, drop it for
`origin_session`." Tester will counter "origin is absent on 44% — those files need
*some* total order." Resolution is the measured 56%/44% split: neither signal alone
is total, so the chain `[date_hint?] → origin_session → mtime → filename` is
required, filename guaranteeing totality (it is the PK). If the implementer finds a
cleaner content-intrinsic key, that reopens the **spec's sort rule**, not just the
test. → reopens design spec §"projection rule" step 4.

### S2 — three sort regimes; **the idempotence fixture must be modeled on a tiebreak-dominant corpus, not hamutay**

**Fact.** Corpora cluster into three populations:
- **origin-driven** (governance 0%/100%, yanantin 0%/90%, promptguard2/willay/
  pukara/rikuy ~0%/100%): sort by `origin_session`.
- **mtime-tail-dominant** (aider 0%/0%, eidolon 0%/0%, bladnman 0%/0%, **tinkuy 71
  files 12%/0%**, arbiter 54 files 0%/46%): a large share have *neither* signal →
  ordered entirely by mtime → filename. tinkuy ≈ 63 files on the tiebreak alone.
- **mixed** (hamutay 13%/38%, ai-honesty 48%/8%).

**Change.** Test 8 (idempotence — the cornerstone) currently implies a hamutay-shaped
fixture. It should be modeled on **tinkuy/aider** — corpora where the filename
tiebreak carries the ordering — so the test exercises the path 44% of real files
depend on. The fixture must also **hold mtimes fixed between the two runs** (mtime
sorting means "same files" → "same files *and same mtimes*"); otherwise the test
fails for non-bug reasons.

**Seam.** Tester writes a tinkuy-shaped fixture with a same-mtime tie pair (per
design spec test 8 fixture requirement). Implementer may object the fixture is
"unrealistically degenerate." It is not — it is the *modal* corpus shape. If real
corpora never actually produced same-mtime ties (they do — same-session batch
writes), this would reopen the need for the filename tiebreak at all. They do, so
it stays. → confirms design spec §test 8 fixture requirement; does not reopen it.

### S3 — tombstone marker is a **small open-vocabulary of curator intent**, not the single literal `SUPERSEDED`

**Fact.** 14 tombstones match `name ~ SUPERSEDED` (matches MODEL.md exactly). **One**
non-`SUPERSEDED` tombstone exists across all other corpora: arbiter has a `name`
marked **`DELETED`**. n=1, but it is a real curator-intent marker the spec's rule
would misclassify as **live**.

**Change.** Broaden the status rule to a **closed set** of curator-intent markers:
`SUPERSEDED | DELETED` for MVP. Semantic basis (Tony): *superseded = replaced;
deleted = removed/eliminated* — distinct acts, both meaning "not the current/live
record," so both are tombstones (excluded-but-declared, per design spec). Keep it
**anchored to the `name` field** and **a closed enum** — do NOT open it to a body
scan or a broad regex (that is the over-broadening failure). The n=1 defector is
read as stochastic phrasing noise (instances reach for different words for the same
act); catch the *cluster of intent*, not an open pattern.

**Change (tests).** Test 4's fixture **must include a `DELETED`-marked file**, so the
broadened rule is pinned by data, not assumed.

**Seam.** Implementer may want to add `DEPRECATED|OBSOLETE|REPLACED` pre-emptively.
Resist unless a sweep *finds* them — the discipline is "broaden to what we measured,
not what we imagined." Tester may want the set configurable; for MVP it is a fixed
enum. If a later corpus surfaces a third marker, that reopens **S3's enum** (additive,
cheap). → reopens design spec §"projection rule" (tombstone exclusion) only on new
evidence.

### S4 — **NOT-PATTERN anchors exist and would be damaged by naive `index`** → the spec needs a guard

**Fact.** Of 23 anchors, **6 are NOT-PATTERN or SUSPECT**:
- **pichay**: `MEMORY.md` 1765 bytes, **0 topic files** — an index over nothing.
- **tinkuy/memory.bak**: 0-topic-file MEMORY.md (a backup; correctly excluded).
- **cv** (1 file), three `/tmp/*` scratch dirs (1–2 files): stubs.

Context (Tony): `~/.claude` is not repo-maintained and Claude Code "cleans up" these
dirs, so several anchors are **cleanup survivors / transient partial states**, not
deliberate corpora.

**Change (spec gap — reaches into design, not just tests).** `qhaway index` must
**refuse to (or loudly warn before) regenerating a MEMORY.md in a directory with
zero / too-few topic files.** Today (D) would preserve pichay's bytes as an orphan —
but the instance still **boots an empty self**. The guard belongs in Error handling.
New test: *given a 0-topic-file dir, `qhaway index` declines/warns rather than
producing an empty index and superseding the existing file.* The guard is *more*
warranted because these dirs appear/vanish outside the user's control.

**Seam.** Threshold is a judgment call: 0 is clearly a refuse; is 1–2 a refuse, a
warn, or fine? Implementer/tester must pick a line. Proposed: **0 → refuse; ≥1 →
proceed but `--check` flags low-count dirs.** If the threshold proves wrong in use,
reopens **the guard's bound**, a one-constant change. → reopens design spec
§"Error handling" (new guard).

---

## OPEN findings (measured, unexplained — written provisionally)

### O1 — 47 wikilinks (3%) resolve under **no** id rule: rot, or temporal drift?

**Fact.** 1489 wikilinks total; 93% resolve by exact match, 97% after slug=stem
reconciliation (confirms MODEL.md finding #4 — reconciliation recovers 62 links and
is worth doing). **47 (3%) resolve under neither.**

**Unknown.** These are *either* real rot (links to deleted files — the genuine
`--check` / test-3 target) *or* an **unrecognized id convention** — possibly
**temporal drift** (older files using a naming scheme Claude Code later changed).
The two need *different* fixes: rot → `--check` reports it; drift → the parser's
id-reconciliation must learn the old convention.

**What would settle it.** Enumerate the 47 (link text + source file + **file age**),
check whether they **cluster by age / naming era**. Age-clustered → drift; scattered
→ rot. Cheap; do it **when test 3 is authored**, not before (YAGNI — test 3 is not
the first test written). Cross-system sweep is justified *only if* O1 turns out to be
an unrecognized mechanism (then "is this convention universal or local?" matters); if
it's plain rot, other systems teach nothing new. Do not pre-spend the sweep.

**Seam.** Test 3 asserts "`--check` reports body-wikilinks pointing at missing
files." If O1 is partly drift, some of those 47 are **false rot** and test 3's
fixture must separate them — which reopens **what the parser reconciles** (design
spec §data model, edges). → potential reopen of design spec §data model.

### O2 — is the tombstone enum complete at `{SUPERSEDED, DELETED}`?

**Fact.** Only these two markers observed across 17 corpora (14 + 1). **Unknown**
whether other principals/systems use further markers.

**What would settle it.** A cross-system sweep (same script, other machines). Gated
on need: only matters if S3's enum proves too narrow in use. Until then,
`{SUPERSEDED, DELETED}` is the pinned MVP set, documented as deliberately-closed.

**Seam.** Additive only — a new marker extends the enum, never restructures it. Low
risk; flagged for honesty, not because it blocks. → reopens S3 enum on new evidence.

---

## Summary of changes this document proposes

**To the design spec:**
- §projection rule step 4 — reorder sort tiers (`origin_session → mtime → filename`,
  `date_hint` optional-where-present); state the mtime/transfer determinism boundary
  (S1) and the same-mtime→alphabetical caveat.
- §projection rule (tombstone exclusion) — broaden status rule to closed set
  `{SUPERSEDED, DELETED}` (S3).
- §Error handling — add the zero/low-topic-file guard (S4).

**To the tests:**
- Test 8 fixture — model on a tiebreak-dominant corpus (tinkuy/aider), hold mtimes
  fixed across runs (S2).
- Test 4 fixture — include a `DELETED`-marked tombstone (S3).
- New test — 0-topic-file dir → `index` declines/warns (S4).
- Test 3 — resolve O1 (rot vs. drift) when authored; fixture may need to separate
  false-rot from real rot.

**Authorship note.** This is a neutral grounding layer: it asserts what the corpus
*contains*, not how to *implement* against it, so it does not pre-bias the
separately-authored tests toward the implementation's shape. Implementer and tester
both reference it; either may push back, and pushback that contradicts a SETTLED
finding should re-measure the corpus before revising — the data, not the argument,
is the referee.
