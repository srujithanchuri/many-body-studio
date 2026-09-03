"""Hardware-accelerated interactive canvas using QGraphicsView.
Provides smooth CAD-style mousewheel zoom, drag-to-pan, and subpixel rendering.
"""

import os
from PySide6.QtCore import Qt, QPointF, Signal, QRectF
from PySide6.QtGui import QPixmap, QPainter, QWheelEvent, QMouseEvent, QPen, QColor, QFont
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QFrame


class InteractivePlotCanvas(QGraphicsView):
    coord_changed = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = None
        self.current_pixmap = None
        self._zoom = 0
        self._empty = True

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.NoFrame)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setMouseTracking(True)
        self.setBackgroundBrush(QColor("#f1f5f9"))

    def set_theme(self, is_dark: bool):
        bg = "#0b1120" if is_dark else "#f1f5f9"
        self.setBackgroundBrush(QColor(bg))

    def load_image(self, source):
        """Loads from file path, QPixmap, or in-memory byte buffer."""
        if isinstance(source, QPixmap):
            pixmap = source
        elif isinstance(source, (bytes, bytearray)):
            pixmap = QPixmap()
            pixmap.loadFromData(source)
        elif isinstance(source, str) and os.path.exists(source):
            pixmap = QPixmap(source)
        else:
            return

        self.scene.clear()
        self.current_pixmap = pixmap
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.setSceneRect(QRectF(pixmap.rect()))
        self._empty = False
        self.fit_in_view()

    def fit_in_view(self):
        if not self._empty and self.pixmap_item:
            self.resetTransform()
            self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
            self._zoom = 0

    def wheelEvent(self, event: QWheelEvent):
        if self._empty:
            return
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else (1.0 / 1.15)
        self.scale(factor, factor)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.fit_in_view()
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self._empty and self.pixmap_item:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            scene_pos = self.mapToScene(pos)
            self.coord_changed.emit(scene_pos.x(), scene_pos.y())
        super().mouseMoveEvent(event)
