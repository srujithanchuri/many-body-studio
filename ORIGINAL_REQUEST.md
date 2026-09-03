# Original User Request

## 2026-09-03T20:11:06Z

Build a polished, production-grade PySide6 scientific desktop application (Many-Body Studio Pro) implementing the first complete vertical slice (Steps 1, 2, and 3): core engine foundation, safe QProcess background worker with GPU memory cleanup, and full-stack interactive execution of Spectral Sweeps.

Working directory: C:\Users\sruji\Projects\masters_thesis_gui
Integrity mode: development

## Requirements

### R1. Core Foundation & Hardware Diagnostics
Implement global path configuration, numerical resolution presets (`Fast Preview N=64`, `Standard N=100`, `High-Res Production N=256`), and hardware detection reporting NVIDIA CUDA GPU availability (e.g. RTX 5060), total VRAM, and CPU fallback.

### R2. Isolated QProcess Worker & GPU VRAM Cleaner
Implement a background execution bridge running calculations in an isolated child process via Qt's native `QProcess` with asynchronous stdout/stderr streaming to protect the GUI from crashes, GIL contention, or CUDA segfaults. Include:
1. Structured JSON progress protocol emitted over stdout (`{"progress": 45, "step": "1-Loop FFT"}`).
2. 2-stage cancellation mechanism (`QProcess.terminate()` with a 1.5s timeout falling back to `QProcess.kill()` for native OS-level termination).
3. Guaranteed CuPy memory pool deallocation (`free_all_blocks()`) upon completion, error, or cancellation.

### R3. Vertical Slice UI & Spectral Sweep End-to-End Execution
Provide a curated, polished PySide6 UI featuring:
1. Context-adaptive parameter inspector with inputs for model Hamiltonian ($t, t', \mu, K$) and spectral sweep controls ($J_K$ vs $J_\perp$).
2. Live streaming solver console tab displaying real-time stdout logs from `self_energy.sweep_core` without UI lag.
3. Hardware-accelerated interactive canvas (`QGraphicsView`) with smooth mousewheel zoom, pan, and double-click fit, automatically loading the newly calculated plot upon completion.
4. Active "⚡ Run" and "⏹ Cancel / Stop" toolbar controls wired directly to the `QProcess` supervisor.

## Acceptance Criteria

### Execution & Visualization
- [ ] Studio launches via `run_studio.bat` with zero startup errors or warnings.
- [ ] Clicking "⚡ Run Active" launches the Spectral Sweep in an isolated `QProcess`.
- [ ] Solver stdout logs stream line-by-line into the live console tab in real time via Qt signals (`readyReadStandardOutput`).
- [ ] Upon calculation completion, the resulting plot image automatically displays on the interactive canvas.
- [ ] Canvas supports smooth mousewheel zoom centered on cursor and click-drag pan.

### Stability & GPU Memory Lifecycle
- [ ] Clicking "⏹ Cancel" mid-calculation immediately halts execution within 1.0 second using `QProcess` termination.
- [ ] Background process is terminated cleanly and does not linger as an orphan Windows process.
- [ ] CuPy GPU memory pools are flushed (`free_all_blocks()`), verified with zero VRAM leak.
- [ ] Any intentional or simulated worker failure/exception is caught cleanly without freezing or crashing the PySide6 GUI.
