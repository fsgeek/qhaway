# Codex curated-memory pilot

The user authorized autonomous exploration and testing on 2026-09-29. Native
Codex memories are disabled in this environment. Khipumaq is available for
episodic search; qhaway is absent from the tools exposed to this session.

## Decision

Connect qhaway's existing stdio MCP server to this project using an explicit
absolute memory directory. Exercise the protocol in a disposable synthetic
store first. Then enable project-local access to the existing Claude/qhaway
curated store, keeping machine-specific configuration out of version control.
This shared-store choice is an experiment authorized by the user's delegation,
not a new default for all Codex projects.

Alternatives: a separate Codex curated store would isolate writes but duplicate
project knowledge; a general Codex installer would add lifecycle code before
we know whether existing tools suffice. Start with project-local configuration.

## Contract

- Khipumaq remains episodic evidence; qhaway remains selected, revisable memory.
- Use counts and limits to inspect availability without loading every entry.
- Full bodies remain readable topic files; the client must know the store root.
- Test remember, recall, query, limits, supersession, and restart over stdio.
- Do not create synthetic memories in the live store.
- Verify that existing live topic files survive connection unchanged.
- Preserve Codex native memory files and existing MCP configuration.
- No automatic projection injection or Claude hook emulation is required.
- Removal of the project-local MCP entry must leave topic files intact.

## Evidence and limitations

A successful stdio client test establishes protocol compatibility, not model
behavior inside Codex. Verify project-config discovery using the installed
Codex CLI. A newly launched session is required to establish actual tool
exposure if the current session cannot reload its tool list. State that limit
rather than claiming a full end-to-end test.

Record findings, exact commands, and reproducible setup/removal instructions.
Changes to the product itself require an observed failure and a regression
test first. Do not merge or publish as part of this pilot.
