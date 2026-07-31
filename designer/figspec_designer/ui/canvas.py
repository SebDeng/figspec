"""Renders the layout tree as nested GutterSplitters inside a page frame."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget
from figspec_designer.document import DesignerDocument
from figspec_designer.model import ops
from figspec_designer.model.tree import Node, PanelNode
from figspec_designer.ui.handle import GutterSplitter
from figspec_designer.ui.panel_widget import PanelWidget
from figspec_designer.ui.theme import panel_shadow

_MARGIN_PX = 24


class Canvas(QWidget):
    # panel_id is `object`, not `str` -- a str-typed Qt signal coerces a
    # Python None argument to "" during marshaling, which would silently
    # turn our blank-canvas-click "select nothing" (None) into a bogus
    # empty-string panel id instead. `object` passes None through as-is.
    panel_action = Signal(str, object)      # (action, panel_id | None)
    ratios_committed = Signal(tuple, tuple)  # (path, ratios)
    asset_dropped = Signal(str, str)         # (panel_id, absolute file path)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._doc: DesignerDocument | None = None
        self._page: QWidget | None = None
        self._panels: dict[str, PanelWidget] = {}
        self._splitters: dict[tuple[int, ...], GutterSplitter] = {}
        self._selected_id: str | None = None
        self._swap_armed_id: str | None = None
        self._asset_base = None
        self.px_per_mm = 1.0
        self._feedback = QLabel(self)
        self._feedback.setObjectName("dragFeedback")
        self._feedback.hide()

    # ---- public API -------------------------------------------------
    def panel_widgets(self) -> dict[str, PanelWidget]:
        return dict(self._panels)

    def splitters(self) -> dict[tuple[int, ...], GutterSplitter]:
        return dict(self._splitters)

    def set_document(self, doc: DesignerDocument, base_dir=None) -> None:
        self._doc = doc
        self._asset_base = base_dir
        self._rebuild()

    def apply_selection(self, panel_id: str | None) -> None:
        self._selected_id = panel_id
        for pid, w in self._panels.items():
            w.set_selected(pid == panel_id)

    def apply_swap_armed(self, panel_id: str | None) -> None:
        """Mirrors apply_selection: visually marks the panel currently
        armed for swap (MainWindow._swap_pending), or clears the cue when
        panel_id is None."""
        self._swap_armed_id = panel_id
        for pid, w in self._panels.items():
            w.set_swap_armed(pid == panel_id)

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
        self._page.setObjectName("page")
        self._page.setAttribute(Qt.WA_StyledBackground, True)
        page_w = round(t.figure_width_mm * self.px_per_mm)
        page_h = round(t.figure_height_mm * self.px_per_mm)
        self._page.setGeometry((self.width() - page_w) // 2,
                               (self.height() - page_h) // 2, page_w, page_h)
        rects = {r.panel_id: r for r in self._doc.panel_rects()}
        content = self._build_node(self._doc.tree, (), labels, rects)
        content.setParent(self._page)
        content.setGeometry(0, 0, page_w, page_h)
        self._page.show()
        content.show()
        # _rebuild() recreates fresh, unselected PanelWidgets -- reapply the
        # prior selection (apply_selection() also re-sets self._selected_id,
        # which is a no-op here since it's already the current value).
        self.apply_selection(self._selected_id)
        self.apply_swap_armed(self._swap_armed_id)
        self._feedback.raise_()

    def _build_node(self, node: Node, path: tuple[int, ...],
                    labels: dict[str, str], rects: dict) -> QWidget:
        if isinstance(node, PanelNode):
            violated = self._aspect_violated(node, rects)
            thumb, missing = self._load_thumb(node)
            w = PanelWidget(node.id, labels.get(node.id, "?"),
                            aspect_violated=violated,
                            thumb=thumb, asset_missing=missing)
            w.action.connect(self.panel_action.emit)
            w.asset_dropped.connect(self.asset_dropped.emit)
            panel_shadow(w)
            self._panels[node.id] = w
            return w
        qt_orient = Qt.Horizontal if node.orientation == "row" else Qt.Vertical
        splitter = GutterSplitter(qt_orient, path, self)
        gutter_px = max(round(self._doc.target.gutter_mm * self.px_per_mm), 1)
        splitter.setHandleWidth(gutter_px)
        for i, child in enumerate(node.children):
            splitter.addWidget(self._build_node(child, path + (i,), labels, rects))
        total_px = round((self._axis_mm(node, path) -
                          (len(node.children) - 1) * self._doc.target.gutter_mm)
                         * self.px_per_mm)
        splitter.setSizes([max(round(r * total_px), 1) for r in node.ratios])
        self._splitters[path] = splitter
        return splitter

    @staticmethod
    def _aspect_violated(node: PanelNode, rects: dict) -> bool:
        """True when node has an aspect_lock and its current rect's w/h ratio
        deviates from that lock by more than 2%."""
        if node.aspect_lock is None:
            return False
        rect = rects.get(node.id)
        if rect is None or rect.h_mm <= 0:
            return False
        current = rect.w_mm / rect.h_mm
        return abs(current - node.aspect_lock) / node.aspect_lock > 0.02

    _THUMB_MAX = 1200  # px cap: canvas preview never needs full-res assets

    def _load_thumb(self, node: PanelNode):
        """(QPixmap|None, missing: bool) for a panel's asset, if any."""
        if node.asset is None:
            return None, False
        from figspec.document import resolve_asset
        path = resolve_asset(node.asset, self._asset_base)
        if path is None:
            return None, True
        pix = QPixmap(str(path))
        if pix.isNull():
            return None, True
        if pix.width() > self._THUMB_MAX:
            pix = pix.scaledToWidth(self._THUMB_MAX, Qt.SmoothTransformation)
        return pix, False

    def _axis_mm(self, node: Node, path: tuple[int, ...]) -> float:
        """Length in mm of this splitter's axis, derived from the flattened rects."""
        rects = {r.panel_id: r for r in self._doc.panel_rects()}
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
        node = ops.node_at(self._doc.tree, splitter.path)
        avail_mm = (self._axis_mm(node, splitter.path)
                    - (len(sizes_px) - 1) * self._doc.target.gutter_mm)
        if not alt_held:
            ratios = ops.snap_ratios(ratios, avail_mm)
        # Clamp AFTER snapping (not before), then renormalize. snap_ratios'
        # own 0.5mm rounding of the *other* child's remainder can itself
        # push an already-near-floor child back under MIN_PANEL_MM even
        # when the pre-snap ratios were clamp-clean -- e.g. avail 50.3mm,
        # drag to [45.3, 5.0] snaps to [45.5, 4.8]. Clamping post-snap is
        # the only ordering that actually holds the floor; it also still
        # runs when Alt bypasses snapping, so a free drag can't produce a
        # <5mm panel either.
        ratios = self._clamp_min_mm(ratios, avail_mm)
        self.ratios_committed.emit(splitter.path, ratios)

    @staticmethod
    def _clamp_min_mm(ratios: tuple[float, ...], avail_mm: float) -> tuple[float, ...]:
        """Raise any child below ops.MIN_PANEL_MM up to exactly that size,
        shrinking the others proportionally to absorb the difference, then
        renormalize back to ratio-space. Runs as a small fixed-point loop
        (bounded by len(ratios) iterations) since locking one child down to
        the minimum can push an already-fine sibling below it in turn."""
        n = len(ratios)
        if avail_mm <= 0 or n * ops.MIN_PANEL_MM > avail_mm + 1e-9:
            return ratios  # not enough room to honor the minimum for every child
        sizes = [r * avail_mm for r in ratios]
        locked = [False] * n
        for _ in range(n):
            below = [i for i in range(n)
                     if not locked[i] and sizes[i] < ops.MIN_PANEL_MM - 1e-9]
            if not below:
                break
            for i in below:
                sizes[i] = ops.MIN_PANEL_MM
                locked[i] = True
            free = [i for i in range(n) if not locked[i]]
            if not free:
                break
            free_total = sum(sizes[i] for i in free)
            target = avail_mm - ops.MIN_PANEL_MM * sum(locked)
            if free_total > 0:
                scale = target / free_total
                for i in free:
                    sizes[i] *= scale
        total = sum(sizes)
        if total <= 0:
            return ratios
        return tuple(s / total for s in sizes)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._doc is not None:
            self._rebuild()

    def mousePressEvent(self, event) -> None:
        # Reaches here only for a click that landed on the canvas itself --
        # i.e. blank space outside any PanelWidget/splitter (those consume
        # the event first). Forward as "select nothing": MainWindow treats
        # it like clicking empty space -- deselects, and (spec A5) cancels
        # an in-progress swap.
        self.panel_action.emit("select", None)
        super().mousePressEvent(event)
