"""Entry point for the `qhaway` command.

This is a packaging skeleton: the implementation (parse / model / project) is the
next phase and is intentionally not present yet. The CLI is wired so the package
builds and installs, but it tells the truth about its state rather than pretending
to work — consistent with the project's no-silent-lies premise.
"""

import sys


def main() -> int:
    sys.stderr.write(
        "qhaway is not implemented yet (v0.1.0 is a packaging skeleton).\n"
        "Design: docs/superpowers/specs/2026-06-20-qhaway-mvp-design.md\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
