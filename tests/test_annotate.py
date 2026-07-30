import pikepdf
import pytest
from PIL import Image
from figspec.pdf.interpreter import extract
from figspec.lint.checks import LintConfig, run_checks
from figspec.lint.annotate import annotate, FAIL_COLOR
from figspec.selftest.samples import write_samples
from figspec.units import pt_to_mm

def test_annotate_bad_sample(tmp_path):
    paths = write_samples(tmp_path)
    doc = extract(paths["bad"])
    findings = run_checks(doc, LintConfig())
    out = tmp_path / "bad.lint.png"
    written = annotate(paths["bad"], findings, out)
    assert written == [out] and out.exists()
    img = Image.open(out).convert("RGB")
    colors = {c for _, c in img.getcolors(maxcolors=1 << 20)}
    assert FAIL_COLOR in colors  # red boxes drawn

def test_annotate_clean_sample_writes_nothing(tmp_path):
    paths = write_samples(tmp_path)
    doc = extract(paths["good"])
    findings = run_checks(doc, LintConfig())
    written = annotate(paths["good"], findings, tmp_path / "good.lint.png")
    assert written == []

def test_annotate_nonzero_origin_mediabox(tmp_path):
    # Finding 3: a page whose MediaBox does not start at (0,0) must still
    # get its violation boxes drawn on-canvas. Text at absolute PDF
    # coordinates (520,520) on a MediaBox [500 500 800 700] page sits at
    # canvas-relative (20,20) -- annotate() must subtract the page origin
    # before scaling to pixels, otherwise the box is drawn far off-canvas
    # and no FAIL_COLOR pixels appear (that was the pre-fix bug).
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(300, 200))
    page.MediaBox = pikepdf.Array([500, 500, 800, 700])
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(
        F1=pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                              BaseFont=pikepdf.Name.Helvetica)))
    page.Contents = pdf.make_stream(b"BT /F1 3 Tf 1 0 0 1 520 520 Tm (tiny) Tj ET")
    path = tmp_path / "offset.pdf"
    pdf.save(path)

    doc = extract(path)
    findings = run_checks(doc, LintConfig())
    font_fail = [f for f in findings if f.check_id == "FONT-EFFECTIVE" and f.level == "FAIL"]
    assert font_fail, "expected a FONT-EFFECTIVE FAIL for 3pt text"
    assert font_fail[0].bbox_mm[0] == pytest.approx(pt_to_mm(20), abs=1.0)

    origins = {p.index: (p.origin_x_pt, p.origin_y_pt) for p in doc.pages}
    out = tmp_path / "offset.lint.png"
    written = annotate(path, findings, out, origins=origins)
    assert written == [out] and out.exists()
    img = Image.open(out).convert("RGB")
    colors = {c for _, c in img.getcolors(maxcolors=1 << 20)}
    assert FAIL_COLOR in colors  # red box drawn on-canvas, not off-canvas
