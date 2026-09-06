"""Centralized Smart Caching and Path Engine for Many-Body Studio Pro.

Handles:
1. Self-contained directory normalization:
   <root>/results/
       plots/   (flat figures)
       data/    (flat finished observable datasets)
       cache/   (flat reusable foundation arrays: sigma_base, chi0_static, chi0_dynamic)
2. Parameter key generation with rigorous invalidation rules:
   - Any change in (t, t1, mu, K, J_perp, N, Nw, wmax, eta) invalidates base Sigma.
   - The ONLY parameter that scales base Sigma without recomputing convolutions is J_K (J_K^2 scaling law).
   - Any change in (t, t1, mu, N) invalidates static chi0.
   - Any change in (t, t1, mu, N, Nw, eta) invalidates dynamic chi0.
3. Live cache status checking for UI badges.
4. Cache inspection and purging utilities.
"""

import os
import glob
import shutil
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List

# Default GUI repository root
STUDIO_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDIO_DIR = os.path.dirname(STUDIO_CORE_DIR)
GUI_ROOT = os.path.dirname(STUDIO_DIR)
DEFAULT_RESULTS_DIR = os.path.join(GUI_ROOT, "results")


def normalize_results_dir(target_dir: Optional[str] = None) -> Tuple[str, str, str, str]:
    """
    Normalizes and creates a self-contained results directory layout.
    
    If the user enters:
      - '.../masters_thesis_gui'        -> '.../masters_thesis_gui/results'
      - '.../masters_thesis_gui/results'-> '.../masters_thesis_gui/results'
      - '.../results/plots'             -> '.../results'
      - '' (or None)                   -> GUI_ROOT/results
      
    Ensures standard subdirectories exist:
      - results_dir/plots
      - results_dir/data
      - results_dir/cache
      
    Also auto-migrates any legacy 'results/plots/data' folder to 'results/data'.
    
    Returns:
        (results_dir, plots_dir, data_dir, cache_dir)
    """
    if not target_dir or not str(target_dir).strip():
        base = DEFAULT_RESULTS_DIR
    else:
        base = os.path.normpath(str(target_dir).strip())

    bname = os.path.basename(base).lower()
    if bname in ["plots", "data", "cache"]:
        results_dir = os.path.dirname(base)
    elif bname == "results":
        results_dir = base
    else:
        results_dir = os.path.join(base, "results")

    results_dir = os.path.normpath(results_dir)
    plots_dir = os.path.join(results_dir, "plots")
    data_dir = os.path.join(results_dir, "data")
    cache_dir = os.path.join(results_dir, "cache")

    for d in [results_dir, plots_dir, data_dir, cache_dir]:
        os.makedirs(d, exist_ok=True)

    # Clean up legacy nested 'results/plots/data' if present
    legacy_nested_data = os.path.join(plots_dir, "data")
    if os.path.isdir(legacy_nested_data):
        for fpath in glob.glob(os.path.join(legacy_nested_data, "*")):
            dest = os.path.join(data_dir, os.path.basename(fpath))
            if not os.path.exists(dest):
                try:
                    shutil.move(fpath, dest)
                except Exception:
                    pass
        try:
            os.rmdir(legacy_nested_data)
        except Exception:
            pass

    return results_dir, plots_dir, data_dir, cache_dir


def get_ibz_indices_and_map(n: int):
    """
    Computes the 1/8th Irreducible Brillouin Zone (IBZ) coordinates and 
    a fast full-BZ reconstruction lookup table for C4v square lattice symmetry.
    Wedge: 0 <= j <= i <= n // 2.
    """
    half_n = n // 2
    ibz_coords = []
    coord_to_idx = {}
    idx = 0
    for i in range(half_n + 1):
        for j in range(i + 1):
            ibz_coords.append((i, j))
            coord_to_idx[(i, j)] = idx
            idx += 1

    full_to_ibz = np.zeros((n, n), dtype=np.int32)
    for i in range(n):
        i_f = min(i, (n - i) % n)
        for j in range(n):
            j_f = min(j, (n - j) % n)
            full_to_ibz[i, j] = coord_to_idx[(max(i_f, j_f), min(i_f, j_f))]

    rows = [c[0] for c in ibz_coords]
    cols = [c[1] for c in ibz_coords]
    return rows, cols, full_to_ibz


