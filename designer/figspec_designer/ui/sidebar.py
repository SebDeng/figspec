"""Selected-panel inspector: label, position, size, aspect, content hint."""
from __future__ import annotations
import math
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout, QWidget)
from figspec_designer.model.flatten import PanelRect, derive
from figspec_designer.ui.theme import smallcaps_font


def _aspect_text(w_mm: float, h_mm: float) -> str:
    """"N:M · 1.554:1" when the reduced integer ratio (at 0.1mm precision)
    has both terms <= 60 (spec A2: 约分显示 + 小数); otherwise just the
    decimal form, since a reduced fraction with a large numerator/
    denominator isn't a meaningful "nice ratio" to show."""
    ratio = w_mm / h_mm if h_mm else 0.0
    decimal = f"{ratio:.3f}:1"
    w10, h10 = round(w_mm * 10), round(h_mm * 10)
    if w10 <= 0 or h10 <= 0:
        return decimal
    g = math.gcd(w10, h10)
    n, m = w10 // g, h10 // g
    if n <= 60 and m <= 60:
        return f"{n}:{m} · {decimal}"
    return decimal


class Sidebar(QWidget):
    content_hint_edited = Signal(str, str)  # (panel_id, text)
    size_edited = Signal(str, str, float)  # (panel_id, axis, mm)
    square_requested = Signal(str)  # (panel_id)
    aspect_lock_toggled = Signal(str, object)  # (panel_id, float|None)
    placement_copy_requested = Signal()
    snippet_copy_requested = Signal()
    card_copy_requested = Signal()
    asset_remove_requested = Signal(str)  # (panel_id)
    asset_dpi_edited = Signal(str, object)  # (panel_id, float|None)
    standin_changed = Signal(str, object)  # (panel_id, archetype|"none"|None)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._panel_id: str | None = None
        self._last_hint: str | None = None
        self._shown_w: float | None = None
        self._shown_h: float | None = None
        self._k: float | None = None  # current placement scale (asset panels)
        self._last_dpi_text: str | None = None
        self._calc_guard = False

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
        self.lbl_xy = QLabel("—")
        self.lbl_aspect = QLabel("—")
        self.lbl_px = QLabel("—")
        self.lbl_figsize = QLabel("—")

        for lbl in (self.lbl_label, self.lbl_xy, self.lbl_aspect,
                   self.lbl_px, self.lbl_figsize):
            lbl.setObjectName("fieldValue")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.spin_w = QDoubleSpinBox()
        self.spin_h = QDoubleSpinBox()
        for spin in (self.spin_w, self.spin_h):
            spin.setObjectName("fieldValue")
            spin.setDecimals(1)
            spin.setRange(5.0, 600.0)
            spin.setSuffix(" mm")
            spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        size_row = QWidget()
        size_row_layout = QHBoxLayout(size_row)
        size_row_layout.setContentsMargins(0, 0, 0, 0)
        size_row_layout.setSpacing(4)
        size_row_layout.addWidget(self.spin_w)
        times_lbl = QLabel("×")
        times_lbl.setObjectName("fieldLabel")
        size_row_layout.addWidget(times_lbl)
        size_row_layout.addWidget(self.spin_h)

        fields = [
            ("Label", self.lbl_label),
            ("Position", self.lbl_xy),
            ("Size (mm)", size_row),
            ("Aspect", self.lbl_aspect),
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
        self.hint_edit.setObjectName("hintEdit")
        self.hint_edit.setPlaceholderText("content hint (e.g. STEM image + FFT inset)")
        outer.addWidget(self.hint_edit)

        # Stand-in archetype: Auto (infer from hint) / explicit / None
        standin_row = QWidget()
        standin_layout = QHBoxLayout(standin_row)
        standin_layout.setContentsMargins(0, 0, 0, 0)
        standin_layout.setSpacing(4)
        standin_lbl = QLabel("Stand-in")
        standin_lbl.setObjectName("fieldLabel")
        self.standin_combo = QComboBox()
        self.standin_combo.setObjectName("standinCombo")
        for text, value in (("Auto", None), ("Line", "line"),
                            ("Scatter", "scatter"), ("Bar", "bar"),
                            ("Heatmap", "heatmap"),
                            ("Micrograph", "micrograph"), ("None", "none")):
            self.standin_combo.addItem(text, value)
        standin_layout.addWidget(standin_lbl)
        standin_layout.addWidget(self.standin_combo, stretch=1)
        outer.addWidget(standin_row)

        # Aspect lock + geometry tools
        self.chk_aspect_lock = QCheckBox("Lock aspect ratio")
        self.chk_aspect_lock.setObjectName("aspectLockCheck")
        outer.addWidget(self.chk_aspect_lock)

        self.btn_square = QPushButton("Make Square")
        self.btn_square.setObjectName("squareButton")
        outer.addWidget(self.btn_square)

        self.btn_copy_placement = QPushButton("Copy Placement Table")
        self.btn_copy_placement.setObjectName("copyPlacementButton")
        outer.addWidget(self.btn_copy_placement)

        self.btn_copy_snippet = QPushButton("Copy matplotlib Snippet")
        self.btn_copy_snippet.setObjectName("copySnippetButton")
        outer.addWidget(self.btn_copy_snippet)

        self.btn_copy_card = QPushButton("Copy Authoring Card")
        self.btn_copy_card.setObjectName("copyCardButton")
        outer.addWidget(self.btn_copy_card)

        # ---- external asset block (hidden unless the panel has one) ----
        self.asset_box = QWidget()
        self.asset_box.setObjectName("assetBox")
        asset_layout = QVBoxLayout(self.asset_box)
        asset_layout.setContentsMargins(0, 8, 0, 0)
        asset_layout.setSpacing(6)
        asset_header = QLabel("Asset")
        asset_header.setObjectName("sectionHeader")
        asset_header.setFont(smallcaps_font())
        asset_layout.addWidget(asset_header)
        asset_grid = QGridLayout()
        asset_grid.setSpacing(8)
        self.lbl_asset_name = QLabel("—")
        self.lbl_asset_px = QLabel("—")
        self.lbl_asset_name.setObjectName("fieldValue")
        self.lbl_asset_px.setObjectName("fieldValue")
        self.lbl_asset_dpi = QLabel("—")
        self.lbl_asset_dpi.setObjectName("dpiValue")

        # Source-DPI declaration: editable number + provenance note. The
        # declared dpi is the bridge that gives a pixel canvas a physical
        # size -- everything below (×k, calculator, card) derives from it.
        dpi_row = QWidget()
        dpi_row_layout = QHBoxLayout(dpi_row)
        dpi_row_layout.setContentsMargins(0, 0, 0, 0)
        dpi_row_layout.setSpacing(4)
        self.dpi_edit = QLineEdit()
        self.dpi_edit.setObjectName("dpiEdit")
        self.dpi_edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_dpi_src = QLabel("")
        self.lbl_dpi_src.setObjectName("fieldLabel")
        dpi_row_layout.addWidget(self.dpi_edit, stretch=1)
        dpi_row_layout.addWidget(self.lbl_dpi_src)

        self.lbl_scale = QLabel("—")
        self.lbl_scale.setObjectName("fieldValue")

        # Two-way nominal <-> effective pt calculator, driven by _k.
        calc_row = QWidget()
        calc_layout = QHBoxLayout(calc_row)
        calc_layout.setContentsMargins(0, 0, 0, 0)
        calc_layout.setSpacing(4)
        self.calc_nominal = QDoubleSpinBox()
        self.calc_effective = QDoubleSpinBox()
        for spin in (self.calc_nominal, self.calc_effective):
            spin.setObjectName("fieldValue")
            spin.setDecimals(2)
            spin.setRange(0.01, 999.0)
            spin.setSuffix(" pt")
            spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        arrow_lbl = QLabel("→")
        arrow_lbl.setObjectName("fieldLabel")
        calc_layout.addWidget(self.calc_nominal)
        calc_layout.addWidget(arrow_lbl)
        calc_layout.addWidget(self.calc_effective)

        self._asset_rows: dict[str, tuple[QWidget, QWidget]] = {}
        for row, (text, widget, key) in enumerate([
                ("File", self.lbl_asset_name, "file"),
                ("Pixels", self.lbl_asset_px, "px"),
                ("Effective", self.lbl_asset_dpi, "eff"),
                ("Source DPI", dpi_row, "dpi"),
                ("Scale", self.lbl_scale, "scale"),
                ("Font calc", calc_row, "calc")]):
            left = QLabel(text)
            left.setObjectName("fieldLabel")
            if isinstance(widget, QLabel):
                widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            asset_grid.addWidget(left, row, 0)
            asset_grid.addWidget(widget, row, 1)
            self._asset_rows[key] = (left, widget)
        asset_layout.addLayout(asset_grid)

        # Pre-assembly prediction rows (vector assets only)
        self.lbl_prediction = QLabel("")
        self.lbl_prediction.setObjectName("predictionList")
        self.lbl_prediction.setWordWrap(True)
        self.lbl_prediction.setVisible(False)
        asset_layout.addWidget(self.lbl_prediction)
        self.btn_remove_asset = QPushButton("Remove Asset")
        self.btn_remove_asset.setObjectName("removeAssetButton")
        asset_layout.addWidget(self.btn_remove_asset)
        outer.addWidget(self.asset_box)
        self.asset_box.setVisible(False)

        # Stretch
        outer.addStretch(1)

        self.hint_edit.editingFinished.connect(self._emit_hint)
        self.hint_edit.setEnabled(False)
        self.spin_w.editingFinished.connect(lambda: self._emit_size("w"))
        self.spin_h.editingFinished.connect(lambda: self._emit_size("h"))
        self.spin_w.setEnabled(False)
        self.spin_h.setEnabled(False)
        self.btn_square.clicked.connect(self._emit_square)
        self.btn_square.setEnabled(False)
        self.chk_aspect_lock.toggled.connect(self._emit_aspect_lock)
        self.chk_aspect_lock.setEnabled(False)
        self.btn_copy_placement.clicked.connect(self.placement_copy_requested.emit)
        self.btn_copy_snippet.clicked.connect(self.snippet_copy_requested.emit)
        self.btn_copy_card.clicked.connect(self.card_copy_requested.emit)
        self.btn_copy_card.setEnabled(False)
        self.btn_remove_asset.clicked.connect(self._emit_asset_remove)
        self.dpi_edit.editingFinished.connect(self._emit_asset_dpi)
        self.calc_nominal.valueChanged.connect(self._on_calc_nominal)
        self.calc_effective.valueChanged.connect(self._on_calc_effective)
        self.calc_nominal.setValue(8.0)  # the plan's narrative anchor
        self.standin_combo.currentIndexChanged.connect(self._emit_standin)
        self.standin_combo.setEnabled(False)

    def _emit_hint(self) -> None:
        if self._panel_id is None:
            return
        text = self.hint_edit.text()
        if text == self._last_hint:
            return  # unchanged -- no spurious emit/dirty/undo entry (mirrors flush_pending)
        self.content_hint_edited.emit(self._panel_id, text)
        self._last_hint = text

    def _emit_size(self, axis: str) -> None:
        if self._panel_id is None:
            return
        spin = self.spin_w if axis == "w" else self.spin_h
        shown = self._shown_w if axis == "w" else self._shown_h
        value = spin.value()
        if shown is not None and abs(value - shown) < 1e-9:
            return  # unchanged vs what was shown -- no spurious emit/history push
        # Record the shown value BEFORE emitting: size_edited is handled
        # synchronously, and on rejection MainWindow's error path calls back
        # into show_panel() (the authoritative writer of _shown_w/_shown_h)
        # before this method regains control. Writing here first means that
        # authoritative reset -- not this optimistic guess -- wins.
        if axis == "w":
            self._shown_w = value
        else:
            self._shown_h = value
        self.size_edited.emit(self._panel_id, axis, value)

    def _emit_square(self) -> None:
        if self._panel_id is not None:
            self.square_requested.emit(self._panel_id)

    def _emit_asset_remove(self) -> None:
        if self._panel_id is not None:
            self.asset_remove_requested.emit(self._panel_id)

    def _emit_asset_dpi(self) -> None:
        if self._panel_id is None:
            return
        text = self.dpi_edit.text().strip()
        if text == self._last_dpi_text:
            return  # unchanged -- no spurious emit/dirty/undo entry
        try:
            value = float(text) if text else None
        except ValueError:
            return  # unparseable -- leave the tree alone; refresh will reset
        if value is not None and value <= 0:
            return
        self._last_dpi_text = text
        self.asset_dpi_edited.emit(self._panel_id, value)

    def _on_calc_nominal(self, value: float) -> None:
        if self._k and not self._calc_guard:
            self._calc_guard = True
            self.calc_effective.setValue(value * self._k)
            self._calc_guard = False

    def _on_calc_effective(self, value: float) -> None:
        if self._k and not self._calc_guard:
            self._calc_guard = True
            self.calc_nominal.setValue(value / self._k)
            self._calc_guard = False

    def _emit_standin(self, index: int) -> None:
        if self._panel_id is not None:
            self.standin_changed.emit(self._panel_id,
                                      self.standin_combo.itemData(index))

    def _emit_aspect_lock(self, checked: bool) -> None:
        if self._panel_id is None:
            return
        # Use the exact shown rect values, not the 1dp-rounded spinboxes --
        # spin_w/spin_h.value() would lock in a ratio that's already off
        # from the panel's real aspect by the rounding error.
        value = None
        if checked and self._shown_w is not None and self._shown_h:
            value = self._shown_w / self._shown_h
        self.aspect_lock_toggled.emit(self._panel_id, value)

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
                   dpi: int, content_hint: str, aspect_lock: float | None = None,
                   w_adjustable: bool = True, h_adjustable: bool = True,
                   asset_name: str | None = None,
                   asset_px: tuple[int, int] | None = None,
                   eff_dpi: float | None = None, dpi_level: str = "ok",
                   asset_missing: bool = False,
                   asset_dpi: float | None = None,
                   scale_k: float | None = None,
                   stand_in: str | None = None,
                   asset_vector: bool = False,
                   prediction: list[str] | None = None) -> None:
        self._panel_id = panel_id
        w_px, h_px, figsize = derive(rect, dpi)
        self.lbl_label.setText(label)
        self.lbl_xy.setText(f"{rect.x_mm:.1f}, {rect.y_mm:.1f} mm")
        self.lbl_aspect.setText(_aspect_text(rect.w_mm, rect.h_mm))
        self.lbl_px.setText(f"{w_px} × {h_px} @ {dpi} dpi")
        self.lbl_figsize.setText(f"({figsize[0]:.3f}, {figsize[1]:.3f})")

        self.spin_w.blockSignals(True)
        self.spin_h.blockSignals(True)
        self.spin_w.setValue(rect.w_mm)
        self.spin_h.setValue(rect.h_mm)
        self.spin_w.setEnabled(w_adjustable)
        self.spin_h.setEnabled(h_adjustable)
        self.spin_w.blockSignals(False)
        self.spin_h.blockSignals(False)
        self._shown_w = rect.w_mm
        self._shown_h = rect.h_mm

        self.chk_aspect_lock.blockSignals(True)
        self.chk_aspect_lock.setChecked(aspect_lock is not None)
        self.chk_aspect_lock.blockSignals(False)
        self.chk_aspect_lock.setEnabled(True)
        self.btn_square.setEnabled(True)

        self.hint_edit.setEnabled(True)
        self.hint_edit.setText(content_hint)
        self._last_hint = content_hint

        self.standin_combo.blockSignals(True)
        idx = self.standin_combo.findData(stand_in)
        self.standin_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.standin_combo.blockSignals(False)
        self.standin_combo.setEnabled(True)

        self.btn_copy_card.setEnabled(True)

        from figspec_designer.ui.theme import repolish
        if asset_name is None:
            self.asset_box.setVisible(False)
            self._k = None
        else:
            self.asset_box.setVisible(True)
            self.lbl_asset_name.setText(
                asset_name + (" (missing)" if asset_missing else ""))
            if asset_vector and asset_px:
                # intrinsic pt, not pixels -- effective-DPI/source-DPI rows
                # are meaningless for vectors and get hidden below
                self.lbl_asset_px.setText(
                    f"{asset_px[0]} × {asset_px[1]} pt · vector")
            else:
                self.lbl_asset_px.setText(
                    f"{asset_px[0]} × {asset_px[1]} px" if asset_px else "—")
            for key in ("eff", "dpi"):
                for w in self._asset_rows[key]:
                    w.setVisible(not asset_vector)
            self.lbl_asset_dpi.setText(
                f"{eff_dpi:.0f} dpi" if eff_dpi is not None else "—")
            self.lbl_asset_dpi.setProperty(
                "level", "bad" if asset_missing else dpi_level)
            repolish(self.lbl_asset_dpi)
            if prediction:
                self.lbl_prediction.setText("\n".join(prediction))
                self.lbl_prediction.setVisible(True)
            else:
                self.lbl_prediction.setVisible(False)

            self._k = scale_k
            self.dpi_edit.blockSignals(True)
            self.dpi_edit.setText(f"{asset_dpi:g}" if asset_dpi is not None
                                  else "96")
            self.dpi_edit.blockSignals(False)
            self._last_dpi_text = self.dpi_edit.text()
            self.lbl_dpi_src.setText("(declared)" if asset_dpi is not None
                                     else "(assumed)")
            self.lbl_scale.setText(f"×{scale_k:.3f}" if scale_k else "—")
            if scale_k:
                # Re-derive the effective side from whatever nominal value
                # the user last explored -- k just changed under it.
                self._calc_guard = True
                self.calc_effective.setValue(self.calc_nominal.value() * scale_k)
                self._calc_guard = False

    def clear(self) -> None:
        self._panel_id = None
        self._last_hint = None
        self._shown_w = None
        self._shown_h = None
        self._k = None
        self._last_dpi_text = None
        self.btn_copy_card.setEnabled(False)
        for lbl in (self.lbl_label, self.lbl_xy, self.lbl_aspect,
                   self.lbl_px, self.lbl_figsize):
            lbl.setText("—")
        self.spin_w.blockSignals(True)
        self.spin_h.blockSignals(True)
        self.spin_w.setValue(self.spin_w.minimum())
        self.spin_h.setValue(self.spin_h.minimum())
        self.spin_w.setEnabled(False)
        self.spin_h.setEnabled(False)
        self.spin_w.blockSignals(False)
        self.spin_h.blockSignals(False)
        self.chk_aspect_lock.blockSignals(True)
        self.chk_aspect_lock.setChecked(False)
        self.chk_aspect_lock.blockSignals(False)
        self.chk_aspect_lock.setEnabled(False)
        self.btn_square.setEnabled(False)
        self.hint_edit.clear()
        self.hint_edit.setEnabled(False)
        self.standin_combo.blockSignals(True)
        self.standin_combo.setCurrentIndex(0)
        self.standin_combo.blockSignals(False)
        self.standin_combo.setEnabled(False)
        self.asset_box.setVisible(False)
        self.lbl_prediction.setVisible(False)
