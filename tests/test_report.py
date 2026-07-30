import json
from figspec import __version__
from figspec.lint.checks import Finding
from figspec.lint.report import summarize, render_text, render_json, exit_code

F = [Finding("FONT-EFFECTIVE", "FAIL", "Text effective size 3.20 pt below 5 pt minimum",
             evidence=["page 1: 'x' nominal 8 pt x scale 0.400 = 3.20 pt"],
             page=0, nominal_pt=8.0, scale=0.4, effective_pt=3.2),
     Finding("FINAL-WIDTH", "WARN", "Page width mismatch"),
     Finding("RASTER-DPI", "PASS", "No raster images placed")]

def test_summarize_and_exit():
    s = summarize(F, strict=False)
    assert s == {"ready": False, "strict": False, "counts": {"PASS": 1, "WARN": 1, "FAIL": 1}}
    assert exit_code(s) == 1
    ok = summarize([F[2]], strict=False)
    assert ok["ready"] and exit_code(ok) == 0
    warn_only = summarize([F[1]], strict=True)
    assert not warn_only["ready"]

def test_render_text():
    out = render_text("fig.pdf", F, summarize(F, strict=False))
    assert "figspec lint fig.pdf" in out
    assert "[FAIL] FONT-EFFECTIVE" in out
    assert "verdict: FIX BEFORE SUBMISSION" in out
    assert "summary: 1 pass, 1 warn, 1 fail" in out

def test_render_json_roundtrip():
    d = render_json("fig.pdf", F, summarize(F, strict=False))
    j = json.loads(json.dumps(d))
    assert j["tool"]["name"] == "figspec"
    assert j["tool"]["version"] == __version__
    assert j["findings"][0]["check_id"] == "FONT-EFFECTIVE"  # FAIL sorts first
    assert j["findings"][0]["page"] == 1  # page 0 converted to 1-indexed
    assert j["findings"][0]["effective_pt"] == 3.2
    assert "boxes_pt" not in j["findings"][0]

def test_evidence_truncation():
    f = Finding("FONT-EFFECTIVE", "FAIL", "m", evidence=[f"e{i}" for i in range(30)])
    out = render_text("x.pdf", [f], summarize([f], False), max_evidence=10)
    assert "e9" in out and "e10" not in out
    assert "20 more evidence lines in --json output" in out

def test_check_id_secondary_sort():
    # Two FAIL findings with different check_ids should be sorted alphabetically
    b_check = Finding("B-CHECK", "FAIL", "B message")
    a_check = Finding("A-CHECK", "FAIL", "A message")
    findings = [b_check, a_check]  # reversed order
    summary = summarize(findings, False)

    # render_json should sort A-CHECK before B-CHECK
    d = render_json("test.pdf", findings, summary)
    assert d["findings"][0]["check_id"] == "A-CHECK"
    assert d["findings"][1]["check_id"] == "B-CHECK"

    # render_text should list them in the same sorted order
    out = render_text("test.pdf", findings, summary)
    a_pos = out.find("A-CHECK")
    b_pos = out.find("B-CHECK")
    assert a_pos < b_pos, "A-CHECK should appear before B-CHECK in text output"
