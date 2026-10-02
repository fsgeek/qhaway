"""Every qhaway command shown in the user-facing docs parses against the real CLI.

Docs drift when code changes: a renamed flag or subcommand leaves the README
showing a command that fails. This finds each `qhaway <subcommand> ...` in fenced
and inline code (sh lines, JSON/TOML arg arrays) and parses it with the real
parser. It checks syntax only, not behavior.
"""
import re
from pathlib import Path

import pytest

from qhaway import cli

ROOT = Path(__file__).resolve().parent.parent
DOCS = ["README.md", "CONTRIBUTING.md", "docs/codex-memory.md"]
_STOP = {"]", "&&", "||", "|", ";", "\\"}


def _chunks(text):
    """Yield (line number, code) for each command-sized piece of code."""
    fence = re.compile(r"^```(\w*)\n(.*?)^```", re.S | re.M)
    for m in fence.finditer(text):
        start = text.count("\n", 0, m.start(2)) + 1
        if m.group(1) in ("", "sh", "bash", "console"):
            for i, line in enumerate(m.group(2).splitlines()):
                yield start + i, line.split(" #")[0]
        else:  # JSON/TOML: an args array can span lines; "]" ends it
            yield start, m.group(2)
    prose = fence.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    for m in re.finditer(r"`([^`\n]+)`", prose):
        yield prose.count("\n", 0, m.start()) + 1, m.group(1)


def _commands(code):
    code = re.sub(r"qhaway(\[\w+\]|@[\w.]+)", "qhaway", code)
    code = re.sub(r"<[^>]*>", "1", code)  # placeholders such as <bytes>
    tokens = re.findall(r'\]|[^\s",\[\]{}]+', code)
    for i, tok in enumerate(tokens):
        if tok.rsplit("/", 1)[-1] == "qhaway" and i + 1 < len(tokens):
            argv = []
            for t in tokens[i + 1:]:
                if t in _STOP:
                    break
                argv.append(t)
            if argv and re.fullmatch(r"[A-Za-z][-\w]*", argv[0]):
                yield argv


def _doc_commands():
    found = []
    for name in DOCS:
        for line, code in _chunks((ROOT / name).read_text(encoding="utf-8")):
            found += [(f"{name}:{line}", argv) for argv in _commands(code)]
    return found


def test_extractor_finds_the_documented_commands():
    # A broken extractor would otherwise pass by finding nothing.
    found = [" ".join(argv) for _, argv in _doc_commands()]
    assert len(found) >= 15
    assert "uninstall --host codex" in found
    assert any(c.startswith("serve --dir") and "--inline-index" in c for c in found)


def test_a_miscased_subcommand_is_checked_not_skipped():
    # Codex review: `qhaway Index` fell outside the extractor and went unchecked.
    assert list(_commands("qhaway Index --check")) == [["Index", "--check"]]


@pytest.mark.parametrize("where,argv", _doc_commands(), ids=lambda x: x if isinstance(x, str) else None)
def test_documented_command_parses(where, argv):
    try:
        cli.build_parser().parse_args(argv)
    except SystemExit:
        pytest.fail(f"{where}: `qhaway {' '.join(argv)}` does not parse")
