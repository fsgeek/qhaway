# Ayllu Stage 2 Retrieval Experiment

**Date:** 2026-07-13

**Status:** Approved focused design; review findings closed 2026-07-14

**Umbrella:** `docs/superpowers/specs/2026-07-10-qhaway-ayllu-memory-design.md`

**Stage 1 contract:** `docs/superpowers/specs/2026-07-12-ayllu-stage-1-episodic-contract-design.md`

**Stage 1 decision:** `docs/superpowers/baselines/2026-07-12-ayllu-stage-1-evaluation.md`

**Review:** `docs/superpowers/specs/2026-07-13-ayllu-stage-2-retrieval-experiment-review.md`

## Decision summary

Stage 2 implements SQLite FTS5 as a lifecycle-complete peer to the existing
ArangoSearch episodic provider and compares the two without requiring a single
winner. The comparison asks:

> What does each lexical retrieval implementation preserve and lose when
> recovering rationale across heterogeneous tool histories, and what
> operational and removal costs does each impose?

The experiment shares source adapters, qualified episode identity, enrollment
authority, and source-backed exact opening. Each provider separately owns only
its derived persistence, reconciliation state, lexical index, search/count
operation, supersession observations, and purge behavior.

Portable synthetic fixtures establish contract and lifecycle behavior. A later
authorized real snapshot establishes retrieval usefulness. That snapshot is
broad across explicitly named projects and tools, but it remains partitioned
into concrete corpus identities. Codex and Gemini source formats must be
characterized before their native histories can participate.

Rationale recovery is evaluated with a mixed fixture:

- documented decisions provide inspectable calibration; and
- recalled but poorly documented decisions test the failure that ordinary
  TODOs and summaries cannot repair.

Retrieval evidence coverage and fresh-participant rationale reconstruction are
reported separately. No aggregate score turns fidelity, usefulness,
deployment, privacy, or removal into one number.

`sqlite-vec` is a named revisit candidate, not a Stage 2 dependency. Evidence
that vocabulary-distant rationale repeatedly escapes both lexical providers may
open a focused vector or hybrid specification. It does not silently expand this
stage.

## Change control

The approved umbrella authorizes a focused SQLite FTS5 peer comparison. Stage 2
does not revise the umbrella's source authority, federation, curatorial
authority, framework delivery, or non-destructive disengagement rules.

The following changes require a new decision record or focused specification:

- adding vector, hybrid, graph, or learned retrieval;
- selecting an embedding model or sending source content to an embedding API;
- making SQLite or Arango the production default;
- changing episode identity or source authority;
- adding federation or cross-project authorization;
- projecting episodic content into resident memory;
- treating evaluator-authored labels as corpus ontology; or
- retaining real evaluation content beyond its authorized lifecycle.

Implementation discoveries may repair this stage only when they preserve its
comparison question and authority boundaries. A change that makes the providers
answer materially different questions is a reframe, not a local convenience.

## Why Stage 2 is earned

Stage 1 established stable qualified identity, concrete corpus scope, nested
source/index/freshness standing, bounded results, exact-or-declared match
population, source-backed opening, bounded reconciliation, and explicit purge.
It also exposed costs that a peer backend can now measure rather than speculate
about:

- a reachable ArangoDB service, credentials, port, collections, and view;
- immutable generation cloning that remains O(active generation documents);
- startup and pre-search reconciliation work;
- provider-specific concurrency and retry behavior;
- storage amplification not captured by serialized document size; and
- removal that spans service state as well as application configuration.

Stage 1 did not establish real retrieval usefulness or generativity. Its
synthetic journey proved mechanics only. Stage 2 therefore needs both a
provider comparison and a real rationale-recovery journey.

The historical lexical evidence is encouraging but insufficient. Conversation-
inclusive Arango search recovered five known taste_open queries that a
state-only index missed, while the later Stage 0 replay lost its source fixture.
Neither observation compares providers, represents heterogeneous tool history,
or tests recovery of the reasons behind a decision.

### Stage boundary accounting

This focused stage is deliberately larger than the umbrella's one-sentence
description in two ways:

1. it makes real rationale recovery necessary evidence rather than treating a
   real corpus as an optional performance sample; and
2. it adds Codex and Gemini source characterization before claiming a
   heterogeneous comparison.

Both additions are accepted consciously. Synthetic text cannot establish
rationale usefulness, and omitting Codex would make the intended reciprocity
one-way. The adapter work extends the existing Stage 1 source contract; it does
not install framework delivery or change episode authority. If either native
format cannot be characterized without materially revising the shared contract,
the stage records `repair` or `reframe` instead of absorbing an unbounded
adapter project.

## Questions this stage answers

Stage 2 answers these questions independently:

1. Can SQLite FTS5 satisfy the Stage 1 episodic contract and lifecycle without
   acquiring source authority?
