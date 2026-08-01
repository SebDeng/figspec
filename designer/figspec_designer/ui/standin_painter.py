"""QPainter rendering of archetype stand-ins.

Honest by construction: every furniture/data value comes from
figspec.standins.roles (constraint floor for furniture, typical weight for
data strokes) and is drawn through the truescale helpers, so a stand-in is
a typographically true preview of what the panel's furniture will occupy.
Coordinates are mm × ppm; pictures are cached on the full input tuple.
The muted palette + corner mark keep stand-ins visibly fake (discipline 3).
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QImage, QPainter, QPainterPath,
                           QPicture, qRgb)

from figspec import standins
from figspec_designer.ui import truescale

_CACHE: dict[tuple, QPicture] = {}
_CACHE_CAP = 256

_INK = "#3A3835"
_MUTED = "#8B8880"
_FILL = "#D9D6D0"
_SERIES = ("#3A3835", "#8B8880", "#B4B1AA")


def standin_picture(archetype: str, w_mm: float, h_mm: float, ppm: float,
                    constraints, seed: str) -> QPicture:
    key = (archetype, round(w_mm, 1), round(h_mm, 1), round(ppm, 2),
           constraints.min_font_pt, constraints.max_font_pt,
           constraints.min_linewidth_pt, seed)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    if len(_CACHE) >= _CACHE_CAP:
        _CACHE.clear()
    pic = QPicture()
    p = QPainter(pic)
    try:
        _DRAWERS[archetype](p, w_mm, h_mm, ppm, constraints, seed)
        _mark(p, w_mm, h_mm, ppm)
    finally:
        p.end()
    _CACHE[key] = pic
    return pic


# ---- shared furniture ----------------------------------------------------

def _axes_rect(w_mm: float, h_mm: float, r: dict) -> QRectF:
    font_mm = r["furniture_font_pt"] * truescale.PT_TO_MM
    ml = min(9.0, max(3.0, 3.2 * font_mm))
    mb = min(8.0, max(2.5, 2.8 * font_mm))
    mt = min(2.5, max(0.6, 0.08 * h_mm))
    mr = min(2.5, max(0.6, 0.06 * w_mm))
    return QRectF(ml, mt, max(w_mm - ml - mr, 1.0), max(h_mm - mt - mb, 1.0))


def _axes(p: QPainter, ax: QRectF, h_mm: float, ppm: float, r: dict,
          x_ticks: int = 5, y_ticks: int = 4) -> None:
    lw, fpt = r["furniture_line_pt"], r["furniture_font_pt"]
    font_mm = fpt * truescale.PT_TO_MM
    for x1, y1, x2, y2 in ((ax.left(), ax.top(), ax.right(), ax.top()),
                           (ax.left(), ax.bottom(), ax.right(), ax.bottom()),
                           (ax.left(), ax.top(), ax.left(), ax.bottom()),
                           (ax.right(), ax.top(), ax.right(), ax.bottom())):
        truescale.draw_line_pt(p, x1, y1, x2, y2, lw, ppm, color=_INK)
    for i in range(x_ticks):
        x = ax.left() + ax.width() * i / (x_ticks - 1)
        truescale.draw_line_pt(p, x, ax.bottom(), x, ax.bottom() + 0.7, lw,
                               ppm, color=_INK)
        truescale.draw_text_pt(p, x - 0.7, ax.bottom() + 0.8 + font_mm,
                               str(i * 2), fpt, ppm, color=_MUTED)
    for j in range(y_ticks):
        y = ax.bottom() - ax.height() * j / (y_ticks - 1)
        truescale.draw_line_pt(p, ax.left() - 0.7, y, ax.left(), y, lw, ppm,
                               color=_INK)
        truescale.draw_text_pt(p, ax.left() - 0.7 - 1.9 * font_mm,
                               y + 0.45 * font_mm, str(j), fpt, ppm,
                               color=_MUTED)
    truescale.draw_text_pt(p, ax.center().x() - 2.5, h_mm - 0.8, "x (a.u.)",
                           fpt, ppm, color=_MUTED)


def _legend(p: QPainter, ax: QRectF, ppm: float, r: dict, n: int) -> None:
    fpt = r["furniture_font_pt"]
    font_mm = fpt * truescale.PT_TO_MM
    row_mm = 1.7 * font_mm
    box_w, box_h = 8.5 * font_mm, n * row_mm + 0.8
    if ax.width() < box_w * 1.6 or ax.height() < box_h * 2.2:
        return  # degrade by omission, like the wireframe's _fits
    x0 = ax.right() - box_w - 0.8
    y0 = ax.top() + 0.8
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    bg = QColor("#FFFFFF")
    bg.setAlphaF(0.85)
    p.fillRect(QRectF(x0 * ppm, y0 * ppm, box_w * ppm, box_h * ppm), bg)
    p.restore()
    for x1, y1, x2, y2 in ((x0, y0, x0 + box_w, y0),
                           (x0, y0 + box_h, x0 + box_w, y0 + box_h),
                           (x0, y0, x0, y0 + box_h),
                           (x0 + box_w, y0, x0 + box_w, y0 + box_h)):
        truescale.draw_line_pt(p, x1, y1, x2, y2, r["furniture_line_pt"],
                               ppm, color=_INK)
    for i in range(n):
        y = y0 + 0.5 + (i + 0.5) * row_mm
        truescale.draw_line_pt(p, x0 + 0.7, y, x0 + 0.7 + 2.2 * font_mm, y,
                               r["data_stroke_pt"], ppm,
                               color=_SERIES[i % len(_SERIES)])
        truescale.draw_text_pt(p, x0 + 1.1 + 2.2 * font_mm,
                               y + 0.4 * font_mm, f"series {chr(65 + i)}",
                               fpt, ppm, color=_INK)


def _mark(p: QPainter, w_mm: float, h_mm: float, ppm: float) -> None:
    """Fixed-px corner mark: UI chrome flagging the content as fake."""
    f = QFont()
    f.setPixelSize(8)
    c = QColor(_MUTED)
    c.setAlphaF(0.55)
    p.save()
    p.setFont(f)
    p.setPen(c)
    p.drawText(QPointF(w_mm * ppm - 38, h_mm * ppm - 3), "stand-in")
    p.restore()


def _poly(p: QPainter, pts_px: list[tuple[float, float]], width_pt: float,
          ppm: float, color: str) -> None:
    path = QPainterPath(QPointF(*pts_px[0]))
    for xy in pts_px[1:]:
        path.lineTo(QPointF(*xy))
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(truescale.line_pen_pt(width_pt, ppm, color))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.restore()


# ---- archetypes ----------------------------------------------------------

def _draw_line(p, w_mm, h_mm, ppm, constraints, seed):
    r = standins.roles(constraints)
    data = standins.pseudo_data("line", seed)
    ax = _axes_rect(w_mm, h_mm, r)
    _axes(p, ax, h_mm, ppm, r)
    for i, series in enumerate(data["series"]):
        n = len(series)
        pts = [((ax.left() + ax.width() * t / (n - 1)) * ppm,
                (ax.bottom() - ax.height() * v) * ppm)
               for t, v in enumerate(series)]
        _poly(p, pts, r["data_stroke_pt"], ppm, _SERIES[i % len(_SERIES)])
    _legend(p, ax, ppm, r, n=len(data["series"]))


def _draw_scatter(p, w_mm, h_mm, ppm, constraints, seed):
    r = standins.roles(constraints)
    data = standins.pseudo_data("scatter", seed)
    ax = _axes_rect(w_mm, h_mm, r)
    _axes(p, ax, h_mm, ppm, r)
    radius_px = 0.5 * truescale.pt_to_px(1.4, ppm)
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(_INK))
    for x, y in data["points"]:
        cx = (ax.left() + ax.width() * x) * ppm
        cy = (ax.bottom() - ax.height() * y) * ppm
        p.drawEllipse(QPointF(cx, cy), radius_px, radius_px)
    p.restore()
    slope, intercept = data["fit"]
    y0, y1 = intercept, min(intercept + slope, 1.0)
    _poly(p, [((ax.left()) * ppm, (ax.bottom() - ax.height() * y0) * ppm),
              ((ax.right()) * ppm, (ax.bottom() - ax.height() * y1) * ppm)],
          r["data_stroke_pt"], ppm, _MUTED)


def _draw_bar(p, w_mm, h_mm, ppm, constraints, seed):
    r = standins.roles(constraints)
    data = standins.pseudo_data("bar", seed)
    ax = _axes_rect(w_mm, h_mm, r)
    _axes(p, ax, h_mm, ppm, r, x_ticks=5)
    n_groups, n_bars = len(data["groups"]), len(data["groups"][0])
    slot = ax.width() / n_bars
    bar_w = slot / (n_groups + 1)
    fills = (_FILL, _MUTED)
    for g, (values, errors) in enumerate(zip(data["groups"], data["errors"])):
        for b, (v, e) in enumerate(zip(values, errors)):
            x = ax.left() + b * slot + (g + 0.5) * bar_w
            top = ax.bottom() - ax.height() * v
            rect = QRectF(x * ppm, top * ppm, bar_w * ppm,
                          (ax.bottom() - top) * ppm)
            p.fillRect(rect, QColor(fills[g % len(fills)]))
            for x1, y1, x2, y2 in (
                    (x, top, x + bar_w, top),
                    (x, top, x, ax.bottom()),
                    (x + bar_w, top, x + bar_w, ax.bottom())):
                truescale.draw_line_pt(p, x1, y1, x2, y2,
                                       r["furniture_line_pt"], ppm,
                                       color=_INK)
            cx = x + bar_w / 2
            e_mm = ax.height() * e
            truescale.draw_line_pt(p, cx, top - e_mm, cx, top + e_mm,
                                   r["data_stroke_pt"], ppm, color=_INK)
            truescale.draw_line_pt(p, cx - 0.6, top - e_mm, cx + 0.6,
                                   top - e_mm, r["data_stroke_pt"], ppm,
                                   color=_INK)


def _draw_heatmap(p, w_mm, h_mm, ppm, constraints, seed):
    r = standins.roles(constraints)
    data = standins.pseudo_data("heatmap", seed)
    plot, cbar = heatmap_layout(w_mm, h_mm, r)
    grid = data["grid"]
    rows, cols = len(grid), len(grid[0])
    for ri, row in enumerate(grid):
        for ci, v in enumerate(row):
            g = round(242 - 150 * v)
            cell = QRectF((plot.left() + plot.width() * ci / cols) * ppm,
                          (plot.top() + plot.height() * ri / rows) * ppm,
                          plot.width() / cols * ppm + 1,
                          plot.height() / rows * ppm + 1)
            p.fillRect(cell, QColor(g, g, g))
    for x1, y1, x2, y2 in ((plot.left(), plot.top(), plot.right(), plot.top()),
                           (plot.left(), plot.bottom(), plot.right(),
                            plot.bottom()),
                           (plot.left(), plot.top(), plot.left(),
                            plot.bottom()),
                           (plot.right(), plot.top(), plot.right(),
                            plot.bottom())):
        truescale.draw_line_pt(p, x1, y1, x2, y2, r["furniture_line_pt"],
                               ppm, color=_INK)
    steps = 24
    for i in range(steps):
        g = round(242 - 150 * (1 - i / (steps - 1)))
        band = QRectF(cbar.left() * ppm,
                      (cbar.top() + cbar.height() * i / steps) * ppm,
                      cbar.width() * ppm,
                      cbar.height() / steps * ppm + 1)
        p.fillRect(band, QColor(g, g, g))
    for x1, y1, x2, y2 in ((cbar.left(), cbar.top(), cbar.right(),
                            cbar.top()),
                           (cbar.left(), cbar.bottom(), cbar.right(),
                            cbar.bottom()),
                           (cbar.left(), cbar.top(), cbar.left(),
                            cbar.bottom()),
                           (cbar.right(), cbar.top(), cbar.right(),
                            cbar.bottom())):
        truescale.draw_line_pt(p, x1, y1, x2, y2, r["furniture_line_pt"],
                               ppm, color=_INK)
    fpt = r["furniture_font_pt"]
    font_mm = fpt * truescale.PT_TO_MM
    truescale.draw_text_pt(p, cbar.right() + 0.5,
                           cbar.top() + 0.45 * font_mm, "1", fpt, ppm,
                           color=_MUTED)
    truescale.draw_text_pt(p, cbar.right() + 0.5,
                           cbar.bottom() + 0.45 * font_mm, "0", fpt, ppm,
                           color=_MUTED)


def heatmap_layout(w_mm: float, h_mm: float, r: dict) -> tuple[QRectF, QRectF]:
    """(plot_rect, colorbar_rect) in mm. Public so tests can pin the
    colorbar's real estate without pixel archaeology."""
    font_mm = r["furniture_font_pt"] * truescale.PT_TO_MM
    ax = _axes_rect(w_mm, h_mm, r)
    cb_w = 3.0
    cb_gap = 1.0
    cb_label = 1.2 * font_mm + 0.6
    plot = QRectF(ax.left(), ax.top(),
                  max(ax.width() - cb_w - cb_gap - cb_label, 1.0),
                  ax.height())
    cbar = QRectF(plot.right() + cb_gap, ax.top(), cb_w, ax.height())
    return plot, cbar


def _draw_micrograph(p, w_mm, h_mm, ppm, constraints, seed):
    r = standins.roles(constraints)
    data = standins.pseudo_data("micrograph", seed)
    tile = data["tile"]
    side = len(tile)
    img = QImage(side, side, QImage.Format_RGB32)
    for y, row in enumerate(tile):
        for x, v in enumerate(row):
            g = round(35 + 165 * v)
            img.setPixel(x, y, qRgb(g, g, g))
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, w_mm * ppm, h_mm * ppm), img)
    p.restore()
    bar_len = min(10.0, 0.28 * w_mm)
    x1 = w_mm - bar_len - 2.0
    y = h_mm - 2.2
    truescale.draw_line_pt(p, x1, y, x1 + bar_len, y, 1.0, ppm,
                           color="#FFFFFF")
    truescale.draw_text_pt(p, x1, y - 0.9, "200 nm",
                           r["furniture_font_pt"], ppm, color="#FFFFFF")


_DRAWERS = {
    "line": _draw_line,
    "scatter": _draw_scatter,
    "bar": _draw_bar,
    "heatmap": _draw_heatmap,
    "micrograph": _draw_micrograph,
}
