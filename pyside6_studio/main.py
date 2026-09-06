"""Many-Body Studio [Beta v1 - PySide6 Launch Script]
Run this script to launch Many-Body Studio.
"""

import sys
import os
import warnings

# Suppress harmless CuPy CUDA_PATH UserWarning when running on NVIDIA driver
warnings.filterwarnings("ignore", message=".*CUDA path could not be detected.*", category=UserWarning)

# Ensure pyside6_studio and its parent directory are on path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
GUI_ROOT = os.path.dirname(CURRENT_DIR)
if GUI_ROOT not in sys.path:
    sys.path.insert(0, GUI_ROOT)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, qInstallMessageHandler, QtMsgType
from PySide6.QtGui import QGuiApplication, QIcon
from main_window import UnifiedWorkbenchWindow


def _qt_message_filter(msg_type, context, msg):
    # Suppress benign internal font pointSize sentinel warnings (-1)
    if "setPointSize" in msg and "<= 0" in msg:
        return
    if msg_type == QtMsgType.QtFatalMsg:
        sys.stderr.write(f"[Qt Fatal] {msg}\n")
    elif msg_type == QtMsgType.QtCriticalMsg:
        sys.stderr.write(f"[Qt Critical] {msg}\n")


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
    qInstallMessageHandler(_qt_message_filter)
    configure_high_dpi()

    # Set explicit AppUserModelID so Windows taskbar displays the custom app icon
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("manybody.studio.beta.v1")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Many-Body Studio")
    app.setApplicationDisplayName("Many-Body Studio")
    app.setApplicationVersion("beta-v1.0")
    app.setQuitOnLastWindowClosed(True)

    from pyside6_studio.core.icon_utils import get_app_icon
    app_icon = get_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    window = UnifiedWorkbenchWindow()
    window.showMaximized()
    exit_code = app.exec()
    
    # Clean teardown of window & event queue to eliminate QThreadStorage warnings
    del window
    app.processEvents()
    sys.exit(exit_code)


if __name__ == "__main__":
    if "--params-b64" in sys.argv or "--params" in sys.argv:
        from pyside6_studio.backend.worker_cli import main as worker_main
        worker_main()
        sys.exit(0)
    main()
