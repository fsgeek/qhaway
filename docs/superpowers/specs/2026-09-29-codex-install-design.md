# Supported local Codex installation

User authorized implementation through completion, with no status check-ins.

Extend init/install/uninstall with `--host codex` and `--project PATH` (default
cwd). Existing invocations continue targeting Claude unchanged. Codex install
writes only the project's `.codex/config.toml`, registering the existing stdio
server with an explicit absolute store. `--dir PATH` selects a shared or separate
store; without it use `~/.qhaway/projects/<sha256 of resolved project>/memory`.
This avoids dependence on Claude paths, hooks, or environment variables.

The server advertises the configured store root and explains bounded retrieval,
full-topic access, and revisable judgments. Do not modify AGENTS files or native
Codex memory. Initialization only wires configuration; serving provisions the
store. Use default redirect mode so a shared Claude store does not acquire an
inline index in addition to its hook projection.

Use an appended, clearly delimited, checksum-protected TOML block. Parse both
original and proposed documents with stdlib tomllib. Preserve all unrelated
bytes. Refuse malformed config, unmanaged qhaway entries, modified owned blocks,
or a changed requested store. Uninstall removes only an intact owned block and
preserves memories. An existing manual pilot entry needs explicit removal before
managed installation; do not silently adopt ownership. Atomic writes and a
per-project install lock under ~/.qhaway/locks serialize qhaway installers.
Delete a zero-byte config after removal and remove its parent only when empty;
pre-existing empty configs are equivalent to missing ones. Do not claim exclusion of
uncooperative external config editors.

Alternatives: global Codex registration risks the wrong store in other projects;
AGENTS rewriting adds another ownership surface; a full TOML editor dependency
is unnecessary for one appended table. Choose project-local wiring and server
instructions. No model API or cloud credentials are needed for CI.

Validation: CLI behavior, independent default store, idempotence, uninstall,
foreign settings/comments, custom path, invalid/modified/unmanaged config,
concurrent installers, real stdio tool discovery and read/write, and wheel
installation. Existing Claude tests remain mandatory. Model behavior remains
local observational validation, not an asserted CI guarantee.
