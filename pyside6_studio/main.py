"""Many-Body Physics Studio Pro [PySide6 Launch Script]
Run this script to launch the Dual-Perspective Studio.
"""

import sys
import os

# Ensure pyside6_studio and its parent directory are on path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
GUI_ROOT = os.path.dirname(CURRENT_DIR)
if GUI_ROOT not in sys.path:
    sys.path.insert(0, GUI_ROOT)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from main_window import UnifiedWorkbenchWindow


def configure_high_dpi():
    """Configures native Windows subpixel fractional DPI rendering without rounding blur.
    Note: Qt 6 automatically manages DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 on Windows natively.
    """
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass


def main():
    configure_high_dpi()
    app = QApplication(sys.argv)
    app.setApplicationName("Many-Body Physics Studio Pro • Alpha v3.5")
    app.setApplicationVersion("alpha-v3.5")
    app.setQuitOnLastWindowClosed(True)
    window = UnifiedWorkbenchWindow()
    window.showMaximized()
    exit_code = app.exec()
    # Guarantee immediate OS-level exit to release console/terminal prompt instantly
    os._exit(exit_code)


if __name__ == "__main__":
    main()
