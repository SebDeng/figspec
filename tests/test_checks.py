import pikepdf
import pytest
from figspec.pdf.interpreter import DocumentContent, PageInfo, TextRun, StrokePath, PlacedImage, extract
from figspec.lint.checks import LintConfig, run_checks
from figspec.units import mm_to_pt, pt_to_mm

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

def test_final_width_uses_trimbox_not_mediabox(tmp_path):
    # Finding 1: a PDF with a bleed MediaBox (197.6mm) but a TrimBox of
    # ~183mm must PASS FINAL-WIDTH against a 183mm target, not WARN.
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(560, 300))
    page.TrimBox = pikepdf.Array([20, 20, 538.7, 280])
    path = tmp_path / "trimbox.pdf"
    pdf.save(path)

    doc = extract(path)
    cfg = LintConfig(width_pt=mm_to_pt(183))
    (f,) = by_id(run_checks(doc, cfg))["FINAL-WIDTH"]
    assert f.level == "PASS"

def test_bbox_mm_is_page_relative_to_origin():
    # Finding 3: bbox_mm must be relative to the page's render origin
    # (CropBox else MediaBox lower-left), not raw absolute PDF coordinates.
    doc = _doc(pages=[PageInfo(0, mm_to_pt(183), 300, origin_x_pt=500.0, origin_y_pt=500.0)],
               text_runs=[_run("a", 8.0, 0.4)])
    (f,) = by_id(run_checks(doc, LintConfig()))["FONT-EFFECTIVE"]
    # _run's raw bbox_pt is (10, 10, 60, 20); relative to origin (500, 500)
    # that's negative, but the point is it must NOT equal the raw-mm union.
    assert f.bbox_mm[0] == pytest.approx(pt_to_mm(10 - 500), abs=0.02)
    assert f.bbox_mm[1] == pytest.approx(pt_to_mm(10 - 500), abs=0.02)

def test_font_evidence_full_under_cap():
    # Finding 2: JSON evidence must be FULL, no 3-line cap / "...and N more".
    # 6 violating runs in one group -> Finding carries 6 evidence lines.
    doc = _doc(text_runs=[_run(f"r{i}", 8.0, 0.4) for i in range(6)])
    (f,) = by_id(run_checks(doc, LintConfig()))["FONT-EFFECTIVE"]
    assert len(f.evidence) == 6
    assert not any("more" in e for e in f.evidence)
    for i in range(6):
        assert any(f"r{i}" in e for e in f.evidence)

def test_font_evidence_full_over_display_cap():
    # 12 violating runs -> Finding still carries all 12 (display truncation
    # to 10 happens only in render_text, not here).
    doc = _doc(text_runs=[_run(f"r{i}", 8.0, 0.4) for i in range(12)])
    (f,) = by_id(run_checks(doc, LintConfig()))["FONT-EFFECTIVE"]
    assert len(f.evidence) == 12
    assert not any("more" in e for e in f.evidence)

def test_font_evidence_render_text_under_cap():
    from figspec.lint.report import render_text, summarize
    doc = _doc(text_runs=[_run(f"r{i}", 8.0, 0.4) for i in range(6)])
    (f,) = by_id(run_checks(doc, LintConfig()))["FONT-EFFECTIVE"]
    out = render_text("x.pdf", [f], summarize([f], False))
    for i in range(6):
        assert f"r{i}" in out
    assert "more evidence lines" not in out

def test_font_evidence_render_text_over_cap():
    from figspec.lint.report import render_text, summarize
    doc = _doc(text_runs=[_run(f"r{i}", 8.0, 0.4) for i in range(12)])
    (f,) = by_id(run_checks(doc, LintConfig()))["FONT-EFFECTIVE"]
    out = render_text("x.pdf", [f], summarize([f], False))
    for i in range(10):
        assert f"r{i}" in out
    assert "(2 more evidence lines in --json output)" in out

def test_linewidth_evidence_per_stroke():
    # Finding 2: linewidth evidence gets one line per stroke group member.
    doc = _doc(strokes=[StrokePath(0, 0.5, 0.2, (0, 0, 10, 10)) for _ in range(3)])
    (f,) = by_id(run_checks(doc, LintConfig()))["LINEWIDTH-EFFECTIVE"]
    assert len(f.evidence) == 3
    for ev in f.evidence:
        assert "page 1" in ev and "nominal" in ev and "scale" in ev

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
