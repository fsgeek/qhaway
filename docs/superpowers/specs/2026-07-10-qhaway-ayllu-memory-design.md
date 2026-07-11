# Ayllu Memory Architecture

**Date:** 2026-07-10
**Status:** Section-approved conceptual draft under architectural review;
implementation requires focused follow-up specs
**Scope:** Architectural umbrella for curated memory, episodic evidence,
cross-project federation, and Claude/Codex delivery
**Product identity:** Deferred

## Decision summary

The system will begin as **federated capabilities**, not as a merged repository
or unified database.

- qhaway retains its focused curated-memory and deterministic-projection
  contract.
- `llm-memory` retains its episodic-ingestion and search contract.
- A thin coordination capability resolves project scope, bilateral sharing, and
  qualified provenance across those systems.
- Claude and Codex receive framework-specific adapters over the same capability
  contracts.
- A shared domain package may be earned later if exercised contracts reveal
  duplication or drift.
- A unified derived knowledge store remains a research hypothesis, not an
  implementation assumption.

This document defines distinctions, invariants, journeys, stage gates, and
declared losses. It deliberately does not settle a database, repository,
package boundary, graph model, or final product name.

### Review posture

During review on the design branch, every architectural decision remains open
to revision. The federated-capabilities decision is selected, not immune from
challenge. Review should find incompatible promises, sharpen authority and
lifecycle seams, and identify focused follow-up specifications. After this
umbrella is approved and merged, later expansion occurs through new decision
records and specifications rather than silent scope growth.

### Decision accounting

**Decision:** Begin with federated capability contracts over the existing
curated and episodic systems.

**Evidence:** qhaway and `llm-memory` already have distinct authoritative
sources, retrieval behavior, operational dependencies, and removal concerns.
Their useful integration does not currently require common persistence.

**What it preserves:** independently useful components, qhaway's small
deployment and removal surface, backend experimentation, and the distinction
between curated assertion and episodic evidence.

**What it gives up:** single-query transactions across memory types, one-place
administration, and an immediately traversable global graph.

**What remains visible:** cross-store resolution failures, duplicated
configuration, semantic differences between frameworks, and the cost of the
coordination layer.

**Failure behavior:** either capability remains locally usable when optional
federated capabilities are absent. A cross-capability operation reports the
specific unavailable source instead of silently narrowing its scope.

**Reversibility:** the coordinator and its declarations can be removed without
migrating or destroying either authoritative corpus.

**Revisit condition:** exercised contracts drift enough to cause failures, or
cross-capability work repeatedly requires consistency the federated model
cannot provide.

### Alternatives considered

**Shared domain core:** Extract identity, scope, provenance, and lifecycle into
a common package used by both systems. This could enforce consistent semantics,
but doing it before federation is exercised risks encoding a prematurely
neutral model and makes both components depend on a new shared lifecycle. It is
an earned consolidation path.

**Unified derived knowledge store:** Ingest curated topics, episodes,
provenance, project relationships, and candidates into one SQLite or Arango
store. This could enable rich search and traversal, but it forces identity,
database, graph, migration, privacy, and removal decisions together. It remains
a research hypothesis with focused revisit triggers.

## Evidence and motivation

The design grows from four observed systems and constraints:

1. qhaway keeps curated Markdown topic files authoritative, builds a
   rebuildable SQLite index, and projects a bounded `MEMORY.md` view that
   declares omissions instead of silently truncating.
2. qhaway's deployment lifecycle is deliberately removable. It modifies only
   self-identified framework configuration, preserves authoritative files, and
   avoids restoring an old `MEMORY.md` over state learned while qhaway was
   active.
3. `llm-memory` indexes conversation-inclusive episodes and exposes lexical
   search plus exact episode recall. Its active ArangoDB implementation uses
   ArangoSearch/BM25 over flat episode documents; it does not yet require graph
   traversal.
4. The projects in the initial deployment form an ayllu: they are distinct but
   overlapping bodies of work whose artificial isolation causes repeated
   reconstruction and hides useful relationships.

Relevant existing artifacts include:

- `README.md`
- `src/qhaway/paths.py`
- `src/qhaway/model.py`
- `src/qhaway/project.py`
- `src/qhaway/reconcile.py`
- `src/qhaway/setup.py`
- `docs/superpowers/specs/2026-06-21-qhaway-mcp-spine-design.md`
- `../llm-memory/docs/superpowers/specs/2026-06-18-conversation-inclusive-memory-design.md`
- `../llm-memory/llm_memory/ingest.py`
- `../llm-memory/llm_memory/search.py`
- `../llm-memory/llm_memory/recall.py`

The initial deployment is Tony's local, single-user collection of related
projects across Claude and Codex. This is an evidence environment, not a
permanent private-product tier. The design remains distributable and must not
depend on undisclosed properties of one machine.

