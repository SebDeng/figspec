import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox
from figspec_designer.ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def _isolated_designer_settings(tmp_path, monkeypatch):
    """MainWindow reads/writes "recent_files"/"last_file" via
    MainWindow._settings(). Left unpatched, any test that saves or opens a
    file would hit the developer's REAL OS-level QSettings store for org
    "figspec" / app "designer". Point it at an ini file under this test's
    own tmp_path instead. (test_batch_a_ui.py additionally defines its own
    copy of this fixture per the task brief; the two simply layer, with
    whichever applies last winning -- both isolate to a tmp_path ini.)"""
    ini_path = tmp_path / "designer-settings.ini"
    monkeypatch.setattr(
        MainWindow, "_settings",
        lambda self: QSettings(str(ini_path), QSettings.IniFormat))


@pytest.fixture(autouse=True)
def _no_blocking_close_dialog(monkeypatch):
    """pytest-qt's qtbot.addWidget() calls widget.close() on every
    registered widget at test teardown, which fires MainWindow.closeEvent
    -> confirm_discard(). If the window is dirty -- the common case, since
    any split or settings change marks it so -- that pops a real, blocking
    QMessageBox.exec() with nothing able to click it, hanging the whole
    suite (also observed when the whole QApplication quits with a dirty
    window still open -- see app.main's --smoke branch). Patch
    QMessageBox.exec() itself (not MainWindow.confirm_discard) to always
    resolve to Discard, so confirm_discard()'s own dirty-check logic still
    runs for real in tests that want to exercise it directly; only the
    literal blocking call is neutralized. Tests exercising the real
    Save/Discard/Cancel choice monkeypatch confirm_discard (or this same
    QMessageBox.exec) again locally, which simply overrides this default
    for the duration of that test."""
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Discard)
