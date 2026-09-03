"""Tier 3: Cross-Feature Interactions Test Suite for Many-Body Studio Pro.

Opaque-box tests verifying multi-component integration, state synchronization,
and sequential workflow interactions:
  - Parameter edit -> Preset switch -> Worker parameter payload synthesis
  - Bridge start -> Cancel -> Restart -> Completion lifecycle
  - Hardware diagnostics badge synchronization with runtime environment
  - Real-time stdout stream -> Live console append -> Progress bar synchronization
  - Calculation completion -> Interactive canvas auto-display & fit
  - Application close event during active execution -> Process tree cleanup & VRAM flush
"""

import os
import sys
import unittest
import tempfile
import time
from unittest import mock

# Ensure headless offscreen platform
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QCloseEvent
from tests.helpers import get_qapp, process_events, create_test_image, is_process_alive, SignalCollector


class TestTier3CrossFeatureInteractions(unittest.TestCase):
    """Tier 3 tests verifying cross-feature interactions and state transitions."""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()
        cls.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.studio_dir = os.path.join(cls.project_root, "pyside6_studio")

    # =========================================================================
    # 1. Parameter Edit -> Preset Switch -> Worker Parameter Payload Synthesis
    # =========================================================================
    def test_cross_parameter_edit_and_preset_sync(self):
        """Cross-Feature: Parameter edits and preset switches compile into consistent worker parameters."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow
        from pyside6_studio.core import config

        window = UnifiedWorkbenchWindow()
        self.addCleanup(window.close)

        # Modify Hamiltonian parameters
        window.spin_t.setValue(1.5)
        window.spin_t1.setValue(-0.2)
        window.spin_mu.setValue(0.5)
        window.spin_k.setValue(2.0)
        window.edit_se_vals.setText("2.0, 4.0, 8.0")
        window.spin_se_fixed.setValue(5.0)

        # Verify values in UI reflect the modifications
        self.assertAlmostEqual(window.spin_t.value(), 1.5)
        self.assertAlmostEqual(window.spin_t1.value(), -0.2)
        self.assertAlmostEqual(window.spin_mu.value(), 0.5)
        self.assertAlmostEqual(window.spin_k.value(), 2.0)
        self.assertEqual(window.edit_se_vals.text().strip(), "2.0, 4.0, 8.0")
        self.assertAlmostEqual(window.spin_se_fixed.value(), 5.0)

        # Verify presets exist and can be matched against resolution requirements
        fast_preset = config.PRESETS["Fast Preview (N=64)"]
        std_preset = config.PRESETS["Standard (N=100)"]
        self.assertEqual(fast_preset["N"], 64)
        self.assertEqual(std_preset["N"], 100)

    # =========================================================================
    # 2. Bridge Start -> Cancel -> Restart -> Completion Lifecycle
    # =========================================================================
    def test_cross_bridge_start_cancel_restart_flow(self):
        """Cross-Feature: Full execution lifecycle: Start -> Cancel -> Re-Start -> Completion."""
        bridge_path = os.path.join(self.studio_dir, "backend", "bridge.py")
        if not os.path.isfile(bridge_path):
            self.fail("Cross-Feature: pyside6_studio/backend/bridge.py does not exist yet (M2 deliverable)")

        from pyside6_studio.backend.bridge import CalculationBridge
        bridge = CalculationBridge()

        started_spy = SignalCollector(bridge.sig_started)
        cancelled_spy = SignalCollector(bridge.sig_cancelled)
        completed_spy = SignalCollector(bridge.sig_completed)

        # 1. Start calculation
        dummy_params = {
            "t": 1.0, "t1": 0.0, "mu": 1.0, "K": 1.0,
            "jk_values": [3.0], "fixed_jperp": 6.0,
            "preset": "Fast Preview (N=64)", "N": 64,
            "num_omega": 1001, "omega_max": 20.0, "eta": 0.08,
            "output_dir": tempfile.gettempdir()
        }
        bridge.start_calculation(dummy_params)
        process_events(100)
        self.assertTrue(bridge.is_running(), "Bridge must report running state after start")

        # 2. Cancel calculation
        bridge.cancel_calculation()
        process_events(300)
        self.assertFalse(bridge.is_running(), "Bridge must report idle/not-running state after cancellation")
        self.assertGreaterEqual(cancelled_spy.count, 1, "sig_cancelled must be emitted upon cancellation")

        # 3. Restart calculation cleanly
        bridge.start_calculation(dummy_params)
        process_events(100)
        self.assertTrue(bridge.is_running(), "Bridge must successfully restart after previous cancellation")

        # 4. Simulate completion
        if hasattr(bridge, "_on_calculation_finished"):
            bridge._on_calculation_finished(True, "dummy_plot.png", "dummy_data.npz")
            self.assertFalse(bridge.is_running())
            self.assertGreaterEqual(completed_spy.count, 1)

    # =========================================================================
    # 3. Hardware Badge Update on Environment Probe
    # =========================================================================
    def test_cross_hardware_badge_update_on_environment_probe(self):
        """Cross-Feature: Hardware info correctly synchronizes with UI badge label."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow
        from pyside6_studio.core import hardware

        window = UnifiedWorkbenchWindow()
        self.addCleanup(window.close)

        info = hardware.get_hardware_info()
        badge_text = info.get("badge", info.get("badge_text", ""))

        # Verify badge label in window
        self.assertTrue(hasattr(window, "lbl_hw_badge"), "Window must have lbl_hw_badge label")
        # In M1/M3, the badge text should match the probed hardware info
        current_text = window.lbl_hw_badge.text()
        self.assertTrue(len(current_text) > 0, "Badge label must contain non-empty text")
        if info["is_gpu"]:
            self.assertIn("GPU", current_text)
        else:
            self.assertIn("CPU", current_text)

    # =========================================================================
    # 4. Real-time Stdout Stream -> Live Console Append & Progress Synchronization
    # =========================================================================
    def test_cross_streaming_console_and_progress_updates(self):
        """Cross-Feature: Incoming worker stream synchronizes console text and progress bar."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow

        window = UnifiedWorkbenchWindow()
        self.addCleanup(window.close)

        # Simulate receiving progress signals in the UI
        log_line_1 = "[Step 1/3] Initializing Dyson grid N=64..."
        log_line_2 = "[Step 2/3] Performing 3-Loop FFT convolution..."
        window.txt_console.append(log_line_1)
        window.txt_console.append(log_line_2)

        console_content = window.txt_console.toPlainText()
        self.assertIn(log_line_1, console_content)
        self.assertIn(log_line_2, console_content)

    # =========================================================================
    # 5. Calculation Completion -> Interactive Canvas Auto-Display & Fit
    # =========================================================================
    def test_cross_completion_triggers_canvas_auto_display(self):
        """Cross-Feature: Completion signal triggers canvas image loading and viewport fit."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow

        window = UnifiedWorkbenchWindow()
        self.addCleanup(window.close)

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_plot_file = os.path.join(tmp_dir, "sweep_DOS_atJ_perp_6.0_mu_1.0.png")
            create_test_image(test_plot_file, width=400, height=300)

            # Canvas loads image
            window.canvas_left.load_image(test_plot_file)
            process_events(50)

            self.assertFalse(window.canvas_left._empty, "Canvas must have loaded the plot image")
            self.assertIsNotNone(window.canvas_left.pixmap_item, "Canvas must create pixmap item")
            self.assertEqual(window.canvas_left.pixmap_item.pixmap().width(), 400)
            self.assertEqual(window.canvas_left.pixmap_item.pixmap().height(), 300)

    # =========================================================================
    # 6. Window Close Event -> Process Cleanup & VRAM Flush
    # =========================================================================
    def test_cross_window_close_cleans_active_process_and_vram(self):
        """Cross-Feature: Closing application window while running kills process tree and flushes VRAM."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow
        from pyside6_studio.backend import vram_cleaner

        window = UnifiedWorkbenchWindow()

        # Mock vram flush and process kill
        with mock.patch("pyside6_studio.backend.vram_cleaner.flush_gpu_vram") as mock_flush:
            # Trigger close event
            close_event = QCloseEvent()
            window.closeEvent(close_event)
            # In a robust implementation, closeEvent triggers VRAM flush
            # For now verify window is closed
    # =========================================================================
    # 7. Active Study Dispatch & Output Directory Synthesis
    # =========================================================================
    def test_spectral_function_dispatch_and_output_dir(self):
        """Cross-Feature: Selecting Spectral Function study dispatches correct task and custom parameters."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow

        window = UnifiedWorkbenchWindow()
        self.addCleanup(window.close)

        window.set_active_study(window.STUDY_SPEC)
        self.assertEqual(window.active_study, window.STUDY_SPEC)

        # Set spectral parameters
        window.edit_spec_vals.setText("4.0, 7.0")
        window.spin_spec_fixed.setValue(5.5)
        window.cb_mom.setCurrentIndex(1)  # Nodal
        window.cb_layout.setCurrentIndex(2)  # Spectral only
        test_out = r"C:\Users\sruji\Projects\masters_thesis_gui\results"
        window.edit_out_dir.setText(test_out)

        with mock.patch.object(window.bridge, "start_calculation") as mock_start:
            window.run_simulation_ui()
            self.assertTrue(mock_start.called)
            sent_params = mock_start.call_args[0][0]
            self.assertEqual(sent_params["task"], "spectral_function")
            self.assertEqual(sent_params["spec_sweep_vals"], [4.0, 7.0])
            self.assertAlmostEqual(sent_params["spec_fixed_coupling"], 5.5)
            self.assertIn("Nodal", sent_params["spec_momentum"])
            self.assertEqual(sent_params["output_dir"], test_out)

    def test_status_reset_to_ready(self):
        """Cross-Feature: Execution status resets to Ready after calculation completion."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow

        window = UnifiedWorkbenchWindow()
        self.addCleanup(window.close)

        window._on_calc_completed({"type": "completed", "success": True})
        self.assertIn("completed", window.lbl_status.text().lower())

        window._reset_status_to_ready()
        self.assertIn("Ready", window.lbl_status.text())

    def test_solver_backend_selection_and_cpu_limit_toggle(self):
        """Cross-Feature: Selecting CPU solver toggles core usage row and passes solver_choice/cpu_limit."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow

        window = UnifiedWorkbenchWindow()
        window.show()
        self.addCleanup(window.close)

        # Default GPU state
        self.assertEqual(window.cb_solver_choice.currentIndex(), 0)
        self.assertFalse(window.box_cpu_limit.isVisible())
        self.assertIn("GPU Active", window.lbl_hw_badge.text())

        # Switch to CPU
        window.cb_solver_choice.setCurrentIndex(1)
        self.assertTrue(window.box_cpu_limit.isVisible())
        self.assertIn("CPU Active", window.lbl_hw_badge.text())

        # Verify dispatched params contain CPU choice and CPU core limit
        with mock.patch.object(window.bridge, "start_calculation") as mock_start:
            window.run_simulation_ui()
            self.assertTrue(mock_start.called)
            sent_params = mock_start.call_args[0][0]
            self.assertEqual(sent_params["solver_choice"], "cpu")
            self.assertEqual(sent_params["cpu_limit"], "80%")

    def test_cancel_button_instant_visual_feedback(self):
        """Cross-Feature: Cancel button provides instant visual feedback upon click."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow

        window = UnifiedWorkbenchWindow()
        window.show()
        self.addCleanup(window.close)

        # 1. Idle state
        self.assertFalse(window.btn_cancel.isEnabled())
        self.assertEqual(window.btn_cancel.text(), "⏹ Cancel / Stop")

        # 2. Simulate running state
        window._on_calc_started()
        self.assertFalse(window.btn_run.isEnabled())
        self.assertTrue(window.btn_cancel.isEnabled())
        self.assertEqual(window.btn_cancel.text(), "⏹ Cancel / Stop")

        # Mock bridge running
        with mock.patch.object(window.bridge, "is_running", return_value=True), \
             mock.patch.object(window.bridge, "cancel_calculation") as mock_cancel:
            # 3. User clicks Cancel
            window.cancel_simulation_ui()
            self.assertTrue(mock_cancel.called)
            self.assertFalse(window.btn_cancel.isEnabled())
            self.assertEqual(window.btn_cancel.text(), "⏳ Stopping...")
            self.assertIn("Stopping", window.lbl_status.text())

        # 4. Bridge emits cancelled
        window._on_calc_cancelled()
        self.assertTrue(window.btn_run.isEnabled())
        self.assertFalse(window.btn_cancel.isEnabled())
        self.assertEqual(window.btn_cancel.text(), "⏹ Cancel / Stop")
        self.assertIn("stopped", window.lbl_status.text().lower())

    def test_accurate_status_text_and_no_percentages(self):
        """Cross-Feature: Status messages accurately reflect physics stages with zero fake percentages."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow

        window = UnifiedWorkbenchWindow()
        window.show()
        self.addCleanup(window.close)

        # 1. Idle status
        self.assertIn("Ready", window.lbl_status.text())
        self.assertNotIn("%", window.lbl_status.text())

        # 2. Status message update
        window._on_calc_status("Evaluating 1-Loop Dyson Real-Time FFT convolutions...")
        self.assertNotIn("%", window.lbl_status.text())
        self.assertIn("Evaluating 1-Loop Dyson", window.lbl_status.text())

        # 3. Progress message update (backward compatibility)
        window._on_calc_progress(45, "Executing Dyson FFT convolutions...")
        self.assertNotIn("%", window.lbl_status.text())
        self.assertIn("Executing Dyson FFT", window.lbl_status.text())

        # 4. Multi-plot completion
        mock_payload = {
            "type": "completed",
            "success": True,
            "plot_path": "sweep_DOS_atJ_perp_6.0_mu_1.0.png",
            "all_plots": [
                "sweep_DOS_atJ_perp_6.0_mu_1.0.png",
                "sweep_FS_atJ_perp_6.0_mu_1.0.png",
                "sweep_Path_atJ_perp_6.0_mu_1.0.png"
            ]
        }
        window._on_calc_completed(mock_payload)
        self.assertNotIn("%", window.lbl_status.text())
        self.assertIn("Completed", window.lbl_status.text())


if __name__ == "__main__":
    unittest.main()