## Purpose

The umbrella system carries useful knowledge across sessions, frameworks, and
explicitly related projects without erasing distinctions between evidence,
interpretation, instruction, and current state.

It supplies four conceptual capabilities:

- **Curated memory:** durable, revisable knowledge deliberately recorded for
  future work. qhaway currently provides this capability.
- **Episodic evidence:** faithful, searchable records of conversations and
  agent activity. `llm-memory` currently provides this capability.
- **Federation:** bilateral, revocable visibility between projects and shared
  collections.
- **Framework delivery:** Claude and Codex adapters that expose the same
  capabilities through framework-appropriate hooks and tools.

The capabilities form one product experience but do not initially require one
repository, process, database, or product identity.

The central promise is **honest availability**, not comprehensive recall:
knowledge appears only within declared scope, carries enough provenance to
inspect its standing, declares when supporting material is omitted or
withdrawn, and can be disengaged without destroying authoritative or locally
created state.

## Participants and inheritance

The system serves an ayllu of distinct participants rather than a single
continuous agent.

- **Active agent instance:** performs work, consults memory, searches evidence,
  and may deliberately record curated knowledge in the active local corpus.
- **Future agent instance:** inherits selected context but remains responsible
  for evaluating applicability and current validity.
- **Human steward:** establishes project relationships, authorizes sharing,
  inspects behavior, and can remove the machinery without losing local state.
- **Background processor:** an optional future participant that may detect
  patterns and emit provisional candidates, never authoritative memories.
- **Maintainer:** evolves adapters and indexes while preserving source material
  and lifecycle guarantees.

Claude and Codex instances do not share an enduring internal self. Continuity
is mediated through artifacts, evidence, and declared relationships. A memory
passed to a future instance is an **inheritance**, not proof that the same
subject remembers.

A receiving participant must be able to determine:

- what is asserted;
- who or what recorded it, when known;
- which project or collection owns it;
- what evidence supported it;
- whether that evidence remains available;
- whether newer material conflicts with it; and
- why it is visible in the active scope.

The system improves participant journeys through:

1. **Continuity:** reduce unnecessary reconstruction of settled context.
2. **Contestability:** make inherited knowledge inspectable and revisable rather
   than silently authoritative.
3. **Generativity:** allow relationships across episodes, memories, and projects
   to expose useful patterns that no single participant encountered directly.

Routine retrieval and index maintenance should not require human routing.
Human attention is reserved for decisions carrying real authority: federation,
trust boundaries, consequential ambiguity, and promotion of provisional
synthesis.

### Curatorial authority

Candidate status describes the authority exercised at recording time, not who
or what generated the words or which reasoning process produced them.

An authorized foreground participant, human or agent, may deliberately invoke
`remember()` and thereby exercise curatorial authority in the active local
corpus. Human approval is not required for every foreground memory. This is the
current qhaway operating model.

A background or analytical process has no curatorial authority. It may emit
only provisional candidates. An authorized foreground participant may later
inspect and explicitly promote a candidate while retaining its origin and
evidence. Neither foreground nor background processes may write through a
mount into another corpus.

## Core distinctions

The system preserves these distinctions even if a future backend stores their
derived representations together:

1. A conversation records what occurred; it does not establish truth.
2. A curated memory records a participant's durable judgment; it may still be
   revised, contested, or superseded.
3. An instruction requests behavior; omitting it may invalidate expected
   operation.
4. A candidate memory is a provisional interpretation with no authority until
   explicitly promoted.
5. A retrieval result identifies potentially relevant evidence; rank does not
   establish correctness.
6. Provenance makes a claim inspectable; it does not make the claim true.

## Core invariants

### Authoritative sources remain outside indexes

```text
topic files          -> authoritative curated memory
conversation logs    -> authoritative episodic evidence
export declarations  -> authority to share
mount declarations   -> authority to consume
derived databases    -> rebuildable indexes
projections          -> bounded, replaceable views
```

No derived database becomes authoritative for identity, ownership, sharing
consent, or provenance.

### Federation is bilateral and consumer-specific

Cross-project access requires both declarations:

```text
source authorizes consumer A to read collection X
consumer A mounts collection X
```

The source-side export names the permitted consumer project identity and
content class. It does not make a collection generally discoverable or
available to every project in the ayllu. Filesystem readability alone does not
grant contextual access. Mounts are read-only in the initial design.

### Disagreement remains recoverable

The system preserves **contestability, not manufactured contrarianism**. It
does not try to make participants disagree. It prevents infrastructure from
making grounded disagreement impossible.

Memory must not compress multiple supported positions into apparent consensus
merely because consensus is easier to summarize, rank, or project.

