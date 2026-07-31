"""Assembles canvas + sidebar + top bar and owns the document/undo state."""
from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog, QMainWindow,
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
        self.current_path: Path | None = None
        self.dirty: bool = False
        # Set while "swap" is armed (panel id chosen first): the next
        # "select" action either executes ops.swap_panels against it (a
        # different id) or cancels (same id / Esc) -- see do_action/
        # keyPressEvent.
        self._swap_pending: str | None = None

        self.topbar = TopBar()
        self.canvas = Canvas()
        self.sidebar = Sidebar()
        self.sidebar.setFixedWidth(260)

        central = QWidget()
        central.setObjectName("chrome")
        central.setAttribute(Qt.WA_StyledBackground, True)
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
        self.topbar.save_requested.connect(self.save)
        self.topbar.copy_requested.connect(self.copy_json)
        self.topbar.open_requested.connect(self._open_dialog)
        self.sidebar.content_hint_edited.connect(self._on_hint_edited)
        self.sidebar.size_edited.connect(self._on_size_edited)
        self.sidebar.square_requested.connect(self._on_square)
        self.sidebar.aspect_lock_toggled.connect(self._on_aspect_lock)
        self.sidebar.placement_copy_requested.connect(self.copy_placement_table)

        self._make_menus()
        # Init-time doc/topbar sync only -- NOT _on_settings_changed(),
        # which additionally marks dirty. A freshly-constructed window with
        # no user edits must not be dirty (see _sync_settings()).
        self._sync_settings()
        self.dirty = False  # belt-and-braces: no _mark_dirty() call above,
        self._refresh_title()  # but make the clean state explicit anyway.

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
        self.recent_menu = file_menu.addMenu("Open Recent")
        self.recent_menu.aboutToShow.connect(self._rebuild_recent_menu)
        act(file_menu, "Save JSON…", "Ctrl+S", self.save)
        act(file_menu, "Save As…", "Ctrl+Shift+S", self.save_as)
        act(file_menu, "Copy JSON", "Ctrl+Shift+C", self.copy_json)
        act(file_menu, "Copy Placement Table", None, self.copy_placement_table)
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
        panel_menu.addSeparator()
        act(panel_menu, "Split Right N…", None,
            lambda: self.do_action("split_right_n", self.selected_panel_id))
        act(panel_menu, "Split Down N…", None,
            lambda: self.do_action("split_down_n", self.selected_panel_id))
        act(panel_menu, "Equalize", None,
            lambda: self.do_action("equalize", self.selected_panel_id))
        act(panel_menu, "Swap", None,
            lambda: self.do_action("swap", self.selected_panel_id))

    # ---- state ------------------------------------------------------
    def _push_tree(self, new_tree) -> None:
        self.doc.tree = new_tree
        self.history.push(new_tree)
        self.refresh()
        self._mark_dirty()

    def _settings(self) -> QSettings:
        """QSettings accessor -- factored to a single method so tests can
        monkeypatch it to an isolated ini-backed QSettings BEFORE
        constructing a MainWindow, keeping recent-files/last-file state out
        of the real user preferences during test runs."""
        return QSettings("figspec", "designer")

    def _mark_dirty(self) -> None:
        self.dirty = True
        self._refresh_title()

    def _refresh_title(self) -> None:
        # Path(...) defensively handles a plain str assigned to
        # current_path (the field is typed Path | None, but nothing
        # enforces that at the attribute-assignment level).
        name = Path(self.current_path).name if self.current_path else "Untitled"
        dot = " •" if self.dirty else ""
        self.setWindowTitle(f"{name}{dot} — FigSpec Designer")

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
        panel = panels[pid]
        self.sidebar.show_panel(pid, self.doc.labels()[pid], rect,
                                self.doc.target.dpi, panel.content_hint,
                                aspect_lock=panel.aspect_lock,
                                w_adjustable=self._axis_adjustable(pid, "w"),
                                h_adjustable=self._axis_adjustable(pid, "h"))

    def _axis_adjustable(self, panel_id: str, axis: str) -> bool:
        """Probe whether axis can be resized on the CURRENT tree, without
        pushing any change -- used to enable/disable the sidebar spinboxes."""
        rect = next((r for r in self.doc.panel_rects() if r.panel_id == panel_id), None)
        if rect is None:
            return False
        size = rect.w_mm if axis == "w" else rect.h_mm
        try:
            ops.set_panel_size(self.doc.tree, panel_id, axis, size,
                               self.doc.target.figure_width_mm,
                               self.doc.target.figure_height_mm,
                               self.doc.target.gutter_mm)
            return True
        except (ValueError, KeyError):
            return False

    # ---- actions ----------------------------------------------------
    def do_action(self, action: str, panel_id: str | None = None) -> None:
        if action == "select":
            if self._swap_pending is not None:
                self._resolve_swap(panel_id)
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
        dims = (self.doc.target.figure_width_mm, self.doc.target.figure_height_mm,
                self.doc.target.gutter_mm)
        try:
            if action == "split_right":
                self._push_tree(ops.split_panel(self.doc.tree, panel_id, "right"))
            elif action == "split_down":
                self._push_tree(ops.split_panel(self.doc.tree, panel_id, "down"))
            elif action == "split_right_n":
                self._split_n(panel_id, "right", dims)
            elif action == "split_down_n":
                self._split_n(panel_id, "down", dims)
            elif action == "equalize":
                self._push_tree(ops.equalize_siblings(self.doc.tree, panel_id))
            elif action == "swap":
                self._swap_pending = panel_id
                self.statusBar().showMessage(
                    "Swap: select another panel to exchange with (Esc to cancel)")
            elif action == "close":
                self._push_tree(ops.close_panel(self.doc.tree, panel_id))
        except ValueError as e:
            msg = "Cannot delete the last panel" if action == "close" else str(e)
            self.statusBar().showMessage(msg, 3000)
        except KeyError:
            self.statusBar().showMessage("Panel no longer exists", 3000)

    def _split_n(self, panel_id: str, direction: str,
                dims: tuple[float, float, float]) -> None:
        n = self._ask_n()
        if n is None:  # dialog cancelled
            return
        page_w_mm, page_h_mm, gutter_mm = dims
        self._push_tree(ops.split_panel_n(
            self.doc.tree, panel_id, direction, n,
            page_w_mm=page_w_mm, page_h_mm=page_h_mm, gutter_mm=gutter_mm))

    def _ask_n(self) -> int | None:
        """Factored out so tests can monkeypatch it to bypass the modal
        QInputDialog. Returns None if the user cancelled."""
        n, ok = QInputDialog.getInt(self, "Split panel", "Number of panels:",
                                    3, 2, 8)
        return n if ok else None

    def _resolve_swap(self, panel_id: str | None) -> None:
        """Called from do_action("select", ...) while swap mode is armed.
        A different, existing panel id completes the swap; the same id
        (or no id) cancels -- either way swap mode is cleared."""
        pending = self._swap_pending
        self._swap_pending = None
        if panel_id is None or panel_id == pending:
            self.statusBar().showMessage("Swap cancelled", 3000)
            return
        try:
            self._push_tree(ops.swap_panels(self.doc.tree, pending, panel_id))
        except (ValueError, KeyError) as e:
            self.statusBar().showMessage(str(e), 3000)

    # ---- keyboard: swap-cancel + nudge -------------------------------
    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape and self._swap_pending is not None:
            self._swap_pending = None
            self.statusBar().showMessage("Swap cancelled", 3000)
            return
        if self.selected_panel_id is not None and event.modifiers() & Qt.ControlModifier:
            axis_delta = {
                Qt.Key_Left: ("w", -1.0), Qt.Key_Right: ("w", 1.0),
                Qt.Key_Up: ("h", -1.0), Qt.Key_Down: ("h", 1.0),
            }.get(event.key())
            if axis_delta is not None:
                axis, sign = axis_delta
                step = 2.0 if event.modifiers() & Qt.ShiftModifier else 0.5
                self._nudge(axis, sign * step)
                return
        super().keyPressEvent(event)

    def _nudge(self, axis: str, delta_mm: float) -> None:
        pid = self.selected_panel_id
        rect = next((r for r in self.doc.panel_rects() if r.panel_id == pid), None)
        if rect is None:
            return
        current = rect.w_mm if axis == "w" else rect.h_mm
        try:
            self._push_tree(ops.set_panel_size(
                self.doc.tree, pid, axis, current + delta_mm,
                self.doc.target.figure_width_mm, self.doc.target.figure_height_mm,
                self.doc.target.gutter_mm))
        except (ValueError, KeyError) as e:
            self.statusBar().showMessage(str(e), 3000)

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

    def _on_size_edited(self, panel_id: str, axis: str, size_mm: float) -> None:
        try:
            self._push_tree(ops.set_panel_size(
                self.doc.tree, panel_id, axis, size_mm,
                self.doc.target.figure_width_mm, self.doc.target.figure_height_mm,
                self.doc.target.gutter_mm))
        except (ValueError, KeyError) as e:
            self.statusBar().showMessage(str(e), 3000)
            self._refresh_sidebar()  # snap the spinbox back to the actual value

    def _on_square(self, panel_id: str) -> None:
        rect = next((r for r in self.doc.panel_rects() if r.panel_id == panel_id), None)
        if rect is None:
            return
        dims = (self.doc.target.figure_width_mm, self.doc.target.figure_height_mm,
                self.doc.target.gutter_mm)
        try:
            new_tree = ops.set_panel_size(self.doc.tree, panel_id, "h", rect.w_mm, *dims)
        except (ValueError, KeyError):
            # h isn't adjustable for this panel (e.g. it's not split along the
            # column axis) -- fall back to matching w to h instead.
            try:
                new_tree = ops.set_panel_size(self.doc.tree, panel_id, "w", rect.h_mm, *dims)
            except (ValueError, KeyError) as e:
                self.statusBar().showMessage(f"Cannot make square: {e}", 3000)
                return
        self._push_tree(new_tree)

    def _on_aspect_lock(self, panel_id: str, value: float | None) -> None:
        try:
            self._push_tree(ops.set_aspect_lock(self.doc.tree, panel_id, value))
        except KeyError:
            pass

    def _sync_settings(self) -> None:
        """Pull target/constraints from the topbar into self.doc and
        refresh -- with NO dirty-marking side effect. Used both by
        __init__ (initial sync from the topbar's own defaults, which must
        not make a fresh window dirty) and by _on_settings_changed (a real
        user edit, which does mark dirty)."""
        (preset, width, height, dpi, gutter,
         min_font, max_font, min_lw) = self.topbar.values()
        self.doc.target = Target(preset, width, height, dpi, gutter)
        self.doc.constraints = Constraints(min_font, max_font, min_lw)
        self.refresh()

    def _on_settings_changed(self) -> None:
        self._sync_settings()
        self._mark_dirty()

    # ---- export / open ----------------------------------------------
    def export_json_text(self) -> str:
        return self.doc.to_json()

    def copy_json(self) -> None:
        QApplication.clipboard().setText(self.export_json_text())
        self.statusBar().showMessage("figspec.json copied to clipboard", 3000)

    def copy_placement_table(self) -> None:
        labels = self.doc.labels()
        rows = ["label\tx_mm\ty_mm\tw_mm\th_mm"]
        for rect in sorted(self.doc.panel_rects(),
                           key=lambda r: (round(r.y_mm, 1), r.x_mm)):
            rows.append(f"{labels[rect.panel_id]}\t{rect.x_mm:.2f}\t"
                        f"{rect.y_mm:.2f}\t{rect.w_mm:.2f}\t{rect.h_mm:.2f}")
        QApplication.clipboard().setText("\n".join(rows) + "\n")
        self.statusBar().showMessage("Placement table copied", 3000)

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
        self.current_path = Path(path)
        self.dirty = False
        self._add_recent(self.current_path)
        self._refresh_title()
        return None

    # ---- save / recents / close guard --------------------------------
    def save(self) -> bool:
        """⌘S: silent write if a current_path is already known, otherwise
        falls through to the Save As dialog. Returns True on a completed
        write, False if the user cancelled a Save As prompt."""
        if self.current_path is not None:
            self.save_json(self.current_path)
            self.dirty = False
            self._refresh_title()
            self._add_recent(self.current_path)
            return True
        return self.save_as()

    def save_as(self) -> bool:
        """⇧⌘S: always prompts for a destination path."""
        path = self._ask_save_path()
        if path is None:
            return False
        self.current_path = path
        self.save_json(self.current_path)
        self.dirty = False
        self._refresh_title()
        self._add_recent(self.current_path)
        return True

    def _ask_save_path(self) -> Path | None:
        """Factored out so tests can monkeypatch it to bypass the modal
        QFileDialog (which returns "" and would make save()/save_as()
        return False when no dialog is available)."""
        path, _ = QFileDialog.getSaveFileName(self, "Save figspec.json", "figspec.json",
                                              "figspec JSON (*.json)")
        return Path(path) if path else None

    def recent_files(self) -> list[str]:
        raw = self._settings().value("recent_files", [])
        if not raw:
            return []
        if isinstance(raw, str):
            # QSettings collapses a single-element list to a bare string
            # under some backends/formats -- normalize back to a list.
            return [raw]
        return list(raw)

    def _add_recent(self, path) -> None:
        entry = str(path)
        recents = [p for p in self.recent_files() if p != entry]
        recents.insert(0, entry)
        recents = recents[:5]
        settings = self._settings()
        settings.setValue("recent_files", recents)
        settings.setValue("last_file", entry)

    def _rebuild_recent_menu(self) -> None:
        menu = self.recent_menu
        menu.clear()
        recents = self.recent_files()
        if not recents:
            empty = QAction("(No Recent Files)", menu)
            empty.setEnabled(False)
            menu.addAction(empty)
        else:
            for path in recents:
                action = QAction(path, menu)
                action.triggered.connect(
                    lambda checked=False, p=path: self._open_recent(p))
                menu.addAction(action)
        menu.addSeparator()
        menu.addAction("Clear Menu", self._clear_recent)

    def _open_recent(self, path: str) -> None:
        if not self.confirm_discard():
            return
        err = self.open_json(path)
        if err and self.isVisible():
            QMessageBox.warning(self, "Cannot open", err)

    def _clear_recent(self) -> None:
        # Deliberately clears only "recent_files" -- "last_file" (used by
        # the startup-restore hook in app.main) is left untouched, since
        # "Clear Menu" reads as clearing the visible list, not disabling
        # next-launch restore.
        self._settings().remove("recent_files")

    def confirm_discard(self) -> bool:
        """True if it's fine to proceed with discarding unsaved changes
        (window is clean, or the user chose Save/Discard); False if the
        user cancelled. Factored to its own method -- rather than inlined
        in closeEvent -- so tests can monkeypatch it to bypass the modal
        QMessageBox entirely."""
        if not self.dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Unsaved Changes")
        box.setText("This document has unsaved changes. Save before closing?")
        box.setStandardButtons(
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Save)
        choice = box.exec()
        if choice == QMessageBox.Save:
            return self.save()
        return choice == QMessageBox.Discard

    def closeEvent(self, event) -> None:
        if self.confirm_discard():
            event.accept()
        else:
            event.ignore()

    def _open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open figspec.json", "",
                                              "figspec JSON (*.json)")
        if not path:
            return
        if not self.confirm_discard():
            return
        err = self.open_json(path)
        if err and self.isVisible():
            QMessageBox.warning(self, "Cannot open", err)
