"""High-DPI Pixel-Perfect Icon Loader for Many-Body Studio.
Ensures crisp, unblurred rendering across all Windows fractional scaling factors (100%, 125%, 150%, 200%).
"""

import os
import sys
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize


def get_app_icon():
    """Builds a multi-resolution QIcon with dedicated pixel-perfect rasters for each DPI scale."""
    icon = QIcon()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, "resources", "icons"),
        os.path.join(os.path.dirname(sys.executable), "resources", "icons"),
    ]
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "pyside6_studio", "resources", "icons"))

    icons_dir = None
    for c in candidates:
        if os.path.isdir(c):
            icons_dir = c
            break

    if not icons_dir:
        return icon

    # Add exact pixel sizes first to prevent linear interpolation blur on High-DPI screens
    exact_sizes = [16, 20, 24, 28, 32, 40, 48, 64, 128, 256]
    for s in exact_sizes:
        png_path = os.path.join(icons_dir, f"app_icon_{s}.png")
        if os.path.isfile(png_path):
            icon.addFile(png_path, QSize(s, s))

    # Add multi-layer ICO
    ico_path = os.path.join(icons_dir, "app_icon.ico")
    if os.path.isfile(ico_path):
        icon.addFile(ico_path)

    # Add master high-res PNG
    master_png = os.path.join(icons_dir, "app_icon.png")
    if os.path.isfile(master_png):
        icon.addFile(master_png)

    return icon
