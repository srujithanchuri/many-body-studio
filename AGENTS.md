# AGENTS.md: Many-Body Studio
 
> **Universal Agent Onboarding & Architecture Blueprint**  
> *Target Context*: Correlated electron physics in Metal-Mott Insulator Heterostructures.  
> *Purpose*: Read this file first in any new session to obtain an instantaneous, complete mental model of the codebase, execution pipelines, data structures, and fragile invariants without scanning individual files.

---

## 1. Project Overview & Environment

- **Domain**: High-performance computational many-body physics (Hubbard model, Kondo breakdown, Fermi surface topology, static/dynamic RPA spin susceptibility, optical/electrical conductivity).
- **Core Stack**: Python 3.12, PySide6 (Qt 6.8+), Matplotlib (`QtAgg` for interactive canvas, `Agg` for headless subprocess rendering), CuPy (CUDA 12 NVIDIA GPU acceleration), NumPy, SciPy, Numba (multi-threaded JIT).
- **Virtual Environment**: `C:\Users\sruji\Projects\masters_thesis_gui\.venv\Scripts\python.exe`
- **GUI Workspace**: `C:\Users\sruji\Projects\masters_thesis_gui`
- **Physics Backend**: `C:\Users\sruji\Projects\masters_thesis` (imported as editable packages `self_energy` and `susceptibility`).
- **Results Output Tree**:
  - `results/plots/`: Final publication figures (`.png`, `.pdf`).
  - `results/data/`: Finished numerical datasets (`.npz`).
  - `results/cache/`: Reusable computational foundations (`sigma_base_*.npz`, `chi0_static_*.npz`, `chi0_dynamic_*.npz`).

---

## 2. Complete File & Module Map

### 2.1 Root Entry Points & Configuration
- [`run_studio.py`](run_studio.py) / [`run_studio.bat`](run_studio.bat): Windows entry point launchers. Forces line-buffered UTF-8 console (`PYTHONIOENCODING=utf-8`) to prevent `cp1252` encoding crashes on Greek symbols ($\Sigma$, $\chi$, $\omega$, $\mu$).
- [`AGENTS.md`](AGENTS.md): This file. Authoritative agent instructions automatically injected into agent system prompt.
- [`README.md`](README.md): High-level overview of Beta v1 capabilities, 6 modular interactive modes, and caching architecture.
- [`STUDIO_ARCHITECTURE_PLAN.md`](STUDIO_ARCHITECTURE_PLAN.md): In-depth historical engineering specification, memory budgets, and benchmark records.

### 2.2 Core GUI Architecture (`pyside6_studio/`)
- [`pyside6_studio/main.py`](pyside6_studio/main.py): Application bootstrap script. Sets Windows fractional High-DPI pass-through policy (`PassThrough`), installs custom Qt message filter to suppress benign font pointSize warnings, and initializes `UnifiedWorkbenchWindow`.
- [`pyside6_studio/main_window.py`](pyside6_studio/main_window.py): Core `QMainWindow` application shell (`UnifiedWorkbenchWindow`).
  - Manages dual-viewport switching (Plot Viewer vs Interactive Plots).
  - Coordinates left dock (260px) and right dock (350px).
  - Handles toolbar actions, traffic-light button synchronization, and `CalculationBridge` signal routing.
  - Implements `CacheManagerDialog`, `ModernCard`, `ModernComboBox`, and `DynamicStackedWidget`.
- [`pyside6_studio/theme.py`](pyside6_studio/theme.py): Centralized Fluent / Slate QSS stylesheet system. Contains `LIGHT_THEME_QSS`, `DARK_THEME_QSS`, and palette factories. Defines explicit `#ObjectName` selectors and widget rules.
- [`pyside6_studio/canvas.py`](pyside6_studio/canvas.py): High-DPI interactive `QGraphicsView` canvas (`InteractivePlotCanvas`). Supports smooth subpixel zoom/pan, crosshair coordinate inspection, and side-by-side split comparison views.

