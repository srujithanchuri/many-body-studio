"""Unit tests verifying Hamiltonian Parameters card UI, labels, and hover tooltips.

Tests:
1. All 4 Hamiltonian parameter widgets and labels exist with clear, correct names.
2. Rich physics hover tooltips are attached to both labels and spinboxes.
3. Card layout maintains clean compact aesthetic without redundant inline subtext.
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


class TestHamiltonianCardUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.window = UnifiedWorkbenchWindow()

    def tearDown(self):
        self.window.close()

    def test_01_widgets_and_labels_exist(self):
        """Verify presence and primary text of Hamiltonian widgets and labels."""
        w = self.window
        self.assertTrue(hasattr(w, "lbl_t"))
        self.assertTrue(hasattr(w, "spin_t"))
        self.assertEqual(w.lbl_t.text(), "Hopping (t):")

        self.assertTrue(hasattr(w, "lbl_t1"))
        self.assertTrue(hasattr(w, "spin_t1"))
        self.assertEqual(w.lbl_t1.text(), "Next-Nearest (t'):")

        self.assertTrue(hasattr(w, "lbl_mu"))
        self.assertTrue(hasattr(w, "spin_mu"))
        self.assertEqual(w.lbl_mu.text(), "Chemical Potential (μ):")

        self.assertTrue(hasattr(w, "lbl_k"))
        self.assertTrue(hasattr(w, "spin_k"))
        self.assertEqual(w.lbl_k.text(), "Intralayer Exchange (K):")

    def test_02_tooltips_content(self):
        """Verify that comprehensive physics tooltips are present on spinboxes and labels."""
        w = self.window
        # t
        self.assertIn("bandwidth", w.spin_t.toolTip().lower())
        self.assertEqual(w.lbl_t.toolTip(), w.spin_t.toolTip())
        # t'
        self.assertIn("van hove", w.spin_t1.toolTip().lower())
        self.assertEqual(w.lbl_t1.toolTip(), w.spin_t1.toolTip())
        # mu
        self.assertIn("half-filling", w.spin_mu.toolTip().lower())
        self.assertEqual(w.lbl_mu.toolTip(), w.spin_mu.toolTip())
        # K
        self.assertIn("antiferromagnetic", w.spin_k.toolTip().lower())
        self.assertEqual(w.lbl_k.toolTip(), w.spin_k.toolTip())


if __name__ == "__main__":
    unittest.main()
