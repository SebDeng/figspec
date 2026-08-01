from PySide6.QtCore import Qt
from figspec_designer.ui.panel_widget import PanelWidget


def test_context_actions_cover_all_panel_verbs(qtbot):
    """Batch I: hover buttons retired; the context menu is the on-canvas
    action surface and must carry the plain splits it inherited."""
    w = PanelWidget("p1", "a")
    qtbot.addWidget(w)
    actions = dict(w.context_actions())
    for label, act in [("Split Right", "split_right"),
                       ("Split Down", "split_down"),
                       ("Delete Panel", "close"),
                       ("Export Panel Artboard…", "export_artboard")]:
        assert actions[label] == act
    assert not hasattr(w, "_actions")  # hover container is gone
    got = []
    w.action.connect(lambda act, pid: got.append((act, pid)))
    w.action.emit("split_right", w.panel_id)
    assert got == [("split_right", "p1")]


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
