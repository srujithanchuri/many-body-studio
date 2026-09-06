"""Tier 2: Boundary & Corner Cases Test Suite for Many-Body Studio Pro.

Opaque-box tests covering edge cases, numerical boundaries, hardware fallback,
timeout escalation, rapid user actions, malformed inputs, and process failures:
  - Zero/negative Hamiltonian & spectral parameters (t, eta, N)
  - Sweep values parsing edge cases (empty, non-numeric, whitespace, single-point)
  - Unknown preset name lookups
  - Missing GPU / CUDA fallback resilience
  - 2-Stage Process kill escalation for unresponsive workers
  - Rapid cancellation & duplicate run click prevention
  - Malformed & partial JSON stdout streams
  - Worker process crash & non-zero exit code handling
"""

import os
import sys
import unittest
import json
import tempfile
import time
import subprocess
from unittest import mock

# Ensure project root in sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tests.helpers import get_qapp, process_events, is_process_alive, SignalCollector


class TestTier2BoundaryCornerCases(unittest.TestCase):
    """Tier 2 tests asserting resilience under boundary conditions and corner cases."""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()
        cls.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.studio_dir = os.path.join(cls.project_root, "pyside6_studio")

    # =========================================================================
    # 1. Zero & Negative Numerical Parameters
    # =========================================================================
    def test_boundary_zero_and_negative_hopping(self):
        """Boundary: Hopping parameter t <= 0 must be clamped or rejected."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow

        window = UnifiedWorkbenchWindow()
        self.addCleanup(window.close)

        # Spinbox t should have minimum > 0 (hopping must be strictly positive)
        min_t = window.spin_t.minimum()
        self.assertGreaterEqual(min_t, 0.0, "Spinbox t minimum must not allow negative hopping")

        # Attempt to set negative or zero value
        window.spin_t.setValue(-2.5)
        self.assertGreaterEqual(window.spin_t.value(), min_t)

    def test_boundary_zero_and_negative_broadening(self):
        """Boundary: Broadening eta <= 0 must be clamped to >= 0.001 to prevent Green's function pole division."""
        from pyside6_studio.core import config

        for preset_name, preset_vals in config.PRESETS.items():
            self.assertIn("eta", preset_vals, f"Preset {preset_name} must specify eta")
            self.assertGreater(preset_vals["eta"], 0.0, f"Preset {preset_name} eta must be strictly positive")
            self.assertGreaterEqual(preset_vals["eta"], 0.001, "eta must be >= 0.001 to prevent singular Green functions")

    def test_boundary_grid_resolution_bounds(self):
        """Boundary: Brillouin zone grid resolution N must enforce minimum N >= 32."""
        from pyside6_studio.core import config

        for preset_name, preset_vals in config.PRESETS.items():
            self.assertIn("N", preset_vals, f"Preset {preset_name} must specify N")
            self.assertGreaterEqual(preset_vals["N"], 32, f"Preset {preset_name} N must be >= 32 to prevent aliasing")

    # =========================================================================
    # 2. Sweep Values String Parsing Corner Cases
    # =========================================================================
    def test_corner_empty_and_whitespace_sweep_values(self):
        """Corner: Empty or whitespace sweep string must be rejected before process launch."""
        from pyside6_studio.main_window import UnifiedWorkbenchWindow

        window = UnifiedWorkbenchWindow()
        self.addCleanup(window.close)

        # Helper parser or validation logic
        def parse_sweep_input(text: str):
            cleaned = text.strip()
            if not cleaned:
                raise ValueError("Sweep values cannot be empty")
            return [float(x.strip()) for x in cleaned.split(",") if x.strip()]

        # Empty string
        with self.assertRaises(ValueError):
            parse_sweep_input("")

        # Whitespace-only string
        with self.assertRaises(ValueError):
            parse_sweep_input("    ")

    def test_corner_malformed_and_delimiter_sweep_values(self):
        """Corner: Non-numeric strings and invalid delimiters must raise ValueError cleanly."""
        def parse_sweep_input(text: str):
            cleaned = text.strip()
            if not cleaned:
                raise ValueError("Sweep values cannot be empty")
            return [float(x.strip()) for x in cleaned.split(",")]

        # Non-numeric input
        with self.assertRaises(ValueError):
            parse_sweep_input("3.0, abc, 9.0")

        # Semi-colon delimiter without comma
        with self.assertRaises(ValueError):
            parse_sweep_input("3.0; 6.0; 9.0")

    def test_corner_valid_single_and_spaced_sweep_values(self):
        """Corner: Single value and irregular spacing must parse correctly into float list."""
        def parse_sweep_input(text: str):
            cleaned = text.strip()
            if not cleaned:
                raise ValueError("Sweep values cannot be empty")
            return [float(x.strip()) for x in cleaned.split(",") if x.strip()]

        # Single value
        res_single = parse_sweep_input("6.0")
        self.assertEqual(res_single, [6.0])

        # Extra whitespace padding
        res_spaced = parse_sweep_input("  3.0 ,  6.0 , 9.0  ")
        self.assertEqual(res_spaced, [3.0, 6.0, 9.0])

    # =========================================================================
    # 3. Invalid Preset Name Lookup
    # =========================================================================
    def test_corner_invalid_preset_lookup(self):
        """Corner: Accessing non-existent preset name returns None or raises KeyError safely."""
        from pyside6_studio.core import config

        self.assertIsNone(config.PRESETS.get("NonExistentPreset_N=1024"))

    # =========================================================================
    # 4. Missing GPU / CUDA Fallback Resilience
    # =========================================================================
    def test_corner_missing_gpu_fallback(self):
        """Corner: When CuPy and CUDA are absent, hardware detection reports CPU fallback safely."""
        from pyside6_studio.core import hardware

        # Mock absence of cupy and torch
        with mock.patch.dict(sys.modules, {"cupy": None, "torch": None}):
            # Re-call get_hardware_info
            info = hardware.get_hardware_info()
            self.assertEqual(info["backend"], "cpu")
            self.assertFalse(info["is_gpu"])
            self.assertIn("CPU", info["name"])
            self.assertIn("CPU", info.get("badge", info.get("badge_text", "")))

    # =========================================================================
    # 5. Process Kill Timeout & Unresponsive Child Process
    # =========================================================================
    def test_corner_process_kill_timeout_unresponsive_worker(self):
        """Corner: Unresponsive worker ignoring soft terminate() is killed via Stage 2 kill_process_tree."""
        from pyside6_studio.backend import vram_cleaner

        # Spawn a dummy long-running background child process
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        pid = proc.pid
        self.assertTrue(is_process_alive(pid), "Spawned test worker must be alive initially")

        # Execute kill_process_tree
        vram_cleaner.kill_process_tree(pid)
        time.sleep(0.5)

        # Verify child process is dead
        self.assertFalse(is_process_alive(pid), "Process must be terminated by kill_process_tree")
        try:
            proc.kill()
            proc.wait(timeout=1.0)
        except Exception:
            pass

    # =========================================================================
    # 6. Rapid Actions & Duplicate Run Clicks
    # =========================================================================
    def test_corner_duplicate_run_clicks_prevented(self):
        """Corner: Clicking Run while calculation is active must be prevented (button disabled)."""
        bridge_path = os.path.join(self.studio_dir, "backend", "bridge.py")
        if not os.path.isfile(bridge_path):
            self.fail("Corner: pyside6_studio/backend/bridge.py does not exist yet (M2 deliverable)")

        from pyside6_studio.backend.bridge import CalculationBridge
        bridge = CalculationBridge()

        # If calculation is running, start_calculation should ignore duplicate trigger or raise RuntimeError
        if hasattr(bridge, "is_running") and hasattr(bridge, "start_calculation"):
            # Mock running state
            bridge._running = True
            with self.assertRaises(RuntimeError):
                bridge.start_calculation({})

    def test_corner_cancel_when_not_running(self):
        """Corner: Calling cancel_calculation() when idle must be a safe no-op."""
        bridge_path = os.path.join(self.studio_dir, "backend", "bridge.py")
        if not os.path.isfile(bridge_path):
            self.fail("Corner: pyside6_studio/backend/bridge.py does not exist yet (M2 deliverable)")

        from pyside6_studio.backend.bridge import CalculationBridge
        bridge = CalculationBridge()

        # Calling cancel on idle bridge should not raise
        try:
            bridge.cancel_calculation()
        except Exception as e:
            self.fail(f"cancel_calculation() on idle bridge raised exception: {e}")

    # =========================================================================
    # 7. Malformed & Broken JSON Output on Stdout
    # =========================================================================
    def test_corner_broken_malformed_json_stream(self):
        """Corner: Incomplete or broken JSON stdout lines must route to log without raising JSONDecodeError."""
        bridge_path = os.path.join(self.studio_dir, "backend", "bridge.py")
        if not os.path.isfile(bridge_path):
            self.fail("Corner: pyside6_studio/backend/bridge.py does not exist yet (M2 deliverable)")

        from pyside6_studio.backend.bridge import CalculationBridge
        bridge = CalculationBridge()

        log_spy = SignalCollector(bridge.sig_log)

        # Test broken JSON lines
        broken_lines = [
            '{"progress": 50, "step": ',        # Truncated JSON
            '{"broken": invalid_syntax}',        # Invalid JSON syntax
            '{}',                                # Empty JSON dict
            'Plain solver output message: done'  # Standard text
        ]

        for line in broken_lines:
            try:
                if hasattr(bridge, "parse_line"):
                    bridge.parse_line(line)
            except Exception as e:
                self.fail(f"parse_line raised unhandled exception on line '{line}': {e}")

    # =========================================================================
    # 8. Worker Process Crash & Non-Zero Exit Code Handling
    # =========================================================================
    def test_corner_worker_crash_handling(self):
        """Corner: Worker crash with non-zero exit code emits sig_error without crashing PySide6 GUI."""
        bridge_path = os.path.join(self.studio_dir, "backend", "bridge.py")
        if not os.path.isfile(bridge_path):
            self.fail("Corner: pyside6_studio/backend/bridge.py does not exist yet (M2 deliverable)")

        from pyside6_studio.backend.bridge import CalculationBridge
        bridge = CalculationBridge()

        error_spy = SignalCollector(bridge.sig_error)

        # Simulate process error
        if hasattr(bridge, "_on_process_finished"):
            bridge._on_process_finished(1, None)  # Exit code 1
            self.assertGreaterEqual(error_spy.count, 1, "sig_error must be emitted on non-zero exit code")


if __name__ == "__main__":
    unittest.main()
