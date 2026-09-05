# Many-Body Studio Pro: Complete Architecture & Implementation Plan

> **Document Version**: alpha-v4.0 (Milestone: Fixed Panel Dimensions, Modular 5-Mode Interactive Plots, High-Precision J_perp / K Susceptibility Tuning)  
> **Target Project**: `C:\Users\sruji\Projects\masters_thesis_gui`  
> **Physics Engine Source**: `C:\Users\sruji\Projects\masters_thesis`  
> **Author**: Antigravity Assistant & Srujith Anchuri  

---

## 1. Executive Summary & Philosophy

**Many-Body Studio Pro** is a modern, high-performance scientific desktop application built with **PySide6 (Qt 6)**. It decouples the presentation layer (GUI, visualization, queue management, caching) from the heavy scientific compute engine (real-time Langreth FFT convolutions, CuPy CUDA kernels, RPA bisection solvers).

### Architectural Decoupling:
* **Physics Engine (`masters_thesis/`)**: Remains pure scientific Python code (`self_energy`, `susceptibility`), free of GUI dependencies, runnable on headless clusters.
* **Studio GUI (`masters_thesis_gui/`)**: Dedicated PySide6 graphical environment that communicates with the physics engine via an editable package link (`pip install -e`).

### The Dual-Perspective Concept:
1. **Simulation Studio (Current Primary Focus)**: An IDE-style scientific workbench dedicated to configuring Hamiltonians, launching GPU/CPU simulations, monitoring live progress, managing batch queues, and inspecting data in a hardware-accelerated interactive canvas.
2. **Figure Composer (Staged for Future)**: A specialized layout perspective that stows away all solver knobs to compose multi-panel journal figures (`(a) DOS`, `(b) Fermi Surface`, `(c) Dispersion Path`), customize colormaps, apply LaTeX typography, and export vector PDFs for LaTeX.

---

## 2. Simulation Workspace: Complete Feature Specification

### 2.1 UI Features & Layout Ergonomics

