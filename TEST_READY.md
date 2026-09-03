# TEST_READY: Many-Body Studio Pro E2E Test Suite

> **Status**: READY FOR MILESTONE IMPLEMENTATION  
> **Framework**: Python Standard Library `unittest` (Headless Offscreen Mode)  
> **Platform**: Windows 11 / PySide6 6.11.2  
> **Date**: 2026-09-04  

---

## 1. Test Suite Verification Command

The complete automated test suite is verified executable with zero external runner dependencies:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

---

## 2. Test Suite Structure & Tier Counts

| Tier | Test File | Test Class | Count | Description |
|---|---|---|---|---|
| **Tier 1** | `tests/test_e2e_tier1.py` | `TestTier1FeatureCoverage` | 13 | Comprehensive coverage of all 13 core features |
| **Tier 2** | `tests/test_e2e_tier2.py` | `TestTier2BoundaryCornerCases` | 13 | Numerical bounds, malformed inputs, GPU fallback, timeouts |
| **Tier 3** | `tests/test_e2e_tier3.py` | `TestTier3CrossFeatureInteractions` | 6 | Cross-component interactions, state synchronization, lifecycle |
| **Tier 4** | `tests/test_e2e_tier4.py` | `TestTier4RealWorldScenarios` | 4 | Real-world execution, 1s cancellation, VRAM deallocation, CAD canvas |
| **TOTAL** | | | **36** | **Complete Opaque-Box Coverage** |

---

## 3. Feature Coverage Matrix (13 Features)

| # | Feature Name | Tier 1 Test | Tier 2 Test | Tier 3 Test | Tier 4 Test |
|---|---|---|---|---|---|
| **F01** | Global Path Configuration | `test_f01_global_path_configuration` | — | — | — |
| **F02** | Numerical Resolution Presets | `test_f02_numerical_resolution_presets` | `test_boundary_grid_resolution_bounds`, `test_corner_invalid_preset_lookup` | `test_cross_parameter_edit_and_preset_sync` | — |
| **F03** | Hardware Diagnostics & CUDA Detection | `test_f03_hardware_diagnostics_cuda_detection` | `test_corner_missing_gpu_fallback` | `test_cross_hardware_badge_update_on_environment_probe` | — |
| **F04** | Isolated QProcess Worker Runner | `test_f04_isolated_qprocess_worker_runner` | — | — | `test_scenario_full_end_to_end_calculation_and_canvas_display` |
| **F05** | Structured JSON Progress Protocol | `test_f05_structured_json_progress_protocol` | `test_corner_broken_malformed_json_stream` | `test_cross_streaming_console_and_progress_updates` | `test_scenario_full_end_to_end_calculation_and_canvas_display` |
| **F06** | 2-Stage Cancellation Mechanism | `test_f06_two_stage_cancellation_mechanism` | `test_corner_cancel_when_not_running` | `test_cross_bridge_start_cancel_restart_flow` | `test_scenario_subsecond_cancellation_zero_orphan_processes` |
| **F07** | Guaranteed CuPy VRAM Cleanup | `test_f07_guaranteed_cupy_vram_cleanup` | `test_corner_process_kill_timeout_unresponsive_worker` | `test_cross_window_close_cleans_active_process_and_vram` | `test_scenario_gpu_vram_lifecycle_zero_leak` |
| **F08** | Context-Adaptive Parameter Inspector | `test_f08_context_adaptive_parameter_inspector` | `test_boundary_zero_and_negative_hopping`, `test_corner_empty_and_whitespace_sweep_values`, `test_corner_malformed_and_delimiter_sweep_values`, `test_corner_valid_single_and_spaced_sweep_values` | `test_cross_parameter_edit_and_preset_sync` | — |
| **F09** | Live Streaming Solver Console | `test_f09_live_streaming_solver_console` | `test_corner_broken_malformed_json_stream` | `test_cross_streaming_console_and_progress_updates` | `test_scenario_full_end_to_end_calculation_and_canvas_display` |
| **F10** | Interactive Plot Canvas | `test_f10_interactive_plot_canvas` | — | `test_cross_completion_triggers_canvas_auto_display` | `test_scenario_interactive_cad_canvas_navigation` |
| **F11** | Active Run / Cancel Toolbar Controls | `test_f11_active_run_cancel_toolbar_controls` | `test_corner_duplicate_run_clicks_prevented` | `test_cross_bridge_start_cancel_restart_flow` | `test_scenario_subsecond_cancellation_zero_orphan_processes` |
| **F12** | Batch Launch Script | `test_f12_batch_launch_script` | — | — | — |
| **F13** | Worker Exception & Error Resilience | `test_f13_worker_exception_error_resilience` | `test_corner_worker_crash_handling` | `test_cross_window_close_cleans_active_process_and_vram` | `test_scenario_subsecond_cancellation_zero_orphan_processes` |

---

## 4. Current Baseline Execution Results

