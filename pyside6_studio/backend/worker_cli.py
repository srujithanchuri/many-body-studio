"""Standalone CLI worker script for Many-Body Studio Pro.
Executed in an isolated child process by QProcess to guarantee GUI crash immunity.
Emits structured JSON progress messages over stdout and flushes GPU VRAM upon exit.
Supports both:
  1. Spectral Sweep (DOS / Fermi Surface / High-Symmetry Path)
  2. Quasiparticle Spectral Function A(k, ω) & Self-Energy at designated k-points
"""

import sys
import os
import json
import base64
import argparse
import time
import glob
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 1. Force UTF-8 line-buffered stdout/stderr to prevent cp1252 Greek char crashes
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

import warnings
warnings.filterwarnings("ignore", message="CUDA path could not be detected.*", category=UserWarning)

# Ensure project roots and physics solver packages are on sys.path
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    INTERNAL_DIR = os.path.join(APP_DIR, "_internal")
    PROJECT_ROOT = APP_DIR
    GUI_ROOT = APP_DIR
    STUDIO_DIR = os.path.join(INTERNAL_DIR, "pyside6_studio")
    paths_to_check = [
        APP_DIR,
        INTERNAL_DIR,
        os.path.join(INTERNAL_DIR, "self_energy"),
        os.path.join(INTERNAL_DIR, "solvers"),
        os.path.join(INTERNAL_DIR, "susceptibility"),
        os.path.join(INTERNAL_DIR, "pyside6_studio"),
    ]
else:
    PROJECT_ROOT = os.environ.get("PHYSICS_REPO_ROOT", r"C:\Users\sruji\Projects\masters_thesis")
    GUI_ROOT = os.environ.get("GUI_ROOT", r"C:\Users\sruji\Projects\masters_thesis_gui")
    STUDIO_DIR = os.path.join(GUI_ROOT, "pyside6_studio")
    paths_to_check = [
        PROJECT_ROOT,
        GUI_ROOT,
        STUDIO_DIR,
        os.path.join(PROJECT_ROOT, "self_energy"),
        os.path.join(PROJECT_ROOT, "susceptibility"),
    ]

for p in reversed(paths_to_check):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

from pyside6_studio.backend.vram_cleaner import flush_gpu_vram
from pyside6_studio.backend.cuda_env import init_cuda_environment
from pyside6_studio.core.cache_manager import (
    normalize_results_dir,
    find_cached_sigma_base,
    get_sigma_base_filename
)

init_cuda_environment()


def emit_status(step_desc: str, phase: str = "running"):
    """Emits structured JSON status protocol line on stdout (no inaccurate percentages)."""
    msg = json.dumps({"type": "status", "phase": phase, "message": str(step_desc), "step": str(step_desc)})
    print(msg, flush=True)


def emit_progress(percent: int, step_desc: str):
    """Backward-compatible wrapper for status emission."""
    emit_status(step_desc)


def emit_completed(plot_path: str = "", data_path: str = "", all_plots: list = None):
    """Emits completion message on stdout."""
    msg = json.dumps({
        "type": "completed",
        "success": True,
        "plot_path": plot_path,
        "data_path": data_path,
        "all_plots": all_plots or ([plot_path] if plot_path else [])
    })
    print(msg, flush=True)


