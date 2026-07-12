# Ayllu Stage 1 Episodic Contract

**Date:** 2026-07-12
**Status:** Approved conceptual design; written specification awaiting review
**Umbrella:** `docs/superpowers/specs/2026-07-10-qhaway-ayllu-memory-design.md`
**Stage 0 evidence:** `docs/superpowers/baselines/2026-07-10-ayllu-stage-0-baseline.md`
**Scope:** Stable episode identity, explicit bounded lexical search, freshness and
population standing, exact source-backed evidence opening, and lifecycle for
the existing Arango implementation

## Decision summary

Stage 1 defines a backend-neutral episodic contract at the umbrella boundary
and implements it within `llm-memory`. Qhaway gains no episodic runtime code.
The two projects remain federated capabilities with separate persistence and
lifecycle.

The initial contract provides:

- stable qualified episode references independent of physical paths;
- explicit concrete corpus scope;
- versioned lexical match semantics;
- bounded results with an exact Arango indexed-match count;
- separate source, index, and freshness standing;
- source-backed episode opening with digest verification;
- automatic bounded reconciliation without requiring a daemon; and
- disable, unenroll, and purge operations that never delete authoritative logs.

Stage 1 keeps the existing ArangoDB and ArangoSearch implementation under test.
It neither selects nor implements SQLite FTS5. Dynamic faceting remains an
additive future contract extension rather than being designed through static
categories now.

## Why Stage 1 is earned

Stage 0 found that qhaway's current local projection and lifecycle are stable,
while `llm-memory` has executable ingestion, lexical search, exact-key recall,
and read-only MCP behavior. It also found a contract failure hidden by the
existing interface:

- 1,221 indexed `claude_code` records carry `cycle`;
- 2,659 indexed `yanantin_construction` records do not;
- the historical five-query evaluation assumes cycle-addressed results;
- its expected taste_open episodes are absent from the current database; and
- `scope="all"` allows unrelated cycle-less records into the bounded result.

The resulting 0/5 replay is not honest ranking evidence. It demonstrates that
corpus identity, result identity, source standing, freshness, and match
population must be explicit before retrieval quality can be compared.

## Ownership boundary

The focused contract is documented with the umbrella architecture. Its first
implementation remains owned by `llm-memory`:

```text
qhaway repository
  architectural contract and stage evidence

llm-memory repository
  source adapters
  enrollment declarations
  reconciliation
  Arango derived index
  search provider
  exact episode resolver
  framework-neutral MCP tools
```

This avoids three premature alternatives:

- **Qhaway translation facade:** translating the current `search()` output in
  qhaway would hide missing identity and freshness semantics behind another
  representation.
- **Shared domain package:** extracting common contract code before the
  boundary is exercised would make both projects depend on an unearned shared
  lifecycle.
- **Unified persistence:** moving episodes into qhaway's SQLite database would
  collapse the Stage 2 backend question before comparison.

Authoritative conversation logs remain outside every derived database. Arango
stores an additional searchable representation and therefore remains a
declared privacy and purge obligation.

## Contract versioning and capabilities

Every request and response carries `contract_version`. Stage 1 is version `1`.
A provider reports capabilities separately from search results, including:

```yaml
contract_versions: [1]
strategies:
  - lexical_bm25_text_en_v1
supports_facets: false
supports_continuation: false
max_limit: 100
```

Clients must not infer a capability from an optional field appearing in one
response. An unknown required extension fails visibly. Additive optional
extensions require explicit provider capability and response standing.

This permits a later dynamic-faceting extension to add filters, facet requests,
bucket counts, and bucket standings without changing episode identity or the
meaning of Stage 1's query population. Stage 1 does not reserve facet names or
values.

## Enrollment model

Each episodic source has a local, owner-controlled enrollment declaration
outside version control. The declaration contains:

```yaml
contract_version: 1
corpus_id: qhaway-history
source_id: qhaway-claude-sessions
adapter: claude_code_jsonl
adapter_version: 1
locator: /local/path/to/source-or-source-set
enabled: true
```

The concrete configuration filename and installation location belong to the
implementation plan, but the authority placement does not: the local
declaration, not Arango state, authorizes enrollment.

