"""The single hand-off surface.

Every way figure state leaves the Designer lives here — one palette
(Cmd+E) instead of seven scattered buttons and menu items. Action bodies
moved out of MainWindow; the window keeps thin delegate methods for API
compatibility.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QLabel,
                               QPushButton, QVBoxLayout)


# ---- actions (each takes the MainWindow) --------------------------------

def board_panels(win) -> list:
    """Doc → BoardPanel list; asset paths resolved so the board embeds
    exactly what the canvas shows (missing files stay None → frame only)."""
    from figspec.board import BoardPanel
    from figspec.document import resolve_asset
    from figspec.layout.tree import iter_panels
    nodes = {p.id: p for p in iter_panels(win.doc.tree)}
    labels = win.doc.labels()
    out = []
    for r in win.doc.panel_rects():
        node = nodes[r.panel_id]
        path = None
        if node.asset is not None:
            resolved = resolve_asset(node.asset, win._asset_base_dir())
            path = str(resolved) if resolved is not None else None
        out.append(BoardPanel(labels[r.panel_id], r.x_mm, r.y_mm,
                              r.w_mm, r.h_mm, asset_path=path,
                              asset_px=node.asset_px,
                              asset_dpi=node.asset_dpi))
    return out


def export_board(win) -> None:
    from figspec.board import build_board
    path, _ = QFileDialog.getSaveFileName(
        win, "Export Illustrator board", "figure-board.pdf",
        "PDF for Illustrator (*.pdf)")
    if not path:
        return
    if not Path(path).suffix:
        path += ".pdf"
    try:
        build_board(win.doc.target.figure_width_mm,
                    win.doc.target.figure_height_mm,
                    board_panels(win), path,
                    constraints=win.doc.constraints,
                    label_style=win.doc.constraints.panel_label_style)
    except OSError as e:
        win.statusBar().showMessage(f"Could not write board: {e}", 5000)
        return
    win.statusBar().showMessage(
        "Illustrator board exported — opens at exact size", 4000)


def export_panel_artboard(win, panel_id: str) -> None:
    from figspec.board import panel_artboard
    from figspec.layout.flatten import format_label
    board = next((p for p in board_panels(win)
                  if p.label == win.doc.labels().get(panel_id)), None)
    if board is None:
        win.statusBar().showMessage("Panel no longer exists", 3000)
        return
    letter = format_label(board.label, win.doc.constraints.panel_label_style)
    path, _ = QFileDialog.getSaveFileName(
        win, "Export panel artboard", f"panel-{letter}-artboard.pdf",
        "PDF for Illustrator (*.pdf)")
    if not path:
        return
    if not Path(path).suffix:
        path += ".pdf"
    try:
        panel_artboard(board, path, constraints=win.doc.constraints,
                       label_style=win.doc.constraints.panel_label_style)
    except OSError as e:
        win.statusBar().showMessage(f"Could not write artboard: {e}", 5000)
        return
    win.statusBar().showMessage(
        "Panel artboard exported — draw on it in Illustrator at 1:1", 4000)


def copy_snippet(win) -> None:
    from figspec.snippet import generate_snippet
    name = win.current_path.name if win.current_path else "Untitled"
    QApplication.clipboard().setText(
        generate_snippet(win.doc.to_spec_dict(), name))
    win.statusBar().showMessage("matplotlib snippet copied", 3000)


def copy_card(win) -> None:
    from figspec import scaling
    from figspec.layout.tree import iter_panels
    pid = win.selected_panel_id
    rect = next((r for r in win.doc.panel_rects() if r.panel_id == pid), None)
    if rect is None:
        win.statusBar().showMessage("Select a panel first", 3000)
        return
    panel = next(p for p in iter_panels(win.doc.tree) if p.id == pid)
    # Undeclared raster sources fall back to the same 96 dpi assumption the
    # sidebar displays -- the card must agree with the ×k on screen.
    dpi = panel.asset_dpi if panel.asset_dpi else (
        96.0 if panel.asset_px else None)
    QApplication.clipboard().setText(scaling.authoring_card(
        (rect.w_mm, rect.h_mm), win.doc.constraints,
        asset_px=panel.asset_px, asset_dpi=dpi))
    win.statusBar().showMessage("Authoring card copied", 3000)


def copy_json(win) -> None:
    QApplication.clipboard().setText(win.export_json_text())
    win.statusBar().showMessage("figspec.json copied to clipboard", 3000)


def copy_placement(win) -> None:
    labels = win.doc.labels()
    rows = ["label\tx_mm\ty_mm\tw_mm\th_mm"]
    for rect in sorted(win.doc.panel_rects(),
                       key=lambda r: (round(r.y_mm, 1), r.x_mm)):
        rows.append(f"{labels[rect.panel_id]}\t{rect.x_mm:.2f}\t"
                    f"{rect.y_mm:.2f}\t{rect.w_mm:.2f}\t{rect.h_mm:.2f}")
    QApplication.clipboard().setText("\n".join(rows) + "\n")
    win.statusBar().showMessage("Placement table copied", 3000)


def export_preview(win) -> None:
    from figspec_designer.ui.preview_export import render_layout_png
    path, _ = QFileDialog.getSaveFileName(win, "Export layout preview",
                                          "layout.png", "PNG image (*.png)")
    if not path:
        return
    if not Path(path).suffix:
        path += ".png"
    if render_layout_png(win.doc, path):
        win.statusBar().showMessage(f"Layout preview exported to {path}", 3000)
    else:
        win.statusBar().showMessage(f"Could not write {path}", 3000)


# ---- the palette --------------------------------------------------------

class HandoffDialog(QDialog):
    """One row per audience. Rows act immediately and close the palette;
    file dialogs then open on their own."""

    def __init__(self, win, parent=None):
        super().__init__(parent or win)
        self.setWindowTitle("Hand Off")
        self.setObjectName("handoffDialog")
        self._win = win
        selected = win.selected_panel_id
        letter = ""
        if selected is not None:
            from figspec.layout.flatten import format_label
            raw = win.doc.labels().get(selected)
            if raw:
                letter = format_label(
                    raw, win.doc.constraints.panel_label_style)

        specs = [
            ("Illustrator board",
             "Exact-size PDF — frames on a hideable layer, assets placed 1:1",
             lambda: export_board(win), True),
            (f"Panel artboard{f' ({letter})' if letter else ''}",
             "One panel's canvas at true size — draw on it in Illustrator",
             lambda: export_panel_artboard(win, selected),
             selected is not None),
            ("matplotlib snippet",
             "Starter code with correct figsize and font sizes — clipboard",
             lambda: copy_snippet(win), True),
            (f"Authoring card{f' ({letter})' if letter else ''}",
             "Sizing instructions for Origin/PPT/hand tools — clipboard",
             lambda: copy_card(win), selected is not None),
            ("figspec.json",
             "Machine-readable spec for agents and CI — clipboard",
             lambda: copy_json(win), True),
            ("Placement table",
             "Panel coordinates for manual assembly — clipboard",
             lambda: copy_placement(win), True),
            ("Layout preview PNG",
             "Wireframe with stand-ins, for sharing the plan",
             lambda: export_preview(win), True),
        ]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(4)
        header = QLabel("Hand off to…")
        header.setObjectName("sectionHeader")
        lay.addWidget(header)
        self.rows: list[QPushButton] = []
        for title, desc, fn, enabled in specs:
            btn = QPushButton(f"{title}\n{desc}")
            btn.setObjectName("handoffRow")
            btn.setEnabled(enabled)
            btn.clicked.connect(lambda _=False, f=fn: self._run(f))
            lay.addWidget(btn)
            self.rows.append(btn)
        self.setMinimumWidth(420)

    def _run(self, fn) -> None:
        self.accept()
        fn()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
