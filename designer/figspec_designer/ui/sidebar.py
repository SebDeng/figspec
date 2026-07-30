"""Selected-panel inspector: label, mm / px / figsize, content hint."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QLineEdit, QVBoxLayout, QWidget
from figspec_designer.model.flatten import PanelRect, derive
from figspec_designer.ui.theme import smallcaps_font


class Sidebar(QWidget):
    content_hint_edited = Signal(str, str)  # (panel_id, text)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._panel_id: str | None = None
        self._last_hint: str | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        # Section header
        header = QLabel("Panel")
        header.setObjectName("sectionHeader")
        header.setFont(smallcaps_font())
        outer.addWidget(header)

        # Grid layout for fields
        grid = QGridLayout()
        grid.setSpacing(8)

        self.lbl_label = QLabel("—")
        self.lbl_mm = QLabel("—")
        self.lbl_px = QLabel("—")
        self.lbl_figsize = QLabel("—")

        for lbl in (self.lbl_label, self.lbl_mm, self.lbl_px, self.lbl_figsize):
            lbl.setObjectName("fieldValue")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        fields = [
            ("Label", self.lbl_label),
            ("Size (mm)", self.lbl_mm),
            ("Pixels", self.lbl_px),
            ("figsize (in)", self.lbl_figsize),
        ]

        for row, (label_text, value_widget) in enumerate(fields):
            left_label = QLabel(label_text)
            left_label.setObjectName("fieldLabel")
            grid.addWidget(left_label, row, 0)
            grid.addWidget(value_widget, row, 1)

        outer.addLayout(grid)

        # Hint edit
        self.hint_edit = QLineEdit()
        self.hint_edit.setPlaceholderText("content hint (e.g. STEM image + FFT inset)")
        outer.addWidget(self.hint_edit)

        # Stretch
        outer.addStretch(1)

        self.hint_edit.editingFinished.connect(self._emit_hint)
        self.hint_edit.setEnabled(False)

    def _emit_hint(self) -> None:
        if self._panel_id is not None:
            self.content_hint_edited.emit(self._panel_id, self.hint_edit.text())
            self._last_hint = self.hint_edit.text()

    def flush_pending(self) -> None:
        """Emit any typed-but-unconfirmed hint edit (no editingFinished yet).

        Safe to call unconditionally: no-ops when no panel is shown, or when
        the text hasn't actually changed since it was last shown/flushed.
        """
        if self._panel_id is None:
            return
        text = self.hint_edit.text()
        if text != self._last_hint:
            self.content_hint_edited.emit(self._panel_id, text)
            self._last_hint = text

    def show_panel(self, panel_id: str, label: str, rect: PanelRect,
                   dpi: int, content_hint: str) -> None:
        self._panel_id = panel_id
        w_px, h_px, figsize = derive(rect, dpi)
        self.lbl_label.setText(label)
        self.lbl_mm.setText(f"{rect.w_mm:.1f} × {rect.h_mm:.1f}")
        self.lbl_px.setText(f"{w_px} × {h_px} @ {dpi} dpi")
        self.lbl_figsize.setText(f"({figsize[0]:.3f}, {figsize[1]:.3f})")
        self.hint_edit.setEnabled(True)
        self.hint_edit.setText(content_hint)
        self._last_hint = content_hint

    def clear(self) -> None:
        self._panel_id = None
        self._last_hint = None
        for lbl in (self.lbl_label, self.lbl_mm, self.lbl_px, self.lbl_figsize):
            lbl.setText("—")
        self.hint_edit.clear()
        self.hint_edit.setEnabled(False)