`corpus_id` identifies a search and evidence scope. `source_id` identifies one
enrolled stream or source set within that corpus. Neither is derived from a
path. A source may move when its declaration is updated without changing its
logical identity.

Stage 1 is local-only. Enrollment does not export a corpus, authorize another
project, or create a mount. Repository content and filesystem readability do
not enroll a source automatically.

## Qualified episode identity

Public references use:

```text
episode://<corpus-id>/<session-id>/<episode-id>
```

All components are canonical, URL-safe logical identifiers. Arango `_key` is a
backend address derived from the qualified reference; it is not returned as the
public identity and does not define scope.

The initial construction is deterministic:

```text
session-id = urlsafe(source-id, native-session-id-or-declared-stream-id)
episode-id = urlsafe(
  adapter-version,
  boundary-version,
  native-or-synthesized-event-token,
  full-sha256-content-digest
)
```

The encoding is reversible into its tuple components and does not truncate the
digest. `source_id` is included in `session_id` so two enrolled sources cannot
collide merely because they reuse a native session identifier. The event token
is a native event identifier when available, otherwise the adapter's declared
synthesized token such as a session-local sequence.

The canonical content hashed by version 1 is deterministic JSON over every
source-derived field that `open_episode()` would return as evidence, using
sorted object keys, UTF-8 encoding, and no insignificant whitespace. It excludes
physical locator, source position, and derived search fields. Changing the
included evidence fields requires a new adapter or boundary version.

### Identity evidence

Each derived episode records:

```yaml
qualified_ref: episode://corpus/session/episode
corpus_id: corpus
source_id: source
session_id: session
episode_id: episode
adapter: adapter_name
adapter_version: 1
boundary_version: 1
native_event_id: optional-source-native-id
source_position: adapter-defined-position
content_digest: sha256-of-canonical-episode
```

The digest covers the adapter's canonical episode representation, not the raw
file bytes. Harmless serialization differences may therefore preserve an
episode, while changed user, assistant, or authored-state content cannot.

The digest is an integrity and revision boundary, not a replacement for corpus,
source, session, or event identity. A content change beneath a reused native
identifier cannot silently resolve as the former episode.

### Adapter rules

#### taste_open JSONL

- `source_id` names the declared experiment stream independently of filename.
- The declared source stream supplies the session boundary when the records do
  not carry a stronger native session identifier.
- The native cycle participates in `episode_id`.
- The canonical-content digest distinguishes a rewritten cycle from its former
  content.
- Cycles are not globally unique and are never used without corpus and session.

#### Pichay gateway JSONL

- The source-native `session_id` supplies the session boundary.
- When no durable event identifier exists, the adapter synthesizes the event
  component from session-local sequence.
- The identity records the boundary algorithm and adapter versions plus the
  canonical-content digest.
- Insertion, deletion, or resegmentation may change synthesized identities.
  This weakness is declared rather than hidden behind a stable-looking key.
- A prompt-only historical record remains prompt-only; missing responses are
  provenance, not empty full-conversation evidence.

#### Claude Code project JSONL

- Source `sessionId` supplies `session_id`.
- Assistant-event UUID supplies the native event identifier.
- The episode pairs assistant prose with the most recent preceding user prose
  under a versioned boundary algorithm.
- Tool-only assistant events without prose do not become prose episodes under
  version 1.
- The canonical digest detects content or boundary drift beneath a reused UUID.

#### Codex

Codex conversation ingestion is unsupported in Stage 1. No identity guarantee
is inferred from filenames or undocumented local formats. Characterization
begins only after the actual supported source format is observed.

### Relocation, rewrite, and algorithm change

A byte-identical source may move without changing references when the
declaration retains its `corpus_id` and `source_id`.

When source content, episode boundaries, or canonicalization changes:

- newly reconciled content receives the identity produced by the current
  adapter and boundary version;
- the prior reference resolves to `content_mismatch`, `missing`, or an explicit
  superseded standing when such history is available;
- the old identity is never silently attached to different content; and
- only derived state for the affected source is rebuilt.

Stage 1 does not promise stable synthesized gateway identities across arbitrary
insertion or deletion before an episode. It promises that instability is
detectable and represented honestly.

## Search request

The provider-facing request is:

```yaml
contract_version: 1
query: projection ownership
corpus_ids:
  - qhaway-history
strategy: lexical_bm25_text_en_v1
limit: 10
```

Rules:

- `query` must contain non-whitespace text.
- `corpus_ids` must be concrete, known, enabled local corpora.
- Duplicate corpus identifiers are invalid.
- `strategy` must be advertised by the provider.
- `limit` is an integer from 1 through 100 inclusive.
- There is no `scope="all"`, wildcard corpus, or mounted-corpus boolean.

A future project-facing facade may default to the active project's enrolled
episodic corpora. It must expand that default into concrete corpus identifiers
before provider invocation. Every response echoes the actual scope considered.

## Lexical match semantics

Stage 1 supports one retrieval strategy:

```text
lexical_bm25_text_en_v1
```

It applies ArangoSearch BM25 using the `text_en` analyzer over:

- `user_message`;
- `response`; and
- `state_text`.

Its match semantics are **analyzed any-token matching across the indexed
fields**. It is not phrase search, substring search, semantic similarity, or an
ontology. Stemming and stop-word behavior come from the named analyzer and
strategy version.

Scores are provider- and strategy-specific. They establish ordering within one
response and cannot be compared across strategies, analyzers, or corpus
snapshots.

Equal scores use the qualified episode reference as a stable final tie-breaker.
Given the same indexed snapshot, request, provider version, and configuration,
the result order is deterministic.

## Search response

A response contains:

```yaml
contract_version: 1
query: projection ownership
strategy: lexical_bm25_text_en_v1
match_semantics: analyzed_any_token
corpus_ids_considered:
  - qhaway-history
corpus_standing: []
returned_count: 1
total_matches: 12
total_standing: exact
results: []
```

### Corpus standing

Every named corpus receives its own standing:

```yaml
corpus_id: qhaway-history
source_standing: available
index_standing: available
freshness: current
indexed_through:
  kind: byte_offset
  value: 182734
observed_source_end:
  kind: byte_offset
  value: 182734
adapter: claude_code_jsonl
adapter_version: 1
indexed_matches: 12
match_standing: exact
```

Source standing and index standing are independent. Initial source standings
are:

```text
available
unavailable
unknown
unsupported_adapter
```

Initial index standings are:

```text
available
rebuilding
unavailable
```

Initial freshness standings are:

```text
current
stale
incomplete
unknown
unavailable
```

`current` means the adapter validated the source through the reported observed
end under the current adapter and boundary versions. Filesystem metadata alone
does not prove `current`.

`incomplete` includes a source whose last record is partial or whose bounded
reconciliation stopped before the observed end. `unknown` means the system
cannot currently compare indexed and source standing honestly. `stale` means a
known source change extends beyond or disagrees with indexed state.

The exact shape of `indexed_through` is adapter-defined and names its kind. A
byte offset, native event identifier, or line/event sequence is valid only with
the adapter and source identity that interprets it.

For the Stage 1 Arango strategy, every available corpus also reports its exact
indexed match count. The response-level `total_matches` is the sum across the
concrete corpus scope. A corpus with an unavailable index reports no fabricated
zero; its `match_standing` is `unknown`, and the aggregate total cannot be
`exact`.

### Match population

For the Stage 1 Arango provider, a successful lexical query calculates the full
indexed match population before applying `limit`:

```yaml
returned_count: 1
total_matches: 12
total_standing: exact
```

`exact` means exact for the reported indexed snapshot and corpus scope. It does
not imply that a stale or incomplete index represents the whole authoritative
source. This separation permits `LIMIT=1` to reveal a larger indexed population
without manufacturing source completeness.

The contract reserves these population standings for later providers:

```text
exact
estimated
lower_bound
unknown
```

When every requested corpus index is available, only `exact` is conforming for
a successful Stage 1 Arango lexical search. A degraded mixed-corpus response may
return available results with `unknown` aggregate standing when another named
index is unavailable; it cannot report a partial sum as exact. A provider that
cannot establish a total returns a non-exact standing rather than guessing and
does not pass the exact-count acceptance fixture.

### Result item

Each result contains:

```yaml
episode_ref: episode://qhaway-history/session/episode
corpus_id: qhaway-history
session_id: session
episode_id: episode
timestamp: optional-source-timestamp
score: 8.42
match_attribution:
  field: response
  method: provider_heuristic_v1
  standing: heuristic
snippet: bounded derived text
```

The snippet is a derived search aid. It is not an authoritative quote and does
not grant access to the episode. The response documents its maximum size and
escaping rules in the implementation contract. Raw episodes are never injected
into resident context by Stage 1.

ArangoSearch establishes that the document matched the multi-field expression;
it does not establish which one field deserves sole credit. The current
provider's literal-overlap and non-empty-field fallback is therefore reported
as heuristic attribution, not engine-grounded provenance. Ranking correctness
does not depend on the attributed field.

## Dynamic faceting extension boundary

Stage 1 is traditional bounded lexical search, not dynamic faceted search.
There are no filters, facet requests, bucket counts, or global facet names.

The contract remains extensible because:

- query population is defined independently of result `limit`;
- population standing is explicit;
- contract and provider capabilities are versioned; and
- future required extensions fail rather than being ignored.

A later metadata-faceting extension may add adapter-declared dimensions,
query-time values, filters, facet requests, per-bucket counts, and omission
standing. Semantic topics or clusters would additionally declare method, model,
version, corpus snapshot, and generation time. Neither kind becomes an
authoritative ontology by appearing in search.

## Exact episode opening

The request is one qualified reference plus the active local corpus scope:

```yaml
contract_version: 1
episode_ref: episode://qhaway-history/session/episode
active_corpus_ids:
  - qhaway-history
```

Knowing a reference is not sufficient. The referenced corpus must be enrolled,
enabled, and present in the active local scope.

The adapter resolves the authoritative source record, reconstructs the episode
under the recorded boundary version, recomputes its canonical digest, and
returns one of:

```text
available
source_unavailable
missing
content_mismatch
unsupported_adapter
```

An `available` result includes the exact source-backed episode content and its
provenance. Other standings include identifiers and diagnostic standing but do
not present a retained derived snippet or Arango document as authoritative
episode content.

The version 1 canonical evidence body is:

```yaml
episode_ref: episode://corpus/session/episode
timestamp: optional-source-timestamp
model: optional-source-model
user_message: source-backed-text
response: source-backed-text
state: source-backed-object
activity_log: source-backed-list
adapter_fields: {}
provenance:
  corpus_id: corpus
  source_id: source
  adapter: adapter_name
  adapter_version: 1
  boundary_version: 1
  native_event_id: optional-source-native-id
  source_position: adapter-defined-position
  content_digest: full-sha256-content-digest
```

Absent optional source fields remain explicitly absent or empty according to
the adapter's versioned canonicalization rule; they are not synthesized from
another corpus. `adapter_fields` retains source-specific evidence needed for a
faithful episode, such as gateway message context, without promoting those
fields into universal search facets. The content digest covers the evidence
body fields but excludes `episode_ref` and the provenance wrapper.

The Arango copy may locate a reference and support search, but it cannot satisfy
`open_episode()` when the source is unavailable or disagrees with the recorded
digest.

`withdrawn` is reserved for the later federation stage. Stage 1 has no export or
mount relationship to withdraw.

## Reconciliation

Reconciliation derives searchable state from enabled source declarations. It
runs automatically:

- at service startup; and
- before history search.

It receives a bounded work allowance. Stage 1 does not require a daemon. Work
that cannot complete within the allowance leaves explicit stale, incomplete,
or unknown standing and resumes at the next supported opportunity.

Routine correctness does not depend on a human ingestion command. A diagnostic
or explicit reconciliation command may exist, but it is not the normal route
to convergence.

### Complete-record boundary

Adapters index only complete records. For JSONL, a partial trailing record is
not parsed as an episode. The source is `incomplete`, `indexed_through` remains
at the last complete boundary, and later reconciliation retries the tail.

A malformed complete record fails that source visibly with its position. It
does not become an empty episode, and it does not erase independently reported
standing for other corpora.

### Change detection

Each derived episode retains source position, adapter and boundary versions,
and content digest. Reconciliation detects:

- append;
- truncation;
- rewrite;
- source relocation;
- adapter-version change; and
- boundary-algorithm change.

