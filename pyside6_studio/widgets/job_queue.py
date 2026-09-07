"""Execution queue presentation widget.

The widget owns queue-table presentation and queue-specific controls.
Batch execution state and CalculationBridge orchestration remain in
UnifiedWorkbenchWindow.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pyside6_studio.core.hardware import get_hardware_info


class JobQueueWidget(QWidget):
    """Owns the execution-queue table and its presentation controls.

    The parent window still owns the CalculationBridge, queued parameter
    records, and execution state. Callbacks are deliberately explicit so
    this widget does not become a generic job-runner abstraction.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        on_start: Callable[[], None] | None = None,
        on_pause: Callable[[], None] | None = None,
        on_add: Callable[[], None] | None = None,
        on_clear: Callable[[], None] | None = None,
        on_clear_pending: Callable[[], None] | None = None,
        on_cancel_all: Callable[[], None] | None = None,
        on_cancel_active: Callable[[], None] | None = None,
        on_remove_row: Callable[[int], None] | None = None,
        on_resize: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_start = on_start
        self._on_pause = on_pause
        self._on_add = on_add
        self._on_clear = on_clear
        self._on_clear_pending = on_clear_pending
        self._on_cancel_all = on_cancel_all
        self._on_cancel_active = on_cancel_active
        self._on_remove_row = on_remove_row
        self._on_resize = on_resize
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.btn_start = QPushButton("▶ Run All Pending")
        self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.setToolTip("Start running all pending calculation jobs in sequential batch queue")
        self.btn_start.setStyleSheet("""
            QPushButton {
                padding: 4px 13px;
                background: #2563eb;
                border: 1px solid #1d4ed8;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 700;
                color: #ffffff;
            }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:pressed { background: #1e40af; }
        """)
        if self._on_start:
            self.btn_start.clicked.connect(self._on_start)
        row.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setToolTip("Pause batch execution after current step")
        if self._on_pause:
            self.btn_pause.clicked.connect(self._on_pause)
        row.addWidget(self.btn_pause)

        self.btn_add_to_queue = QPushButton("➕ Add Active Study")
        self.btn_add_to_queue.setToolTip("Enqueue current study and parameter snapshot into the batch list")
        if self._on_add:
            self.btn_add_to_queue.clicked.connect(self._on_add)
        row.addWidget(self.btn_add_to_queue)

        self.btn_clear = QPushButton("🗑 Clear Finished")
        self.btn_clear.setToolTip("Remove all completed or cancelled entries from the queue")
        if self._on_clear:
            self.btn_clear.clicked.connect(self._on_clear)
        row.addWidget(self.btn_clear)

        self.btn_clear_pending = QPushButton("🗑 Clear Pending")
        self.btn_clear_pending.setToolTip("Remove all unstarted and queued entries waiting in batch queue")
        if self._on_clear_pending:
            self.btn_clear_pending.clicked.connect(self._on_clear_pending)
        row.addWidget(self.btn_clear_pending)

        self.btn_cancel_all = QPushButton("⏹ Cancel All")
        self.btn_cancel_all.setObjectName("BtnCancelAll")
        self.btn_cancel_all.setToolTip("Immediately stop active calculation and cancel all queued jobs")
        self.btn_cancel_all.setStyleSheet("""
            QPushButton {
                padding: 4px 11px;
                background: #fef2f2;
                border: 1px solid #fca5a5;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                color: #b91c1c;
            }
            QPushButton:hover {
                background: #fee2e2;
                border-color: #ef4444;
                color: #991b1b;
            }
        """)
        if self._on_cancel_all:
            self.btn_cancel_all.clicked.connect(self._on_cancel_all)
        row.addWidget(self.btn_cancel_all)
        row.addStretch(1)

        self.lbl_queue_badge = QLabel("0 Jobs Queued")
        row.addWidget(self.lbl_queue_badge)
        layout.addLayout(row)

        self.table_queue = QTableWidget(0, 6)
        self.table_queue.setObjectName("QueueTable")
        self.table_queue.setHorizontalHeaderLabels(
            ["#", "Study", "Parameters Snapshot", "Solver", "Progress", "Status"]
        )
        self.table_queue.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_queue.customContextMenuRequested.connect(self._on_context_menu)

        original_key_press = self.table_queue.keyPressEvent

        def queue_key_press(event):
            if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                selected_rows = sorted(
                    set(idx.row() for idx in self.table_queue.selectedIndexes()),
                    reverse=True,
                )
                for row_index in selected_rows:
                    self.remove_row(row_index)
            else:
                original_key_press(event)

        self.table_queue.keyPressEvent = queue_key_press

        header = self.table_queue.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table_queue.setColumnWidth(4, 130)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table_queue.verticalHeader().setDefaultSectionSize(26)
        self.table_queue.verticalHeader().setVisible(False)
        self.table_queue.setShowGrid(True)
        self.table_queue.setAlternatingRowColors(True)
        layout.addWidget(self.table_queue)

    def create_row(
        self,
        study_name: str,
        summary: str,
        solver_choice: str,
        status: str = "⏳ Queued",
    ) -> int:
        """Create a standardized queue row and return its row index."""
        row = self.table_queue.rowCount()
        self.table_queue.insertRow(row)

        item_num = QTableWidgetItem(str(row + 1))
        item_num.setTextAlignment(Qt.AlignCenter)
        self.table_queue.setItem(row, 0, item_num)

        item_study = QTableWidgetItem(study_name)
        font_study = item_study.font()
        font_study.setBold(True)
        item_study.setFont(font_study)
        item_study.setForeground(QColor("#60a5fa") if self.is_dark else QColor("#2563eb"))
        self.table_queue.setItem(row, 1, item_study)

        item_snap = QTableWidgetItem(summary)
        item_snap.setTextAlignment(Qt.AlignCenter)
        item_snap.setForeground(QColor("#94a3b8") if self.is_dark else QColor("#475569"))
        self.table_queue.setItem(row, 2, item_snap)

        hw = get_hardware_info()
        gpu_name = hw.get("name", "CUDA GPU")
        solver_str = f"{gpu_name} (GPU)" if solver_choice == "gpu" else "CPU (Multi-Core)"
        item_solver = QTableWidgetItem(solver_str)
        item_solver.setTextAlignment(Qt.AlignCenter)
        self.table_queue.setItem(row, 3, item_solver)

        prog = QProgressBar()
        prog.setStyleSheet("""
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                text-align: center;
                background: #f1f5f9;
                font-size: 10px;
                font-weight: 600;
                color: #0f172a;
                height: 16px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
                border-radius: 3px;
            }
        """)
        if status.startswith("🔄"):
            prog.setRange(0, 0)
        else:
            prog.setRange(0, 100)
            prog.setValue(0)
        self.table_queue.setCellWidget(row, 4, prog)

        item_status = QTableWidgetItem(status)
        item_status.setTextAlignment(Qt.AlignCenter)
        self.table_queue.setItem(row, 5, item_status)
        self.request_resize()
        return row

    def remove_row(self, row: int) -> None:
        """Request row removal while retaining execution ownership in the main window."""
        if 0 <= row < self.table_queue.rowCount() and self._on_remove_row:
            self._on_remove_row(row)

    def _on_context_menu(self, pos) -> None:
        row = self.table_queue.rowAt(pos.y())
        menu = QMenu(self)

        if 0 <= row < self.table_queue.rowCount():
            item = self.table_queue.item(row, 5)
            status = item.text() if item else ""
            if any(k in status for k in ["Running", "Solving", "🔄"]):
                action = menu.addAction("⏹ Cancel Active Calculation")
                if self._on_cancel_active:
                    action.triggered.connect(self._on_cancel_active)
            elif any(k in status for k in ["Queued", "Pending", "⏳"]):
                action = menu.addAction("🗑 Remove from Queue")
                action.triggered.connect(lambda: self.remove_row(row))
            else:
                action = menu.addAction("🗑 Remove Entry")
                action.triggered.connect(lambda: self.remove_row(row))
            menu.addSeparator()

        action = menu.addAction("🗑 Clear All Pending")
        if self._on_clear_pending:
            action.triggered.connect(self._on_clear_pending)
        action = menu.addAction("🗑 Clear All Finished / Cancelled")
        if self._on_clear:
            action.triggered.connect(self._on_clear)
        action = menu.addAction("⏹ Cancel All Calculations")
        if self._on_cancel_all:
            action.triggered.connect(self._on_cancel_all)
        menu.exec(self.table_queue.viewport().mapToGlobal(pos))

    def clear_finished(self, queued_param_list: list, active_queue_row: int) -> tuple[list, int, int]:
        """Remove completed/failed/cancelled rows and return updated queue state."""
        row = 0
        removed = 0
        while row < self.table_queue.rowCount():
            item = self.table_queue.item(row, 5)
            status = item.text() if item else ""
            if any(tag in status for tag in ["Completed", "Failed", "Cancelled", "Error", "⏹", "✅", "❌"]):
                self.table_queue.removeRow(row)
                removed += 1
                if active_queue_row > row:
                    active_queue_row -= 1
                for job in queued_param_list:
                    if job.get("row_idx", 0) > row:
                        job["row_idx"] -= 1
            else:
                row += 1
        self.renumber()
        self.request_resize()
        return queued_param_list, active_queue_row, removed

    def clear_pending(self, queued_param_list: list, active_queue_row: int) -> tuple[list, int, int]:
        """Remove unstarted jobs while preserving active and finished records."""
        queued_param_list.clear()
        row = 0
        removed = 0
        while row < self.table_queue.rowCount():
            item = self.table_queue.item(row, 5)
            status = item.text() if item else ""
            if any(tag in status for tag in ["Running", "Solving", "🔄"]):
                row += 1
            elif any(tag in status for tag in ["Completed", "Failed", "Cancelled", "Error", "⏹", "✅", "❌"]):
                row += 1
            else:
                self.table_queue.removeRow(row)
                removed += 1
                if active_queue_row > row:
                    active_queue_row -= 1
        self.renumber()
        self.request_resize()
        return queued_param_list, active_queue_row, removed

    def renumber(self) -> None:
        for row in range(self.table_queue.rowCount()):
            self.table_queue.setItem(row, 0, QTableWidgetItem(str(row + 1)))

    def request_resize(self) -> None:
        if self._on_resize:
            self._on_resize()

    def update_badge(self) -> None:
        count = self.table_queue.rowCount()
        self.lbl_queue_badge.setText(
            "0 Jobs Queued" if count == 0 else f"{count} Job{'s' if count != 1 else ''} Total"
        )

    @property
    def is_dark(self) -> bool:
        parent = self.parentWidget()
        return bool(getattr(parent, "is_dark", False))

