"""scripts/check_cc_limits.py finds Claude Code's MEMORY.md load caps in an
installed build and compares them with the ones qhaway assumes."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "check_cc_limits.py"


def _check(tmp_path, blob: bytes):
    fake = tmp_path / "claude"
    fake.write_bytes(b"\x00junk\x00" + blob + b"\x00more")
    return subprocess.run([sys.executable, str(SCRIPT), str(fake)], capture_output=True, text=True)


def test_matching_limits_pass(tmp_path):
    r = _check(tmp_path, b'var cp="MEMORY.md",mF=200,Ule=25000,y$r=4*Ule')
    assert r.returncode == 0, r.stdout + r.stderr
    assert "200 lines, 25000 bytes" in r.stdout


def test_changed_limits_fail(tmp_path):
    r = _check(tmp_path, b'var xq="MEMORY.md",aB=150,c_d=20000,z=1')
    assert r.returncode == 1
    assert "150" in r.stdout and "20000" in r.stdout


def test_missing_anchor_is_not_a_pass(tmp_path):
    r = _check(tmp_path, b'nothing recognisable here')
    assert r.returncode == 2
    assert "not found" in r.stdout
