# Ayllu Stage 0 Baseline

**Umbrella:** `docs/superpowers/specs/2026-07-10-qhaway-ayllu-memory-design.md`
**Plan:** `docs/superpowers/plans/2026-07-10-ayllu-stage-0-baseline.md`
**Observation started:** 2026-07-12
**Boundary:** Evidence gathering only; no Stage 1 capability is implemented or authorized here.

## Revisions and Environment

| Surface | Reviewed revision | Worktree standing | Runtime dependency standing |
|---|---|---|---|
| qhaway | `6c90f8655a9e651218ae849d76d0fccb2029a80f` | Clean at observation start on `design/ayllu-memory-architecture`; later commits on this branch are documentation-only Stage 0 artifacts | Python 3.14.3, uv 0.11.24, SQLite 3.37.2 |
| llm-memory | `e95e32fbc739a4f5d3e21131b506472214346ce2` | Pre-existing modifications to `pyproject.toml` and `uv.lock`; untouched by Stage 0 | ArangoDB container running; database and ArangoSearch reachability evaluated separately below |

Command outputs in this report are summaries, not raw transcripts. A passing
test establishes only the behavior asserted by that test. A failed evaluation
is classified separately as an unavailable source, unavailable index, stale
index, contract mismatch, implementation defect, or retrieval-quality result
before it is used as evidence.

The plan and artifact names retain their approval date, 2026-07-10. Evidence
collection began on 2026-07-12, so volatile environment observations belong to
the latter date.

## qhaway Baseline

## llm-memory Baseline

## Adversarial Fixture Standing

## Evaluation Dimensions

## Stage Decision
