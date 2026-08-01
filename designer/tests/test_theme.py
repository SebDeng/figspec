from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QWidget
from figspec_designer.ui import theme
from figspec_designer.ui.main_window import MainWindow


def test_tokens_present_in_qss():
    for token in (theme.CHROME, theme.CANVAS, theme.INK, theme.DIVIDER):
        assert token in theme.QSS


def test_mainwindow_applies_theme(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    assert theme.CHROME in QApplication.instance().styleSheet()


def test_smallcaps_font():
    f = theme.smallcaps_font()
    assert f.capitalization() == QFont.AllUppercase
    assert f.letterSpacing() == 112.0


def test_panel_shadow_and_repolish(qtbot):
    w = QWidget()
    qtbot.addWidget(w)
    eff = theme.panel_shadow(w)
    assert w.graphicsEffect() is eff
    assert eff.blurRadius() == 12
    theme.repolish(w)  # must not raise


def test_panel_widget_theme_hooks(qtbot):
    from figspec_designer.ui.panel_widget import PanelWidget
    w = PanelWidget("p1", "a")
    qtbot.addWidget(w)
    assert w.findChild(QWidget, "panelActions") is not None
    assert w.label_widget.objectName() == "panelLetter"
    w.set_selected(True)
    assert w.property("selected") is True  # property survives repolish path


def test_canvas_theme_hooks(qtbot):
    from figspec_designer.document import DesignerDocument
    from figspec_designer.ui.canvas import Canvas
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(600, 400)
    canvas.set_document(DesignerDocument.default())
    page = canvas.findChild(QWidget, "page")
    assert page is not None
    for w in canvas.panel_widgets().values():
        assert w.graphicsEffect() is not None  # shadow attached


def test_sidebar_theme_hooks(qtbot):
    from figspec_designer.ui.sidebar import Sidebar
    sb = Sidebar()
    qtbot.addWidget(sb)
    assert sb.objectName() == "sidebar"
    header = sb.findChild(QWidget, "sectionHeader")
    assert header is not None
    assert sb.spin_w.objectName() == "fieldValue"
    assert sb.spin_h.objectName() == "fieldValue"
    assert sb.hint_edit.objectName() == "hintEdit"


def test_topbar_theme_hooks(qtbot):
    from figspec_designer.ui.toolbar import TopBar
    tb = TopBar()
    qtbot.addWidget(tb)
    assert tb.objectName() == "topbar"
    assert tb.btn_handoff.objectName() == "primary"
    assert tb.btn_document.objectName() == "docChip"


def test_asset_missing_border_yields_to_selection():
    # Regression: PanelWidget[assetMissing="true"] must be declared BEFORE
    # the selected/swapArmed rules -- equal-specificity QSS is
    # last-declared-wins, so if assetMissing came after selected, selecting
    # a missing-asset panel would silently drop the 2px ink selection
    # border (the missingBadge label still communicates the missing state
    # on a selected panel, so the border can safely yield to selection).
    missing_idx = theme.QSS.index('PanelWidget[assetMissing="true"]')
    selected_idx = theme.QSS.index('PanelWidget[selected="true"]')
    swap_armed_idx = theme.QSS.index('PanelWidget[swapArmed="true"]')
    assert missing_idx < selected_idx
    assert missing_idx < swap_armed_idx
