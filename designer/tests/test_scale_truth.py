"""Batch D UI tests: source-DPI auto-read, scale factor, calculator, card."""
import pytest

from figspec.layout.tree import iter_panels
from figspec_designer.ui.main_window import MainWindow


def _make_png(tmp_path, w=1472, h=879, dpi=None, name="asset.png"):
    from PySide6.QtGui import QImage
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(0xFFFFFFFF)
    if dpi is not None:
        dpm = round(dpi / 25.4 * 1000)
        img.setDotsPerMeterX(dpm)
        img.setDotsPerMeterY(dpm)
    path = tmp_path / name
    img.save(str(path))
    return path


def test_drop_reads_resolution_metadata(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    png = _make_png(tmp_path, dpi=220)
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(png))
    assert next(iter_panels(win.doc.tree)).asset_dpi == pytest.approx(220, abs=1)


def test_drop_without_metadata_records_none(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    png = _make_png(tmp_path)  # Qt-default dots/meter == indistinguishable
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(png))
    assert next(iter_panels(win.doc.tree)).asset_dpi is None


def test_remove_asset_clears_dpi(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    png = _make_png(tmp_path, dpi=220)
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(png))
    win._on_asset_removed(pid)
    panel = next(iter_panels(win.doc.tree))
    assert panel.asset is None and panel.asset_dpi is None


# ---- sidebar block (task D3) --------------------------------------------

def _drop_and_select(win, tmp_path, dpi=None):
    from figspec import scaling
    png = _make_png(tmp_path, dpi=dpi)
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(png))
    win.do_action("select", pid)
    rect = next(r for r in win.doc.panel_rects() if r.panel_id == pid)
    k = scaling.placement_scale(
        (rect.w_mm, rect.h_mm),
        scaling.asset_size_mm((1472, 879), dpi or 96.0))
    return pid, rect, k


def test_sidebar_scale_block_assumed_dpi(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    _pid, _rect, k = _drop_and_select(win, tmp_path)
    sb = win.sidebar
    assert sb.lbl_scale.text() == f"×{k:.3f}"
    assert sb.dpi_edit.text() == "96"
    assert sb.lbl_dpi_src.text() == "(assumed)"


def test_sidebar_calculator_two_way(qtbot, tmp_path):
    import pytest as _pytest
    win = MainWindow()
    qtbot.addWidget(win)
    _pid, _rect, k = _drop_and_select(win, tmp_path)
    sb = win.sidebar
    sb.calc_nominal.setValue(8.0)
    assert sb.calc_effective.value() == _pytest.approx(8.0 * k, abs=0.01)
    sb.calc_effective.setValue(5.0)
    assert sb.calc_nominal.value() == _pytest.approx(5.0 / k, abs=0.05)


def test_sidebar_dpi_edit_updates_scale(qtbot, tmp_path):
    from figspec import scaling
    win = MainWindow()
    qtbot.addWidget(win)
    pid, rect, _k = _drop_and_select(win, tmp_path)
    sb = win.sidebar
    sb.dpi_edit.setText("220")
    sb.dpi_edit.editingFinished.emit()
    panel = next(iter_panels(win.doc.tree))
    assert panel.asset_dpi == pytest.approx(220.0)
    k2 = scaling.placement_scale(
        (rect.w_mm, rect.h_mm), scaling.asset_size_mm((1472, 879), 220.0))
    assert sb.lbl_scale.text() == f"×{k2:.3f}"
    assert sb.lbl_dpi_src.text() == "(declared)"
    assert win.dirty


def test_sidebar_declared_dpi_shown(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    _drop_and_select(win, tmp_path, dpi=300)
    sb = win.sidebar
    assert float(sb.dpi_edit.text()) == pytest.approx(300, abs=1)
    assert sb.lbl_dpi_src.text() == "(declared)"


def test_no_asset_hides_block(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    pid = next(iter_panels(win.doc.tree)).id
    win.do_action("select", pid)
    assert not win.sidebar.asset_box.isVisibleTo(win.sidebar)


# ---- authoring card (task D4) -------------------------------------------

def test_copy_authoring_card_with_asset(qtbot, tmp_path):
    from PySide6.QtWidgets import QApplication
    win = MainWindow()
    qtbot.addWidget(win)
    _drop_and_select(win, tmp_path)
    win.copy_authoring_card()  # batch I: card lives in Hand Off
    text = QApplication.clipboard().text()
    assert text.startswith("FigSpec authoring card")
    assert "Option 1" in text and "Option 2" in text and "Option 3" in text


def test_copy_authoring_card_without_asset(qtbot):
    from PySide6.QtWidgets import QApplication
    win = MainWindow()
    qtbot.addWidget(win)
    pid = next(iter_panels(win.doc.tree)).id
    win.do_action("select", pid)
    win.copy_authoring_card()  # batch I: card lives in Hand Off
    text = QApplication.clipboard().text()
    assert "Option 1" in text and "Option 2" not in text
    assert "Option 3" not in text
