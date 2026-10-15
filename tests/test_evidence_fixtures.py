"""yanantin's evidence verifier reads qhaway's `retracts:` and `supersedes:` to
report a cited memory as withdrawn or superseded. These are its fixtures
(tests/fixtures/evidence/SOURCE.md). qhaway must read the same files the same
way, and must leave them byte-identical."""
import csv
import shutil
from pathlib import Path

from qhaway import server

FIXTURES = Path(__file__).parent / "fixtures" / "evidence"


def _line(text, stem):
    return next((l for l in text.splitlines() if l.startswith(f"- [{stem}](")), None)


def test_qhaway_agrees_with_yanantins_withdrawn_and_superseded(tmp_path):
    shutil.copytree(FIXTURES, tmp_path, dirs_exist_ok=True)
    before = {p.name: p.read_bytes() for p in tmp_path.glob("*.md")}
    server.initialize_server(str(tmp_path))
    live = server.recall(memory_dir=str(tmp_path))
    superseded = server.recall(memory_dir=str(tmp_path), status="superseded")

    notes = {}
    with open(FIXTURES / "expected.tsv", newline="") as f:
        for _, ref, _, note in csv.reader(f, delimiter="\t"):
            if note:
                notes[ref.removeprefix("memory:")] = note
    assert notes == {"claim": "withdrawn", "plan": "superseded"}

    for slug, note in notes.items():
        if note == "withdrawn":
            assert _line(live, slug).endswith(" [retracted](correction.md)")
        else:
            assert _line(live, slug) is None
            assert _line(superseded, slug) is not None
    assert _line(live, "cites") is not None
    assert {p.name: p.read_bytes() for p in tmp_path.glob("*.md") if p.name in before} == before