### 2.3 Core Configuration & Caching Engine (`pyside6_studio/core/`)
- [`pyside6_studio/core/cache_manager.py`](pyside6_studio/core/cache_manager.py): High-performance 1/8th Irreducible Brillouin Zone (IBZ) caching engine.
  - `normalize_results_dir()`: Canonicalizes directory structures (`results/plots`, `results/data`, `results/cache`).
  - `get_ibz_indices_and_map()`: Computes 1/8th IBZ wedge ($0 \le j \le i \le N/2$) and full-BZ reconstruction lookup table for $C_{4v}$ square lattice symmetry.
  - `mask_mantissa_8()`: Bit-grooming utility zeroing lowest 8 bits of float32 mantissa for entropy reduction.
  - `byte_shuffle_f32()` / `byte_unshuffle_f32()`: Transposes float32 memory into uint8 contiguous streams for 4x–8x lossless compression ratios.
  - `LazyIBZArray`: Zero-copy proxy wrapper for IBZ self-energy arrays, preventing gigabyte RAM inflation during sweeps.
  - `check_cache_status()`, `get_cache_stats()`, `purge_cache()`: Utilities for UI badges and cache inspection.
- [`pyside6_studio/core/hardware.py`](pyside6_studio/core/hardware.py): Hardware diagnostics probe. Probes CuPy CUDA VRAM availability, device names, and multi-core CPU availability.
- [`pyside6_studio/core/config.py`](pyside6_studio/core/config.py): Global configuration constants, resolution presets (Draft $64\times 64$, Standard $100\times 100$, High-Res Production $256\times 256$), and default parameter bounds.

### 2.4 IPC Backend & Execution Supervisor (`pyside6_studio/backend/`)
- [`pyside6_studio/backend/bridge.py`](pyside6_studio/backend/bridge.py): `CalculationBridge` (`QObject`).
  - Launches worker process via `QProcess` with unbuffered UTF-8 I/O.
  - Encodes parameters via Base64 JSON (`--params-b64`) to eliminate command-line character escaping issues.
  - Parses newline-delimited JSON messages from child stdout.
  - Dispatches Qt signals: `sig_started`, `sig_status`, `sig_progress`, `sig_completed`, `sig_error`, `sig_cancelled`.
- [`pyside6_studio/backend/worker_cli.py`](pyside6_studio/backend/worker_cli.py): Standalone CLI entry point executed in an isolated child process.
  - Contains task functions: `run_spectral_sweep_task`, `run_spectral_function_task`, `run_phase_diagram_task`, `run_susceptibility_task`, `run_foundation_cache_task`.
  - Dispatches tasks to backend physics solvers in `masters_thesis/`.
  - Flushes GPU VRAM and exits cleanly.
- [`pyside6_studio/backend/vram_cleaner.py`](pyside6_studio/backend/vram_cleaner.py): Process killer and GPU memory reclaimer. Uses `psutil` to kill entire subprocess process trees and invokes CuPy memory pool reclamation.
- [`pyside6_studio/backend/cuda_env.py`](pyside6_studio/backend/cuda_env.py): Configures CUDA environment variables and suppresses benign driver path warnings.

### 2.5 Widgets & Interactive Plots Studio (`pyside6_studio/widgets/`)
- [`pyside6_studio/widgets/interactive_plots.py`](pyside6_studio/widgets/interactive_plots.py): **Interactive Plots Studio** (`InteractivePlotsWidget`).
  - Real-time 60 FPS canvas with continuous $J_K$ slider (0.1 to 12.0) utilizing analytical $J_K^2$ scaling.
  - Houses the top control bar (Cache Selector, J_K slider, J_K spinbox, Mode Selector, `▶ Compute Cache`, Send to Sweeper).
  - Pluggable mode architecture via `BaseInteractiveMode`.
