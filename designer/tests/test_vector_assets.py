"""Batch G tests: PDF assets — pdfium thumbnails, intrinsic scale, and
drop-time lint prediction (all against the matplotlib-free selftest PDFs)."""
import pytest

from figspec.layout.tree import iter_panels
from figspec.selftest.samples import write_samples
from figspec_designer.ui.main_window import MainWindow


def _drop_pdf(win, tmp_path, which):
    paths = write_samples(tmp_path / "samples")
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(paths[which]))
    return pid


def test_pdf_drop_sets_vector_asset(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    pid = _drop_pdf(win, tmp_path, "good")  # 89 mm × 200 pt page
    panel = next(iter_panels(win.doc.tree))
    assert panel.asset_dpi == 72.0
    assert panel.asset_px == (round(89 * 72 / 25.4), 200)
    assert win.canvas.panel_widgets()[pid]._thumb is not None


def test_pdf_sidebar_vector_mode(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    pid = _drop_pdf(win, tmp_path, "good")
    win.do_action("select", pid)
    sb = win.sidebar
    assert "vector" in sb.lbl_asset_px.text()
    assert "pt" in sb.lbl_asset_px.text()
    # effective-DPI light and source-DPI declaration are raster concepts
    assert not sb.dpi_edit.isVisibleTo(sb.asset_box)
    assert not sb.lbl_asset_dpi.isVisibleTo(sb.asset_box)
    # scale factor still shown (derived from intrinsic size)
    assert sb.lbl_scale.text().startswith("×")


def test_pdf_prediction_red_on_known_bad(qtbot, tmp_path):
    """bad.pdf: 183 mm wide, 8 pt under a 0.4 scale = 3.2 pt effective.
    The default document is 183 mm wide too, so k = 1.0 and the placed
    values equal the in-asset effectives — deterministic verdicts."""
    win = MainWindow()
    qtbot.addWidget(win)
    pid = _drop_pdf(win, tmp_path, "bad")
    win.do_action("select", pid)
    text = win.sidebar.lbl_prediction.text()
    assert win.sidebar.lbl_prediction.isVisibleTo(win.sidebar.asset_box)
    assert "3.2 pt → 3.20 pt ✗" in text
    assert "line 0.2 pt → 0.20 pt ✗" in text


def test_pdf_prediction_reacts_to_panel_resize(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    pid = _drop_pdf(win, tmp_path, "good")
    win.do_action("select", pid)
    first = win.sidebar.lbl_prediction.text()
    win.topbar.width_spin.setValue(89.0)  # narrow the figure → smaller k
    win.do_action("select", pid)
    assert win.sidebar.lbl_prediction.text() != first


def test_raster_drop_still_shows_dpi_rows(qtbot, tmp_path):
    from PySide6.QtGui import QImage
    win = MainWindow()
    qtbot.addWidget(win)
    img = QImage(400, 300, QImage.Format_RGB32)
    img.fill(0xFFFFFFFF)
    png = tmp_path / "a.png"
    img.save(str(png))
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(png))
    win.do_action("select", pid)
    sb = win.sidebar
    assert sb.dpi_edit.isVisibleTo(sb.asset_box)  # vector-mode hiding reverts
    assert sb.lbl_asset_dpi.isVisibleTo(sb.asset_box)
    assert not sb.lbl_prediction.isVisibleTo(sb.asset_box)
    assert "px" in sb.lbl_asset_px.text()