def run_spectral_sweep_task(params: dict, results_dir: str, out_plots_dir: str, out_data_dir: str, out_cache_dir: str):
    """Executes the full-BZ Spectral Sweep (DOS, FS, Path) with cache optimization and multi-plot delivery."""
    t = float(params.get("t", 1.0))
    t1 = float(params.get("t1", 0.0))
    mu = float(params.get("mu", 1.0))
    K = float(params.get("K", 1.0))
    N = int(params.get("N", 64))
    num_omega = int(params.get("num_omega", params.get("Nw", 2001)))
    omega_max = float(params.get("omega_max", params.get("w_max", 20.0)))
    eta = float(params.get("eta", 0.08))

    jk_vals = params.get("jk_values", [3.0, 6.0, 9.0])
    fixed_jperp = float(params.get("fixed_jperp", 6.0))
    sweep_mode = params.get("sweep_mode", "Kondo Coupling (J_K)")
    raw_solver = params.get("solver_choice", "gpu").lower()
    solver_choice = "cpu" if "cpu" in raw_solver else "gpu64"
    cpu_limit_str = str(params.get("cpu_limit", "80%")).rstrip("%")
    force_recompute = bool(params.get("force_recompute", False))
    try:
        cpu_limit = float(cpu_limit_str) / 100.0
    except Exception:
        cpu_limit = 0.80

    backend_label = "CUDA GPU (64-bit)" if solver_choice == "gpu64" else f"Multi-Core CPU ({int(cpu_limit*100)}% cores)"
    emit_status(f"Configuring parameters on {backend_label}: t={t}, mu={mu}, K={K}, N={N}×{N}, Nw={num_omega}")

    try:
        from self_energy.parameters import ModelParameters
    except (ImportError, ModuleNotFoundError):
        from parameters import ModelParameters

    try:
        import self_energy.sweep_core as sweep_core
    except (ImportError, ModuleNotFoundError):
        import sweep_core

    emit_status(f"Building Hamiltonian & numerical grids on {backend_label}...")
    p = ModelParameters(
        t=t, t1=t1, mu=mu, K=K,
        N=N, num_omega=num_omega, omega_max=omega_max, eta=eta,
        solver=solver_choice,
        cpu_limit=cpu_limit
    )

    emit_status(f"Evaluating 1-Loop & 3-Loop Self-Energy on {backend_label}...")

    is_jperp_sweep = ("Interlayer" in sweep_mode or "J_⊥" in sweep_mode)
    if is_jperp_sweep:
        res = sweep_core.run_J_perp_sweep(
            j_perp_values=jk_vals,
            fixed_jk=fixed_jperp,
            mu=mu,
            p=p,
            output_dir=results_dir,
            use_cache=True,
            force_recompute=force_recompute
        )
        safe_suffix = f"atJ_K_{fixed_jperp:.1f}_mu_{mu:.1f}".replace("$", "").replace("\\", "").replace(" ", "").replace("=", "_").replace("{", "").replace("}", "").replace(",", "_").replace("/", "_")
    else:
        res = sweep_core.run_J_k_sweep(
            j_k_values=jk_vals,
            fixed_jperp=fixed_jperp,
            mu=mu,
            p=p,
            output_dir=results_dir,
            use_cache=True,
            force_recompute=force_recompute
        )
        safe_suffix = f"atJ_perp_{fixed_jperp:.1f}_mu_{mu:.1f}".replace("$", "").replace("\\", "").replace(" ", "").replace("=", "_").replace("{", "").replace("}", "").replace(",", "_").replace("/", "_")

    emit_status("Locating and verifying generated composite spectral plots...")

    dos_plot = os.path.join(out_plots_dir, f"sweep_DOS_{safe_suffix}.png")
    fs_plot = os.path.join(out_plots_dir, f"sweep_FS_{safe_suffix}.png")
    path_plot = os.path.join(out_plots_dir, f"sweep_Path_{safe_suffix}.png")

    all_plots = [p_path for p_path in [dos_plot, fs_plot, path_plot] if os.path.isfile(p_path)]
    if not all_plots:
        for f in sorted(os.listdir(out_plots_dir), reverse=True):
            if f.endswith(".png") and "sweep" in f:
                all_plots.append(os.path.join(out_plots_dir, f))

    primary_plot = dos_plot if os.path.isfile(dos_plot) else (all_plots[0] if all_plots else "")
    data_path = str(res) if res and os.path.isfile(str(res)) else ""

    emit_status("Spectral Sweep completed successfully.")
    emit_completed(plot_path=primary_plot, data_path=data_path, all_plots=all_plots)


