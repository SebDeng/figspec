import subprocess, sys

def test_version_runs():
    out = subprocess.run([sys.executable, "-m", "figspec.cli", "--version"],
                         capture_output=True, text=True)
    assert out.returncode == 0
    assert "figspec" in out.stdout
