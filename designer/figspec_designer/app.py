"""Application entry point."""
from __future__ import annotations
import os
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    smoke = "--smoke" in argv
    if smoke:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from pathlib import Path
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from figspec_designer.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(argv)
    win = MainWindow()
    # Startup-restore lives here, NOT in MainWindow.__init__, so it never
    # runs (and never needs isolating) under the designer test suite --
    # every test there constructs MainWindow() directly.
    last_file = win._settings().value("last_file")
    if last_file and Path(last_file).exists():
        win.open_json(last_file)
    win.show()
    if smoke:
        # A fresh MainWindow (and a no-op/failed restore above) is never
        # dirty, so app.quit() below drives an ordinary closeEvent ->
        # confirm_discard() fast path (not dirty -> True) with no modal.
        # If that ever stops being true, this headless boot-check would
        # hang forever on a QMessageBox nobody can click -- see
        # MainWindow.confirm_discard / the designer test suite's
        # _no_blocking_close_dialog fixture for the same concern under
        # pytest.
        QTimer.singleShot(0, app.quit)
        app.exec()
        return 0
    return app.exec()