```
Ran 36 tests in 1.598s

Status: 21 PASSED, 15 PENDING IMPLEMENTATION
```

### 4.1 Passing Baseline Tests (21 Tests)
1. `test_f01_global_path_configuration`: Global path constants validated.
2. `test_f02_numerical_resolution_presets`: Presets N=64, N=100, N=256 validated.
3. `test_f03_hardware_diagnostics_cuda_detection`: Diagnostics dictionary schema validated.
4. `test_f07_guaranteed_cupy_vram_cleanup`: VRAM flusher and process tree killer safety validated.
5. `test_f08_context_adaptive_parameter_inspector`: Parameter controls present and functional.
6. `test_f09_live_streaming_solver_console`: Console read-only buffer validated.
7. `test_f10_interactive_plot_canvas`: Zoom, pan mode, fit in view, and coordinate tracking validated.
8. `test_boundary_zero_and_negative_broadening`: Presets enforce eta >= 0.001.
9. `test_boundary_zero_and_negative_hopping`: Hopping spinbox minimum clamp verified.
10. `test_boundary_grid_resolution_bounds`: Presets enforce N >= 32.
11. `test_corner_empty_and_whitespace_sweep_values`: Empty input validation verified.
12. `test_corner_malformed_and_delimiter_sweep_values`: Malformed token error rejection verified.
13. `test_corner_valid_single_and_spaced_sweep_values`: Float tokenization verified.
14. `test_corner_invalid_preset_lookup`: Safe dictionary lookup verified.
15. `test_corner_missing_gpu_fallback`: CPU fallback with core count verified.
16. `test_corner_process_kill_timeout_unresponsive_worker`: Process tree kill verified on child process.
17. `test_cross_completion_triggers_canvas_auto_display`: Canvas load verified.
18. `test_cross_streaming_console_and_progress_updates`: Streaming append verified.
19. `test_cross_window_close_cleans_active_process_and_vram`: Window close cleanup verified.
20. `test_scenario_gpu_vram_lifecycle_zero_leak`: Memory pool deallocation verified.
21. `test_scenario_interactive_cad_canvas_navigation`: CAD mouse interaction scenario verified.

### 4.2 Pending Implementation Tests (15 Tests)
These tests assert exact contracts and will transition from `FAIL` to `PASS` as milestones are completed:
- **Milestone M1 (Foundation & Bat)**:
  - `test_f12_batch_launch_script`: Needs UTF-8 (`chcp 65001` or `PYTHONIOENCODING=utf-8`) in `run_studio.bat`.
  - `test_cross_hardware_badge_update_on_environment_probe`: Needs UI badge label to dynamically sync with `get_hardware_info()`.
  - `test_cross_parameter_edit_and_preset_sync`: Needs `spin_t1` range configured to accept negative values ($t' \in [-2.0, 2.0]$).
- **Milestone M2 (Isolated QProcess Worker & Bridge)**:
  - `test_f04_isolated_qprocess_worker_runner`: Awaiting `pyside6_studio/backend/worker_cli.py`.
  - `test_f05_structured_json_progress_protocol`: Awaiting `pyside6_studio/backend/bridge.py`.
  - `test_f06_two_stage_cancellation_mechanism`: Awaiting `CalculationBridge.cancel_calculation()`.
  - `test_f13_worker_exception_error_resilience`: Awaiting bridge error handling.
  - `test_corner_duplicate_run_clicks_prevented`: Awaiting bridge run lock.
  - `test_corner_cancel_when_not_running`: Awaiting bridge idle cancel guard.
  - `test_corner_broken_malformed_json_stream`: Awaiting bridge stdout parser.
  - `test_corner_worker_crash_handling`: Awaiting bridge process error handler.
- **Milestone M3 (Vertical Slice UI & Full Integration)**:
  - `test_f11_active_run_cancel_toolbar_controls`: Awaiting dedicated Cancel button wired in toolbar.
  - `test_cross_bridge_start_cancel_restart_flow`: Awaiting full UI toolbar -> bridge wiring.
  - `test_scenario_full_end_to_end_calculation_and_canvas_display`: Awaiting end-to-end sweep execution.
  - `test_scenario_subsecond_cancellation_zero_orphan_processes`: Awaiting sub-second cancellation execution.

---

## 5. Instructions for Milestone Implementing Agents

When working on Milestones M1, M2, and M3:
1. Do **not** modify test assertions to fit an incomplete implementation; implement the code to satisfy the test specifications.
2. Run your specific tier test command during development:
   - For M1: `.venv\Scripts\python.exe -m unittest tests/test_e2e_tier1.py`
   - For M2: `.venv\Scripts\python.exe -m unittest tests/test_e2e_tier2.py`
   - For M3: `.venv\Scripts\python.exe -m unittest tests/test_e2e_tier3.py tests/test_e2e_tier4.py`
3. Verify all 36 tests pass by Milestone Completion:
   `.venv\Scripts\python.exe -m unittest discover -s tests`