def run_spectral_function_task(params: dict, results_dir: str, out_plots_dir: str, out_data_dir: str, out_cache_dir: str):
    """Executes single-point Quasiparticle Spectral Function A(k, ω) calculation."""
    t = float(params.get("t", 1.0))
    t1 = float(params.get("t1", 0.0))
    mu = float(params.get("mu", 1.0))
    K = float(params.get("K", 1.0))
    N = int(params.get("N", 64))
    num_omega = int(params.get("num_omega", params.get("Nw", 2001)))
    omega_max = float(params.get("omega_max", params.get("w_max", 20.0)))
    eta = float(params.get("eta", 0.08))
    force_recompute = bool(params.get("force_recompute", False))

    sweep_mode = "JK" if ("Kondo" in params.get("spec_sweep_mode", "JK") or params.get("spec_sweep_mode") == "JK") else "J_perp"
    sweep_vals = params.get("spec_sweep_vals", [3.0, 6.0, 9.0])
    fixed_coupling = float(params.get("spec_fixed_coupling", 6.0))
    plot_layout = params.get("spec_plot_mode", "Both (Re Σ, A, Im Σ) [3 Panels]")
    mom_str = params.get("spec_momentum", "Antinodal k_F (π, 0)")
    custom_k = params.get("spec_custom_k", "1.0, 0.0")

    emit_progress(15, f"Configuring target momentum: {mom_str}...")

    # Determine kx, ky
    if "Antinodal" in mom_str:
        mult_x, mult_y = 1.0, 0.0
        k_label = r"$\mathbf{k} = (\pi, 0)$"
    elif "Nodal" in mom_str:
        mult_x, mult_y = 0.5, 0.5
        k_label = r"$\mathbf{k} = (\pi/2, \pi/2)$"
    elif "Corner" in mom_str or "(π, π)" in mom_str:
        mult_x, mult_y = 1.0, 1.0
        k_label = r"$\mathbf{k} = (\pi, \pi)$"
    elif "Center" in mom_str or "(0, 0)" in mom_str:
        mult_x, mult_y = 0.0, 0.0
        k_label = r"$\mathbf{k} = (0, 0)$"
    else:
        try:
            parts = [float(x.strip()) for x in custom_k.split(",") if x.strip()]
            mult_x = parts[0] if len(parts) > 0 else 1.0
            mult_y = parts[1] if len(parts) > 1 else 0.0
        except Exception:
            mult_x, mult_y = 1.0, 0.0
        k_label = rf"$\mathbf{{k}} = ({mult_x:g}\pi, {mult_y:g}\pi)$"

    kx_val = mult_x * np.pi
    ky_val = mult_y * np.pi
    ix = int(round((kx_val / (2.0 * np.pi)) * N)) % N
    iy = int(round((ky_val / (2.0 * np.pi)) * N)) % N
    ext_P = (ix, iy)

    try:
        from self_energy.parameters import ModelParameters
    except (ImportError, ModuleNotFoundError):
        from parameters import ModelParameters
    import importlib

    raw_solver = params.get("solver_choice", "gpu").lower()
    solver_choice = "cpu" if "cpu" in raw_solver else "gpu64"
    cpu_limit_str = str(params.get("cpu_limit", "80%")).rstrip("%")
    try:
        cpu_limit = float(cpu_limit_str) / 100.0
    except Exception:
        cpu_limit = 0.80

    p = ModelParameters(
        t=t, t1=t1, mu=mu, K=K,
        N=N, num_omega=num_omega, omega_max=omega_max, eta=eta,
        solver=solver_choice,
        cpu_limit=cpu_limit
    )

    solver_label = "RTX 5060 GPU" if solver_choice == "gpu64" else f"CPU ({int(cpu_limit*100)}% cores)"
    emit_progress(35, f"Solving single-point Dyson FFT on {solver_label} at P=({ix}, {iy})...")
    solver_dir = "cpu" if solver_choice == "cpu" else "gpu64"
    solver_m1 = importlib.import_module(f"solvers.{solver_dir}.one_loop")
    solver_m3 = importlib.import_module(f"solvers.{solver_dir}.three_loop")

    omega = np.linspace(-omega_max, omega_max, num_omega, dtype=np.float64)
    xi_k = -2.0 * t * (np.cos(kx_val) + np.cos(ky_val)) - 4.0 * t1 * (np.cos(kx_val) * np.cos(ky_val)) - mu

    curves = []
    if sweep_mode == "JK":
        p.j_perp = float(fixed_coupling)
        p.j_k = 1.0

        # Check single-point base cache in results/cache/
        base_cached = find_cached_sigma_base(
            cache_dir=out_cache_dir, fixed_jperp=fixed_coupling,
            t=t, t1=t1, mu=mu, K=K, N=N, num_omega=num_omega, omega_max=omega_max, eta=eta,
            ext_P=ext_P
        )
        s_loaded = False
        if base_cached and not force_recompute:
            try:
                t_load = time.time()
                d_c = np.load(base_cached)
                s1_re, s1_im = d_c["s1_re"], d_c["s1_im"]
                s3_re, s3_im = d_c["s3_re"], d_c["s3_im"]
                s_loaded = True
                emit_status(f"⚡ Loaded point Base Σ from cache ({time.time()-t_load:.2f}s)")
            except Exception:
                s_loaded = False

        if not s_loaded:
            emit_progress(50, "Evaluating 1-Loop and 3-Loop convolutions at target k...")
            s1_re, s1_im = solver_m1.calculate_one_loop(omega, p, external_P=ext_P)
            s3_re, s3_im = solver_m3.calculate_three_loop(omega, p, external_P=ext_P)
            try:
                base_fname = get_sigma_base_filename(
                    fixed_jperp=fixed_coupling, t=t, t1=t1, mu=mu, K=K,
                    N=N, num_omega=num_omega, omega_max=omega_max, eta=eta, ext_P=ext_P
                )
                np.savez_compressed(
                    os.path.join(out_cache_dir, base_fname),
                    s1_re=s1_re, s1_im=s1_im, s3_re=s3_re, s3_im=s3_im,
                    omega=omega, fixed_jperp=fixed_coupling, ext_P=ext_P,
                    t=t, t1=t1, mu=mu, K=K, N=N, num_omega=num_omega, eta=eta
                )
            except Exception:
                pass

        emit_progress(75, "Scaling spectral weight across Kondo coupling values...")
        for jk in sweep_vals:
            scale = (float(jk) / 1.0) ** 2
            re_sig = (s1_re + s3_re) * scale
            im_sig = (s1_im + s3_im) * scale
            im_tot = im_sig - eta
            denom = (omega - xi_k - re_sig) ** 2 + im_tot ** 2
            A_k = -(1.0 / np.pi) * (im_tot / denom)
            curves.append({"val": jk, "label": f"$J_K = {jk}$", "re": re_sig, "im": im_sig, "A": A_k})
        title_params = f"$J_\\perp = {fixed_coupling:.1f}$, $\\mu = {mu:.2f}$, $t = {t:.2f}$"
    else:
        for jp in sweep_vals:
            p_curr = ModelParameters(t=t, t1=t1, mu=mu, K=K, N=N, num_omega=num_omega, omega_max=omega_max, eta=eta, solver="gpu64")
            p_curr.j_perp = float(jp)
            p_curr.j_k = 1.0
            s1_re, s1_im = solver_m1.calculate_one_loop(omega, p_curr, external_P=ext_P)
            s3_re, s3_im = solver_m3.calculate_three_loop(omega, p_curr, external_P=ext_P)
            scale = (float(fixed_coupling) / 1.0) ** 2
            re_sig = (s1_re + s3_re) * scale
            im_sig = (s1_im + s3_im) * scale
            im_tot = im_sig - eta
            denom = (omega - xi_k - re_sig) ** 2 + im_tot ** 2
            A_k = -(1.0 / np.pi) * (im_tot / denom)
            curves.append({"val": jp, "label": f"$J_\\perp = {jp}$", "re": re_sig, "im": im_sig, "A": A_k})
        title_params = f"$J_K = {fixed_coupling:.1f}$, $\\mu = {mu:.2f}$, $t = {t:.2f}$"

    emit_progress(88, "Rendering multi-panel spectral function figure...")
    colors = ["#2563eb", "#d97706", "#dc2626", "#16a34a", "#9333ea", "#0891b2"]

    if "Only" in plot_layout and "Spectral" in plot_layout:
        fig, ax_spec = plt.subplots(figsize=(7.0, 5.0), constrained_layout=True)
        fig.suptitle(f"Spectral Function at {k_label} • {title_params}", fontsize=11)
        ax_spec.axvline(0, color='#94a3b8', linestyle='--', linewidth=0.9, alpha=0.7)
        for i, c in enumerate(curves):
            ax_spec.plot(omega, c["A"], label=c["label"], color=colors[i % len(colors)], lw=2.0)
        ax_spec.set_xlabel(r"$\omega$", fontsize=11)
        ax_spec.set_ylabel(r"$A(\mathbf{k}, \omega)$", fontsize=11)
        ax_spec.set_xlim(-omega_max, omega_max)
        ax_spec.set_ylim(bottom=0.0)
        ax_spec.grid(True, linestyle=':', alpha=0.35)
        ax_spec.legend(frameon=True, fontsize=9)
        plot_prefix = "spectral_only"
    elif "Self-Energy" in plot_layout:
        fig, (ax_re, ax_im) = plt.subplots(1, 2, figsize=(11.5, 4.8), constrained_layout=True)
        fig.suptitle(f"Retarded Self-Energy $\\Sigma(\\mathbf{{k}}, \\omega)$ at {k_label} • {title_params}", fontsize=11)
        for i, c in enumerate(curves):
            ax_re.plot(omega, c["re"], label=c["label"], color=colors[i % len(colors)], lw=1.8)
            ax_im.plot(omega, c["im"], label=c["label"], color=colors[i % len(colors)], lw=1.8)
        ax_re.set_xlabel(r"$\omega$"); ax_re.set_ylabel(r"$\operatorname{Re}\Sigma(\mathbf{k}, \omega)$")
        ax_im.set_xlabel(r"$\omega$"); ax_im.set_ylabel(r"$\operatorname{Im}\Sigma(\mathbf{k}, \omega)$")
        ax_re.grid(True, linestyle=':', alpha=0.35); ax_im.grid(True, linestyle=':', alpha=0.35)
        ax_re.legend(frameon=True, fontsize=9); ax_im.legend(frameon=True, fontsize=9)
        plot_prefix = "self_energy_only"
    else:
        # Both: 3 panels
        fig, (ax_re, ax_spec, ax_im) = plt.subplots(1, 3, figsize=(15.5, 4.8), constrained_layout=True)
        fig.suptitle(f"Quasiparticle Spectrum & Self-Energy at {k_label} • {title_params}", fontsize=11)
        for i, c in enumerate(curves):
            ax_re.plot(omega, c["re"], label=c["label"], color=colors[i % len(colors)], lw=1.8)
            ax_spec.plot(omega, c["A"], label=c["label"], color=colors[i % len(colors)], lw=2.0)
            ax_im.plot(omega, c["im"], label=c["label"], color=colors[i % len(colors)], lw=1.8)
        ax_re.set_title(r"$\operatorname{Re}\Sigma(\mathbf{k}, \omega)$ [Energy Shift]")
        ax_spec.set_title(r"$A(\mathbf{k}, \omega)$ [Spectral Function]")
        ax_im.set_title(r"$\operatorname{Im}\Sigma(\mathbf{k}, \omega)$ [Scattering Rate]")
        for ax in (ax_re, ax_spec, ax_im):
            ax.set_xlabel(r"$\omega$"); ax.set_xlim(-omega_max, omega_max); ax.grid(True, linestyle=':', alpha=0.35)
            ax.legend(frameon=True, fontsize=9)
        ax_spec.set_ylim(bottom=0.0)
        plot_prefix = "both"

    plot_file = os.path.join(out_plots_dir, f"{plot_prefix}_{sweep_mode}_k_{mult_x:g}_{mult_y:g}_mu_{mu:.1f}.png")
    fig.savefig(plot_file, dpi=300)
    plt.close(fig)

    # Save raw numerical dataset to results/data/
    data_file = os.path.join(out_data_dir, f"{plot_prefix}_{sweep_mode}_k_{mult_x:g}_{mult_y:g}_mu_{mu:.1f}_eta_{eta:.4f}.npz")
    save_data = {
        "omega": omega,
        "xi_k": xi_k,
        "kx": kx_val,
        "ky": ky_val,
        "ext_P": np.array(ext_P),
        "num_curves": len(curves),
        "sweep_mode": sweep_mode,
        "fixed_coupling": fixed_coupling,
        "mu": mu, "t": t, "t1": t1, "K": K, "N": N, "eta": eta
    }
    for idx, c in enumerate(curves):
        save_data[f"val_{idx}"] = c["val"]
        save_data[f"label_{idx}"] = c["label"]
        save_data[f"re_{idx}"] = c["re"]
        save_data[f"im_{idx}"] = c["im"]
        save_data[f"A_{idx}"] = c["A"]
    np.savez_compressed(data_file, **save_data)

    emit_progress(100, "Spectral Function calculation completed successfully.")
    emit_completed(plot_path=plot_file, data_path=data_file)


