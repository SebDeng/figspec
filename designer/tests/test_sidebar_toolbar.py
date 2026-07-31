import pytest
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


# ---- F1: Sidebar.flush_pending -------------------------------------------

def test_flush_pending_emits_only_on_real_change(qtbot):
    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.show_panel("p1", "a", PanelRect("p1", 0.0, 0.0, 10.0, 10.0), 300, "orig")
    got = []
    sb.content_hint_edited.connect(lambda pid, t: got.append((pid, t)))

    sb.flush_pending()
    assert got == []  # nothing typed -> no spurious emit

    sb.hint_edit.setText("typed")
    sb.flush_pending()
    assert got == [("p1", "typed")]

    sb.flush_pending()  # calling again with no further change -> no dup emit
    assert got == [("p1", "typed")]


def test_flush_pending_noop_when_no_panel_shown(qtbot):
    sb = Sidebar()
    qtbot.addWidget(sb)
    got = []
    sb.content_hint_edited.connect(lambda pid, t: got.append((pid, t)))
    sb.hint_edit.setText("stray text")
    sb.flush_pending()
    assert got == []


# ---- F5: constraints spinboxes on TopBar ----------------------------------

def test_topbar_constraint_spin_defaults():
    tb = TopBar()
    assert tb.min_font_spin.value() == pytest.approx(5.0)
    assert tb.max_font_spin.value() == pytest.approx(8.0)
    assert tb.min_lw_spin.value() == pytest.approx(0.5)
    vals = tb.values()
    assert len(vals) == 8
    assert vals[5:8] == pytest.approx((5.0, 8.0, 0.5))


def test_topbar_constraint_spin_changes_emit_settings_changed(qtbot):
    tb = TopBar()
    qtbot.addWidget(tb)
    got = []
    tb.settings_changed.connect(lambda: got.append("settings"))
    tb.min_font_spin.setValue(6.0)
    assert "settings" in got
    assert tb.values()[5] == pytest.approx(6.0)


def test_topbar_set_values_syncs_constraint_spins(qtbot):
    tb = TopBar()
    qtbot.addWidget(tb)
    tb.set_values("nature_double", 183.0, 120.0, 600, 4.0, 7.0, 9.0, 0.8)
    assert tb.min_font_spin.value() == pytest.approx(7.0)
    assert tb.max_font_spin.value() == pytest.approx(9.0)
    assert tb.min_lw_spin.value() == pytest.approx(0.8)


# ---- Task 1: corrected journal presets + constraints ----------------------

def test_preset_values_corrected():
    from figspec_designer import presets
    assert presets.PRESETS["acs_single"] == 84.7
    assert presets.PRESETS["acs_double"] == 177.8
    assert presets.PRESETS["aps_single"] == 85.0
    assert presets.PRESETS["aps_double"] == 178.0
    assert presets.PRESETS["nature_research_single"] == 88.0
    assert presets.PRESETS["science_double"] == 183.0


def test_all_presets_have_constraints():
    from figspec_designer import presets
    assert set(presets.PRESET_CONSTRAINTS) == set(presets.PRESETS)
    assert presets.PRESET_CONSTRAINTS["nature_single"] == {
        "min_font_pt": 5.0, "max_font_pt": 7.0, "min_linewidth_pt": 0.25}
    assert presets.PRESET_CONSTRAINTS["acs_double"]["min_font_pt"] == 4.5
    assert presets.PRESET_CONSTRAINTS["aps_single"]["min_font_pt"] == 8.0
