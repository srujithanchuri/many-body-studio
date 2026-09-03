"""Many-Body Physics Studio Pro [PySide6 Launch Script]
Run this script to launch the Dual-Perspective Studio.
"""

import sys
import os

# Ensure pyside6_studio is on path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from main_window import UnifiedWorkbenchWindow


def configure_high_dpi():
    """Configures native Windows Per-Monitor High-DPI awareness and subpixel rendering."""
    # Prevent Windows Desktop Window Manager (DWM) from bitmap-stretching python.exe
    if sys.platform == "win32":
        import ctypes
        try:
            # PROCESS_PER_MONITOR_DPI_AWARE_V2 = 2 (Windows 10 1703+)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    # Ensure Qt uses subpixel fractional DPI scaling without rounding blur
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass


def main():
    configure_high_dpi()
    app = QApplication(sys.argv)
    app.setApplicationName("Many-Body Physics Studio Pro")
    window = UnifiedWorkbenchWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
