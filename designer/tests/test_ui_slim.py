"""Batch I tests: hand-off palette, slim top bar, sidebar layers, status strip."""
import pytest
from PySide6.QtWidgets import QApplication

from figspec.layout.tree import iter_panels
from figspec_designer.ui.main_window import MainWindow


# ---- I1: Hand Off palette -----------------------------------------------

def test_handoff_dialog_has_seven_rows(qtbot):
    from figspec_designer.ui.handoff import HandoffDialog
    win = MainWindow()
    qtbot.addWidget(win)
    dlg = HandoffDialog(win)
    qtbot.addWidget(dlg)
    assert len(dlg.rows) == 7
    # panel-scoped rows disabled with no selection
    titles = [b.text().split("\n")[0] for b in dlg.rows]
    artboard = dlg.rows[titles.index("Panel artboard")]
    card = dlg.rows[[t.startswith("Authoring card") for t in titles].index(True)]
    assert not artboard.isEnabled() and not card.isEnabled()


def test_handoff_rows_enable_with_selection(qtbot):
    from figspec_designer.ui.handoff import HandoffDialog
    win = MainWindow()
    qtbot.addWidget(win)
    pid = next(iter_panels(win.doc.tree)).id
    win.do_action("select", pid)
    dlg = HandoffDialog(win)
    qtbot.addWidget(dlg)
    assert all(b.isEnabled() for b in dlg.rows)
    assert any("(a)" in b.text() for b in dlg.rows)


def test_handoff_snippet_row_copies(qtbot):
    from figspec_designer.ui.handoff import HandoffDialog
    win = MainWindow()
    qtbot.addWidget(win)
    dlg = HandoffDialog(win)
    qtbot.addWidget(dlg)
    snippet_row = next(b for b in dlg.rows
                       if b.text().startswith("matplotlib snippet"))
    snippet_row.click()
    assert QApplication.clipboard().text().startswith("# Generated")
    assert dlg.result() == 1  # palette closed itself


def test_file_menu_consolidated(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    texts = [a.text() for a in win.file_menu.actions() if a.text()]
    assert "Hand Off…" in texts
    assert not any(t.startswith("Copy") for t in texts)
    assert not any(t.startswith("Export") for t in texts)
    assert len(texts) <= 8


def test_sidebar_has_no_copy_buttons(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    for name in ("btn_copy_snippet", "btn_copy_placement", "btn_copy_card"):
        assert not hasattr(win.sidebar, name)