2. Which rationale evidence does each lexical provider recover, omit, or rank
   differently under the same query and source snapshot?
3. Can a fresh participant reconstruct the chosen action, reasons, strongest
   rejected alternative, uncertainty, and revisit conditions from each bounded
   result set?
4. How do ingestion, append, rewrite, reconciliation, concurrency, startup,
   query/count, storage, outage, rebuild, selective purge, and full removal
   differ?
5. Does lexical vocabulary mismatch dominate provider differences strongly
   enough to earn a later vector or hybrid experiment?

It does not answer whether semantic proximity establishes meaning, whether a
graph captures conversation ontology, or whether either backend should become a
unified store.

## Alternatives considered

### Contract-peer experiment (selected)

SQLite implements the same public episodic obligations as Arango: bounded
reconciliation, nested standing, search and count from one defensible snapshot,
source-backed opening support, supersession lookup, selective purge, and full
derived-state removal.

This costs more than a search prototype, but it compares the capabilities users
would actually have to install, operate, recover, and remove.

### Evaluation-only FTS5 mirror

A small script could copy active Arango documents into an FTS5 table and replay
queries. It would cheaply compare rankings, but it would inherit Arango's
ingestion result, omit source reconciliation, avoid concurrent writers, and
make SQLite removal look easier by excluding most lifecycle obligations. It is
rejected because it would answer a narrower and biased question.

### SQLite migration pilot

Replacing Arango before comparison would exercise a realistic deployment but
would presume the backend decision, complicate rollback, and remove the
controlled baseline. It is rejected as premature collapse.

### Immediate lexical, vector, and hybrid comparison

Adding vector retrieval now could test vocabulary-distant rationale earlier.
It would also introduce an embedding model, model version, dimensions, distance
metric, content-disclosure policy, rebuild behavior, candidate-population
semantics, and rank-fusion policy. Those variables would obscure the lexical
provider comparison. The option remains available behind an evidence trigger.

## Ownership and provider boundary

Stage 2 remains implemented in `llm-memory`. Qhaway receives the focused
specification and final evidence record; it does not acquire episodic
persistence or service lifecycle.

The logical boundary is:

```text
authoritative conversation sources
             |
             v
shared versioned source adapters
             |
             +----------------------+
             |                      |
             v                      v
    Arango derived provider   SQLite derived provider
             |                      |
             +----------+-----------+
                        |
                        v
             Stage 1 search response

qualified episode reference
             |
             v
shared source adapter resolver -> source-backed open_episode()
```

Shared code may own:

- contract types and validation;
- enrollment declarations;
- source adapters and canonical episode records;
- qualified references and identity digests;
- source-backed exact opening; and
- evaluation report types that do not contain source content by default.

Each provider owns:

- schema creation and versioning for its derived state;
- active and staging generation state;
- reconciliation cursors and integrity observations;
- derived episode documents and lexical indexes;
- one-snapshot search and population counts;
- rebuildable supersession observations;
- concurrency and retry behavior;
- provider-specific measurements; and
- scoped purge and full removal.

No provider owns source declarations or authoritative episode content. Cached
documents and supersession observations cannot authorize opening or enrollment.

## Provider contract

The focused implementation plan defines concrete Python types, but the provider
boundary must support these operations:

```text
capabilities() -> provider and strategy declarations
ensure() -> schema/index standing
reconcile(registry, work_budget) -> nested corpus standing and work report
search(registry, request, work_budget) -> Stage 1 bounded search response
resolve_supersession(enrollment, old_ref) -> replacement ref or none
purge(scope, state_classes) -> exact deletion counts and declared losses
measure(scope) -> provider-specific resource observations with standing
```

`open_episode()` remains source-first. It may ask the selected provider for a
supersession observation only after source resolution fails to find the old
identity. A provider document never supplies authoritative episode content.

Operational service configuration selects exactly one provider at startup for
derived supersession observations. The open request does not infer a provider,
query both and merge their answers, or fall back to whichever provider is
available. Exact source-backed opening remains provider-independent; only the
optional transition from `missing` to `superseded` uses the configured
provider's observation.

The Stage 2 comparison harness may perform separate provider-scoped openings
for the same old reference. Each observation is labeled with its provider in
the evaluation envelope. A `superseded` observation from one provider and a
`missing` observation from the other is recorded as reconciliation or retained-
history divergence, not reconciled into one apparently authoritative standing.

The Arango implementation may be wrapped to satisfy this boundary, but Stage 2
does not authorize broad refactoring merely to make the two implementations
look symmetrical.

## Retrieval strategies and honest comparison

The providers share the response contract, query text, corpus scope, indexed
fields, and source snapshot. They do not claim identical tokenization or score
meaning.

The existing Arango strategy remains:

```text
lexical_bm25_text_en_v1
```

The initial SQLite strategy is separately named:

```text
lexical_bm25_fts5_porter_unicode61_v1
```

It uses `tokenize = 'porter unicode61 remove_diacritics 2'` with default FTS5
BM25 column weights. A portable startup probe must establish that this exact
configuration is available. Different strategy identifiers are intentional.
Reusing one identifier for non-identical analyzers would manufacture
equivalence.

Its public `match_semantics` value is:

```text
analyzed_any_segment_phrase
```

It must not reuse Arango's `analyzed_any_token` value.

The initial SQLite query interpretation is also fixed before real replay:

- trim the validated natural-language query;
- split it on Unicode whitespace;
- encode every segment as an escaped FTS5 quoted string; and
- join the segments with explicit `OR` operators.

The configured FTS5 tokenizer then interprets each quoted segment. A segment
that the tokenizer divides into several terms is a phrase within that segment.
This is not identical to Arango `text_en` tokenization and is declared in the
retrieval basis. Query syntax supplied by source text is never passed through as
an FTS5 operator.

Both strategies index:

- `user_message`;
- `response`; and
- flattened `state_text`.

Neither strategy indexes evaluator labels, decision facets, expected
references, project names, or rationale ground truth.

The initial configuration is frozen before real results are observed. Stage 2
does not tune analyzers, weights, stemming, stopwords, or BM25 parameters per
query. A later tuning experiment requires its own predeclared comparison.

Each evaluation observation combines the unchanged public response with a
retrieval-basis envelope sufficient to identify:

- provider and provider version;
- strategy identifier;
- analyzer/tokenizer configuration;
- indexed fields;
- match semantics;
- score ordering semantics; and
- whether total population is exact, estimated, a lower bound, or unknown.

The evaluator replays the same natural-language query against each provider.
It does not rewrite a failed query differently for one provider.

### Contract compatibility

Stage 2 retains episodic contract version 1. The contract already requires a
strategy identifier and match-semantics declaration, so adding a separately
named SQLite strategy does not require a new request or response shape.

The public response is not extended with ad hoc provider fields. Provider name,
provider implementation version, full analyzer/tokenizer configuration, score
ordering, and measurement basis live in the Stage 2 evaluation envelope and in
the provider's capability declaration. Existing Arango callers retain the
current default strategy and behavior. An unknown strategy continues to fail
visibly rather than selecting whichever provider is available.

SQLite FTS5 `bm25()` uses lower, normally more-negative values for better
matches. The SQLite provider exposes `score = -bm25()` and sorts the public
response by score descending, then episode reference ascending, preserving the
Stage 1 ordering convention. The evaluation envelope records the raw polarity
and normalization. Score magnitudes are never compared across providers.

## SQLite FTS5 provider

The Stage 2 SQLite provider uses Python's standard `sqlite3` module and requires
an `ENABLE_FTS5` runtime probe. The current evaluation environment reports
SQLite 3.50.4 with FTS5 enabled. A missing FTS5 build fails visibly as
unsupported; it does not download an extension or fall back to substring
search.

The provider stores all derived state in one explicitly configured SQLite file
for the evaluation environment. The file contains ordinary relational state
plus an FTS5 index. The implementation may use an external-content FTS5 table
only when transactions, triggers, and integrity checks prove that content and
index cannot silently diverge. Otherwise it uses the simpler self-contained
FTS5 representation and declares the duplication.

The schema must preserve these logical classes even if table names differ:

```text
provider metadata and schema version
derived episode generations
active/staging source-member state
FTS5 lexical index
reconciliation and integrity cursors
supersession observations
```

SQLite write topology is explicit:

- separate sessions use separate connections;
- transactions, not a process-elected writer, serialize state transitions;
- WAL mode may allow readers during a bounded writer transaction;
- a bounded busy timeout ends in a visible retryable/provider-unavailable
  standing rather than an indefinite wait;
- activation of a completed generation and its standing is atomic;
- a search and its per-corpus/aggregate counts use one read snapshot; and
- a crash cannot expose a partial staging generation as active.

Bounded reconciliation may persist staging work across calls. The first
implementation favors a simple, inspectable generation representation over a
deduplication layer. If append seeding clones active rows, that database work is
measured separately from authoritative source bytes, as it is for Arango.

The provider supports:

- disable without deleting the declaration or source;
- unenroll without pretending retained derived data is authorized;
- selective purge by corpus, optional source, and state class;
- full derived-file removal with an explicit loss report; and
- rebuild from an authorized source declaration.

Deleting the SQLite file is not described as lossless when it removes retained
supersession observations or evaluation state that cannot be reproduced from
current source bytes.

SQLite FTS5 documentation is treated as the implementation reference:
`https://www.sqlite.org/fts5.html`.

