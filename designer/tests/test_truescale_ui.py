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


# ---- zoom model (task E2) -----------------------------------------------

def test_default_zoom_is_fit(qtbot):
    from figspec_designer.ui.main_window import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.canvas.zoom_mode == "fit"


def test_actual_size_uses_screen_derivation(qtbot, monkeypatch):
    from figspec_designer.ui.main_window import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "_actual_ppm", lambda: 4.862)
    win.zoom_actual()
    assert win.canvas.zoom_mode == "actual"
    assert win.canvas.px_per_mm == pytest.approx(4.862)


def test_manual_zoom_pins_scale_and_emits(qtbot):
    from figspec_designer.ui.main_window import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    with qtbot.waitSignal(win.canvas.scale_changed, timeout=2000) as blocker:
        win.canvas.set_zoom("manual", 12.0)
    assert blocker.args[0] == pytest.approx(12.0)
    assert win.canvas.px_per_mm == pytest.approx(12.0)
    # canvas advertises the page extent so the scroll area can scroll
    assert win.canvas.minimumWidth() > 12 * 183 * 0.9


def test_zoom_step_clamps_to_actual_band(qtbot, monkeypatch):
    from figspec_designer.ui.main_window import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "_actual_ppm", lambda: 4.0)
    win.canvas.set_zoom("manual", 15.5)
    win.zoom_step(1.25)  # would be 19.4 — clamps to 4×actual = 16
    assert win.canvas.px_per_mm == pytest.approx(16.0)


def test_zoom_fit_restores_window_tracking(qtbot):
    from figspec_designer.ui.main_window import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    win.canvas.set_zoom("manual", 12.0)
    win.zoom_fit()
    assert win.canvas.zoom_mode == "fit"
    assert win.canvas.minimumWidth() == 0  # no stale floor


def test_layout_edits_survive_pinned_zoom(qtbot):
    from figspec.layout.tree import iter_panels
    from figspec_designer.ui.main_window import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    win.canvas.set_zoom("manual", 10.0)
    pid = next(iter_panels(win.doc.tree)).id
    win.do_action("split_right", pid)
    assert len(list(iter_panels(win.doc.tree))) == 2
    assert win.canvas.px_per_mm == pytest.approx(10.0)  # zoom survives rebuild


# ---- calibration dialog (task E3) ---------------------------------------

def test_calibrate_dialog_slider_drives_ruler(qtbot):
    from figspec_designer.ui.calibrate_dialog import CalibrateDialog
    dlg = CalibrateDialog(base_ppm=4.0, correction=1.0)
    qtbot.addWidget(dlg)
    before = dlg.ruler.bar_px()
    dlg.slider.setValue(1100)
    assert dlg.ruler.bar_px() == pytest.approx(before * 1.10, rel=1e-6)
    assert dlg.correction() == pytest.approx(1.10)


# ---- specimen strip (task E4) -------------------------------------------

def test_specimen_strip_state(qtbot):
    from figspec.spec import Constraints
    from figspec_designer.ui.specimen_strip import SpecimenStrip
    strip = SpecimenStrip()
    qtbot.addWidget(strip)
    strip.set_context(9.724, 4.862,
                      Constraints(min_font_pt=5.0, max_font_pt=7.0))
    assert strip.badge_text() == "200% of print size"
    rows = strip.rows()
    assert "Aa 5.0 pt" in rows and "Aa 7.0 pt" in rows
    assert "0.25 pt" in rows and "1 pt" in rows and "10 mm" in rows
    assert "5.0 pt = 1.76 mm" in strip.toolTip()


def test_specimen_strip_panel_row(qtbot):
    from figspec.spec import Constraints
    from figspec_designer.ui.specimen_strip import SpecimenStrip
    strip = SpecimenStrip()
    qtbot.addWidget(strip)
    strip.set_context(4.862, 4.862, Constraints())
    strip.set_panel_scale(0.154)
    assert "8 pt → 1.23 pt" in strip.rows()
    strip.set_panel_scale(None)
    assert not any("→" in r for r in strip.rows())


def test_strip_button_requests_actual_size(qtbot):
    from figspec_designer.ui.specimen_strip import SpecimenStrip
    strip = SpecimenStrip()
    qtbot.addWidget(strip)
    with qtbot.waitSignal(strip.actual_size_requested, timeout=2000):
        strip.btn_actual.click()


def test_mainwindow_strip_follows_zoom(qtbot, monkeypatch):
    from figspec_designer.ui.main_window import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "_actual_ppm", lambda: 4.862)
    win.canvas.set_zoom("manual", 9.724)
    assert win.specimen_strip.badge_text() == "200% of print size"


def test_mainwindow_strip_shows_selected_panel_scale(qtbot, tmp_path):
    from PySide6.QtGui import QImage
    from figspec.layout.tree import iter_panels
    from figspec_designer.ui.main_window import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    img = QImage(1472, 879, QImage.Format_RGB32)
    img.fill(0xFFFFFFFF)
    png = tmp_path / "asset.png"
    img.save(str(png))
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(png))
    win.do_action("select", pid)
    assert any(r.startswith("8 pt → ") for r in win.specimen_strip.rows())
    win.do_action("select", None)
    assert not any("→" in r for r in win.specimen_strip.rows())
