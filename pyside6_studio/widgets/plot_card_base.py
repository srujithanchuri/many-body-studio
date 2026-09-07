"""Shared mechanics for Plot Gallery cards."""

import datetime
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QMenu


def card_timestamp(plot_path: str) -> str:
    try:
        mtime = os.path.getmtime(plot_path)
        return datetime.datetime.fromtimestamp(mtime).strftime("%b %d, %H:%M")
    except Exception:
        return ""


class PlotCardInteractionMixin:
    """Shared click and context-menu behavior for gallery cards."""

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.sig_selected.emit(self.plot_path)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        a_view = menu.addAction("👁️ View Fullscreen")
        a_copy = menu.addAction("📋 Copy Image to Clipboard")
        menu.addSeparator()
        a_reveal = menu.addAction("📂 Reveal in File Explorer")
        chosen = menu.exec(event.globalPos())
        if chosen == a_view:
            self.sig_view_fullscreen.emit(self.plot_path)
        elif chosen == a_copy:
            pix = QPixmap(self.plot_path)
            if not pix.isNull():
                QApplication.clipboard().setPixmap(pix)
        elif chosen == a_reveal:
            os.system(f'explorer /select,"{self.plot_path}"')
