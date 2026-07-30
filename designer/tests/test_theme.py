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