def run_phase_diagram_task(params: dict, results_dir: str, out_plots_dir: str, out_data_dir: str):
    """Executes Phase Boundary Bisection Search det[1 - Gamma(q)*chi0(q)] = 0 across the BZ."""
    mu = float(params.get("mu", 1.0))
    t = float(params.get("t", 1.0))
    t1 = float(params.get("t1", 0.0))
    K = float(params.get("K", 1.0))
    N = int(params.get("N", 64))

    jk_min = float(params.get("JK_min", params.get("jk_min", 0.0)))
    jk_max = float(params.get("JK_max", params.get("jk_max", 12.0)))
    jk_pts = int(params.get("JK_pts", params.get("jk_pts", 200)))
    force_recompute = bool(params.get("force_recompute", False))

    raw_solver = str(params.get("solver_choice", "gpu")).lower()
    solver_choice = "cpu" if "cpu" in raw_solver else "gpu64"
    cpu_limit_str = str(params.get("cpu_limit", "80%")).rstrip("%")
    try:
        cpu_limit = float(cpu_limit_str) / 100.0
    except Exception:
        cpu_limit = 0.80

    backend_label = "CUDA GPU (64-bit)" if solver_choice == "gpu64" else f"Multi-Core CPU ({int(cpu_limit*100)}% cores)"
    emit_status(f"Configuring Phase Diagram on {backend_label}: μ={mu}, t={t}, K={K}, N={N}×{N}, JK=[{jk_min:.1f} .. {jk_max:.1f}] ({jk_pts} pts)")

    SUSC_DIR = os.path.join(PROJECT_ROOT, "susceptibility")
    if SUSC_DIR in sys.path:
        sys.path.remove(SUSC_DIR)
    sys.path.insert(0, SUSC_DIR)
    if "solvers" in sys.modules:
        del sys.modules["solvers"]

    if solver_choice == "cpu":
        try:
            from solvers import set_cpu_threads
            total = os.cpu_count() or 4
            workers = max(1, int(round(total * cpu_limit)))
            set_cpu_threads(workers)
            emit_status(f"Allocated {workers} of {total} CPU cores for Numba parallel execution.")
        except Exception:
            pass

    import phase_diagram

    emit_status(f"Solving exact critical boundary instability condition on {backend_label}...")

    def on_status(msg):
        emit_status(f"{msg}")

    phase_diagram.run_phase_diagram(
        mu=mu,
        t=t,
        t1=t1,
        K_coupling=K,
        N=N,
        JK_min=jk_min,
        JK_max=jk_max,
        JK_pts=jk_pts,
        solver_choice=solver_choice,
        output_dir=results_dir,
        status_callback=on_status,
        force_recompute=force_recompute
    )

    k_tag = "AFM" if K > 0 else "FM"
    plot_file = os.path.join(out_plots_dir, f"phase_diagram_mu{mu:.2f}_{k_tag}.png")
    data_file = os.path.join(out_data_dir, f"phase_diagram_mu{mu:.2f}_{k_tag}.npz")

    emit_status("Phase Diagram calculation completed successfully.")
    emit_completed(plot_path=plot_file if os.path.exists(plot_file) else "", data_path=data_file if os.path.exists(data_file) else "")


