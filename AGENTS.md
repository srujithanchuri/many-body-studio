# AGENTS.md: Many-Body Studio Pro [Beta v1]

> **Universal Agent Onboarding & Architecture Blueprint**  
> *Target Context*: Correlated electron physics in Metal-Mott Insulator Heterostructures.  
> *Purpose*: Read this file first in any new session to obtain an instantaneous, complete mental model of the codebase, execution pipelines, data structures, build systems, and fragile invariants without scanning individual files.

---

## 1. Project Overview & Environment

- **Domain**: High-performance computational many-body physics (Hubbard model, Kondo breakdown, Fermi surface topology, static/dynamic RPA spin susceptibility, optical/electrical conductivity).
- **Core Stack**: Python 3.12, PySide6 (Qt 6.8+), Matplotlib (`QtAgg` for interactive canvas, `Agg` for headless subprocess rendering), CuPy (CUDA 12 NVIDIA GPU acceleration), NumPy, SciPy, Numba (multi-threaded JIT).
- **Virtual Environment**: `C:\Users\sruji\Projects\masters_thesis_gui\.venv\Scripts\python.exe`
- **GUI Workspace**: `C:\Users\sruji\Projects\masters_thesis_gui`
- **Physics Backend**: `C:\Users\sruji\Projects\masters_thesis` (imported as editable packages `self_energy`, `susceptibility`, and `conductivity`).
- **Results Output Tree**:
  - `results/plots/`: Final publication figures (`.png`, `.pdf`).
  - `results/data/`: Finished numerical datasets (`.npz`).
  - `results/cache/`: Reusable computational foundations (`sigma_base_*.npz`, `chi0_static_*.npz`, `chi0_dynamic_*.npz`).

---

## 2. Complete File & Module Map

### 2.1 Root Entry Points & Launchers
- [`build_onedir_cpu.bat`](build_onedir_cpu.bat): One-click Windows batch builder for generating standalone CPU-only portable distribution folders.
- [`AGENTS.md`](AGENTS.md): This file. Authoritative agent instructions automatically injected into agent system prompt.
- [`README.md`](README.md): High-level overview of Beta v1 capabilities, 6 modular interactive modes, and caching architecture.
- [`STUDIO_ARCHITECTURE_PLAN.md`](STUDIO_ARCHITECTURE_PLAN.md): In-depth historical engineering specification, memory budgets, and benchmark records.

### 2.2 Core GUI Architecture (`pyside6_studio/`)
- [`pyside6_studio/main.py`](pyside6_studio/main.py): Application bootstrap script. Sets Windows fractional High-DPI pass-through policy (`PassThrough`), installs custom Qt message filter to suppress benign font pointSize warnings, loads multi-scale Dyson $\Sigma$ icons, and initializes `UnifiedWorkbenchWindow`.
- [`pyside6_studio/main_window.py`](pyside6_studio/main_window.py): Core `QMainWindow` application shell (`UnifiedWorkbenchWindow`).
  - Manages dual-viewport switching (Plot Viewer Mode 0 vs Interactive Plots Mode 1).
  - Coordinates Left Dock (260px dynamic stack: Plot Gallery vs Interactive Mode Navigation) and Right Dock (350px Simulation Setup).
  - Hosts 5 distinct calculation studies (`STUDY_SE`, `STUDY_SPEC`, `STUDY_PD`, `STUDY_SUSC`, `STUDY_COND`).
  - Dynamically probes GPU/CPU hardware via `get_hardware_info()`.
  - Coordinates toolbar actions, traffic-light button synchronization, and `CalculationBridge` signal routing.
  - Uses extracted `CacheManagerDialog`, study-form builders, `JobQueueWidget`, and theme helpers while retaining the controller/orchestration contract.