- Conflicting memories remain distinct and retain provenance.
- Recency does not silently convert a newer claim into truth.
- Supersession is explicit, scoped, and reversible.
- Retrieval does not prefer agreement with the active participant.
- Framework-specific interpretations are not normalized away solely because
  they refer to common evidence.
- A curated projection conflict never exposes one side as an unqualified
  standalone assertion. A complete group is preferred; a bounded subset is
  permitted only inside an explicit envelope that declares omitted positions.

### Disengagement is non-destructive

Removing active machinery does not pretend the installation interval never
occurred. Borrowed behavior and derived access can be removed while locally
authored state remains. Pre-install state may be preserved separately for
intentional restoration.

### Examples do not define the ontology

Categories, sources, statuses, strategies, and relationship names shown in this
document are illustrative unless explicitly identified as behavioral
invariants. Examples cannot silently become a closed taxonomy.

## Initial architecture

```text
authoritative sources
  topic files                 conversation logs
      |                              |
      v                              v
curated index                 episodic index
      |                              |
      +-------- memory facade -------+
                   |
        scope and provenance resolver
                   |
        Claude and Codex adapters
```

Each index remains locally rebuildable. The memory facade does not own source
content and does not require cross-store transactions.

The coordinator is a small owner of operational and derived state, not a
lifecycle authority over either corpus. It may retain:

- resolved-identity and qualified-reference lookup caches;
- reconciliation cursors and freshness observations;
- the last observed state of an export/mount relationship;
- non-content withdrawal observations needed to distinguish withdrawal from an
  unknown missing source; and
- self-identifying framework installation records.

Cached agreements never grant access. Current source and consumer declarations
are rechecked before cross-project access. Deleting coordinator state may lose
historical standing and reduce a reference from `withdrawn` to `missing` or
`unknown`, but it cannot grant access, delete authoritative material, or make a
stale agreement active.

The focused coordinator specification must define its writer topology before
choosing storage. Multiple sessions and multiple consumer projects may update
coordinator state concurrently. It must not default to one shared mutable file
without an explicit concurrency protocol. Distinct immutable artifacts,
append-only records, locks, or database transactions are selected according to
the state transition they protect; a single writer is acceptable only when the
system actually enforces one.

Purge granularity is part of that topology. A purge must name the project,
corpus, and operational-state classes it removes, and must declare when it
erases withdrawal history or other non-rebuildable observations.

A project has a stable identity and declares:

- its local curated corpus;
- its enrolled episodic sources;
- collections it exports;
- collections it mounts; and
- framework adapters it enables.

The facade exposes distinct operations:

- `remember`: write curated memory to the active local corpus;
- `recall`: return a bounded curated projection from permitted corpora;
- `search_history`: search permitted episodic corpora;
- `open_episode`: retrieve exact evidence identified by a search result.

Cross-store provenance uses stable qualified references rather than copied
content. A curated memory may cite an episode without importing the episode
into its topic file or resident projection.

An optional future candidate generator may read permitted evidence and emit
provisional records through a narrow extension interface. It cannot write
curated memory, grant access, or modify authoritative sources.

Candidates, if implemented, live in a separate local candidate corpus rather
than among qhaway's authoritative topic files. The focused candidate-generation
specification must choose its physical representation and lifecycle.

## Domain model

Stable identity is separate from physical location. Paths may change;
filenames, cycle numbers, and session-local sequence numbers are not globally
unique.

The initial episodic evidence environment contains a mixture of source shapes:

- Hamut'ay or `taste_open` append-oriented JSONL records keyed by cycle;
- pichay gateway JSONL events grouped by session, with some episode identifiers
  synthesized from session and sequence; and
- Claude Code project JSONL events carrying session identifiers and, for
  assistant events, source UUIDs.

Codex conversation ingestion is not yet characterized and is not part of the
initial episode-identity guarantee.

- **Project:** a declared working context with a stable identifier.
- **Corpus:** an authoritative collection owned by a project or shared ayllu
  scope. A corpus may contain curated or episodic material.
- **Memory:** a durable curated assertion stored in one authoritative topic
  file.
- **Episode:** an addressable portion of an authoritative conversation record.
- **Evidence reference:** a qualified pointer from a memory or candidate to an
  episode or other inspectable source.
- **Export:** a source-side declaration making selected corpus content classes
  available to named consumer project identities.
- **Mount:** a consumer-side declaration accepting one export.
- **Candidate:** a provisional interpretation that may cite evidence but has no
  curated-memory authority.
- **Suspected conflict:** a derived, provisional observation that assertions
  may be incompatible. It has no projection authority.
- **Curated relationship record:** an authoritative local record that relates
  qualified memory identifiers without modifying the referenced memories. It
  is stored in the consumer's authoritative curated corpus and written only
  through an authorized foreground action. Its authority is limited to the
  owning corpus and scopes that consume it.
- **Projection conflict set:** a curated relationship record that identifies
  supported but incompatible positions. Its membership affects projection.

