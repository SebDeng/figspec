import pytest
from figspec.cli import main
from figspec.lint.checks import LintConfig, run_checks
from figspec.pdf.interpreter import extract

def _sizes(doc):
    return [r.effective_pt for r in doc.text_runs]

def test_unscaled_panel_all_7pt(mpl_dir):
    doc = extract(mpl_dir / "panel42.pdf")
    assert doc.text_runs, "matplotlib panel must contain text objects"
    assert all(6.8 <= s <= 7.2 for s in _sizes(doc)), sorted(_sizes(doc))

def test_text_decoded(mpl_dir):
    doc = extract(mpl_dir / "panel42.pdf")
    assert any("Vds" in r.text for r in doc.text_runs)

def test_rotated_ylabel_not_shrunk(mpl_dir):
    doc = extract(mpl_dir / "panel42.pdf")
    # ylabel is rotated 90 degrees; a wrong formula would report ~0 or inflated size
    spread = max(_sizes(doc)) - min(_sizes(doc))
    assert spread < 0.4

def test_scaled_assembly_detects_315(mpl_dir):
    doc = extract(mpl_dir / "assembled045.pdf")
    assert min(_sizes(doc)) == pytest.approx(3.15, abs=0.1)
    findings = run_checks(doc, LintConfig())
    assert any(f.check_id == "FONT-EFFECTIVE" and f.level == "FAIL" for f in findings)

def test_fonttype3_matches_fonttype42(mpl_dir):
    s42 = sorted(_sizes(extract(mpl_dir / "panel42.pdf")))
    s3 = sorted(_sizes(extract(mpl_dir / "panel3.pdf")))
    assert min(s42) == pytest.approx(min(s3), abs=0.1)
    assert max(s42) == pytest.approx(max(s3), abs=0.1)

def test_outlined_panel_warns_text_present(mpl_dir):
    doc = extract(mpl_dir / "outlined.pdf")
    assert not doc.text_runs
    findings = run_checks(doc, LintConfig())
    assert any(f.check_id == "TEXT-PRESENT" and f.level == "WARN" for f in findings)

def test_raster_dpi_warn(mpl_dir):
    doc = extract(mpl_dir / "raster.pdf")
    assert doc.images
    assert doc.images[0].effective_dpi == pytest.approx(50, abs=5)

def test_clean_panel_cli_ready(mpl_dir):
    assert main(["lint", str(mpl_dir / "panel42.pdf")]) == 0

def test_assembled_cli_fails(mpl_dir):
    assert main(["lint", str(mpl_dir / "assembled045.pdf"), "--width", "183"]) == 1