- [`pyside6_studio/theme.py`](pyside6_studio/theme.py): Centralized Fluent / Slate QSS stylesheet system. Contains `LIGHT_THEME_QSS`, `DARK_THEME_QSS`, and palette factories. Defines explicit `#ObjectName` selectors and widget rules.
- [`pyside6_studio/canvas.py`](pyside6_studio/canvas.py): High-DPI interactive `QGraphicsView` canvas (`InteractivePlotCanvas`). Supports smooth subpixel zoom/pan, crosshair coordinate inspection, and side-by-side split comparison views.

### 2.3 Core Configuration & Caching Engine (`pyside6_studio/core/`)
- [`pyside6_studio/core/icon_utils.py`](pyside6_studio/core/icon_utils.py): High-DPI icon loader (`get_app_icon()`). Assembles multi-resolution `QIcon` from dedicated pixel-perfect rasters (16, 20, 24, 28, 32, 40, 48, 64, 128, 256px) and `.ico` to prevent fractional scaling blur on Windows.
- [`pyside6_studio/core/cache_manager.py`](pyside6_studio/core/cache_manager.py): High-performance 1/8th Irreducible Brillouin Zone (IBZ) caching engine.
  - `normalize_results_dir()`: Canonicalizes directory structures (`results/plots`, `results/data`, `results/cache`).
  - `get_ibz_indices_and_map()`: Computes 1/8th IBZ wedge ($0 \le j \le i \le N/2$) and full-BZ reconstruction lookup table for $C_{4v}$ square lattice symmetry.
  - `mask_mantissa_8()`: Bit-grooming utility zeroing lowest 8 bits of float32 mantissa for entropy reduction.
  - `byte_shuffle_f32()` / `byte_unshuffle_f32()`: Transposes float32 memory into uint8 contiguous streams for 4x–8x lossless compression ratios.
  - `LazyIBZArray`: Zero-copy proxy wrapper for IBZ self-energy arrays, preventing gigabyte RAM inflation during sweeps.
  - `check_cache_status()`, `get_cache_stats()`, `purge_cache()`: Utilities for UI badges and cache inspection.
- [`pyside6_studio/core/hardware.py`](pyside6_studio/core/hardware.py): Hardware diagnostics probe (`get_hardware_info()`). Probes CuPy CUDA VRAM availability, device names, and multi-core CPU availability.
- [`pyside6_studio/core/config.py`](pyside6_studio/core/config.py): Global configuration constants, resolution presets (Fast Preview $64\times 64$, Standard $100\times 100$, High-Res Production $256\times 256$), and default parameter bounds.

### 2.4 IPC Backend & Execution Supervisor (`pyside6_studio/backend/`)
- [`pyside6_studio/backend/bridge.py`](pyside6_studio/backend/bridge.py): `CalculationBridge` (`QObject`).
  - Launches worker process via `QProcess` with unbuffered UTF-8 I/O.
  - Encodes parameters via Base64 JSON (`--params-b64`) to eliminate command-line character escaping issues.
  - Parses newline-delimited JSON messages from child stdout.
  - Dispatches Qt signals: `sig_started`, `sig_status`, `sig_progress`, `sig_completed`, `sig_error`, `sig_cancelled`.
- [`pyside6_studio/backend/worker_cli.py`](pyside6_studio/backend/worker_cli.py): Standalone CLI entry point executed in an isolated child process.
  - Dispatches 6 distinct computation tasks:
    1. `run_spectral_sweep_task`: full-BZ sweeps of $J_K$ or $J_\perp$ for DOS, Fermi surface, and high-symmetry path.
    2. `run_spectral_function_task`: $A(\mathbf{k},\omega)$, $\text{Re}\,\Sigma$, $\text{Im}\,\Sigma$ at designated $\mathbf{k}$-points.
    3. `run_phase_diagram_task`: bisection search for critical magnetic instability $J_K^c(\mu)$.
    4. `run_susceptibility_task`: multi-threaded static $\chi(\mathbf{q})$ and dynamic $\chi(\mathbf{q},\omega)$ sweeps.
    5. `run_conductivity_task`: optical $\sigma(\omega)$ and DC conductivity sweeps across $J_K$ or $J_\perp$.
    6. `run_foundation_cache_task`: in-situ generation of reusable foundations ($\Sigma_{\text{base}}$, $\chi_0$).
  - Flushes GPU VRAM and exits cleanly.
