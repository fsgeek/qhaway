# Claim re-grounding at recall — design

**Date:** 2026-06-28
**Status:** Self-approved by the guardian instance (yanantin), ready to build.
**Companion:** yanantin `docs/superpowers/specs/2026-06-28-claim-regrounding-design.md`
(the `reground()` mechanism, already built and proven live: 1221→3880).

---

## The gap (verified, not assumed)

`reground(claim) -> Regrounding` exists in yanantin and is proven, but runs
*outside* qhaway. A `claim:` block on a memory:

- **survives reconcile** — `reconcile._reconcile_nodes` only *reads* topic files
  into SQLite; the only file qhaway writes is `MEMORY.md`. Verified.
- **is dropped by the index** — `model._NODE_COLUMNS` has no claim slot, so
  `upsert_file` discards it. Verified.
- therefore **never reaches `recall()`**. The frozen value is all a future
  instance sees.

Close the loop: parse the claim, carry it through the index, re-ground it on
recall — so `recall()` shows the live value beside the frozen one.

## The cross-repo decision (rule 3): dependency inversion

qhaway must reach `reground` WITHOUT yanantin's DB layer becoming a hard qhaway
dependency. Resolution: **qhaway defines the interface; yanantin injects the
implementation.**

- qhaway holds an optional `reground: Callable[[dict], str] | None` — a callable
  that takes a claim dict and returns a rendered live string.
- When yanantin starts the qhaway server, it injects its `reground` (wrapped to
  return `Regrounding.render()`).
- When qhaway runs standalone (no injection), a claim renders frozen-with-as_of
  — honest, just not live.

qhaway never imports yanantin. yanantin owns DB reach. This is the wrangler/edge
pattern: the re-grounder is an EDGE yanantin plugs into qhaway's recall — same
shape as the storage feedback edge, different node.

## Why NOT re-ground inside project_slice

`recall()` returns a *budgeted projection* — headers + one-line hooks, not full
bodies. Re-grounding every claim on every recall = one live DB round-trip per
memory in the working set: slow, and couples the index view to the DB. So
re-grounding happens only for memories that HAVE a claim, and only at the recall
boundary where the injected callable is available — not in the pure projection.

## The three coordinated changes

1. **Parse** (`parse.py`): surface `metadata.get("claim")` into the node dict as
   `claim` (a dict or None). Trivial — `_split_frontmatter` already YAML-loads the
   whole frontmatter; the tolerant fallback ignores nested blocks, which is fine
   (a claim needs valid YAML to be checkable anyway).
2. **Store** (`model.py`): add a `claim` column (JSON-encoded text, nullable) to
   `_NODE_COLUMNS` and the schema; `upsert_file` writes `json.dumps(node["claim"])`
   or NULL; `fetch_nodes` reads it back (JSON-decode). Additive column —
   `get_connection`'s drift-rebuild handles the schema change (existing rows
   re-parse from disk; no claim → NULL).
3. **Re-ground at recall** (`server.py`): `recall()` gains an optional injected
   `reground`. After projecting, for each memory carrying a claim, append a
   re-grounded line (`reground(claim)` → live string) to the output. Frozen value
   preserved in the body; live value shown beside it.

## Additivity (rule 4)

A memory with NO claim block: `claim` parses to None, stores NULL, projects
exactly as today. Proven by an explicit unchanged-projection check in the test.

## Testing (Codex authors, rule 5)

Red→green, live store, no mocks:
1. Seed a topic `.md` file with a `claim:` block whose value is deliberately
   stale vs a known live count (seed a throwaway collection in `apacheta_test`).
2. Call the recall path WITH an injected reground. The test injects a
   qhaway-LOCAL callable that counts live via `arango` directly (NO yanantin
   import — that would invert the dependency the design forbids; NO mock — it
   hits the real `apacheta_test` store). This also proves the interface is
   genuinely decoupled: any conforming callable works, not just yanantin's.
3. Assert the recall output contains the LIVE value, and still contains the
   frozen value (before/after both visible).
4. Assert a claimless memory's projection is byte-identical with and without the
   reground injection (additivity).
5. Red before (claim dropped by index / not re-grounded), green after.

Then the proof case: add a `claim:` block to
`project_federation_runs_today_and_i_was_the_uningested_episode`, recall it,
read 3880 live beside frozen 1221.

## Files

- `qhaway/src/qhaway/parse.py` — surface `claim`.
- `qhaway/src/qhaway/model.py` — `claim` column + JSON round-trip.
- `qhaway/src/qhaway/server.py` — injected `reground`, re-ground on recall.
- yanantin side — inject `reground` when starting the server (a wiring shim).
- `qhaway/tests/test_claim_regrounding.py` — Codex-authored.

## Done

An instance calls `recall()`; the federation memory's frozen 1221 self-corrects
to live 3880 in the recall output. The loop is closed end-to-end. The temporary
structure is improved, not worked around.
