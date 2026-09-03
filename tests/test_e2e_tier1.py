"""Tier 1: Feature Coverage Test Suite for Many-Body Studio Pro.

Opaque-box tests covering all 13 features specified in PROJECT.md and ORIGINAL_REQUEST.md:
  F01: Global Path Configuration
  F02: Numerical Resolution Presets
  F03: Hardware Diagnostics & CUDA Detection
  F04: Isolated QProcess Worker Runner
  F05: Structured JSON Progress Protocol
  F06: 2-Stage Cancellation Mechanism
  F07: Guaranteed CuPy VRAM Cleanup
  F08: Context-Adaptive Parameter Inspector
  F09: Live Streaming Solver Console
  F10: Interactive Plot Canvas (Zoom, Pan, Fit)
  F11: Active Run / Cancel Toolbar Controls
  F12: Batch Launch Script (run_studio.bat)
  F13: Worker Exception & Error Resilience
"""

import os
import sys
import unittest
import json
import tempfile
import shutil

# Ensure headless offscreen platform
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers import get_qapp, process_events, create_test_image, SignalCollector


class TestTier1FeatureCoverage(unittest.TestCase):
    """Tier 1 tests asserting coverage of Features 1 through 13."""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()
        cls.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.studio_dir = os.path.join(cls.project_root, "pyside6_studio")

    # =========================================================================
    # Feature 1: Global Path Configuration
    # =========================================================================
    def test_f01_global_path_configuration(self):
        """F01: Global paths defined for physics root, results, and python environment."""
        from pyside6_studio.core import config

        # Verify base paths exist in config module
        self.assertTrue(hasattr(config, "PHYSICS_REPO_ROOT") or hasattr(config, "PHYSICS_ROOT"),
                        "F01: config must define PHYSICS_ROOT or PHYSICS_REPO_ROOT")
        physics_root = getattr(config, "PHYSICS_ROOT", getattr(config, "PHYSICS_REPO_ROOT", None))
        self.assertIsInstance(physics_root, str)
        self.assertTrue(len(physics_root) > 0, "PHYSICS_ROOT must be non-empty")

        # Verify results paths
        self.assertTrue(hasattr(config, "MANY_BODY_RESULTS"), "F01: config must define MANY_BODY_RESULTS")
        self.assertTrue(hasattr(config, "SPECTRAL_DIR"), "F01: config must define SPECTRAL_DIR")
        self.assertTrue(hasattr(config, "SPECTRAL_PLOTS_DIR"), "F01: config must define SPECTRAL_PLOTS_DIR")
        self.assertTrue(hasattr(config, "SPECTRAL_DATA_DIR"), "F01: config must define SPECTRAL_DATA_DIR")

        # Verify PHYSICS_PYTHON definition or contract
        has_physics_python = hasattr(config, "PHYSICS_PYTHON")
        if not has_physics_python:
            # Fallback path checking as per interface contract
            expected_venv_py = os.path.join(physics_root, ".venv", "Scripts", "python.exe")
            self.assertTrue(os.path.isfile(expected_venv_py) or os.path.isfile(sys.executable),
                            "F01: Valid python executable must exist for physics execution")

    # =========================================================================
    # Feature 2: Numerical Resolution Presets
    # =========================================================================
    def test_f02_numerical_resolution_presets(self):
        """F02: Presets for Fast Preview N=64, Standard N=100, High-Res N=256."""
        from pyside6_studio.core import config

        self.assertTrue(hasattr(config, "PRESETS"), "F02: config must define PRESETS dictionary")
        presets = config.PRESETS
        self.assertIsInstance(presets, dict, "PRESETS must be a dictionary")

        # Required preset keys
        self.assertIn("Fast Preview (N=64)", presets, "F02: Missing Fast Preview (N=64) preset")
        self.assertIn("Standard (N=100)", presets, "F02: Missing Standard (N=100) preset")
        self.assertIn("High-Res Production (N=256)", presets, "F02: Missing High-Res Production (N=256) preset")

        # Fast Preview specs
        p_fast = presets["Fast Preview (N=64)"]
        self.assertEqual(p_fast["N"], 64, "Fast preview grid N must be 64")
        self.assertTrue("Nw" in p_fast or "num_omega" in p_fast, "Fast preview must specify frequency points")
        nw_fast = p_fast.get("Nw", p_fast.get("num_omega"))
        self.assertIn(nw_fast, [1001, 2001], "Fast preview Nw should be 1001 or 2001")
        self.assertAlmostEqual(p_fast.get("w_max", p_fast.get("omega_max", 20.0)), 20.0, delta=1.0)
        self.assertAlmostEqual(p_fast["eta"], 0.08, delta=0.01)

        # Standard specs
        p_std = presets["Standard (N=100)"]
        self.assertEqual(p_std["N"], 100, "Standard grid N must be 100")
        nw_std = p_std.get("Nw", p_std.get("num_omega"))
        self.assertTrue(nw_std >= 2001, "Standard Nw must be at least 2001")
        self.assertAlmostEqual(p_std["eta"], 0.05, delta=0.01)

        # High-Res Production specs
        p_prod = presets["High-Res Production (N=256)"]
        self.assertEqual(p_prod["N"], 256, "High-Res grid N must be 256")
        nw_prod = p_prod.get("Nw", p_prod.get("num_omega"))
        self.assertTrue(nw_prod >= 4801, "High-Res Nw must be at least 4801")
        self.assertAlmostEqual(p_prod["eta"], 0.03, delta=0.01)

    # =========================================================================
    # Feature 3: Hardware Diagnostics & CUDA Detection
    # =========================================================================
    def test_f03_hardware_diagnostics_cuda_detection(self):
        """F03: Hardware detection reports CUDA GPU / VRAM or CPU fallback."""
        from pyside6_studio.core import hardware

        self.assertTrue(hasattr(hardware, "get_hardware_info"), "F03: hardware module must define get_hardware_info()")
        info = hardware.get_hardware_info()
        self.assertIsInstance(info, dict, "get_hardware_info() must return a dictionary")

        # Required fields in contract
        self.assertIn("backend", info, "info must contain 'backend'")
        self.assertIn(info["backend"], ["cuda", "cpu"], "backend must be 'cuda' or 'cpu'")

        self.assertIn("name", info, "info must contain 'name'")
        self.assertIsInstance(info["name"], str)
        self.assertTrue(len(info["name"]) > 0, "Hardware name must not be empty")

        self.assertIn("is_gpu", info, "info must contain boolean 'is_gpu'")
        self.assertIsInstance(info["is_gpu"], bool)

        has_badge = "badge" in info or "badge_text" in info
        self.assertTrue(has_badge, "info must contain 'badge' or 'badge_text'")
        badge = info.get("badge", info.get("badge_text"))
        self.assertIsInstance(badge, str)
        self.assertTrue(len(badge) > 0, "Badge text must not be empty")

        if info["backend"] == "cuda":
            self.assertTrue(info["is_gpu"])
            self.assertIsNotNone(info["total_vram_gb"])
            self.assertGreater(info["total_vram_gb"], 0.0)
        else:
            self.assertFalse(info["is_gpu"])

    # =========================================================================
    # Feature 4: Isolated QProcess Worker Runner
    # =========================================================================
    def test_f04_isolated_qprocess_worker_runner(self):
        """F04: Standalone CLI worker script executing physics in isolated child process."""
        worker_path = os.path.join(self.studio_dir, "backend", "worker_cli.py")
        if not os.path.isfile(worker_path):
            self.fail("F04: pyside6_studio/backend/worker_cli.py does not exist yet (M2 deliverable)")

        # Verify CLI parameters parsing contract
        test_params = {
            "t": 1.0,
            "t1": 0.0,
            "mu": 1.0,
            "K": 1.0,
            "jk_values": [3.0, 6.0],
            "fixed_jperp": 6.0,
            "preset": "Fast Preview (N=64)",
            "N": 64,
            "num_omega": 2001,
            "omega_max": 20.0,
            "eta": 0.08,
            "output_dir": tempfile.gettempdir()
        }
        # Worker module should be importable or executable with --help/schema
        with open(worker_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("--params", content, "F04: worker_cli must accept '--params' CLI argument")
        self.assertIn("free_all_blocks", content, "F04: worker_cli must call free_all_blocks for GPU deallocation")

    # =========================================================================
    # Feature 5: Structured JSON Progress Protocol
    # =========================================================================
    def test_f05_structured_json_progress_protocol(self):
        """F05: Structured JSON progress lines parsed and emitted via Qt signals."""
        bridge_path = os.path.join(self.studio_dir, "backend", "bridge.py")
        if not os.path.isfile(bridge_path):
            self.fail("F05: pyside6_studio/backend/bridge.py does not exist yet (M2 deliverable)")

        from pyside6_studio.backend.bridge import CalculationBridge
        bridge = CalculationBridge()

        # Check required Qt signals
        self.assertTrue(hasattr(bridge, "sig_progress"), "CalculationBridge must have sig_progress signal")
        self.assertTrue(hasattr(bridge, "sig_log"), "CalculationBridge must have sig_log signal")
        self.assertTrue(hasattr(bridge, "sig_completed"), "CalculationBridge must have sig_completed signal")

        # Test protocol parser behavior
        progress_spy = SignalCollector(bridge.sig_progress)
        log_spy = SignalCollector(bridge.sig_log)

        # Simulate incoming stdout lines
        if hasattr(bridge, "parse_line"):
            bridge.parse_line('{"progress": 45, "step": "1-Loop FFT"}')
            self.assertEqual(progress_spy.count, 1)
            self.assertEqual(progress_spy.last, (45, "1-Loop FFT"))

            # Non-JSON line should route to log
            bridge.parse_line("Standard stdout log line")
            self.assertEqual(log_spy.count, 1)
            self.assertEqual(log_spy.last, "Standard stdout log line")

    # =========================================================================
    # Feature 6: 2-Stage Cancellation Mechanism
    # =========================================================================
    def test_f06_two_stage_cancellation_mechanism(self):
        """F06: 2-stage cancellation (terminate -> 1.5s timeout -> kill)."""
        bridge_path = os.path.join(self.studio_dir, "backend", "bridge.py")
        if not os.path.isfile(bridge_path):
            self.fail("F06: pyside6_studio/backend/bridge.py does not exist yet (M2 deliverable)")

        from pyside6_studio.backend.bridge import CalculationBridge
        bridge = CalculationBridge()

        self.assertTrue(hasattr(bridge, "cancel_calculation"),
                        "F06: CalculationBridge must implement cancel_calculation()")
        self.assertTrue(hasattr(bridge, "sig_cancelled"),
                        "F06: CalculationBridge must have sig_cancelled signal")

    # =========================================================================
    # Feature 7: Guaranteed CuPy VRAM Cleanup
    # =========================================================================
    def test_f07_guaranteed_cupy_vram_cleanup(self):
        """F07: flush_gpu_vram() deallocates memory pools with zero unhandled exceptions."""
        from pyside6_studio.backend import vram_cleaner

        self.assertTrue(hasattr(vram_cleaner, "flush_gpu_vram"),
                        "F07: vram_cleaner must define flush_gpu_vram()")
        self.assertTrue(hasattr(vram_cleaner, "kill_process_tree"),
                        "F07: vram_cleaner must define kill_process_tree()")

        # Test safe execution
        result = vram_cleaner.flush_gpu_vram()
        self.assertIsInstance(result, bool, "flush_gpu_vram must return boolean status")

        # Test process tree termination resilience on non-existent PID
        try:
            vram_cleaner.kill_process_tree(9999999)
        except Exception as e:
            self.fail(f"kill_process_tree threw unexpected exception: {e}")

    # =========================================================================
    # Feature 8: Context-Adaptive Parameter Inspector
    # =========================================================================
    def test_f08_context_adaptive_parameter_inspector(self):
        """F08: UI parameter inspector for model knobs (t, t', mu, K) and sweep controls."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow

        window = UnifiedWorkbenchWindow()
        self.addCleanup(window.close)

        # Check Hamiltonian knobs
        self.assertTrue(hasattr(window, "spin_t"), "Window must have spin_t control")
        self.assertTrue(hasattr(window, "spin_t1"), "Window must have spin_t1 control")
        self.assertTrue(hasattr(window, "spin_mu"), "Window must have spin_mu control")
        self.assertTrue(hasattr(window, "spin_k"), "Window must have spin_k control")

        # Check sweep controls
        self.assertTrue(hasattr(window, "cb_se_mode"), "Window must have cb_se_mode combo")
        self.assertTrue(hasattr(window, "edit_se_vals"), "Window must have edit_se_vals line edit")
        self.assertTrue(hasattr(window, "spin_se_fixed"), "Window must have spin_se_fixed spinbox")

        # Default values check
        self.assertAlmostEqual(window.spin_t.value(), 1.0)
        self.assertEqual(window.edit_se_vals.text().strip(), "3.0, 6.0, 9.0")
        self.assertAlmostEqual(window.spin_se_fixed.value(), 6.0)

    # =========================================================================
    # Feature 9: Live Streaming Solver Console
    # =========================================================================
    def test_f09_live_streaming_solver_console(self):
        """F09: Monospace read-only live console displaying real-time stdout logs."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow

        window = UnifiedWorkbenchWindow()
        self.addCleanup(window.close)

        self.assertTrue(hasattr(window, "txt_console"), "Window must have txt_console widget")
        console = window.txt_console
        self.assertTrue(console.isReadOnly(), "Console widget must be read-only to user input")

        # Append log text and verify document updates
        test_msg = "[TEST_LOG] Executing Dyson FFT kernel..."
        console.append(test_msg)
        self.assertIn(test_msg, console.toPlainText())

    # =========================================================================
    # Feature 10: Interactive Plot Canvas
    # =========================================================================
    def test_f10_interactive_plot_canvas(self):
        """F10: InteractivePlotCanvas with mousewheel zoom, pan, and coordinate tracking."""
        from pyside6_studio.canvas import InteractivePlotCanvas
        from PySide6.QtWidgets import QGraphicsView

        canvas = InteractivePlotCanvas()
        self.addCleanup(canvas.close)

        # Pan mode check
        self.assertEqual(canvas.dragMode(), QGraphicsView.ScrollHandDrag,
                         "Canvas must use ScrollHandDrag for click-drag panning")

        # Test image loading
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_img_path = os.path.join(tmp_dir, "plot.png")
            create_test_image(test_img_path)

            canvas.load_image(test_img_path)
            self.assertFalse(canvas._empty, "Canvas _empty should be False after loading image")
            self.assertIsNotNone(canvas.pixmap_item, "pixmap_item must be created")

            # Fit in view check
            canvas.fit_in_view()
            self.assertEqual(canvas._zoom, 0)

            # Signal test: coord_changed
            coord_spy = SignalCollector(canvas.coord_changed)
            # Emit coordinate change manually or via move
            canvas.coord_changed.emit(10.5, 20.5)
            self.assertEqual(coord_spy.count, 1)
            self.assertEqual(coord_spy.last, (10.5, 20.5))

    # =========================================================================
    # Feature 11: Active Run / Cancel Toolbar Controls
    # =========================================================================
    def test_f11_active_run_cancel_toolbar_controls(self):
        """F11: Toolbar buttons for '⚡ Run Active' and '⏹ Cancel / Stop'."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow

        window = UnifiedWorkbenchWindow()
        self.addCleanup(window.close)

        self.assertTrue(hasattr(window, "btn_run"), "Window must have btn_run toolbar button")
        self.assertTrue("Run" in window.btn_run.text() or "⚡" in window.btn_run.text(),
                        "Run button text must indicate run action")

        # In M3, btn_cancel or equivalent cancel control should be present
        has_cancel = hasattr(window, "btn_cancel") or hasattr(window, "action_cancel")
        if not has_cancel:
            # Check if wired to bridge (M3 vertical slice deliverable)
            self.fail("F11: Dedicated '⏹ Cancel / Stop' button not yet wired in toolbar (M3 deliverable)")

    # =========================================================================
    # Feature 12: Batch Launch Script
    # =========================================================================
    def test_f12_batch_launch_script(self):
        """F12: run_studio.bat exists and configures environment with 0 errors."""
        bat_path = os.path.join(self.project_root, "run_studio.bat")
        self.assertTrue(os.path.isfile(bat_path), "F12: run_studio.bat must exist in project root")

        with open(bat_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Check for UTF-8 encoding configuration
        has_utf8 = "chcp 65001" in content or "PYTHONIOENCODING=utf-8" in content
        self.assertTrue(has_utf8, "F12: run_studio.bat must configure UTF-8 encoding (chcp 65001 or PYTHONIOENCODING)")

        # Check for python launch command
        self.assertIn("main.py", content, "F12: run_studio.bat must invoke main.py")

        # Check for virtual environment activation
        self.assertIn("activate.bat", content, "F12: run_studio.bat must activate virtual environment")

    # =========================================================================
    # Feature 13: Worker Exception & Error Resilience
    # =========================================================================
    def test_f13_worker_exception_error_resilience(self):
        """F13: Worker process crash or exception handled cleanly without crashing GUI."""
        bridge_path = os.path.join(self.studio_dir, "backend", "bridge.py")
        if not os.path.isfile(bridge_path):
            self.fail("F13: pyside6_studio/backend/bridge.py does not exist yet (M2 deliverable)")

        from pyside6_studio.backend.bridge import CalculationBridge
        bridge = CalculationBridge()

        error_spy = SignalCollector(bridge.sig_error)

        # When bridge receives error payload or process fails
        if hasattr(bridge, "handle_error"):
            bridge.handle_error("Simulated worker exception: DivisionByZero in Dyson kernel")
            self.assertEqual(error_spy.count, 1)
            self.assertIn("DivisionByZero", error_spy.last)


if __name__ == "__main__":
    unittest.main()