- [`pyside6_studio/backend/vram_cleaner.py`](pyside6_studio/backend/vram_cleaner.py): Process killer and GPU memory reclaimer. Uses `psutil` to kill entire subprocess process trees and invokes CuPy memory pool reclamation.
- [`pyside6_studio/backend/cuda_env.py`](pyside6_studio/backend/cuda_env.py): Configures CUDA environment variables and suppresses benign driver path warnings.

### 2.5 Widgets & Interactive Modes (`pyside6_studio/widgets/`)
- [`pyside6_studio/widgets/interactive_mode_nav.py`](pyside6_studio/widgets/interactive_mode_nav.py): Left Dock **Interactive Mode Navigation** panel (`InteractiveModeNavWidget`). Houses interactive cards (`InteractiveModeCard`) with selection dots (`●`) and two-way sync with the active experiment.
- [`pyside6_studio/widgets/interactive_plots.py`](pyside6_studio/widgets/interactive_plots.py): **Interactive Plots Studio** (`InteractivePlotsWidget`).
  - Real-time 60 FPS canvas with continuous $J_K$ slider (0.1 to 12.0) utilizing analytical $J_K^2$ scaling.
  - Top control bar: Cache Selector, $J_K$ slider/spinbox, Mode Selector, `▶ Compute Cache`, Send to Sweeper.
- [`pyside6_studio/widgets/interactive_modes/`](pyside6_studio/widgets/interactive_modes/):
  - `base_mode.py`: Abstract base class defining `setup_ui()`, `render()`, `fit_view()`, `on_scroll()`, `on_press()`, `on_motion()`, `on_release()`.
  - `spectral_function_mode.py`: $A(\mathbf{k},\omega)$, $\text{Re}\,\Sigma$, $\text{Im}\,\Sigma$, and full-BZ $Z(\mathbf{k})$ quasiparticle weight heatmap with interactive click-and-drag $\mathbf{k}$-probe.
  - `energy_slice_mode.py`: Dynamic constant-energy surface movie across BZ with continuous energy slider $\omega$.
  - `band_dispersion_mode.py`: Renormalized quasiparticle dispersion $E(\mathbf{k})$ along $\Gamma - X - M - \Gamma$ with self-energy corrections.
  - `rpa_susceptibility_mode.py`: Static RPA spin susceptibility $\chi_{\text{RPA}}(\mathbf{q})$ 2D map with real-time Stoner magnetic instability tracking ($1 - U \chi_0 \to 0$).
  - `dynamic_susceptibility_mode.py`: Dynamical spin susceptibility $\chi''(\mathbf{q},\omega)$ intensity map along high-symmetry path.
  - `conductivity_mode.py`: Optical / DC electrical conductivity $\sigma(\omega)$ calculation.
- [`pyside6_studio/widgets/compute_cache_dialog.py`](pyside6_studio/widgets/compute_cache_dialog.py) / [`foundation_cache_dialog.py`](pyside6_studio/widgets/foundation_cache_dialog.py): In-situ dialog spawned from `▶ Compute Cache` button in Interactive Plots.
- [`pyside6_studio/widgets/gallery_browser.py`](pyside6_studio/widgets/gallery_browser.py): Left dock visual gallery browser (`PlotGalleryWidget`). Dual display modes (Cards vs Compact List) with search/filter.
- [`pyside6_studio/widgets/dataset_explorer.py`](pyside6_studio/widgets/dataset_explorer.py): Left dock dataset inspector (`DatasetExplorerWidget`). Scans `results/data/`, displays metadata cards, and provides quick actions.

