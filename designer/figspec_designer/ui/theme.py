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
AMBER_BG = "#F5A623"
AMBER_INK = "#3D2B00"
DPI_OK = "#3D7A44"
DPI_WARN = "#B07D2A"
DPI_BAD = "#B04A3A"

QSS = f"""
QMainWindow, QWidget#chrome {{ background: {CHROME}; }}
QMenuBar {{ background: {CHROME}; color: {INK}; }}
QStatusBar {{ background: {CHROME}; color: {INK_SECONDARY}; border-top: 1px solid {HAIRLINE}; }}

Canvas {{ background: {CANVAS}; }}
QWidget#page {{ background: transparent; border: none; }}

PanelWidget {{ background: {PANEL_BG}; border: 1px solid {HAIRLINE}; border-radius: 4px; }}
PanelWidget[assetMissing="true"] {{ border: 1px solid {AMBER_BG}; }}
PanelWidget[selected="true"] {{ border: 2px solid {INK}; }}
PanelWidget[swapArmed="true"] {{ border: 2px dashed {AMBER_BG}; }}
QLabel#panelLetter {{ color: {LETTER}; font-size: 20px; font-weight: 600; background: transparent; border: none; }}

QWidget#panelActions {{ background: {PANEL_BG}; border: 1px solid {HAIRLINE}; border-radius: 6px; }}
QWidget#panelActions QToolButton {{ border: none; border-radius: 4px; padding: 2px 6px;
    color: {INK_SECONDARY}; background: transparent; font-size: 12px; }}
QWidget#panelActions QToolButton:hover {{ background: {CANVAS}; color: {INK}; }}

QLabel#aspectBadge {{ background: {AMBER_BG}; color: {AMBER_INK}; font-size: 10px;
    font-weight: 700; padding: 1px 6px; border-radius: 8px; }}

QLabel#missingBadge {{
    background: {AMBER_BG}; color: {AMBER_INK}; border-radius: 4px;
    padding: 1px 6px; font-size: 10px;
}}
QLabel#panelLetter[onImage="true"] {{
    background: rgba(255, 255, 255, 0.75); border-radius: 6px;
}}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover, QSplitter::handle:pressed {{ background: {DIVIDER}; }}

QLabel#dragFeedback {{ background: {INK}; color: {CHROME}; padding: 3px 8px;
    border-radius: 6px; font-size: 11px; }}

QWidget#topbar {{ background: {CHROME}; border-bottom: 1px solid {HAIRLINE}; }}
QWidget#topbar QLabel {{ color: {INK_SECONDARY}; font-size: 12px; }}
QPushButton#docChip {{ background: {CANVAS}; border: 1px solid {HAIRLINE};
    border-radius: 12px; padding: 4px 12px; color: {INK_SECONDARY};
    font-size: 12px; }}
QPushButton#docChip:hover {{ border-color: {DIVIDER}; color: {INK}; }}
QWidget#docPopover {{ background: {PANEL_BG}; border: 1px solid {DIVIDER};
    border-radius: 8px; }}
QWidget#docPopover QLabel {{ color: {INK_MUTED}; font-size: 12px; }}
QComboBox, QDoubleSpinBox, QSpinBox {{ background: {PANEL_BG}; border: 1px solid {HAIRLINE};
    border-radius: 6px; padding: 3px 8px; color: {INK}; }}
QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover {{ border-color: {DIVIDER}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QDoubleSpinBox[overLimit="true"] {{
    color: {AMBER_INK}; border: 1px solid {AMBER_BG};
    background: #FBF3E2;
}}
QPushButton {{ background: {CHROME}; border: 1px solid {DIVIDER}; border-radius: 12px;
    padding: 4px 14px; color: {INK}; }}
QPushButton:hover {{ background: {CANVAS}; }}
QPushButton#primary {{ background: {INK}; color: {CHROME}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: {INK_HOVER}; }}

QWidget#sidebar {{ background: {CHROME}; border-left: 1px solid {HAIRLINE}; }}
QLabel#sectionHeader {{ color: {INK_MUTED}; font-size: 10px; font-weight: 600; }}
QLabel#fieldLabel {{ color: {INK_MUTED}; font-size: 12px; }}
#fieldValue {{ color: {INK}; font-size: 12px; font-weight: 600; }}
QLineEdit#hintEdit {{ background: transparent; border: none; border-bottom: 1px solid {DIVIDER};
    border-radius: 0; padding: 3px 0; color: {INK}; }}
QLineEdit#hintEdit:focus {{ border-bottom: 2px solid {INK}; }}
QLineEdit#hintEdit:disabled {{ border-bottom-color: {HAIRLINE}; color: {INK_MUTED}; }}

QLabel#dpiValue[level="ok"] {{ color: {DPI_OK}; font-weight: 600; }}
QLabel#dpiValue[level="warn"] {{ color: {DPI_WARN}; font-weight: 600; }}
QLabel#dpiValue[level="bad"] {{ color: {DPI_BAD}; font-weight: 600; }}

QPushButton#truthLine {{ background: {CANVAS}; border: 1px solid {HAIRLINE};
    border-radius: 8px; padding: 5px 10px; text-align: left;
    font-weight: 600; }}
QPushButton#truthLine:disabled {{ color: {INK_MUTED}; font-weight: 400; }}
QPushButton#truthLine[level="ok"] {{ color: {DPI_OK}; }}
QPushButton#truthLine[level="warn"] {{ color: {DPI_WARN}; }}
QPushButton#truthLine[level="bad"] {{ color: {DPI_BAD}; }}
QToolButton#detailsToggle {{ border: none; color: {INK_MUTED};
    font-size: 11px; padding: 2px 0; }}
QToolButton#detailsToggle:hover {{ color: {INK}; }}
QWidget#truthPopover {{ background: {PANEL_BG}; border: 1px solid {DIVIDER};
    border-radius: 8px; }}

QLabel#lintError {{ color: {DPI_BAD}; }}
QLabel#lintSummary {{ font-weight: 600; }}
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