def run_susceptibility_task(params: dict, results_dir: str, out_plots_dir: str, out_data_dir: str):
    """Executes 2D Static & Dynamic RPA Spin Susceptibility calculations."""
    mu = float(params.get("mu", 1.0))
    t = float(params.get("t", 1.0))
    t1 = float(params.get("t1", 0.0))
    K = float(params.get("K", 1.0))
    N = int(params.get("N", 64))
    num_omega = int(params.get("num_omega", params.get("Nw", 600)))
    omega_max = float(params.get("omega_max", params.get("w_max", 10.0)))
    eta = float(params.get("eta", 0.01))
    force_recompute = bool(params.get("force_recompute", False))

    run_static = bool(params.get("run_static", True))
    run_dynamic = bool(params.get("run_dynamic", True))

    sweep_mode = params.get("susc_sweep_mode", "JK")
    sweep_vals = params.get("susc_sweep_vals", [3.0, 6.0, 9.0])
    if isinstance(sweep_vals, str):
        sweep_vals = [float(x.strip()) for x in sweep_vals.split(",") if x.strip()]

    fixed_J = float(params.get("fixed_J", 6.0)) if sweep_mode == "JK" else None
    fixed_JK = float(params.get("fixed_JK", 3.0)) if sweep_mode in ["J", "J_perp"] else None

    raw_solver = str(params.get("solver_choice", "gpu")).lower()
    solver_choice = "cpu" if "cpu" in raw_solver else "gpu64"
    cpu_limit_str = str(params.get("cpu_limit", "80%")).rstrip("%")
    try:
        cpu_limit = float(cpu_limit_str) / 100.0
    except Exception:
        cpu_limit = 0.80

    backend_label = "CUDA GPU (64-bit)" if solver_choice == "gpu64" else f"Multi-Core CPU ({int(cpu_limit*100)}% cores)"
    modes_str = []
    if run_static: modes_str.append("Static χ(q)")
    if run_dynamic: modes_str.append("Dynamic χ(q,ω)")
    emit_status(f"Configuring RPA Susceptibility ({' + '.join(modes_str)}) on {backend_label}: N={N}×{N}, Nw={num_omega}, values={sweep_vals}")

    SUSC_DIR = os.path.join(PROJECT_ROOT, "susceptibility")
    if SUSC_DIR in sys.path:
        sys.path.remove(SUSC_DIR)
    sys.path.insert(0, SUSC_DIR)
    if "solvers" in sys.modules:
        del sys.modules["solvers"]

    if solver_choice == "cpu":
        try:
            from solvers import set_cpu_threads
            total = os.cpu_count() or 4
            workers = max(1, int(round(total * cpu_limit)))
            set_cpu_threads(workers)
            emit_status(f"Allocated {workers} of {total} CPU cores for Numba parallel execution.")
        except Exception:
            pass

    import sweeper

    def on_status(msg):
        emit_status(f"{msg}")

    sweeper.run_sweep(
        run_static=run_static,
        run_dynamic=run_dynamic,
        sweep_mode=sweep_mode,
        sweep_values=sweep_vals,
        fixed_J=fixed_J,
        fixed_JK=fixed_JK,
        mu=mu,
        t=t,
        t1=t1,
        K_coupling=K,
        N=N,
        omega_max=omega_max,
        num_omegas=num_omega,
        eta=eta,
        solver_choice=solver_choice,
        output_dir=results_dir,
        status_callback=on_status,
        force_recompute=force_recompute
    )

    fixed_str = f"J_{fixed_J}" if sweep_mode == "JK" else f"JK_{fixed_JK}"
    filename_base = f"sweep_{sweep_mode}_fixed_{fixed_str}_mu_{mu:.2f}"
    static_plot = os.path.join(out_plots_dir, f"{filename_base}_static.png")
    dynamic_plot = os.path.join(out_plots_dir, f"{filename_base}_dynamic.png")

    all_plots = []
    if os.path.exists(static_plot):
        all_plots.append(static_plot)
    if os.path.exists(dynamic_plot):
        all_plots.append(dynamic_plot)

    static_data = os.path.join(out_data_dir, f"{filename_base}_static.npz")
    dynamic_data = os.path.join(out_data_dir, f"{filename_base}_dynamic.npz")
    primary_data = static_data if os.path.exists(static_data) else (dynamic_data if os.path.exists(dynamic_data) else "")

    primary_plot = static_plot if os.path.exists(static_plot) else (dynamic_plot if os.path.exists(dynamic_plot) else "")
    emit_status("RPA Susceptibility calculation completed successfully.")
    emit_completed(plot_path=primary_plot, data_path=primary_data, all_plots=all_plots)