### 2.6 Physics Backend Packages (`masters_thesis/`)
- **`self_energy`**:
  - `parameters.py`: `ModelParameters` dataclass ($t, t_1, \mu, K, N, N_\omega, \omega_{\max}, \eta, \text{solver}, \text{cpu\_limit}$).
  - `sweep_core.py`: Full BZ sweeps `run_J_k_sweep`, `run_J_perp_sweep`, composite figure generation (DOS, Fermi Surface, Path).
  - `full_bz_solver.py`: 1-loop and 3-loop FFT convolution physics kernels implemented on CuPy CUDA and NumPy/SciPy.
- **`susceptibility`**:
  - `phase_diagram.py`: Root bisection solver determining critical magnetic phase boundaries ($J_K^c$ vs $\mu$).
  - `precompute_chi0.py`: Static and dynamic Lindhard bubble tensor evaluations across 2D Brillouin zone.
  - `sweeper.py`: Multi-threaded RPA susceptibility sweeps $\chi_{\text{RPA}}(\mathbf{q}, \omega) = \frac{\chi_0}{1 - U \chi_0}$.
- **`conductivity`**:
  - `parameters.py`: `ConductivityParameters` dataclass and filename formatting utilities.
  - `engine.py`: `compute_optical_conductivity`, unpacks 8-bit groomed IBZ cache arrays.
  - `solvers.py`: `compute_conductivity_cpu` (multithreaded Numba/NumPy) and `compute_conductivity_gpu` (CuPy).
  - `symmetry.py`: $C_{4v}$ IBZ integration weights (`compute_ibz_weights`, `compute_full_bz_weights`).
  - `sweeper.py`: `run_sweep` across $J_K$ or $J_\perp$ coupling values for $\sigma(\omega)$.

### 2.7 Build & Standalone Packaging (`tools/`)
- [`tools/build_icons.py`](tools/build_icons.py): Generates crisp multi-resolution icon assets (`app_icon_*.png`, `.ico`) from master SVG.
- [`tools/build_onedir_cpu.py`](tools/build_onedir_cpu.py): PyInstaller automation script generating a self-contained, CPU-only portable distribution in `dist/ManyBodyStudio/` (~350 MB).

---


## Current Refactor Layout

- `core/metadata.py` owns shared filename metadata parsing for Gallery and Dataset Explorer.
- `widgets/study_forms/` owns study-specific inspector construction.
- `widgets/job_queue.py` owns queue presentation; execution remains in `UnifiedWorkbenchWindow` and `CalculationBridge`.
- `main_window_theme.py` owns main-window dynamic theme propagation.
- `widgets/interactive_plot_controls.py` and `interactive_plot_theme.py` own Interactive Plots presentation helpers.
- `widgets/plot_card_base.py` owns shared Plot Gallery card interaction mechanics.
- `widgets/interactive_modes/` remains the numerical strategy layer; do not rewrite its physics kernels during UI debloating.
- The legacy Data Plotter / Figure Composer path has been removed.

## 3. Critical Invariants & Fragile Rules (DO NOT BREAK)

Agents modifying this codebase **must strictly preserve** these rules:

1. **Zero Compute on GUI Main Thread**:
   - Heavy physics (FFT convolutions, CuPy CUDA kernels, Dyson equation inversions, bisection sweeps, Kubo bubbles) **must never** execute in the main Qt thread.
   - All long calculations must be dispatched through `self.bridge.start_calculation(params)` (`CalculationBridge` running `worker_cli.py` via `QProcess`).
   - Communication must use newline-delimited JSON over stdout: `{"type": "status|progress|completed|error", ...}`.

