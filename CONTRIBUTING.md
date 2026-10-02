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
uv run pytest -q         # a clean run: all pass, 3 skipped
```

The 3 skips are the live-store (`reground`) tests — they need an ArangoDB and a
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

qhaway keeps a memory index within its budget and makes whatever it leaves out
cheap to get back. That is why `recall(query=...)` searches titles and
descriptions. Searching bodies, ranking, write tooling, and audit are real later
ideas, deliberately out of scope here — see the "Design philosophy" section of
the README. A PR that adds one of these
is more likely to start as an issue discussing whether it belongs at all.

## Security review

The `audit` CI job (pip-audit, bandit, zizmor — pinned versions) must stay at
zero findings. Two rules keep it honest:

- **Suppress at the site, with the reason.** A false positive gets an inline
  `# nosec <id>` / `# zizmor: ignore[<audit>]` comment saying *why*, right
  where a reviewer will read it — never a config-file exclusion.
- **Touch a trust boundary, update the threat model.** If your change alters
  what qhaway parses, writes, installs, serves, or connects to, say how
  [`docs/threat-model.md`](docs/threat-model.md) is affected in the PR — even
  when the answer is "it isn't, because…". Vulnerabilities go through private
  reporting (see [`SECURITY.md`](SECURITY.md)), not public issues.

## Releasing

For maintainers:

1. Changes that users will notice add a line under `## [Unreleased]` in
   [`CHANGELOG.md`](CHANGELOG.md) when they merge, written for someone
   installing qhaway. To release, one PR bumps `version` in `pyproject.toml`
   and renames that heading to the new version and date.
   Before that PR, have a reader with no history check the docs: a fresh agent
   on a clean machine, given only the README, installs and uses qhaway and
   reports every place it had to guess. CI checks only that documented commands
   parse (`tests/test_docs_commands.py`); stale claims and missing steps need a
   reader.
2. After it merges, tag the merge commit on `main`: `git tag -s vX.Y.Z` and
   push the tag. The release workflow refuses a tag that doesn't match
   `pyproject.toml` or has no changelog entry, then publishes to TestPyPI.
3. Install from TestPyPI and check the change, then publish those same files
   to PyPI and create the GitHub release from the changelog entry.

## Reporting a bug

Open an issue with the smallest reproduction you can manage. If it's a
concurrency or filesystem-edge bug, say what filesystem and platform you saw it
on — those details are usually the whole story.
