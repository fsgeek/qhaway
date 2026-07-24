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

| Dimension | Finding | Evidence | Declared limitation |
|---|---|---|---|
| Fidelity | Current local transforms and exact retrieval paths preserve the fields asserted by their tests | Qhaway complete suite; `llm-memory` ingestion, search, recall, and MCP slice | The absent historical episodes prevent a current real-corpus ranking-fidelity measurement |
| Declared loss | Qhaway declares bounded projection omissions and preserves a displaced pre-install file | Budget-overflow, no-silent-omission, exit-footer, and lifecycle assertions | Episodic search does not declare total-match standing, freshness, or the effect of mixed-corpus truncation |
| Selectivity | `llm-memory` can filter by `experiment_label`, but its default all-corpus scope invalidates the cycle-only historical fixture in the current mixed collection | Scoped-search test and live replay returning cycle-less records | Labels are illustrative partitions, not bilateral authorization or a stable corpus ontology |
| Dissent retention | Current qhaway can retain authoritative topic files while projection applies supersession and bounded selection | Qhaway complete suite and preserved topic-corpus lifecycle | Curated conflict sets, cross-corpus conflict envelopes, and privacy-preserving withdrawal are not observable at Stage 0 |
| Provenance | Qhaway projects from authoritative topic files; episodic search returns an exact collection key that recall can open | Qhaway rebuild tests; `llm-memory` search/recall and MCP tests | There is no cross-capability reference standing, and a missing episode resolves only to absence rather than a qualified failure state |
| Continuity | A fresh Claude session can receive a rebuilt local projection, and uninstall preserves curated sources and the pre-install file | Session lifecycle, exit sequence, setup, and rebuild assertions | Episodic history is not reconciled or delivered through the qhaway lifecycle, and no Codex journey exists |
| Isolation | Search scope prevents one test corpus from appearing in another label-scoped query | `test_scope_partitions_corpora_by_experiment_label` | A label filter is not an access-control boundary; bilateral export/mount authorization is only a declarative fixture |
| Recoverability | Qhaway rebuilds its derived SQLite state from topic files after schema drift and serializes destructive rebuilds | Focused schema-drift, bounded-rebuild, and serialization probes | Episodic source-to-index rebuilding was not exercised because Stage 0 neither opened authoritative logs nor modified the live index |
| Unobtrusiveness | Qhaway self-gates when no topic corpus exists and needs no operator action for its tested session lifecycle | Dormant/active lifecycle and idempotent setup assertions | `llm-memory` currently requires a configured ArangoDB and explicit corpus ingestion; freshness and automatic reconciliation are absent from the interface |
| Generativity | Not observable at Stage 0 | The five real queries are preserved, but their expected source episodes are unavailable | Synthetic passing tests and ranked unrelated hits do not establish that the combined system creates useful new connections |
| Complexity | The two current capabilities have visible, different operational boundaries: local SQLite projection versus containerized ArangoSearch history | Dependency inventory, worktree inspection, test execution, and live database probes | Coordinator ownership, adapter migration, federation lifecycle, and total removal cost cannot be measured before their focused specifications exist |

The dimensions remain separate. In particular, the clean qhaway lifecycle does
not cancel the episodic evaluation gap, and the episodic identity gap does not
erase qhaway's demonstrated declared-loss and recovery behavior.

## Stage Decision

**Decision: continue**

Stage 0 has enough evidence to authorize a focused Stage 1 episodic-contract
specification, and nothing beyond it. Three observations earn that next design
step:

1. The existing episodic implementation has executable ingestion, scoped
   lexical search, exact-key recall, and a read-only MCP surface across three
   source shapes.
2. The live collection contains two incompatible result-identity shapes, while
   the historical evaluation assumes one cycle-addressed shape and no concrete
   corpus. This is direct evidence that stable episode identity and explicit
   corpus scope are prerequisites rather than speculative abstraction.
3. Index availability is observable, but source availability, freshness,
   indexed-through position, and total-match standing are not. These are the
   exact contract distinctions Stage 1 is intended to define.

Repairing the missing historical fixture inside Stage 0 is the strongest
alternative. It is rejected because ingesting a former corpus would mutate
persistent derived state, would restore only one evaluation environment, and
would not resolve the mixed identity or missing-standing contracts exposed by
the current corpus. Retrieval backend quality remains unevaluated and is not a
basis for this decision.

### Stage 1 Specification Preconditions

1. Define a result identity that does not assume every corpus has `cycle`.
2. Require concrete corpus scope in the evaluation fixture and retrieval
   contract.
3. Separate source, index, freshness, and match-population standing.
4. Define bounded results plus exact or explicitly unavailable total-match
   standing.
5. Characterize taste_open, gateway, and Claude Code identity; characterize
   Codex only after its actual source format is observed.
6. Preserve ArangoDB as the implementation under test; do not select or
   implement SQLite FTS5 in Stage 1.

This decision stops at permission to write the focused specification. No Stage
1 design or implementation is part of this artifact.
