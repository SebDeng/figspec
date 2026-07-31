"""A single panel on the canvas: big label, hover action buttons."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMenu, QToolButton,
                               QVBoxLayout, QWidget)
from figspec_designer.ui.theme import repolish

_BTN_SPECS = [("btn_split_right", "▸", "split_right", "Split right (Cmd+D)"),
              ("btn_split_down", "▾", "split_down", "Split down (Shift+Cmd+D)"),
              ("btn_close", "✕", "close", "Delete panel (Cmd+Backspace)")]

ASSET_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


class PanelWidget(QFrame):
    action = Signal(str, str)  # (action, panel_id)
    asset_dropped = Signal(str, str)  # (panel_id, absolute file path)
    ASSET_EXTS = ASSET_EXTS

    def __init__(self, panel_id: str, label_text: str, parent: QWidget | None = None,
                *, aspect_violated: bool = False, thumb: "QPixmap | None" = None,
                asset_missing: bool = False):
        super().__init__(parent)
        self.panel_id = panel_id
        self._thumb = thumb
        self.setObjectName("panel")
        self.setProperty("selected", False)
        self.setProperty("swapArmed", False)
        self.setProperty("assetMissing", bool(asset_missing))
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        bar = QHBoxLayout()

        self.aspect_badge = QLabel("aspect", self)
        self.aspect_badge.setObjectName("aspectBadge")
        self.aspect_badge.setVisible(aspect_violated)
        bar.addWidget(self.aspect_badge)

        self.missing_badge = QLabel("missing asset", self)
        self.missing_badge.setObjectName("missingBadge")
        self.missing_badge.setVisible(asset_missing)
        bar.addWidget(self.missing_badge)

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
        if thumb is not None:
            self.label_widget.setProperty("onImage", True)
        root.addWidget(self.label_widget, stretch=1)

    def set_label(self, text: str) -> None:
        self.label_widget.setText(text)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", bool(on))
        repolish(self)

    def set_swap_armed(self, on: bool) -> None:
        self.setProperty("swapArmed", bool(on))
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

    @staticmethod
    def _accepts_mime(mime) -> bool:
        if not mime.hasUrls():
            return False
        urls = mime.urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            return False
        from pathlib import Path
        return Path(urls[0].toLocalFile()).suffix.lower() in ASSET_EXTS

    def dragEnterEvent(self, event) -> None:
        if self._accepts_mime(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if self._accepts_mime(event.mimeData()):
            self.asset_dropped.emit(
                self.panel_id, event.mimeData().urls()[0].toLocalFile())
            event.acceptProposedAction()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)  # QSS card background/border first
        if self._thumb is None or self._thumb.isNull():
            return
        from PySide6.QtGui import QPainter
        scaled = self._thumb.scaled(self.size(), Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation)
        painter = QPainter(self)
        painter.drawPixmap((self.width() - scaled.width()) // 2,
                           (self.height() - scaled.height()) // 2, scaled)
        painter.end()