Qualified references use a logical form independent of backend:

```text
memory://<corpus-id>/<memory-id>
episode://<corpus-id>/<session-id>/<episode-id>
```

Resolvers map logical identifiers to current files or records. Resolution can
produce materially different states, including:

```text
available
withdrawn
temporarily unavailable
missing
superseded
```

This list is illustrative. Implementations must preserve the distinctions they
support and must not collapse an unknown state into a more convenient one.

Every curated memory records enough provenance to answer:

- owning corpus;
- recording participant or process, when known;
- recording time;
- evidence references;
- supersession relationships;
- whether it originated as a provisional candidate.

A curated relationship record separately records its owning corpus, recording
participant and time, relationship kind, and qualified member identifiers. A
consumer may therefore curate a local conflict between a local memory and a
read-only mounted memory without writing through the mount. The foreign source
does not acquire or imply knowledge of that consumer-local relationship.

Episode identity prefers source-native durable event identifiers. An adapter
that must synthesize identity records its adapter name, boundary-algorithm
version, source locator, and content digest. If a source is rewritten or the
boundary algorithm changes, the adapter creates a new derived episode identity
or marks the earlier identity unresolved; it never silently reuses an identity
for different content.

Where a source format permits, an evidence reference retains a source digest or
stable event identifier so resolution cannot silently drift to different
content.

Scope is evaluated at access time. Knowing a valid identifier does not grant
visibility. Resolution requires an active project and the applicable export,
mount, and content-class permission.

Projection conflict sets do not identify a winner. A consumer-local set affects
only projections that authorize its owning corpus; it does not become a global
claim about foreign members. Supersession expresses an explicit lineage
judgment within an authorized scope; it does not erase the earlier record or
automatically apply across corpora.

## Classification and observation

The system distinguishes three forms of classification.

### Structural distinctions

Behavior may depend on relatively stable distinctions such as curated
assertion, episodic evidence, provisional candidate, local, mounted, available,
or withdrawn. The exact vocabulary remains subject to focused specifications.

### Authored facets

Types, roles, tags, and applicability supplied by participants are open-ended,
revisable, and never presumed exhaustive. An uncategorized state remains valid
and visible.

### Derived observations

Search clusters, embedding neighborhoods, inferred topics, recurring patterns,
and suspected conflicts are dynamic outputs tied to:

- the method or model that produced them;
- version and configuration;
- the corpus snapshot;
- generation time; and
- supporting episode identifiers.

They are observations about a corpus, not silent additions to its ontology.
Derived observations never determine access scope, consent, or ownership.
In particular, a suspected conflict does not make memories an indivisible
projection unit until an authorized foreground participant curates a projection
conflict set.

The possible analysis path is:

```text
authoritative evidence
        |
lexical / vector / graph indexes
        |
dynamic observations
        |
provisional candidates
        |
explicitly curated memory
```

Initial implementation requires only the demonstrated lexical episodic-search
contract. Vector, hybrid, and graph retrieval remain possible providers behind
a retrieval contract; they do not automatically inject results into resident
context.

## Projection and retrieval

The resident projection contains curated memory only. Episodic evidence remains
searchable on demand.

Projection is deterministic: the same authoritative memories, curated
relationship records, current declarations, projector version, configuration,
and budget produce byte-identical output. No model decides at session start
what the next participant should know. "One-sided" is determined only by a
curated projection conflict set, never by model judgment or a suspected
conflict observation.

The active budget is partitioned conceptually among:

```text
required projection structure
local curated-memory floor
explicitly mounted collection allocations
declarations of omissions, conflicts, and unavailable sources
```

These are allocation responsibilities, not a fixed byte formula. Mounted
content cannot consume the local floor. Corpus size alone cannot determine
representation.

Projected entries identify their owning corpus. When supported, they may expose
evidence standing such as grounded, partially grounded, unresolved,
unsupported, or conflicted. Such labels describe inspectability, not truth, and
the examples do not define a closed status list.

Curated projection conflict sets require a conflict envelope whenever any
member appears. The preferred rendering includes every materially distinct
position with its source. If the complete set cannot fit, the projector may
include a subset only inside an envelope that declares the number and owners of
omitted positions and gives a route to recall the conflict. A member never
appears as an unqualified standalone assertion.

If even an honest conflict envelope cannot fit, the projector omits every
assertion in the set and emits the shortest truthful conflict declaration the
budget permits.

Withdrawal suppression outranks envelope owner disclosure. After a foreign
member withdraws, the consumer-local relationship record remains local state,
but the envelope identifies only the count and standing of withdrawn positions,
not their former owners, identifiers, or content. If all opposing foreign
members withdraw, a surviving local member still requires an envelope such as
"one opposing position withdrawn" until an authorized foreground participant
explicitly revises or retires the local relationship record. Withdrawal cannot
silently convert a contested claim into an unqualified one.

