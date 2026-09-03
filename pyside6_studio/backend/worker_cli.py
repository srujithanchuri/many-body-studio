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

# Ensure project roots are on sys.path
PROJECT_ROOT = r"C:\Users\sruji\Projects\masters_thesis"
GUI_ROOT = r"C:\Users\sruji\Projects\masters_thesis_gui"
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

from pyside6_studio.backend.vram_cleaner import flush_gpu_vram


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


def run_spectral_sweep_task(params: dict, out_plots_dir: str, out_data_dir: str):
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
    try:
        cpu_limit = float(cpu_limit_str) / 100.0
    except Exception:
        cpu_limit = 0.80

    backend_label = "NVIDIA RTX 5060 GPU (64-bit)" if solver_choice == "gpu64" else f"Multi-Core CPU ({int(cpu_limit*100)}% cores)"
    emit_status(f"Configuring parameters on {backend_label}: t={t}, mu={mu}, K={K}, N={N}×{N}, Nw={num_omega}")

    from parameters import ModelParameters
    import sweep_core

    emit_status(f"Building Hamiltonian & numerical grids on {backend_label}...")
    p = ModelParameters(
        t=t, t1=t1, mu=mu, K=K,
        N=N, num_omega=num_omega, omega_max=omega_max, eta=eta,
        solver=solver_choice,
        cpu_limit=cpu_limit
    )

    emit_status(f"Evaluating Dyson real-time FFT convolutions on {backend_label}...")

    is_jperp_sweep = ("Interlayer" in sweep_mode or "J_⊥" in sweep_mode)
    if is_jperp_sweep:
        res = sweep_core.run_J_perp_sweep(
            j_perp_values=jk_vals,
            fixed_jk=fixed_jperp,
            mu=mu,
            p=p,
            output_dir=out_plots_dir,
            use_cache=True
        )
        safe_suffix = f"atJ_K_{fixed_jperp:.1f}_mu_{mu:.1f}".replace("$", "").replace("\\", "").replace(" ", "").replace("=", "_").replace("{", "").replace("}", "").replace(",", "_").replace("/", "_")
    else:
        res = sweep_core.run_J_k_sweep(
            j_k_values=jk_vals,
            fixed_jperp=fixed_jperp,
            mu=mu,
            p=p,
            output_dir=out_plots_dir,
            use_cache=True
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

    emit_status("Spectral Sweep completed successfully.")
    emit_completed(plot_path=primary_plot, all_plots=all_plots)


def run_spectral_function_task(params: dict, out_plots_dir: str, out_data_dir: str):
    """Executes single-point Quasiparticle Spectral Function A(k, ω) calculation."""
    t = float(params.get("t", 1.0))
    t1 = float(params.get("t1", 0.0))
    mu = float(params.get("mu", 1.0))
    K = float(params.get("K", 1.0))
    N = int(params.get("N", 64))
    num_omega = int(params.get("num_omega", params.get("Nw", 2001)))
    omega_max = float(params.get("omega_max", params.get("w_max", 20.0)))
    eta = float(params.get("eta", 0.08))

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
        emit_progress(50, "Evaluating 1-Loop and 3-Loop convolutions at target k...")
        s1_re, s1_im = solver_m1.calculate_one_loop(omega, p, external_P=ext_P)
        s3_re, s3_im = solver_m3.calculate_three_loop(omega, p, external_P=ext_P)

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

    emit_progress(100, "Spectral Function calculation completed successfully.")
    emit_completed(plot_path=plot_file)


def run_worker(params: dict):
    """Dispatches requested calculation task."""
    task = params.get("task", "spectral_sweep").lower()
    emit_progress(5, f"Initializing worker for task: {task}...")

    # Default output directory: masters_thesis_gui/results
    base_out_dir = params.get("output_dir", os.path.join(GUI_ROOT, "results"))
    out_plots_dir = os.path.join(base_out_dir, "plots")
    out_data_dir = os.path.join(base_out_dir, "data")
    os.makedirs(out_plots_dir, exist_ok=True)
    os.makedirs(out_data_dir, exist_ok=True)

    try:
        if "function" in task or "a(k" in task or "spec" in task and "sweep" not in task:
            run_spectral_function_task(params, out_plots_dir, out_data_dir)
        else:
            run_spectral_sweep_task(params, out_plots_dir, out_data_dir)

    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(f"[WORKER ERROR] Solver execution failed: {e}", file=sys.stderr, flush=True)
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
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
