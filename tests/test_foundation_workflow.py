"""Unit and integration test suite for Direct Foundation Cache Synthesis and In-Situ Discovery Workflow.

Tests:
1. FoundationCacheDialog configuration, parameter reactivity, and visibility
2. Direct backend foundation cache task execution
3. Dual-action dock buttons (Fast Foundation vs Full Sweep) and automatic canvas mode transition
"""

import os
import sys
import tempfile
import unittest

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TEST_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication
from pyside6_studio.widgets.foundation_cache_dialog import FoundationCacheDialog
from pyside6_studio.widgets.interactive_plots import InteractivePlotsWidget
from pyside6_studio.main_window import UnifiedWorkbenchWindow


class TestFoundationWorkflow(unittest.TestCase):
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

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_foundation_cache_dialog_ui(self):
        """Test FoundationCacheDialog instantiation, field reactivity, and visibility."""
        dlg = FoundationCacheDialog(
            out_dir=self.root,
            default_category='sigma_base',
            default_mu=1.5,
            default_jperp=4.0
        )
        dlg.show()
        self.assertEqual(dlg.spin_mu.value(), 1.5)
        self.assertEqual(dlg.spin_jperp.value(), 4.0)
        self.assertTrue(dlg.row_jperp.isVisible())

        # Switch to Bare Static Susceptibility -> J_perp row should hide
        dlg.cb_category.setCurrentIndex(1)
        self.assertFalse(dlg.row_jperp.isVisible())

        # Switch back to 3-Loop Self-Energy -> J_perp row should reappear
        dlg.cb_category.setCurrentIndex(0)
        self.assertTrue(dlg.row_jperp.isVisible())

        # Ensure target dropdown items
        self.assertEqual(dlg.cb_category.itemText(0), "Self-Energy Σ(k, ω)")
        self.assertEqual(dlg.cb_category.itemText(1), "Bare Static Susceptibility χ₀(q)")

        # Ensure run button is enabled and properly labeled
        self.assertTrue(dlg.btn_run.isEnabled())
        self.assertIn('Run', dlg.btn_run.text())

        # Test dynamic engine state updates
        dlg.update_engine_state(is_running=True)
        self.assertIn('Add to Queue', dlg.btn_run.text())
        dlg.update_engine_state(is_running=False)
        self.assertIn('Run', dlg.btn_run.text())
        dlg.close()

    def test_foundation_button_menu_and_actions(self):
        """Test InteractivePlotsWidget button is a direct Compute Cache launcher."""
        w = InteractivePlotsWidget(out_dir=self.root)
        self.assertIsNotNone(w.btn_compute_cache)
        self.assertIn("Compute Cache", w.btn_compute_cache.text())
        w.close()

    def test_dual_action_dock_buttons_and_execution_state(self):
        """Test primary execution buttons and verify redundant dock buttons are removed."""
        window = UnifiedWorkbenchWindow()
        window.edit_out_dir.setText(self.root)

        # Redundant dock run buttons are removed from Computation & Cache Status
        self.assertFalse(hasattr(window, "btn_dock_foundation"))
        self.assertFalse(hasattr(window, "btn_dock_sweep"))

        # Initially idle
        self.assertTrue(window.btn_run.isEnabled())
        self.assertFalse(window.btn_cancel.isEnabled())

        # Update to running state
        window._update_execution_buttons(is_running=True)
        self.assertFalse(window.btn_run.isEnabled())
        self.assertTrue(window.btn_cancel.isEnabled())

        # Update back to idle state
        window._update_execution_buttons(is_running=False)
        self.assertTrue(window.btn_run.isEnabled())
        self.assertFalse(window.btn_cancel.isEnabled())

        window.close()

    def test_foundation_completion_auto_switches_canvas(self):
        """Test that completing a direct cache task switches automatically to Interactive Plots."""
        window = UnifiedWorkbenchWindow()
        window.edit_out_dir.setText(self.root)

        # Start at Plot Viewer (mode 0)
        window.set_canvas_mode(0)
        self.assertEqual(window.central_view_stack.currentIndex(), 0)

        # Flag that a cache was requested
        window._foundation_requested = True

        # Simulate completion payload
        fake_payload = {
            'plot_path': '',
            'data_path': os.path.join(self.cache_dir, 'sigma_base_test.npz'),
            'all_plots': []
        }
        window._on_calc_completed(fake_payload)

        # Should auto-switch to Interactive Plots (mode 1) and reset flag
        self.assertFalse(window._foundation_requested)
        self.assertEqual(window.central_view_stack.currentIndex(), 1)
        self.assertIn('cache ready', window.lbl_status.text().lower())

        window.close()

    def test_run_or_queue_foundation_job(self):
        """Test run_or_queue_foundation_job behavior when idle vs when busy."""
        window = UnifiedWorkbenchWindow()
        window.edit_out_dir.setText(self.root)

        params_1 = {
            "task": "foundation_cache",
            "cache_category": "sigma_base",
            "mu": 0.0,
            "N": 100,
            "solver_choice": "cpu",
            "output_dir": self.root
        }
        params_2 = {
            "task": "foundation_cache",
            "cache_category": "chi0_static",
            "mu": 1.0,
            "N": 64,
            "solver_choice": "cpu",
            "output_dir": self.root
        }

        # Case 1: Engine is busy -> enqueues job
        window.bridge._running = True
        res = window.run_or_queue_foundation_job(params_2)
        self.assertEqual(res, "queued")
        self.assertEqual(len(window.queued_param_list), 1)
        self.assertEqual(window.table_queue.rowCount(), 1)
        self.assertEqual(window.table_queue.item(0, 5).text(), "⏳ Queued")

        # Test cancel all clears the queue
        window.cancel_all_queue()
        self.assertEqual(len(window.queued_param_list), 0)
        self.assertEqual(window.table_queue.item(0, 5).text(), "⏹ Cancelled")

        window.bridge._running = False
        window.close()

    def test_unified_queue_serialization_and_progression(self):
        """Test full multi-job serialization: active running in row 0, subsequent queued in rows 1+, automatic progression upon completion, and clean cancellation."""
        window = UnifiedWorkbenchWindow()
        window.edit_out_dir.setText(self.root)

        # Mock start_calculation to simulate running without launching actual background processes
        started_jobs = []
        def mock_start_calculation(params):
            window.bridge._running = True
            started_jobs.append(params)
        window.bridge.start_calculation = mock_start_calculation

        job1 = {"task": "self_energy", "study": "Spectral Sweep", "mu": 0.0, "N": 64, "solver_choice": "cpu", "output_dir": self.root}
        job2 = {"task": "foundation_cache", "cache_category": "sigma_base", "mu": 0.5, "N": 64, "solver_choice": "cpu", "output_dir": self.root}
        job3 = {"task": "susceptibility", "study": "RPA Susceptibility", "mu": 1.0, "N": 64, "solver_choice": "cpu", "output_dir": self.root}
        job4 = {"task": "phase_diagram", "study": "Phase Diagram", "mu": 1.0, "N": 64, "solver_choice": "cpu", "output_dir": self.root}

        # Step 1: Submit Job 1 while engine is idle -> starts immediately and switches to Console tab (index 1)
        res1 = window.run_or_queue_job(job1, study_name="Spectral Sweep", summary="Sweep 1")
        self.assertEqual(res1, "running")
        self.assertEqual(window.table_queue.rowCount(), 1)
        self.assertEqual(window.active_queue_row, 0)
        self.assertIn("Running", window.table_queue.item(0, 5).text())
        self.assertEqual(window.bottom_tabs.currentIndex(), 1)  # Live Console
        self.assertEqual(len(started_jobs), 1)

        # Step 2: Add Job 2 via add_to_queue style dispatch -> stays on / switches to Queue tab (index 0)
        res2 = window.run_or_queue_foundation_job(job2)
        res3 = window.run_or_queue_job(job3, study_name="RPA Susceptibility", summary="Susc 3")
        res4 = window.run_or_queue_job(job4, study_name="Phase Diagram", summary="PD 4")
        self.assertEqual(res2, "queued")
        self.assertEqual(res3, "queued")
        self.assertEqual(res4, "queued")
        self.assertEqual(window.table_queue.rowCount(), 4)
        self.assertEqual(len(window.queued_param_list), 3)
        self.assertIn("Queued", window.table_queue.item(1, 5).text())
        self.assertIn("Queued", window.table_queue.item(2, 5).text())
        self.assertIn("Queued", window.table_queue.item(3, 5).text())
        self.assertEqual(window.bottom_tabs.currentIndex(), 0)  # Batch Queue Tab
        self.assertEqual(len(started_jobs), 1)

        # Step 3: Test live progress updates active row
        window._on_calc_progress(60, "Solving Dyson equation")
        prog_0 = window.table_queue.cellWidget(0, 4)
        self.assertEqual(prog_0.value(), 60)
        self.assertIn("Solving Dyson equation", window.table_queue.item(0, 5).text())

        # Step 4: Job 1 completes -> marks row 0 as Completed and automatically launches Job 2 in row 1
        window.bridge._running = False
        fake_payload_1 = {"plot_path": "", "data_path": "", "all_plots": []}
        window._on_calc_completed(fake_payload_1)

        self.assertIn("Completed", window.table_queue.item(0, 5).text())
        self.assertEqual(window.table_queue.cellWidget(0, 4).value(), 100)
        self.assertEqual(window.active_queue_row, 1)
        self.assertIn("Running", window.table_queue.item(1, 5).text())
        self.assertEqual(len(window.queued_param_list), 2)
        self.assertEqual(len(started_jobs), 2)

        # Step 5: User cancels active job (Job 2) -> marks row 1 Cancelled and auto-advances to Job 3 in row 2!
        window.cancel_simulation_ui()
        self.assertIn("Cancelled", window.table_queue.item(1, 5).text())
        window.bridge._running = False
        window._on_calc_cancelled()

        # Check that Job 3 was popped and launched
        self.assertEqual(window.active_queue_row, 2)
        self.assertIn("Running", window.table_queue.item(2, 5).text())
        self.assertEqual(len(window.queued_param_list), 1)
        self.assertEqual(len(started_jobs), 3)

        # Step 6: User clicks Cancel All -> halts active Job 3 AND cancels pending Job 4, purges queue!
        window.cancel_all_queue()
        self.assertIn("Cancelled", window.table_queue.item(2, 5).text())
        self.assertIn("Cancelled", window.table_queue.item(3, 5).text())
        self.assertEqual(len(window.queued_param_list), 0)

        # Step 7: Clear finished -> clears all completed/cancelled rows
        window.clear_queue()
        self.assertEqual(window.table_queue.rowCount(), 0)

        window.bridge._running = False
        window.close()


if __name__ == '__main__':
    unittest.main()

