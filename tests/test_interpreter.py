import pikepdf
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

def _simple_font() -> pikepdf.Dictionary:
    return pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica
    )

def test_q_restores_text_state(tmp_path):
    # PDF32000 8.4/9.3: Tc, Tw, Tz, TL, Tf/Tfs, Tr, Ts are graphics-state
    # (text-state) parameters and MUST be restored by Q. Tm/Tlm are NOT part
    # of graphics state -- they reset at BT regardless of q/Q.
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(200, 200))
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=_simple_font(), F2=_simple_font()))
    stream = (
        b"/F1 12 Tf\n"
        b"BT 1 0 0 1 10 10 Tm (before) Tj ET\n"
        b"q\n"
        b"/F2 20 Tf\n"
        b"BT 1 0 0 1 10 30 Tm (during) Tj ET\n"
        b"Q\n"
        b"BT 1 0 0 1 10 50 Tm (after) Tj ET\n"
    )
    page.Contents = pdf.make_stream(stream)
    path = tmp_path / "qrestore.pdf"
    pdf.save(path)

    doc = extract(path)
    sizes = [r.nominal_pt for r in doc.text_runs]
    assert sizes == [pytest.approx(12.0), pytest.approx(20.0), pytest.approx(12.0)]
    after = next(r for r in doc.text_runs if r.text == "after")
    assert after.nominal_pt == pytest.approx(12.0)  # Q must restore pre-q text state

def test_missing_mediabox_does_not_raise(tmp_path):
    # Observed: pikepdf/qpdf synthesizes a default MediaBox (US Letter,
    # 612x792pt) for a page whose /MediaBox is absent on disk, so deleting
    # the key cannot be made to raise out of extract() in this pikepdf
    # version. Kept as a regression guard for extract()'s robustness; the
    # deterministic exercise of the try/except degrade path itself is in
    # test_broken_mediabox_isolated below.
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(150, 150))
    del page["/MediaBox"]
    path = tmp_path / "nomediabox.pdf"
    pdf.save(path)

    doc = extract(path)  # must not raise
    assert len(doc.pages) == 1
    assert doc.pages[0].width_pt > 0 and doc.pages[0].height_pt > 0

def test_broken_mediabox_isolated(tmp_path, monkeypatch):
    # Deterministically force page 0's MediaBox coordinate conversion to
    # raise (simulating a malformed /MediaBox entry that pikepdf/qpdf does
    # not heal -- see test_missing_mediabox_does_not_raise for why a
    # genuinely-missing key can't be used to trigger this) and verify
    # extract() isolates the failure per-page: it records a parse_errors
    # entry, still appends a PageInfo so page indices stay aligned, and
    # continues parsing later pages correctly.
    #
    # pikepdf.Page's attribute access bypasses normal Python descriptor
    # resolution (confirmed experimentally: monkeypatching a `MediaBox`
    # property on the class has no effect on real `page.MediaBox` reads),
    # so we instead target the `float(v)` conversion that extract() applies
    # to each MediaBox coordinate -- that IS a plain, interceptable call,
    # and is exactly the expression finding 2 is about. Patched only on the
    # figspec.pdf.interpreter module's own global namespace (not
    # builtins.float) so pikepdf's internals -- which use `float | None`
    # style unions requiring the real `float` type -- are unaffected.
    import figspec.pdf.interpreter as interpreter_mod
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(101, 101))
    pdf.add_blank_page(page_size=(120, 140))
    path = tmp_path / "brokenbox.pdf"
    pdf.save(path)

    real_float = float

    def fake_float(x):
        v = real_float(x)
        if v == 101.0:
            raise ValueError("simulated malformed MediaBox coordinate")
        return v

    monkeypatch.setattr(interpreter_mod, "float", fake_float, raising=False)
    doc = extract(path)
    monkeypatch.undo()  # restore float immediately; assertions below don't need the patch

    assert len(doc.pages) == 2  # index alignment preserved despite page 0 failure
    assert doc.pages[0].index == 0
    assert doc.pages[0].width_pt == 0.0 and doc.pages[0].height_pt == 0.0
    assert any(idx == 0 for idx, _msg in doc.parse_errors)
    assert doc.pages[1].width_pt == pytest.approx(120.0)
    assert doc.pages[1].height_pt == pytest.approx(140.0)
