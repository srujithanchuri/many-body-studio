"""Rigorous 8-Pathway Solver Verification Suite.

Tests all four physics studies on both GPU (CUDA) and CPU (Numba parallel):
  1. Spectral Sweep (GPU)
  2. Spectral Sweep (CPU)
  3. Quasiparticle Spectral Function A(k, w) (GPU)
  4. Quasiparticle Spectral Function A(k, w) (CPU)
  5. Phase Boundary Bisection (GPU)
  6. Phase Boundary Bisection (CPU)
  7. RPA Spin Susceptibility (GPU)
  8. RPA Spin Susceptibility (CPU)

Uses lightweight grids (N=16, Nw=21..51, JK_pts=5) for rapid execution (~15-30s total).
Asserts stdout JSON protocol contract, exit code 0, and non-empty plot/data artifact production.
"""

import os
import sys
import json
import base64
import shutil
import tempfile
import unittest
import subprocess

PROJECT_ROOT = r"C:\Users\sruji\Projects\masters_thesis"
GUI_ROOT = r"C:\Users\sruji\Projects\masters_thesis_gui"
STUDIO_DIR = os.path.join(GUI_ROOT, "pyside6_studio")
WORKER_SCRIPT = os.path.join(STUDIO_DIR, "backend", "worker_cli.py")
VENV_PYTHON = os.path.join(GUI_ROOT, ".venv", "Scripts", "python.exe")