def run_conductivity_task(params: dict, results_dir: str, out_plots_dir: str, out_data_dir: str, out_cache_dir: str):
    """Executes the Optical / DC Electrical Conductivity Sweep across J_K or J_perp."""
    t = float(params.get("t", 1.0))
    t1 = float(params.get("t1", 0.0))
    mu = float(params.get("mu", 0.0))
    K = float(params.get("K", 1.0))
    N = int(params.get("N", 100))
    num_omega = int(params.get("num_omega", params.get("Nw", 4801)))
    omega_max = float(params.get("omega_max", params.get("w_max", 40.0)))
    eta = float(params.get("eta", 0.05))

    sweep_mode_raw = params.get("cond_sweep_mode", params.get("sweep_mode", "JK"))
    is_jk_sweep = not ("Interlayer" in str(sweep_mode_raw) or "J_perp" in str(sweep_mode_raw) or "J_⊥" in str(sweep_mode_raw))
    sweep_mode = "JK" if is_jk_sweep else "J_perp"

    sweep_vals = params.get("cond_sweep_vals", params.get("sweep_values", [0.0, 3.0, 6.0, 9.0]))
    if isinstance(sweep_vals, str):
        sweep_vals = [float(x.strip()) for x in sweep_vals.split(",") if x.strip()]

    fixed_jperp = float(params.get("fixed_jperp", 6.0))
    fixed_jk = float(params.get("fixed_jk", 3.0))
    w_active_max = float(params.get("w_active_max", 20.0))

    raw_solver = str(params.get("solver_choice", "gpu")).lower()
    solver_choice = "cpu" if "cpu" in raw_solver else "gpu"
    precision = str(params.get("precision", "float32")).lower()
    cpu_limit_str = str(params.get("cpu_limit", "80%")).rstrip("%")
    force_recompute = bool(params.get("force_recompute", False))

    try:
        cpu_limit = float(cpu_limit_str) / 100.0
    except Exception:
        cpu_limit = 0.80

    backend_label = "CUDA GPU" if solver_choice == "gpu" else f"Multi-Core CPU ({int(cpu_limit*100)}% cores)"
    sweep_label = "J_K" if is_jk_sweep else "J_⊥"
    fixed_label = "J_⊥" if is_jk_sweep else "J_K"
    fixed_val = fixed_jperp if is_jk_sweep else fixed_jk
    emit_status(f"Configuring Conductivity Sweep ({sweep_label}={sweep_vals}, fixed {fixed_label}={fixed_val:.2f}) on {backend_label}...")

    COND_DIR = os.path.join(PROJECT_ROOT, "conductivity")
    if COND_DIR not in sys.path:
        sys.path.insert(0, COND_DIR)

    from conductivity.sweeper import run_sweep

    def on_status(msg):
        emit_status(msg)

    omega_pos, sweep_vals_arr, sigma_curves, data_file, plot_file = run_sweep(
        sweep_mode=sweep_mode,
        sweep_values=sweep_vals,
        fixed_jperp=fixed_jperp,
        fixed_jk=fixed_jk,
        mu=mu,
        t=t,
        t1=t1,
        K=K,
        N=N,
        num_omega=num_omega,
        omega_max=omega_max,
        eta=eta,
        solver_choice=solver_choice,
        precision=precision,
        w_active_max=w_active_max,
        output_dir=results_dir,
        status_callback=on_status,
        force_recompute=force_recompute
    )

    plot_path = str(plot_file) if plot_file and os.path.isfile(str(plot_file)) else ""
    data_path = str(data_file) if data_file and os.path.isfile(str(data_file)) else ""
    all_plots = [plot_path] if plot_path else []

    emit_status("Electrical Conductivity Sweep completed successfully.")
    emit_completed(plot_path=plot_path, data_path=data_path, all_plots=all_plots)


