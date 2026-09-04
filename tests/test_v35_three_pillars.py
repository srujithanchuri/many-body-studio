"""Comprehensive test suite for the 2-Perspective Visualization Architecture:
- Perspective 1: Publication Figures (PlotGalleryWidget + Interactive Canvas)
- Perspective 2: Live Analytical Lab (LiveAnalyticalLabWidget + Cache-driven real-time physics)
- Dual-Perspective Integration in UnifiedWorkbenchWindow
"""

import os
import sys
import tempfile
import unittest
import numpy as np

# Ensure masters_thesis_gui is on sys.path
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TEST_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from pyside6_studio.widgets.gallery_browser import (
    PlotGalleryWidget,
    ThumbnailCard,
    CompactRowCard,
    parse_plot_metadata
)
from pyside6_studio.widgets.live_analytical_lab import LiveAnalyticalLabWidget
from pyside6_studio.main_window import UnifiedWorkbenchWindow


class TestTwoPerspectivesArchitecture(unittest.TestCase):
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

        # Generate sample publication plots
        self.plot_path_disp = os.path.join(self.plots_dir, "sweep_Path_atJ_perp_6.0_mu_1.0.png")
        self.plot_path_dos = os.path.join(self.plots_dir, "sweep_DOS_atJ_perp_6.0_mu_1.0.png")
        self.plot_path_fs = os.path.join(self.plots_dir, "sweep_FS_atJ_perp_6.0_mu_1.0.png")
        self.plot_path_susc = os.path.join(self.plots_dir, "susceptibility_dynamic_mu_1.0.png")

        for p in [self.plot_path_disp, self.plot_path_dos, self.plot_path_fs, self.plot_path_susc]:
            with open(p, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        # Generate sample companion dataset (.npz)
        self.data_path_sweep = os.path.join(self.data_dir, "sweep_data_atJ_perp_6.0_mu_1.0.npz")
        omega = np.linspace(-10.0, 10.0, 501)
        # Model Lorentzians for DOS: A_loc(w)
        a0 = (1.0 / np.pi) * 0.5 / (omega**2 + 0.25)
        a1 = (1.0 / np.pi) * 0.8 / (omega**2 + 0.64)
        # Self energies: Re Sigma linear around zero, Im Sigma quadratic
        re0 = -0.5 * omega
        im0 = -0.1 - 0.2 * omega**2
        re1 = -0.7 * omega
        im1 = -0.15 - 0.3 * omega**2

        np.savez(
            self.data_path_sweep,
            omega=omega,
            labels=np.array(["$J_K = 3.0$", "$J_K = 6.0$"]),
            sweep_vals=np.array([3.0, 6.0]),
            Atot_loc_0=a0,
            Atot_loc_1=a1,
            re_tot_0=re0,
            im_tot_0=im0,
            re_tot_1=re1,
            im_tot_1=im1,
            mu=1.0,
            t=1.0,
            fixed_jperp=6.0
        )

        # Generate sample Full BZ Base Sigma cache foundation
        self.cache_base_sigma = os.path.join(self.cache_dir, "sigma_base_full_bz_Jperp_6.00_t_1.00_t1_0.00_mu_1.00_K_1.00_N_16_Nw_101_wmax_10.0_eta_0.0500.npz")
        N_grid = 16
        w_grid = np.linspace(-5.0, 5.0, 101)
        # Shapes: (Nw, N, N)
        sig_re = np.zeros((101, N_grid, N_grid), dtype=np.float32)
        sig_im = -0.05 * np.ones((101, N_grid, N_grid), dtype=np.float32)
        for iw, w in enumerate(w_grid):
            sig_re[iw, :, :] = -0.3 * w
            sig_im[iw, :, :] = -0.05 - 0.1 * w**2

        np.savez(
            self.cache_base_sigma,
            sig_re=sig_re,
            sig_im=sig_im,
            omega=w_grid,
            N=N_grid,
            t=1.0,
            t1=0.0,
            mu=1.0,
            eta=0.05,
            is_ibz=False
        )

        # Generate sample Static Chi0 cache foundation
        self.cache_static_chi0 = os.path.join(self.cache_dir, "chi0_static_N16_mu1.00_t1.00_t1_0.00.npz")
        q_axis = np.linspace(-np.pi, np.pi, 16)
        chi0_grid = 0.5 * np.ones((16, 16), dtype=np.float32)
        np.savez(
            self.cache_static_chi0,
            chi0_grid=chi0_grid,
            q_axis=q_axis,
            N=16,
            mu=1.0,
            t=1.0
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # Pillar 1 Tests: PlotGalleryWidget & Metadata Parsing
    # -------------------------------------------------------------------------
    def test_01_parse_plot_metadata(self):
        """Verifies clear physics titles and parameter badges derived from filenames."""
        title, badges, cat, obs, _ = parse_plot_metadata(self.plot_path_disp)
        self.assertIn("Band Dispersion", title)
        self.assertIn("J_⊥ = 6.0", badges)
        self.assertIn("μ = 1.0", badges)
        self.assertEqual(cat, "🌊 Spectral")
        self.assertEqual(obs, "Band Dispersion (Path)")

        title_dos, _, cat_dos, obs_dos, _ = parse_plot_metadata(self.plot_path_dos)
        self.assertIn("Density of States", title_dos)
        self.assertEqual(obs_dos, "Density of States (DOS)")

    def test_02_gallery_browser_scanning_and_pairing(self):
        """Verifies gallery finds plots, pairs them with companion .npz data, and filters."""
        gallery = PlotGalleryWidget()
        gallery.set_output_dir(self.root)

        self.assertEqual(len(gallery.all_plots), 4)

        # Pairing verification: sweep_DOS... and sweep_Path... should pair with sweep_data...
        paired_disp = gallery._find_paired_data(self.plot_path_disp)
        self.assertIsNotNone(paired_disp)
        self.assertTrue(paired_disp.endswith("sweep_data_atJ_perp_6.0_mu_1.0.npz"))

        paired_dos = gallery._find_paired_data(self.plot_path_dos)
        self.assertIsNotNone(paired_dos)
        self.assertTrue(paired_dos.endswith("sweep_data_atJ_perp_6.0_mu_1.0.npz"))

        # Category Filtering via Pills
        gallery._on_category_pill_clicked("Spectral Results")
        self.app.processEvents()
        # Should exclude susceptibility (3 spectral plots)
        self.assertEqual(len(gallery.card_widgets), 3)

        # Smart Parameter Search: 'mu = 1' should match 'mu_1.0'
        gallery.edit_search.setText("mu = 1")
        self.app.processEvents()
        self.assertEqual(len(gallery.card_widgets), 3)

        # Keyword filtering: 'DOS'
        gallery.edit_search.setText("DOS")
        self.app.processEvents()
        self.assertEqual(len(gallery.card_widgets), 1)
        card_dos = list(gallery.card_widgets.values())[0]
        self.assertIn("Density of States", card_dos.title)

        # Dual View Mode Switcher: Cards vs Compact List
        gallery.edit_search.clear()
        gallery._on_category_pill_clicked("All")
        self.app.processEvents()
        self.assertEqual(len(gallery.card_widgets), 4)
        self.assertIsInstance(list(gallery.card_widgets.values())[0], ThumbnailCard)

        # Switch to Compact List mode
        gallery._set_view_mode("list")
        self.app.processEvents()
        self.assertEqual(len(gallery.card_widgets), 4)
        self.assertIsInstance(list(gallery.card_widgets.values())[0], CompactRowCard)

        # Switch back to Cards mode
        gallery._set_view_mode("cards")
        self.app.processEvents()
        self.assertEqual(len(gallery.card_widgets), 4)
        self.assertIsInstance(list(gallery.card_widgets.values())[0], ThumbnailCard)

    # -------------------------------------------------------------------------
    # Perspective 2 Tests: Live Analytical Lab On-The-Fly Physics
    # -------------------------------------------------------------------------
    def test_03_live_analytical_lab_experiments(self):
        """Verifies cache discovery, real-time J_K scaling, and analytical experiments."""
        lab = LiveAnalyticalLabWidget(out_dir=self.root)
        lab.scan_caches()

        self.assertGreaterEqual(len(lab.scanned_caches), 2)
        self.assertGreaterEqual(lab.cb_cache_file.count(), 1)

        # Select Base Sigma cache
        sigma_idx = -1
        for i in range(lab.cb_cache_file.count()):
            if "Σ" in lab.cb_cache_file.itemText(i):
                sigma_idx = i
                break
        self.assertNotEqual(sigma_idx, -1)
        lab.cb_cache_file.setCurrentIndex(sigma_idx)
        self.assertIsNotNone(lab.loaded_base_sigma)

        # Experiment 0: Analytical BZ k-probe
        lab.cb_experiment.setCurrentIndex(0)
        lab.slider_jk.setValue(30)  # J_K = 3.0
        self.assertEqual(lab.current_JK, 3.0)
        # Should have updated live HUD labels
        self.assertTrue("Z(k):" in lab.lbl_live_z.text())
        self.assertTrue("m*/m:" in lab.lbl_live_mass.text())
        self.assertTrue("Γ(k):" in lab.lbl_live_gamma.text())
        # Should produce 2 subplots: A(k, w) and Re/Im Sigma
        self.assertEqual(len(lab.fig.axes), 2)

        # Experiment 1: Energy Sliced Fermi Contours & Integrated DOS
        lab.cb_experiment.setCurrentIndex(1)
        self.assertEqual(lab.active_mode, "energy_slice")
        lab.slider_slice.setValue(50)  # w = 0.50 eV
        self.assertEqual(lab.current_omega_slice, 0.50)
        self.assertGreaterEqual(len(lab.fig.axes), 1)
        # Verify exact DOS was calculated without subsampling errors
        mode1 = lab.current_mode
        self.assertIsNotNone(mode1._current_dos)
        self.assertEqual(len(mode1._current_dos), len(lab.loaded_base_sigma["omega"]))
        self.assertTrue(np.all(mode1._current_dos >= 0.0))

        # Experiment 2: Energy-Momentum Band Dispersion along High-Symmetry Path
        lab.cb_experiment.setCurrentIndex(2)
        self.assertEqual(lab.active_mode, "band_dispersion")
        mode2 = lab.current_mode
        self.assertIsNotNone(mode2._path_ix)
        self.assertGreater(len(mode2._path_ix), 0)
        self.assertIsNotNone(mode2._xi_path)
        self.assertEqual(len(lab.fig.axes), 3)  # 2 subplots + 1 colorbar

        # Experiment 3: Static RPA Susceptibility
        # Selecting RPA should auto-switch to static chi0 cache
        lab.cb_experiment.setCurrentIndex(3)
        self.assertEqual(lab.active_mode, "rpa_susc")
        self.assertIsNotNone(lab.loaded_chi0_static)
        # Continuous slider changes J_K and updates Stoner instability gap
        lab.slider_jk.setValue(60)  # J_K = 6.0
        self.assertEqual(lab.current_JK, 6.0)

    # -------------------------------------------------------------------------
    # Integration Test: Mode Switcher & Two Perspectives Integration
    # -------------------------------------------------------------------------
    def test_04_workbench_perspectives_integration(self):
        """Verifies switching between the 2 perspectives and gallery selection."""
        win = UnifiedWorkbenchWindow()
        win.gallery.set_output_dir(self.root)
        self.app.processEvents()

        # Check Perspective 0 (Publication Figures)
        win.set_canvas_mode(0)
        self.assertEqual(win.central_view_stack.currentIndex(), 0)
        self.assertTrue(win.btn_canvas_figure.isChecked())
        self.assertFalse(win.btn_canvas_lab.isChecked())

        # Check Perspective 1 (Live Analytical Lab)
        win.set_canvas_mode(1)
        self.assertEqual(win.central_view_stack.currentIndex(), 1)
        self.assertFalse(win.btn_canvas_figure.isChecked())
        self.assertTrue(win.btn_canvas_lab.isChecked())

        # Clicking a gallery plot switches to Perspective 0 and loads the image
        win._on_gallery_plot_selected(self.plot_path_dos)
        self.app.processEvents()
        self.assertEqual(win.central_view_stack.currentIndex(), 0)
        self.assertEqual(win.current_view_plot_path, self.plot_path_dos)
        self.assertTrue(win.btn_canvas_figure.isChecked())

        win.close()


if __name__ == "__main__":
    unittest.main()
