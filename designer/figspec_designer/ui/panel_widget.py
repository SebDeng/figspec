"""A single panel on the canvas: big label, hover action buttons."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMenu,
                               QVBoxLayout, QWidget)
from figspec_designer.ui.theme import repolish

ASSET_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf"}


class PanelWidget(QFrame):
    action = Signal(str, str)  # (action, panel_id)
    asset_dropped = Signal(str, str)  # (panel_id, absolute file path)
    ASSET_EXTS = ASSET_EXTS

    def __init__(self, panel_id: str, label_text: str, parent: QWidget | None = None,
                *, aspect_violated: bool = False, thumb: "QPixmap | None" = None,
                asset_missing: bool = False, standin: str | None = None,
                standin_mm: tuple[float, float] | None = None,
                constraints=None):
        super().__init__(parent)
        self.panel_id = panel_id
        self._thumb = thumb
        self._standin = standin
        self._standin_mm = standin_mm
        self._constraints = constraints
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
        root.addLayout(bar)

        self.label_widget = QLabel(label_text, self)
        self.label_widget.setObjectName("panelLetter")
        self.label_widget.setAlignment(Qt.AlignCenter)
        if thumb is not None or self._has_standin():
            self.label_widget.setProperty("onImage", True)
        root.addWidget(self.label_widget, stretch=1)

    def _has_standin(self) -> bool:
        return (self._thumb is None and self._standin is not None
                and self._standin_mm is not None
                and self._constraints is not None)

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

    def mousePressEvent(self, event) -> None:
        self.action.emit("select", self.panel_id)
        super().mousePressEvent(event)

    # Hover buttons retired (batch I): the context menu is the panel's one
    # on-canvas action surface, alongside menubar shortcuts.
    def context_actions(self) -> list[tuple[str, str]]:
        return [("Split Right", "split_right"),
                ("Split Down", "split_down"),
                ("Split Right N…", "split_right_n"),
                ("Split Down N…", "split_down_n"),
                ("Equalize", "equalize"),
                ("Swap", "swap"),
                ("Export Panel Artboard…", "export_artboard"),
                ("Delete Panel", "close")]

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        for text, action in self.context_actions():
            menu.addAction(text,
                           lambda a=action: self.action.emit(a, self.panel_id))
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

    # 2px selected/swap-armed border + 1px breathing room -- scaling the
    # thumb to the FULL widget rect let it paint over that border whenever
    # the image's aspect matched the panel's (see paintEvent).
    _THUMB_INSET_PX = 3

    def paintEvent(self, event) -> None:
        super().paintEvent(event)  # QSS card background/border first
        if self._thumb is None or self._thumb.isNull():
            self._paint_standin()
            return
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QPainter
        inset = self._THUMB_INSET_PX
        target = self.size() - QSize(2 * inset, 2 * inset)
        scaled = self._thumb.scaled(target, Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation)
        painter = QPainter(self)
        painter.drawPixmap(inset + (target.width() - scaled.width()) // 2,
                           inset + (target.height() - scaled.height()) // 2, scaled)
        painter.end()

    def _paint_standin(self) -> None:
        if not self._has_standin():
            return
        avail_w = self.width() - 2 * self._THUMB_INSET_PX
        avail_h = self.height() - 2 * self._THUMB_INSET_PX
        w_mm, h_mm = self._standin_mm
        if avail_w < 12 or avail_h < 12 or w_mm <= 0 or h_mm <= 0:
            return
        from PySide6.QtGui import QPainter
        from figspec_designer.ui.standin_painter import standin_picture
        # The widget's own px/mm: the picture is generated at exactly this
        # scale, so replaying it needs no transform (and stays honest).
        ppm = min(avail_w / w_mm, avail_h / h_mm)
        pic = standin_picture(self._standin, w_mm, h_mm, ppm,
                              self._constraints, self.panel_id)
        painter = QPainter(self)
        painter.drawPicture(self._THUMB_INSET_PX, self._THUMB_INSET_PX, pic)
        painter.end()
