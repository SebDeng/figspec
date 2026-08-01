"""figspec.board: geometry, layers, letters, and 1:1 asset placement —
verified by reading every claim back with our own lint interpreter."""
import pikepdf
import pytest

from figspec import scaling
from figspec.board import BoardPanel, build_board, panel_artboard
from figspec.pdf.interpreter import extract
from figspec.spec import Constraints
from figspec.units import mm_to_pt

NATURE = Constraints(min_font_pt=5.0, max_font_pt=7.0, min_linewidth_pt=0.25)

PANEL_A = BoardPanel("a", 0.0, 0.0, 91.5, 50.0)
PANEL_B = BoardPanel("b", 95.5, 54.0, 87.5, 46.0)


def _build(tmp_path, **kw):
    path = tmp_path / "board.pdf"
    build_board(183.0, 100.0, [PANEL_A, PANEL_B], path,
                constraints=NATURE, **kw)
    return path


def test_board_page_geometry(tmp_path):
    path = _build(tmp_path)
    doc = extract(path)
    assert doc.pages[0].width_pt == pytest.approx(mm_to_pt(183.0), abs=0.1)
    assert doc.pages[0].height_pt == pytest.approx(mm_to_pt(100.0), abs=0.1)
    with pikepdf.open(path) as pdf:
        trim = [float(v) for v in pdf.pages[0].TrimBox]
        assert trim[2] == pytest.approx(mm_to_pt(183.0), abs=0.1)


def test_board_letters_true_size_and_flipped_position(tmp_path):
    path = _build(tmp_path)
    doc = extract(path)
    letters = {r.text: r for r in doc.text_runs if r.text in ("a", "b")}
    assert set(letters) == {"a", "b"}
    for r in letters.values():
        assert r.nominal_pt == pytest.approx(7.0)
        assert "Bold" in r.font_name
    # y-flip pin: panel b starts 54 mm from the TOP, so its letter's
    # baseline must sit in the page's upper-left region of that panel —
    # in PDF coords, ABOVE H − (54 + 8) mm.
    H = mm_to_pt(100.0)
    b = letters["b"]
    assert b.bbox_pt[0] >= mm_to_pt(95.5)
    assert b.bbox_pt[1] >= H - mm_to_pt(54.0 + 8.0)
    assert b.bbox_pt[1] <= H - mm_to_pt(54.0)


def test_board_label_style(tmp_path):
    path = tmp_path / "upper.pdf"
    build_board(183.0, 100.0, [PANEL_A], path, constraints=NATURE,
                label_style="uppercase")
    texts = [r.text for r in extract(path).text_runs]
    assert "A" in texts and "a" not in texts


def test_board_layers(tmp_path):
    path = _build(tmp_path)
    with pikepdf.open(path) as pdf:
        names = {str(oc.Name) for oc in pdf.Root.OCProperties.OCGs}
        assert names == {"figspec layout", "figspec content"}
        props = pdf.pages[0].Resources.Properties
        assert "/L1" in props and "/L2" in props
        raw = pdf.pages[0].Contents.read_bytes()
        assert b"/OC /L1 BDC" in raw and b"/OC /L2 BDC" in raw


def test_board_mm_annotation_toggle(tmp_path):
    with_note = extract(_build(tmp_path))
    assert any("91.5 x 50.0 mm" == r.text for r in with_note.text_runs)
    bare = tmp_path / "bare.pdf"
    build_board(183.0, 100.0, [PANEL_A, PANEL_B], bare, constraints=NATURE,
                annotate_mm=False)
    assert not any("mm" in r.text for r in extract(bare).text_runs)


def test_panel_artboard(tmp_path):
    path = tmp_path / "artboard.pdf"
    panel_artboard(BoardPanel("c", 10.0, 20.0, 60.0, 36.0), path,
                   constraints=NATURE)
    doc = extract(path)
    assert doc.pages[0].width_pt == pytest.approx(mm_to_pt(60.0), abs=0.1)
    assert doc.pages[0].height_pt == pytest.approx(mm_to_pt(36.0), abs=0.1)
    texts = [r.text for r in doc.text_runs]
    assert "c" in texts
    note = next(t for t in texts if t.startswith("panel c"))
    assert "60.0 x 36.0 mm" in note
    assert "fonts 5.0-7.0 pt" in note


# ---- 1:1 asset placement (task H2) ---------------------------------------

def test_board_places_pdf_asset_1to1(tmp_path):
    """bad.pdf is 183 mm x 200 pt with in-asset effective 3.2 pt text; the
    91.5 mm panel gives k = 0.5 exactly, so the board must contain that
    text at 1.6 pt effective — read back by the shipped interpreter's own
    form-XObject recursion."""
    from figspec.selftest.samples import write_samples
    samples = write_samples(tmp_path / "s")
    panel = BoardPanel("a", 0.0, 0.0, 91.5, 50.0,
                       asset_path=str(samples["bad"]))
    path = tmp_path / "board.pdf"
    build_board(183.0, 100.0, [panel, PANEL_B], path, constraints=NATURE)
    doc = extract(path)
    run = next(r for r in doc.text_runs if r.text == "Scaled tiny text")
    assert run.effective_pt == pytest.approx(1.6, abs=0.02)
    # centered inside the panel, in PDF coords (panel occupies the TOP half)
    H = mm_to_pt(100.0)
    assert run.bbox_pt[1] >= H - mm_to_pt(50.0)


def test_board_places_raster_1to1(tmp_path):
    from PIL import Image
    png = tmp_path / "img.png"
    Image.new("RGB", (400, 300), (180, 40, 40)).save(png)
    panel = BoardPanel("b", 95.5, 54.0, 60.0, 36.0, asset_path=str(png),
                       asset_px=(400, 300), asset_dpi=None)  # assume 96
    path = tmp_path / "board.pdf"
    build_board(183.0, 100.0, [PANEL_A, panel], path, constraints=NATURE)
    doc = extract(path)
    assert len(doc.images) == 1
    img = doc.images[0]
    assert (img.px_w, img.px_h) == (400, 300)
    src_mm = scaling.asset_size_mm((400, 300), 96.0)
    k = scaling.placement_scale((60.0, 36.0), src_mm)
    expect_dpi = 400 / (src_mm[0] * k / 25.4)
    assert img.effective_dpi == pytest.approx(expect_dpi, abs=2)
    # placed inside the panel rect (non-symmetric position pins the flip)
    H = mm_to_pt(100.0)
    x0, y0, x1, y1 = img.bbox_pt
    assert x0 >= mm_to_pt(95.5) - 0.5 and x1 <= mm_to_pt(95.5 + 60.0) + 0.5
    assert y0 >= H - mm_to_pt(54.0 + 36.0) - 0.5 and y1 <= H - mm_to_pt(54.0) + 0.5


def test_board_missing_asset_keeps_frame(tmp_path):
    panel = BoardPanel("a", 0.0, 0.0, 91.5, 50.0,
                       asset_path=str(tmp_path / "nope.pdf"))
    path = tmp_path / "board.pdf"
    build_board(183.0, 100.0, [panel], path, constraints=NATURE)
    doc = extract(path)
    assert any(r.text == "a" for r in doc.text_runs)  # board still valid
    assert not doc.images
