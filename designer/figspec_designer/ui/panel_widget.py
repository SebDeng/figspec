"""A single panel on the canvas: big label, hover action buttons."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMenu, QToolButton,
                               QVBoxLayout, QWidget)
from figspec_designer.ui.theme import repolish

_BTN_SPECS = [("btn_split_right", "▸", "split_right", "Split right (Cmd+D)"),
              ("btn_split_down", "▾", "split_down", "Split down (Shift+Cmd+D)"),
              ("btn_close", "✕", "close", "Delete panel (Cmd+Backspace)")]


class PanelWidget(QFrame):
    action = Signal(str, str)  # (action, panel_id)

    def __init__(self, panel_id: str, label_text: str, parent: QWidget | None = None,
                *, aspect_violated: bool = False):
        super().__init__(parent)
        self.panel_id = panel_id
        self.setObjectName("panel")
        self.setProperty("selected", False)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        bar = QHBoxLayout()

        self.aspect_badge = QLabel("aspect", self)
        self.aspect_badge.setObjectName("aspectBadge")
        self.aspect_badge.setVisible(aspect_violated)
        bar.addWidget(self.aspect_badge)

        bar.addStretch(1)

        # Create panelActions container
        actions = QWidget(self)
        actions.setObjectName("panelActions")
        actions.setAttribute(Qt.WA_StyledBackground, True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(2, 2, 2, 2)
        actions_layout.setSpacing(0)

        self._buttons = []
        for name, glyph, act, tip in _BTN_SPECS:
            btn = QToolButton(actions)
            btn.setObjectName(name)
            btn.setText(glyph)
            btn.setToolTip(tip)
            btn.setAutoRaise(True)
            btn.clicked.connect(lambda _=False, a=act: self.action.emit(a, self.panel_id))
            actions_layout.addWidget(btn)
            self._buttons.append(btn)

        actions.setVisible(False)
        self._actions = actions
        bar.addWidget(actions)
        root.addLayout(bar)

        self.label_widget = QLabel(label_text, self)
        self.label_widget.setObjectName("panelLetter")
        self.label_widget.setAlignment(Qt.AlignCenter)
        root.addWidget(self.label_widget, stretch=1)

    def set_label(self, text: str) -> None:
        self.label_widget.setText(text)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", bool(on))
        repolish(self)

    def set_aspect_violation(self, violated: bool) -> None:
        self.aspect_badge.setVisible(violated)

    def enterEvent(self, event) -> None:
        self._actions.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._actions.setVisible(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.action.emit("select", self.panel_id)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.addAction("Split Right N…",
                       lambda: self.action.emit("split_right_n", self.panel_id))
        menu.addAction("Split Down N…",
                       lambda: self.action.emit("split_down_n", self.panel_id))
        menu.addAction("Equalize",
                       lambda: self.action.emit("equalize", self.panel_id))
        menu.addAction("Swap", lambda: self.action.emit("swap", self.panel_id))
        menu.exec(event.globalPos())
