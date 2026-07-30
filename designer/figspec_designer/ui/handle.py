"""Custom splitter whose handles ARE the gutters, with live mm feedback."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QSplitterHandle


class GutterHandle(QSplitterHandle):
    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        splitter = self.splitter()
        splitter.canvas.show_drag_feedback(splitter, self)

    def mouseReleaseEvent(self, event) -> None:
        alt = bool(event.modifiers() & Qt.AltModifier)
        super().mouseReleaseEvent(event)
        splitter = self.splitter()
        splitter.canvas.hide_drag_feedback()
        splitter.canvas.commit_splitter(splitter, alt_held=alt)


class GutterSplitter(QSplitter):
    def __init__(self, orientation_qt, path: tuple[int, ...], canvas):
        super().__init__(orientation_qt)
        self.path = path
        self.canvas = canvas
        self.setChildrenCollapsible(False)

    def createHandle(self) -> QSplitterHandle:
        return GutterHandle(self.orientation(), self)
