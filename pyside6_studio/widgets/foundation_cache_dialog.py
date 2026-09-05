"""In-situ Foundation Cache Synthesizer dialog for Many-Body Studio Pro.
Allows direct evaluation of base self-energy (1-loop & 3-loop FFT) or bare susceptibility
without requiring the user to configure or run batch parameter sweeps.
"""

import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QDoubleSpinBox, QProgressBar, QFrame, QMessageBox,
    QGroupBox
)

from pyside6_studio.backend.bridge import CalculationBridge
from pyside6_studio.core.config import DEFAULT_RESULTS_DIR


class FoundationCacheDialog(QDialog):
    """
    Direct in-situ synthesizer dialog for intermediate foundation arrays:
    - Sigma_base(k, omega) (Total 1-loop + 3-loop FFT convolution)
    - Bare Static chi0(q)
    - Bare Dynamic chi0(q, omega)
    """
    sig_cache_generated = Signal(str)

    def __init__(self, parent=None, out_dir: str = DEFAULT_RESULTS_DIR,
                 default_category: str = "sigma_base", default_mu: float = 0.0,
                 default_jperp: float = 6.0):
        super().__init__(parent)
        self.out_dir = out_dir
        self.setWindowTitle("▶ Foundation Cache Synthesizer")
        self.setMinimumWidth(440)
        self.setModal(False)

        self.bridge = CalculationBridge(self)
        self.bridge.sig_status.connect(self._on_bridge_status)
        self.bridge.sig_completed.connect(self._on_bridge_completed)
        self.bridge.sig_error.connect(self._on_bridge_error)
        self.bridge.sig_cancelled.connect(self._on_bridge_cancelled)

        self._build_ui(default_category, default_mu, default_jperp)

        # Check if engine is already busy
        main_win = self._find_main_window()
        if main_win and hasattr(main_win, "bridge") and main_win.bridge.is_running():
            self.update_engine_state(True)

    def _find_main_window(self):
        """Locates the parent or global MainWindow instance managing execution."""
        p = self.parent()
        while p:
            if hasattr(p, "run_or_queue_foundation_job"):
                return p
            p = p.parent()
        for w in QApplication.topLevelWidgets():
            if hasattr(w, "run_or_queue_foundation_job"):
                return w
        return None

    def _build_ui(self, default_cat: str, default_mu: float, default_jperp: float):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(16, 16, 16, 16)

        is_dark = False
        if self.parent() and hasattr(self.parent(), "is_dark"):
            is_dark = self.parent().is_dark
        else:
            win_col = self.palette().window().color()
            is_dark = win_col.lightness() < 128

        title_color = "#f8fafc" if is_dark else "#0f172a"
        desc_color = "#94a3b8" if is_dark else "#475569"
        border_color = "#334155" if is_dark else "#cbd5e1"
        grp_color = "#cbd5e1" if is_dark else "#334155"

        # Header info
        lbl_title = QLabel("▶ In-Situ Foundation Synthesizer")
        lbl_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {title_color};")
        lay.addWidget(lbl_title)

        lbl_desc = QLabel(
            "Synthesize base foundation arrays in milliseconds for real-time 60 FPS exploration "
            "in Interactive Plots. No batch sweeper or plot generation required."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"font-size: 11px; color: {desc_color}; line-height: 1.3;")
        lay.addWidget(lbl_desc)

        # Form Card
        grp_form = QGroupBox("Foundation Parameters")
        grp_form.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 700;
                font-size: 11px;
                color: {grp_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 14px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }}
        """)
        f_lay = QVBoxLayout(grp_form)
        f_lay.setSpacing(8)

        # Category
        h_cat = QHBoxLayout()
        h_cat.addWidget(QLabel("Target:"))
        self.cb_category = QComboBox()
        self.cb_category.addItems([
            "Self-Energy Σ(k, ω)",
            "Bare Static Susceptibility χ₀(q)",
            "Bare Dynamic Susceptibility χ₀(q, ω)"
        ])
        if "dynamic" in default_cat:
            self.cb_category.setCurrentIndex(2)
        elif "susc" in default_cat or "chi0" in default_cat:
            self.cb_category.setCurrentIndex(1)
        else:
            self.cb_category.setCurrentIndex(0)
        self.cb_category.currentIndexChanged.connect(self._on_category_changed)
        h_cat.addWidget(self.cb_category, 1)
        f_lay.addLayout(h_cat)

        # Chemical Potential mu
        h_mu = QHBoxLayout()
        h_mu.addWidget(QLabel("Chemical Potential (μ):"))
        self.spin_mu = QDoubleSpinBox()
        self.spin_mu.setRange(-20.0, 20.0)
        self.spin_mu.setSingleStep(0.1)
        self.spin_mu.setDecimals(2)
        self.spin_mu.setValue(default_mu)
        self.spin_mu.setFixedWidth(100)
        h_mu.addWidget(self.spin_mu)
        f_lay.addLayout(h_mu)

        # Interlayer J_perp (only for self-energy)
        self.row_jperp = QWidget()
        h_jp = QHBoxLayout(self.row_jperp)
        h_jp.setContentsMargins(0, 0, 0, 0)
        h_jp.addWidget(QLabel("Interlayer Coupling (J_⊥):"))
        self.spin_jperp = QDoubleSpinBox()
        self.spin_jperp.setRange(0.0, 50.0)
        self.spin_jperp.setSingleStep(0.5)
        self.spin_jperp.setDecimals(2)
        self.spin_jperp.setValue(default_jperp)
        self.spin_jperp.setFixedWidth(100)
        h_jp.addWidget(self.spin_jperp)
        f_lay.addWidget(self.row_jperp)

        # Grid Resolution N
        h_n = QHBoxLayout()
        h_n.addWidget(QLabel("Grid Resolution (N):"))
        self.cb_n = QComboBox()
        self.cb_n.addItems([
            "Fast Preview (N=100)",
            "High-Res Production (N=256)",
            "Ultra Fast (N=64)"
        ])
        self.cb_n.setCurrentIndex(0)  # Default N=100
        h_n.addWidget(self.cb_n, 1)
        f_lay.addLayout(h_n)

        # Solver choice
        h_solv = QHBoxLayout()
        h_solv.addWidget(QLabel("Solver Backend:"))
        self.cb_solver = QComboBox()
        self.cb_solver.addItems([
            "CUDA GPU 64-bit (NVIDIA RTX)",
            "Multi-Core CPU (NumPy / SciPy)"
        ])
        h_solv.addWidget(self.cb_solver, 1)
        f_lay.addLayout(h_solv)

        lay.addWidget(grp_form)

        # Progress bar & status label
        self.lbl_status = QLabel("Ready to synthesize.")
        self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #2563eb;")
        lay.addWidget(self.lbl_status)

        self.pbar = QProgressBar()
        self.pbar.setTextVisible(False)
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.pbar.setFixedHeight(8)
        self.pbar.setStyleSheet("""
            QProgressBar {
                background: #e2e8f0;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background: #2563eb;
                border-radius: 4px;
            }
        """)
        lay.addWidget(self.pbar)

        # Action Buttons
        h_btn = QHBoxLayout()
        h_btn.addStretch(1)

        self.btn_cancel = QPushButton("Close")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                padding: 5px 14px;
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                color: #475569;
            }
            QPushButton:hover { background: #e2e8f0; color: #0f172a; }
        """)
        self.btn_cancel.clicked.connect(self._on_cancel)
        h_btn.addWidget(self.btn_cancel)

        self.btn_run = QPushButton("▶ Run")
        self.btn_compute = self.btn_run  # Alias for backward compatibility
        self.btn_run.setStyleSheet("""
            QPushButton {
                padding: 5px 16px;
                background: #2563eb;
                border: 1px solid #1d4ed8;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 700;
                color: #ffffff;
            }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:disabled { background: #94a3b8; border-color: #94a3b8; }
        """)
        self.btn_run.clicked.connect(self._start_or_queue_synthesis)
        h_btn.addWidget(self.btn_run)

        lay.addLayout(h_btn)

        self._on_category_changed(self.cb_category.currentIndex())

    def update_engine_state(self, is_running: bool):
        """Updates the action button state based on whether the engine is active."""
        if is_running:
            self.btn_run.setText("➕ Add to Queue")
            self.btn_run.setStyleSheet("""
                QPushButton {
                    padding: 5px 16px;
                    background: #d97706;
                    border: 1px solid #b45309;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                    color: #ffffff;
                }
                QPushButton:hover { background: #b45309; }
            """)
        else:
            self.btn_run.setText("▶ Run")
            self.btn_run.setStyleSheet("""
                QPushButton {
                    padding: 5px 16px;
                    background: #2563eb;
                    border: 1px solid #1d4ed8;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                    color: #ffffff;
                }
                QPushButton:hover { background: #1d4ed8; }
            """)

    def _on_category_changed(self, idx: int):
        is_sigma = (idx == 0)
        self.row_jperp.setVisible(is_sigma)

    def _start_or_queue_synthesis(self):
        cat_idx = self.cb_category.currentIndex()
        if cat_idx == 0:
            category = "sigma_base"
        elif cat_idx == 1:
            category = "chi0_static"
        else:
            category = "chi0_dynamic"

        n_idx = self.cb_n.currentIndex()
        N = 100 if n_idx == 0 else (256 if n_idx == 1 else 64)
        solver = "gpu" if self.cb_solver.currentIndex() == 0 else "cpu"

        params = {
            "task": "foundation_cache",
            "cache_category": category,
            "mu": float(self.spin_mu.value()),
            "fixed_jperp": float(self.spin_jperp.value()),
            "Jperp": float(self.spin_jperp.value()),
            "N": N,
            "t": 1.0,
            "t1": 0.0,
            "K": 1.0,
            "solver_choice": solver,
            "force_recompute": True,
            "output_dir": self.out_dir
        }

        main_win = self._find_main_window()
        if main_win and hasattr(main_win, "run_or_queue_foundation_job"):
            outcome = main_win.run_or_queue_foundation_job(params)
            if outcome == "queued":
                self.lbl_status.setText("⏳ Job added to Batch Execution Queue.")
                self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #d97706;")
                self.pbar.setRange(0, 100)
                self.pbar.setValue(0)
            else:
                self.lbl_status.setText("▶ Synthesizing on main engine in background...")
                self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #2563eb;")
                self.pbar.setRange(0, 0)
                self.update_engine_state(True)
        else:
            # Fallback for isolated execution / unit testing
            self.pbar.setRange(0, 0)
            self.lbl_status.setText("▶ Synthesizing foundation array...")
            self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #2563eb;")
            self.bridge.start_calculation(params)
            self.update_engine_state(True)

    def _on_bridge_status(self, msg: str):
        self.lbl_status.setText(msg)

    def _on_bridge_completed(self, payload: dict):
        self.pbar.setRange(0, 100)
        self.pbar.setValue(100)
        self.lbl_status.setText("✅ Foundation synthesis completed successfully.")
        self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #16a34a;")
        self.update_engine_state(False)

        target_data = payload.get("data_path", "")
        self.sig_cache_generated.emit(target_data)

    def _on_bridge_error(self, err: str):
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.lbl_status.setText(f"❌ Synthesis failed: {err}")
        self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #dc2626;")
        self.update_engine_state(False)

    def _on_bridge_cancelled(self):
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.lbl_status.setText("Calculation cancelled.")
        self.update_engine_state(False)

    def _on_cancel(self):
        self.reject()

    def closeEvent(self, event):
        # Dialog close does NOT kill running calculations on the main engine
        event.accept()