## Arango provider baseline

Stage 2 preserves the repaired Stage 1 Arango provider as the implementation
under test. Correctness defects may be repaired with regression evidence, but
the real-query result must not trigger analyzer or ranking changes.

The comparison runs against a pinned, disposable ArangoDB container and volume
rather than mixing evaluation documents into an unrelated long-lived service.
This makes these costs observable:

- image acquisition and supported architecture;
- service startup and readiness;
- credential and port configuration;
- idle and active resource use;
- collection and view creation;
- on-disk volume growth;
- outage and restart behavior;
- selective corpus purge; and
- container, volume, credential, and configuration removal.

Containerization is a deployment mechanism, not a zero-cost standing. The
report distinguishes container runtime availability from Arango provider
availability.

## Source adapter entry gate

The real experiment is heterogeneous only when the source layer can identify
and reopen native evidence honestly.

Stage 2 begins with the three Stage 1 adapters:

- taste_open JSONL;
- Pichay gateway JSONL; and
- Claude Code project JSONL.

Before native Codex or Gemini history is enrolled, each new adapter must define
and test:

- source-set and member discovery within an explicitly authorized root;
- native session identity when present;
- native event identity or an explicitly synthesized event token;
- the assistant-prose episode boundary;
- included and excluded event types;
- canonicalization, boundary, and implementation versions;
- chunked scanning and complete-record boundaries;
- relocation, append, rewrite, truncation, and malformed-record behavior;
- source-backed exact opening using the recorded semantic versions; and
- synthetic structural fixtures that contain no private conversation prose.

Characterizing ingestion does not install hooks, project memory, or resident
delivery for Codex or Gemini. Framework delivery remains a later stage.

Actual native formats are not guessed from product documentation. A minimal
authorized local sample establishes their shape. If a format lacks enough
durable evidence for the Stage 1 identity contract, its standing is
`unsupported_adapter` or declared synthesized instability; the adapter does not
invent stronger guarantees to satisfy the evaluation schedule.

## Real-corpus authorization and snapshot

No real conversation source is read, copied, indexed, or opened until a local
manifest has been presented to and authorized by the human steward.

The authorization decision is narrow, while the evidence corpus is broad. The
manifest names:

- every permitted source root or file set;
- its project and tool partition;
- the proposed corpus and source identifiers;
- the adapter and known version standing;
- any time or path exclusions;
- the snapshot location and access permissions;
- which local processes may read it;
- every agent surface used to construct fixtures, adjudicate evidence, or write
  content-bearing private reports, with its maximum evidence scope;
- any hosted participant surfaces permitted to receive selected opened
  evidence, and the maximum evidence scope they may receive;
- report fields allowed to survive;
- snapshot and index retention duration; and
- the purge and verification procedure.

Authorization never uses `~`, a project parent, or automatic home-directory
discovery as an implicit wildcard. Broad scope is produced by enumerating
approved roots, not by making scope unknowable.

An initial manifest may label a Codex or Gemini family `uncharacterized` and
name the bounded samples that may be inspected to determine adapter standing.
Characterization then amends that manifest with adapter and version standing;
it does not require another authorization round when paths, evidence scope,
processes, disclosure, retention, and purge terms are unchanged. Any amendment
that expands one of those authority-bearing terms requires explicit approval.

The target evidence environment includes native Codex history and at least one
non-Codex tool family. It should include Claude Code, Gemini, Pichay, and
taste_open wherever authorized sources and conforming adapters are available.
Unavailable or unsupported families remain visible in the report; they are not
replaced with synthetic diversity.

Sources remain partitioned by project and tool in concrete corpus identities.
An evaluation request may name several corpora deliberately, but Stage 2 does
not flatten them into one corpus or implement federation.

The authorized source files are copied byte-for-byte into a disposable,
read-only evaluation snapshot. The snapshot manifest records file digests and
structure without committing paths or content. Both providers derive their
indexes from this identical snapshot. The originals are hashed before and after
where feasible and are never modified by lifecycle operations.

Creating the snapshot is itself another sensitive data projection. The default
end-of-stage action purges both provider indexes and the snapshot after the
allowed report is durably recorded. Retaining it for repeatability requires a
separate explicit retention choice. Purging it declares the resulting loss of
byte-identical replayability.

## Rationale-recovery fixture

The evaluation unit is a decision whose reasoning may span several episodes.
The fixture is local and content-bearing; the committed report is not.

Each fixture record contains:

```text
opaque decision token
ground-truth class: documented / recalled
natural-language query
query vocabulary stratum
rationale facets
expected qualified episode references by facet
ground-truth standing
adjudication notes and source-opening standing
```

The rationale facets are experimental observations, not corpus ontology. The
initial facets are:

