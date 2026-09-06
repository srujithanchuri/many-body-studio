# Many-Body Physics Studio Pro • Alpha v4

Modern, high-performance scientific desktop workbench for strongly correlated quantum heterostructures. Built with PySide6 (Qt6), isolated `QProcess` execution bridges, native multi-backend GPU/CPU physics engines, 1/8th IBZ cache optimization, Numba JIT parallel acceleration, balanced and fixed panel layouts, and an interactive dual-perspective analytical architecture.

---

## Key Features

### 1. Unified Simulation Studio & Dual Viewports
- **Simulation Studio**:
  - Configure Hamiltonians, launch asynchronous simulations, monitor live progress via an isolated subprocess `CalculationBridge`, and inspect raw numerical arrays in a hardware-accelerated interactive canvas.
  - **Balanced Ergonomic Layout**: Rigidly proportioned $350\text{ px}$ Parameter Inspector dock paired with a spacious $\sim 730\text{ px}$ central canvas, ensuring un-cramped toolbars and comfortable controls across all screen resolutions (down to $1366\times 768$).
- **Integrated Dual Viewports & Plot Gallery**:
  - **Dual Viewports**: Switch instantaneously between CAD **Plot Viewer** (with pan/zoom, coordinate probing, and direct PNG export) and real-time **Interactive Plots**.
  - **Visual Gallery Browser**: Integrated in the left Navigator dock with grid and compact list views, metadata badges, parameter search, and instant file-system synchronization.
  - *(Note: Standalone Figure Composer workspace has been scrapped in favor of direct integrated viewports).*

### 2. Full 5-Mode Modular Interactive Plots (Live Analytical Studio)
- **Spectral Function $[A(\mathbf{k}, \omega)]$**:
  - Probes $A(\mathbf{k}, \omega)$, $\text{Re }\Sigma$, and $\text{Im }\Sigma$ at any arbitrary Brillouin Zone momentum. Defaults to the antinodal point $\mathbf{k} = (\pi, 0)$ with interactive high-symmetry and custom coordinate pickers.
- **Fermi Surface & DOS $[A(\mathbf{k}, \omega)]$**:
  - Side-by-side visualization: 2D Brillouin Zone contour $A(\mathbf{k}, \omega = \omega_{\text{slice}})$ with multi-point coordinate pinning alongside the full integrated Density of States $\rho(\omega) = \frac{1}{N^2} \sum_{\mathbf{k}} A(\mathbf{k}, \omega)$ with click-to-slice navigation.
- **Band Dispersion along High-Symmetry Path**:
  - Full-range quasiparticle band structure $A(\mathbf{k}, \omega)$ mapped across $\Gamma \to X \to M \to \Gamma$, matched to the authoritative source aspect ratio ($6.2 : 4.8$) with attached vertical colorbar.
- **Static Susceptibility $[\chi_{\text{RPA}}(\mathbf{q})]$**:
  - Real-time 2D magnetic susceptibility intensity maps across the Brillouin Zone with live interactive $J_K$, $J_\perp \in [4.01, 12.00]$, and $K$ (+1 AFM / -1 FM) controls.
- **Dynamic Susceptibility $[-\text{Im}\chi(\mathbf{q}, \omega)]$ along Path**:
  - Real-time frequency-momentum dynamical susceptibility colormaps computed via vectorized RPA, featuring live triplon mode tracking $\Omega(\mathbf{q}) = J_\perp \sqrt{1 + \frac{4K}{J_\perp}\gamma(\mathbf{q})}$ with continuous $J_\perp \ge 4.01$, $J_K$, and $K$ tuning.

### 3. Numba JIT Multi-Core Parallel Acceleration
- Compiled native C-kernel with `@njit(parallel=True, fastmath=True)` utilizing OpenMP (`omp`) multi-threading across all 16 CPU cores via `prange`.
- Drops full IBZ integration latency on $N=256, N_\omega=8001$ from $\sim 620\text{ ms}$ down to **$\sim 10.8\text{ ms}$** ($57\times$ speedup).
- In-place total render latency on $N=100$ runs in **$\sim 7.3\text{ ms}$** (136 FPS throughput), guaranteeing smooth, lag-free continuous slider dragging.
- 100% full mathematical resolution evaluated during dragging (no tail decimation or peak blunting), with an automatic vectorized NumPy fallback.

### 4. Smart Cache Engine & Scientific UX
- **1/8th Irreducible Brillouin Zone (IBZ) Storage**: Reduces self-energy array sizes from $\sim 2\text{ GB}$ down to $\sim 15\text{ MB}$ with lossless Bit-Grooming and byte-shuffling.
- **Zero-Copy Memory Mapping**: `LazyIBZArray` allows instant cache loading with 0 GB RAM ballooning.
- **Strict Mode-Isolated Caching**: Spectral modes show only $\Sigma$ caches; Susceptibility mode shows only $\chi_0$ caches.
- **Dual-Functionality $\mu$ Filter**: Blank by default (implying all chemical potentials), supports instant typing and dropdown selection with a single-click inline `✕` clear button.
- **Unobstructed Viewports**: Clean plot canvases with controls, parameter metadata, and tooltips cleanly placed in the control header.

### 5. Multi-Backend Physics Engine
- **NVIDIA CUDA GPU (`gpu64`)**: Hardware-accelerated CuPy FFTs and custom Numba CUDA kernels verified on NVIDIA GeForce RTX GPUs.
- **Multi-Threaded CPU (`cpu`)**: Parallel Linear Tetrahedron Method (LTM) with dynamic CPU core quota allocation (50% to 100%).

---

## Quick Launch

To run the application:

```bat
run_studio.bat
```

Or from Python in the activated virtual environment:

```powershell
.venv\Scripts\activate
python -m pyside6_studio.main
```

---

## Running Automated Tests

Run the complete 40-test suite across Tiers 1–4:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```
