import json
import pytest
from figspec.cli import main
from figspec.selftest.samples import write_samples

@pytest.fixture()
def samples(tmp_path):
    return write_samples(tmp_path)

def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert "figspec" in capsys.readouterr().out

def test_lint_bad_exits_1(samples, capsys):
    rc = main(["lint", str(samples["bad"])])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[FAIL] FONT-EFFECTIVE" in out
    assert "FIX BEFORE SUBMISSION" in out

def test_lint_good_ready(samples, capsys):
    rc = main(["lint", str(samples["good"]), "--width", "89"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[PASS] FINAL-WIDTH" in out
    assert "READY FOR SUBMISSION" in out

def test_strict_promotes_warn(samples):
    # good.pdf vs wrong width target -> WARN -> strict makes it exit 1
    assert main(["lint", str(samples["good"]), "--width", "183"]) == 0
    assert main(["lint", str(samples["good"]), "--width", "183", "--strict"]) == 1

def test_json_stdout(samples, capsys):
    rc = main(["lint", str(samples["bad"]), "--json"])
    cap = capsys.readouterr()
    data = json.loads(cap.out)          # stdout is pure JSON
    assert data["summary"]["ready"] is False
    assert "FIX BEFORE SUBMISSION" in cap.err  # human report moved to stderr
    assert rc == 1

def test_json_file(samples, tmp_path, capsys):
    p = tmp_path / "r.json"
    main(["lint", str(samples["bad"]), "--json", str(p)])
    assert json.loads(p.read_text())["tool"]["name"] == "figspec"
    assert "FIX BEFORE" in capsys.readouterr().out  # human report stays on stdout

def test_annotate_auto_path(samples):
    main(["lint", str(samples["bad"]), "--annotate"])
    assert samples["bad"].with_suffix(".lint.png").exists()

def test_missing_file_exits_2(capsys):
    assert main(["lint", "/nonexistent/x.pdf"]) == 2
    assert "cannot open" in capsys.readouterr().err

def test_min_font_flag(samples):
    assert main(["lint", str(samples["good"]), "--min-font", "8"]) == 1  # 6pt/7pt text now fails

def test_self_test(capsys):
    rc = main(["lint", "--self-test"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[ok]" in out and "[FAIL]" not in out
    assert "self-test passed" in out
