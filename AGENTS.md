# AGENT.md: Many-Body Studio Pro

> **Instructions for AI Coding Assistants**: Read this file first to grasp project architecture, module layout, execution patterns, and strict constraints without scanning individual files.

---

## 1. Project Summary & Tech Stack

- **Purpose**: High-performance scientific desktop workbench for correlated electron physics (Metal-Mott Insulator Heterostructures).
- **Core Technology**: Python 3.12, PySide6 (Qt 6.11+), Matplotlib, CuPy (CUDA 12 GPU acceleration), NumPy, SciPy.
- **Python Environment**: `c:\Users\sruji\Projects\masters_thesis_gui\.venv\Scripts\python.exe`
- **Physics Backend**: `c:\Users\sruji\Projects\masters_thesis` (imported as editable package `self_energy`, `susceptibility`).

---

## 2. Fast Repository Map

| Path | Primary Responsibility |
|---|---|
| [`run_studio.py`](run_studio.py) / [`run_studio.bat`](run_studio.bat) | Application entry point launchers (forces UTF-8 console on Windows). |
| [`pyside6_studio/main_window.py`](pyside6_studio/main_window.py) | Main `QMainWindow` shell, toolbars, docks, perspectives, and signal routing. |
| [`pyside6_studio/theme.py`](pyside6_studio/theme.py) | Centralized QSS stylesheets (`LIGHT_THEME_QSS`, `DARK_THEME_QSS`) and color palettes. |
| [`pyside6_studio/backend/bridge.py`](pyside6_studio/backend/bridge.py) | `CalculationBridge`: `QProcess` supervisor, JSON stdout stream parser, process killer. |
| [`pyside6_studio/backend/worker_cli.py`](pyside6_studio/backend/worker_cli.py) | Standalone CLI entry point executing physics kernels in an isolated child process. |
| [`pyside6_studio/core/hardware.py`](pyside6_studio/core/hardware.py) | Hardware probe: CuPy NVIDIA GPU VRAM detection and CPU core limits. |
| [`pyside6_studio/core/cache_manager.py`](pyside6_studio/core/cache_manager.py) | 1/8th IBZ bit-groomed $\Sigma$ cache detection, parameter hashing, and cache badges. |
| [`pyside6_studio/core/config.py`](pyside6_studio/core/config.py) | Resolution presets: Draft ($64\times 64$), Standard ($100\times 100$), High-Res Production ($256\times 256$). |
| [`pyside6_studio/canvas.py`](pyside6_studio/canvas.py) | High-DPI interactive `QGraphicsView` canvas (smooth zoom, pan, coordinates, split view). |
| [`pyside6_studio/widgets/gallery_browser.py`](pyside6_studio/widgets/gallery_browser.py) | Left visual thumbnail cards & compact list gallery browser with search/filter. |
| [`pyside6_studio/widgets/dataset_explorer.py`](pyside6_studio/widgets/dataset_explorer.py) | Left dock dataset tree scanner with metadata inspection cards and quick-load actions. |
| [`pyside6_studio/widgets/data_plotter.py`](pyside6_studio/widgets/data_plotter.py) | Interactive curve plotting and slice visualizer dialog. |
| [`pyside6_studio/widgets/interactive_plots.py`](pyside6_studio/widgets/interactive_plots.py) | **Interactive Plots Studio**: 60 FPS real-time $J_K$ slider coupling & interactive plot modes (`InteractivePlotsWidget`). |
| [`pyside6_studio/widgets/interactive_modes/`](pyside6_studio/widgets/interactive_modes/) | Interactive modes: DOS & Fermi Surface, Dynamic $\chi(\mathbf{q},\omega)$, Static RPA $\chi(\mathbf{q})$, Band Dispersion. |
| [`tests/`](tests/) | Headless automated test suite running with Python standard `unittest` (37 tests). |
| [`results/`](results/) | Gitignored calculation outputs: `cache/` (.npz), `plots/` (.png/.pdf), `data/` (.npz). |

---

## 3. Critical Invariants & Architectural Rules

Agents modifying this codebase **must strictly preserve** these rules:

1. **Zero Compute on GUI Main Thread**:
   - Heavy physics (FFT convolutions, CuPy CUDA kernels, bisection sweeps) **must never** run in the main Qt thread.
   - Always dispatch computations via `self.bridge.start_calculation(params)` (`CalculationBridge` running `worker_cli.py` via `QProcess`).
   - Communication uses newline-delimited JSON stdout: `{"type": "progress|status|result|error", ...}`.

2. **Fixed Dock Widths**:
   - Left Dock (`self.dock_nav`): exactly **$260\text{ px}$**.
   - Right Dock (`self.dock_inspector`): exactly **$350\text{ px}$**.
   - Do not allow dynamic stretching that violates these bounds.

3. **Styling & Theme Discipline**:
   - Never hardcode inline background/text colors (e.g. `background: white; color: black;`) in widget code.
   - Always define semantic `#ObjectName` or class selectors in [`pyside6_studio/theme.py`](pyside6_studio/theme.py) for both `LIGHT_THEME_QSS` and `DARK_THEME_QSS`.
   - When dynamically switching `objectName` or pseudo-states at runtime, always invoke:
     ```python
     widget.style().unpolish(widget)
     widget.style().polish(widget)
     widget.update()
     ```

4. **Execution "Traffic Light" Controls**:
   - `▶ Run Calculation` (`#BtnRun`): IDE Emerald Green (`#16a34a` Light / `#059669` Dark). Disabled during computation.
   - `⏹ Cancel / Stop` (`#BtnCancel`): **Vivid Red** (`#ef4444`) when active/running; **Disabled Grey** (`#f1f5f9` / `#1e293b`) when idle.
   - Always synchronize execution buttons via `self._update_execution_buttons(is_running=True/False)`.

5. **Two-Tier Navigation Architecture**:
   - **Tier 1: Global Workspace Mode** (Top Toolbar):
     - `WORKSPACE: [ 🔬 Simulation Studio ] [ 🎨 Figure Composer ]` (controlled via `self.set_perspective("simulation" | "composer")`).
   - **Tier 2: Central Viewport Switcher** (Central Header):
     - `VIEWPORT: [ 📊 Plot Viewer ] [ ⚡ Interactive Plots ]` (controlled via `self.set_canvas_mode(0 | 1)`).

---

## 4. Standard Verification Commands

After any modification, run automated tests using the venv interpreter:

```powershell
# Fast 3-Pillars validation test (Interactive Plots, Figure Composer, Caching Engine)
.venv\Scripts\python.exe tests/test_v35_three_pillars.py

# Complete 37-test automated discovery suite (Headless offscreen)
.venv\Scripts\python.exe -m unittest discover tests

# Physics solvers parameter & execution test
.venv\Scripts\python.exe tests/test_all_four_solvers.py
```
