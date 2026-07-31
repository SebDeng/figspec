"""Tree -> absolute mm rectangles (top-left origin, y down) + labels."""
from __future__ import annotations
from dataclasses import dataclass
from figspec.layout.tree import Node, PanelNode


@dataclass(frozen=True)
class PanelRect:
    panel_id: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float


def flatten(root: Node, width_mm: float, height_mm: float,
            gutter_mm: float) -> list[PanelRect]:
    out: list[PanelRect] = []

    def rec(node: Node, x: float, y: float, w: float, h: float) -> None:
        if isinstance(node, PanelNode):
            out.append(PanelRect(node.id, round(x, 3), round(y, 3),
                                 round(w, 3), round(h, 3)))
            return
        n = len(node.children)
        if node.orientation == "row":
            avail = w - (n - 1) * gutter_mm
            cx = x
            for child, ratio in zip(node.children, node.ratios):
                cw = avail * ratio
                rec(child, cx, y, cw, h)
                cx += cw + gutter_mm
        else:
            avail = h - (n - 1) * gutter_mm
            cy = y
            for child, ratio in zip(node.children, node.ratios):
                ch = avail * ratio
                rec(child, x, cy, w, ch)
                cy += ch + gutter_mm

    rec(root, 0.0, 0.0, width_mm, height_mm)
    return out


def _label(i: int) -> str:
    s = ""
    while True:
        s = chr(ord("a") + i % 26) + s
        i = i // 26 - 1
        if i < 0:
            return s


def assign_labels(rects: list[PanelRect]) -> dict[str, str]:
    ordered = sorted(rects, key=lambda r: (round(r.y_mm, 1), r.x_mm))
    return {r.panel_id: _label(i) for i, r in enumerate(ordered)}


def derive(rect: PanelRect, dpi: int) -> tuple[int, int, tuple[float, float]]:
    w_px = round(rect.w_mm / 25.4 * dpi)
    h_px = round(rect.h_mm / 25.4 * dpi)
    return w_px, h_px, (round(rect.w_mm / 25.4, 3), round(rect.h_mm / 25.4, 3))
