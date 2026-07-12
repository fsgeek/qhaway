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

| Probe | Source standing | Index standing | Result | Interpretation |
|---|---|---|---|---|
| Frozen complete suite | Live ArangoDB accepts uniquely keyed test episodes; tests remove those records afterward | Existing collection and search view are reachable | 17 passed in 1.18 seconds | Current ingestion transforms, scoped BM25 search, exact-key recall, and read-only MCP surfaces satisfy their shipped assertions |
| Aggregate corpus-shape query | Authoritative source files were not opened; the derived collection contains 1,221 `claude_code` records and 2,659 `yanantin_construction` records | Collection is available; freshness is not observable | Every `claude_code` record has `cycle`; every `yanantin_construction` record lacks `cycle` | A result contract centered on `cycle` cannot represent every currently indexed corpus |
| Five-query historical replay | Expected derived episode keys `000430`, `000431`, `000444`, `000456`, and `000457` are absent | Conversation-inclusive view is available and returns ranked mixed-corpus hits; freshness is not observable | 0/5 in top three; returned hits have `cycle: null`; command exits 1 | Ground truth is unavailable in the current collection, so this is a fixture/source-standing failure plus a result-identity mismatch, not evidence that conversation-inclusive ranking lost the expected episodes |
| Read-only state/conversation comparison | Same absent historical episodes | Both `episodes_state_only` and `episodes_search` exist; neither view was created or updated by Stage 0 | State-only 0/5; conversation-inclusive 0/5 | The comparison is observable but cannot discriminate retrieval quality without its expected source episodes |
| Margin and paraphrase characterization | Same absent historical episodes | Conversation-inclusive view returns scored top-ten lists | Expected cycles absent from all top-ten lists; all three paraphrases miss | Neither margin nor semantic reach can be evaluated against missing ground truth; the lexical limitation remains a hypothesis rather than a Stage 0 verdict |
| Adapter/search/recall/MCP slice | Test-owned records only | Existing view and exact-key collection lookup are reachable | 11 passed in 0.87 seconds | Adapter identity and current search/recall behavior are executable independently of the unavailable historical fixture |

### Corpus and Identity Observations

- taste_open maps one record to a cycle-addressed episode and currently uses the
  zero-padded cycle as `_key`.
- The pichay gateway maps request events to session plus a synthesized sequence;
  that sequence becomes both part of `_key` and the returned `cycle`.
- Claude Code maps assistant prose turns to session plus assistant UUID. These
  records have no `cycle`, although the current `search()` response always
  includes a `cycle` field.
- No Codex conversation source or stable event identity has been characterized.
- `scope="all"` deliberately searches across corpora. The historical evaluation
  fixture names expected cycles but names no concrete corpus, so unrelated
  records without cycles can occupy its bounded result set.

### Known Baseline Failure

The five real queries remain useful records of prior retrieval failures, but
their current replay is not self-contained. It assumes that a particular
cycle-addressed taste_open corpus has already been ingested and that a mixed
`scope="all"` result can be judged solely by `cycle`. The current database
contains neither the expected episode keys nor a taste_open-labeled corpus.

Stage 0 therefore declares the retrieval-quality comparison unavailable rather
than converting 0/5 into manufactured evidence. Stage 1 must make corpus
identity and result identity explicit, and must report source availability,
index availability, freshness, and match-population standing separately.

### Operational Dependencies

`llm-memory` requires a reachable ArangoDB, local database configuration, the
`episodes` collection, and the named ArangoSearch views. Its tests and reads
succeeded with the running container. The current search response exposes no
indexed-through cursor or timestamp, so index freshness cannot be inferred from
availability. Running commands from the qhaway environment also produces a
benign uv warning that its active virtual environment is ignored in favor of
`llm-memory/.venv`.

## Adversarial Fixture Standing

The fixture catalog is
`docs/superpowers/baselines/2026-07-10-ayllu-stage-0-adversarial-fixtures.yaml`.
Its standing is `declarative_only`: these are reviewable, backend-neutral
scenarios with explicit expected standing, not passing product tests.

| Fixture | Earliest executable stage | Standing at Stage 0 |
|---|---|---|
| `missing-episode-evidence` | Stage 1 | Defined; exact reference and unavailable-source semantics require the episodic contract |
| `stale-index-bounded-search` | Stage 1 | Defined; bounded results, total-match standing, and indexed-through standing require the episodic contract |
| `curated-conflict-local-mounted` | Stage 4 | Defined; no current federation or consumer-local cross-corpus conflict record exists |
| `export-withdrawal` | Stage 4 | Defined; no current bilateral export/mount relationship exists to withdraw |
| `bilateral-isolation` | Stage 4 | Defined; no current named-consumer authorization path exists to exercise |

All five fixtures are non-sensitive and contain synthetic qualified identifiers.
None is executable in the current qhaway/`llm-memory` capability set. Preserving
that distinction prevents declarative coverage from being reported as product
behavior.

## Evaluation Dimensions

## Stage Decision
