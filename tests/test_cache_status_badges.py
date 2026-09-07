"""Automated unit test suite for Unified Physics Cache Status Badges.

Verifies:
1. No emojis in any badge text string across all studies and states.
2. Self-energy studies (Spectral Sweep, Conductivity) in J_K and J_perp modes.
3. Point self-energy (Quasiparticle Spectral Function).
4. Bare susceptibility (Phase Diagram & RPA Susceptibility), including static vs dynamic edge cases.
5. Force Recompute styling and text.
"""

import os
import sys
import tempfile
import unittest
import numpy as np

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TEST_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication
from pyside6_studio.core.cache_manager import (
    normalize_results_dir,
    check_cache_status,
    get_sigma_base_filename,
    get_chi0_static_filename,
    get_chi0_dynamic_filename
)
from pyside6_studio.main_window import UnifiedWorkbenchWindow


class TestCacheStatusBadges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        self.res_dir, self.plots_dir, self.data_dir, self.cache_dir = normalize_results_dir(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_mock_sigma_file(self, jperp=6.0, mu=1.0, N=64, ext_P=None):
        fn = get_sigma_base_filename(fixed_jperp=jperp, mu=mu, N=N, ext_P=ext_P)
        path = os.path.join(self.cache_dir, fn)
        np.savez_compressed(path, is_ibz=True, is_bitgroomed=True, is_shuffled=True, shape=(2001, 100))
        return path

    def _create_mock_chi0_file(self, dynamic=False, mu=1.0, N=64):
        fn = get_chi0_dynamic_filename(N=N, mu=mu) if dynamic else get_chi0_static_filename(N=N, mu=mu)
        path = os.path.join(self.cache_dir, fn)
        np.savez_compressed(path, chi0=np.zeros((10, 10)))
        return path

    def test_spectral_sweep_jk_mode(self):
        """Spectral Sweep in J_K mode: checks Base Self-Energy."""
        params = {"sweep_mode": "Kondo Coupling (J_K)", "fixed_jperp": 6.0, "mu": 1.0, "N": 64}
        
        # Cold state
        st = check_cache_status("spectral_sweep", params, self.root)
        self.assertEqual(st["state"], "cold")
        self.assertEqual(st["badge_text"], "Base Self-Energy (Σ) Not Cached")
        self.assertNotIn("⚡", st["badge_text"])
        self.assertNotIn("⚙️", st["badge_text"])

        # Cached state
        self._create_mock_sigma_file(jperp=6.0, mu=1.0, N=64)
        st = check_cache_status("spectral_sweep", params, self.root)
        self.assertEqual(st["state"], "cached")
        self.assertEqual(st["badge_text"], "Base Self-Energy (Σ) Cached")
        self.assertNotIn("⚡", st["badge_text"])

    def test_spectral_sweep_jperp_mode_partial_and_full(self):
        """Spectral Sweep in J_perp mode: checks multi-point caching."""
        params = {
            "sweep_mode": "Interlayer Coupling (J_perp)",
            "jk_values": "2.0, 4.0, 6.0, 8.0",
            "mu": 1.0,
            "N": 64
        }
        # 0 of 4 cached -> cold
        st = check_cache_status("spectral_sweep", params, self.root)
        self.assertEqual(st["state"], "cold")
        self.assertEqual(st["badge_text"], "Base Self-Energy (Σ) Not Cached")

        # 2 of 4 cached -> partial
        self._create_mock_sigma_file(jperp=2.0, mu=1.0, N=64)
        self._create_mock_sigma_file(jperp=6.0, mu=1.0, N=64)
        st = check_cache_status("spectral_sweep", params, self.root)
        self.assertEqual(st["state"], "partial")
        self.assertEqual(st["badge_text"], "Partial Self-Energy (Σ) Cached (2 of 4 Points)")

        # All 4 cached -> cached
        self._create_mock_sigma_file(jperp=4.0, mu=1.0, N=64)
        self._create_mock_sigma_file(jperp=8.0, mu=1.0, N=64)
        st = check_cache_status("spectral_sweep", params, self.root)
        self.assertEqual(st["state"], "cached")
        self.assertEqual(st["badge_text"], "Base Self-Energy (Σ) Cached")

    def test_spectral_function_point_sigma(self):
        """Quasiparticle Spectral Function: checks Point Self-Energy."""
        params = {
            "spec_sweep_mode": "JK",
            "spec_fixed_coupling": 6.0,
            "spec_momentum": "Antinodal k_F (π, 0)",
            "mu": 1.0,
            "N": 64
        }
        # Cold
        st = check_cache_status("spectral_function", params, self.root)
        self.assertEqual(st["state"], "cold")
        self.assertEqual(st["badge_text"], "Point Self-Energy (Σ) Not Cached")

        # Cached (create point file)
        self._create_mock_sigma_file(jperp=6.0, mu=1.0, N=64, ext_P=(32, 0))
        st = check_cache_status("spectral_function", params, self.root)
        self.assertEqual(st["state"], "cached")
        self.assertEqual(st["badge_text"], "Point Self-Energy (Σ) Cached")

    def test_phase_diagram_chi0(self):
        """Phase Diagram: checks Bare Susceptibility."""
        params = {"mu": 1.0, "N": 64}
        st = check_cache_status("phase_diagram", params, self.root)
        self.assertEqual(st["state"], "cold")
        self.assertEqual(st["badge_text"], "Bare Susceptibility (χ₀) Not Cached")

        self._create_mock_chi0_file(dynamic=False, mu=1.0, N=64)
        st = check_cache_status("phase_diagram", params, self.root)
        self.assertEqual(st["state"], "cached")
        self.assertEqual(st["badge_text"], "Bare Susceptibility (χ₀) Cached")

    def test_susceptibility_static_dynamic_permutations(self):
        """RPA Susceptibility: checks all permutations of static & dynamic."""
        params = {
            "run_static": True,
            "run_dynamic": True,
            "mu": 1.0,
            "N": 64,
            "num_omega": 600,
            "eta": 0.01
        }
        # Neither cached
        st = check_cache_status("susceptibility", params, self.root)
        self.assertEqual(st["state"], "cold")
        self.assertEqual(st["badge_text"], "Bare Susceptibility (χ₀) Not Cached")

        # Static only cached
        self._create_mock_chi0_file(dynamic=False, mu=1.0, N=64)
        st = check_cache_status("susceptibility", params, self.root)
        self.assertEqual(st["state"], "partial")
        self.assertEqual(st["badge_text"], "Partial χ₀ Cached (Static Only)")

        # Both cached
        self._create_mock_chi0_file(dynamic=True, mu=1.0, N=64)
        st = check_cache_status("susceptibility", params, self.root)
        self.assertEqual(st["state"], "cached")
        self.assertEqual(st["badge_text"], "Bare Susceptibility (χ₀) Cached")

        # Uncheck static -> dynamic only
        params["run_static"] = False
        params["run_dynamic"] = True
        st = check_cache_status("susceptibility", params, self.root)
        self.assertEqual(st["state"], "cached")
        self.assertEqual(st["badge_text"], "Bare Susceptibility (χ₀) Cached")

        # Uncheck both -> No channel
        params["run_static"] = False
        params["run_dynamic"] = False
        st = check_cache_status("susceptibility", params, self.root)
        self.assertEqual(st["state"], "cold")
        self.assertEqual(st["badge_text"], "No Susceptibility Channel Selected")

    def test_ui_force_recompute_and_theme_styling(self):
        """Tests that UnifiedWorkbenchWindow displays clean Force Recompute text without emojis."""
        win = UnifiedWorkbenchWindow()
        win.edit_out_dir.setText(self.root)
        
        # Check Force Recompute
        win.chk_force_recompute.setChecked(True)
        win._update_cache_badge()
        self.assertEqual(win.lbl_cache_badge.text(), "Force Recompute (Ignoring Cache)")
        self.assertNotIn("⚡", win.lbl_cache_badge.text())
        self.assertNotIn("⚠️", win.lbl_cache_badge.text())

        # Uncheck Force Recompute
        win.chk_force_recompute.setChecked(False)
        win._update_cache_badge()
        self.assertIn("Not Cached", win.lbl_cache_badge.text())
        win.close()


if __name__ == '__main__':
    unittest.main()
