"""Compare Claude Code's MEMORY.md load caps with the ones qhaway assumes.

Usage: python scripts/check_cc_limits.py [path-to-claude-binary]

Claude Code keeps the caps in one block next to the file name, e.g.
`cp="MEMORY.md",mF=200,Ule=25000` (2.1.304); minified names change between
builds, so the pattern anchors on the string, not the names. Exit 0 if the caps
match qhaway's, 1 if they differ, 2 if the block can't be found (check by hand).
"""
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from qhaway.cli import LOADER_BYTES, LOADER_LINES  # noqa: E402

_BLOCK = re.compile(rb'"MEMORY\.md",[A-Za-z_$][\w$]*=(\d+),[A-Za-z_$][\w$]*=(\d+)')


def main(argv):
    target = Path(argv[1]) if len(argv) > 1 else Path(shutil.which("claude") or "")
    if not target.is_file():
        print(f"no Claude Code binary at {target!s}")
        return 2
    match = _BLOCK.search(target.resolve().read_bytes())
    if not match:
        print(f"MEMORY.md caps not found in {target}; check by hand")
        return 2
    lines, size = int(match.group(1)), int(match.group(2))
    print(f"Claude Code ({target}): {lines} lines, {size} bytes")
    if (lines, size) != (LOADER_LINES, LOADER_BYTES):
        print(f"qhaway assumes {LOADER_LINES} lines, {LOADER_BYTES} bytes: update LOADER_LINES/"
              "LOADER_BYTES in src/qhaway/cli.py and the README")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