The local floor reserves capacity for local material; it does not guarantee
inclusion of a particular local assertion. A local conflict member is subject
to the same envelope rule. The projector may fill unused local capacity with
other local memories, and may leave capacity unused when using it would create
a one-sided representation. Honest standing outranks budget utilization.

Omissions are declared by the most useful available dimensions, which may
include source, authored facet, or unresolved conflict. When a budget is too
small for exact declarations, the projector preserves the higher-order fact
that the view is incomplete. A shorter truthful declaration outranks an
apparently complete but partial index.

`recall()` defaults to the active local curated corpus plus deliberately mounted
curated collections.

`search_history()` defaults to the current project's enrolled episodic corpus.
Searching mounted episodic collections requires the caller to name the actual
qualified corpus identifiers in the query. A boolean such as
`include_mounted=true` is insufficient contextual consent. A later named scope
may be supported only if the response expands it into the concrete corpora
considered. This retains friction at the point where conversation crosses a
project boundary.

`open_episode()` resolves one qualified identifier and rechecks current scope.
A previously returned search result is not an access grant after withdrawal.

### Curated and episodic consent

Mounted curated and episodic corpora use different consent moments because
they were authored for different purposes.

A curated-memory mount explicitly names resident delivery, content classes,
and allocation. That durable mount-time act authorizes bounded startup
projection because curated memories were deliberately authored for inheritance.
A generic mount that does not request resident delivery does not place content
in startup context.

An episodic mount authorizes availability, not contextual use. Conversation
records were not authored for inheritance, are more sensitive, and are
potentially much larger. Each cross-project history query therefore names the
concrete episodic corpora it searches. The asymmetry is intentional: consent to
inherit curated guidance is durable, while consent to inspect another
project's conversation is exercised at query time as well as mount time.

### Bounded retrieval contract

A bounded search response declares both what it returned and what it can
establish about the unreturned match population:

```text
query
strategy
match semantics
scope considered
source availability
index freshness and indexed-through position
items returned
total matches
total standing: exact / estimated / lower bound / unknown
results
continuation, when supported
```

The standing values are illustrative; the invariant is that the response does
not represent an estimate or unknown population as an exact count.

This permits a `LIMIT=1` query to act as a probe. A participant can inspect one
result while learning whether the query matched none, one, many, or an
unmeasurable population, then deliberately narrow or change retrieval strategy.

For vector retrieval, every embedded item has some distance. A provider must
declare whether its total describes a similarity threshold, bounded candidate
set, entire searchable corpus, or an unknown population.

The coordinator does not silently switch strategies. Different strategies
retain their retrieval basis, and merged rankings disclose their merge method.
Rank is a retrieval aid, not a correctness judgment.

## Trust and privacy

Filesystem readability is not permission to use content as memory. Repository
configuration alone cannot authorize another project's curated or episodic
corpus.

- Source enrollment and export authority live in local owner-controlled
  configuration.
- A repository may request a mount, but the source export must authorize the
  consumer.
- Cloning a repository does not reproduce another user's approvals, enrolled
  histories, or private mounts.
- Shareable configuration may describe logical identifiers but should not
  contain private absolute paths or credentials.

Authority placement is independent of the eventual package layout:

- an export declaration lives in owner-controlled local configuration
  associated with the source project's canonical root;
- a mount declaration lives in consumer-controlled local configuration
  associated with the consumer's canonical root; and
- neither declaration is inherited from version-controlled repository content.

There is no discovery service in the initial design. A local mount declaration
names both the qualified source corpus and a local source locator. The
coordinator follows that explicit locator to read the source-side declaration,
then verifies that the declaration names the active consumer identity and
content class. This one-time manual locator is the cost of avoiding a registry
while preserving bilateral consent; subsequent validation and reconciliation
are automatic.

Project identity must incorporate local context that repository content alone
cannot spoof. Canonical roots plus locally held declarations may be adequate
for the initial single-user implementation; broader identity and authorization
are deferred.

Conversation logs may be more sensitive than curated memories:

- episodic export is distinct from curated-memory export;
- mounts do not automatically include both;
- cross-project episodic search requires explicit query scope;
- raw episodes are not injected at session start;
- `open_episode()` rechecks authorization; and
- episodic indexes participate in explicit purge behavior.

Indexing creates another local representation of selected conversation data.
That representation can leak information, persist after the source moves, and
require explicit purging. Improved availability necessarily increases the
places from which content may be recovered.

The system does not claim reliable automatic secret detection. Enrollment must
make the additional representation visible. Future redaction may be a source
adapter, but cannot be presented as complete protection.

Retrieved episodes are evidence, not instructions. Their content cannot grant
access, create mounts, promote itself, or alter configuration.

