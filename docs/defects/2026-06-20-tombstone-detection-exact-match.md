# Defect: tombstone detection uses exact-match, real names are prefix-form

**Found:** 2026-06-20, by running `qhaway index` against the live hamutay memory
dir (137 files) and reading the output — NOT caught by the 19 green unit tests.
**Severity:** real. 14 superseded handoffs leak into the projected MEMORY.md,
eat budget, and crowd out live memories (the run omitted 19 live `project`
memories while carrying 14 dead ones).
**Role note:** diagnosed by Claude (critic). Fix is one line in `parse.py`
(code-author's lane: GPT). The pinning test is the test-author's lane (Gemini).
Reported with exact cause + fix so each model has only the authorship to do.

## Symptom

`uv run qhaway index --dir <hamutay memory> --dry-run` emits 14 lines whose
description begins `SUPERSEDED — see ...` in the body of the index. Per spec
projection rule step 1, tombstoned/superseded nodes must be excluded from the
default `status=live` slice and declared in the footer (`+N superseded memories
hidden`). Neither happens: they appear in the body, and there is no superseded
footer line.

## Root cause (proven, not guessed)

NOT in the projection. `project.py:project_slice` is **correct** — line 29
filters `row["status"] == status` (default `"live"`), and lines 33–40 build
`hidden_superseded` for the footer. If a node's status were `"superseded"` it
would be handled correctly.

The fault is upstream, in detection — `parse.py:125`:

```python
TOMBSTONE_NAMES = {"SUPERSEDED", "DELETED"}
def _status(name: str | None) -> str:
    if name and name.strip().upper() in TOMBSTONE_NAMES:   # <-- exact set membership
        return "superseded"
    return "live"
```

This requires `name` to EQUAL `"SUPERSEDED"`. But real tombstone names in the
corpus are the full redirect string, e.g.:

```
name: SUPERSEDED — see instructions_for_next_20260330.md
```

`"SUPERSEDED — SEE ...".upper() in {"SUPERSEDED", "DELETED"}` is `False` (set
membership is exact, not prefix). So **all 14 tombstones parse as
`status="live"`**, pass the correct filter, and land in the body.

## Fix (one line)

Prefix-match instead of equality:

```python
def _status(name: str | None) -> str:
    if name and name.strip().upper().startswith(tuple(TOMBSTONE_NAMES)):
        return "superseded"
    return "live"
```

(`str.startswith` accepts a tuple of prefixes.)

## Why the suite missed it (the deeper finding)

The unit tests are green because their tombstone fixture almost certainly uses a
**bare** `name: SUPERSEDED` — the idealized shape — not the real prefix-form
`name: SUPERSEDED — see X.md`. The fixture doesn't match the data. This is the
same root cause as the missing end-to-end test: *the suite verifies an
idealized shape the corpus does not actually have.*

## Tests to add (Gemini)

1. **Unit (turns this bug red):** a parse fixture whose frontmatter `name` is
   `"SUPERSEDED — see other.md"` (the REAL prefix-form, not the bare word) must
   yield `status == "superseded"`. Add a `"DELETED — ..."` variant too.
2. **End-to-end / golden-file (the category the suite lacks):** build a small
   frozen golden corpus containing the real pathologies (prefix-form tombstones,
   unquoted-colon YAML, a dangling `[[wikilink]]`), run `index` to write the
   file, read the WRITTEN MEMORY.md back, and assert the spec contract on the
   artifact: under budget; every line matches `- [Title](file.md) — hook`;
   **zero `SUPERSEDED` lines in the body**; a `+N superseded memories hidden`
   footer line present; declared-omission accounting `(shown + declared) == live
   total`. This is the test whose absence let a real bug pass 19 green checks.
