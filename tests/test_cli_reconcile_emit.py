from qhaway import cli, reconcile


def _seed(tmp_path):
    text = reconcile.compose_topic_file(
        "project", "a real memory", "body text here", None, None
    )
    (tmp_path / "a-real-memory.md").write_text(text)


def test_reconcile_emit_writes_projection_to_stdout(tmp_path, capsys):
    _seed(tmp_path)
    rc = cli.main(["reconcile", "--dir", str(tmp_path), "--emit"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "a real memory" in out  # the projection includes the seeded memory


def test_reconcile_without_emit_is_silent(tmp_path, capsys):
    _seed(tmp_path)
    rc = cli.main(["reconcile", "--dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == ""  # reconcile-only writes nothing to stdout
