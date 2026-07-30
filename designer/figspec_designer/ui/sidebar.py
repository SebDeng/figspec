"""Selected-panel inspector: label, mm / px / figsize, content hint."""
from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QWidget
from figspec_designer.model.flatten import PanelRect, derive


class Sidebar(QWidget):
    content_hint_edited = Signal(str, str)  # (panel_id, text)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._panel_id: str | None = None
        self._last_hint: str | None = None
        form = QFormLayout(self)
        self.lbl_label = QLabel("—")
        self.lbl_mm = QLabel("—")
        self.lbl_px = QLabel("—")
        self.lbl_figsize = QLabel("—")
        self.hint_edit = QLineEdit()
        self.hint_edit.setPlaceholderText("content hint (e.g. STEM image + FFT inset)")
        form.addRow("Panel", self.lbl_label)
        form.addRow("Size (mm)", self.lbl_mm)
        form.addRow("Pixels", self.lbl_px)
        form.addRow("figsize (in)", self.lbl_figsize)
        form.addRow("Hint", self.hint_edit)
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
