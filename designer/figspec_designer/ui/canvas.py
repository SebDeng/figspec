"""Renders the layout tree as nested GutterSplitters inside a page frame."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QWidget
from figspec_designer.document import DesignerDocument
from figspec_designer.model import ops
from figspec_designer.model.tree import Node, PanelNode
from figspec_designer.ui.handle import GutterSplitter
from figspec_designer.ui.panel_widget import PanelWidget

_MARGIN_PX = 24


class Canvas(QWidget):
    panel_action = Signal(str, str)      # (action, panel_id)
    ratios_committed = Signal(tuple, tuple)  # (path, ratios)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._doc: DesignerDocument | None = None
        self._page: QWidget | None = None
        self._panels: dict[str, PanelWidget] = {}
        self._splitters: dict[tuple[int, ...], GutterSplitter] = {}
        self.px_per_mm = 1.0
        self._feedback = QLabel(self)
        self._feedback.setStyleSheet(
            "background: #333; color: white; padding: 2px 6px; border-radius: 3px;")
        self._feedback.hide()

    # ---- public API -------------------------------------------------
    def panel_widgets(self) -> dict[str, PanelWidget]:
        return dict(self._panels)

    def splitters(self) -> dict[tuple[int, ...], GutterSplitter]:
        return dict(self._splitters)

    def set_document(self, doc: DesignerDocument) -> None:
        self._doc = doc
        self._rebuild()

    def apply_selection(self, panel_id: str | None) -> None:
        for pid, w in self._panels.items():
            w.set_selected(pid == panel_id)

    # ---- geometry ---------------------------------------------------
    def _fit_scale(self) -> float:
        t = self._doc.target
        avail_w = max(self.width() - 2 * _MARGIN_PX, 50)
        avail_h = max(self.height() - 2 * _MARGIN_PX, 50)
        return max(min(avail_w / t.figure_width_mm, avail_h / t.figure_height_mm), 0.1)

    def mm_sizes(self, splitter: GutterSplitter) -> list[float]:
        return [s / self.px_per_mm for s in splitter.sizes()]

    # ---- build ------------------------------------------------------
    def _rebuild(self) -> None:
        if self._page is not None:
            self._page.deleteLater()
        self._panels.clear()
        self._splitters.clear()
        if self._doc is None:
            return
        t = self._doc.target
        self.px_per_mm = self._fit_scale()
        labels = self._doc.labels()
        self._page = QWidget(self)
        self._page.setStyleSheet("background: white; border: 1px solid #888;")
        page_w = round(t.figure_width_mm * self.px_per_mm)
        page_h = round(t.figure_height_mm * self.px_per_mm)
        self._page.setGeometry((self.width() - page_w) // 2,
                               (self.height() - page_h) // 2, page_w, page_h)
        content = self._build_node(self._doc.tree, (), labels)
        content.setParent(self._page)
        content.setGeometry(0, 0, page_w, page_h)
        self._page.show()
        content.show()
        self._feedback.raise_()

    def _build_node(self, node: Node, path: tuple[int, ...],
                    labels: dict[str, str]) -> QWidget:
        if isinstance(node, PanelNode):
            w = PanelWidget(node.id, labels.get(node.id, "?"))
            w.action.connect(self.panel_action.emit)
            self._panels[node.id] = w
            return w
        qt_orient = Qt.Horizontal if node.orientation == "row" else Qt.Vertical
        splitter = GutterSplitter(qt_orient, path, self)
        gutter_px = max(round(self._doc.target.gutter_mm * self.px_per_mm), 1)
        splitter.setHandleWidth(gutter_px)
        for i, child in enumerate(node.children):
            splitter.addWidget(self._build_node(child, path + (i,), labels))
        total_px = round((self._axis_mm(node, path) -
                          (len(node.children) - 1) * self._doc.target.gutter_mm)
                         * self.px_per_mm)
        splitter.setSizes([max(round(r * total_px), 1) for r in node.ratios])
        self._splitters[path] = splitter
        return splitter

    def _axis_mm(self, node: Node, path: tuple[int, ...]) -> float:
        """Length in mm of this splitter's axis, derived from the flattened rects."""
        rects = {r.panel_id: r for r in self._doc.panel_rects()}
        first = next(iter(self._iter_node_panels(node)))
        last_rects = [rects[p.id] for p in self._iter_node_panels(node)]
        if node.orientation == "row":
            x0 = min(r.x_mm for r in last_rects)
            x1 = max(r.x_mm + r.w_mm for r in last_rects)
            return x1 - x0
        y0 = min(r.y_mm for r in last_rects)
        y1 = max(r.y_mm + r.h_mm for r in last_rects)
        return y1 - y0

    @staticmethod
    def _iter_node_panels(node: Node):
        from figspec_designer.model.tree import iter_panels
        return iter_panels(node)

    # ---- drag feedback + commit ------------------------------------
    def show_drag_feedback(self, splitter: GutterSplitter, handle) -> None:
        sizes = self.mm_sizes(splitter)
        idx = max(splitter.indexOf(handle) - 1, 0)
        left = sizes[idx]
        right = sizes[idx + 1] if idx + 1 < len(sizes) else 0.0
        self._feedback.setText(f"{left:.1f} mm | {right:.1f} mm")
        self._feedback.adjustSize()
        pos = handle.mapTo(self, handle.rect().center())
        self._feedback.move(pos.x() + 8, pos.y() - 24)
        self._feedback.show()
        self._feedback.raise_()

    def hide_drag_feedback(self) -> None:
        self._feedback.hide()

    def commit_splitter(self, splitter: GutterSplitter, alt_held: bool) -> None:
        sizes_px = splitter.sizes()
        total = sum(sizes_px)
        if total <= 0:
            return
        ratios = tuple(s / total for s in sizes_px)
        if not alt_held:
            node = ops.node_at(self._doc.tree, splitter.path)
            avail_mm = (self._axis_mm(node, splitter.path)
                        - (len(sizes_px) - 1) * self._doc.target.gutter_mm)
            ratios = ops.snap_ratios(ratios, avail_mm)
        self.ratios_committed.emit(splitter.path, ratios)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._doc is not None:
            self._rebuild()