- question or tension being resolved;
- chosen action or present standing;
- supporting reasons and evidence;
- strongest rejected or deferred alternative;
- uncertainty, dissent, or declared loss; and
- condition that should reopen the decision.

These facets may be absent from the historical evidence. Absence is reported;
it is not filled with a plausible explanation.

### Documented calibration decisions

Calibration decisions have an inspectable specification, review, decision
record, or other artifact outside the indexed conversation corpus. That
artifact defines the expected rationale structure but is not searchable by the
providers and is not shown to a reconstruction participant.

Expected episode references are established by source scan and exact opening,
not by accepting the top result from either provider as ground truth. If the
written record makes a claim for which no supporting episode can be found, that
facet is labeled unsupported or unresolved.

### Recalled, poorly documented decisions

For the harder fixture, the human steward records a question and provisional
rationale from memory before transcript search. This preserves the actual use
case: recovering reasoning that was not already converted into a clean artifact.

Later evidence adjudication may confirm, complicate, or contradict that recall.
A recalled answer does not become authoritative merely because it came first.
When no source evidence can be established, the fixture remains unresolved and
can evaluate discovery behavior qualitatively, but it is excluded from exact
expected-reference claims.

Provider output may suggest candidate evidence during recalled-fixture
adjudication, but it cannot define the expected set. Whenever Arango or SQLite
output contributes a candidate, an independent sequential scan of every
authorized source member in the fixture's concrete corpus scope must complete
before coverage is computed. That scan uses the versioned adapters and exact
opening, not either provider's index or ranking. The fixture records
`adjudication_basis: provider_assisted_independent_scan` and which provider
contributed candidates. This prevents one provider from defining the ground
truth against which its peer is measured.

### Query vocabulary strata

Queries are frozen before provider execution and classified for experimental
analysis as:

- **aligned:** substantial decision vocabulary is known to appear in expected
  evidence;
- **partial:** some vocabulary overlaps, while important rationale is
  paraphrased; or
- **distant:** the natural question expresses the decision with little observed
  lexical overlap.

These labels test the declared lexical limitation. They are not static source
categories and do not become search facets.

An unresolved recalled fixture has `stratum: unassigned`. It does not enter
aligned, partial, or distant strata analysis until independent adjudication has
established source evidence against which vocabulary overlap can be observed.

The query text, expected references, and rationale prose remain local unless a
separate disclosure decision permits publication. The committed evaluation may
retain digests, lengths, opaque tokens, strata, counts, standing, and redacted
findings.

## Retrieval evaluation

Every frozen query runs against both providers with:

- the same immutable source snapshot;
- the same concrete corpus identifiers;
- the same result limits;
- the provider's predeclared lexical strategy;
- cold and warm observations where meaningful; and
- no query-specific tuning or retry that changes semantics.

The evaluator records per query and provider:

- returned qualified references and rank positions;
- exact opening standing for expected and returned references;
- expected-reference coverage at each tested bound;
- rationale-facet evidence coverage;
- returned and total-match standing;
- source, index, and freshness standing;
- result-set and ordering differences;
- query/count latency with measurement basis;
- reconciliation work performed before the query; and
- declared failures or unavailable measurements.

A result counts as evidence for a facet only when its exact source-backed
opening contains the relevant material. A snippet, score, or evaluator
impression alone is insufficient.

The experiment does not collapse the observations into mean reciprocal rank,
hit rate, latency, or another single verdict. Such statistics may be reported
as descriptive views, but every decision retains the underlying per-query
record and independent dimensions.

## Fresh-participant reconstruction

Retrieval coverage establishes whether evidence was available, not whether it
was usable for continuity. A separate journey gives a fresh participant only:

- the frozen question;
- the bounded, source-opened evidence returned by one provider; and
- a fixed request to reconstruct the rationale facets and identify uncertainty.

The participant does not receive the decision record, expected references,
other provider's results, prior conversation summary, or evaluator labels.

Where available, the journey uses participants from more than one model family
and records the family and delivery surface. Participant outputs are not votes
and are not averaged. Differences may reveal that a retrieval set supports one
participant but not another.

A hosted participant receives opened episode text only when the real-corpus
manifest explicitly authorizes that named surface and disclosure scope. Ordinary
use of Claude Code, Codex, Gemini, or another tool does not imply permission to
send a new cross-tool evidence bundle. Without that authorization, the journey
uses an authorized local participant or reports reconstruction unavailable.

The same rule applies before reconstruction. Claude Code, Codex, Gemini, and
other frontier-agent sessions used for fixture construction, adjudication, or
private report writing are hosted evaluating surfaces when their inference runs
through a remote service. The manifest must name them and bound the opened
evidence they may receive. In this specification, **local participant** means
inference executed locally on the evaluation host, not merely a locally
installed client for a hosted model.

Adjudication records:

