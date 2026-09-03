"""Qt-native QProcess execution bridge for Many-Body Studio Pro.
Coordinates subprocess execution, real-time stdout streaming, JSON protocol parsing,
2-stage cancellation, and GPU VRAM deallocation without GUI thread contention.
"""

import os
import sys
import json
import base64
from PySide6.QtCore import QObject, Signal, QProcess, QProcessEnvironment, QTimer

from pyside6_studio.backend.vram_cleaner import flush_gpu_vram, kill_process_tree

PROJECT_ROOT = r"C:\Users\sruji\Projects\masters_thesis"
GUI_ROOT = r"C:\Users\sruji\Projects\masters_thesis_gui"
STUDIO_DIR = os.path.join(GUI_ROOT, "pyside6_studio")


class CalculationBridge(QObject):
    """Coordinates isolated child process execution via QProcess."""

    sig_started = Signal()
    sig_progress = Signal(int, str)
    sig_log = Signal(str)
    sig_completed = Signal(dict)
    sig_error = Signal(str)
    sig_failed = sig_error  # Alias for backward compatibility
    sig_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = None
        self._running = False
        self._current_pid = None
        self._was_cancelled = False
        self._stdout_buffer = ""

    def is_running(self) -> bool:
        """Returns True if a child worker calculation is currently running."""
        return bool(self._running)

    @property
    def pid(self):
        """Returns the active child process PID or None."""
        if self._process and self._running:
            return self._process.processId()
        return self._current_pid

    @property
    def process_id(self):
        """Alias for pid."""
        return self.pid

    def start_calculation(self, params: dict):
        """Launches the worker CLI in an isolated QProcess child process."""
        if self.is_running():
            raise RuntimeError("Calculation already in progress")

        self._was_cancelled = False
        self._stdout_buffer = ""

        # Prepare worker CLI script path
        worker_script = os.path.join(STUDIO_DIR, "backend", "worker_cli.py")
        python_exe = sys.executable

        # Serialize params to Base64 JSON (safe across all OS command line interpreters)
        json_bytes = json.dumps(params).encode("utf-8")
        b64_params = base64.b64encode(json_bytes).decode("utf-8")

        # Clean up any lingering previous process signals
        if self._process is not None:
            try:
                self._process.finished.disconnect()
                self._process.errorOccurred.disconnect()
                self._process.readyReadStandardOutput.disconnect()
                self._process.readyReadStandardError.disconnect()
            except Exception:
                pass
            self._process.deleteLater()
            self._process = None

        self._process = QProcess(self)
        self._process.setProgram(python_exe)
        self._process.setArguments(["-u", worker_script, "--params-b64", b64_params])

        # Configure process environment with PYTHONPATH and unbuffered IO
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        existing_pythonpath = env.value("PYTHONPATH", "")
        paths_to_add = [PROJECT_ROOT, GUI_ROOT, STUDIO_DIR, os.path.join(PROJECT_ROOT, "self_energy"), os.path.join(PROJECT_ROOT, "susceptibility")]
        new_pythonpath = os.pathsep.join(paths_to_add)
        if existing_pythonpath:
            new_pythonpath = new_pythonpath + os.pathsep + existing_pythonpath
        env.insert("PYTHONPATH", new_pythonpath)
        self._process.setProcessEnvironment(env)

        # Connect signals
        self._process.readyReadStandardOutput.connect(self._on_stdout_ready)
        self._process.readyReadStandardError.connect(self._on_stderr_ready)
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(self._on_process_error)

        self._process.start()
        self._running = True
        self._current_pid = self._process.processId()

        self.sig_started.emit()

    def _on_stdout_ready(self):
        """Reads incoming stdout bytes, splits lines, and parses them."""
        if not self._process:
            return
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self._stdout_buffer += data

        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            line = line.strip("\r")
            if line:
                self.parse_line(line)

    def _on_stderr_ready(self):
        """Reads incoming stderr and emits to log signal."""
        if not self._process:
            return
        data = self._process.readAllStandardError().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            line = line.strip()
            if line:
                self.sig_log.emit(f"[STDERR] {line}")

    def parse_line(self, line: str):
        """Parses stdout line; routes JSON progress or plain log lines."""
        if not line:
            return

        # Attempt to parse as JSON protocol
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                if "progress" in payload and "step" in payload:
                    self.sig_progress.emit(int(payload["progress"]), str(payload["step"]))
                    return
                elif payload.get("type") == "completed":
                    self._running = False
                    self.sig_completed.emit(payload)
                    return
        except (json.JSONDecodeError, ValueError):
            pass

        # Plain text log message - inspect for progress milestones to advance progress bar smoothly
        if "Starting 1-Loop FFT" in line:
            self.sig_progress.emit(50, "Solving 1-Loop Dyson FFT on RTX 5060...")
        elif "1-Loop FFT completed" in line:
            self.sig_progress.emit(60, "1-Loop FFT completed. Starting 3-Loop...")
        elif "Starting 3-Loop FFT" in line:
            self.sig_progress.emit(65, "Solving 3-Loop Dyson FFT on RTX 5060...")
        elif "3-Loop FFT completed" in line:
            self.sig_progress.emit(75, "FFT convolutions finished. Scaling self-energies...")
        elif "Scaling for" in line:
            self.sig_progress.emit(80, "Applying Kondo/interlayer coupling scaling...")
        elif "Generating Sweep Plots" in line:
            self.sig_progress.emit(90, "Rendering composite high-resolution plots...")

        self.sig_log.emit(line)

    def cancel_calculation(self):
        """
        Executes 2-stage cancellation:
        Stage 1: QProcess.terminate() soft interrupt
        Stage 2: kill_process_tree native Windows process kill and GPU VRAM flush.
        """
        if not self.is_running():
            return  # Safe no-op when idle

        self._was_cancelled = True
        pid_to_kill = self.pid

        # Stage 1: Soft terminate
        if self._process and self._process.state() != QProcess.NotRunning:
            self._process.terminate()

        # Stage 2: Ensure hard kill if still alive
        if pid_to_kill:
            kill_process_tree(pid_to_kill)

        flush_gpu_vram()

        self._running = False
        self.sig_cancelled.emit()

    def _on_calculation_finished(self, success: bool, plot_path: str = "", data_path: str = ""):
        """Helper to simulate completion or emit completion payload."""
        self._running = False
        payload = {
            "type": "completed",
            "success": success,
            "plot_path": plot_path,
            "data_path": data_path
        }
        self.sig_completed.emit(payload)

    def _on_process_finished(self, exit_code: int, exit_status):
        """Handles process termination and exit code inspection."""
        # Flush any remaining buffer
        if self._stdout_buffer.strip():
            self.parse_line(self._stdout_buffer.strip())
            self._stdout_buffer = ""

        flush_gpu_vram()

        was_running = self._running
        self._running = False

        if self._was_cancelled:
            return

        if exit_code != 0:
            self.sig_error.emit(f"Calculation process failed with exit code {exit_code}")
        elif was_running:
            # If exited 0 but no completed JSON was parsed
            self.sig_completed.emit({"type": "completed", "success": True})

    def _on_process_error(self, error):
        """Handles QProcess internal errors (e.g. FailedToStart, Crashed)."""
        if self._was_cancelled:
            return
        self._running = False
        flush_gpu_vram()
        self.sig_error.emit(f"Process execution error: {error}")
