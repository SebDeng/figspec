import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from figspec_designer.ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def _isolated_designer_settings(tmp_path, monkeypatch):
    """MainWindow reads/writes "recent_files"/"last_file" via
    MainWindow._settings(). Left unpatched, any test that saves or opens a
    file would hit the developer's REAL OS-level QSettings store for org
    "figspec" / app "designer". Point it at an ini file under this test's
    own tmp_path instead. This is the single, suite-wide copy of this
    fixture (test_batch_a_ui.py does not duplicate it)."""
    ini_path = tmp_path / "designer-settings.ini"
    monkeypatch.setattr(
        MainWindow, "_settings",
        lambda self: QSettings(str(ini_path), QSettings.IniFormat))


@pytest.fixture(autouse=True)
def _no_blocking_close_dialog(monkeypatch):
    """pytest-qt's qtbot.addWidget() calls widget.close() on every
    registered widget at test teardown, which fires MainWindow.closeEvent
    -> confirm_discard(). If the window is dirty (any split/settings
    change marks it so -- see _push_tree/_on_settings_changed) that pops a
    real, blocking QMessageBox.exec() with nothing able to click it,
    hanging the whole suite. _open_dialog/_open_recent route through
    confirm_discard() too, for the same reason.

    Patch MainWindow.confirm_discard itself (not the QMessageBox
    primitive it uses internally) to always return True -- confirm_discard
    is deliberately factored out and documented as monkeypatchable for
    exactly this. This is a coarser default than patching QMessageBox.exec
    (it also short-circuits confirm_discard's own dirty check), but is the
    narrower, more legible patch surface: it touches only our own class,
    not a shared Qt primitive, so it can't accidentally swallow an
    unrelated QMessageBox.exec() call elsewhere. Note QMessageBox.warning()
    (used to report open errors) is a *static* method that builds and
    execs its own QMessageBox internally -- an instance-level or
    class-level patch of confirm_discard has no effect on it, and no
    current test calls it on a visible window, so it's simply never an
    issue here.

    Tests exercising the real Save/Discard/Cancel choice monkeypatch
    confirm_discard again locally (instance-level, which shadows this
    class-level default), which simply overrides this default for the
    duration of that test."""
    monkeypatch.setattr(MainWindow, "confirm_discard", lambda self: True)