Curated memory has greater behavioral influence but does not become system
policy. Mandatory security or operational enforcement belongs in framework
configuration, permissions, or hooks.

## Framework adapters

Claude and Codex adapters share capability contracts but may differ in
delivery. Each adapter must:

- use supported lifecycle hooks and MCP configuration;
- identify the active project through documented framework context;
- avoid mutating framework-generated native memory stores;
- install self-identifying entries only;
- remove only owned entries; and
- declare capabilities it cannot represent equivalently.

No adapter hides semantic differences solely to present identical
configuration.

### Resident-projection ownership

Exactly one adapter owns resident delivery for each `(project, framework)`
pair. Projection computation and any qhaway-managed `MEMORY.md` remain owned by
the qhaway capability; an umbrella adapter orchestrates and delegates to that
capability rather than introducing a second writer.

Umbrella installation detects an existing standalone qhaway hook, plugin, or
other resident-delivery adapter. It must adopt and supersede that adapter
through an explicit migration or fail visibly; the two never coexist. The
migration preserves the displaced self-identified configuration and records
what assumed ownership. The focused adapter specification defines when
uninstall can safely reinstate the displaced adapter and when it must instead
leave a preserved snapshot plus a visible restoration decision.

The projection writer, SessionStart/SessionEnd delivery, MCP service, and
project resolver must agree on one active corpus identity. Ambiguous ownership
or split resolution blocks resident delivery rather than allowing competing
writes or divergent projections.

Codex's native memory implementation is experimental in the initial evidence
environment and remains independent. The initial Codex adapter exposes the
umbrella capabilities through supported hooks and MCP rather than rewriting
Codex-generated memory state.

## Lifecycle and non-destructive disengagement

Lifecycle operations distinguish stopping behavior, removing integration, and
destroying data:

```text
disable   -> stop active hooks, tools, and background work
uninstall -> remove owned integration while preserving local state
purge     -> explicitly delete selected retained or derived data
```

These operations are not aliases.

### Enrollment and reconciliation

A project explicitly enrolls each episodic source. Initially, enrollment means
only an explicit local declaration plus derived reconciliation state:

```text
source corpus identity
source path
source format
last completely indexed position
```

No central registry or automatic discovery is implied.

Enrollment performs an initial index build. Subsequent reconciliation is
automatic and incremental until removal. A cursor advances only after records
are durably indexed. Losing the cursor causes safe re-indexing, not evidence
loss.

Framework adapters modify only self-identified configuration.

### Normal operation

At session start, the adapter resolves the active project and synchronously
reconciles the local curated source required to build the resident projection.
It validates exports and mounts, but a large episodic backlog, deleted episodic
index, or incomplete episodic reconciliation does not block curated startup.

The adapter may perform a bounded incremental episodic reconciliation during
startup. Work that cannot complete within that bound continues through a
framework-supported later action or leaves history search visibly stale or
incomplete. The initial focused specification must select the concrete
execution mechanism; this umbrella does not imply a daemon.

Reconciliation after enrollment remains automatic. Incomplete work is retried
at subsequent supported lifecycle opportunities and before history search; it
does not wait for a human ingestion command. A focused implementation that
cannot converge under the observed source-growth rate fails its stage gate and
must repair or reframe rather than normalize permanent staleness.

Source availability, derived-index availability, and index freshness are
separate observations. An episodic source can be available while its index is
stale or rebuilding. History-search responses disclose the indexed-through
position or time and one of the supported freshness standings rather than
presenting the indexed subset as current.

Background processing, if later implemented, runs only for enrolled sources
and writes provisional candidate state separately.

`remember()` writes the authoritative topic file before updating derived state.
Index failure cannot make the database appear newer than its source.

### Withdrawal

Removing either side of an export/mount relationship ends access. Borrowed
indexed content and caches are removed. Qualified references remain but resolve
as withdrawn.

Locally authored memories and candidates remain. If they relied on withdrawn
evidence, the affected provenance becomes visibly unresolved. This preserves
local state change without pretending its former grounding remains inspectable.

Consumer-local curated relationship records also remain because they are local
authored state. Their foreign references resolve as withdrawn, and projection
uses the privacy-preserving envelope rule: retain the existence and count of
withdrawn positions without disclosing former owner identity or content.

### Disable, uninstall, and purge

Disabling stops new activity without transforming existing state.

Uninstall removes only owned integration and preserves:

- authoritative topic files;
- authoritative conversation logs;
- curated memories created while active;
- provisional candidates not known to be reproducible; and
- pre-install artifacts retained for intentional restoration.

Rebuildable indexes may remain inert but no longer affect a framework. Deleting
them is an explicit purge operation.

