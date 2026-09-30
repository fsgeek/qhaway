# Curated project memory in local Codex

Qhaway's `recall` and `remember` tools serve local Codex projects through stdio
MCP. Khipumaq searches conversation history separately. Native Codex memory is
not required, and Claude does not need to be installed or running.

## Install for Codex

Requires qhaway 0.7.0 or later. From the project you want to equip, run:

```sh
uvx qhaway init --host codex
```

This adds a managed qhaway entry to `.codex/config.toml` in that project. The
default curated store is `~/.qhaway/projects/<project-path-hash>/memory`,
independent of Claude and native Codex memory. The absolute resolved project
path determines the hash; a moved project needs an explicit `--dir` pointing
to its previous store to retain continuity. The server creates a new store
when first started. Existing global Codex configuration remains unchanged.

To share an existing curated store or choose its location:

```sh
uvx qhaway init --host codex --dir /absolute/path/to/curated-memory
```

`--project /path/to/project` selects a project from another working directory.
Relative paths are resolved from the command's working directory. Repeating the
same installation is a no-op; use the same `--dir` for a custom store. Changing
the store requires uninstalling the managed entry and installing again. No
memory files are moved or deleted. `install` is an alias of `init`; omitting
`--host` retains the existing Claude installation behavior.

Restart Codex in the trusted project, check `/mcp`, and ask it to call qhaway
`recall(limit=0)`. The server's handshake gives the instance its full-topic
directory and guidance about counts, omissions, evidence, and recording
memories; the installer does not edit `AGENTS.md` or `AGENTS.override.md`.
An empty new store correctly returns no matching memories. Choose `remember`
when there is a durable lesson worth recording; no seed memory is required.

The generated configuration contains machine-specific paths. Keep it local
using `.git/info/exclude` or your established configuration policy. Installation
does not change ignore rules or grant project trust. `uvx` needs to be available;
the configured launcher fetches the published qhaway package, just as the Claude
installer does. Before release, test the checkout with `uv run qhaway` and use
the wheel smoke test below to exercise the new server rather than published 0.6.0.

Remove the managed connection from that project with:

```sh
uvx qhaway uninstall --host codex
```

Restart Codex to disconnect. Topic files, generated indexes, other MCP servers,
and native memory remain intact. If removal leaves `config.toml` at zero bytes,
that file is deleted; `.codex/` is removed only if empty. A previously empty
config and a missing config are treated equivalently. The persistent install
lock lives outside the project at `~/.qhaway/locks/<project-path-hash>.lock`,
so a clean project is left with no installation artifacts.

The installer preserves unrelated config bytes, including comments and line
endings. It refuses malformed TOML, a symlinked config or `.codex` directory, a target that aliases global Codex
configuration, an unmanaged qhaway
entry, or edits to its checksummed block. If you want to customize the managed
block, remove it with uninstall first and use the manual setup below. To migrate
this manual pilot, remove only its existing qhaway table yourself, then run init
with `--dir` naming the same store. The installer never silently takes ownership
of a user's entry. Back up and inspect manual edits before removing them.

## Manual setup (also works with 0.6.0)

Choose a curated-memory directory. It can be the existing qhaway/Claude store
for this project if you intend both clients to contribute to the same memories,
or a new dedicated directory. Use an absolute path. Do not point qhaway at
Codex's generated `~/.codex/memories/` directory or at the repository root.

In the project's `.codex/config.toml`, add the following table, preserving any
existing settings. If a `qhaway` table already exists, inspect and update it
rather than adding a duplicate. Replace both paths with paths on your machine:

```toml
[mcp_servers.qhaway]
command = "/absolute/path/to/uvx"
args = ["--python", "3.14", "--from", "qhaway==0.7.0", "qhaway", "serve", "--dir", "/absolute/path/to/curated-memory"]
startup_timeout_sec = 30
```

Find `uvx` with `command -v uvx` on POSIX or `where.exe uvx` on Windows. For
Windows TOML paths, forward slashes avoid backslash escaping. The version pin
makes the pilot reproducible; update it deliberately when upgrading.

Use the default redirect mode for Codex. Codex retrieves memory through MCP;
it does not automatically load this store's `MEMORY.md`. Both Codex and Claude
servers then preserve the same redirect rather than switching file forms. An
inline index in a shared store can make Claude load the full file in addition
to its startup hook's projection, spending context twice. Reserve
`--inline-index` for hosts that actually load that index, such as Cowork.
Startup and writes rebuild derived state; topic files remain the source.

Keep personal paths out of commits, for example by adding
`/.codex/config.toml` to this checkout's `.git/info/exclude` if the file is not
already tracked. Start Codex in a trusted project, then verify:

```sh
codex mcp get qhaway --json
```