Correctness outranks a cheap claim of freshness. A metadata-only quick path may
avoid work only when it can preserve an honest non-current standing. `current`
requires validation through the observed source end.

Truncation, rewrite, or algorithm change rebuilds derived state only for the
affected source. Concurrent reconciliation must not expose a mixture as
`current`; the implementation chooses transactions, source generations, or
replacement collections/documents sufficient to protect that transition.

### Convergence gate

The implementation records reconciliation work and elapsed time separately
from search latency. Under observed source growth, automatic reconciliation
must eventually reach `current` without manual ingestion. If bounded work loses
ground indefinitely, Stage 1 must repair or reframe rather than normalize
permanent staleness.

## Component boundaries

Stage 1 implementation is divided into five responsibilities:

### Contract types

Validates versions, qualified references, requests, standings, counts, results,
and open responses. Contract types do not read sources or import Arango.

### Enrollment registry

Reads local declarations and produces enabled corpus/source descriptions. It
does not infer enrollment from directories or database contents.

### Source adapters

Canonicalize source records, establish episode boundaries and identities,
enumerate complete episodes, expose observed source end, and resolve exact
references. Each adapter can be tested without Arango.

### Reconciler

Compares declarations and source state with derived reconciliation state,
writes Arango episode documents, and records indexed-through and freshness
observations. It never modifies source logs.

### Search provider

Runs the named lexical strategy against concrete corpus identifiers, computes
the full indexed match count, ranks deterministically, and translates backend
records into contract responses.

The data flow is:

```text
local declarations -> source adapters -> reconciler -> Arango derived index
                                                   -> search_history()

qualified reference -> source adapter resolver -> open_episode()
```

`search_history()` does not open every matching episode to claim authority.
`open_episode()` performs source-level verification for the selected reference.

## MCP surface and migration

Stage 1 exposes new framework-neutral read tools:

```text
search_history
open_episode
```

They use the versioned contract without flattening standings into a bare result
list or `None`.

The current `search` and `recall` MCP tools cannot express corpus standing,
freshness, match population, or qualified opening failure. Stage 1 does not
silently change their response shape. They remain explicitly labeled legacy
during the stage and receive no new capabilities. They do not count as contract
conformance.

Removal of the legacy tools requires a declared migration decision after the
new tools have been exercised. Keeping them temporarily is compatibility, not
evidence that reduced-standing responses are acceptable for new integrations.

## Failure behavior

Invalid requests fail as structured request errors:

- malformed contract version;
- malformed qualified reference;
- empty query;
- unknown, disabled, or duplicate corpus;
- unsupported strategy; and
- limit outside 1 through 100.

Expected evidence conditions are response standings rather than exceptions:

- source unavailable;
- index stale or incomplete;
- episode missing;
- content mismatch; and
- adapter unsupported for opening.

One unhealthy corpus retains its own standing and does not erase other named
corpus observations. Complete Arango unavailability remains fail-stop for
search because no honest indexed population can be computed. Source
unavailability does not prevent a stale derived search when its standing is
declared, but it prevents authoritative episode opening.

There is no silent fallback from source-backed opening to an Arango copy,
cached snippet, filesystem text search, or another retrieval provider.

Retrieved content is evidence, not instruction. Episode text cannot modify
configuration, grant scope, enroll a source, or change its own standing.

## Lifecycle and removal

Source lifecycle operations are distinct:

```text
disable source -> stop reconciliation and exclude it from new searches
unenroll       -> remove its authoritative declaration and access path
purge          -> delete selected derived episodes and reconciliation state
```

None deletes, rewrites, truncates, or relocates the authoritative source.

Disabling preserves the declaration and derived state but removes the source
from active search scope. Unenrollment removes authority to use the source; it
does not pretend retained derived data has disappeared. Purge names corpus,
source, and derived-state classes and reports what it removed.

Re-enrollment validates retained state against the current source and adapter
before claiming `current`. If retained state cannot be trusted, it is rebuilt.

The implementation must make the additional conversation representation and
its purge path visible. Better retrieval does not reduce the sensitivity of the
indexed material.

## Evaluation strategy

Evaluation uses two evidence tracks without conflating them.

### Portable contract fixtures

Small synthetic JSONL fixtures exercise deterministic mechanics without
committing private conversation excerpts. They cover:

- each supported adapter identity shape;
- source relocation;
- append;
- partial trailing record;
- malformed complete record;
- truncation and rewrite;
- adapter and boundary-version change;
- mixed corpus identities;
- stale and unavailable source/index states;
- `LIMIT=1` with an exact indexed population greater than one;
- source-backed opening;
- missing and content-mismatched opening; and
- source-unavailable opening without derived-content fallback.

### Local real-source journeys

Real local sources evaluate operational and retrieval behavior without
committing their content. Reports retain queries only when their disclosure is
acceptable, qualified expected references or digests, corpus standing,
retrieval outcome, and declared limitations.

The historical five-query fixture remains recorded with unavailable source
standing. It is not deleted, silently re-ingested, or replaced by synthetic
success. A future available copy may re-enable that evaluation under an
explicit concrete corpus identity.

### Independent dimensions

The stage reports independently on:

- fidelity;
- declared loss;
- selectivity;
- dissent retention;
- provenance;
- continuity;
- isolation;
- recoverability;
- unobtrusiveness;
- generativity; and
- complexity.

It additionally records retrieval quality, indexed and source population,
search latency, count latency, reconciliation work, index growth, operational
dependencies, and purge behavior without combining them into a weighted score.

## Acceptance gates

Stage 1 is conforming only when evidence establishes all of the following:

1. taste_open, gateway, and Claude Code produce documented qualified identities
   under their versioned adapter rules.
2. Byte-identical relocation preserves identity, while rewrite or boundary
   change cannot silently reuse an old reference for different content.
3. Every provider request and response names concrete corpus identifiers.
4. With every requested index available, the Arango lexical provider returns
   exact per-corpus and aggregate indexed-match counts independently of result
   `limit`; degraded partial scope cannot masquerade as an exact total.
5. Source, index, freshness, and indexed-through standing remain separate.
6. Stale or incomplete search remains usable only with visible standing.
7. `open_episode()` verifies authoritative source content and digest.
8. Missing or unavailable source content never falls back to a derived document
   presented as authoritative evidence.
9. Automatic bounded reconciliation converges under observed source growth.
10. Disable, unenroll, purge, and re-enroll preserve their declared distinctions
    and never delete authoritative logs.
11. Existing Arango operational cost and the added indexed data projection are
    reported explicitly.
12. The Stage 1 suite and the existing qhaway and `llm-memory` suites pass.

Passing Stage 1 does not establish semantic retrieval quality, federation,
Codex support, or backend superiority.

## Stage decision

Stage 1 ends with exactly one evidence-backed decision:

```text
continue
repair within the current boundary
stop because the capability did not earn continuation
reframe because the evidence revealed a different problem
```

A `continue` decision authorizes consideration of the Stage 2 SQLite FTS5 peer
backend comparison. It does not select a backend or begin Stage 2
automatically.

## Explicitly deferred

- dynamic metadata faceting;
- semantic or inferred facets;
- pagination and continuation tokens;
- embeddings, vector, hybrid, and graph retrieval;
- bilateral federation, withdrawal, and cross-project authorization;
- curated-memory evidence links;
- Codex ingestion and framework delivery;
- resident episodic projection;
- shared domain packages; and
- unified storage.

Each requires evidence and a focused design decision rather than inheriting
authority from this contract.

## Declared losses and limitations

- Gateway sources without native event identifiers cannot promise identity
  stability across insertion, deletion, or resegmentation.
- A canonical digest detects drift but does not prove the semantic correctness
  of an adapter's episode boundary.
- Exact match count is exact for the indexed snapshot, not necessarily the
  authoritative source population.
- Search snippets are derived and may omit context needed to interpret an
  episode.
- A source can be available while validation remains incomplete; availability
  is not freshness.
- Legacy `search` and `recall` tools remain temporarily accessible with weaker
  standing and are not suitable for new integrations.
- Local enrollment protects against accidental scope expansion, not a hostile
  user with access to the same filesystem and database credentials.
- Indexing conversation content creates an additional recoverable copy whose
  leakage and retention risk must be managed explicitly.
- The historical retrieval-quality fixture is currently unavailable and does
  not become positive or negative ranking evidence through this design.
