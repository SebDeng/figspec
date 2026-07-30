from figspec_designer.model.flatten import PanelRect
from figspec_designer.ui.sidebar import Sidebar
from figspec_designer.ui.toolbar import TopBar


def test_sidebar_shows_values(qtbot):
    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.show_panel("p1", "b", PanelRect("p1", 93.5, 0.0, 89.5, 57.6), 600, "hero")
    assert sb.lbl_label.text() == "b"
    assert "89.5" in sb.lbl_mm.text() and "57.6" in sb.lbl_mm.text()
    assert "2114" in sb.lbl_px.text()
    assert "3.524" in sb.lbl_figsize.text()
    assert sb.hint_edit.text() == "hero"
    got = []
    sb.content_hint_edited.connect(lambda pid, t: got.append((pid, t)))
    sb.hint_edit.setText("new hint")
    sb.hint_edit.editingFinished.emit()
    assert got[-1] == ("p1", "new hint")
    sb.clear()
    assert sb.lbl_label.text() == "—"


def test_topbar_preset_drives_width(qtbot):
    tb = TopBar()
    qtbot.addWidget(tb)
    tb.preset_combo.setCurrentText("nature_single")
    assert tb.values()[0] == "nature_single"
    assert tb.values()[1] == 89.0
    assert not tb.width_spin.isEnabled()
    tb.preset_combo.setCurrentText("custom")
    assert tb.width_spin.isEnabled()
    tb.width_spin.setValue(120.0)
    assert tb.values()[1] == 120.0


def test_topbar_signals(qtbot):
    tb = TopBar()
    qtbot.addWidget(tb)
    got = []
    tb.settings_changed.connect(lambda: got.append("settings"))
    tb.save_requested.connect(lambda: got.append("save"))
    tb.height_spin.setValue(120.0)
    tb.btn_save.click()
    assert "settings" in got and "save" in got