- [`pyside6_studio/widgets/interactive_modes/`](pyside6_studio/widgets/interactive_modes/):
  - `base_mode.py`: Abstract base class defining `setup_ui()`, `render()`, `fit_view()`, `on_scroll()`, `on_press()`, `on_motion()`, `on_release()`.
  - `spectral_function_mode.py`: $A(\mathbf{k},\omega)$, $\text{Re}\,\Sigma$, $\text{Im}\,\Sigma$, and full-BZ $Z(\mathbf{k})$ quasiparticle weight heatmap with interactive click-and-drag $\mathbf{k}$-probe.
  - `energy_slice_mode.py`: Dynamic constant-energy surface movie across BZ with continuous energy slider $\omega$.
  - `band_dispersion_mode.py`: Renormalized quasiparticle dispersion $E(\mathbf{k})$ along $\Gamma - X - M - \Gamma$ with self-energy corrections.
  - `rpa_susceptibility_mode.py`: Static RPA spin susceptibility $\chi_{\text{RPA}}(\mathbf{q})$ 2D map with real-time Stoner magnetic instability tracking ($1 - U \chi_0 \to 0$).
  - `dynamic_susceptibility_mode.py`: Dynamical spin susceptibility $\chi''(\mathbf{q},\omega)$ intensity map along high-symmetry path.
  - `conductivity_mode.py`: Optical / DC electrical conductivity $\sigma(\omega)$ calculation.
- [`pyside6_studio/widgets/compute_cache_dialog.py`](pyside6_studio/widgets/compute_cache_dialog.py) / [`foundation_cache_dialog.py`](pyside6_studio/widgets/foundation_cache_dialog.py):
  - In-situ dialog spawned from `▶ Compute Cache` button in Interactive Plots. Computes self-energy or bare static/dynamic susceptibility foundations without batch sweeps.
- [`pyside6_studio/widgets/gallery_browser.py`](pyside6_studio/widgets/gallery_browser.py): Left dock visual gallery browser (`PlotGalleryWidget`). Offers dual display modes (Visual Thumbnail Cards vs Compact List View) with search/filter.
- [`pyside6_studio/widgets/dataset_explorer.py`](pyside6_studio/widgets/dataset_explorer.py): Left dock dataset inspector (`DatasetExplorerWidget`). Scans `results/data/`, displays metadata cards, and provides quick actions.
- [`pyside6_studio/widgets/data_plotter.py`](pyside6_studio/widgets/data_plotter.py): Interactive curve plotter and slice visualizer dialog (`VectorExportDialog`, `InteractiveDataCanvas`).

### 2.6 Physics Backend Packages (`masters_thesis/`)
- [`self_energy/parameters.py`](../masters_thesis/self_energy/parameters.py): Defines `ModelParameters` dataclass ($t, t_1, \mu, K, N, N_\omega, \omega_{\max}, \eta, \text{solver}, \text{cpu\_limit}$).
- [`self_energy/sweep_core.py`](../masters_thesis/self_energy/sweep_core.py): Full BZ sweeps `run_J_k_sweep`, `run_J_perp_sweep`, composite figure generation (DOS, Fermi Surface, Path).
- [`self_energy/full_bz_solver.py`](../masters_thesis/self_energy/full_bz_solver.py): Core 1-loop and 3-loop FFT convolution physics kernels implemented on CuPy CUDA and NumPy/SciPy.
- [`susceptibility/phase_diagram.py`](../masters_thesis/susceptibility/phase_diagram.py): Root bisection solver determining critical magnetic phase boundaries ($J_K^c$ vs $\mu$).
- [`susceptibility/precompute_chi0.py`](../masters_thesis/susceptibility/precompute_chi0.py): Static and dynamic Lindhard bubble tensor evaluations across 2D Brillouin zone.
- [`susceptibility/sweeper.py`](../masters_thesis/susceptibility/sweeper.py): Multi-threaded RPA susceptibility sweeps $\chi_{\text{RPA}}(\mathbf{q}, \omega) = \frac{\chi_0}{1 - U \chi_0}$.

