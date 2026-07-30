"""Assembles canvas + sidebar + top bar and owns the document/undo state."""
from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QMainWindow,
                               QMessageBox, QApplication, QVBoxLayout, QWidget)
from figspec.spec import Constraints, Target
from figspec_designer.document import DesignerDocument, MissingDesignerData
from figspec_designer.model import ops
from figspec_designer.model.history import History
from figspec_designer.model.tree import iter_panels
from figspec_designer.ui.canvas import Canvas
from figspec_designer.ui.sidebar import Sidebar
from figspec_designer.ui.theme import apply_theme
from figspec_designer.ui.toolbar import TopBar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        apply_theme(QApplication.instance())
        self.setWindowTitle("FigSpec Designer")
        self.resize(1100, 700)
        self.doc = DesignerDocument.default()
        self.history = History(self.doc.tree)
        self.selected_panel_id: str | None = None

        self.topbar = TopBar()
        self.canvas = Canvas()
        self.sidebar = Sidebar()
        self.sidebar.setFixedWidth(260)

        central = QWidget()
        central.setObjectName("chrome")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.topbar)
        row = QHBoxLayout()
        row.addWidget(self.canvas, stretch=1)
        row.addWidget(self.sidebar)
        outer.addLayout(row, stretch=1)
        self.setCentralWidget(central)

        self.canvas.panel_action.connect(lambda a, pid: self.do_action(a, pid))
        self.canvas.ratios_committed.connect(self.apply_ratios)
        self.topbar.settings_changed.connect(self._on_settings_changed)
        self.topbar.save_requested.connect(self._save_dialog)
        self.topbar.copy_requested.connect(self.copy_json)
        self.topbar.open_requested.connect(self._open_dialog)
        self.sidebar.content_hint_edited.connect(self._on_hint_edited)

        self._make_menus()
        self.refresh()

    # ---- menus ------------------------------------------------------
    def _make_menus(self) -> None:
        def act(menu, text, shortcut, slot):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(slot)
            menu.addAction(a)
            return a

        file_menu = self.menuBar().addMenu("File")
        act(file_menu, "Open…", "Ctrl+O", self._open_dialog)
        act(file_menu, "Save JSON…", "Ctrl+S", self._save_dialog)
        act(file_menu, "Copy JSON", "Ctrl+Shift+C", self.copy_json)
        edit_menu = self.menuBar().addMenu("Edit")
        act(edit_menu, "Undo", "Ctrl+Z", self.undo)
        act(edit_menu, "Redo", "Ctrl+Shift+Z", self.redo)
        panel_menu = self.menuBar().addMenu("Panel")
        act(panel_menu, "Split Right", "Ctrl+D",
            lambda: self.do_action("split_right", self.selected_panel_id))
        act(panel_menu, "Split Down", "Ctrl+Shift+D",
            lambda: self.do_action("split_down", self.selected_panel_id))
        act(panel_menu, "Delete Panel", "Ctrl+Backspace",
            lambda: self.do_action("close", self.selected_panel_id))

    # ---- state ------------------------------------------------------
    def _push_tree(self, new_tree) -> None:
        self.doc.tree = new_tree
        self.history.push(new_tree)
        self.refresh()

    def refresh(self) -> None:
        self.canvas.set_document(self.doc)
        self.canvas.apply_selection(self.selected_panel_id)
        self._refresh_sidebar()

    def _refresh_sidebar(self) -> None:
        pid = self.selected_panel_id
        panels = {p.id: p for p in iter_panels(self.doc.tree)}
        if pid is None or pid not in panels:
            self.selected_panel_id = None
            self.sidebar.clear()
            return
        rect = next(r for r in self.doc.panel_rects() if r.panel_id == pid)
        self.sidebar.show_panel(pid, self.doc.labels()[pid], rect,
                                self.doc.target.dpi, panels[pid].content_hint)

    # ---- actions ----------------------------------------------------
    def do_action(self, action: str, panel_id: str | None = None) -> None:
        if action == "select":
            # Flush any typed-but-unconfirmed content hint before the
            # sidebar's show_panel() overwrites hint_edit with the newly
            # selected panel's text (clicking another panel never fires
            # QLineEdit.editingFinished on its own).
            self.sidebar.flush_pending()
            self.selected_panel_id = panel_id
            self.canvas.apply_selection(panel_id)
            self._refresh_sidebar()
            return
        if panel_id is None:
            self.statusBar().showMessage("Select a panel first", 3000)
            return
        try:
            if action == "split_right":
                self._push_tree(ops.split_panel(self.doc.tree, panel_id, "right"))
            elif action == "split_down":
                self._push_tree(ops.split_panel(self.doc.tree, panel_id, "down"))
            elif action == "close":
                self._push_tree(ops.close_panel(self.doc.tree, panel_id))
        except ValueError:
            self.statusBar().showMessage("Cannot delete the last panel", 3000)
        except KeyError:
            self.statusBar().showMessage("Panel no longer exists", 3000)

    def apply_ratios(self, path, ratios) -> None:
        self._push_tree(ops.set_ratios(self.doc.tree, tuple(path), tuple(ratios)))

    def undo(self) -> None:
        self.doc.tree = self.history.undo()
        self.refresh()

    def redo(self) -> None:
        self.doc.tree = self.history.redo()
        self.refresh()

    def _on_hint_edited(self, panel_id: str, text: str) -> None:
        try:
            self._push_tree(ops.set_content_hint(self.doc.tree, panel_id, text))
        except KeyError:
            pass

    def _on_settings_changed(self) -> None:
        (preset, width, height, dpi, gutter,
         min_font, max_font, min_lw) = self.topbar.values()
        self.doc.target = Target(preset, width, height, dpi, gutter)
        self.doc.constraints = Constraints(min_font, max_font, min_lw)
        self.refresh()

    # ---- export / open ----------------------------------------------
    def export_json_text(self) -> str:
        return self.doc.to_json()

    def copy_json(self) -> None:
        QApplication.clipboard().setText(self.export_json_text())
        self.statusBar().showMessage("figspec.json copied to clipboard", 3000)

    def save_json(self, path) -> None:
        Path(path).write_text(self.export_json_text())

    def open_json(self, path) -> str | None:
        """Returns an error message, or None on success."""
        try:
            data = json.loads(Path(path).read_text())
            self.doc = DesignerDocument.from_spec_dict(data)
        except MissingDesignerData as e:
            return str(e)
        except Exception as e:
            # Catch-all is intentional: this function's contract is
            # error-string-or-None, and malformed sidecar data can surface
            # as SpecError/ValueError/OSError (bad JSON, bad target/panels)
            # as well as TypeError/AttributeError/KeyError from a malformed
            # "designer.tree" shape (e.g. designer: 5, tree: [...] or a
            # string, a panel node missing "id", non-iterable "ratios").
            # None of those should ever crash the packaged app.
            return f"cannot open: {e}"
        self.history = History(self.doc.tree)
        self.selected_panel_id = None
        self.topbar.set_values(self.doc.target.journal_preset,
                               self.doc.target.figure_width_mm,
                               self.doc.target.figure_height_mm,
                               self.doc.target.dpi, self.doc.target.gutter_mm,
                               self.doc.constraints.min_font_pt,
                               self.doc.constraints.max_font_pt,
                               self.doc.constraints.min_linewidth_pt)
        self.refresh()
        return None

    def _save_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save figspec.json", "figspec.json",
                                              "figspec JSON (*.json)")
        if path:
            self.save_json(path)

    def _open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open figspec.json", "",
                                              "figspec JSON (*.json)")
        if not path:
            return
        err = self.open_json(path)
        if err and self.isVisible():
            QMessageBox.warning(self, "Cannot open", err)
