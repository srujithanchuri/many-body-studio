"""Unit tests for RPA Spin Susceptibility Sweep UI configuration.

Verifies:
1. All Susceptibility UI elements (cb_susc_mode, edit_susc_vals, spin_susc_fixed, checkboxes) are created and placed.
2. Toggling the Sweep Target dynamically updates labels, descriptions, and default values.
3. Parameter extraction produces correct payload for both J_K and J_perp sweep targets.
4. Interactive parameter dispatch auto-selects Susceptibility study and pre-fills values accurately.
"""

import os
import sys
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHONIOENCODING"] = "utf-8"

GUI_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STUDIO_DIR = os.path.join(GUI_ROOT, "pyside6_studio")
PROJECT_ROOT = os.path.abspath(os.path.join(GUI_ROOT, "..", "masters_thesis"))

for p in [GUI_ROOT, STUDIO_DIR, PROJECT_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

from PySide6.QtWidgets import QApplication
from pyside6_studio.main_window import UnifiedWorkbenchWindow


class TestSusceptibilityUIConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.window = UnifiedWorkbenchWindow()

    def tearDown(self):
        self.window.close()

    def test_01_susceptibility_widgets_exist(self):
        """Verify that all susceptibility widgets are initialized and present in the UI."""
        w = self.window
        self.assertTrue(hasattr(w, "cb_susc_mode"), "cb_susc_mode must exist")
        self.assertTrue(hasattr(w, "edit_susc_vals"), "edit_susc_vals must exist")
        self.assertTrue(hasattr(w, "spin_susc_fixed"), "spin_susc_fixed must exist")
        self.assertTrue(hasattr(w, "lbl_susc_fixed"), "lbl_susc_fixed must exist")
        self.assertTrue(hasattr(w, "lbl_susc_fixed_desc"), "lbl_susc_fixed_desc must exist")
        self.assertTrue(hasattr(w, "chk_static"), "chk_static must exist")
        self.assertTrue(hasattr(w, "chk_dynamic"), "chk_dynamic must exist")

        self.assertEqual(w.cb_susc_mode.count(), 2)
        self.assertEqual(w.cb_susc_mode.itemText(0), "Kondo Coupling (J_K)")
        self.assertEqual(w.cb_susc_mode.itemText(1), "Interlayer Coupling (J_⊥)")
        self.assertEqual(w.edit_susc_vals.text(), "3.0, 6.0, 9.0")
        self.assertAlmostEqual(w.spin_susc_fixed.value(), 6.0)

    def test_02_mode_change_toggle(self):
        """Verify that toggling cb_susc_mode updates the fixed coupling label and values."""
        w = self.window

        # Initial state: index 0 (J_K sweep)
        w.cb_susc_mode.setCurrentIndex(0)
        self.assertIn("Interlayer", w.lbl_susc_fixed.text())
        self.assertAlmostEqual(w.spin_susc_fixed.value(), 6.0)

        # Toggle to index 1 (J_perp sweep)
        w.cb_susc_mode.setCurrentIndex(1)
        self.assertIn("Kondo", w.lbl_susc_fixed.text())
        self.assertAlmostEqual(w.spin_susc_fixed.value(), 6.0)
        self.assertEqual(w.edit_susc_vals.text(), "4.5, 6.0, 8.0")

        # Toggle back to index 0 (J_K sweep)
        w.cb_susc_mode.setCurrentIndex(0)
        self.assertIn("Interlayer", w.lbl_susc_fixed.text())
        self.assertEqual(w.edit_susc_vals.text(), "3.0, 6.0, 9.0")

    def test_03_extract_params_jk_sweep(self):
        """Verify parameter extraction when sweeping J_K with fixed J_perp."""
        w = self.window
        w.set_active_study(w.STUDY_SUSC)
        w.cb_susc_mode.setCurrentIndex(0)
        w.edit_susc_vals.setText("2.0, 4.0, 6.0")
        w.spin_susc_fixed.setValue(8.0)
        w.chk_static.setChecked(True)
        w.chk_dynamic.setChecked(False)

        params, study_name, summary = w._extract_active_study_params()
        self.assertIsNotNone(params)
        self.assertEqual(params["task"], "susceptibility")
        self.assertEqual(params["susc_sweep_mode"], "JK")
        self.assertEqual(params["susc_sweep_vals"], [2.0, 4.0, 6.0])
        self.assertEqual(params["fixed_J"], 8.0)
        self.assertIsNone(params["fixed_JK"])
        self.assertTrue(params["run_static"])
        self.assertFalse(params["run_dynamic"])
        self.assertIn("J_K", summary)
        self.assertIn("fixed J_⊥=8.0", summary)

    def test_04_extract_params_jperp_sweep(self):
        """Verify parameter extraction when sweeping J_perp with fixed J_K."""
        w = self.window
        w.set_active_study(w.STUDY_SUSC)
        w.cb_susc_mode.setCurrentIndex(1)
        w.edit_susc_vals.setText("5.0, 7.0")
        w.spin_susc_fixed.setValue(3.5)
        w.chk_static.setChecked(True)
        w.chk_dynamic.setChecked(True)

        params, study_name, summary = w._extract_active_study_params()
        self.assertIsNotNone(params)
        self.assertEqual(params["task"], "susceptibility")
        self.assertEqual(params["susc_sweep_mode"], "J")
        self.assertEqual(params["susc_sweep_vals"], [5.0, 7.0])
        self.assertIsNone(params["fixed_J"])
        self.assertEqual(params["fixed_JK"], 3.5)
        self.assertTrue(params["run_static"])
        self.assertTrue(params["run_dynamic"])
        self.assertIn("J_⊥", summary)
        self.assertIn("fixed J_K=3.5", summary)

    def test_05_receive_interactive_parameters_susceptibility(self):
        """Verify that sending interactive parameters from susceptibility mode updates UI and study."""
        w = self.window
        w.cb_susc_mode.setCurrentIndex(0)
        interactive_payload = {
            "mu": 0.5,
            "JK": 4.25,
            "Jperp": 7.5,
            "K": 1.0,
            "N": 128,
            "active_mode": "rpa_susceptibility"
        }
        w._on_receive_interactive_parameters(interactive_payload)
        self.assertEqual(w.active_study, w.STUDY_SUSC)
        self.assertEqual(w.edit_susc_vals.text(), "4.25")
        self.assertAlmostEqual(w.spin_susc_fixed.value(), 7.5)
        self.assertAlmostEqual(w.spin_mu.value(), 0.5)


if __name__ == "__main__":
    unittest.main()
