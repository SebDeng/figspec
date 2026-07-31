"""Batch E tests: honesty red lines, zoom model, calibration, specimen strip."""
import pytest
from PySide6.QtCore import QRect, QSizeF
from PySide6.QtGui import QImage, QPainter

from figspec_designer.ui import truescale


class FakeScreen:
    def __init__(self, geo_w=1512, phys_w_mm=311.0, serial="SN-TEST",
                 name="fake"):
        self._geo_w, self._phys_w = geo_w, phys_w_mm
        self._serial, self._name = serial, name

    def geometry(self):
        return QRect(0, 0, self._geo_w, 900)

    def physicalSize(self):
        return QSizeF(self._phys_w, 200.0)

    def serialNumber(self):
        return self._serial

    def name(self):
        return self._name


def _render_text(size_pt: float, ppm: float, text="Hg") -> QImage:
    img = QImage(400, 200, QImage.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    truescale.draw_text_pt(p, 2.0, 150.0 / ppm, text, size_pt, ppm)
    p.end()
    return img


def _ink_height(img: QImage) -> float:
    """Fractional ink height: per-row max alpha summed / 255. Antialiased
    edge rows count fractionally, giving sub-pixel resolution."""
    total = 0.0
    for y in range(img.height()):
        row_max = 0
        for x in range(img.width()):
            row_max = max(row_max, img.pixelColor(x, y).alpha())
        total += row_max / 255.0
    return total


def test_text_scales_linearly(qapp):
    h1 = _ink_height(_render_text(5.0, 20.0))
    h2 = _ink_height(_render_text(5.0, 40.0))
    assert h1 > 3  # sanity: something was drawn
    assert h2 / h1 == pytest.approx(2.0, rel=0.02)


def test_text_has_no_integer_pixel_snap(qapp):
    """5 pt at ppm 4.5 vs 4.9 is 7.94 px vs 8.64 px em — an int-px font
    would render both at the same snapped size."""
    h1 = _ink_height(_render_text(5.0, 4.5))
    h2 = _ink_height(_render_text(5.0, 4.9))
    assert h2 > h1 * 1.03


def test_hairline_stays_subpixel_and_translucent(qapp):
    pen = truescale.line_pen_pt(0.25, 4.0)
    assert pen.widthF() == pytest.approx(0.353, abs=0.005)
    img = QImage(60, 20, QImage.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    truescale.draw_line_pt(p, 1.0, 2.6, 13.0, 2.6, 0.25, 4.0)
    p.end()
    alphas = [img.pixelColor(x, y).alpha()
              for x in range(60) for y in range(20)]
    assert max(alphas) > 0  # drawn
    assert max(alphas) < 255  # partial coverage, never an opaque pixel


def test_screen_px_per_mm():
    s = FakeScreen()
    assert truescale.screen_px_per_mm(s) == pytest.approx(1512 / 311.0,
                                                          abs=1e-3)
    assert truescale.screen_px_per_mm(s, correction=1.03) == pytest.approx(
        1512 / 311.0 * 1.03, abs=1e-3)


def test_correction_roundtrip(tmp_path):
    from PySide6.QtCore import QSettings
    ini = str(tmp_path / "cal.ini")
    s1 = QSettings(ini, QSettings.IniFormat)
    screen = FakeScreen()
    assert truescale.load_correction(screen, s1) == 1.0
    truescale.save_correction(screen, 1.07, s1)
    s1.sync()
    s2 = QSettings(ini, QSettings.IniFormat)
    assert truescale.load_correction(screen, s2) == pytest.approx(1.07)
