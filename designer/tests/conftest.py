import os

# Set QT platform - use offscreen if available, otherwise minimal
# On macOS, offscreen may have issues so we use minimal as fallback
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
