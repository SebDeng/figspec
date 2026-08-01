"""View > Calibrate Display… — drag until the on-screen bar matches a real
ruler (100 mm) or a credit card's long edge (85.60 mm). OS-reported physical
sizes are usually right on built-in panels and often wrong on external
monitors; the stored per-screen correction fixes actual-size mode."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QSlider,
                               QVBoxLayout, QWidget)

CARD_W_MM = 85.60  # ISO/IEC 7810 ID-1 long edge
CARD_H_MM = 53.98
_BAR_MM = 100.0


class _RulerWidget(QWidget):
    """100 mm bar + credit-card outline, painted at base_ppm × correction."""

    def __init__(self, base_ppm: float, parent=None):
        super().__init__(parent)
        self._base_ppm = base_ppm
        self._correction = 1.0
        self.setMinimumHeight(120)

    def set_correction(self, value: float) -> None:
        self._correction = value
        self.update()

    def bar_px(self) -> float:
        return _BAR_MM * self._base_ppm * self._correction

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ppm = self._base_ppm * self._correction
        x0, y0 = 12.0, 30.0
        pen = QPen(QColor("#3A3835"), 2.0)
        p.setPen(pen)
        p.drawLine(int(x0), int(y0), int(x0 + _BAR_MM * ppm), int(y0))
        for mm in (0, 50, 100):
            x = x0 + mm * ppm
            p.drawLine(int(x), int(y0 - 6), int(x), int(y0 + 6))
        p.drawText(int(x0), int(y0 - 12), "100 mm")
        card_y = y0 + 18
        p.setPen(QPen(QColor("#B9B6B0"), 1.5))
        p.drawRoundedRect(int(x0), int(card_y), int(CARD_W_MM * ppm),
                          int(min(CARD_H_MM * ppm, 60)), 8, 8)
        p.drawText(int(x0 + 6), int(card_y + 16), "credit card: 85.60 mm")
        p.end()


class CalibrateDialog(QDialog):
    def __init__(self, base_ppm: float, correction: float = 1.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibrate Display")
        self.ruler = _RulerWidget(base_ppm, self)

        hint = QLabel("Adjust until the bar matches a real ruler (100 mm) "
                      "or a credit card's long edge (85.60 mm).")
        hint.setWordWrap(True)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setObjectName("calibrateSlider")
        self.slider.setRange(850, 1150)  # ±15 %
        self.slider.setValue(round(correction * 1000))
        self.slider.valueChanged.connect(
            lambda v: self.ruler.set_correction(v / 1000.0))
        self.ruler.set_correction(self.slider.value() / 1000.0)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(hint)
        lay.addWidget(self.ruler, stretch=1)
        lay.addWidget(self.slider)
        lay.addWidget(buttons)

    def correction(self) -> float:
        return self.slider.value() / 1000.0
