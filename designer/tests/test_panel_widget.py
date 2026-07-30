from PySide6.QtCore import Qt
from figspec_designer.ui.panel_widget import PanelWidget


def test_buttons_emit_actions(qtbot):
    w = PanelWidget("p1", "a")
    qtbot.addWidget(w)
    got = []
    w.action.connect(lambda act, pid: got.append((act, pid)))
    for name, expected in [("btn_split_right", "split_right"),
                           ("btn_split_down", "split_down"),
                           ("btn_close", "close")]:
        btn = w.findChild(object, name)
        qtbot.mouseClick(btn, Qt.LeftButton)
        assert got[-1] == (expected, "p1")


def test_click_selects_and_label_updates(qtbot):
    w = PanelWidget("p2", "a")
    qtbot.addWidget(w)
    got = []
    w.action.connect(lambda act, pid: got.append((act, pid)))
    qtbot.mouseClick(w, Qt.LeftButton)
    assert ("select", "p2") in got
    w.set_label("c")
    assert w.label_widget.text() == "c"
    w.set_selected(True)
    assert w.property("selected") is True
