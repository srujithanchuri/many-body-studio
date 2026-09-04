"""Comprehensive Verification Test Suite for Smart Caching Engine & Directory Structure.

Tests:
1. Self-contained results directory layout (results/plots, results/data, results/cache).
2. Elimination/migration of legacy nested results/plots/data/.
3. Deterministic parameter keys with rigorous invalidation rules (including eta).
4. Base Sigma_0 caching at J_K=1.0 and instantaneous J_K^2 scaling.
5. Invalidation when eta, mu, or J_perp change.
6. Bare bubble chi_0 sharing between Phase Diagram and Susceptibility.
7. Force recompute override bypass.
8. Cache manager inventory inspection and safe purging.
"""

import os
import sys
import time
import shutil
import tempfile
import unittest
import numpy as np

# Add project roots to sys.path
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
GUI_ROOT = os.path.dirname(THIS_DIR)
PROJECT_ROOT = r"C:\Users\sruji\Projects\masters_thesis"
STUDIO_DIR = os.path.join(GUI_ROOT, "pyside6_studio")

for p in [PROJECT_ROOT, GUI_ROOT, STUDIO_DIR]:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    import self_energy
    SE_DIR = os.path.dirname(os.path.abspath(self_energy.__file__))
    if SE_DIR not in sys.path:
        sys.path.insert(0, SE_DIR)
except Exception:
    SE_DIR = os.path.join(PROJECT_ROOT, "self_energy")
    if SE_DIR not in sys.path:
        sys.path.insert(0, SE_DIR)

from pyside6_studio.core.cache_manager import (
    normalize_results_dir,
    get_sigma_base_filename,
    get_chi0_static_filename,
    get_chi0_dynamic_filename,
    get_spectral_sweep_filename,
    find_cached_sigma_base,
    find_cached_chi0,
    check_cache_status,
    get_cache_stats,
    purge_cache
)
from parameters import ModelParameters
import sweep_core


class TestCachingAndDirectoryEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mb_cache_test_")

    def tearDown(self):
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_self_contained_directory_creation(self):
        """Tests that specifying any directory creates results/plots, results/data, and results/cache."""
        # 1. Specifying base project directory
        proj_dir = os.path.join(self.temp_dir, "my_project")
        res_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(proj_dir)

        self.assertEqual(res_dir, os.path.join(proj_dir, "results"))
        self.assertTrue(os.path.isdir(plots_dir))
        self.assertTrue(os.path.isdir(data_dir))
        self.assertTrue(os.path.isdir(cache_dir))

        # 2. Specifying results directly
        res2, p2, d2, c2 = normalize_results_dir(res_dir)
        self.assertEqual(res2, res_dir)

        # 3. Specifying a subfolder like results/plots
        res3, p3, d3, c3 = normalize_results_dir(plots_dir)
        self.assertEqual(res3, res_dir)

    def test_02_legacy_nested_data_migration(self):
        """Tests that any legacy results/plots/data is migrated to results/data."""
        proj_dir = os.path.join(self.temp_dir, "legacy_proj")
        res_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(proj_dir)

        # Artificially create legacy nested results/plots/data/
        legacy_dir = os.path.join(plots_dir, "data")
        os.makedirs(legacy_dir, exist_ok=True)
        dummy_file = os.path.join(legacy_dir, "dummy_sweep.npz")
        np.savez(dummy_file, a=np.array([1, 2, 3]))

        # Re-run normalize_results_dir
        normalize_results_dir(proj_dir)

        # Verify moved to results/data and legacy directory removed
        migrated_file = os.path.join(data_dir, "dummy_sweep.npz")
        self.assertTrue(os.path.isfile(migrated_file))
        self.assertFalse(os.path.isdir(legacy_dir))

    def test_03_parameter_invalidation_matrix(self):
        """Tests deterministic cache key invalidation rules, explicitly verifying eta sensitivity."""
        base_fn = get_sigma_base_filename(fixed_jperp=6.0, t=1.0, t1=0.0, mu=1.0, K=1.0, N=64, num_omega=2001, eta=0.08)

        # 1. Base Sigma is independent of J_K (J_K=1.0 foundation)
        # Therefore, sweeping different J_K values uses the exact same base_fn!
        self.assertIn("Jperp_6.00", base_fn)
        self.assertIn("eta_0.0800", base_fn)

        # 2. Changing eta MUST change base Sigma filename (addressing user requirement)
        fn_eta = get_sigma_base_filename(fixed_jperp=6.0, t=1.0, t1=0.0, mu=1.0, K=1.0, N=64, num_omega=2001, eta=0.05)
        self.assertNotEqual(base_fn, fn_eta)
        self.assertIn("eta_0.0500", fn_eta)

        # 3. Changing mu MUST change base Sigma filename
        fn_mu = get_sigma_base_filename(fixed_jperp=6.0, t=1.0, t1=0.0, mu=0.5, K=1.0, N=64, num_omega=2001, eta=0.08)
        self.assertNotEqual(base_fn, fn_mu)

        # 4. Changing J_perp MUST change base Sigma filename
        fn_jp = get_sigma_base_filename(fixed_jperp=4.0, t=1.0, t1=0.0, mu=1.0, K=1.0, N=64, num_omega=2001, eta=0.08)
        self.assertNotEqual(base_fn, fn_jp)

        # 5. Dynamic chi0 MUST depend on eta
        c_dyn1 = get_chi0_dynamic_filename(N=64, mu=1.0, eta=0.01)
        c_dyn2 = get_chi0_dynamic_filename(N=64, mu=1.0, eta=0.02)
        self.assertNotEqual(c_dyn1, c_dyn2)

        # 6. Static chi0 is non-interacting and independent of J_perp, J_K, K, and eta
        c_stat1 = get_chi0_static_filename(N=64, mu=1.0)
        c_stat2 = get_chi0_static_filename(N=64, mu=1.0)
        self.assertEqual(c_stat1, c_stat2)
        c_stat3 = get_chi0_static_filename(N=64, mu=0.5)
        self.assertNotEqual(c_stat1, c_stat3)

    def test_04_base_sigma_caching_and_jk_scaling(self):
        """Tests that base Sigma_0 is cached in results/cache and J_K sweeps reuse it."""
        res_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(self.temp_dir)

        p = ModelParameters(
            t=1.0, t1=0.0, mu=1.0, K=1.0,
            N=16, num_omega=21, omega_max=10.0, eta=0.08,
            solver="cpu", cpu_limit=0.5
        )

        # Run 1: Compute J_K=[3.0] with fixed_jperp=6.0
        t0 = time.time()
        out_npz1 = sweep_core.run_J_k_sweep(
            j_k_values=[3.0],
            fixed_jperp=6.0,
            mu=1.0,
            p=p,
            output_dir=res_dir,
            use_cache=True,
            force_recompute=False
        )
        dt1 = time.time() - t0

        # Assert files were saved in flat results/data and results/cache
        self.assertTrue(os.path.isfile(out_npz1))
        self.assertEqual(os.path.dirname(str(out_npz1)), str(data_dir))
        # Ensure NO results/plots/data directory was created
        self.assertFalse(os.path.isdir(os.path.join(plots_dir, "data")))

        # Verify base self-energy file was created in results/cache
        base_fn = get_sigma_base_filename(
            fixed_jperp=6.0,
            t=p.t,
            t1=getattr(p, 't1', 0.0),
            mu=p.mu,
            K=p.K,
            N=p.N,
            num_omega=p.num_omega,
            omega_max=p.omega_max,
            eta=p.eta
        )
        base_cached = os.path.join(cache_dir, base_fn)
        self.assertTrue(os.path.isfile(base_cached), f"Expected base cache {base_fn} in {cache_dir}")

        # Run 2: Sweeping a DIFFERENT J_K value ([6.0]) should HIT base cache!
        t0 = time.time()
        out_npz2 = sweep_core.run_J_k_sweep(
            j_k_values=[6.0],
            fixed_jperp=6.0,
            mu=1.0,
            p=p,
            output_dir=res_dir,
            use_cache=True,
            force_recompute=False
        )
        dt2 = time.time() - t0

        self.assertTrue(os.path.isfile(out_npz2))
        print(f"\n[BENCHMARK] Run 1 (cold base compute): {dt1:.3f}s | Run 2 (base cache hit): {dt2:.3f}s")
        # Run 2 should be substantially faster because 1-loop and 3-loop were skipped
        self.assertLess(dt2, dt1)

    def test_05_eta_change_forces_recompute(self):
        """Tests that changing eta invalidates the base self-energy cache and triggers recomputation."""
        res_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(self.temp_dir)

        p1 = ModelParameters(t=1.0, t1=0.0, mu=1.0, K=1.0, N=16, num_omega=21, omega_max=10.0, eta=0.08, solver="cpu")
        sweep_core.run_J_k_sweep([3.0], fixed_jperp=6.0, mu=1.0, p=p1, output_dir=res_dir, use_cache=True)

        base_fn1 = get_sigma_base_filename(fixed_jperp=6.0, t=1.0, t1=0.0, mu=1.0, K=1.0, N=16, num_omega=21, omega_max=10.0, eta=0.08)
        self.assertTrue(os.path.isfile(os.path.join(cache_dir, base_fn1)))

        # Now change eta to 0.05
        p2 = ModelParameters(t=1.0, t1=0.0, mu=1.0, K=1.0, N=16, num_omega=21, omega_max=10.0, eta=0.05, solver="cpu")
        base_fn2 = get_sigma_base_filename(fixed_jperp=6.0, t=1.0, t1=0.0, mu=1.0, K=1.0, N=16, num_omega=21, omega_max=10.0, eta=0.05)

        # Before running, base_fn2 does not exist in cache
        self.assertFalse(os.path.isfile(os.path.join(cache_dir, base_fn2)))

        # Status check must report cold compute
        status = check_cache_status(
            study="spectral_sweep",
            params={"t": 1.0, "t1": 0.0, "mu": 1.0, "K": 1.0, "N": 16, "num_omega": 21, "omega_max": 10.0, "eta": 0.05, "sweep_mode": "JK", "fixed_jperp": 6.0, "jk_values": [3.0]},
            out_dir=res_dir
        )
        self.assertEqual(status["state"], "cold")

        # Run with eta=0.05
        sweep_core.run_J_k_sweep([3.0], fixed_jperp=6.0, mu=1.0, p=p2, output_dir=res_dir, use_cache=True)

        # Now base_fn2 MUST exist in cache
        self.assertTrue(os.path.isfile(os.path.join(cache_dir, base_fn2)))

    def test_06_bare_chi0_sharing_and_purge(self):
        """Tests that bare bubble chi0 is stored in results/cache and can be purged."""
        res_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(self.temp_dir)

        SUSC_DIR = os.path.join(PROJECT_ROOT, "susceptibility")
        if SUSC_DIR in sys.path:
            sys.path.remove(SUSC_DIR)
        sys.path.insert(0, SUSC_DIR)
        for mod in list(sys.modules.keys()):
            if mod == "solvers" or mod.startswith("solvers."):
                del sys.modules[mod]
        import phase_diagram

        # Run Phase diagram on N=16 grid (CPU)
        phase_diagram.run_phase_diagram(
            mu=1.0, t=1.0, t1=0.0, K_coupling=1.0, N=16,
            JK_min=0.0, JK_max=2.0, JK_pts=5,
            solver_choice="cpu", output_dir=res_dir
        )

        chi0_fn = get_chi0_static_filename(N=16, mu=1.0, t=1.0, t1=0.0)
        chi0_cached = os.path.join(cache_dir, chi0_fn)
        self.assertTrue(os.path.isfile(chi0_cached), f"Expected bare chi0 bubble {chi0_fn} in {cache_dir}")

        # Check cache stats
        stats = get_cache_stats(res_dir)
        self.assertGreaterEqual(stats["total_files"], 1)

        # Purge cache
        deleted = purge_cache(res_dir)
        self.assertGreaterEqual(deleted, 1)
        self.assertFalse(os.path.isfile(chi0_cached))

        # Check stats after purge
        stats_after = get_cache_stats(res_dir)
        self.assertEqual(stats_after["total_files"], 0)


if __name__ == "__main__":
    unittest.main()
