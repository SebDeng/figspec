import pytest
from figspec.pdf.interpreter import extract
from figspec.selftest.samples import write_samples, BAD_EFFECTIVE_FONT

@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    return write_samples(tmp_path_factory.mktemp("samples"))

def test_good_text_runs(samples):
    doc = extract(samples["good"])
    sizes = sorted(r.effective_pt for r in doc.text_runs)
    assert sizes == [pytest.approx(6.0), pytest.approx(7.0)]
    rot = next(r for r in doc.text_runs if r.nominal_pt == 6.0)
    assert rot.effective_pt == pytest.approx(6.0)  # rotation must not shrink size
    assert "Good 7pt label" in {r.text for r in doc.text_runs}

def test_bad_text_scaled(samples):
    doc = extract(samples["bad"])
    (run,) = doc.text_runs
    assert run.nominal_pt == pytest.approx(8.0)
    assert run.scale == pytest.approx(0.4)
    assert run.effective_pt == pytest.approx(BAD_EFFECTIVE_FONT)

def test_bbox_sane(samples):
    doc = extract(samples["good"])
    run = next(r for r in doc.text_runs if r.nominal_pt == 7.0)
    x0, y0, x1, y1 = run.bbox_pt
    assert x1 > x0 and y1 > y0
    assert x0 == pytest.approx(20, abs=1) and y0 == pytest.approx(60 - 7 * 0.25, abs=2)

def test_page_info(samples):
    doc = extract(samples["bad"])
    assert doc.pages[0].width_pt == pytest.approx(183 * 72 / 25.4, abs=0.5)

def test_missing_file_raises():
    from figspec.pdf.interpreter import LintInputError
    with pytest.raises(LintInputError):
        extract("/nonexistent/nope.pdf")