### 2.7 Automated Test Suite (`tests/`)
- [`tests/test_v35_three_pillars.py`](tests/test_v35_three_pillars.py): Fast validation test covering Interactive Plots, CAD Plot Viewer, and Caching Engine.
- [`tests/test_all_four_solvers.py`](tests/test_all_four_solvers.py): Headless physics execution test running all 4 solvers via `worker_cli.py`.
- [`tests/test_caching_and_directory_engine.py`](tests/test_caching_and_directory_engine.py): Tests directory layout, cache key generation, bit-grooming, and `LazyIBZArray`.
- [`tests/test_dataset_explorer.py`](tests/test_dataset_explorer.py): Tests dataset scanning and tree population.
- [`tests/test_e2e_tier1.py`](tests/test_e2e_tier1.py) to [`test_e2e_tier4.py`](tests/test_e2e_tier4.py): Comprehensive end-to-end integration test tiers.
- [`tests/test_foundation_workflow.py`](tests/test_foundation_workflow.py): Tests in-situ foundation cache computation and invalidation.

---

## 3. Critical Invariants & Fragile Rules (DO NOT BREAK)

Agents modifying this codebase **must strictly preserve** these rules:

1. **Zero Compute on GUI Main Thread**:
   - Heavy physics (FFT convolutions, CuPy CUDA kernels, Dyson equation inversions, bisection sweeps) **must never** execute in the main Qt thread.
   - Long computations must be dispatched through `self.bridge.start_calculation(params)` (`CalculationBridge` running `worker_cli.py` via `QProcess`).
   - Communication must use newline-delimited JSON over stdout: `{"type": "status|progress|completed|error", ...}`.

2. **Fixed Dock Width Invariants**:
   - Left Navigator Dock (`self.dock_nav`): exactly **$260\text{ px}$** (min 240, max 320).
   - Right Simulation Setup Dock (`self.dock_inspector`): exactly **$350\text{ px}$**.
   - Do not set expanding policies on docks that violate these bounds.

3. **Styling & Theme Discipline**:
   - **Never hardcode inline colors** (e.g. `background: white; color: black;`) in widget code.
   - Always define semantic `#ObjectName` or class selectors in [`pyside6_studio/theme.py`](pyside6_studio/theme.py) for both `LIGHT_THEME_QSS` and `DARK_THEME_QSS`.
   - When dynamically toggling `objectName` or pseudo-states at runtime, always invoke the unpolish/polish cycle:
     ```python
     widget.style().unpolish(widget)
     widget.style().polish(widget)
     widget.update()
     ```

4. **Execution "Traffic Light" Controls**:
   - `▶ Run Calculation` (`#BtnRun`): IDE Emerald Green (`#16a34a` Light / `#059669` Dark). Disabled during computation.
   - `⏹ Cancel / Stop` (`#BtnCancel`): **Vivid Red** (`#ef4444`) when active/running; **Disabled Grey** (`#f1f5f9` / `#1e293b`) when idle.
   - Always synchronize execution buttons via `self._update_execution_buttons(is_running=True/False)`.

5. **Wheel Scroll Redirection**:
   - All parameter panels must use `WheelScrollRedirectFilter`. This prevents accidental value drift on spinboxes and comboboxes while the user vertically scrolls through parameter panels.

6. **Process Lifecycle & GPU VRAM Cleanliness**:
   - Always use 2-stage cancellation: soft SIGINT/SIGTERM followed by hard process tree kill (`kill_process_tree(pid)`).
   - After child process completion or cancellation, always trigger `flush_gpu_vram()` to ensure CuPy memory pool releases allocated VRAM back to the OS.

---

## 4. Data Flow & Interface Contracts