Preserving a candidate across uninstall means retaining it as inert local data.
It is not visible to a framework and is not eligible for promotion while the
interpreting capability is absent. Reinstallation may reactivate it only when
the generating method, schema version, evidence scope, and corpus snapshot
remain interpretable. Otherwise it remains an archival candidate requiring
explicit review or purge.

Reinstallation reconciles authoritative sources and recognizes prior owned
artifacts. It does not duplicate mounts, hooks, memories, or episodes.

### Failure behavior

Failure of a local authoritative source blocks the affected operation and is
reported. Failure of an optional mounted source permits local operation with a
visible partial-availability declaration. No fallback silently changes scope.

At minimum, implementations distinguish the independent facts needed to
represent these situations:

```text
source available, index current
source available, index stale
source available, reconciliation incomplete
source unavailable, prior derived state retained
source unavailable, prior derived state purged
```

The examples are not a required enum. The invariant is that source resolution,
index presence, freshness, and access standing are not collapsed into one
`available` flag.

Previously derived local episodic results may be queried only through an
explicit stale-reading mode that reports their indexed-through position.
Previously derived mounted results are inaccessible when the coordinator cannot
verify the current source export; a cached agreement never extends consent.

## Complexity containment and placement

This boundary is **provisional**. Each implementation stage bears the burden of
showing that it does not reconstruct yanantin inside qhaway.

The initial implementation avoids:

- a central project registry;
- automatic source discovery;
- a resident daemon;
- filesystem watchers;
- cross-store transactions;
- bidirectional synchronization;
- distributed authorization;
- database-managed source ownership; and
- graph traversal infrastructure.

Each capability must answer:

1. Can it remain independently useful and removable?
2. Does qhaway already own the relevant source and invariant?
3. Can its state be rebuilt or preserved without coordinating another service?
4. Does it materially enlarge installation, failure, or recovery behavior?
5. Is the relationship better owned by an umbrella coordinator or yanantin?

Expected initial placement is illustrative but intentional:

```text
qhaway
  curated topic files
  deterministic projection
  local recall and remember
  qualified provenance fields

llm-memory
  conversation adapters
  episodic indexing
  history search and exact episode retrieval

umbrella coordinator
  project identity
  export and mount agreement
  cross-capability reference resolution
  framework packaging

yanantin or later research tier
  graph traversal
  pattern analysis across large corpora
  sophisticated background synthesis
```

A capability moves into qhaway only when doing so simplifies the total system
without weakening deployment and removal guarantees. Shared code alone is not
sufficient justification.

If federation, episodic search, or candidate generation is disabled, qhaway
continues functioning as the small curated-memory projector it is today.

Complexity is reported across operational dependencies, state ownership,
failure modes, removal behavior, and conceptual surface. Those costs are not
compressed into a line count or aggregate score.

## Evaluation

Evaluation produces a decision record, not an aggregate score. Each stage
reports independently on:

- **Fidelity:** retrieved material corresponds to authoritative sources.
- **Declared loss:** bounded outputs expose omitted or unmeasurable material.
- **Selectivity:** relevant scope is available without unrelated contamination.
- **Dissent retention:** supported conflicts remain recoverable.
- **Provenance:** references resolve to exact evidence or an honest failure
  state.
- **Continuity:** a fresh participant can recover prior reasoning without being
  forced to accept it.
- **Isolation:** access requires the declared export/mount relationship.
- **Recoverability:** derived state can be rebuilt without changing sources.
- **Unobtrusiveness:** routine operation does not require index maintenance or
  source routing.
- **Generativity:** the system enables useful connections or questions that
  were not already encoded.
- **Complexity:** new ownership, dependencies, failures, and removal obligations
  remain visible.

A stage decision is one of:

```text
continue
repair within the current boundary
stop because the capability did not earn continuation
reframe because the evidence revealed a different problem
```

No weighted total converts these findings into a verdict.

Evaluation uses real journeys plus deliberate perturbations:

- delete indexes and rebuild them;
- withdraw exports;
- introduce supported conflicting memories;
- change framework;
- limit a search to one result while retaining population standing;
- search an available source through a stale or incomplete index;
- make supporting evidence unavailable;
- distinguish a suspected conflict from a curated projection conflict;
- project a consumer-local conflict spanning local and mounted memories;
- withdraw every foreign side of a consumer-local conflict;
- start with both standalone qhaway and umbrella resident adapters installed;
- update and selectively purge coordinator state from concurrent sessions;
- attempt access without one half of the federation agreement; and
- uninstall and reinstall adapters around state created while active.

The test is whether state remains honest, contestable, and recoverable, not
merely whether an answer still appears.

## Staged delivery

Every stage is independently reviewable and removable. Passing one stage does
not commit the project to the next.

### Stage 0: Baseline

Record current qhaway and `llm-memory` behavior, real retrieval queries,
lifecycle guarantees, known failures, and operational dependencies. Establish
adversarial fixtures for conflict, withdrawal, missing evidence, and isolation.