def mask_mantissa_8(arr_f32: np.ndarray) -> np.ndarray:
    """Zeroes out the lowest 8 bits of float32 mantissa (Bit-Grooming)."""
    u32 = np.ascontiguousarray(arr_f32).view(np.uint32)
    return (u32 & np.uint32(0xFFFFFF00)).view(np.float32)


def byte_shuffle_f32(arr: np.ndarray) -> np.ndarray:
    """Byte-shuffles a float32 array into transposed uint8 memory stream."""
    u8 = np.ascontiguousarray(arr).view(np.uint8).reshape(-1, 4)
    return np.ascontiguousarray(u8.T)


def byte_unshuffle_f32(u8_transposed: np.ndarray, shape: tuple) -> np.ndarray:
    """Reconstructs float32 array from byte-shuffled uint8 stream."""
    u8_2d = np.ascontiguousarray(u8_transposed.T)
    return np.ascontiguousarray(u8_2d).view(np.float32).reshape(shape)


class LazyIBZArray:
    """
    Zero-copy / lazy reconstruction wrapper for 1/8th IBZ self-energy arrays.
    Avoids expanding (Nw, N, N) into multiple gigabytes of memory, enabling instantaneous
    cache loading (< 200ms) and silky-smooth interactive parameter sweeps with minimal RAM.
    """
    def __init__(self, arr_ibz: np.ndarray, full_to_ibz: np.ndarray, n: int):
        self._arr = arr_ibz  # shape: (Nw, num_ibz)
        self._map = full_to_ibz  # shape: (n, n)
        self.shape = (arr_ibz.shape[0], n, n)
        self.ndim = 3
        self.dtype = arr_ibz.dtype
        self.nbytes = arr_ibz.nbytes

    def reshape(self, *shape):
        if len(shape) == 1 and isinstance(shape[0], (tuple, list)):
            shape = tuple(shape[0])
        if shape == self.shape:
            return self
        return np.asarray(self).reshape(shape)

    def __array__(self, dtype=None):
        arr = self._arr[:, self._map]
        return arr.astype(dtype) if dtype is not None else arr

    def __len__(self):
        return self.shape[0]

    def __getitem__(self, key):
        if isinstance(key, tuple):
            if len(key) == 3:
                w_sel, ikx, iky = key
                if isinstance(ikx, (int, np.integer)) and isinstance(iky, (int, np.integer)):
                    return self._arr[w_sel, self._map[ikx, iky]]
                elif isinstance(w_sel, (int, np.integer)):
                    sub_map = self._map[ikx, iky]
                    return self._arr[w_sel, sub_map]
                else:
                    sub_map = self._map[ikx, iky]
                    return self._arr[w_sel][:, sub_map]
            elif len(key) == 2:
                sub_map = self._map[key[1]]
                return self._arr[key[0], sub_map]
            elif len(key) == 1:
                return self.__getitem__(key[0])
        elif isinstance(key, (int, np.integer)):
            return self._arr[key, self._map]
        elif isinstance(key, slice):
            return self._arr[key][:, self._map]

        return np.asarray(self)[key]

    def __mul__(self, other):
        return np.asarray(self) * other

    def __rmul__(self, other):
        return other * np.asarray(self)


def inspect_cache_foundation(fpath: str) -> dict:
    """
    Lightweight metadata inspector for cache foundations.
    Detects whether an array is stored as 8-bit bit-groomed, 1/8th IBZ, or legacy full BZ.
    """
    if not os.path.isfile(fpath):
        return {"exists": False}
    try:
        with np.load(fpath) as d:
            is_ibz = bool(d.get("is_ibz", False))
            is_shuffled = bool(d.get("is_shuffled", False))
            is_bitgroomed = bool(d.get("is_bitgroomed", False))
            bitgroom_bits = int(d.get("bitgroom_bits", 8)) if is_bitgroomed else 0

            if is_shuffled and "shape" in d:
                dt = "float32 (groomed)" if is_bitgroomed else "float32 (shuffled)"
                shape = tuple(d["shape"])
            elif "sig_re" in d:
                dt = str(d["sig_re"].dtype)
                shape = tuple(d["sig_re"].shape)
            elif "sig1_re" in d:
                dt = str(d["sig1_re"].dtype)
                shape = tuple(d["sig1_re"].shape)
            else:
                dt = "unknown"
                shape = ()

            if is_bitgroomed:
                fmt = f"1/8th IBZ ({bitgroom_bits}-bit Groomed)"
            elif is_ibz:
                fmt = "1/8th IBZ (C4v compressed)"
            else:
                fmt = "Legacy Full BZ"

            return {
                "exists": True,
                "is_ibz": is_ibz,
                "is_shuffled": is_shuffled,
                "is_bitgroomed": is_bitgroomed,
                "bitgroom_bits": bitgroom_bits,
                "dtype": dt,
                "shape": shape,
                "format": fmt
            }
    except Exception:
        return {"exists": True, "is_ibz": False, "dtype": "unknown", "format": "Legacy NPZ"}


