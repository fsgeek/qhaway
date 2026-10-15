"""Topic files are never rewritten, so frontmatter keys qhaway doesn't know
survive. Other tools (yanantin's evidence references, hamut'ay's writer
identity) rely on this to attach fields qhaway ignores."""
import os

from qhaway import cli, server

TOPIC = (
    "---\n"
    "name: Claim with evidence\n"
    "description: carries keys qhaway does not know\n"
    "type: project\n"
    "evidence:\n"
    "  - ref: episode://khipumaq/session/episode\n"
    "    sha256: 4dad0cfee64c858aafcc1e68fd8fd387186d0f1fa26c727ca0c22d455da30951\n"
    "who: {asserted_by: hamutay, id: 7}\n"
    "---\n"
    "body\n"
)


def test_unknown_frontmatter_survives_every_command(tmp_path):
    topic = tmp_path / "claim.md"
    topic.write_bytes(TOPIC.encode())

    old = dict(os.environ)
    os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    try:
        assert cli.main(["index", "--dir", str(tmp_path)]) == 0
        assert "Claim with evidence" in (tmp_path / "MEMORY.md").read_text()
        assert cli.main(["reconcile", "--dir", str(tmp_path)]) == 0
        assert cli.main(["exit", "--dir", str(tmp_path)]) == 0
    finally:
        os.environ.clear(); os.environ.update(old)
    server.remember("project", "Correction", "the claim was wrong",
                    retracts=["claim"], retracted_claim="body", memory_dir=str(tmp_path))
    server.remember("project", "Successor", "newer", supersedes=["claim"],
                    memory_dir=str(tmp_path))

    assert topic.read_bytes() == TOPIC.encode()