def run_foundation_cache_task(params: dict, results_dir: str, out_plots_dir: str, out_data_dir: str, out_cache_dir: str):
    """
    Direct in-situ synthesizer for intermediate foundation arrays:
    - Base Self-Energy Sigma_base(k, omega) (1-loop and 3-loop FFT)
    - Bare Static Susceptibility chi0_static(q)
    - Bare Dynamic Susceptibility chi0_dynamic(q, omega)

    Skips batch loops and plotting routines entirely, executing in ~0.3s - 2.5s.
    """
    cache_category = params.get("cache_category", "sigma_base")  # "sigma_base", "chi0_static", "chi0_dynamic"
    t = float(params.get("t", 1.0))
    t1 = float(params.get("t1", 0.0))
    mu = float(params.get("mu", 0.0))
    K = float(params.get("K", 1.0))
    N = int(params.get("N", 100))
    raw_solver = params.get("solver_choice", "gpu").lower()
    solver_choice = "cpu" if "cpu" in raw_solver else "gpu64"
    force_recompute = bool(params.get("force_recompute", True))

    if cache_category == "sigma_base" or "sigma" in cache_category:
        fixed_jperp = float(params.get("fixed_jperp", params.get("Jperp", 6.0)))
        num_omega = int(params.get("num_omega", params.get("Nw", 4801 if N >= 100 else 2001)))
        omega_max = float(params.get("omega_max", params.get("w_max", 40.0 if N >= 100 else 20.0)))
        eta = float(params.get("eta", 0.05 if N >= 100 else 0.08))

        emit_status(f"Computing Total Self-Energy Σ on {solver_choice.upper()} (N={N}, μ={mu:.1f}, J⊥={fixed_jperp:.1f})...")
        try:
            from self_energy.parameters import ModelParameters
        except (ImportError, ModuleNotFoundError):
            from parameters import ModelParameters

        try:
            import self_energy.sweep_core as sweep_core
        except (ImportError, ModuleNotFoundError):
            import sweep_core

        p = ModelParameters(
            t=t, t1=t1, mu=mu, K=K,
            N=N, num_omega=num_omega, omega_max=omega_max, eta=eta,
            solver=solver_choice,
            cpu_limit=0.80
        )

        sweep_core.run_J_k_sweep(
            j_k_values=[1.0],
            fixed_jperp=fixed_jperp,
            mu=mu,
            p=p,
            output_dir=results_dir,
            use_cache=True,
            force_recompute=force_recompute
        )

        cache_name = sweep_core.get_sigma_base_filename(fixed_jperp, p)
        target_fpath = os.path.join(out_cache_dir, cache_name)
        if not os.path.exists(target_fpath):
            target_fpath = os.path.join(out_data_dir, cache_name)

        emit_status(f"✅ Total Self-Energy Σ computed: {cache_name}")
        emit_completed(plot_path="", data_path=target_fpath, all_plots=[])

    else:
        SUSC_DIR = os.path.join(PROJECT_ROOT, "susceptibility")
        if SUSC_DIR in sys.path:
            sys.path.remove(SUSC_DIR)
        sys.path.insert(0, SUSC_DIR)
        if "solvers" in sys.modules:
            del sys.modules["solvers"]
        if "sweeper" in sys.modules:
            del sys.modules["sweeper"]

        if solver_choice == "cpu":
            try:
                from solvers import set_cpu_threads
                total = os.cpu_count() or 4
                workers = max(1, int(round(total * 0.80)))
                set_cpu_threads(workers)
            except Exception:
                pass

        import sweeper

        is_dynamic = ("dynamic" in cache_category)
        omega_max = float(params.get("omega_max", 10.0))
        num_omega = int(params.get("num_omega", 600 if N <= 100 else 1600))
        eta = float(params.get("eta", 0.01 if N <= 100 else 0.004))

        emit_status(f"Synthesizing Bare {'Dynamic' if is_dynamic else 'Static'} χ₀ on {solver_choice.upper()} (N={N}, μ={mu:.1f})...")

        sweeper.run_sweep(
            run_static=not is_dynamic,
            run_dynamic=is_dynamic,
            sweep_mode="JK",
            sweep_values=[1.0],
            fixed_J=1.0,
            mu=mu,
            t=t,
            t1=t1,
            K_coupling=K,
            N=N,
            omega_max=omega_max,
            num_omegas=num_omega,
            eta=eta,
            solver_choice=solver_choice,
            output_dir=results_dir,
            force_recompute=force_recompute
        )

        if is_dynamic:
            cache_file = os.path.join(out_cache_dir, f"chi0_dynamic_t_{t:.2f}_t1_{t1:.2f}_mu_{mu:.2f}_K_{K:.2f}_N_{N}_wmax_{omega_max:.1f}_Nw_{num_omega}_eta_{eta:.4f}.npz")
        else:
            cache_file = os.path.join(out_cache_dir, f"chi0_static_t_{t:.2f}_t1_{t1:.2f}_mu_{mu:.2f}_K_{K:.2f}_N_{N}.npz")
        if not os.path.exists(cache_file):
            cache_file = ""

        emit_status(f"✅ Bare χ₀ computed successfully (N={N}, μ={mu:.1f}).")
        emit_completed(plot_path="", data_path=cache_file, all_plots=[])


