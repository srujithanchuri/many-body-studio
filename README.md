# Many-Body Physics Studio Pro • Alpha v1

Modern, high-performance scientific desktop workbench for strongly correlated quantum heterostructures. Built with PySide6 (Qt6), isolated `QProcess` execution bridges, and dual-perspective workspace architecture.

---

## Key Features

1. **Dual-Perspective Architecture**:
   - 🔬 **Simulation Studio**: Full physics workspace with live parameter inspector, grid presets (N=64 to 256), batch queue, and sub-second calculation controls.
   - 🎨 **Publication Figure Studio**: Dedicated camera-ready multi-panel composer, Physical Review B formatting presets, vector PDF export (300+ DPI), and instant LaTeX snippet generator.

2. **Isolated Asynchronous Compute Engine**:
   - Subprocess `CalculationBridge` decoupled from Qt GUI thread (0% UI freeze).
   - High-contrast live solver console with rich HTML colored logs.
   - Instant sub-second cancellation with Windows process tree termination and CUDA VRAM purging.

3. **Multi-Backend Physics Engine**:
   - **GPU 64-Bit (CUDA / CuPy)**: Hardware-accelerated Dyson real-time FFT convolutions on NVIDIA GeForce RTX 5060 Laptop GPU.
   - **CPU Multithreaded (NumPy / SciPy)**: Dynamic CPU core usage limit controls (50% to 100%).

4. **Hardware-Accelerated CAD Viewport**:
   - `InteractivePlotCanvas` with sub-pixel rendering, smooth mousewheel zoom, click-drag panning, and coordinate inspection.

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
