# Contributing to qhaway

Thanks for considering a change. qhaway fixes one pain — silent truncation of a
Markdown memory index — and tries to do it completely without sprawling. Changes
that keep that focus are the easiest to accept.

## The short version

1. Fork, branch from `main`.
2. Make your change **test-first** (see below).
3. Run the suite: `uv run --group dev pytest -q` — it must be green.
4. Open a pull request. CI runs the same suite; `main` is protected and will not
   merge until it passes.

## Setup

qhaway is [`uv`](https://docs.astral.sh/uv/)-managed and targets Python 3.14.

```sh
git clone https://github.com/fsgeek/qhaway
cd qhaway
uv sync --group dev      # installs the package + test tooling
uv run pytest -q         # 133 passed, 2 skipped is a clean run
```

The 2 skips are the live-store (`reground`) tests — they need an ArangoDB and a
`~/.yanantin/config/db.ini`, and skip cleanly without them. You do not need
Arango to contribute to core qhaway.

## How changes are expected to land

- **Test-first.** Write a failing test that pins the behavior, watch it fail for
  the right reason, then make it pass. A bug fix starts with a test that
  reproduces the bug.
- **Code and tests in separate commits.** A pre-commit hook enforces this:
  implementation and its validating tests are authored — and signed —
  independently. Commit the test, then the implementation (or vice versa), not
  both at once. If you ever need to bypass it deliberately, that's
  `git commit --no-verify`, and say why in the message.
- **Surgical changes.** Touch only what the change requires. Don't reformat or
  "improve" adjacent code in the same PR — it makes the diff hard to trust.
- **The files are the source of truth.** `MEMORY.md` and the SQLite index are
  both derived and rebuildable; never hand-edit them as part of a change.

## Scope

This version fixes truncation and nothing else. Full-text search, ranking,
write tooling, and audit are real later ideas, deliberately out of scope here —
see the "Design philosophy" section of the README. A PR that adds one of these
is more likely to start as an issue discussing whether it belongs at all.

## Reporting a bug

Open an issue with the smallest reproduction you can manage. If it's a
concurrency or filesystem-edge bug, say what filesystem and platform you saw it
on — those details are usually the whole story.
