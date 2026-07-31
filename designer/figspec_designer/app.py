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
        # A freshly-constructed MainWindow is already "dirty" (its
        # trailing __init__ call to _on_settings_changed() marks it so,
        # per the file-lifecycle contract), and on this Qt build,
        # app.quit() drives a real closeEvent on visible top-level windows
        # -> confirm_discard() -> a blocking QMessageBox with nobody able
        # to click it, hanging this headless boot-check forever. --smoke
        # only verifies the app can construct/show/exit cleanly -- it
        # isn't exercising the close-guard -- so mark clean before quitting.
        win.dirty = False
        QTimer.singleShot(0, app.quit)
        app.exec()
        return 0
    return app.exec()
