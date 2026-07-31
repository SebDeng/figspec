"""Batch B UI tests: height warning, preset tooltips, label style, lint dock."""
from PySide6.QtCore import Qt

from figspec_designer.ui.main_window import MainWindow


def test_preset_tooltips(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    combo = win.topbar.preset_combo
    tip = combo.itemData(combo.findText("nature_double"), Qt.ToolTipRole)
    assert tip and "183" in tip
    assert combo.itemData(combo.findText("custom"), Qt.ToolTipRole) in (None, "")


def test_height_warning_flips_property(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    spin = win.topbar.height_spin
    assert spin.property("overLimit") is not True  # 100mm under 170 limit
    spin.setValue(180.0)  # nature_double limit 170
    assert spin.property("overLimit") is True
    assert "170" in spin.toolTip()
    spin.setValue(150.0)
    assert spin.property("overLimit") is not True
    assert spin.toolTip() == ""


def test_no_warning_for_custom_or_aps(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.topbar.preset_combo.setCurrentText("aps_single")
    win.topbar.height_spin.setValue(500.0)
    assert win.topbar.height_spin.property("overLimit") is not True
    win.topbar.preset_combo.setCurrentText("custom")
    assert win.topbar.height_spin.property("overLimit") is not True