class TestAllFourSolversE2E(unittest.TestCase):
    """Verifies end-to-end execution of all four physics solvers across GPU and CPU."""

    @classmethod
    def setUpClass(cls):
        cls.python_exe = VENV_PYTHON if os.path.isfile(VENV_PYTHON) else sys.executable
        cls.test_dir = tempfile.mkdtemp(prefix="solver_verify_")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def _run_worker_subprocess(self, params: dict):
        """Executes worker_cli.py with base64 encoded params in a subprocess."""
        json_bytes = json.dumps(params).encode("utf-8")
        b64_params = base64.b64encode(json_bytes).decode("utf-8")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = os.pathsep.join([
            PROJECT_ROOT, GUI_ROOT, STUDIO_DIR,
            os.path.join(PROJECT_ROOT, "self_energy"),
            os.path.join(PROJECT_ROOT, "susceptibility")
        ])

        cmd = [self.python_exe, "-u", WORKER_SCRIPT, "--params-b64", b64_params]
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return proc

    def _assert_worker_success(self, proc, expected_task_name: str):
        """Validates that worker completed with exit code 0, emitted JSON messages, and generated files."""
        self.assertEqual(
            proc.returncode, 0,
            f"Worker failed for {expected_task_name}!\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}"
        )

        completed_payload = None
        status_count = 0

        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
                msg_type = data.get("type")
                if msg_type in ["status", "progress"]:
                    status_count += 1
                elif msg_type == "completed":
                    completed_payload = data
            except Exception:
                pass

        self.assertGreater(
            status_count, 0,
            f"Expected status updates for {expected_task_name}, but none received."
        )
        self.assertIsNotNone(
            completed_payload,
            f"No completed JSON message emitted for {expected_task_name}!\nSTDOUT:\n{proc.stdout}"
        )
        self.assertTrue(completed_payload.get("success", False))

        plot_path = completed_payload.get("plot_path", "")
        if plot_path:
            self.assertTrue(os.path.isfile(plot_path), f"Reported plot does not exist: {plot_path}")
            self.assertGreater(os.path.getsize(plot_path), 100, f"Plot file is empty: {plot_path}")

        data_path = completed_payload.get("data_path", "")
        if data_path:
            self.assertTrue(os.path.isfile(data_path), f"Reported data file does not exist: {data_path}")
            self.assertGreater(os.path.getsize(data_path), 50, f"Data file is empty: {data_path}")

        return completed_payload

    # =========================================================================
    # 1. SPECTRAL SWEEP (GPU & CPU)
    # =========================================================================
    def test_01_spectral_sweep_gpu(self):
        """Spectral Sweep on GPU (NVIDIA CUDA)."""
        out_dir = os.path.join(self.test_dir, "sweep_gpu")
        params = {
            "task": "spectral_sweep",
            "solver_choice": "gpu",
            "t": 1.0, "t1": 0.0, "mu": 1.0, "K": 1.0,
            "N": 16, "num_omega": 51, "omega_max": 10.0, "eta": 0.08,
            "jk_values": [3.0], "fixed_jperp": 6.0,
            "sweep_mode": "Kondo Coupling (J_K)",
            "output_dir": out_dir
        }
        proc = self._run_worker_subprocess(params)
        self._assert_worker_success(proc, "spectral_sweep_gpu")

    def test_02_spectral_sweep_cpu(self):
        """Spectral Sweep on CPU (Numba Parallel)."""
        out_dir = os.path.join(self.test_dir, "sweep_cpu")
        params = {
            "task": "spectral_sweep",
            "solver_choice": "cpu",
            "cpu_limit": "50%",
            "t": 1.0, "t1": 0.0, "mu": 1.0, "K": 1.0,
            "N": 16, "num_omega": 51, "omega_max": 10.0, "eta": 0.08,
            "jk_values": [3.0], "fixed_jperp": 6.0,
            "sweep_mode": "Kondo Coupling (J_K)",
            "output_dir": out_dir
        }
        proc = self._run_worker_subprocess(params)
        self._assert_worker_success(proc, "spectral_sweep_cpu")

    # =========================================================================
    # 2. SPECTRAL FUNCTION A(k, w) (GPU & CPU)
    # =========================================================================
    def test_03_spectral_function_gpu(self):
        """Quasiparticle Spectral Function A(k, w) on GPU."""
        out_dir = os.path.join(self.test_dir, "spec_gpu")
        params = {
            "task": "spectral_function",
            "solver_choice": "gpu",
            "t": 1.0, "t1": 0.0, "mu": 1.0, "K": 1.0,
            "N": 16, "num_omega": 51, "omega_max": 10.0, "eta": 0.08,
            "spec_sweep_mode": "JK",
            "spec_sweep_vals": [3.0],
            "spec_fixed_coupling": 6.0,
            "spec_momentum": "Antinodal k_F (π, 0)",
            "spec_plot_mode": "Both (Re Σ, A, Im Σ) [3 Panels]",
            "output_dir": out_dir
        }
        proc = self._run_worker_subprocess(params)
        self._assert_worker_success(proc, "spectral_function_gpu")

    def test_04_spectral_function_cpu(self):
        """Quasiparticle Spectral Function A(k, w) on CPU."""
        out_dir = os.path.join(self.test_dir, "spec_cpu")
        params = {
            "task": "spectral_function",
            "solver_choice": "cpu",
            "cpu_limit": "50%",
            "t": 1.0, "t1": 0.0, "mu": 1.0, "K": 1.0,
            "N": 16, "num_omega": 51, "omega_max": 10.0, "eta": 0.08,
            "spec_sweep_mode": "JK",
            "spec_sweep_vals": [3.0],
            "spec_fixed_coupling": 6.0,
            "spec_momentum": "Antinodal k_F (π, 0)",
            "spec_plot_mode": "Both (Re Σ, A, Im Σ) [3 Panels]",
            "output_dir": out_dir
        }
        proc = self._run_worker_subprocess(params)
        self._assert_worker_success(proc, "spectral_function_cpu")

    # =========================================================================
    # 3. PHASE DIAGRAM BISECTION (GPU & CPU)
    # =========================================================================
    def test_05_phase_diagram_gpu(self):
        """Phase Boundary Bisection on GPU."""
        out_dir = os.path.join(self.test_dir, "pd_gpu")
        params = {
            "task": "phase_diagram",
            "solver_choice": "gpu",
            "t": 1.0, "t1": 0.0, "mu": 1.0, "K": 1.0,
            "N": 16,
            "JK_min": 0.0, "JK_max": 6.0, "JK_pts": 5,
            "output_dir": out_dir
        }
        proc = self._run_worker_subprocess(params)
        payload = self._assert_worker_success(proc, "phase_diagram_gpu")
        self.assertTrue(payload.get("data_path", "").endswith(".npz"))

    def test_06_phase_diagram_cpu(self):
        """Phase Boundary Bisection on CPU."""
        out_dir = os.path.join(self.test_dir, "pd_cpu")
        params = {
            "task": "phase_diagram",
            "solver_choice": "cpu",
            "cpu_limit": "50%",
            "t": 1.0, "t1": 0.0, "mu": 1.0, "K": 1.0,
            "N": 16,
            "JK_min": 0.0, "JK_max": 6.0, "JK_pts": 5,
            "output_dir": out_dir
        }
        proc = self._run_worker_subprocess(params)
        payload = self._assert_worker_success(proc, "phase_diagram_cpu")
        self.assertTrue(payload.get("data_path", "").endswith(".npz"))

    # =========================================================================
    # 4. RPA SPIN SUSCEPTIBILITY (GPU & CPU)
    # =========================================================================
    def test_07_susceptibility_gpu(self):
        """Static & Dynamic RPA Susceptibility on GPU."""
        out_dir = os.path.join(self.test_dir, "susc_gpu")
        params = {
            "task": "susceptibility",
            "solver_choice": "gpu",
            "t": 1.0, "t1": 0.0, "mu": 1.0, "K": 1.0,
            "N": 16, "num_omega": 21, "omega_max": 5.0, "eta": 0.05,
            "run_static": True, "run_dynamic": True,
            "susc_sweep_mode": "JK",
            "susc_sweep_vals": [3.0],
            "fixed_J": 6.0,
            "output_dir": out_dir
        }
        proc = self._run_worker_subprocess(params)
        payload = self._assert_worker_success(proc, "susceptibility_gpu")
        self.assertGreaterEqual(len(payload.get("all_plots", [])), 1)

    def test_08_susceptibility_cpu(self):
        """Static & Dynamic RPA Susceptibility on CPU."""
        out_dir = os.path.join(self.test_dir, "susc_cpu")
        params = {
            "task": "susceptibility",
            "solver_choice": "cpu",
            "cpu_limit": "50%",
            "t": 1.0, "t1": 0.0, "mu": 1.0, "K": 1.0,
            "N": 16, "num_omega": 21, "omega_max": 5.0, "eta": 0.05,
            "run_static": True, "run_dynamic": True,
            "susc_sweep_mode": "JK",
            "susc_sweep_vals": [3.0],
            "fixed_J": 6.0,
            "output_dir": out_dir
        }
        proc = self._run_worker_subprocess(params)
        payload = self._assert_worker_success(proc, "susceptibility_cpu")
        self.assertGreaterEqual(len(payload.get("all_plots", [])), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
