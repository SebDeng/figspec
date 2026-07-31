"""Batch F tests: stand-in painter honesty, cache, canvas/sidebar wiring."""
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter

from figspec.spec import Constraints
from figspec import standins

NATURE = Constraints(min_font_pt=5.0, max_font_pt=7.0, min_linewidth_pt=0.25)


def _render(archetype, ppm, w_mm=40.0, h_mm=30.0, seed="seed-1"):
    from figspec_designer.ui.standin_painter import standin_picture
    pic = standin_picture(archetype, w_mm, h_mm, ppm, NATURE, seed)
    img = QImage(int(w_mm * ppm) + 2, int(h_mm * ppm) + 2,
                 QImage.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.drawPicture(QPointF(0, 0), pic)
    p.end()
    return img


def _ink_rows(img, y0, y1, x1):
    """Fractional ink height of rows [y0, y1), columns [0, x1)."""
    total = 0.0
    for y in range(y0, min(y1, img.height())):
        row_max = 0
        for x in range(0, min(x1, img.width())):
            row_max = max(row_max, img.pixelColor(x, y).alpha())
        total += row_max / 255.0
    return total


def test_all_archetypes_render(qapp):
    for archetype in standins.ARCHETYPES:
        for w, h in ((40.0, 30.0), (12.0, 9.0), (90.0, 60.0)):
            img = _render(archetype, 6.0, w, h, seed="x")
            assert any(img.pixelColor(x, y).alpha() > 0
                       for x in range(0, img.width(), 7)
                       for y in range(0, img.height(), 7)), (archetype, w)


def test_cache_returns_same_object(qapp):
    from figspec_designer.ui.standin_painter import standin_picture
    a = standin_picture("line", 40.0, 30.0, 6.0, NATURE, "s")
    b = standin_picture("line", 40.0, 30.0, 6.0, NATURE, "s")
    assert a is b
    c = standin_picture("line", 40.0, 30.0, 6.0, NATURE, "other")
    assert c is not a


def test_deterministic_pixels(qapp):
    from figspec_designer.ui import standin_painter
    standin_painter._CACHE.clear()
    img1 = _render("micrograph", 6.0)
    standin_painter._CACHE.clear()
    img2 = _render("micrograph", 6.0)
    assert img1 == img2


def test_tick_labels_scale_linearly(qapp):
    """Honesty red line on the composed stand-in: the bottom furniture
    strip (tick labels + axis caption, all true-scale text) must double in
    ink height when ppm doubles. The fixed-px corner mark sits in the
    excluded right columns."""
    # mm-aligned crop: below the tick marks (which end ~25.8 mm), left of
    # the fixed-px corner mark — only true-scale text ink remains. ppm 16/32
    # keeps glyphs big enough that antialias fuzz stays inside the 4% band
    # (the strict small-size linearity law lives in test_truescale_ui).
    img1 = _render("line", 16.0)
    img2 = _render("line", 32.0)
    h1 = _ink_rows(img1, round(26.0 * 16), img1.height(), round(33.0 * 16))
    h2 = _ink_rows(img2, round(26.0 * 32), img2.height(), round(33.0 * 32))
    assert h1 > 3
    assert h2 / h1 == pytest.approx(2.0, rel=0.04)


def test_heatmap_reserves_colorbar(qapp):
    from figspec_designer.ui.standin_painter import heatmap_layout
    plot, cbar = heatmap_layout(40.0, 30.0, standins.roles(NATURE))
    assert cbar.width() == pytest.approx(3.0)
    assert cbar.left() > plot.right()
    assert cbar.right() < 40.0
    assert plot.width() > 10.0


def test_micrograph_has_bright_scalebar(qapp):
    img = _render("micrograph", 8.0)
    w, h = img.width(), img.height()
    found = False
    for y in range(int(h - 8 * 3.2), h):
        for x in range(int(w * 0.6), w):
            c = img.pixelColor(x, y)
            if c.alpha() > 0 and min(c.red(), c.green(), c.blue()) >= 240:
                found = True
    assert found
