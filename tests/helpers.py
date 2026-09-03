"""Shared test helpers and test doubles for Many-Body Studio Pro E2E tests."""

import os
import sys
import tempfile
import time
import subprocess
from typing import Any, List, Optional

# Ensure headless offscreen mode
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor


def get_qapp() -> QApplication:
    """Returns or instantiates the headless QApplication singleton."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def process_events(ms: int = 50) -> None:
    """Spins the Qt event loop for specified duration to allow signal delivery."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


class SignalCollector:
    """Helper to collect emitted signals for assertions."""

    def __init__(self, signal=None):
        self.emissions: List[Any] = []
        if signal is not None:
            signal.connect(self)

    def __call__(self, *args):
        if len(args) == 1:
            self.emissions.append(args[0])
        else:
            self.emissions.append(args)

    @property
    def count(self) -> int:
        return len(self.emissions)

    @property
    def last(self) -> Optional[Any]:
        return self.emissions[-1] if self.emissions else None

    def wait_until(self, condition_fn, timeout_sec: float = 2.0, poll_ms: int = 20) -> bool:
        """Spins event loop until condition_fn() returns True or timeout."""
        start = time.time()
        while time.time() - start < timeout_sec:
            process_events(poll_ms)
            if condition_fn():
                return True
        return condition_fn()


def create_test_image(filepath: str, width: int = 120, height: int = 80) -> str:
    """Generates a valid minimal PNG image file for canvas testing."""
    img = QImage(width, height, QImage.Format_RGB32)
    img.fill(QColor(40, 80, 160))
    painter = QPainter(img)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(10, 40, "Test Plot")
    painter.end()
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    img.save(filepath, "PNG")
    return filepath


def is_process_alive(pid: int) -> bool:
    """Checks if a process with given PID is alive on Windows."""
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            output = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                text=True,
                stderr=subprocess.DEVNULL
            )
            return str(pid) in output
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
