"""Direction C ("minimal studio") theme: every color and style decision lives here."""
from __future__ import annotations
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

CHROME = "#FAF9F7"
CANVAS = "#F1EFEB"
HAIRLINE = "#EAE7E1"
DIVIDER = "#D8D5CF"
INK = "#1A1A18"
INK_SECONDARY = "#6B6862"
INK_MUTED = "#A09D96"
INK_HOVER = "#33332F"
PANEL_BG = "#FFFFFF"
LETTER = "#C6C3BC"

QSS = f"""
QMainWindow, QWidget#chrome {{ background: {CHROME}; }}
QMenuBar {{ background: {CHROME}; color: {INK}; }}
QStatusBar {{ background: {CHROME}; color: {INK_SECONDARY}; border-top: 1px solid {HAIRLINE}; }}

Canvas {{ background: {CANVAS}; }}
QWidget#page {{ background: transparent; border: none; }}

PanelWidget {{ background: {PANEL_BG}; border: 1px solid {HAIRLINE}; border-radius: 4px; }}
PanelWidget[selected="true"] {{ border: 2px solid {INK}; }}
QLabel#panelLetter {{ color: {LETTER}; font-size: 20px; font-weight: 600; background: transparent; border: none; }}

QWidget#panelActions {{ background: {PANEL_BG}; border: 1px solid {HAIRLINE}; border-radius: 6px; }}
QWidget#panelActions QToolButton {{ border: none; border-radius: 4px; padding: 2px 6px;
    color: {INK_SECONDARY}; background: transparent; font-size: 12px; }}
QWidget#panelActions QToolButton:hover {{ background: {CANVAS}; color: {INK}; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover, QSplitter::handle:pressed {{ background: {DIVIDER}; }}

QLabel#dragFeedback {{ background: {INK}; color: {CHROME}; padding: 3px 8px;
    border-radius: 6px; font-size: 11px; }}

QWidget#topbar {{ background: {CHROME}; border-bottom: 1px solid {HAIRLINE}; }}
QWidget#topbar QLabel {{ color: {INK_SECONDARY}; font-size: 12px; }}
QComboBox, QDoubleSpinBox, QSpinBox {{ background: {PANEL_BG}; border: 1px solid {HAIRLINE};
    border-radius: 6px; padding: 3px 8px; color: {INK}; }}
QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover {{ border-color: {DIVIDER}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QPushButton {{ background: {CHROME}; border: 1px solid {DIVIDER}; border-radius: 12px;
    padding: 4px 14px; color: {INK}; }}
QPushButton:hover {{ background: {CANVAS}; }}
QPushButton#primary {{ background: {INK}; color: {CHROME}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: {INK_HOVER}; }}

QWidget#sidebar {{ background: {CHROME}; border-left: 1px solid {HAIRLINE}; }}
QLabel#sectionHeader {{ color: {INK_MUTED}; font-size: 10px; font-weight: 600; }}
QLabel#fieldLabel {{ color: {INK_MUTED}; font-size: 12px; }}
QLabel#fieldValue {{ color: {INK}; font-size: 12px; font-weight: 600; }}
QLineEdit#hintEdit {{ background: transparent; border: none; border-bottom: 1px solid {DIVIDER};
    border-radius: 0; padding: 3px 0; color: {INK}; }}
QLineEdit#hintEdit:focus {{ border-bottom: 2px solid {INK}; }}
QLineEdit#hintEdit:disabled {{ border-bottom-color: {HAIRLINE}; color: {INK_MUTED}; }}
"""


def apply_theme(app) -> None:
    app.setStyleSheet(QSS)


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def smallcaps_font() -> QFont:
    f = QFont()
    f.setLetterSpacing(QFont.PercentageSpacing, 112)
    f.setCapitalization(QFont.AllUppercase)
    return f


def panel_shadow(widget: QWidget) -> QGraphicsDropShadowEffect:
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(12)
    eff.setOffset(0, 1)
    eff.setColor(QColor(26, 26, 24, 26))
    widget.setGraphicsEffect(eff)
    return eff
