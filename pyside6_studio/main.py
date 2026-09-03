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
from main_window import UnifiedWorkbenchWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Many-Body Physics Studio Pro")
    window = UnifiedWorkbenchWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
