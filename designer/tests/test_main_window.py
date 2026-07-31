import json
import pytest
from figspec.spec import Constraints, parse_spec
from figspec_designer.model.tree import iter_panels
from figspec_designer.ui.main_window import MainWindow


def _first_panel(win):
    return next(iter_panels(win.doc.tree)).id


def test_split_and_labels(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    assert len(list(iter_panels(win.doc.tree))) == 2
    assert sorted(win.doc.labels().values()) == ["a", "b"]


def test_close_last_panel_is_noop(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("close", _first_panel(win))
    assert len(list(iter_panels(win.doc.tree))) == 1


def test_undo_redo(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    assert len(list(iter_panels(win.doc.tree))) == 2
    win.undo()
    assert len(list(iter_panels(win.doc.tree))) == 1
    win.redo()
    assert len(list(iter_panels(win.doc.tree))) == 2


# ---- Important 2: undo/redo after save must not leave doc marked clean ----

def test_undo_after_save_marks_dirty(qtbot, tmp_path, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    monkeypatch.setattr(win, "_ask_save_path", lambda: tmp_path / "f.json")
    assert win.save() is True
    assert win.dirty is False
    win.undo()
    assert win.dirty is True  # content now differs from what's on disk


def test_undo_with_nothing_to_undo_does_not_mark_dirty(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.dirty is False
    win.undo()  # empty history -- History.undo() is a no-op at the boundary
    assert win.dirty is False


def test_redo_after_save_marks_dirty(qtbot, tmp_path, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    win.undo()
    monkeypatch.setattr(win, "_ask_save_path", lambda: tmp_path / "f.json")
    assert win.save() is True
    assert win.dirty is False
    win.redo()
    assert win.dirty is True


def test_redo_with_nothing_to_redo_does_not_mark_dirty(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.dirty is False
    win.redo()  # nothing was undone -- no-op
    assert win.dirty is False


def test_apply_ratios_updates_model(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    win.apply_ratios((), (0.6, 0.4))
    rects = sorted(win.doc.panel_rects(), key=lambda r: r.x_mm)
    assert abs(rects[0].w_mm - (183 - 4) * 0.6) < 1e-6


# ---- Important 3a: split_right/split_down route real page dims into the
# ops.split_panel min-size guard ---------------------------------------------

def test_split_right_enforces_min_size_guard_end_to_end(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    first = _first_panel(win)
    win.do_action("split_right", first)  # 2 panels, default 183x100mm/gutter4
    win.apply_ratios((), (5 / 179, 174 / 179))  # pin `first` to exactly 5mm wide
    rects = {r.panel_id: r for r in win.doc.panel_rects()}
    assert rects[first].w_mm == pytest.approx(5.0)
    before_count = len(list(iter_panels(win.doc.tree)))
    win.do_action("split_right", first)  # would shrink both halves under 5mm
    assert len(list(iter_panels(win.doc.tree))) == before_count  # rejected


def test_export_valid_and_copy(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    data = json.loads(win.export_json_text())
    target, constraints, panels, designer = parse_spec(data)
    assert len(panels) == 2 and designer is not None
    win.copy_json()
    from PySide6.QtWidgets import QApplication
    assert json.loads(QApplication.clipboard().text()) == data


def test_save_and_open_roundtrip(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_down", _first_panel(win))
    p = tmp_path / "layout.figspec.json"
    win.save_json(p)
    win2 = MainWindow()
    qtbot.addWidget(win2)
    assert win2.open_json(p) is None  # no error
    assert win2.doc.to_spec_dict() == win.doc.to_spec_dict()


def test_open_without_sidecar_reports_error(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    data = win.doc.to_spec_dict()
    del data["designer"]
    p = tmp_path / "plain.json"
    p.write_text(json.dumps(data))
    err = win.open_json(p)
    assert err is not None and "designer" in err


def test_open_with_malformed_tree_reports_error(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    data = win.doc.to_spec_dict()
    data["designer"]["tree"] = {"type": "bogus"}
    p = tmp_path / "malformed.json"
    p.write_text(json.dumps(data))
    err = win.open_json(p)
    assert err is not None
    assert len(list(iter_panels(win.doc.tree))) >= 1


# ---- Minor 8: "Save JSON…" no longer promises a dialog it doesn't show ---

def test_save_menu_label_has_no_ellipsis(qtbot):
    from PySide6.QtGui import QAction
    win = MainWindow()
    qtbot.addWidget(win)
    texts = {a.text() for a in win.findChildren(QAction)}
    assert "Save JSON" in texts
    assert "Save JSON…" not in texts
    assert "Save As…" in texts  # unchanged -- it does show a dialog


def test_smoke_flag():
    from figspec_designer.app import main
    assert main(["--smoke"]) == 0


# ---- F1: typed hint flushed when switching panels without Enter ----------

def test_typed_hint_flushed_on_panel_switch(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    first_pid = _first_panel(win)
    win.do_action("split_right", first_pid)
    other_pid = next(p.id for p in iter_panels(win.doc.tree) if p.id != first_pid)
    win.do_action("select", first_pid)
    win.sidebar.hint_edit.setText("typed but not confirmed")
    # no editingFinished emitted -- simulates clicking another panel directly
    win.do_action("select", other_pid)
    panels = {p.id: p for p in iter_panels(win.doc.tree)}
    assert panels[first_pid].content_hint == "typed but not confirmed"


def test_unchanged_hint_does_not_spuriously_push_history(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    first_pid = _first_panel(win)
    win.do_action("split_right", first_pid)
    other_pid = next(p.id for p in iter_panels(win.doc.tree) if p.id != first_pid)
    win.do_action("select", first_pid)
    depth_before = len(win.history._undo) if hasattr(win.history, "_undo") else None
    win.do_action("select", other_pid)  # hint_edit untouched -> no emit expected
    if depth_before is not None:
        assert len(win.history._undo) == depth_before


# ---- F2: open_json broadened to catch all malformed-sidecar shapes -------

def _mutate_designer_int(data):
    data["designer"] = 5


def _mutate_tree_list(data):
    data["designer"]["tree"] = [1, 2, 3]


def _mutate_tree_str(data):
    data["designer"]["tree"] = "not-a-tree"


def _mutate_panel_missing_id(data):
    del data["designer"]["tree"]["children"][0]["id"]


def _mutate_ratios_int(data):
    data["designer"]["tree"]["ratios"] = 5


@pytest.mark.parametrize("mutate", [
    _mutate_designer_int,
    _mutate_tree_list,
    _mutate_tree_str,
    _mutate_panel_missing_id,
    _mutate_ratios_int,
], ids=["designer-int", "tree-list", "tree-str", "panel-no-id", "ratios-int"])
def test_open_json_malformed_shapes_report_error(qtbot, tmp_path, mutate):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))  # gives tree a "ratios" key
    data = win.doc.to_spec_dict()
    mutate(data)
    p = tmp_path / "malformed.json"
    p.write_text(json.dumps(data))
    doc_before = win.doc
    err = win.open_json(p)
    assert err is not None
    assert win.doc is doc_before


# ---- F5: constraints spinboxes round-trip through export/open ------------

def test_export_reflects_constraint_spin_changes(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.topbar.min_font_spin.setValue(6.5)
    win.topbar.max_font_spin.setValue(9.5)
    win.topbar.min_lw_spin.setValue(0.75)
    data = json.loads(win.export_json_text())
    assert data["constraints"]["min_font_pt"] == 6.5
    assert data["constraints"]["max_font_pt"] == 9.5
    assert data["constraints"]["min_linewidth_pt"] == 0.75


def test_open_syncs_constraint_spinboxes(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    win.doc.constraints = Constraints(min_font_pt=6.0, max_font_pt=9.0,
                                      min_linewidth_pt=0.7)
    p = tmp_path / "custom_constraints.json"
    p.write_text(win.doc.to_json())
    win2 = MainWindow()
    qtbot.addWidget(win2)
    assert win2.open_json(p) is None
    assert win2.topbar.min_font_spin.value() == pytest.approx(6.0)
    assert win2.topbar.max_font_spin.value() == pytest.approx(9.0)
    assert win2.topbar.min_lw_spin.value() == pytest.approx(0.7)


def test_topbar_edit_preserves_min_effective_dpi(qtbot):
    # Regression: _sync_settings() used to rebuild Constraints from only the
    # three topbar fields, silently resetting min_effective_dpi to its
    # dataclass default (300) on every topbar edit -- even one unrelated to
    # DPI, like nudging the gutter.
    win = MainWindow()
    qtbot.addWidget(win)
    win.doc.constraints.min_effective_dpi = 450
    win.topbar.gutter_spin.setValue(5.0)
    assert win.doc.constraints.min_effective_dpi == 450
    assert win.doc.constraints.min_font_pt == pytest.approx(win.topbar.min_font_spin.value())
    assert win.doc.constraints.max_font_pt == pytest.approx(win.topbar.max_font_spin.value())
    assert win.doc.constraints.min_linewidth_pt == pytest.approx(win.topbar.min_lw_spin.value())


def test_preset_export_with_aps_single(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.topbar.preset_combo.setCurrentText("aps_single")
    data = json.loads(win.export_json_text())
    assert data["constraints"]["min_font_pt"] == 8.0
    assert data["constraints"]["max_font_pt"] == 10.0
    assert data["constraints"]["min_linewidth_pt"] == 0.5
    assert data["target"]["figure_width_mm"] == 85.0
