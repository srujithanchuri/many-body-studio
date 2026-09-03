# Test Infrastructure Specification: Many-Body Studio Pro

## 1. Overview & Architectural Philosophy

The Many-Body Studio Pro automated test suite provides an **opaque-box, requirement-driven, headless** testing harness across all architectural layers of the application. 
The test architecture strictly adheres to:
1. **Zero-Flake Decoupling**: Compute kernels and UI presentation execute asynchronously; tests verify IPC signals, process isolation boundaries, and state transitions without timing deadlocks.
2. **Standard Library `unittest`**: Tests utilize Python's standard library `unittest` module, requiring zero external test runner dependencies (such as `pytest` or `pytest-qt`).
3. **Headless Offscreen Execution**: All PySide6 GUI and `QGraphicsView` tests run completely headless by configuring `QT_QPA_PLATFORM=offscreen`. No display server, physical monitor, or GUI window is spawned during execution.
4. **Deterministic GPU & Process Safety**: Tests verify that process termination leaves zero orphan Windows processes and that CuPy GPU memory pools are flushed with 0 bytes of residual VRAM allocation.

---

## 2. Directory Layout

The test suite is located in the root `tests/` directory:

```
masters_thesis_gui/
├── tests/
│   ├── __init__.py            # Sets QT_QPA_PLATFORM=offscreen, sys.path
│   ├── helpers.py             # Shared test helpers, SignalCollector, test fixtures
│   ├── test_e2e_tier1.py      # Tier 1: Feature Coverage (Features 1 through 13)
│   ├── test_e2e_tier2.py      # Tier 2: Boundary & Corner Cases
│   ├── test_e2e_tier3.py      # Tier 3: Cross-Feature Interactions
│   └── test_e2e_tier4.py      # Tier 4: Real-World Application Scenarios
├── TEST_INFRA.md              # Test infrastructure documentation (this document)
└── TEST_READY.md              # Test readiness declaration and feature checklist
```

---

## 3. Environment & Runtime Requirements

### 3.1 Python Interpreter
- Recommended Python: `.venv\Scripts\python.exe` (PySide6 6.11.2, Python 3.12.10).
- Physics Python: `C:\Users\sruji\Projects\masters_thesis\.venv\Scripts\python.exe` (CuPy 13.6.0, CUDA 12 runtime wheels).

### 3.2 Environment Variables
The test runner and test modules automatically enforce the following environment variables:
- `QT_QPA_PLATFORM=offscreen`: Enables headless Qt widget instantiation.
- `PYTHONIOENCODING=utf-8`: Guarantees UTF-8 console encoding on Windows command prompts to prevent charmap codec errors.

---

## 4. Test Infrastructure Components (`tests/helpers.py`)

### 4.1 Headless Qt Singleton (`get_qapp`)
Instantiates a singleton `QApplication(["--platform", "offscreen"])` if not already created, preventing duplicate `QApplication` instantiation errors.

### 4.2 Qt Event Loop Pump (`process_events`)
Spins `QEventLoop` via `QTimer.singleShot()` to allow queued Qt signal/slot deliveries and deferred events to dispatch deterministically without blocking.

### 4.3 Signal Spy (`SignalCollector`)
A Qt signal spy that connects to any PySide6 `Signal`, records emitted payloads and emission counts, and provides `wait_until(condition_fn, timeout_sec)` to await asynchronous state changes without arbitrary sleep delays.

### 4.4 Test Image Generator (`create_test_image`)
Generates valid minimal PNG images on-the-fly using `QImage` and `QPainter`, saving to temporary directories for testing canvas loading, zoom, and pan operations.

### 4.5 Process Table Inspector (`is_process_alive`)
Queries the Windows operating system process table (`tasklist /FI "PID eq <pid>"`) to verify native child process termination and ensure zero orphan process leaks.

---

## 5. Test Execution Commands

### 5.1 Run Full Test Suite (Headless Discovery)
```powershell
$env:QT_QPA_PLATFORM="offscreen"
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

### 5.2 Run Specific Tier
```powershell
# Tier 1: Feature Coverage
.venv\Scripts\python.exe -m unittest tests/test_e2e_tier1.py

# Tier 2: Boundary & Corner Cases
.venv\Scripts\python.exe -m unittest tests/test_e2e_tier2.py

# Tier 3: Cross-Feature Interactions
.venv\Scripts\python.exe -m unittest tests/test_e2e_tier3.py

# Tier 4: Real-World Scenarios
.venv\Scripts\python.exe -m unittest tests/test_e2e_tier4.py
```

### 5.3 Run Single Test Method
```powershell
.venv\Scripts\python.exe -m unittest tests.test_e2e_tier1.TestTier1FeatureCoverage.test_f01_global_path_configuration
```

---

## 6. Progressive Milestone Verification Matrix

| Tier | File | Scope | Passing Initially | Awaiting Milestones |
|---|---|---|---|---|
| **Tier 1** | `test_e2e_tier1.py` | Features 1–13 Coverage | 7 | 6 (M2: worker_cli, bridge; M3: cancel button, bat utf8) |
| **Tier 2** | `test_e2e_tier2.py` | Boundary & Corner Cases | 9 | 4 (M2: bridge error/cancellation handling) |
| **Tier 3** | `test_e2e_tier3.py` | Cross-Feature Interactions | 3 | 3 (M1/M3: badge sync, t1 negative bounds, bridge flow) |
| **Tier 4** | `test_e2e_tier4.py` | Real-World Application Scenarios | 2 | 2 (M2/M3: full e2e execution, 1s cancellation) |
| **Total** | | **36 Test Cases** | **21 PASS** | **15 PENDING** |