- facets recovered with cited episode evidence;
- facets omitted despite available evidence;
- claims added without retrieved support;
- disagreements with the calibration record;
- uncertainty appropriately retained or erased; and
- whether the resulting action can be reconstructed without treating it as
  unquestionable.

The human steward is the final authority for the provisional recalled fixture.
Reviewer or model judgments may propose corrections but do not silently rewrite
the ground truth.

## Operational comparison

Operational evidence is collected independently from retrieval usefulness.

### Installation and readiness

- dependency and artifact acquisition;
- platform and architecture requirements;
- configuration, credentials, ports, and file permissions;
- first schema/index creation;
- cold startup to ready standing; and
- failure behavior when the runtime, service, file, or extension is absent.

### Ingestion and reconciliation

- authoritative bytes read;
- provider database work that is not source-byte bounded;
- initial build latency and resource use;
- append latency and amplification;
- rewrite/truncation rebuild behavior;
- validation work needed to reach `current`;
- concurrent session behavior and retry standing; and
- crash recovery around staging and activation.

### Search and count

- cold and warm end-to-end latency;
- isolated provider query/count latency where observable;
- automatic pre-search reconciliation work;
- exact/unknown match population behavior;
- bounded-result determinism; and
- behavior during provider outage or lock contention.

### Storage and idle cost

- authoritative snapshot bytes, reported separately;
- derived document and index bytes;
- temporary/staging amplification;
- WAL, journal, or Arango volume growth;
- idle and active memory where measurable;
- service/container idle state; and
- compaction or optimization work explicitly invoked.

Measurements name their basis. Serialized document length is not reported as
physical disk use, host cache is not reported as database resident memory, and
container image size is not conflated with corpus-derived storage.

### Removal and recovery

- disable and re-enable;
- unenroll with retained derived state;
- selective corpus/source/state-class purge;
- full provider-derived-state removal;
- provider reinstallation and rebuild;
- residual files, volumes, configuration, credentials, and processes;
- preserved or lost supersession standing; and
- verification that authoritative source bytes remain unchanged.

Removal is evaluated as a user journey, not just a successful database delete
call.

## Execution phases

Stage 2 proceeds through independently reviewable phases.

### Phase A: portable provider contract

Implement the provider boundary and SQLite FTS5 behavior using only synthetic
sources. Replay the Stage 1 identity, standing, count, opening, reconciliation,
concurrency, crash, and lifecycle fixtures against both providers where the
behavior is provider-owned.

Phase A branches from `llm-memory` local `main` at `1826809` or a reviewed
descendant. The preserved Stage 1 feature worktree is not the Stage 2 base.

No real-source authorization is needed for Phase A.

### Phase B: source-format characterization

After the real-source manifest is proposed and authorized, inspect the minimum
necessary Codex and Gemini samples, define their adapters, and replace private
samples with synthetic structural fixtures. Do not commit native conversation
content.

### Phase C: immutable real snapshot

Create the authorized byte-identical snapshot, record its private manifest and
digests, configure concrete corpus partitions, and establish source/opening
standing before indexing.

### Phase D: provider and lifecycle comparison

Build both providers from the same snapshot and run predeclared ingestion,
append/rewrite simulations on disposable copies, concurrency, outage, storage,
search/count, purge, and rebuild journeys.

### Phase E: rationale recovery

Freeze and replay the mixed rationale fixture, open returned evidence, measure
coverage, and run fresh-participant reconstruction without exposing the
calibration artifact.

### Phase F: decision and disengagement

Produce the redacted evidence record, choose exactly one stage decision, purge
the authorized snapshot and both provider projections unless retention was
separately authorized, verify residual state, and record any loss of
repeatability.

Passing one phase does not authorize skipping the next phase's privacy or
authority gate.

## Failure behavior

The experiment fails visibly rather than manufacturing comparability:

- unavailable Arango and unavailable SQLite receive separate provider standing;
- missing FTS5 is unsupported, not replaced by `LIKE`;
- one provider's failed index does not borrow results from the other;
- incomplete reconciliation retains its nested standing;
- a query with an exact count on one provider and unknown count on the other
  preserves both standings;
- source-open failure prevents a result from counting as verified rationale
  evidence;
- an unsupported Codex or Gemini format remains absent from real claims;
- participant hallucination is recorded as unsupported reconstruction, not a
  retrieval hit;
- a private report write failure stops purge until the operator can preserve or
  explicitly abandon the evidence; and
- purge failure reports residual paths, collections, views, volumes, or
  processes without claiming removal.

Neither provider silently becomes the other's fallback. A deliberate retry
uses the same frozen request and records that a retry occurred.

## Trust, privacy, and report boundary

The real evaluation adds at least three sensitive projections:

1. the immutable source snapshot;
2. the Arango derived representation; and
3. the SQLite derived representation.

