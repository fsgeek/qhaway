import os
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "qhaway-plugin" / "bin" / "qhaway"


def _env_with_python_dir(python_executable: str) -> dict:
    """Return an env whose PATH makes `python3` resolve to a chosen interpreter."""
    env = dict(os.environ)
    env["PATH"] = str(Path(python_executable).parent) + os.pathsep + env.get("PATH", "")
    return env


def test_bin_reconcile_runs(tmp_path):
    """Happy path: with a qhaway-capable interpreter, the launcher runs the CLI."""
    (tmp_path / "m.md").write_text("---\nname: m\ntype: project\n---\nbody\n")
    # Pin python3 to THIS test interpreter, which can import qhaway + deps.
    env = _env_with_python_dir(sys.executable)
    result = subprocess.run(
        [str(BIN), "reconcile", "--dir", str(tmp_path)],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr


def test_bin_do_no_harm_when_deps_missing(tmp_path):
    """Do no harm: an interpreter that cannot import qhaway must exit non-zero
    with a clear error and NOT touch the memory dir (no MEMORY.md written)."""
    # A throwaway venv with NO packages installed → `import qhaway` fails.
    broken_venv = tmp_path / "broken-venv"
    subprocess.run([sys.executable, "-m", "venv", str(broken_venv)], check=True)
    broken_python = broken_venv / "bin" / "python"

    mem_dir = tmp_path / "mem"
    mem_dir.mkdir()
    (mem_dir / "m.md").write_text("---\nname: m\ntype: project\n---\nbody\n")

    env = _env_with_python_dir(str(broken_python))
    result = subprocess.run(
        [str(BIN), "reconcile", "--dir", str(mem_dir)],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode != 0
    assert "not importable" in result.stderr
    # do no harm: the launcher must not have invoked qhaway, so no MEMORY.md
    assert not (mem_dir / "MEMORY.md").exists()
