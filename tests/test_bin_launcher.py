import os
import subprocess
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "qhaway-plugin" / "bin" / "qhaway"


def test_bin_reconcile_runs(tmp_path):
    (tmp_path / "m.md").write_text("---\nname: m\ntype: project\n---\nbody\n")
    env = dict(os.environ)
    result = subprocess.run(
        [str(BIN), "reconcile", "--dir", str(tmp_path)],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