| Feature | Description | Benefit |
|---|---|---|
| **Dockable Multi-Window Layout** | Four specialized dock areas: Left Navigator, Central Canvas, Right Inspector, Bottom Drawer. | Can be rearranged, tabbed, collapsed, or undocked to a second monitor. |
| **Smart Dataset Explorer (Left Panel)** | Dedicated view of finished plots and observable datasets with automatic run grouping and multi-file pairing. | Internal cache files removed to eliminate workspace clutter; clean research overview. |
| **High-Precision Scientific Search** | Parameter-aware token search (`mu=1.0`, `JK=3.0`, `N=64`, `dos 6.0`) with numerical float parsing and instant tree auto-expansion. | Locates matching runs across thousands of files with typed accuracy. |
| **Context-Adaptive Inspector** | The right-hand parameter inspector dynamically morphs its fields depending on the active study. | You only see the knobs relevant to your current calculation; zero visual clutter. |
| **Pinned Hamiltonian Core** | Fundamental model variables ($t, t', \mu, K$) remain pinned at the bottom of the inspector. | Tweak band dispersion and chemical potential without navigating away. |
| **Numerical Presets** | Three built-in presets: `Fast Preview (N=64)`, `Standard (N=100)`, `Production (N=256)`. | Instant switching between 1-second sanity checks and production-grade runs. |
| **Hardware Diagnostics Badge** | Real-time detector reporting CUDA availability, GPU device name (e.g. *RTX 5060 Laptop GPU*), and VRAM status. | Transparent feedback on whether calculations run on GPU or CPU fallback. |
| **Theme Engine** | Fluid switching between **Slate-50 Light** and **OLED Dark** stylesheets. | High-contrast readability during daytime research or low-light night sessions. |
| **Keyboard Shortcuts** | `Ctrl+Enter` (Run Active), `Ctrl+Space` (Add to Queue), `Ctrl+F` (Fit Canvas), `Ctrl+T` (Theme). | High-speed ergonomics for power users. |

---

### 2.2 Smart Caching & 1/8th IBZ Storage Optimization

| Feature | Description | Benefit |
|---|---|---|
| **$C_{4v}$ 1/8th IBZ Wedge Serialization** | Base $\Sigma$ caches fold the 2D Brillouin Zone down to the triangular $C_{4v}$ irreducible wedge ($0 \le j \le i \le N/2$) with `float32` precision. | **$19.2\times$ disk footprint reduction** ($861.6\text{ MB} \to 44.86\text{ MB}$ for $N=100$; $8.4\text{ GB} \to \sim 435\text{ MB}$ for $N=256$). |
| **100% Full-BZ Physics Preservation** | All Dyson convolutions, FFT convolutions, and physical observables run strictly on the Full Brillouin Zone. Instant reconstruction in RAM ($<0.05\text{s}$) via index mapping table. | Absolute observable discrepancy $< 0.0003\%$ (negligible roundoff). Zero algorithmic compromise. |
| **Deterministic Hash & Key Signatures** | Computes deterministic keys from parameter tuples: `(study_type, t, t1, mu, K, sweep_target, sweep_vals, fixed_val, N, Nw, eta)`. | Replaces fragile filename string matching with mathematical certainty. |
| **Live Cache-Hit Status Badging** | The UI inspects cache foundation arrays in real time: `⚡ Base Σ Cached (1/8th IBZ) (Fast J_K Scaling)` vs `⚙️ No Cache: Full Computation Needed`. | Immediate visual feedback on whether calculations will run instantly or require cold compute. |
| **Force Recompute Switch** | A toggle `[ ] Force Recompute` allows overriding cache when testing algorithm updates. | Total control over when to reuse data vs recalculate. |
| **Reusable Bubble $\chi_0$ Tracking** | Bare bubble $\chi_0(q, \omega)$ is independent of $J_K, J_\perp, K$. | Once computed for a given $(t, t', \mu, N)$, Phase Diagram and RPA sweeps skip bubble calculation and finish in $< 1\text{ second}$! |
| **Dedicated Cache Lifecycle Manager** | Cache management is decoupled from study browsing into a dedicated `🧹 Cache (X MB)` modal dialog with granular inspection and safe purging. | Protects published figures and datasets from accidental deletion while freeing gigabytes of cache. |

---

### 2.3 Interactive Scientific Plotting & Visualization Engine

| Feature | Description | Benefit |
|---|---|---|
| **Hybrid Canvas Architecture** | Seamlessly tabs between high-DPI raster/vector Plot Viewer (`QGraphicsView`) and native Interactive Curves (`FigureCanvasQTAgg` / `pyqtgraph`). | Best of both worlds: crisp figure presentation alongside deep interactive data exploration. |
| **Interactive Curve Analytics** | Live crosshairs, curve toggle visibility, toolbar zoom/pan, coordinate readouts, and observable switching (DOS, self-energy slices, susceptibilities). | Direct physical insight from raw `.npz` arrays without having to open an external notebook. |
| **Split-Screen Comparative Mode** | Side-by-side viewports (`QSplitter`) with synchronized or independent zoom/pan. | Instant comparison across coupling regimes (e.g. $J_K=3.0$ vs $J_K=9.0$) or cross-validation between datasets. |
| **Hardware-Accelerated Smooth Zoom/Pan** | Subpixel rendering with smooth transformation anchors centered directly on cursor position. | Butter-smooth navigation of high-density colormaps and fine spectral features. |
| **Plot Viewer Quick Actions** | Context actions: `Copy to Clipboard`, `Save High-Res PNG`, `Open in System Viewer`, `Reveal in File Explorer`. | Instant workflow integration for drafting presentations and writing manuscripts. |

### 2.4 The Core Paradigm Shift: Static PNGs vs. Native Interactive Data

In the legacy Tkinter alpha build, every calculation completed by writing a flat `.png` bitmap to disk, which the GUI rendered as a static image. In **Many-Body Studio Pro**, calculations generate and preserve **raw numerical NumPy arrays** (`omega`, `Atot_loc`, `Atot_path`, `Atot_w0`, `chi0`, `J_c_curve`, `spectral_maps`).

Rather than confining analysis to flat raster pictures, the Studio architecture leverages native, hardware-accelerated interactive scientific data visualization (via `pyqtgraph` and hardware-accelerated embedded Matplotlib Qt canvases) with four flagship priority features:

| Priority Feature | Architectural Implementation & Mechanism | Research Benefit |
|---|---|---|
| **Interactive Crosshairs & Peak Readout** | Binds mouse cursor hover events over the 1D & 2D spectral arrays ($A(\mathbf{k}, \omega)$, $\operatorname{Im}\Sigma(\mathbf{k}, \omega)$, $\chi(\mathbf{q}, \omega)$). Real-time interpolation displays the exact numerical frequency $\omega$, quasiparticle energy shifts $\operatorname{Re}\Sigma$, scattering rates, and peak heights directly in the viewport readout HUD. | Quantitative extraction of quasiparticle lifetimes and peak positions on the fly without manual raw data exports. |
| **Interactive Brillouin Zone Cutlines** | An interactive vector line tool drawn across the 2D Static Susceptibility $\chi(\mathbf{q})$ Brillouin zone map. Slicing through the underlying 2D array dynamically extracts and plots the 1D intensity profile $\chi(q)$ along that custom trajectory in a companion sub-view in real time. | Real-time exploration of incommensurate nesting peaks and directional anisotropy along arbitrary BZ paths. |
| **Instant Parametric Sliders (Zero-Wait Physics)** | Because the bare bubble $\chi_0(\mathbf{q}, \omega)$ is computationally intensive but completely independent of $J_K$ and $J_\perp$, it is cached in RAM/disk. Dragging real-time interactive sliders for $J_K$ evaluates the scalar RPA inversion formula $\chi = \chi_0 / [1 - \Gamma \chi_0]$ instantaneously at **60 FPS** without recomputing the bubble. | Zero-wait physical exploration of magnetic phase boundaries and peak divergences in real time. |
| **Vector Export on Demand** | One-click export of native figure elements to vector formats (**`.pdf`**, **`.svg`**, **`.eps`**) with embedded LaTeX fonts and scalable vector line art directly from the underlying data. | Thesis-ready vector graphics that scale infinitely in LaTeX documents without bitmap rasterization artifacts. |

---

### 2.5 Stability, Security & Crash Protection

| Feature | Description | Benefit |
|---|---|---|
| **Process Isolation (IPC)** | Calculations run in a child worker process (`multiprocessing.Process`), completely isolated from the GUI process. | **Zero GUI freezes**: A numerical failure, segfault, or CuPy error in the solver **cannot crash or freeze the GUI**. |
| **CUDA OOM Trap & Diagnostics** | Worker wraps CuPy routines in memory guards. Catches `cupy.cuda.memory.OutOfMemoryError`. | Instead of a silent crash, the UI catches the error, flushes VRAM, and suggests: *"Reduce N from 256 to 128 or Nw to 4801."* |
| **Input Parameter Validation** | Sanitizes inputs before launching solvers ($t > 0, N \ge 32, \eta > 0, \text{Nw} \ge 1001$). | Prevents divide-by-zero, negative square roots, or infinite loops before they reach the GPU. |
| **Global Uncaught Exception Hook** | Captures unexpected Python exceptions (`sys.excepthook`) into a custom Qt Error Dialog. | Provides a clean "Copy Traceback" button and automatic session logging instead of an abrupt program termination. |

---

### 2.6 Execution Lifecycle & Stop Execution (GPU Memory Release)

| Feature | Description | Benefit |
|---|---|---|
| **2-Stage Cancellation Protocol** | **Stage 1 (Soft Interrupt)**: Sends a cancellation event flag. The solver loop breaks at the next step, cleans up, and exits.<br>**Stage 2 (Hard Terminate)**: If a heavy C-kernel is unresponsive after 2.5s, forcefully kills the worker process tree (`taskkill /F /T /PID`). | Guaranteed immediate response when the user hits "Cancel / Stop", even during heavy CUDA FFT loops. |
| **Guaranteed GPU VRAM Flush** | Calls `cp.get_default_memory_pool().free_all_blocks()` and `cp.get_default_pinned_memory_pool().free_all_blocks()`. | Guarantees **zero VRAM leaks** on the RTX 5060 across consecutive, failed, or cancelled runs. |
| **Live Solver Console Streaming** | Redirects solver stdout/stderr via an IPC pipe directly into the live console tab. | Real-time visibility into FFT progress, Langreth integration steps, and execution timers. |

---

### 2.7 Batch Queue Management

| Feature | Description | Benefit |
|---|---|---|
| **Thread-Safe FIFO Queue** | Manages jobs with states: `Pending` ➔ `Running` ➔ `Completed` \| `Failed` \| `Cancelled`. | Queue up 10 parameter sweeps and let them run unattended overnight. |
| **In-Cell Animated Progress** | Embedded `QProgressBar` inside each table row, displaying live percentage and elapsed time. | Visual clarity on current progress across individual batch items. |
| **Interactive Queue Controls** | `▶ Start Queue`, `⏸ Pause` (finishes current job and halts), `⏹ Cancel Active`, `🗑 Clear Finished`. | Complete control over multi-job execution without interrupting background work. |
| **Job Duplication & Reordering** | Right-click options to duplicate a job with modified parameters, move up, or move down. | Rapid setup of parameter grids without re-typing common configurations. |
| **Queue Serialization** | Serializes pending and completed jobs to `job_queue.json`. | If you close the app or restart your computer, your batch queue resumes right where you left off. |

---

## 3. Directory Structure of the Studio

```
masters_thesis_gui/
├── pyside6_studio/
│   ├── __init__.py
│   ├── main.py                  # Application entry point
│   ├── main_window.py           # Flagship studio window (Simulation Studio + Figure Composer)
│   ├── theme.py                 # Slate-50 Light & Slate-900 Dark QSS
│   ├── canvas.py                # High-performance CAD zoom/pan canvas (QGraphicsView)
│   ├── composer.py              # Figure Composer multi-panel engine
│   │
│   ├── core/                    # Engine Configuration & Diagnostics
│   │   ├── __init__.py
│   │   ├── config.py            # Paths, resolution presets, defaults
│   │   ├── hardware.py          # CUDA RTX 5060 detection & VRAM monitoring
│   │   ├── cache_manager.py     # SHA-256 parameter hashing & .npz scanner
│   │   └── job_queue.py         # Thread-safe FIFO batch queue manager
│   │
│   ├── backend/                 # Process Isolation & IPC Bridge
│   │   ├── __init__.py
│   │   ├── vram_cleaner.py      # Bulletproof CuPy memory pool flushing
│   │   ├── workers.py           # Subprocess worker wrapper for self_energy & susceptibility
│   │   └── bridge.py            # Qt supervisor thread & signal dispatcher
│   │
│   └── widgets/                 # Refined Interactive Controls
│       ├── __init__.py
│       ├── parameter_cards.py   # Context-adaptive parameter inspector cards
│       ├── queue_table.py       # In-cell animated progress & status badges
│       └── console_widget.py    # Syntax-highlighted live solver log output
│
├── STUDIO_ARCHITECTURE_PLAN.md  # This comprehensive architecture document
└── run_studio.bat               # 1-Click launcher
```

---

## 4. Implementation Phasing (Vertical Slice Approach)

### Phase 1: Core Foundation & Safe IPC Bridge (In Progress)
1. Build `core/config.py` and `core/hardware.py` (RTX 5060 detection, VRAM monitor, presets).
2. Build `backend/vram_cleaner.py` and `backend/workers.py` (Subprocess isolation, stdout pipe, cancellation flag).
3. Build `backend/bridge.py` (Qt supervisor thread managing inter-process queues and Qt signals).

### Phase 2: First Physics Vertical Slice (`Spectral Sweep`)
1. Connect `self_energy.sweep_core.run_sweep` through the IPC bridge.
2. Wire the UI **`⚡ Run Active`** and **`⏹ Stop / Cancel`** buttons.
3. Stream real-time stdout logs to the live console tab.
4. Automatically load the newly generated plot into the interactive canvas upon completion.
5. Verify cancellation: verify that clicking "Stop" halts computation within 1 second and flushes all GPU memory.

### Phase 3: Scaling to Remaining Physics Studies (Current Focus)
1. Connect `Spectral Function A(k, ω)` (`self_energy.run_spectral`).
2. Connect `Phase Diagram Bisection` (`susceptibility.phase_diagram`).
3. Connect `RPA Susceptibility Sweep` (`susceptibility.sweeper`).
4. Rigorous verification of all 4 solvers across both GPU (`gpu64`) and CPU (`cpu`) backends.

### Phase 4: Smart Caching & Batch Queue
1. Implement `core/cache_manager.py` with SHA-256 parameter hashing.
2. Build instant cache hit detection in the UI.
3. Wire the persistent batch queue table with in-cell animated progress bars.

### Phase 5: Native Interactive Data & Scientific Analysis Tools (Top Priority Track)
1. **Interactive Crosshairs & Peak Readout**: Real-time HUD displaying numerical $\omega, A(\mathbf{k}, \omega), \operatorname{Re}\Sigma, \operatorname{Im}\Sigma, \chi(\mathbf{q}, \omega)$ on cursor hover.
2. **Interactive Brillouin Zone Cutlines**: Free-hand or guided vector slice tool on 2D Static $\chi(\mathbf{q})$ maps extracting real-time 1D intensity cuts.
3. **Instant Parametric Sliders (Zero-Wait Physics)**: GPU/RAM-cached bubble $\chi_0$ enables continuous 60 FPS slider manipulation of $J_K / J_\perp$ with instant RPA inversion.
4. **Vector Export on Demand**: Direct export of figures to `.pdf`, `.svg`, and `.eps` with embedded LaTeX typography for thesis manuscripts.

---

## 5. Verification & Testing Matrix

| Test Case | Method | Expected Outcome |
|---|---|---|
| **Hardware Detection** | Launch Studio | UI status badge displays: `⚡ GPU Active: NVIDIA GeForce RTX 5060 Laptop GPU (8 GB)`. |
| **Process Isolation** | Inject a divide-by-zero or crash into worker | Worker process exits with error signal; GUI remains 100% fluid and displays error dialog. |
| **Live Log Streaming** | Run Spectral Sweep ($N=64$) | Real-time FFT, Simpson integration, and timer messages appear in the live console. |
| **Plot Auto-Load** | Complete calculation | Newly generated `.png` renders on `InteractivePlotCanvas` with CAD zoom enabled. |
| **2-Stage Cancellation** | Click "Cancel" mid-FFT loop | Worker halts within 1s; CuPy pools freed; status bar updates to *"Job Cancelled"*. |
| **GPU VRAM Cleanup** | Measure VRAM before and after run | Memory delta is 0 MB (all CuPy blocks returned to OS/pool). |
