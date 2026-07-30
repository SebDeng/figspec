import os
import sys

# Set QT platform - try offscreen, fall back to cocoa on macOS
if sys.platform == "darwin":
    # On macOS, offscreen has known issues; use cocoa which is available
    os.environ["QT_QPA_PLATFORM"] = "cocoa"
else:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

def pytest_configure(config):
    """Initialize QApplication before test collection."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
    except Exception as e:
        print(f"Warning: Could not initialize QApplication: {e}")
