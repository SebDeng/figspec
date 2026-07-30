from PySide6.QtCore import Qt
from figspec_designer.ui.panel_widget import PanelWidget


def test_buttons_emit_actions():
    """Test that buttons emit correct actions when clicked."""
    w = PanelWidget("p1", "a")
    got = []
    w.action.connect(lambda act, pid: got.append((act, pid)))
    # Simulate hover to make buttons visible (workaround for offscreen platform)
    w.enterEvent(None)
    for name, expected in [("btn_split_right", "split_right"),
                           ("btn_split_down", "split_down"),
                           ("btn_close", "close")]:
        btn = w.findChild(object, name)
        btn.click()
        assert got[-1] == (expected, "p1")


def test_click_selects_and_label_updates():
    """Test that clicking panel emits select, and label/selected can be updated."""
    w = PanelWidget("p2", "a")
    got = []
    w.action.connect(lambda act, pid: got.append((act, pid)))
    w.mousePressEvent(None)
    assert ("select", "p2") in got
    w.set_label("c")
    assert w.label_widget.text() == "c"
    w.set_selected(True)
    assert w.property("selected") is True
