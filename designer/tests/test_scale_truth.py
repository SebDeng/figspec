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
