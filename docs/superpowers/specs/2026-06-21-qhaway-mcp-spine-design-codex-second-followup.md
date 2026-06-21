# Second Follow-Up Review: Qhaway MCP Spine Design

**Date:** 2026-06-21
**Target spec:** `2026-06-21-qhaway-mcp-spine-design.md`
**Reviewer:** Codex
**Status:** Follow-up after second spec update

The latest update resolves the prior follow-up findings in substance:

- FUP-1 is addressed by changing the regression guard from "tests pass unchanged"
  to "cure invariants are preserved and tests are retargeted."
- FUP-2 is addressed by rewriting the Error handling section so MCP failures are
  structured tool errors, not success strings.
- The architecture row for `server.py` now names `project_slice_with_overflow`.

One remaining implementation contract is still underspecified.

## Findings

### SFUP-1: `--check` still needs an explicit CLI home after `index` becomes a reconcile alias

**Severity:** Medium

The spec still references `--check` as the CLI mechanism that surfaces dangling
links and orphan visibility, and the MCP surface correctly excludes a `check`
tool. But after OQ-3, `qhaway index` becomes a deprecated alias for
redirect-writing `reconcile`, and the regression guard retargets old `index`
tests away from the full-projection CLI surface.

That leaves the non-writing check surface ambiguous. An implementer can infer
several plausible shapes:

- keep `qhaway index --check` for backward compatibility even though `index`
  otherwise aliases `reconcile`;
- add `qhaway reconcile --check`;
- add a dedicated `qhaway check`;
- keep check logic only as lower-level test/API behavior.

Those choices differ in user-facing CLI contract, docs, and tests.

**Recommendation:** Pin the CLI shape explicitly. The cleanest option is likely a
dedicated `qhaway check --dir ...` command, with `qhaway index --check` either a
deprecated compatibility alias or removed intentionally. In either case, state
where the tests for dangling links, overflow-before-projection, and orphan
`MEMORY-<ts>.md` visibility should land.

## Minor Cleanup

The spec currently ends with a stray closing code fence line:

```text
```
```

Remove it so Markdown renderers do not produce an empty or unbalanced final code
block.
