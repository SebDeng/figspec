from PIL import Image
from figspec.pdf.interpreter import extract
from figspec.lint.checks import LintConfig, run_checks
from figspec.lint.annotate import annotate, FAIL_COLOR
from figspec.selftest.samples import write_samples

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