2. **Left Dock Dynamic Dual-Stack Synchronization**:
   - Left Navigator Dock (`self.dock_nav`) hosts a `QStackedWidget` with two pages:
     - **Page 0 (Plot Viewer mode)**: `PlotGalleryWidget` (`self.gallery`) with title `"🖼️ Plot Gallery Browser"`.
     - **Page 1 (Interactive Plots mode)**: `InteractiveModeNavWidget` (`self.interactive_mode_nav`) with title `"🔬 Interactive Modes"`.
   - **Two-Way Synchronization**: Clicking any card in `InteractiveModeNavWidget` must switch `cb_experiment` in `InteractivePlotsWidget`, and changing the dropdown in Interactive Plots must update the active card dot (`●`) and highlight in `InteractiveModeNavWidget`.

3. **Fixed Dock Width Invariants**:
   - Left Navigator Dock (`self.dock_nav`): exactly **$260\text{ px}$** (min 240, max 320).
   - Right Inspector Dock (`self.dock_inspector`): exactly **$350\text{ px}$** (min 320, max 380).
   - Do not set expanding policies on docks that violate these bounds.

4. **Styling & Theme Discipline**:
   - **Never hardcode inline colors** (e.g. `background: white; color: black;`) in widget code.
   - Always define semantic `#ObjectName` or class selectors in [`pyside6_studio/theme.py`](pyside6_studio/theme.py) for both `LIGHT_THEME_QSS` and `DARK_THEME_QSS`.
   - When dynamically toggling `objectName` or pseudo-states at runtime, always invoke the unpolish/polish cycle:
     ```python
     widget.style().unpolish(widget)
     widget.style().polish(widget)
     widget.update()
     ```

5. **Execution "Traffic Light" Controls**:
   - `▶ Run Calculation` (`#BtnRun`): IDE Emerald Green (`#16a34a` Light / `#059669` Dark). Disabled during computation.
   - `⏹ Cancel / Stop` (`#BtnCancel`): **Vivid Red** (`#ef4444`) when active/running; **Disabled Grey** (`#f1f5f9` / `#1e293b`) when idle.
   - Always synchronize execution buttons via `self._update_execution_buttons(is_running=True/False)`.

6. **Wheel Scroll Redirection**:
   - All parameter panels must use `WheelScrollRedirectFilter`. This prevents accidental value drift on spinboxes and comboboxes while the user vertically scrolls through parameter panels.

7. **Process Lifecycle & GPU VRAM Cleanliness**:
   - Always use 2-stage cancellation: soft SIGINT/SIGTERM followed by hard process tree kill (`kill_process_tree(pid)`).
   - After child process completion or cancellation, always trigger `flush_gpu_vram()` to ensure CuPy memory pool releases allocated VRAM back to the OS.

---

## 4. Data Flow & Interface Contracts

### 4.1 Calculation Dispatch Pipeline
```text
User Action (Click '▶ Run Calculation' or '▶ Compute Cache')
  │
  ├── 1. Parameters gathered from UI into dictionary:
  │      {
  │        "study_type": "spectral_sweep" | "spectral_function" | "phase_diagram" | "susceptibility" | "conductivity" | "foundation_cache",
  │        "t": 1.0, "t1": 0.0, "mu": 1.0, "K": 1.0, "J_perp": 6.0,
  │        "jk_values": [3.0, 6.0, 9.0], "solver_choice": "gpu" | "cpu",
  │        "N": 64, "Nw": 2001, "w_max": 20.0, "eta": 0.08,
  │        "results_dir": "C:/Users/.../results", "force_recompute": False
  │      }
  │
  ├── 2. CalculationBridge serializes payload:
  │      b64_params = base64.b64encode(json.dumps(params).encode()).decode()
  │
  ├── 3. QProcess spawned:
  │      python -u pyside6_studio/backend/worker_cli.py --params-b64 <b64_params>
  │
  ├── 4. Real-time stdout stream parsed line-by-line:
  │      {"type": "status", "phase": "running", "message": "Evaluating Convolutions / Bubbles..."}
  │      ↳ Triggers CalculationBridge.sig_status -> MainWindow status bar / progress bar
  │
  └── 5. Completion emitted on stdout:
         {"type": "completed", "success": true, "plot_path": "...", "data_path": "...", "all_plots": [...]}
         ↳ Triggers CalculationBridge.sig_completed -> Loads plots into Plot Viewer & Left Gallery
```

