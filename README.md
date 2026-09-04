# Many-Body Physics Studio Pro • Alpha v2

Modern, high-performance scientific desktop workbench for strongly correlated quantum heterostructures. Built with PySide6 (Qt6), isolated `QProcess` execution bridges, native multi-backend GPU/CPU physics engines, and dual-perspective workspace architecture.

---

## Key Features

1. **Complete 4-Study Multi-Backend Physics Suite**:
   - ⚡ **Spectral Sweep**: Full Brillouin zone composite density of states (DOS), Fermi surfaces, and high-symmetry path dispersion.
   - 🌊 **Quasiparticle Spectral Function $A(\mathbf{k}, \omega)$**: Single-point Dyson FFT convolutions, retarded self-energy $\Sigma(\mathbf{k}, \omega)$, and lifetime/scattering rate decomposition.
   - 📈 **Phase Diagram**: Exact root bisection search for the critical magnetic instability boundary $\det[\mathbf{1} - \mathbf{\Gamma}(\mathbf{q})\mathbf{\chi}_0(\mathbf{q})] = 0$ with AFM/FM order classification.
   - 📊 **RPA Spin Susceptibility**: Full-BZ static $\chi(\mathbf{q})$ intensity maps and dynamic $\chi(\mathbf{q}, \omega)$ energy-momentum slices with automatic bare bubble $\chi_0$ caching.

2. **Dual Execution Backends (GPU & CPU)**:
   - **NVIDIA CUDA GPU (`gpu64`)**: Hardware-accelerated CuPy FFTs and custom Numba CUDA kernels verified on NVIDIA GeForce RTX 5060 Laptop GPU.
   - **Multi-Threaded CPU (`cpu`)**: Parallel Linear Tetrahedron Method (LTM) with dynamic CPU core quota limits (50% to 100%).

3. **Isolated Asynchronous Compute Engine**:
   - Subprocess `CalculationBridge` decoupled from Qt GUI thread (0% UI freeze).
   - High-contrast live solver console with rich HTML colored logs.
   - Instant sub-second cancellation with Windows process tree termination, stopping cooldown, and CUDA VRAM purging.

4. **Hardware-Accelerated Viewport**:
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
