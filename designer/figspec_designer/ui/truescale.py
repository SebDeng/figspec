"""True-scale painting helpers: fractional-pt text, honest hairlines, and
screen physical px/mm. The honesty disciplines live here exactly once,
shared by the specimen strip and the stand-in painter.

Disciplines enforced:
- Text goes through a painter-scale transform (draw big, scale down), so a
  pt size maps to a *fractional* pixel size. QFont.setPixelSize is int-only;
  rounding 5 pt up at small zooms would err ~15% in the dangerous direction
  (looking more readable than print).
- Line pens carry their exact fractional widthF and are drawn antialiased:
  a 0.25 pt line at fit zoom covers <1 px and must read as faint partial
  coverage, never be inflated to an opaque pixel.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QSettings
from PySide6.QtGui import QColor, QFont, QPainter, QPen

PT_TO_MM = 25.4 / 72.0
_BASE_FONT_PX = 64  # rendered size before the down-scale transform


def pt_to_px(pt: float, ppm: float) -> float:
    """Exact (float) pixel size of a pt length at ppm pixels-per-mm."""
    return pt * PT_TO_MM * ppm


def draw_text_pt(painter: QPainter, x_mm: float, y_mm: float, text: str,
                 size_pt: float, ppm: float, *, bold: bool = False,
                 color="#000000") -> float:
    """Draw `text` with an em size of exactly size_pt at this scale,
    baseline-left at (x_mm, y_mm). Returns the advance width in mm."""
    target_px = pt_to_px(size_pt, ppm)
    scale = target_px / _BASE_FONT_PX
    font = QFont()
    font.setPixelSize(_BASE_FONT_PX)
    font.setBold(bold)
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    painter.setPen(QColor(color))
    painter.translate(x_mm * ppm, y_mm * ppm)
    painter.scale(scale, scale)
    painter.setFont(font)
    painter.drawText(QPointF(0.0, 0.0), text)
    advance_px = painter.fontMetrics().horizontalAdvance(text) * scale
    painter.restore()
    return advance_px / ppm


def line_pen_pt(width_pt: float, ppm: float, color="#000000") -> QPen:
    """Pen whose stroke is exactly width_pt at this scale — widthF is never
    floored to a whole pixel. Draw it antialiased (draw_line_pt does) so
    sub-pixel widths render as partial coverage, the physical truth."""
    pen = QPen(QColor(color))
    pen.setWidthF(pt_to_px(width_pt, ppm))
    return pen


def draw_line_pt(painter: QPainter, x1_mm: float, y1_mm: float, x2_mm: float,
                 y2_mm: float, width_pt: float, ppm: float,
                 color="#000000") -> None:
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(line_pen_pt(width_pt, ppm, color))
    painter.drawLine(QPointF(x1_mm * ppm, y1_mm * ppm),
                     QPointF(x2_mm * ppm, y2_mm * ppm))
    painter.restore()


# ---- screen physical scale ----------------------------------------------

def screen_px_per_mm(screen, correction: float = 1.0) -> float:
    """Logical pixels per physical millimetre: geometry (logical px) over
    physicalSize (mm). Deliberately avoids physicalDotsPerInch, whose
    device-vs-logical pixel basis differs across platforms."""
    geo_w = screen.geometry().width()
    phys_w = screen.physicalSize().width()
    if geo_w <= 0 or phys_w <= 0:
        return 96.0 / 25.4  # last-ditch assumption: 96 dpi logical
    return geo_w / phys_w * correction


def _screen_key(screen) -> str:
    serial = ""
    if hasattr(screen, "serialNumber"):
        serial = screen.serialNumber() or ""
    return f"calibration/{serial or screen.name() or 'default'}"


def load_correction(screen, settings: QSettings | None = None) -> float:
    s = settings if settings is not None else QSettings("figspec", "designer")
    try:
        return float(s.value(_screen_key(screen), 1.0))
    except (TypeError, ValueError):
        return 1.0


def save_correction(screen, value: float,
                    settings: QSettings | None = None) -> None:
    s = settings if settings is not None else QSettings("figspec", "designer")
    s.setValue(_screen_key(screen), float(value))
