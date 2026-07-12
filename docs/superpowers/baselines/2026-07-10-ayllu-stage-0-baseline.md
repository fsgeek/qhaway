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

| Probe | Result | Established | Not established |
|---|---|---|---|
| Frozen complete suite | 137 passed in 12.86 seconds | All assertions shipped at the reviewed product revision pass under Python 3.14.3 | The suite cannot establish capabilities absent from the reviewed implementation |
| Session lifecycle and setup/removal slice | 25 passed in 1.60 seconds | A project remains dormant without topic files; a topic activates the next session; a lone hand-written `MEMORY.md` remains untouched; session exit writes a signed, bounded, self-sufficient projection; the pre-install file is preserved; omission counts match actual omissions; install is idempotent; uninstall removes only qhaway-owned hook and MCP entries | Cross-framework ownership transfer, umbrella-adapter supersession, export withdrawal, and reinstall around federated state |
| Projection loss, rebuild, and concurrency slice | 6 passed in 6.88 seconds | Budget overflow is declared; no topic omission is silent; schema drift causes bounded derived-index rebuilding; concurrent `remember()` calls retain both bodies; destructive rebuilds are serialized | Cross-corpus conflict envelopes, consumer-local foreign references, bilateral isolation, and coordinator concurrency |

The current lifecycle behavior supports continuity without pretending that
uninstall is erasure: active integration can stop, qhaway-owned configuration
can be removed, the curated topic corpus survives, and a displaced hand-written
`MEMORY.md` remains recoverable under its distinguished pre-install name.

Current qhaway evidence is intentionally local and Claude-specific. It does not
cover cross-project mounted content, export withdrawal, framework switching,
Codex delivery, or any interpretation of `AGENTS.md` or `CLAUDE.md`.

## llm-memory Baseline

## Adversarial Fixture Standing

## Evaluation Dimensions

## Stage Decision
