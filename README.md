# Many-Body Physics Studio Pro • Alpha v3.7

Modern, high-performance scientific desktop workbench for strongly correlated quantum heterostructures. Built with PySide6 (Qt6), isolated `QProcess` execution bridges, native multi-backend GPU/CPU physics engines, 1/8th IBZ cache optimization, Numba JIT parallel acceleration, and a dual-perspective analytical architecture.

---

## Key Features

### 1. Dual-Perspective Architecture
- **Simulation Studio**:
  - Configure Hamiltonians, launch asynchronous simulations, monitor live progress via an isolated subprocess `CalculationBridge`, and inspect raw numerical arrays in a hardware-accelerated interactive canvas.
- **Visual Analysis & Publication Perspective**:
  - **Visual Gallery Browser**: Grid and compact list views, metadata badges, parameter search, and instant file-system synchronization.
  - **Live Analytical Lab**: On-the-fly physics powered by cached foundation arrays (`.npz` in `results/cache/`), enabling continuous $J_K$ and energy-slice scrubbing at 60+ FPS.

### 2. Modular Analytical Physics Modes
- **Spectral Function $[A(\mathbf{k}, \omega)]$**:
  - Probes $A(\mathbf{k}, \omega)$, $\text{Re }\Sigma$, and $\text{Im }\Sigma$ at any arbitrary Brillouin Zone momentum. Defaults to the antinodal point $\mathbf{k} = (\pi, 0)$ with interactive high-symmetry and custom coordinate pickers.
- **DOS & Fermi Surface $[A(\mathbf{k}, \omega)]$**:
  - Side-by-side visualization: 2D Brillouin Zone contour $A(\mathbf{k}, \omega = \omega_{\text{slice}})$ with multi-point coordinate pinning alongside the full integrated Density of States $\rho(\omega) = \frac{1}{N^2} \sum_{\mathbf{k}} A(\mathbf{k}, \omega)$ with click-to-slice navigation.
- **Magnetic Susceptibility $[\chi_{\text{RPA}}(\mathbf{q})]$**:
  - Real-time RPA magnetic susceptibility intensity maps $\chi_{\text{RPA}}(\mathbf{q}) = \frac{\chi_0(\mathbf{q})}{1 - U_{\text{eff}}\chi_0(\mathbf{q})}$ with dynamic instability gap tracking.

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