Fresh-participant prompts and outputs may add a fourth. The authorization
manifest names all permitted locations and processes.

Committed reports exclude by default:

- conversation prose;
- raw query text;
- source paths and project names;
- credentials and ports when identifying;
- raw qualified references;
- participant prompts containing source evidence; and
- database artifacts.

They may retain:

- opaque corpus, source, decision, and query tokens;
- cryptographic digests;
- adapter and provider versions;
- counts and independent standings;
- query vocabulary stratum;
- timings and their measurement basis;
- storage/resource observations;
- redacted rationale-facet outcomes; and
- declared limitations and losses.

Redaction must be atomic: a failed redaction cannot leave a partially written
content-bearing report at the intended public path.

The evaluation environment is local by default. Stage 2 does not itself
authorize sending conversation content to hosted evaluators, embedding APIs,
telemetry, or cloud storage. A real-corpus manifest may separately authorize a
named hosted reconstruction surface and bounded evidence bundle; it cannot
authorize embedding, telemetry, or general cloud retention under this stage.
Evaluating and adjudicating agent surfaces are subject to the same rule as
reconstruction surfaces.

## Vector and hybrid revisit note

Lexical retrieval may fail precisely where rationale recovery matters: a later
participant can ask the right conceptual question using words absent from the
original decision.

If the real fixture shows repeated vocabulary-distant failures across both
lexical providers while aligned queries recover the expected evidence, the
Stage 2 record should recommend a focused semantic-retrieval specification.
That trigger is qualitative evidence, not an automatic threshold.

`sqlite-vec` is the current lightweight candidate because it keeps vectors in a
removable SQLite envelope and is available under permissive licenses, but it is
pre-1.0 and does not produce embeddings. A later specification must separately
choose and version embedding production, privacy, distance semantics, candidate
population standing, rebuild, and hybrid rank fusion.

`sqliteai-vector` is not the initial candidate because its modified Elastic
License introduces commercial and managed-service conditions despite an
open-source grant. SQLite's newer native `vec1` work should be observed but is
not a Stage 2 dependency.

No vector package is added, no embedding is generated, and no vector schema is
reserved in Stage 2.

## Evaluation dimensions

The stage produces a decision record, not an aggregate score. It reports:

- **Fidelity:** returned references open to the expected authoritative evidence.
- **Declared loss:** missing evidence, bounded omissions, unavailable counts,
  and redaction remain visible.
- **Selectivity:** concrete corpus scope and bounded results avoid unrelated
  contamination.
- **Rationale recovery:** evidence supports reasons, alternatives, uncertainty,
  and revisit conditions, not only the terminal action.
- **Dissent retention:** retrieved and reconstructed material does not silently
  erase supported disagreement.
- **Provenance:** every counted rationale claim cites source-opened episodes.
- **Continuity:** a fresh participant can reconstruct and question the inherited
  decision.
- **Isolation:** provider and corpus scope cannot leak results across the
  declared request.
- **Recoverability:** derived state rebuilds from authorized source snapshots
  with honest standing.
- **Unobtrusiveness:** routine use exposes required services, files, locks, and
  reconciliation work without operator theater.
- **Generativity:** retrieval reveals useful connections or questions not
  already present in a curated artifact.
- **Complexity:** dependencies, state classes, failures, privacy projections,
  and removal obligations remain explicit.

Provider differences may favor different dimensions. One benefit does not
cancel an unrelated loss.

## Acceptance gates

Stage 2 is conforming only when evidence establishes all of the following:

1. A provider boundary keeps source identity, enrollment authority, and exact
   opening shared while derived persistence and lifecycle remain provider-owned.
2. Arango and SQLite pass the applicable portable Stage 1 contract fixtures
   without one provider acting as the other's fallback.
3. Provider-specific strategies, analyzers, match semantics, and score ordering
   are declared rather than presented as identical; FTS5 score polarity is
   normalized at the public boundary and retained in the evaluation envelope.
4. SQLite search, bounded results, and per-corpus/aggregate counts use one read
   snapshot and never label partial scope exact.
5. SQLite staging/activation, concurrent writers, crashes, and lock contention
   preserve honest standing and never expose a partial generation as current.
6. Disable, unenroll, selective purge, full removal, and rebuild preserve their
   declared distinctions for both providers.
7. Codex and Gemini native formats are either characterized under the Stage 1
   identity/opening rules or reported unsupported with concrete reasons.
8. The authorized real snapshot is enumerated, partitioned by project/tool,
   byte-identical for both providers, and never modifies original source logs.
9. The mixed rationale fixture freezes queries and source-verified expected
   references before provider results are judged; provider-assisted recalled
   adjudication completes and records an independent full source scan.
10. Documented and recalled decisions retain distinct ground-truth standing;
    unresolved recall is not converted into fact.