### 4.2 Smart Caching & 1/8th IBZ Storage Architecture
- **Analytical $J_K^2$ Scaling Law**:
  $$\Sigma(J_K, \mathbf{k}, \omega) = J_K^2 \cdot \Sigma_{\text{base}}(\mathbf{k}, \omega)$$
  Changing $J_K$ does **not** require recomputing convolutions. It scales the precomputed foundation array instantly in $<1\text{ ms}$ at 60 FPS.
- **Cache Invalidation Rules**:
  - $\Sigma_{\text{base}}$ ($J_K=1.0$): Invalidated if any of $(t, t_1, \mu, K, J_\perp, N, N_\omega, \omega_{\max}, \eta)$ change.
  - $\chi_{0,\text{static}}$: Invalidated if any of $(t, t_1, \mu, N)$ change.
  - $\chi_{0,\text{dynamic}}$: Invalidated if any of $(t, t_1, \mu, N, N_\omega, \eta)$ change.
- **Storage Layout in `results/cache/`**:
  - `sigma_base_*.npz`: Contains `sigma_ibz` (1/8th IBZ slice), `omega`, `full_to_ibz` (mapping index table), and parameter metadata.
  - Loaded via `LazyIBZArray`: Reconstructs full BZ on demand without holding multi-gigabyte dense arrays in RAM.
  - Bit-grooming masks lowest 8 mantissa bits of float32; byte-shuffling groups contiguous exponent and mantissa bytes for 4x–8x lossless compression.

---

## 5. Viewport Architecture

The central widget is a unified simulation studio with dual analytical viewports toggled via the central header bar (`self.set_canvas_mode(0 | 1)`):

### 5.1 `[ 📊 Plot Viewer ]` (Mode 0)
- Hardware-accelerated CAD zoom/pan canvas (`InteractivePlotCanvas`).
- Active Plot selector dropdown, Reset Zoom, Copy to Clipboard, Export, and Open Output Folder buttons.
- Side-by-side comparison splitter (`canvas_left` and `canvas_right`).
- Synchronized with Left Dock `PlotGalleryWidget`.

### 5.2 `[ ⚡ Interactive Plots ]` (Mode 1)
- High-speed interactive research workbench (`InteractivePlotsWidget`).
- Synchronized with Left Dock `InteractiveModeNavWidget` cards:
  1. **Quasiparticle Spectral Function $A(\mathbf{k},\omega)$**: Real-time spectral density with interactive $\mathbf{k}$-point crosshair click-and-probe and $Z(\mathbf{k})$ weight map.
  2. **Energy Slices (Fermi Surface Movie)**: Constant-energy contours across BZ with smooth $\omega$-slider scrub.
  3. **Band Dispersion $E(\mathbf{k})$**: Quasiparticle dispersions along $\Gamma-X-M-\Gamma$ path.
  4. **Static Spin Susceptibility $\chi_{\text{RPA}}(\mathbf{q})$**: 2D momentum map with Stoner instability alert ($1 - U \chi_0 \to 0$).
  5. **Dynamic Spin Susceptibility $\chi''(\mathbf{q},\omega)$**: Fluctuation intensity maps along high-symmetry path.
  6. **Electrical Conductivity $\sigma(\omega)$**: Optical/DC conductivity curves across frequency.
- **Header Controls**:
  - *Cache Dropdown*: Displays available foundation arrays with concise parameter badges (e.g. `Σ (μ=0.0, J⊥=6.0, K=1.0, N=100)`).
  - *Continuous $J_K$ Slider & Spinbox*: Analytical 60 FPS scaling from 0.1 to 12.0.
  - *`▶ Compute Cache` Button*: Spawns `ComputeCacheDialog` for instant in-situ foundation generation.
  - *Send to Sweeper*: Transfers current interactive parameters into the Right Dock Simulation Setup.

