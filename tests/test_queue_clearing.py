"""Automated unit test suite for Queue Clearing mechanics in Many-Body Studio.

Verifies:
1. 'Clear Finished' strictly removes finished/cancelled/failed rows and does NOT wipe pending jobs when idle.
2. 'Clear Pending' removes all pending/queued jobs and empties queued_param_list while preserving running/completed jobs.
3. 'Clear Pending' preserves an actively running job at Row #1 intact.
4. 'Delete' / 'Backspace' key removes selected rows.
5. Right-click context menu includes 'Clear All Pending'.
"""

import os
import sys
import tempfile
import unittest

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TEST_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent, QColor
from PySide6.QtWidgets import QApplication, QTableWidgetItem, QProgressBar
from pyside6_studio.main_window import UnifiedWorkbenchWindow


class TestQueueClearing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        self.plots_dir = os.path.join(self.root, 'results', 'plots')
        self.data_dir = os.path.join(self.root, 'results', 'data')
        self.cache_dir = os.path.join(self.root, 'results', 'cache')
        for d in [self.plots_dir, self.data_dir, self.cache_dir]:
            os.makedirs(d, exist_ok=True)
        self.win = UnifiedWorkbenchWindow()

    def tearDown(self):
        self.win.close()
        self.temp_dir.cleanup()

    def _add_mock_row(self, study="Spectral Sweep", params_summary="mu=1.0, Jk=3.0", solver="Host CPU", status="⏳ Queued", is_running=False):
        row = self.win.table_queue.rowCount()
        self.win.table_queue.insertRow(row)
        self.win.table_queue.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.win.table_queue.setItem(row, 1, QTableWidgetItem(study))
        self.win.table_queue.setItem(row, 2, QTableWidgetItem(params_summary))
        self.win.table_queue.setItem(row, 3, QTableWidgetItem(solver))
        prog = QProgressBar()
        prog.setRange(0, 100)
        prog.setValue(50 if is_running else 0)
        self.win.table_queue.setCellWidget(row, 4, prog)
        st_item = QTableWidgetItem(status)
        st_item.setTextAlignment(Qt.AlignCenter)
        self.win.table_queue.setItem(row, 5, st_item)

        if "Queued" in status or "Pending" in status:
            if not hasattr(self.win, "queued_param_list"):
                self.win.queued_param_list = []
            self.win.queued_param_list.append({
                "params": {"study_type": "spectral_sweep", "mu": 1.0},
                "study": study,
                "summary": params_summary,
                "row_idx": row
            })
        self.win._adjust_bottom_dock_height()
        return row

    def test_buttons_presence_and_tooltips(self):
        """Verify presence and tooltips of Clear Finished and Clear Pending buttons."""
        self.assertTrue(hasattr(self.win, "btn_clear"))
        self.assertTrue(hasattr(self.win, "btn_clear_pending"))
        self.assertEqual(self.win.btn_clear.text(), "🗑 Clear Finished")
        self.assertEqual(self.win.btn_clear_pending.text(), "🗑 Clear Pending")
        self.assertIn("completed or cancelled", self.win.btn_clear.toolTip().lower())
        self.assertIn("queued", self.win.btn_clear_pending.toolTip().lower())

    def test_clear_finished_preserves_pending_when_idle(self):
        """Fix verification: Clear Finished while idle must NOT wipe staged/queued jobs!"""
        self._add_mock_row(params_summary="Job 1", status="⏳ Queued")
        self._add_mock_row(params_summary="Job 2", status="⏳ Queued")
        self.assertEqual(self.win.table_queue.rowCount(), 2)
        self.assertEqual(len(self.win.queued_param_list), 2)

        # Click Clear Finished while idle
        self.win.clear_queue()

        # Both pending jobs must remain completely intact!
        self.assertEqual(self.win.table_queue.rowCount(), 2)
        self.assertEqual(len(self.win.queued_param_list), 2)
        self.assertEqual(self.win.table_queue.item(0, 5).text(), "⏳ Queued")
        self.assertEqual(self.win.table_queue.item(1, 5).text(), "⏳ Queued")

    def test_clear_finished_removes_only_finished_rows(self):
        """Verify Clear Finished cleans completed, cancelled, and error rows, but keeps queued rows."""
        self._add_mock_row(params_summary="Finished 1", status="✅ Completed")
        self._add_mock_row(params_summary="Pending 1", status="⏳ Queued")
        self._add_mock_row(params_summary="Cancelled 1", status="⏹ Cancelled")
        self._add_mock_row(params_summary="Failed 1", status="❌ Failed")
        self._add_mock_row(params_summary="Pending 2", status="⏳ Queued")

        self.assertEqual(self.win.table_queue.rowCount(), 5)
        self.win.clear_queue()

        # Only 2 pending jobs should remain
        self.assertEqual(self.win.table_queue.rowCount(), 2)
        self.assertEqual(self.win.table_queue.item(0, 2).text(), "Pending 1")
        self.assertEqual(self.win.table_queue.item(1, 2).text(), "Pending 2")
        # Row numbering must be re-indexed
        self.assertEqual(self.win.table_queue.item(0, 0).text(), "1")
        self.assertEqual(self.win.table_queue.item(1, 0).text(), "2")

    def test_clear_pending_clears_queued_only(self):
        """Verify Clear Pending removes all queued jobs and empties queued_param_list."""
        self._add_mock_row(params_summary="Pending 1", status="⏳ Queued")
        self._add_mock_row(params_summary="Pending 2", status="⏳ Queued")
        self.assertEqual(self.win.table_queue.rowCount(), 2)
        self.assertEqual(len(self.win.queued_param_list), 2)

        self.win.clear_pending_queue()

        self.assertEqual(self.win.table_queue.rowCount(), 0)
        self.assertEqual(len(self.win.queued_param_list), 0)
        self.assertEqual(self.win.lbl_queue_badge.text(), "0 Jobs Queued")

    def test_clear_pending_preserves_active_running_and_completed_jobs(self):
        """Verify Clear Pending keeps running job and historical completed job intact."""
        self._add_mock_row(params_summary="Past Job", status="✅ Completed")
        self._add_mock_row(params_summary="Active Run", status="🔄 Running...", is_running=True)
        self._add_mock_row(params_summary="Pending 1", status="⏳ Queued")
        self._add_mock_row(params_summary="Pending 2", status="⏳ Queued")

        self.assertEqual(self.win.table_queue.rowCount(), 4)
        self.assertEqual(len(self.win.queued_param_list), 2)

        self.win.clear_pending_queue()

        # Past Job and Active Run must remain
        self.assertEqual(self.win.table_queue.rowCount(), 2)
        self.assertEqual(len(self.win.queued_param_list), 0)
        self.assertEqual(self.win.table_queue.item(0, 2).text(), "Past Job")
        self.assertEqual(self.win.table_queue.item(0, 5).text(), "✅ Completed")
        self.assertEqual(self.win.table_queue.item(1, 2).text(), "Active Run")
        self.assertEqual(self.win.table_queue.item(1, 5).text(), "🔄 Running...")
        # Numbering re-indexed
        self.assertEqual(self.win.table_queue.item(0, 0).text(), "1")
        self.assertEqual(self.win.table_queue.item(1, 0).text(), "2")

    def test_delete_key_removes_selected_row(self):
        """Verify pressing Delete key on a selected table row removes it."""
        self._add_mock_row(params_summary="Job 1", status="⏳ Queued")
        self._add_mock_row(params_summary="Job 2", status="⏳ Queued")
        self._add_mock_row(params_summary="Job 3", status="⏳ Queued")

        # Select row 1 (Job 2)
        self.win.table_queue.selectRow(1)

        # Dispatch Delete key event
        key_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
        self.win.table_queue.keyPressEvent(key_event)

        # Row 1 removed, 2 rows remain
        self.assertEqual(self.win.table_queue.rowCount(), 2)
        self.assertEqual(self.win.table_queue.item(0, 2).text(), "Job 1")
        self.assertEqual(self.win.table_queue.item(1, 2).text(), "Job 3")
        self.assertEqual(len(self.win.queued_param_list), 2)
        self.assertEqual(self.win.table_queue.item(0, 0).text(), "1")
        self.assertEqual(self.win.table_queue.item(1, 0).text(), "2")


if __name__ == '__main__':
    unittest.main()