11. Aligned, partial, and vocabulary-distant query outcomes are reported without
    turning the strata into corpus ontology, and unresolved fixtures remain
    explicitly unassigned.
12. Each provider's rationale evidence coverage is established through exact
    source opening, not snippets or scores alone.
13. Fresh-participant reconstruction occurs only on explicitly authorized
    surfaces and records supported recovery, omissions, inventions, dissent
    loss, uncertainty, or honest unavailability independently from retrieval
    coverage.
14. Every hosted or locally executed agent used for fixture construction,
    adjudication, private report writing, or reconstruction is named with its
    maximum evidence scope; locally installed hosted clients are not mislabeled
    local inference.
15. Installation, startup, reconciliation, query/count, concurrency, storage,
    outage, purge, rebuild, and full removal costs name their measurement basis.
16. The committed report contains no unauthorized conversation content, query
    text, paths, credentials, raw references, or participant evidence prompts.
17. End-of-stage purge verifies provider artifacts and snapshot disposition and
    declares any lost repeatability or retained sensitive state.
18. Existing qhaway and `llm-memory` suites and the new provider/evaluation
    suites pass at the reviewed endpoints.
19. No vector, hybrid, graph, federation, resident projection, or framework
    delivery capability is implemented under Stage 2 authority.

Failure of a gate produces `repair`, `stop`, or `reframe`; it is not averaged
away by strong performance elsewhere.

## Stage decision

Stage 2 ends with exactly one evidence-backed decision:

```text
continue
repair within the current boundary
stop because the capability did not earn continuation
reframe because the evidence revealed a different problem
```

`continue` means the episodic capability has enough honest operational and
rationale-recovery evidence to consider Stage 3 evidence-linked curated memory.
It does not require selecting a backend. The record may retain Arango, retain
SQLite as a peer, identify a provisional default, or defer selection, provided
those standings remain explicit.

`repair` names a bounded contract, provider, adapter, fixture, privacy, or
lifecycle defect that can be corrected without changing the question.

`stop` means the peer comparison or rationale-recovery capability did not earn
additional implementation.

`reframe` applies when lexical retrieval, episode boundaries, ground-truth
construction, or another observed issue dominates the backend question. A
vector/hybrid recommendation is a possible reframe, not the predetermined
outcome.

Passing Stage 2 does not automatically authorize Stage 3 implementation.

## Explicitly deferred

- vector, hybrid, graph, and learned retrieval;
- embedding generation or external inference;
- dynamic metadata faceting;
- pagination and continuation tokens;
- backend selection as a product default;
- unified episodic and curated persistence;
- shared domain packages or an umbrella repository;
- evidence-linked curated memory writes;
- bilateral federation and cross-project authorization;
- Codex or Gemini framework delivery;
- native Codex-memory modification;
- resident episodic projection;
- background candidate generation; and
- multi-machine or multi-user synchronization.

## Declared losses and limitations

- A broad real snapshot creates an additional sensitive copy even when local
  and short-lived.
- Source adapters interpret episode boundaries; they do not discover natural
  decision units.
- A rationale may span episodes that no bounded lexical query retrieves
  together.
- Written decision records may be cleaner than the reasoning that actually
  occurred and can bias calibration.
- Human recall may be wrong; preserving it as provisional avoids making it
  authoritative but does not make adjudication cheap.
- Query strata depend on observed vocabulary and evaluator judgment.
- BM25 scores are provider-local and are not directly comparable magnitudes.
- Tokenizer, stemming, and stopword differences confound a pure storage-engine
  comparison; declaring them is more honest than pretending equivalence.
- Fresh-participant reconstruction also measures participant behavior, not
  retrieval alone.
- Redacted public evidence cannot independently reproduce private relevance
  judgments without renewed source authorization.
- Purging the immutable snapshot reduces exact repeatability.
- Retaining the snapshot preserves repeatability by extending privacy and
  removal obligations.
- SQLite simplifies service deployment but still introduces a shared mutable
  file, lock behavior, schema lifecycle, WAL/journal artifacts, and corruption
  risk.
- Containerized Arango reduces setup variability but retains runtime, image,
  port, credential, volume, readiness, and removal obligations.
- Exact match counts describe each provider's declared lexical match semantics,
  not a shared semantic population.
- Good rationale evidence does not make the inherited decision true.
- Failure by both lexical providers does not prove that embeddings will solve
  the problem.

## Design success condition

This design succeeds when implementation can compare two honest lexical
providers against the same heterogeneous evidence without weakening source
authority, collapsing independent evaluation dimensions, manufacturing a
backend winner, or reading private history before an explicit manifest is
authorized.

The experiment earns continuation only when future participants can recover not
just what was done, but enough inspectable evidence to understand why, disagree
intelligently, and recognize when the decision should be reopened.
