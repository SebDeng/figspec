"""Page settings + export actions."""
from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox, QWidget)
from figspec_designer import presets


class TopBar(QWidget):
    settings_changed = Signal()
    save_requested = Signal()
    copy_requested = Signal()
    open_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(presets.PRESETS) + ["custom"])
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
        self.btn_open = QPushButton("Open…")
        self.btn_save = QPushButton("Save JSON…")
        self.btn_copy = QPushButton("Copy JSON")

        for label, w in [("Preset", self.preset_combo), ("Width", self.width_spin),
                         ("Height", self.height_spin), ("DPI", self.dpi_spin),
                         ("Gutter", self.gutter_spin)]:
            lay.addWidget(QLabel(label))
            lay.addWidget(w)
        lay.addStretch(1)
        for b in (self.btn_open, self.btn_save, self.btn_copy):
            lay.addWidget(b)

        self.set_values("nature_double", presets.PRESETS["nature_double"],
                        presets.DEFAULT_HEIGHT_MM, presets.DEFAULT_DPI,
                        presets.DEFAULT_GUTTER_MM)

        self.preset_combo.currentTextChanged.connect(self._on_preset)
        for spin in (self.width_spin, self.height_spin, self.gutter_spin):
            spin.valueChanged.connect(lambda _=None: self.settings_changed.emit())
        self.dpi_spin.valueChanged.connect(lambda _=None: self.settings_changed.emit())
        self.btn_save.clicked.connect(self.save_requested.emit)
        self.btn_copy.clicked.connect(self.copy_requested.emit)
        self.btn_open.clicked.connect(self.open_requested.emit)

    def _on_preset(self, key: str) -> None:
        if key in presets.PRESETS:
            self.width_spin.blockSignals(True)
            self.width_spin.setValue(presets.PRESETS[key])
            self.width_spin.blockSignals(False)
            self.width_spin.setEnabled(False)
        else:
            self.width_spin.setEnabled(True)
        self.settings_changed.emit()

    def values(self) -> tuple[str, float, float, int, float]:
        return (self.preset_combo.currentText(), self.width_spin.value(),
                self.height_spin.value(), self.dpi_spin.value(),
                self.gutter_spin.value())

    def set_values(self, preset_key: str, width: float, height: float,
                   dpi: int, gutter: float) -> None:
        for w in (self.preset_combo, self.width_spin, self.height_spin,
                  self.dpi_spin, self.gutter_spin):
            w.blockSignals(True)
        self.preset_combo.setCurrentText(preset_key)
        self.width_spin.setValue(width)
        self.width_spin.setEnabled(preset_key not in presets.PRESETS)
        self.height_spin.setValue(height)
        self.dpi_spin.setValue(dpi)
        self.gutter_spin.setValue(gutter)
        for w in (self.preset_combo, self.width_spin, self.height_spin,
                  self.dpi_spin, self.gutter_spin):
            w.blockSignals(False)