### Stage 1: Episodic contract

Define stable episode identity and bounded search responses, including retrieval
basis, match semantics, total-match standing, freshness, and exact episode
opening. Characterize identity for each existing JSONL adapter and run the
existing Arango implementation through the contract.

### Stage 2: Retrieval experiment

Implement SQLite FTS5 as a peer backend and compare it with ArangoSearch.
Preserve differences in ranking, match population, latency, ingestion, updates,
operation, and removal. Backend selection is not required for the stage to be
useful.

### Stage 3: Evidence-linked memory

Allow curated memories to reference exact episodes. Verify available,
temporarily unavailable, withdrawn, missing, and superseded provenance without
copying episodic content into curated files.

### Stage 4: Read-only federation

Implement bilateral export and mount declarations. Test local budget protection,
conflict-envelope projection, named-consumer authorization, withdrawal,
consumer-local relationships spanning mounted memories, privacy-preserving
withdrawal envelopes, coordinator writer topology and purge granularity,
consumer cleanup, and preservation of locally created state.

### Stage 5: Codex delivery

Expose the same capabilities through supported Codex hooks and MCP
configuration. Verify single resident-projection ownership, migration from a
standalone qhaway adapter, symmetric removal, and that Codex-generated native
memory remains untouched.

### Later gated work

Vector or hybrid retrieval, background candidates, graph relationships,
instruction projection, shared domain packages, and unified storage require
their own evidence and specification.

## Declared losses and accepted limitations

- Episodic indexing creates another local representation that may leak, outlive
  its source, or require explicit purging.
- Curated memories may be wrong, stale, incomplete, or grounded in evidence
  that later becomes unavailable.
- Projection preserves bounded honesty, not comprehensive awareness.
- Deterministic selection may omit the memory that would have been most useful.
- Lexical retrieval cannot reliably recover semantic similarity expressed in
  different language.
- Vector similarity, if added, observes proximity but does not establish
  meaning or ontology.
- Episode boundaries are source-adapter interpretations, not natural facts
  inherent in conversation logs.
- Sources without durable event identifiers require synthesized identities that
  can become unresolved after rewriting or adapter-algorithm changes.
- Conflict detection is incomplete unless participants or analysis identify a
  conflict.
- Cross-framework delivery cannot guarantee identical interpretation or
  behavioral weight.
- Local path-based project identity is adequate only for the initial
  single-user environment.
- Removal can stop access and preserve state but cannot make participants
  forget content already observed.
- A consumer-local relationship may preserve the fact and count of withdrawn
  opposing positions after their owner and content are suppressed.
- Exact total-match counts may be unavailable for some retrieval strategies.
- Episodic search may be stale or incomplete while curated session startup
  remains current.
- Purging coordinator observations can erase the distinction between a
  previously observed withdrawal and an unknown missing source.
- Migrating resident-projection ownership adds restoration state that must be
  preserved until the displaced adapter is either reinstated or deliberately
  retired.
- Provenance makes a claim inspectable; it does not make the claim true.

## Deferred decisions

- Umbrella product name and repository
- SQLite versus Arango as an episodic default
- Shared domain package
- Unified storage
- Vector or hybrid retrieval
- Conversation graph
- Background candidate generation
- Instruction projection
- Multi-machine synchronization
- Multi-user authorization
- Native Codex-memory integration

## Revisit triggers

These are qualitative evidence, not automatic numeric thresholds:

- Known evidence repeatedly escapes lexical retrieval.
- Participants require broad scans to reconstruct related episodes.
- Cross-project questions require relationship traversal rather than filtering
  or searching.
- Independent capability contracts drift and cause visible failures.
- Installation or removal requires coordination the federated architecture
  cannot express cleanly.
- Qhaway begins acquiring state or lifecycle responsibilities outside curated
  projection.
- Multiple users or machines need to share corpora.
- Native framework capabilities become stable enough to reduce custom
  machinery.
- Instruction growth produces measured omission or adherence failures.
- Background analysis demonstrates useful patterns active participants
  consistently miss.

A trigger opens a new specification. It does not silently expand this one.

## Non-goals

This umbrella specification does not authorize implementation of:

- a merged qhaway/`llm-memory` repository;
- a database migration;
- vector retrieval or RAG;
- a conversation graph;
- automatic memory promotion;
- a central registry or daemon;
- multi-user sharing;
- `AGENTS.md` or `CLAUDE.md` projection; or
- modification of native Codex memory files.

Those capabilities may later earn focused designs.

## Design success condition

The design succeeds if it gives future work stable distinctions, reversible
stages, honest failure states, and enough shared language to test integration
without requiring agreement on database, graph, package, or product identity.

It should make continuation more grounded without optimizing away the friction
needed to disagree intelligently.
