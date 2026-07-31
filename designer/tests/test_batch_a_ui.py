import types
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox
from figspec.layout.tree import iter_panels
from figspec_designer.ui.main_window import MainWindow

# QSettings isolation for this module is provided by the suite-wide
# autouse fixture in designer/tests/conftest.py (_isolated_designer_settings);
# no file-local duplicate here.

# Captured at collection time -- i.e. BEFORE conftest's autouse
# _no_blocking_close_dialog fixture patches MainWindow.confirm_discard for
# any given test -- so tests that want to exercise the real
# confirm_discard() implementation (bypassing that default) can rebind it.
_REAL_CONFIRM_DISCARD = MainWindow.confirm_discard


def _win(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    first = next(iter_panels(win.doc.tree)).id
    win.do_action("split_right", first)
    return win, first


def test_sidebar_size_edit_resizes(qtbot):
    win, first = _win(qtbot)
    win.do_action("select", first)
    win.sidebar.spin_w.setValue(100.0)
    win.sidebar.spin_w.editingFinished.emit()
    rects = {r.panel_id: r for r in win.doc.panel_rects()}
    assert rects[first].w_mm == pytest.approx(100.0)


def test_sidebar_shows_position_and_aspect(qtbot):
    win, first = _win(qtbot)
    win.do_action("select", first)
    assert win.sidebar.lbl_xy.text().startswith("0.0, 0.0")
    assert ":" in win.sidebar.lbl_aspect.text() or "." in win.sidebar.lbl_aspect.text()


def test_make_square(qtbot):
    win, first = _win(qtbot)
    win.do_action("split_down", [p.id for p in iter_panels(win.doc.tree)
                                 if p.id != first][0])
    win.do_action("select", first)
    win.sidebar.btn_square.click()
    rects = {r.panel_id: r for r in win.doc.panel_rects()}
    assert rects[first].h_mm == pytest.approx(rects[first].w_mm, abs=0.05)


def test_placement_table(qtbot):
    win, first = _win(qtbot)
    win.copy_placement_table()
    text = QApplication.clipboard().text()
    lines = text.strip().split("\n")
    assert lines[0] == "label\tx_mm\ty_mm\tw_mm\th_mm"
    assert len(lines) == 3  # header + 2 panels
    assert lines[1].startswith("a\t0.00\t0.00\t")


def test_rejected_size_edit_does_not_cause_spurious_reemit(qtbot):
    # Regression: Sidebar._emit_size used to write self._shown_w/_shown_h
    # AFTER emitting size_edited. When the edit is rejected, the synchronous
    # emit -> MainWindow._on_size_edited -> _refresh_sidebar -> show_panel
    # chain correctly resets _shown_w back to the real value, but control
    # then returns to _emit_size and clobbers that reset with the rejected
    # (stale) value. The next editingFinished -- even with no user change --
    # then spuriously re-emits size_edited and pushes a redundant undo entry.
    win, first = _win(qtbot)
    win.do_action("select", first)
    depth_before = len(win.history._undo)
    got = []
    win.sidebar.size_edited.connect(lambda pid, axis, v: got.append((pid, axis, v)))

    win.sidebar.spin_w.setValue(500.0)  # out of range for this layout -> rejected
    win.sidebar.spin_w.editingFinished.emit()
    assert len(got) == 1  # the rejected attempt itself still emits once
    assert win.sidebar.spin_w.value() == pytest.approx(89.5)  # snapped back
    assert len(win.history._undo) == depth_before  # rejected -> no tree push

    win.sidebar.spin_w.editingFinished.emit()  # no further user change
    assert len(got) == 1  # must NOT spuriously re-emit
    assert len(win.history._undo) == depth_before  # must NOT push a redundant entry


def test_aspect_lock_roundtrips_via_export(qtbot):
    win, first = _win(qtbot)
    win.do_action("select", first)
    win.sidebar.chk_aspect_lock.setChecked(True)
    tree_panel = next(p for p in iter_panels(win.doc.tree) if p.id == first)
    assert tree_panel.aspect_lock is not None


# ---- amber aspectBadge: canvas -> PanelWidget wiring -----------------------

def test_aspect_badge_hidden_without_lock(qtbot):
    win, first = _win(qtbot)
    widget = win.canvas.panel_widgets()[first]
    assert widget.aspect_badge.objectName() == "aspectBadge"
    assert not widget.aspect_badge.isVisibleTo(widget)


def test_aspect_badge_visible_on_violation(qtbot):
    win, first = _win(qtbot)
    win.do_action("select", first)
    win.sidebar.chk_aspect_lock.setChecked(True)  # locks at current ratio (~0.895)
    win.sidebar.spin_w.setValue(150.0)  # blows well past the 2% tolerance
    win.sidebar.spin_w.editingFinished.emit()
    widget = win.canvas.panel_widgets()[first]
    assert widget.aspect_badge.isVisibleTo(widget)


def test_aspect_badge_hidden_when_within_tolerance(qtbot):
    win, first = _win(qtbot)
    win.do_action("select", first)
    win.sidebar.chk_aspect_lock.setChecked(True)
    widget = win.canvas.panel_widgets()[first]
    assert not widget.aspect_badge.isVisibleTo(widget)


# ---- Task 3: file lifecycle -------------------------------------------------

def test_dirty_flag_and_title(qtbot, tmp_path):
    win, first = _win(qtbot)
    assert win.dirty is True  # split marked dirty
    p = tmp_path / "f.figspec.json"
    win.save_json(p)  # low-level write does NOT manage state
    win.current_path = p
    win.save()
    assert win.dirty is False
    assert "•" not in win.windowTitle()
    win.do_action("split_down", first)
    assert win.dirty is True and "•" in win.windowTitle()


def test_save_silent_with_path(qtbot, tmp_path):
    win, _ = _win(qtbot)
    p = tmp_path / "f.figspec.json"
    win.current_path = p
    assert win.save() is True
    assert p.exists()


def test_recent_files_tracked(qtbot, tmp_path):
    win, _ = _win(qtbot)
    p = tmp_path / "f.figspec.json"
    win.current_path = p
    win.save()
    assert str(p) in win.recent_files()


def test_open_marks_clean_and_recent(qtbot, tmp_path):
    win, _ = _win(qtbot)
    p = tmp_path / "f.figspec.json"
    win.current_path = p
    win.save()
    win2 = MainWindow()
    qtbot.addWidget(win2)
    assert win2.open_json(p) is None
    assert win2.dirty is False and win2.current_path == p


# ---- Task 3 supplementary: close guard + recents (Global Constraints,
# not covered by the brief's literal Step-1 block) --------------------------

def test_confirm_discard_clean_returns_true_without_dialog(qtbot):
    win, _ = _win(qtbot)
    win.dirty = False
    assert win.confirm_discard() is True  # no QMessageBox needed when clean


class _FakeCloseEvent:
    def __init__(self):
        self.accepted = None

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.accepted = False


def test_close_event_cancel_ignores(qtbot, monkeypatch):
    win, _ = _win(qtbot)
    assert win.dirty is True
    monkeypatch.setattr(win, "confirm_discard", lambda: False)  # user hit Cancel
    event = _FakeCloseEvent()
    win.closeEvent(event)
    assert event.accepted is False


def test_close_event_discard_or_save_accepts(qtbot, monkeypatch):
    win, _ = _win(qtbot)
    monkeypatch.setattr(win, "confirm_discard", lambda: True)  # Save or Discard
    event = _FakeCloseEvent()
    win.closeEvent(event)
    assert event.accepted is True


def test_recent_files_dedup_mru_order_and_max_five(qtbot, tmp_path):
    win, _ = _win(qtbot)
    paths = [tmp_path / f"f{i}.json" for i in range(6)]
    for p in paths:
        win.current_path = p
        win.save()
    # max 5, most-recent first
    assert win.recent_files() == [str(p) for p in reversed(paths[1:])]
    # re-saving an already-recent path moves it to front without duplicating
    win.current_path = paths[3]
    win.save()
    assert win.recent_files()[0] == str(paths[3])
    assert win.recent_files().count(str(paths[3])) == 1
    assert len(win.recent_files()) == 5


def test_recent_menu_clear_empties_recent_files(qtbot, tmp_path):
    win, _ = _win(qtbot)
    p = tmp_path / "f.figspec.json"
    win.current_path = p
    win.save()
    assert win.recent_files() == [str(p)]
    win._clear_recent()
    assert win.recent_files() == []


# ---- Post-review fixes ------------------------------------------------------

def test_fresh_window_is_not_dirty(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.dirty is False
    assert "•" not in win.windowTitle()


def test_open_recent_respects_confirm_discard(qtbot, tmp_path, monkeypatch):
    win, _ = _win(qtbot)
    assert win.dirty is True
    doc_before = win.doc
    other_path = tmp_path / "other.figspec.json"
    other_path.write_text(win.export_json_text())

    monkeypatch.setattr(win, "confirm_discard", lambda: False)  # user hit Cancel
    win._open_recent(str(other_path))
    assert win.doc is doc_before  # cancelled -- current doc untouched

    monkeypatch.setattr(win, "confirm_discard", lambda: True)  # Save or Discard
    win._open_recent(str(other_path))
    assert win.doc is not doc_before  # proceeded -- open_json replaced doc


def test_save_returns_false_when_ask_save_path_cancelled(qtbot, monkeypatch):
    win, _ = _win(qtbot)
    win.current_path = None
    monkeypatch.setattr(win, "_ask_save_path", lambda: None)  # dialog cancelled
    assert win.save() is False


def test_confirm_discard_save_choice_routes_through_save(qtbot, monkeypatch):
    win, _ = _win(qtbot)
    assert win.dirty is True
    # Rebind the real (unpatched-by-conftest) implementation to this
    # instance so this test exercises confirm_discard()'s actual
    # Save/Discard/Cancel logic rather than conftest's always-True default.
    monkeypatch.setattr(win, "confirm_discard",
                        types.MethodType(_REAL_CONFIRM_DISCARD, win))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Save)
    save_calls = []
    monkeypatch.setattr(win, "save", lambda: save_calls.append(True) or True)
    assert win.confirm_discard() is True
    assert save_calls == [True]
