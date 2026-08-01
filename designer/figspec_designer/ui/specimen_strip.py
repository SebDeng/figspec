"""Always-honest specimen strip under the canvas.

Everything specimen-shaped (the Aa glyphs, the line swatches, the 10 mm
bar, the effective-pt sample) is drawn through the SAME px_per_mm the
canvas uses, via the truescale helpers — so at any zoom the strip shows
what pt values really look like at that magnification, and the badge says
how far the view is from print size. Tiny grey captions are UI chrome, not
specimens, and use a fixed screen font.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from figspec_designer.ui import truescale

_LINE_SAMPLES_PT = (0.25, 0.5, 1.0)
_SCALEBAR_MM = 10.0
_ANCHOR_NOMINAL_PT = 8.0  # the plan's narrative anchor for the panel row
_CAPTION_PX = 9
_INK = "#3A3835"
_CAPTION_COLOR = "#6E6B66"


class _SpecimenArea(QWidget):
    def __init__(self, strip: "SpecimenStrip", parent=None):
        super().__init__(parent)
        self._strip = strip
        self.setMinimumHeight(56)

    def paintEvent(self, event) -> None:
        s = self._strip
        if s.ppm is None or s.constraints is None:
            return
        ppm = s.ppm
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        caption_font = QFont()
        caption_font.setPixelSize(_CAPTION_PX)
        baseline_mm = 26.0 / ppm  # first row's text baseline, in mm
        caption_y = 40
        x_mm = 8.0 / ppm

        def caption(x_px: float, text: str) -> float:
            p.setFont(caption_font)
            p.setPen(QColor(_CAPTION_COLOR))
            p.drawText(int(x_px), caption_y, text)
            return p.fontMetrics().horizontalAdvance(text)

        for pt in (s.constraints.min_font_pt, s.constraints.max_font_pt):
            w_mm = truescale.draw_text_pt(p, x_mm, baseline_mm, "Aa", pt, ppm,
                                          color=_INK)
            cap_w = caption(x_mm * ppm, f"{pt:.1f} pt")
            x_mm += max(w_mm, cap_w / ppm) + 6.0 / ppm

        for pt in _LINE_SAMPLES_PT:
            seg_mm = 24.0 / ppm
            truescale.draw_line_pt(p, x_mm, baseline_mm - 1.0 / ppm,
                                   x_mm + seg_mm, baseline_mm - 1.0 / ppm,
                                   pt, ppm, color=_INK)
            cap_w = caption(x_mm * ppm, f"{pt:g} pt")
            x_mm += max(seg_mm, cap_w / ppm) + 6.0 / ppm

        truescale.draw_line_pt(p, x_mm, baseline_mm, x_mm + _SCALEBAR_MM,
                               baseline_mm, 1.0, ppm, color=_INK)
        for end_mm in (x_mm, x_mm + _SCALEBAR_MM):
            truescale.draw_line_pt(p, end_mm, baseline_mm - 1.2,
                                   end_mm, baseline_mm + 1.2, 1.0, ppm,
                                   color=_INK)
        cap_w = caption(x_mm * ppm, "10 mm")
        x_mm += max(_SCALEBAR_MM, cap_w / ppm) + 8.0 / ppm

        if s.panel_k:
            eff = _ANCHOR_NOMINAL_PT * s.panel_k
            cap_w = caption(x_mm * ppm,
                            f"{_ANCHOR_NOMINAL_PT:g} pt → {eff:.2f} pt")
            x_mm += cap_w / ppm + 3.0 / ppm
            # the payload: that effective size, at true scale
            truescale.draw_text_pt(p, x_mm, baseline_mm, "Aa", eff, ppm,
                                   color=_INK)
        p.end()


class SpecimenStrip(QWidget):
    actual_size_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("specimenStrip")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.ppm: float | None = None
        self.actual_ppm: float | None = None
        self.constraints = None
        self.panel_k: float | None = None

        self.area = _SpecimenArea(self)
        self.badge = QLabel("")
        self.badge.setObjectName("zoomBadge")

        # One place for every zoom entry (View menu drives the same slots).
        self.btn_expand = QPushButton("▸")
        self.btn_expand.setObjectName("stripExpand")
        self.btn_expand.setToolTip("Show type and line specimens")
        self.btn_fit = QPushButton("Fit")
        self.btn_fit.setObjectName("zoomButton")
        self.btn_actual = QPushButton("1:1")
        self.btn_actual.setObjectName("zoomButton")
        self.btn_actual.setToolTip("Show at actual print size")
        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setObjectName("zoomButton")
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setObjectName("zoomButton")
        self.btn_actual.clicked.connect(self.actual_size_requested.emit)
        self.btn_expand.clicked.connect(
            lambda: self.set_expanded(not self._expanded))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.setSpacing(8)
        lay.addWidget(self.btn_expand)
        lay.addWidget(self.area, stretch=1)
        lay.addWidget(self.badge)
        for b in (self.btn_fit, self.btn_actual, self.btn_zoom_out,
                  self.btn_zoom_in):
            lay.addWidget(b)
        self._expanded = False
        self.set_expanded(False)

    # ---- state (pure, test-pinned) ----------------------------------
    def set_expanded(self, on: bool) -> None:
        """Collapsed by default: a slim badge line. Expanding reveals the
        full specimen strip — the truth is one click away, not 60 px of
        permanent chrome."""
        self._expanded = bool(on)
        self.area.setVisible(self._expanded)
        self.btn_expand.setText("▾" if self._expanded else "▸")
        self.setFixedHeight(60 if self._expanded else 26)

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_context(self, ppm: float, actual_ppm: float, constraints) -> None:
        self.ppm, self.actual_ppm, self.constraints = ppm, actual_ppm, constraints
        mm = truescale.PT_TO_MM * constraints.min_font_pt
        self.setToolTip(
            f"{constraints.min_font_pt:.1f} pt = {mm:.2f} mm · specimens are "
            "drawn at the canvas scale; the badge compares it to print size")
        self.badge.setText(self.badge_text())
        self.area.update()

    def set_panel_scale(self, k: float | None) -> None:
        self.panel_k = k
        self.area.update()

    def badge_text(self) -> str:
        if not self.ppm or not self.actual_ppm:
            return ""
        return f"{self.ppm / self.actual_ppm * 100:.0f}% of print size"

    def rows(self) -> list[str]:
        if self.constraints is None:
            return []
        out = [f"Aa {self.constraints.min_font_pt:.1f} pt",
               f"Aa {self.constraints.max_font_pt:.1f} pt"]
        out += [f"{w:g} pt" for w in _LINE_SAMPLES_PT]
        out.append(f"{_SCALEBAR_MM:g} mm")
        if self.panel_k:
            out.append(f"{_ANCHOR_NOMINAL_PT:g} pt → "
                       f"{_ANCHOR_NOMINAL_PT * self.panel_k:.2f} pt")
        return out