# ==============================================================================
# PARAMETER-PRECISE CACHE KEY FILENAMES
# ==============================================================================

def get_sigma_base_filename(
    fixed_jperp: float,
    t: float = 1.0,
    t1: float = 0.0,
    mu: float = 1.0,
    K: float = 1.0,
    N: int = 64,
    num_omega: int = 2001,
    omega_max: float = 20.0,
    eta: float = 0.08,
    ext_P: Optional[Tuple[int, int]] = None
) -> str:
    """
    Generates deterministic filename for base self-energy computed at J_K = 1.0.
    Includes all physical and numerical parameters: t, t1, mu, K, J_perp, N, Nw, wmax, eta.
    Any change in eta or other grid/Hamiltonian parameter invalidates the cache.
    """
    p_tag = f"point_{ext_P[0]}_{ext_P[1]}" if ext_P is not None else "full_bz"
    return (
        f"sigma_base_{p_tag}_Jperp_{float(fixed_jperp):.2f}"
        f"_t_{float(t):.2f}_t1_{float(t1):.2f}_mu_{float(mu):.2f}_K_{float(K):.2f}"
        f"_N_{int(N)}_Nw_{int(num_omega)}_wmax_{float(omega_max):.1f}_eta_{float(eta):.4f}.npz"
    )


def get_chi0_static_filename(
    N: int = 256,
    mu: float = 1.0,
    t: float = 1.0,
    t1: float = 0.0
) -> str:
    """Bare static bubble chi0(q, w=0). Non-interacting; independent of J_perp, J_K, K, and eta."""
    return f"chi0_static_N{int(N)}_mu{float(mu):.2f}_t{float(t):.2f}_t1_{float(t1):.2f}.npz"


def get_chi0_dynamic_filename(
    N: int = 64,
    mu: float = 1.0,
    t: float = 1.0,
    t1: float = 0.0,
    num_omega: int = 600,
    eta: float = 0.01
) -> str:
    """Bare dynamic bubble chi0(q, w). Depends on N, mu, t, t1, Nw, and eta."""
    return f"chi0_dynamic_N{int(N)}_mu{float(mu):.2f}_t{float(t):.2f}_t1_{float(t1):.2f}_w{int(num_omega)}_eta{float(eta):.4f}.npz"


def get_spectral_sweep_filename(
    mode: str,
    sweep_vals: List[float],
    fixed_val: float,
    t: float = 1.0,
    t1: float = 0.0,
    mu: float = 1.0,
    K: float = 1.0,
    N: int = 64,
    num_omega: int = 2001,
    eta: float = 0.08
) -> str:
    """Finished observable dataset for Spectral Sweep."""
    sweep_str = "_".join(f"{float(x):.2f}" for x in sweep_vals)
    prefix = "sweep_JK" if mode == "JK" else "sweep_Jperp"
    fixed_tag = f"Jperp_{float(fixed_val):.2f}" if mode == "JK" else f"JK_{float(fixed_val):.2f}"
    return (
        f"{prefix}_vals_{sweep_str}_{fixed_tag}"
        f"_t_{float(t):.2f}_t1_{float(t1):.2f}_mu_{float(mu):.2f}_K_{float(K):.2f}"
        f"_N_{int(N)}_Nw_{int(num_omega)}_eta_{float(eta):.4f}.npz"
    )


# ==============================================================================
# CACHE LOOKUP HELPERS
# ==============================================================================

