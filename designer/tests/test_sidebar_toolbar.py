import pytest
from figspec_designer.model.flatten import PanelRect
from figspec_designer.ui.sidebar import Sidebar, _aspect_text
from figspec_designer.ui.toolbar import TopBar


def test_sidebar_shows_values(qtbot):
    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.show_panel("p1", "b", PanelRect("p1", 93.5, 0.0, 89.5, 57.6), 600, "hero")
    assert sb.lbl_label.text() == "b"
    assert sb.spin_w.value() == pytest.approx(89.5)
    assert sb.spin_h.value() == pytest.approx(57.6)
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


# ---- Minor 4: no-op Enter in hint field must not spuriously emit ----------

def test_emit_hint_noop_when_unchanged(qtbot):
    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.show_panel("p1", "a", PanelRect("p1", 0.0, 0.0, 10.0, 10.0), 300, "orig")
    got = []
    sb.content_hint_edited.connect(lambda pid, t: got.append((pid, t)))
    sb.hint_edit.editingFinished.emit()  # no text change -- e.g. plain Enter
    assert got == []
    sb.hint_edit.setText("changed")
    sb.hint_edit.editingFinished.emit()
    assert got == [("p1", "changed")]
    sb.hint_edit.editingFinished.emit()  # confirming again with no further change
    assert got == [("p1", "changed")]  # must NOT re-emit


# ---- Minor 5: reduced w:h fraction alongside the decimal aspect ----------

def test_aspect_text_reduces_to_small_integer_ratio():
    assert _aspect_text(89.5, 89.5) == "1:1 · 1.000:1"
    assert _aspect_text(120.0, 80.0) == "3:2 · 1.500:1"


def test_aspect_text_falls_back_to_decimal_when_reduction_is_large():
    text = _aspect_text(91.3, 58.7)
    assert "·" not in text
    assert text.endswith(":1")


def test_sidebar_shows_reduced_aspect_fraction(qtbot):
    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.show_panel("p1", "b", PanelRect("p1", 0.0, 0.0, 120.0, 80.0), 300, "")
    assert sb.lbl_aspect.text() == "3:2 · 1.500:1"


# ---- Minor 7: aspect lock uses exact shown values, not 1dp spinboxes ------

def test_aspect_lock_uses_exact_shown_values_not_rounded_spinboxes(qtbot):
    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.show_panel("p1", "a", PanelRect("p1", 0.0, 0.0, 91.333, 47.111), 300, "")
    got = []
    sb.aspect_lock_toggled.connect(lambda pid, v: got.append(v))
    sb.chk_aspect_lock.setChecked(True)
    assert got == [91.333 / 47.111]
    sb.chk_aspect_lock.setChecked(False)
    assert got[-1] is None


# ---- F5: constraints spinboxes on TopBar ----------------------------------

def test_topbar_constraint_spin_defaults():
    tb = TopBar()
    assert tb.min_font_spin.value() == pytest.approx(5.0)
    assert tb.max_font_spin.value() == pytest.approx(7.0)
    assert tb.min_lw_spin.value() == pytest.approx(0.25)
    vals = tb.values()
    assert len(vals) == 8
    assert vals[5:8] == pytest.approx((5.0, 7.0, 0.25))


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


# ---- Task 2: TopBar preset -> constraints wiring ---------------------------

def test_preset_applies_constraints(qtbot):
    from figspec_designer.ui.toolbar import TopBar
    tb = TopBar()
    qtbot.addWidget(tb)
    got = []
    tb.settings_changed.connect(lambda: got.append(1))
    tb.preset_combo.setCurrentText("acs_single")
    assert tb.values()[1] == 84.7
    assert tb.min_font_spin.value() == 4.5
    assert tb.max_font_spin.value() == 8.0
    assert tb.min_lw_spin.value() == 0.5
    assert len(got) == 1  # ONE settings_changed for the whole batch


def test_custom_preserves_constraints(qtbot):
    from figspec_designer.ui.toolbar import TopBar
    tb = TopBar()
    qtbot.addWidget(tb)
    tb.preset_combo.setCurrentText("acs_single")
    tb.preset_combo.setCurrentText("custom")
    assert tb.min_font_spin.value() == 4.5  # untouched
    assert tb.width_spin.isEnabled()


def test_mainwindow_initial_constraints_match_preset(qtbot):
    from figspec_designer.ui.main_window import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.doc.constraints.min_font_pt == 5.0
    assert win.doc.constraints.max_font_pt == 7.0   # nature_double preset
    assert win.doc.constraints.min_linewidth_pt == 0.25
