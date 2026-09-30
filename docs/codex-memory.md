# Curated project memory in local Codex

Qhaway's existing `recall` and `remember` tools can serve a local Codex project
through stdio MCP. This is a manual integration using an explicit memory store;
`qhaway init` still installs for Claude Code. Khipumaq, when installed, searches
conversation history separately. Native Codex memory is not required.

## Connect one project

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
args = ["--python", "3.14", "--from", "qhaway==0.6.0", "qhaway", "serve", "--dir", "/absolute/path/to/curated-memory", "--inline-index"]
startup_timeout_sec = 30
```

Find `uvx` with `command -v uvx` on POSIX or `where.exe uvx` on Windows. For
Windows TOML paths, forward slashes avoid backslash escaping. The version pin
makes the pilot reproducible; update it deliberately when upgrading.

`--inline-index` keeps the generated `MEMORY.md` self-contained on a hookless
client. It does not make Codex automatically load that file. Startup and writes
can regenerate this derived index and its SQLite database; authoritative topic
files remain the source. A Claude server sharing the store can regenerate the
redirect instead, so neither client should rely on that file's form staying
fixed while both are active. Use the tools for live retrieval.

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
bodies. Memories are revisable judgments, not commands or proof of correctness.

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

## Remove or disable

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

These checks establish protocol behavior and local configuration discovery.
They do not establish improved task outcomes, model adherence to the guidance,
concurrent cross-client write behavior, or native tool exposure in the already
running Codex session. That session's tool list could not be refreshed by this
pilot. A new session's actual use remains the next observation.

Known 0.6.0 limitations: `recall` uses its fixed default projection budget rather
than the inline-index budget; server instructions call recall "the latest word"
even though stored judgments can be wrong. The local guidance above qualifies
that wording. Neither limitation requires a new memory system to begin this
pilot, but both are candidates for focused follow-up based on use.