### 4.1 Calculation Dispatch & IPC Contract
```text
User Action (Click '▶ Run Calculation' or '▶ Compute Cache')
  │
  ├── 1. Parameters gathered from UI into dictionary:
  │      {
  │        "study_type": "spectral_sweep" | "spectral_function" | "phase_diagram" | "susceptibility" | "foundation_cache",
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
  │      {"type": "status", "phase": "running", "message": "Evaluating 1-Loop & 3-Loop Self-Energy..."}
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

### 5.2 `[ ⚡ Interactive Plots ]` (Mode 1)
- High-speed interactive research workbench (`InteractivePlotsWidget`).
- **Header Controls**:
  - *Cache Dropdown*: Displays available foundation arrays with concise parameter badges (e.g. `Σ (μ=0.0, J⊥=6.0, K=1.0, N=100)`).
  - *Continuous $J_K$ Slider & Spinbox*: Analytical 60 FPS scaling from 0.1 to 12.0.
  - *Mode Selector*: Switches between the 6 interactive modes:
    1. **Quasiparticle Spectral Function $A(\mathbf{k},\omega)$**: Real-time spectral density with interactive $\mathbf{k}$-point crosshair click-and-probe and $Z(\mathbf{k})$ weight map.
    2. **Energy Slices (Fermi Surface Movie)**: Constant-energy contours across BZ with smooth $\omega$-slider scrub.
    3. **Band Dispersion $E(\mathbf{k})$**: Quasiparticle dispersions along $\Gamma-X-M-\Gamma$ path.
    4. **Static Spin Susceptibility $\chi_{\text{RPA}}(\mathbf{q})$**: 2D momentum map with Stoner instability alert ($1 - U \chi_0 \to 0$).
    5. **Dynamic Spin Susceptibility $\chi''(\mathbf{q},\omega)$**: Fluctuation intensity maps along high-symmetry path.
    6. **Electrical Conductivity $\sigma(\omega)$**: Optical/DC conductivity curves across frequency.
  - *`▶ Compute Cache` Button*: Spawns `ComputeCacheDialog` for instant in-situ foundation generation.
  - *Send to Sweeper*: Transfers current interactive parameters into the Right Dock Simulation Setup for batch sweeps.

---

## 6. Standard Verification Commands

Always verify changes using the virtual environment interpreter before reporting completion:

```powershell
# 1. Fast 3-Pillars Validation Test (Interactive Plots, CAD Plot Viewer, Caching Engine)
.venv\Scripts\python.exe tests/test_v35_three_pillars.py

# 2. Physics Solvers Execution Test (Runs all 5 solvers across GPU & CPU via worker_cli)
.venv\Scripts\python.exe tests/test_all_four_solvers.py

# 3. Cache & Directory Engine Test
.venv\Scripts\python.exe tests/test_caching_and_directory_engine.py

# 4. In-Situ Foundation Cache Workflow Test
.venv\Scripts\python.exe tests/test_foundation_workflow.py

# 5. Complete 37-Test Automated Discovery Suite (Headless offscreen)
.venv\Scripts\python.exe -m unittest discover tests
```

---

## 7. Late-Stage Polish & Future Physics Roadmap

### 7.1 Immediate Polish Checklist
- [x] Unify "Run Cache" terminology to "Compute Cache" across all dialogs, tooltips, and docs.
- [x] Synchronize 6th interactive mode (`ElectricalConductivityMode`) across selector and documentation.
- [x] Streamline Right Dock Inspector Cache Card with 2-column parameter layouts.
- [ ] Add tooltips/hover help over all physics spinboxes in the Right Dock parameter panels.
- [ ] Implement export of interactive mode states to reproducible Python scripts.

### 7.2 Physics Roadmap (Next Horizons)
- **Non-Local Vertex Corrections**: Extending spin susceptibility beyond RPA via Maki-Thompson and Aslamazov-Larkin fluctuation diagrams.
- **DMFT Continuous Coupling**: Interfacing with continuous-time quantum Monte Carlo (CT-QMC) solvers for strong correlation regimes.
- **Superconducting Pairing**: Adding anomalous self-energy channel $\Delta(\mathbf{k})$ for $d_{x^2-y^2}$-wave pairing instability sweeps.