def find_cached_sigma_base(
    cache_dir: str,
    fixed_jperp: float,
    t: float = 1.0,
    t1: float = 0.0,
    mu: float = 1.0,
    K: float = 1.0,
    N: int = 64,
    num_omega: int = 2001,
    omega_max: float = 20.0,
    eta: float = 0.08,
    ext_P: Optional[Tuple[int, int]] = None
) -> Optional[str]:
    """Looks for a matching base self-energy array in results/cache/."""
    fname = get_sigma_base_filename(
        fixed_jperp=fixed_jperp, t=t, t1=t1, mu=mu, K=K,
        N=N, num_omega=num_omega, omega_max=omega_max, eta=eta,
        ext_P=ext_P
    )
    target = os.path.join(cache_dir, fname)
    if os.path.isfile(target) and os.path.getsize(target) > 0:
        return target
    return None


def find_cached_chi0(
    cache_dir: str,
    data_dir: str,
    dynamic: bool = False,
    N: int = 64,
    mu: float = 1.0,
    t: float = 1.0,
    t1: float = 0.0,
    num_omega: int = 600,
    eta: float = 0.01
) -> Optional[str]:
    """
    Looks for bare bubble chi0 in cache_dir (primary) or data_dir (backward-compatibility).
    """
    fname = (
        get_chi0_dynamic_filename(N=N, mu=mu, t=t, t1=t1, num_omega=num_omega, eta=eta)
        if dynamic else
        get_chi0_static_filename(N=N, mu=mu, t=t, t1=t1)
    )
    for d in [cache_dir, data_dir]:
        p = os.path.join(d, fname)
        if os.path.isfile(p) and os.path.getsize(p) > 0:
            return p
    return None


# ==============================================================================
# UI LIVE STATUS INSPECTOR
# ==============================================================================

