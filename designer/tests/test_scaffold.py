import figspec_designer


def test_version():
    assert figspec_designer.__version__ == "0.1.0.dev0"


def test_qt_importable():
    from PySide6.QtWidgets import QApplication  # noqa: F401
