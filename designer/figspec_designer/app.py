"""Application entry point."""
from __future__ import annotations
import os
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    smoke = "--smoke" in argv
    if smoke:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from figspec_designer.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(argv)
    win = MainWindow()
    win.show()
    if smoke:
        QTimer.singleShot(0, app.quit)
        app.exec()
        return 0
    return app.exec()
