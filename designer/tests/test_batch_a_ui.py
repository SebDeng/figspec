import pytest
from PySide6.QtWidgets import QApplication
from figspec.layout.tree import iter_panels
from figspec_designer.ui.main_window import MainWindow


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
