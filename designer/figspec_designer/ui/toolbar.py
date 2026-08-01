"""Slim top bar: Preset + W×H + a Document chip + one primary action.

The five set-once controls (DPI, gutter, and the three constraint fields)
keep their widget objects — and therefore the values()/set_values()
contract and every test that drives them programmatically — but live in a
popover behind the settings chip. Visible chrome drops from eleven
controls and three buttons to four controls and one button.
"""
from __future__ import annotations
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QGridLayout,
                               QHBoxLayout, QLabel, QPushButton, QSpinBox,
                               QWidget)
from figspec_designer import presets


class TopBar(QWidget):
    settings_changed = Signal()
    handoff_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(presets.PRESETS) + ["custom"])
        for i in range(self.preset_combo.count()):
            key = self.preset_combo.itemText(i)
            if key in presets.PRESET_SOURCES:
                self.preset_combo.setItemData(
                    i, presets.PRESET_SOURCES[key], Qt.ToolTipRole)
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(10.0, 1000.0)
        self.width_spin.setSuffix(" mm")
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(10.0, 1000.0)
        self.height_spin.setSuffix(" mm")
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 2400)
        self.gutter_spin = QDoubleSpinBox()
        self.gutter_spin.setRange(0.0, 50.0)
        self.gutter_spin.setSingleStep(0.5)
        self.gutter_spin.setSuffix(" mm")
        self.min_font_spin = QDoubleSpinBox()
        self.min_font_spin.setRange(1.0, 72.0)
        self.min_font_spin.setSingleStep(0.5)
        self.min_font_spin.setSuffix(" pt")
        self.max_font_spin = QDoubleSpinBox()
        self.max_font_spin.setRange(1.0, 72.0)
        self.max_font_spin.setSingleStep(0.5)
        self.max_font_spin.setSuffix(" pt")
        self.min_lw_spin = QDoubleSpinBox()
        self.min_lw_spin.setRange(0.05, 10.0)
        self.min_lw_spin.setSingleStep(0.05)
        self.min_lw_spin.setSuffix(" pt")

        # Document popover: set-once values, out of the permanent chrome.
        self.btn_document = QPushButton()
        self.btn_document.setObjectName("docChip")
        self.btn_document.setCursor(Qt.PointingHandCursor)
        self._popover = QWidget(self, Qt.Popup)
        self._popover.setObjectName("docPopover")
        self._popover.setAttribute(Qt.WA_StyledBackground, True)
        grid = QGridLayout(self._popover)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setSpacing(8)
        for row, (text, widget) in enumerate([
                ("Resolution", self.dpi_spin), ("Gutter", self.gutter_spin),
                ("Min font", self.min_font_spin),
                ("Max font", self.max_font_spin),
                ("Min line", self.min_lw_spin)]):
            grid.addWidget(QLabel(text), row, 0)
            grid.addWidget(widget, row, 1)

        self.btn_handoff = QPushButton("Hand Off…")
        self.btn_handoff.setObjectName("primary")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(8)
        preset_lbl = QLabel("Preset")
        lay.addWidget(preset_lbl)
        lay.addWidget(self.preset_combo)
        lay.addSpacing(8)
        lay.addWidget(self.width_spin)
        times = QLabel("×")
        lay.addWidget(times)
        lay.addWidget(self.height_spin)
        lay.addSpacing(8)
        lay.addWidget(self.btn_document)
        lay.addStretch(1)
        lay.addWidget(self.btn_handoff)

        _nd_constraints = presets.PRESET_CONSTRAINTS["nature_double"]
        self.set_values("nature_double", presets.PRESETS["nature_double"],
                        presets.DEFAULT_HEIGHT_MM, presets.DEFAULT_DPI,
                        presets.DEFAULT_GUTTER_MM,
                        _nd_constraints["min_font_pt"],
                        _nd_constraints["max_font_pt"],
                        _nd_constraints["min_linewidth_pt"])

        self.preset_combo.currentTextChanged.connect(self._on_preset)
        for spin in (self.width_spin, self.height_spin, self.gutter_spin,
                    self.min_font_spin, self.max_font_spin, self.min_lw_spin):
            spin.valueChanged.connect(lambda _=None: self.settings_changed.emit())
        self.dpi_spin.valueChanged.connect(lambda _=None: self.settings_changed.emit())
        self.settings_changed.connect(self._refresh_chip)
        self.btn_document.clicked.connect(self._show_popover)
        self.btn_handoff.clicked.connect(self.handoff_requested.emit)

    def _refresh_chip(self) -> None:
        self.btn_document.setText(
            f"{self.dpi_spin.value()} dpi · {self.gutter_spin.value():g} mm · "
            f"{self.min_font_spin.value():g}–{self.max_font_spin.value():g} pt"
            f" · ≥{self.min_lw_spin.value():g} pt")

    def _show_popover(self) -> None:
        self._popover.adjustSize()
        self._popover.move(self.btn_document.mapToGlobal(
            QPoint(0, self.btn_document.height() + 4)))
        self._popover.show()

    def _on_preset(self, key: str) -> None:
        if key in presets.PRESETS:
            spins = (self.width_spin, self.min_font_spin,
                     self.max_font_spin, self.min_lw_spin)
            for s in spins:
                s.blockSignals(True)
            self.width_spin.setValue(presets.PRESETS[key])
            c = presets.PRESET_CONSTRAINTS[key]
            self.min_font_spin.setValue(c["min_font_pt"])
            self.max_font_spin.setValue(c["max_font_pt"])
            self.min_lw_spin.setValue(c["min_linewidth_pt"])
            for s in spins:
                s.blockSignals(False)
            self.width_spin.setEnabled(False)
        else:
            self.width_spin.setEnabled(True)
        self.settings_changed.emit()

    def values(self) -> tuple[str, float, float, int, float, float, float, float]:
        return (self.preset_combo.currentText(), self.width_spin.value(),
                self.height_spin.value(), self.dpi_spin.value(),
                self.gutter_spin.value(), self.min_font_spin.value(),
                self.max_font_spin.value(), self.min_lw_spin.value())

    def set_values(self, preset_key: str, width: float, height: float,
                   dpi: int, gutter: float, min_font: float, max_font: float,
                   min_lw: float) -> None:
        widgets = (self.preset_combo, self.width_spin, self.height_spin,
                  self.dpi_spin, self.gutter_spin, self.min_font_spin,
                  self.max_font_spin, self.min_lw_spin)
        for w in widgets:
            w.blockSignals(True)
        self.preset_combo.setCurrentText(preset_key)
        self.width_spin.setValue(width)
        self.width_spin.setEnabled(preset_key not in presets.PRESETS)
        self.height_spin.setValue(height)
        self.dpi_spin.setValue(dpi)
        self.gutter_spin.setValue(gutter)
        self.min_font_spin.setValue(min_font)
        self.max_font_spin.setValue(max_font)
        self.min_lw_spin.setValue(min_lw)
        for w in widgets:
            w.blockSignals(False)
        self._refresh_chip()

    def set_height_over_limit(self, over: bool, tooltip: str = "") -> None:
        """Advisory amber styling on the height spinbox -- never blocks input."""
        from figspec_designer.ui.theme import repolish
        self.height_spin.setProperty("overLimit", bool(over))
        self.height_spin.setToolTip(tooltip if over else "")
        repolish(self.height_spin)