def run_worker(params: dict):
    """Dispatches requested calculation task."""
    try:
        task = params.get("task", "spectral_sweep").lower()
        emit_progress(5, f"Initializing worker for task: {task}...")

        # Normalize to self-contained results directory layout
        base_out_dir = params.get("output_dir") or params.get("results_dir") or os.path.join(GUI_ROOT, "results")
        results_dir, out_plots_dir, out_data_dir, out_cache_dir = normalize_results_dir(base_out_dir)

        if "foundation" in task or "direct_cache" in task or ("cache" in task and "sweep" not in task):
            run_foundation_cache_task(params, results_dir, out_plots_dir, out_data_dir, out_cache_dir)
        elif "phase" in task or "diagram" in task or "bisection" in task:
            run_phase_diagram_task(params, results_dir, out_plots_dir, out_data_dir)
        elif "susc" in task or "rpa" in task or "chi" in task:
            run_susceptibility_task(params, results_dir, out_plots_dir, out_data_dir)
        elif "cond" in task or "conductivity" in task or "sigma" in task:
            run_conductivity_task(params, results_dir, out_plots_dir, out_data_dir, out_cache_dir)
        elif "function" in task or "a(k" in task or ("spec" in task and "sweep" not in task):
            run_spectral_function_task(params, results_dir, out_plots_dir, out_data_dir, out_cache_dir)
        else:
            run_spectral_sweep_task(params, results_dir, out_plots_dir, out_data_dir, out_cache_dir)

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"[STDERR] {err_tb}", flush=True)
        print(f"[WORKER ERROR] Solver execution failed: {e}", flush=True)
        try:
            print(f"[WORKER ERROR] Solver execution failed: {e}", file=sys.stderr, flush=True)
        except Exception:
            pass
        raise e
    finally:
        flush_gpu_vram()
        try:
            import cupy as cp
            if cp.cuda.is_available():
                cp.get_default_memory_pool().free_all_blocks()
                cp.get_default_pinned_memory_pool().free_all_blocks()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Many-Body Studio Pro Worker CLI")
    parser.add_argument("--params-b64", type=str, default=None, help="Base64-encoded JSON parameters")
    parser.add_argument("--params", type=str, default=None, help="Raw JSON string parameters")
    parser.add_argument("--task", type=str, default="spectral_sweep", help="Target calculation task name")

    args = parser.parse_args()

    params = None
    if args.params_b64:
        try:
            decoded = base64.b64decode(args.params_b64.encode("utf-8")).decode("utf-8")
            params = json.loads(decoded)
        except Exception as e:
            print(f"[FATAL] Failed to decode --params-b64: {e}", file=sys.stderr, flush=True)
            sys.exit(1)
    elif args.params:
        try:
            params = json.loads(args.params)
        except Exception as e:
            print(f"[FATAL] Failed to parse --params JSON: {e}", file=sys.stderr, flush=True)
            sys.exit(1)
    else:
        print("[FATAL] Either --params-b64 or --params must be provided", file=sys.stderr, flush=True)
        sys.exit(1)

    try:
        run_worker(params)
    except Exception as e:
        import traceback
        print(f"[STDERR] Fatal worker exception: {traceback.format_exc()}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