def check_cache_status(study: str, params: dict, out_dir: Optional[str] = None) -> dict:
    """
    Inspects disk to determine the computation state for the active parameters:
      - 'full': 100% computed, finished observable ready in data/.
      - 'foundation': Reusable foundation (Base Sigma or chi_0) ready in cache/; compute will be fast.
      - 'cold': Cold compute needed.
    
    Returns:
      {
         "state": "full" | "foundation" | "cold",
         "badge_text": str,
         "badge_color": "#16a34a" | "#0891b2" | "#64748b",
         "details": str,
         "foundation_file": Optional[str],
         "data_file": Optional[str]
      }
    """
    results_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(out_dir)

    t = float(params.get("t", 1.0))
    t1 = float(params.get("t1", 0.0))
    mu = float(params.get("mu", 1.0))
    K = float(params.get("K", 1.0))
    N = int(params.get("N", 64))
    num_omega = int(params.get("num_omega", params.get("Nw", 2001)))
    omega_max = float(params.get("omega_max", params.get("w_max", 20.0)))
    eta = float(params.get("eta", 0.08))

    study_clean = str(study).lower()

    # 1. ELECTRICAL CONDUCTIVITY SWEEP (Checked before generic 'sweep')
    if "cond" in study_clean or "conductivity" in study_clean or "sigma" in study_clean:
        cond_mode_raw = str(params.get("cond_sweep_mode", params.get("sweep_mode", "Kondo Coupling (J_K)")))
        is_jk_sweep = not ("interlayer" in cond_mode_raw.lower() or "j_perp" in cond_mode_raw.lower() or "j_⊥" in cond_mode_raw.lower())
        if is_jk_sweep:
            fixed_jperp = float(params.get("fixed_jperp", 6.0))
            base_file = find_cached_sigma_base(
                cache_dir=cache_dir, fixed_jperp=fixed_jperp,
                t=t, t1=t1, mu=mu, K=K, N=N, num_omega=num_omega, omega_max=omega_max, eta=eta
            )
            if base_file:
                meta = inspect_cache_foundation(base_file)
                ibz_tag = " (8-bit Groomed)" if meta.get("is_bitgroomed") else (" (1/8th IBZ)" if meta.get("is_ibz") else "")
                return {
                    "state": "foundation",
                    "badge_text": f"⚡ Base Σ Cached{ibz_tag} (Fast Kubo Integration)",
                    "badge_color": "#0891b2",
                    "details": f"Base self-energy ({os.path.basename(base_file)}) cached in results/cache/. Fast Kubo bubble integration across sweep points.",
                    "foundation_file": base_file,
                    "data_file": None
                }

            return {
                "state": "cold",
                "badge_text": "⚙️ Base Σ Missing: Convolutions Required",
                "badge_color": "#64748b",
                "details": f"Base self-energy for J_⊥={fixed_jperp:.2f}, μ={mu:.2f}, N={N} not found in results/cache/. Convolutions will be computed once and cached before Kubo sweep.",
                "foundation_file": None,
                "data_file": None
            }
        else:
            return {
                "state": "cold",
                "badge_text": "⚙️ J_⊥ Sweep: Convolutions Per Point",
                "badge_color": "#64748b",
                "details": "J_⊥ sweep requires independent base self-energy computations for each J_⊥ value in results/cache/.",
                "foundation_file": None,
                "data_file": None
            }

    # 2. SPECTRAL SWEEP
    elif "spectral" in study_clean or study_clean == "spectral_sweep" or ("sweep" in study_clean and "susc" not in study_clean):
        sweep_mode_raw = str(params.get("sweep_mode", "Kondo Coupling (J_K)"))
        is_jk_sweep = not ("Interlayer" in sweep_mode_raw or "J_perp" in sweep_mode_raw or "J_⊥" in sweep_mode_raw)
        fixed_jperp = float(params.get("fixed_jperp", 6.0))
        sweep_vals = params.get("jk_values", [3.0, 6.0, 9.0])
        if isinstance(sweep_vals, str):
            try:
                sweep_vals = [float(x.strip()) for x in sweep_vals.split(",") if x.strip()]
            except Exception:
                sweep_vals = [3.0, 6.0, 9.0]

        # Check full finished observable
        obs_name = get_spectral_sweep_filename(
            mode="JK" if is_jk_sweep else "Jperp",
            sweep_vals=sweep_vals,
            fixed_val=fixed_jperp,
            t=t, t1=t1, mu=mu, K=K, N=N, num_omega=num_omega, eta=eta
        )
        obs_path = os.path.join(data_dir, obs_name)
        if os.path.isfile(obs_path) and os.path.getsize(obs_path) > 0:
            return {
                "state": "full",
                "badge_text": "⚡ 100% Cached (Instant Load)",
                "badge_color": "#16a34a",
                "details": f"Observable dataset {obs_name} already available in data/",
                "foundation_file": None,
                "data_file": obs_path
            }

        # Check foundation (Base Sigma) for J_K sweep
        if is_jk_sweep:
            base_file = find_cached_sigma_base(
                cache_dir=cache_dir, fixed_jperp=fixed_jperp,
                t=t, t1=t1, mu=mu, K=K, N=N, num_omega=num_omega, omega_max=omega_max, eta=eta
            )
            if base_file:
                meta = inspect_cache_foundation(base_file)
                if meta.get("is_bitgroomed"):
                    ibz_tag = " (8-bit Groomed)"
                elif meta.get("is_ibz"):
                    ibz_tag = " (1/8th IBZ)"
                else:
                    ibz_tag = ""
                fmt_desc = meta.get("format", "Foundation")
                return {
                    "state": "foundation",
                    "badge_text": f"⚡ Base Σ Cached{ibz_tag} (Fast J_K Scaling)",
                    "badge_color": "#0891b2",
                    "details": f"Base self-energy ({fmt_desc}) in results/cache/. Fast analytical J_K² scaling on Full BZ.",
                    "foundation_file": base_file,
                    "data_file": None
                }

        return {
            "state": "cold",
            "badge_text": "⚙️ No Cache: Full Computation Needed",
            "badge_color": "#64748b",
            "details": "No cache found. Full 1-loop & 3-loop convolutions will be computed.",
            "foundation_file": None,
            "data_file": None
        }

    # 2. QUASIPARTICLE SPECTRAL FUNCTION
    elif "function" in study_clean or "spec" in study_clean:
        mom_str = params.get("spec_momentum", "Antinodal k_F (π, 0)")
        if "Antinodal" in mom_str: mult_x, mult_y = 1.0, 0.0
        elif "Nodal" in mom_str: mult_x, mult_y = 0.5, 0.5
        elif "Corner" in mom_str: mult_x, mult_y = 1.0, 1.0
        elif "Center" in mom_str: mult_x, mult_y = 0.0, 0.0
        else: mult_x, mult_y = 1.0, 0.0

        ix = int(round((mult_x * np.pi / (2.0 * np.pi)) * N)) % N
        iy = int(round((mult_y * np.pi / (2.0 * np.pi)) * N)) % N
        fixed_coupling = float(params.get("spec_fixed_coupling", 6.0))
        spec_mode = params.get("spec_sweep_mode", "JK")
        is_jk = "JK" in spec_mode or "Kondo" in spec_mode

        if is_jk:
            base_file = find_cached_sigma_base(
                cache_dir=cache_dir, fixed_jperp=fixed_coupling,
                t=t, t1=t1, mu=mu, K=K, N=N, num_omega=num_omega, omega_max=omega_max, eta=eta,
                ext_P=(ix, iy)
            )
            if base_file:
                return {
                    "state": "foundation",
                    "badge_text": "⚡ Point Σ Cached (Instant Scaling)",
                    "badge_color": "#0891b2",
                    "details": f"Single-point self-energy at P=({ix},{iy}) cached in results/cache/.",
                    "foundation_file": base_file,
                    "data_file": None
                }

        return {
            "state": "cold",
            "badge_text": "⚙️ No Cache: Full Computation Needed",
            "badge_color": "#64748b",
            "details": f"No cache found. Computing single-point Dyson convolution at P=({ix},{iy}).",
            "foundation_file": None,
            "data_file": None
        }

    # 3. PHASE DIAGRAM
    elif "phase" in study_clean or "diagram" in study_clean:
        k_tag = "AFM" if K > 0 else "FM"
        pd_name = f"phase_diagram_mu{mu:.2f}_{k_tag}.npz"
        pd_path = os.path.join(data_dir, pd_name)
        if os.path.isfile(pd_path) and os.path.getsize(pd_path) > 0:
            return {
                "state": "full",
                "badge_text": "⚡ 100% Cached (Instant Load)",
                "badge_color": "#16a34a",
                "details": f"Phase diagram dataset {pd_name} already in data/",
                "foundation_file": None,
                "data_file": pd_path
            }

        chi0_file = find_cached_chi0(cache_dir, data_dir, dynamic=False, N=N, mu=mu, t=t, t1=t1)
        if chi0_file:
            return {
                "state": "foundation",
                "badge_text": "⚡ Bare χ₀ Cached (Fast Bisection)",
                "badge_color": "#0891b2",
                "details": f"Bare static bubble found at {os.path.basename(chi0_file)}. Bisection only.",
                "foundation_file": chi0_file,
                "data_file": None
            }

        return {
            "state": "cold",
            "badge_text": "⚙️ No Cache: Full Computation Needed",
            "badge_color": "#64748b",
            "details": f"No cache found. Bare static bubble χ₀(q) will be computed on {N}×{N} grid, then cached.",
            "foundation_file": None,
            "data_file": None
        }

    # 4. SUSCEPTIBILITY
    elif "susc" in study_clean or "rpa" in study_clean:
        run_static = bool(params.get("run_static", True))
        run_dynamic = bool(params.get("run_dynamic", True))
        fixed_J = float(params.get("fixed_J", 6.0))
        fixed_str = f"fixed_J_{fixed_J}"
        fname_base = f"sweep_JK_{fixed_str}_mu_{mu:.2f}"
        static_data = os.path.join(data_dir, f"{fname_base}_static.npz")
        dynamic_data = os.path.join(data_dir, f"{fname_base}_dynamic.npz")

        has_static = (not run_static) or (os.path.isfile(static_data) and os.path.getsize(static_data) > 0)
        has_dynamic = (not run_dynamic) or (os.path.isfile(dynamic_data) and os.path.getsize(dynamic_data) > 0)

        if has_static and has_dynamic:
            return {
                "state": "full",
                "badge_text": "⚡ 100% Cached (Instant Load)",
                "badge_color": "#16a34a",
                "details": "Finished RPA observable datasets available in data/",
                "foundation_file": None,
                "data_file": static_data if os.path.isfile(static_data) else dynamic_data
            }

        # Check foundations
        has_c_stat = find_cached_chi0(cache_dir, data_dir, dynamic=False, N=N, mu=mu, t=t, t1=t1) is not None
        has_c_dyn = find_cached_chi0(cache_dir, data_dir, dynamic=True, N=N, mu=mu, t=t, t1=t1, num_omega=num_omega, eta=eta) is not None

        if (run_static and has_c_stat) or (run_dynamic and has_c_dyn):
            return {
                "state": "foundation",
                "badge_text": "⚡ Bare χ₀ Cached (Fast RPA Sweep)",
                "badge_color": "#0891b2",
                "details": "Bare bubble foundation found in results/cache/. Fast RPA algebraic inversion only.",
                "foundation_file": has_c_stat or has_c_dyn,
                "data_file": None
            }

        return {
            "state": "cold",
            "badge_text": "⚙️ No Cache: Full Computation Needed",
            "badge_color": "#64748b",
            "details": "No cache found. Bare bubble χ₀ array must be computed before RPA sweep.",
            "foundation_file": None,
            "data_file": None
        }

    # 5. ELECTRICAL CONDUCTIVITY SWEEP
    elif "cond" in study_clean or "conductivity" in study_clean or "sigma" in study_clean:
        fixed_jperp = float(params.get("fixed_jperp", 6.0))
        base_file = find_cached_sigma_base(
            cache_dir=cache_dir, fixed_jperp=fixed_jperp,
            t=t, t1=t1, mu=mu, K=K, N=N, num_omega=num_omega, omega_max=omega_max, eta=eta
        )
        if base_file:
            meta = inspect_cache_foundation(base_file)
            ibz_tag = " (8-bit Groomed)" if meta.get("is_bitgroomed") else (" (1/8th IBZ)" if meta.get("is_ibz") else "")
            return {
                "state": "foundation",
                "badge_text": f"⚡ Base Σ Cached{ibz_tag} (Fast Kubo Integration)",
                "badge_color": "#0891b2",
                "details": "Base self-energy cached in results/cache/. Fast Kubo bubble integration across sweep points.",
                "foundation_file": base_file,
                "data_file": None
            }

        return {
            "state": "cold",
            "badge_text": "⚙️ Base Σ Missing: Convolutions Required",
            "badge_color": "#64748b",
            "details": "Base self-energy not found. Convolutions will be computed once and cached before Kubo sweep.",
            "foundation_file": None,
            "data_file": None
        }

    return {
        "state": "cold",
        "badge_text": "⚙️ No Cache: Full Computation Needed",
        "badge_color": "#64748b",
        "details": "No cache found. Full computation required.",
        "foundation_file": None,
        "data_file": None
    }


