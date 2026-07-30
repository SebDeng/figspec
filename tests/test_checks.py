import pytest
from figspec.pdf.interpreter import DocumentContent, PageInfo, TextRun, StrokePath, PlacedImage
from figspec.lint.checks import LintConfig, run_checks
from figspec.units import mm_to_pt

def _doc(**kw):
    base = dict(pages=[PageInfo(0, mm_to_pt(183), 300)], text_runs=[], strokes=[],
                images=[], parse_errors=[])
    base.update(kw)
    return DocumentContent(**base)

def _run(text, nominal, scale, page=0):
    return TextRun(page, text, "Helvetica", nominal, nominal * scale, scale,
                   (10, 10, 60, 20))

def by_id(findings):
    out = {}
    for f in findings:
        out.setdefault(f.check_id, []).append(f)
    return out

def test_font_fail_and_grouping():
    doc = _doc(text_runs=[_run("a", 8.0, 0.4), _run("b", 8.0, 0.4), _run("ok", 7.0, 1.0)])
    fs = by_id(run_checks(doc, LintConfig()))["FONT-EFFECTIVE"]
    assert len(fs) == 1                      # two same-size violations grouped
    f = fs[0]
    assert f.level == "FAIL"
    assert f.effective_pt == pytest.approx(3.2)
    assert f.nominal_pt == 8.0 and f.scale == pytest.approx(0.4)
    assert len(f.boxes_pt) == 2
    assert "3.2" in f.message

def test_font_pass():
    doc = _doc(text_runs=[_run("ok", 7.0, 1.0)])
    (f,) = by_id(run_checks(doc, LintConfig()))["FONT-EFFECTIVE"]
    assert f.level == "PASS"

def test_linewidth_and_zero_w():
    doc = _doc(strokes=[StrokePath(0, 0.5, 0.2, (0, 0, 10, 10)),
                        StrokePath(0, 0.0, 0.0, (0, 0, 10, 10))])
    fs = by_id(run_checks(doc, LintConfig()))["LINEWIDTH-EFFECTIVE"]
    assert all(f.level == "FAIL" for f in fs)
    assert any("thinnest" in f.message for f in fs)

def test_final_width():
    doc = _doc()
    cfg = LintConfig(width_pt=mm_to_pt(183))
    (f,) = by_id(run_checks(doc, cfg))["FINAL-WIDTH"]
    assert f.level == "PASS"
    cfg = LintConfig(width_pt=mm_to_pt(89))
    (f,) = by_id(run_checks(doc, cfg))["FINAL-WIDTH"]
    assert f.level == "WARN"
    assert "183.0" in f.message and "89.0" in f.message

def test_text_present_and_raster():
    doc = _doc(images=[PlacedImage(0, 100, 100, 50.0, (0, 0, 144, 144))])
    d = by_id(run_checks(doc, LintConfig()))
    assert d["TEXT-PRESENT"][0].level == "WARN"
    assert d["RASTER-DPI"][0].level == "WARN"
    assert "50" in d["RASTER-DPI"][0].message

def test_page_parse_warn():
    doc = _doc(parse_errors=[(0, "ValueError: boom")])
    assert by_id(run_checks(doc, LintConfig()))["PAGE-PARSE"][0].level == "WARN"

def test_page_parse_clean_pass():
    """Clean doc (no parse errors) should emit PAGE-PARSE PASS finding."""
    doc = _doc()  # no parse_errors
    d = by_id(run_checks(doc, LintConfig()))
    assert "PAGE-PARSE" in d
    assert d["PAGE-PARSE"][0].level == "PASS"
    assert "cleanly" in d["PAGE-PARSE"][0].message.lower()

def test_font_grouping_precision_round2():
    """Two text runs at nominal 8.01 and 8.04 with scale 0.4 should NOT merge under round(,2)."""
    doc = _doc(text_runs=[_run("a", 8.01, 0.4), _run("b", 8.04, 0.4)])
    fs = by_id(run_checks(doc, LintConfig()))["FONT-EFFECTIVE"]
    assert len(fs) == 2, f"Expected 2 FONT-EFFECTIVE findings but got {len(fs)}"
    # Both should be FAIL (< 5.0 pt effective)
    assert all(f.level == "FAIL" for f in fs)
    # Verify distinct groups
    assert fs[0].nominal_pt == 8.01
    assert fs[1].nominal_pt == 8.04
