"""A single panel on the canvas: big label, hover action buttons."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QToolButton,
                               QVBoxLayout, QWidget)

_BTN_SPECS = [("btn_split_right", "▸", "split_right", "Split right (Cmd+D)"),
              ("btn_split_down", "▾", "split_down", "Split down (Shift+Cmd+D)"),
              ("btn_close", "✕", "close", "Delete panel (Cmd+Backspace)")]


class PanelWidget(QFrame):
    action = Signal(str, str)  # (action, panel_id)

    def __init__(self, panel_id: str, label_text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.panel_id = panel_id
        self.setObjectName("panel")
        self.setProperty("selected", False)
        self._apply_style()

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        bar = QHBoxLayout()
        bar.addStretch(1)
        self._buttons = []
        for name, glyph, act, tip in _BTN_SPECS:
            btn = QToolButton(self)
            btn.setObjectName(name)
            btn.setText(glyph)
            btn.setToolTip(tip)
            btn.setAutoRaise(True)
            btn.clicked.connect(lambda _=False, a=act: self.action.emit(a, self.panel_id))
            btn.setVisible(False)
            bar.addWidget(btn)
            self._buttons.append(btn)
        root.addLayout(bar)

        self.label_widget = QLabel(label_text, self)
        self.label_widget.setAlignment(Qt.AlignCenter)
        self.label_widget.setStyleSheet("font-size: 24px; font-weight: bold; color: #555;")
        root.addWidget(self.label_widget, stretch=1)

    def _apply_style(self) -> None:
        selected = self.property("selected")
        border = "2px solid #0F62FE" if selected else "1px solid #b0b0b0"
        self.setStyleSheet(f"QFrame#panel {{ background: #fafafa; border: {border}; }}")

    def set_label(self, text: str) -> None:
        self.label_widget.setText(text)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", bool(on))
        self._apply_style()

    def enterEvent(self, event) -> None:
        for b in self._buttons:
            b.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        for b in self._buttons:
            b.setVisible(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.action.emit("select", self.panel_id)
        super().mousePressEvent(event)