# ==============================================================================
# CACHE MANAGEMENT (STATS & PURGE)
# ==============================================================================

def get_cache_stats(out_dir: Optional[str] = None) -> dict:
    """
    Returns inventory and total size of reusable arrays in results/cache/.
    """
    results_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(out_dir)
    items = []
    total_bytes = 0

    if os.path.isdir(cache_dir):
        for f in sorted(os.listdir(cache_dir)):
            full_p = os.path.join(cache_dir, f)
            if os.path.isfile(full_p) and f.endswith(".npz"):
                sz = os.path.getsize(full_p)
                total_bytes += sz
                sz_str = f"{sz / 1024:.1f} KB" if sz < 1024 * 1024 else f"{sz / (1024 * 1024):.2f} MB"
                items.append({
                    "name": f,
                    "path": full_p,
                    "size_bytes": sz,
                    "size_str": sz_str,
                    "mtime": os.path.getmtime(full_p)
                })

    if total_bytes < 1024 * 1024:
        size_fmt = f"{total_bytes / 1024:.1f} KB"
    else:
        size_fmt = f"{total_bytes / (1024 * 1024):.1f} MB"

    return {
        "cache_dir": cache_dir,
        "results_dir": results_dir,
        "total_files": len(items),
        "total_bytes": total_bytes,
        "formatted_size": size_fmt,
        "items": items
    }


def purge_cache(out_dir: Optional[str] = None, pattern: str = "*.npz") -> int:
    """
    Deletes reusable cache arrays matching pattern in results/cache/.
    Does NOT delete finished plots or observable data datasets.
    Returns number of files deleted.
    """
    results_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(out_dir)
    deleted_count = 0
    if os.path.isdir(cache_dir):
        for fpath in glob.glob(os.path.join(cache_dir, pattern)):
            try:
                os.remove(fpath)
                deleted_count += 1
            except Exception:
                pass
    return deleted_count
