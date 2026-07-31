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


def test_label_style_follows_preset(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    from figspec.layout.tree import iter_panels
    pid = next(iter_panels(win.doc.tree)).id
    win.topbar.preset_combo.setCurrentText("science_double")
    assert win.doc.constraints.panel_label_style == "uppercase"
    assert win.canvas.panel_widgets()[pid].label_widget.text() == "A"
    win.do_action("select", pid)
    assert win.sidebar.lbl_label.text() == "A"
    win.topbar.preset_combo.setCurrentText("aps_double")
    assert win.canvas.panel_widgets()[pid].label_widget.text() == "(a)"
    # spec export keeps internal lowercase labels regardless of display
    assert win.doc.to_spec_dict()["panels"][0]["label"] == "a"


def test_label_style_survives_spec_roundtrip(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.topbar.preset_combo.setCurrentText("science_double")
    data = win.doc.to_spec_dict()
    assert data["constraints"]["panel_label_style"] == "uppercase"


def test_sync_settings_preserves_min_effective_dpi(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.doc.constraints.min_effective_dpi = 450
    win.topbar.gutter_spin.setValue(5.0)  # triggers _on_settings_changed
    assert win.doc.constraints.min_effective_dpi == 450


def test_wireframe_export_uses_label_style(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    win.topbar.preset_combo.setCurrentText("science_double")
    from figspec_designer.ui.preview_export import render_layout_png
    out = tmp_path / "wf.png"
    assert render_layout_png(win.doc, out) is True
    # can't OCR the letter; assert the code path accepts the style without
    # error and the file is written (letter correctness is pinned by the
    # canvas/sidebar assertions above via the same format_label call)
    assert out.stat().st_size > 0