---

## 6. Standalone Distribution & Packaging (`tools/build_onedir_cpu.py`)

Many-Body Studio includes an automated PyInstaller pipeline to build a fully self-contained, portable Windows application:

```powershell
# Build standalone CPU-only distribution:
build_onedir_cpu.bat
# Or directly via Python:
.venv\Scripts\python.exe tools/build_onedir_cpu.py
```

### Packaging Architecture & Invariants:
1. **Lightweight Footprint (~350 MB)**:
   - Excludes CuPy, PyTorch, CUDA runtime drivers (`--exclude-module cupy`, `--exclude-module torch`).
   - Bundles optimized NumPy, SciPy, Numba multithreaded JIT, and Matplotlib.
2. **Resource Harvesting**:
   - Collects all multi-scale Dyson $\Sigma$ icons from `pyside6_studio/resources/icons`.
   - Embeds pre-configured results directories (`results/plots`, `results/data`, `results/cache`).
3. **Hidden Imports Invariant**:
   - Must include `self_energy`, `susceptibility`, `conductivity`, and `pyside6_studio.backend.worker_cli` so child processes run cleanly without virtualenv dependencies.

---

## 7. Standard Verification Commands

Always verify changes using the virtual environment interpreter before reporting completion:

```powershell
# 1. Fast 3-Pillars Validation Test (Interactive Plots, CAD Plot Viewer, Caching Engine)
.venv\Scripts\python.exe tests/test_v35_three_pillars.py

# 2. Physics Solvers Execution Test (Runs all solvers headless via worker_cli)
.venv\Scripts\python.exe tests/test_all_four_solvers.py

# 3. Targeted UI Tests
.venv\Scripts\python.exe tests/test_hamiltonian_card_ui.py
.venv\Scripts\python.exe tests/test_susceptibility_ui_config.py

# 4. Cache & Directory Engine Test
.venv\Scripts\python.exe tests/test_caching_and_directory_engine.py

# 5. In-Situ Foundation Cache Workflow Test
.venv\Scripts\python.exe tests/test_foundation_workflow.py

# 6. Complete Automated Discovery Suite (Headless offscreen with top-level package flag)
.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

---

## 8. Late-Stage Polish & Future Physics Roadmap

### 8.1 Completed Beta v1 Milestones
- [x] Official Dyson Self-Energy ($\Sigma$) icon suite with High-DPI Windows rasterization.
- [x] Left Dock dynamic dual-stack switching (`PlotGalleryWidget` vs `InteractiveModeNavWidget`).
- [x] 5th calculation study: Electrical / Optical Conductivity Sweep $\sigma(\omega)$.
- [x] Backend `conductivity` submodule with Kubo bubble solvers and $C_{4v}$ IBZ symmetry reduction.
- [x] Dynamic hardware probing via `get_hardware_info()` with no hardcoded device strings.
- [x] Standalone one-directory CPU distribution builder (`tools/build_onedir_cpu.py`).

### 8.2 Remaining Polish & Next Horizons
- [ ] Add physics tooltips/hover help over all spinboxes in the Right Dock parameter panels.
- [ ] Implement export of interactive mode states to reproducible Python scripts.
- [ ] **Non-Local Vertex Corrections**: Extending spin susceptibility beyond RPA via Maki-Thompson and Aslamazov-Larkin fluctuation diagrams.
- [ ] **DMFT Continuous Coupling**: Interfacing with continuous-time quantum Monte Carlo (CT-QMC) solvers for strong correlation regimes.
- [ ] **Superconducting Pairing**: Adding anomalous self-energy channel $\Delta(\mathbf{k})$ for $d_{x^2-y^2}$-wave pairing instability sweeps.
