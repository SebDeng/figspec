"""Clean wireframe rendering of a layout — deliberately NOT canvas.grab():
no selection borders, hover buttons, or armed-state cues in the output."""
from __future__ import annotations
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from figspec_designer.model.flatten import assign_labels, flatten, format_label

PX_PER_MM = 4.0
_PAGE = QColor("#FFFFFF")
_FRAME = QColor("#B9B6B0")
_TEXT = QColor("#6E6B66")
_LETTER = QColor("#3A3835")
_TEXT_MARGIN_MM = 0.6  # clearance kept between annotation text and the frame


def _fits(fm, text: str, rect: QRectF, margin_px: float) -> bool:
    """Whether `text`, measured with font metrics `fm`, fits inside `rect`
    with `margin_px` of clearance on every side.

    Used to skip the per-panel letter/mm-size annotations on narrow slivers
    instead of letting them bleed across the panel's own frame (or a
    neighbor's) — degrading by omission is correct for a wireframe."""
    return (fm.horizontalAdvance(text) + 2 * margin_px <= rect.width()
            and fm.height() + 2 * margin_px <= rect.height())


def render_layout_image(tree, target, *, scale: int = 2,
                        label_style: str = "lowercase",
                        with_standins: bool = False,
                        constraints=None) -> QImage:
    ppm = PX_PER_MM * scale
    w = round(target.figure_width_mm * ppm)
    h = round(target.figure_height_mm * ppm)
    footer = round(8 * ppm)
    img = QImage(w, h + footer, QImage.Format_RGB32)
    img.fill(_PAGE)
    rects = flatten(tree, target.figure_width_mm, target.figure_height_mm,
                    target.gutter_mm)
    labels = assign_labels(rects)

    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing)

    if with_standins and constraints is not None:
        from PySide6.QtCore import QPointF
        from figspec.layout.tree import iter_panels
        from figspec_designer.ui.canvas import Canvas
        from figspec_designer.ui.standin_painter import standin_picture
        nodes = {n.id: n for n in iter_panels(tree)}
        for r in rects:
            kind = Canvas._resolve_standin(nodes[r.panel_id])
            if kind is None:
                continue
            pic = standin_picture(kind, r.w_mm, r.h_mm, ppm, constraints,
                                  r.panel_id)
            painter.save()
            painter.translate(r.x_mm * ppm, r.y_mm * ppm)
            painter.drawPicture(QPointF(0, 0), pic)
            painter.restore()
    letter_font = QFont()
    letter_font.setBold(True)
    letter_font.setPixelSize(max(10, round(3.2 * ppm)))
    small_font = QFont()
    small_font.setPixelSize(max(8, round(2.2 * ppm)))

    margin_px = _TEXT_MARGIN_MM * ppm
    for r in rects:
        rect = QRectF(r.x_mm * ppm, r.y_mm * ppm, r.w_mm * ppm, r.h_mm * ppm)
        painter.setPen(QPen(_FRAME, max(1.0, 0.35 * scale)))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

        letter_text = format_label(labels[r.panel_id], label_style)
        painter.setFont(letter_font)
        if _fits(painter.fontMetrics(), letter_text, rect, margin_px):
            painter.setPen(_LETTER)
            painter.drawText(rect.adjusted(1.2 * ppm, 0.6 * ppm, 0, 0),
                             Qt.AlignLeft | Qt.AlignTop, letter_text)

        mm_text = f"{r.w_mm:.1f} × {r.h_mm:.1f} mm"
        painter.setFont(small_font)
        if _fits(painter.fontMetrics(), mm_text, rect, margin_px):
            painter.setPen(_TEXT)
            painter.drawText(rect, Qt.AlignCenter, mm_text)

    painter.setPen(_TEXT)
    painter.setFont(small_font)
    painter.drawText(QRectF(0, h, w, footer), Qt.AlignCenter,
                     f"{target.journal_preset} · "
                     f"{target.figure_width_mm:g} × {target.figure_height_mm:g} mm"
                     f" · {target.dpi} dpi · gutter {target.gutter_mm:g} mm")
    painter.end()
    return img


def render_layout_png(doc, path, scale: int = 2) -> bool:
    img = render_layout_image(doc.tree, doc.target, scale=scale,
                              label_style=doc.constraints.panel_label_style,
                              with_standins=True, constraints=doc.constraints)
    return img.save(str(path))
