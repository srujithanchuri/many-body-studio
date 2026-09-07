"""Unit test suite for DatasetExplorerWidget and InteractiveDataCanvas.
Verifies run grouping, parameter extraction, search filtering, and visualization modes.
"""

import os
import sys
import tempfile
import unittest
import numpy as np

# Ensure project root is on sys.path
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TEST_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from pyside6_studio.widgets.dataset_explorer import (
    DatasetExplorerWidget,
    parse_filename_parameters,
    read_npz_metadata,
    format_bytes
)


class TestDatasetExplorerAndVisualizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        self.plots_dir = os.path.join(self.root, "results", "plots")
        self.data_dir = os.path.join(self.root, "results", "data")
        self.cache_dir = os.path.join(self.root, "results", "cache")
        for d in [self.plots_dir, self.data_dir, self.cache_dir]:
            os.makedirs(d, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_parse_filename_parameters(self):
        """Verifies regex parameter parsing from filenames."""
        fn = "sweep_DOS_atJ_perp_6.0_mu_1.0_N64_Nw2001_eta_0.0800.png"
        meta = parse_filename_parameters(fn)
        self.assertEqual(meta.get("mu"), 1.0)
        self.assertEqual(meta.get("fixed_jperp"), 6.0)
        self.assertEqual(meta.get("N"), 64)
        self.assertEqual(meta.get("num_omega"), 2001)
        self.assertEqual(meta.get("eta"), 0.08)

    def test_02_read_npz_metadata(self):
        """Verifies metadata extraction from .npz files."""
        npz_file = os.path.join(self.data_dir, "test_dataset.npz")
        np.savez(npz_file, omega=np.linspace(-5, 5, 101), mu=1.25, t=1.0, N=32, eta=0.05)

        meta = read_npz_metadata(npz_file)
        self.assertEqual(meta.get("mu"), 1.25)
        self.assertEqual(meta.get("t"), 1.0)
        self.assertEqual(meta.get("N"), 32)
        self.assertEqual(meta.get("eta"), 0.05)
        self.assertEqual(meta.get("omega_len"), 101)

    def test_03_run_grouping(self):
        """Verifies multiple plots and data arrays from one run are grouped into one record."""
        # Create Spectral Sweep files
        suffix = "atJ_perp_6.0_mu_1.0"
        p1 = os.path.join(self.plots_dir, f"sweep_DOS_{suffix}.png")
        p2 = os.path.join(self.plots_dir, f"sweep_FS_{suffix}.png")
        p3 = os.path.join(self.plots_dir, f"sweep_Path_{suffix}.png")
        d1 = os.path.join(self.data_dir, f"sweep_data_{suffix}.npz")

        for p in [p1, p2, p3]:
            with open(p, "wb") as f:
                f.write(b"PNGDATA")
        np.savez(d1, omega=np.linspace(-1, 1, 10), mu=1.0, N=64)

        # Create a cache foundation file (must NOT be shown in explorer)
        c1 = os.path.join(self.cache_dir, "chi0_static_N64_mu1.00_t1.00_t1_0.00.npz")
        np.savez(c1, chi0_grid=np.zeros((64, 64)), N=64)

        explorer = DatasetExplorerWidget(out_dir=self.root)
        self.assertEqual(len(explorer._runs_data), 1)
        run = explorer._runs_data[0]
        self.assertEqual(run["category"], "Sweeps")
        self.assertEqual(len(run["plots"]), 3)
        self.assertIsNotNone(run["data"])

        # Verify zero cache items in the explorer tree
        all_tree_text = " ".join(explorer.tree.topLevelItem(i).text(0) for i in range(explorer.tree.topLevelItemCount()))
        self.assertNotIn("chi0", all_tree_text.lower())
        self.assertNotIn("cache", all_tree_text.lower())

    def test_04_search_and_category_filtering(self):
        """Verifies real-time scientific search filtering and category tabs."""
        # Create 2 runs with distinct parameters
        p1 = os.path.join(self.plots_dir, "sweep_DOS_atJ_perp_6.0_mu_1.0_N64.png")
        p2 = os.path.join(self.plots_dir, "phase_diagram_mu0.50_AFM.png")
        with open(p1, "wb") as f: f.write(b"DATA")
        with open(p2, "wb") as f: f.write(b"DATA")

        # Cache file in results/cache (must NOT appear in tree)
        c1 = os.path.join(self.cache_dir, "chi0_static_N64_mu1.00_t1.00_t1_0.00.npz")
        np.savez(c1, dummy=1)

        explorer = DatasetExplorerWidget(out_dir=self.root)

        # 1. Test search by exact parameter mu=1.0
        explorer.edit_search.setText("mu=1.0")
        self.assertEqual(explorer.tree.topLevelItemCount(), 1)  # Sweeps category
        sweeps_cat = explorer.tree.topLevelItem(0)
        self.assertEqual(sweeps_cat.childCount(), 1)
        self.assertIn("Spectral Sweep", sweeps_cat.child(0).text(0))

        # 2. Test search by parameter mu=0.5
        explorer.edit_search.setText("mu=0.5")
        self.assertEqual(explorer.tree.topLevelItemCount(), 1)  # Phase Diagram category
        phase_cat = explorer.tree.topLevelItem(0)
        self.assertEqual(phase_cat.childCount(), 1)
        self.assertIn("Phase Diagram", phase_cat.child(0).text(0))

        # 3. Test search by order AFM
        explorer.edit_search.setText("AFM")
        self.assertEqual(explorer.tree.topLevelItemCount(), 1)
        self.assertIn("Phase Diagram", explorer.tree.topLevelItem(0).child(0).text(0))

        # 4. Test category filter pill (Sweeps: index 1)
        explorer.edit_search.clear()
        explorer._on_filter_changed(1)  # Sweeps only
        self.assertEqual(explorer.tree.topLevelItemCount(), 1)
        self.assertIn("SWEEPS", explorer.tree.topLevelItem(0).text(0))

        # 5. Test category filter pill (Phase: index 4)
        explorer._on_filter_changed(4)  # Phase Diagram only
        self.assertEqual(explorer.tree.topLevelItemCount(), 1)
        self.assertIn("PHASE DIAGRAM", explorer.tree.topLevelItem(0).text(0))


if __name__ == "__main__":
    unittest.main()