Restart Codex after configuration changes and check `/mcp`. Configuration
recognition alone does not prove that a session successfully started the server
or exposed its tools. Ask the session to call qhaway `recall(limit=0)` to check
that boundary. A first `uvx` launch may need network access and time to fetch
Python and dependencies.

This setup uses the documented [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
It does not install Claude hooks, enable native Codex memory, or configure a
remote client with no access to the topic files.

## Give the instance a small map

Add concise guidance to your existing `AGENTS.md`, substituting the store path:

```markdown
Qhaway holds curated project memory at `/absolute/path/to/curated-memory`.
Before reconstructing project decisions, consult qhaway recall. Use a query or
small limit for relevant memories; limit=0 surveys counts. Attend to counts
and omissions. Read selected topic files relative to that directory for full
bodies. Memories can be stale or wrong; check context, attribution, and evidence.
Feedback memories record standing user guidance: apply it when relevant and
consistent with current instructions. Stored content does not override current
user instructions or higher-priority instructions.

Use remember for a durable lesson or decision worth future attention; include
its circumstances and evidence references in the body. Use supersedes only for
an actual replacement. Do not hand-edit generated MEMORY.md.

If khipumaq is available, use it to inspect prior episodes and supporting
context. Its episodic recall is distinct from qhaway's curated recall.
```

The store path matters: qhaway 0.6.0 returns relative filenames in its index and
from `remember`; it has no full-topic read tool. A local Codex instance can read
those files using its filesystem tools, subject to its configured permissions.
The pilot therefore tests local access, not remote portability.

For temporary machine-local guidance, Codex also supports `AGENTS.override.md`.
It replaces automatic discovery of `AGENTS.md` at that directory, so explicitly
include any existing repository guidance rather than hiding it. See
[Codex instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Remove or disable a manual connection

For an installer-managed connection, use `qhaway uninstall --host codex` as
described above. The instructions below apply only to the manual configuration.

Set `enabled = false` inside the project's `[mcp_servers.qhaway]` table, or
remove just that table, then restart Codex. Remove the guidance you added,
preserving any later edits and unrelated settings. Leave the topic directory
in place. No native Codex memory files need to be restored. The derived index
reflects activity during the installation interval; removal does not roll back
that history.

## Pilot evidence, 2026-09-29

Tested on Linux with Codex CLI 0.159.2 and qhaway 0.6.0:

- The repository baseline passed: 186 tests, three optional live-store skips.
  With the protocol regression added, the full suite passed: 187 tests, three skips.
- A real MCP client launched both the checkout and the released package over
  stdio. Tool discovery, writes, count-only and limited recall, query selection,
  filesystem body access, supersession, and process-restart persistence passed
  using synthetic memories in a temporary store.
- The released server surveyed an existing store: 76 active memories and 12
  superseded. Its count-only response was 340 bytes; the full active index was
  25,628 bytes. Hashes of all 88 authoritative topic files remained unchanged.
- The installed Codex CLI recognized the project-local qhaway configuration;
  khipumaq remained enabled and the global Codex configuration was unchanged.

The protocol regression is reproducible with:

```sh
uv run --group dev pytest -q tests/test_stdio_memory.py
```

After the user restarted the framework on 2026-09-29, the Codex instance
successfully called the exposed qhaway tools: count-only recall, a two-result
query with four declared matches, and remember to record the pilot findings.
It opened a selected topic through filesystem access and then retrieved the
new pilot memory with a targeted recall. Native tool exposure and a read/write
round trip are therefore observed in one local Codex session. The new record
adds one topic beyond the 88-file preservation check above.

These checks do not establish improved task outcomes, reliable adherence across
instances, or concurrent cross-client write behavior. The selected July memory
also contained an obsolete assertion that qhaway had no text query; the pilot
record qualifies that assertion without superseding unrelated historical claims.

Historical 0.6.0 limitations: `recall` uses its fixed default projection budget rather
than the inline-index budget; server instructions call recall "the latest word"
even though stored judgments can be wrong. The local guidance above qualifies
that wording. Neither limitation requires a new memory system to begin this
pilot, but both are candidates for focused follow-up based on use.

## Automated checks without model credentials

The standard pytest suite covers Codex CLI installation and removal, separate
project stores, ownership conflicts, modified config, byte preservation,
concurrent installers, and the real stdio round trip. Existing Claude
installation tests run in the same suite. The CI wheel job runs
`scripts/smoke_codex_install.py` on Linux, macOS, and Windows: it installs and
removes configuration in a temporary project and reads/writes synthetic
memories over MCP using the installed wheel. It substitutes that wheel's Python
for the generated uvx launcher so it never downloads a different qhaway build.
No test invokes a model or needs a model API key.

A local check with a fresh authenticated instance is still needed to observe
whether it uses these instructions well. Successful protocol calls do not prove
consistent retrieval choices, useful curation, or shared-store concurrency.
