"""Live Analytical Physics Lab for Many-Body Studio Pro.

Pillar 3: On-the-fly physics powered by cached foundation arrays (.npz in results/cache/):
1. Interactive Brillouin Zone k-Probe: Click or drag anywhere in [-π, π]² to evaluate A(k, ω), Re Σ, Im Σ in real time (< 1 ms).
2. Continuous J_K slider (0.1 to 12.0) with live 60 FPS analytical scaling.
3. 2D Quasiparticle Weight Map Z(k_x, k_y) across the full Brillouin Zone revealing mass enhancement hot spots.
4. Dynamic energy-sliced Fermi surface movie (slider for energy ω).
5. Live RPA static magnetic susceptibility χ_RPA(q_x, q_y) with real-time instability tracking.
"""

import io
import os
import glob
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from mpl_toolkits.axes_grid1 import make_axes_locatable

from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QFrame, QMessageBox, QFileDialog, QDoubleSpinBox,
    QSizePolicy
)

from pyside6_studio.core.config import DEFAULT_RESULTS_DIR
from pyside6_studio.core.cache_manager import (
    normalize_results_dir,
    get_ibz_indices_and_map,
    byte_unshuffle_f32,
    LazyIBZArray
)
from pyside6_studio.widgets.analytical_modes import (
    BaseAnalyticalMode,
    SpectralFunctionMode,
    EnergySliceMode,
    BandDispersionMode,
    StaticSusceptibilityMode,
    DynamicSusceptibilityMode,
    RpaSusceptibilityMode,
)


def format_smart_cache_label(fname: str, ftype: str) -> str:
    """
    Creates concise, human-friendly, physics-rich cache labels that consume minimal space.
    Formats Σ and χ₀ identifiers with physical and computational parameters (no 'Base' prefix).
    """
    import re
    if ftype == "sigma_base" or fname.startswith("sigma_base"):
        jp_match = re.search(r"Jperp_([0-9.]+)", fname) or re.search(r"J_perp_([0-9.]+)", fname)
        n_match = re.search(r"N_([0-9]+)", fname) or re.search(r"N([0-9]+)", fname)
        mu_match = re.search(r"mu_([0-9.-]+)", fname) or re.search(r"mu([0-9.-]+)", fname)
        eta_match = re.search(r"eta_([0-9.]+)", fname)
        parts = []
        if mu_match:
            try: parts.append(f"μ={float(mu_match.group(1)):.1f}")
            except ValueError: parts.append(f"μ={mu_match.group(1)}")
        if jp_match:
            try: parts.append(f"J⊥={float(jp_match.group(1)):.1f}")
            except ValueError: parts.append(f"J⊥={jp_match.group(1)}")
        if n_match:
            parts.append(f"N={n_match.group(1)}")
        if eta_match:
            try: parts.append(f"η={float(eta_match.group(1)):.2f}")
            except ValueError: pass
        param_str = f" ({', '.join(parts)})" if parts else ""
        return f"Σ{param_str}"

    elif ftype == "chi0_static" or fname.startswith("chi0_static"):
        jp_match = re.search(r"Jperp_([0-9.]+)", fname) or re.search(r"J_perp_([0-9.]+)", fname)
        n_match = re.search(r"N_([0-9]+)", fname) or re.search(r"N([0-9]+)", fname)
        mu_match = re.search(r"mu_([0-9.-]+)", fname) or re.search(r"mu([0-9.-]+)", fname)
        parts = []
        if mu_match:
            try: parts.append(f"μ={float(mu_match.group(1)):.1f}")
            except ValueError: parts.append(f"μ={mu_match.group(1)}")
        if jp_match:
            try: parts.append(f"J⊥={float(jp_match.group(1)):.1f}")
            except ValueError: parts.append(f"J⊥={jp_match.group(1)}")
        if n_match:
            parts.append(f"N={n_match.group(1)}")
        param_str = f" ({', '.join(parts)})" if parts else ""
        return f"Static χ₀{param_str}"

    elif ftype == "chi0_dynamic" or fname.startswith("chi0_dynamic"):
        jp_match = re.search(r"Jperp_([0-9.]+)", fname) or re.search(r"J_perp_([0-9.]+)", fname)
        n_match = re.search(r"N_([0-9]+)", fname) or re.search(r"N([0-9]+)", fname)
        mu_match = re.search(r"mu_([0-9.-]+)", fname) or re.search(r"mu([0-9.-]+)", fname)
        parts = []
        if mu_match:
            try: parts.append(f"μ={float(mu_match.group(1)):.1f}")
            except ValueError: pass
        if jp_match:
            try: parts.append(f"J⊥={float(jp_match.group(1)):.1f}")
            except ValueError: pass
        if n_match:
            parts.append(f"N={n_match.group(1)}")
        param_str = f" ({', '.join(parts)})" if parts else ""
        return f"Dynamic χ₀{param_str}"

    return fname[:28] + ("..." if len(fname) > 28 else "")


def parse_cache_metadata(fname: str, ftype: str) -> dict:
    """Extracts numeric physical parameters and category from cache filenames."""
    import re
    meta = {
        "mu": None,
        "Jperp": None,
        "N": None,
        "eta": None,
        "category": "sigma" if (ftype == "sigma_base" or fname.startswith("sigma_base")) else (
            "chi0_dynamic" if (ftype == "chi0_dynamic" or fname.startswith("chi0_dynamic")) else "chi0_static"
        )
    }
    mu_match = re.search(r"mu_([0-9.-]+)", fname) or re.search(r"mu([0-9.-]+)", fname)
    if mu_match:
        try: meta["mu"] = float(mu_match.group(1))
        except ValueError: pass
    jp_match = re.search(r"Jperp_([0-9.]+)", fname) or re.search(r"J_perp_([0-9.]+)", fname)
    if jp_match:
        try: meta["Jperp"] = float(jp_match.group(1))
        except ValueError: pass
    n_match = re.search(r"N_([0-9]+)", fname) or re.search(r"N([0-9]+)", fname)
    if n_match:
        try: meta["N"] = int(n_match.group(1))
        except ValueError: pass
    eta_match = re.search(r"eta_([0-9.]+)", fname)
    if eta_match:
        try: meta["eta"] = float(eta_match.group(1))
        except ValueError: pass
    return meta


class ModernComboBox(QComboBox):
    """QComboBox that prevents long item text from artificially inflating minimumSizeHint."""
    def __init__(self, parent=None, max_hint_width=180):
        super().__init__(parent)
        self._max_hint_width = max_hint_width
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(8)

    def minimumSizeHint(self):
        sz = super().minimumSizeHint()
        return QSize(min(sz.width(), self._max_hint_width), sz.height())

    def sizeHint(self):
        sz = super().sizeHint()
        return QSize(min(sz.width(), self._max_hint_width), sz.height())


class LiveAnalyticalLabWidget(QWidget):
    """
    On-The-Fly Theoretical Physics Lab.
    Uses cached Base Sigma or Bare Chi0 to evaluate physical observables instantaneously.
    """
    sig_status_msg = Signal(str)

    def __init__(self, out_dir: str = DEFAULT_RESULTS_DIR, parent=None):
        super().__init__(parent)
        self.out_dir = out_dir
        self.cached_files: dict = {}
        self.scanned_caches: list[dict] = []
        self._suppress_mu_filter: bool = False
        self.loaded_base_sigma: dict = {}
        self.loaded_chi0_static: dict = {}
        self.loaded_chi0_dynamic: dict = {}

        # Current physics state
        self.active_mode = "k_probe"  # "k_probe", "energy_slice", "band_dispersion", "static_susc", "dynamic_susc"
        self.current_kx = np.pi  # Antinodal by default
        self.current_ky = 0.0
        self.current_JK = 6.0
        self.current_Jperp = 6.0
        self.current_K = 1.0
        self.current_omega_slice = 0.0

        # Modular Analytical Mode Handlers
        self.modes: dict[str, BaseAnalyticalMode] = {
            "k_probe": SpectralFunctionMode(self),
            "energy_slice": EnergySliceMode(self),
            "band_dispersion": BandDispersionMode(self),
            "rpa_susc": StaticSusceptibilityMode(self),
            "static_susc": StaticSusceptibilityMode(self),
            "dynamic_susc": DynamicSusceptibilityMode(self),
        }
        self.mode_order = ["k_probe", "energy_slice", "band_dispersion", "static_susc", "dynamic_susc"]

        self._build_ui()
        self.scan_caches()

        # Background auto-resync timer (detects new cache foundations on disk without manual clicking)
        self.resync_timer = QTimer(self)
        self.resync_timer.setInterval(4000)
        self.resync_timer.timeout.connect(self._auto_resync_if_needed)
        self.resync_timer.start()

        # Ultra-smooth 50 FPS debouncers for continuous mouse dragging (prevents event loop congestion)
        self._jk_render_timer = QTimer(self)
        self._jk_render_timer.setSingleShot(True)
        self._jk_render_timer.setInterval(20)
        self._jk_render_timer.timeout.connect(self._recompute_and_render)

        self._slice_render_timer = QTimer(self)
        self._slice_render_timer.setSingleShot(True)
        self._slice_render_timer.setInterval(20)
        self._slice_render_timer.timeout.connect(self._recompute_and_render)

        self._jperp_render_timer = QTimer(self)
        self._jperp_render_timer.setSingleShot(True)
        self._jperp_render_timer.setInterval(20)
        self._jperp_render_timer.timeout.connect(self._recompute_and_render)

    @property
    def current_mode(self) -> BaseAnalyticalMode:
        return self.modes.get(self.active_mode, self.modes["k_probe"])

    @property
    def _user_xlim_kprobe(self):
        return self.modes["k_probe"]._user_xlim

    @_user_xlim_kprobe.setter
    def _user_xlim_kprobe(self, val):
        self.modes["k_probe"]._user_xlim = val

    @property
    def _user_ylim_a(self):
        return self.modes["k_probe"]._user_ylim_a

    @_user_ylim_a.setter
    def _user_ylim_a(self, val):
        self.modes["k_probe"]._user_ylim_a = val

    @property
    def _user_ylim_s(self):
        return self.modes["k_probe"]._user_ylim_s

    @_user_ylim_s.setter
    def _user_ylim_s(self, val):
        self.modes["k_probe"]._user_ylim_s = val

    @property
    def _is_panning(self):
        return getattr(self.modes.get("k_probe"), "_is_panning", False)

    @_is_panning.setter
    def _is_panning(self, val):
        if "k_probe" in self.modes:
            self.modes["k_probe"]._is_panning = val

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # =====================================================================
        # 1. UNIFIED TWO-ROW COMPACT CONTROL HEADER
        # =====================================================================
        self.header_frame = QFrame()
        self.header_frame.setObjectName("analytical_header_frame")
        self.header_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.header_frame.setStyleSheet("""
            QFrame#analytical_header_frame {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        h_lay = QVBoxLayout(self.header_frame)
        h_lay.setContentsMargins(6, 4, 6, 4)
        h_lay.setSpacing(4)

        # Row 1: Mode + Foundation Cache + Quick Canvas Actions
        r1_lay = QHBoxLayout()
        r1_lay.setContentsMargins(0, 0, 0, 0)
        r1_lay.setSpacing(4)
        r1_lay.setAlignment(Qt.AlignVCenter)

        lbl_mode = QLabel("Mode:")
        lbl_mode.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
        r1_lay.addWidget(lbl_mode)

        combo_style = """
            QComboBox {
                padding: 2px 18px 2px 6px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background: #ffffff;
                color: #0f172a;
                font-size: 11px;
                min-height: 20px;
            }
            QComboBox:hover { border-color: #3b82f6; }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 14px;
                border-left: none;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #0f172a;
                selection-background-color: #eff6ff;
                selection-color: #1d4ed8;
                border: 1px solid #cbd5e1;
            }
        """

        self.cb_experiment = ModernComboBox(max_hint_width=135)
        self.cb_experiment.setStyleSheet(combo_style + "QComboBox { font-weight: 600; min-width: 85px; max-width: 110px; }")
        self.cb_experiment.setMaximumWidth(135)
        self.cb_experiment.addItems([
            self.modes[m_id].display_name for m_id in self.mode_order
        ])
        self.cb_experiment.currentIndexChanged.connect(self._on_experiment_changed)
        r1_lay.addWidget(self.cb_experiment)

        # Chemical potential mu filter with pre-filled cached values and free-typing
        lbl_mu = QLabel("μ:")
        lbl_mu.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
        r1_lay.addWidget(lbl_mu)

        self.cb_filter_mu = QComboBox()
        self.cb_filter_mu.setEditable(True)
        self.cb_filter_mu.setInsertPolicy(QComboBox.NoInsert)
        self.cb_filter_mu.setStyleSheet(combo_style + "QComboBox { min-width: 22px; max-width: 26px; font-weight: 600; padding: 2px 8px 2px 4px; }")
        self.cb_filter_mu.setFixedWidth(40)
        self.cb_filter_mu.addItem("")  # Blank default implies all mu
        if self.cb_filter_mu.lineEdit():
            self.cb_filter_mu.lineEdit().clear()
        self.cb_filter_mu.setCurrentIndex(0)
        self.cb_filter_mu.currentTextChanged.connect(self._on_mu_filter_changed)
        r1_lay.addWidget(self.cb_filter_mu)

        self.btn_clear_mu = QPushButton("✕")
        self.btn_clear_mu.setToolTip("Clear μ filter (show all caches)")
        self.btn_clear_mu.setFixedSize(16, 20)
        self.btn_clear_mu.setStyleSheet("""
            QPushButton {
                padding: 1px 2px;
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                color: #64748b;
                min-width: 15px;
                max-width: 15px;
                min-height: 18px;
                max-height: 18px;
            }
            QPushButton:hover { background: #fee2e2; border-color: #ef4444; color: #dc2626; }
        """)
        self.btn_clear_mu.clicked.connect(self._clear_mu_filter)
        r1_lay.addWidget(self.btn_clear_mu)

        lbl_cache = QLabel("Cache:")
        lbl_cache.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
        r1_lay.addWidget(lbl_cache)

        self.cb_cache_file = ModernComboBox(max_hint_width=165)
        self.cb_cache_file.setStyleSheet(combo_style + "QComboBox { min-width: 95px; max-width: 140px; }")
        self.cb_cache_file.setMaximumWidth(165)
        self.cb_cache_file.currentIndexChanged.connect(self._on_cache_selected)
        r1_lay.addWidget(self.cb_cache_file)

        # Hidden rescan proxy button for full backwards compatibility
        self.btn_rescan = QPushButton("🔄", parent=self)
        self.btn_rescan.setVisible(False)
        self.btn_rescan.clicked.connect(self.scan_caches)

        # Frequency range options for Spectral Function mode (±8 eV or ±15 eV, non-adaptive)
        # Kept immediately adjacent to Cache box as requested
        self.container_wmax = QWidget()
        wmax_lay = QHBoxLayout(self.container_wmax)
        wmax_lay.setContentsMargins(0, 0, 0, 0)
        wmax_lay.setSpacing(2)
        wmax_lay.setAlignment(Qt.AlignVCenter)
        lbl_w = QLabel("ω:")
        lbl_w.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
        wmax_lay.addWidget(lbl_w)
        self.cb_wmax = ModernComboBox(max_hint_width=52)
        self.cb_wmax.setStyleSheet(combo_style + "QComboBox { min-width: 28px; max-width: 34px; font-weight: 600; padding: 2px 8px 2px 4px; }")
        self.cb_wmax.setFixedWidth(52)
        self.cb_wmax.addItems(["±8 eV", "±15 eV"])
        self.cb_wmax.currentIndexChanged.connect(self._on_wmax_changed)
        wmax_lay.addWidget(self.cb_wmax)
        r1_lay.addWidget(self.container_wmax)

        # Stretch creates a clean visual gap between inputs and action buttons
        r1_lay.addStretch(1)

        # Canvas quick actions directly on header
        btn_action_style = """
            QPushButton {
                padding: 2px 6px;
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                color: #334155;
            }
            QPushButton:hover { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }
        """
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setToolTip("Reset view, zoom, slice, and pinned coordinates to default")
        self.btn_reset.setStyleSheet(btn_action_style)
        self.btn_reset.setFixedWidth(46)
        self.btn_reset.clicked.connect(self._reset_view)
        self.btn_fit = self.btn_reset  # Backwards compatibility alias
        r1_lay.addWidget(self.btn_reset)

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setToolTip("Copy high-resolution figure to clipboard (300 DPI)")
        self.btn_copy.setStyleSheet(btn_action_style)
        self.btn_copy.setFixedWidth(44)
        self.btn_copy.clicked.connect(self._copy_figure_to_clipboard)
        r1_lay.addWidget(self.btn_copy)

        self.btn_save = QPushButton("Save")
        self.btn_save.setToolTip("Save publication figure (PNG, PDF, SVG)")
        self.btn_save.setStyleSheet(btn_action_style)
        self.btn_save.setFixedWidth(44)
        self.btn_save.clicked.connect(self._save_figure_dialog)
        r1_lay.addWidget(self.btn_save)

        h_lay.addLayout(r1_lay)

        # Row 2: J_K Continuous Slider + Contextual Physics Controls + Live HUD Chips
        r2_lay = QHBoxLayout()
        r2_lay.setContentsMargins(0, 0, 0, 0)
        r2_lay.setSpacing(6)
        r2_lay.setAlignment(Qt.AlignVCenter)

        lbl_jk = QLabel("J_K:")
        lbl_jk.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
        r2_lay.addWidget(lbl_jk)

        self.slider_jk = QSlider(Qt.Horizontal)
        self.slider_jk.setRange(5, 120)  # 0.5 to 12.0
        self.slider_jk.setValue(60)       # 6.0 default
        self.slider_jk.setFixedWidth(120)
        self.slider_jk.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #cbd5e1;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #2563eb;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #2563eb;
                border: 2px solid #ffffff;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #1d4ed8;
            }
        """)
        self.slider_jk.valueChanged.connect(self._on_jk_slider_changed)
        self.slider_jk.sliderReleased.connect(self._flush_render)
        r2_lay.addWidget(self.slider_jk)

        self.lbl_jk_val = QLabel("J_K = 6.00")
        self.lbl_jk_val.setFixedHeight(24)
        self.lbl_jk_val.setStyleSheet("""
            QLabel {
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 4px;
                padding: 2px 6px;
                font-weight: 700;
                color: #1d4ed8;
                font-size: 11px;
                min-width: 65px;
            }
        """)
        r2_lay.addWidget(self.lbl_jk_val)

        r2_lay.addSpacing(8)

        # Contextual Sub-container: Momentum Dropdown & Custom k-point Spinboxes
        self.container_mom = QWidget()
        mom_lay = QHBoxLayout(self.container_mom)
        mom_lay.setContentsMargins(0, 0, 0, 0)
        mom_lay.setSpacing(5)
        mom_lay.setAlignment(Qt.AlignVCenter)

        self.lbl_mom_title = QLabel("k:")
        self.lbl_mom_title.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
        mom_lay.addWidget(self.lbl_mom_title)

        self.cb_momentum = ModernComboBox(max_hint_width=130)
        self.cb_momentum.setStyleSheet(combo_style + "QComboBox { min-width: 110px; max-width: 155px; font-weight: 600; }")
        self.cb_momentum.addItems([
            "Antinodal (π, 0)",
            "Nodal (π/2, π/2)",
            "Center Γ (0, 0)",
            "Corner M (π, π)",
            "Custom (kx, ky)..."
        ])
        self.cb_momentum.currentIndexChanged.connect(self._on_momentum_combo_changed)
        mom_lay.addWidget(self.cb_momentum)

        # Custom k-point spinboxes (visible only when Custom is chosen)
        self.container_custom_k = QWidget()
        ck_lay = QHBoxLayout(self.container_custom_k)
        ck_lay.setContentsMargins(0, 0, 0, 0)
        ck_lay.setSpacing(3)
        ck_lay.setAlignment(Qt.AlignVCenter)

        lbl_kx = QLabel("kx:")
        lbl_kx.setStyleSheet("font-size: 10px; font-weight: 600; color: #475569;")
        ck_lay.addWidget(lbl_kx)

        self.spin_kx = QDoubleSpinBox()
        self.spin_kx.setRange(-1.0, 1.0)
        self.spin_kx.setSingleStep(0.05)
        self.spin_kx.setValue(1.0)
        self.spin_kx.setSuffix(" π")
        self.spin_kx.setDecimals(2)
        self.spin_kx.setFixedWidth(62)
        self.spin_kx.setStyleSheet("""
            QDoubleSpinBox {
                padding: 2px 3px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background: #ffffff;
                color: #0f172a;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        self.spin_kx.valueChanged.connect(self._on_custom_k_spin_changed)
        ck_lay.addWidget(self.spin_kx)

        lbl_ky = QLabel("ky:")
        lbl_ky.setStyleSheet("font-size: 10px; font-weight: 600; color: #475569;")
        ck_lay.addWidget(lbl_ky)

        self.spin_ky = QDoubleSpinBox()
        self.spin_ky.setRange(-1.0, 1.0)
        self.spin_ky.setSingleStep(0.05)
        self.spin_ky.setValue(0.0)
        self.spin_ky.setSuffix(" π")
        self.spin_ky.setDecimals(2)
        self.spin_ky.setFixedWidth(62)
        self.spin_ky.setStyleSheet(self.spin_kx.styleSheet())
        self.spin_ky.valueChanged.connect(self._on_custom_k_spin_changed)
        ck_lay.addWidget(self.spin_ky)

        self.container_custom_k.setVisible(False)
        mom_lay.addWidget(self.container_custom_k)

        # Retained hidden button proxies with parent=self (never top-level windows!)
        self.btn_k_antinodal = QPushButton("Antinodal (π, 0)", parent=self)
        self.btn_k_antinodal.clicked.connect(lambda: self._set_momentum(np.pi, 0.0))
        self.btn_k_antinodal.setVisible(False)

        self.btn_k_nodal = QPushButton("Nodal (π/2, π/2)", parent=self)
        self.btn_k_nodal.clicked.connect(lambda: self._set_momentum(0.5 * np.pi, 0.5 * np.pi))
        self.btn_k_nodal.setVisible(False)

        self.btn_k_center = QPushButton("Center Γ(0, 0)", parent=self)
        self.btn_k_center.clicked.connect(lambda: self._set_momentum(0.0, 0.0))
        self.btn_k_center.setVisible(False)

        self.btn_k_corner = QPushButton("Corner M(π, π)", parent=self)
        self.btn_k_corner.clicked.connect(lambda: self._set_momentum(np.pi, np.pi))
        self.btn_k_corner.setVisible(False)

        r2_lay.addWidget(self.container_mom)

        # Contextual Sub-container: Energy Slice Slider
        self.container_slice = QWidget()
        slice_lay = QHBoxLayout(self.container_slice)
        slice_lay.setContentsMargins(0, 0, 0, 0)
        slice_lay.setSpacing(6)
        slice_lay.setAlignment(Qt.AlignVCenter)

        self.lbl_slice_title = QLabel("Energy Slice ω:")
        self.lbl_slice_title.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
        slice_lay.addWidget(self.lbl_slice_title)

        self.slider_slice = QSlider(Qt.Horizontal)
        self.slider_slice.setRange(-200, 200)  # -2.0 to 2.0 eV
        self.slider_slice.setValue(0)
        self.slider_slice.setFixedWidth(120)
        self.slider_slice.setStyleSheet(self.slider_jk.styleSheet())
        self.slider_slice.valueChanged.connect(self._on_slice_slider_changed)
        self.slider_slice.sliderReleased.connect(self._flush_render)
        slice_lay.addWidget(self.slider_slice)

        self.lbl_slice_val = QLabel("ω = 0.00 eV")
        self.lbl_slice_val.setFixedHeight(24)
        self.lbl_slice_val.setStyleSheet("""
            QLabel {
                background: #fdf2f8;
                border: 1px solid #fbcfe8;
                border-radius: 4px;
                padding: 2px 6px;
                font-weight: 700;
                color: #be185d;
                font-size: 11px;
                min-width: 75px;
            }
        """)
        slice_lay.addWidget(self.lbl_slice_val)
        self.container_slice.setVisible(False)
        r2_lay.addWidget(self.container_slice)

        # Contextual Sub-container: Susceptibility Parameters (J_perp slider + K AFM/FM dropdown)
        self.container_susc_params = QWidget()
        susc_lay = QHBoxLayout(self.container_susc_params)
        susc_lay.setContentsMargins(0, 0, 0, 0)
        susc_lay.setSpacing(6)
        susc_lay.setAlignment(Qt.AlignVCenter)

        lbl_jperp = QLabel("J_⊥:")
        lbl_jperp.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
        susc_lay.addWidget(lbl_jperp)

        self.slider_jperp = QSlider(Qt.Horizontal)
        self.slider_jperp.setRange(5, 120)  # 0.5 to 12.0
        self.slider_jperp.setValue(60)       # 6.0 default
        self.slider_jperp.setFixedWidth(110)
        self.slider_jperp.setStyleSheet(self.slider_jk.styleSheet())
        self.slider_jperp.valueChanged.connect(self._on_jperp_slider_changed)
        self.slider_jperp.sliderReleased.connect(self._flush_render)
        susc_lay.addWidget(self.slider_jperp)

        self.lbl_jperp_val = QLabel("J_⊥ = 6.00")
        self.lbl_jperp_val.setFixedHeight(24)
        self.lbl_jperp_val.setStyleSheet("""
            QLabel {
                background: #ecfeff;
                border: 1px solid #a5f3fc;
                border-radius: 4px;
                padding: 2px 6px;
                font-weight: 700;
                color: #0e7490;
                font-size: 11px;
                min-width: 65px;
            }
        """)
        susc_lay.addWidget(self.lbl_jperp_val)

        susc_lay.addSpacing(4)

        lbl_k = QLabel("K:")
        lbl_k.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
        susc_lay.addWidget(lbl_k)

        self.cb_k = ModernComboBox(max_hint_width=110)
        self.cb_k.setStyleSheet(combo_style + "QComboBox { min-width: 95px; max-width: 120px; font-weight: 600; }")
        self.cb_k.addItem("+1 (AFM)", 1.0)
        self.cb_k.addItem("-1 (FM)", -1.0)
        self.cb_k.currentIndexChanged.connect(self._on_k_changed)
        susc_lay.addWidget(self.cb_k)

        self.container_susc_params.setVisible(False)
        r2_lay.addWidget(self.container_susc_params)

        # Contextual Tip for 2D Maps
        self.lbl_map_tip = QLabel("💡 Tip: Click map to probe k • Double-click for A(k, ω)")
        self.lbl_map_tip.setStyleSheet("color: #64748b; font-size: 10px; font-style: italic;")
        self.lbl_map_tip.setWordWrap(True)
        self.lbl_map_tip.setMinimumWidth(0)
        self.lbl_map_tip.setVisible(False)
        r2_lay.addWidget(self.lbl_map_tip)

        r2_lay.addStretch(1)

        # Live Physics HUD Chips (Clean, no noisy emoji icons, with rich explanatory tooltips)
        chip_style_z = "QLabel { background: #ecfeff; border: 1px solid #a5f3fc; border-radius: 4px; padding: 2px 7px; font-weight: 700; color: #0e7490; font-size: 11px; } QLabel:hover { background: #cffafe; border-color: #0891b2; }"
        chip_style_g = "QLabel { background: #fffbeb; border: 1px solid #fde68a; border-radius: 4px; padding: 2px 7px; font-weight: 700; color: #b45309; font-size: 11px; } QLabel:hover { background: #fef3c7; border-color: #d97706; }"
        chip_style_m = "QLabel { background: #f5f3ff; border: 1px solid #ddd6fe; border-radius: 4px; padding: 2px 7px; font-weight: 700; color: #6d28d9; font-size: 11px; } QLabel:hover { background: #ede9fe; border-color: #7c3aed; }"

        self.lbl_live_z = QLabel("Z(k): —")
        self.lbl_live_z.setStyleSheet(chip_style_z)
        self.lbl_live_z.setFixedHeight(24)
        self.lbl_live_z.setToolTip(
            "<b>Quasiparticle Residue Z(k) ∈ (0, 1]</b><br>"
            "<i>Formula: Z(k) = [1 - ∂ReΣ/∂ω |<sub>ω→0</sub>]<sup>-1</sup></i><br><br>"
            "• <b>What it is:</b> Coherent single-particle pole weight at the Fermi level.<br>"
            "• <b>Physical Meaning:</b> Fraction of the electron state behaving as a coherent quasiparticle.<br>"
            "• <b>Interpretation:</b><br>"
            "  - <i>Z ≈ 1:</i> Bare / weakly interacting Fermi liquid.<br>"
            "  - <i>Z ≪ 1:</i> Heavy fermion state formed by strong Kondo exchange coupling J<sub>K</sub>.<br>"
            "  - <i>Z → 0:</i> Complete quasiparticle breakdown / localized Mott insulating state."
        )
        r2_lay.addWidget(self.lbl_live_z)

        self.lbl_live_gamma = QLabel("Γ(k): —")
        self.lbl_live_gamma.setStyleSheet(chip_style_g)
        self.lbl_live_gamma.setFixedHeight(24)
        self.lbl_live_gamma.setToolTip(
            "<b>Quasiparticle Damping / Scattering Rate Γ(k)</b><br>"
            "<i>Formula: Γ(k) = |ImΣ(k, ω=0)| [eV]</i><br><br>"
            "• <b>What it is:</b> Inelastic electronic scattering rate off the localized spin background.<br>"
            "• <b>Quasiparticle Lifetime:</b> τ<sub>k</sub> ~ ħ / [2 Γ(k)].<br>"
            "• <b>Physical Meaning:</b> Directly broadens the spectral function peak A(k, ω).<br>"
            "• In a strict Fermi liquid at T=0, Γ(0) → 0. Here, Kondo fluctuations introduce finite damping."
        )
        r2_lay.addWidget(self.lbl_live_gamma)

        self.lbl_live_mass = QLabel("m*/m: —")
        self.lbl_live_mass.setStyleSheet(chip_style_m)
        self.lbl_live_mass.setFixedHeight(24)
        self.lbl_live_mass.setToolTip(
            "<b>Effective Mass Enhancement m*/m</b><br>"
            "<i>Formula: m*/m ≈ 1 / Z(k) = 1 - ∂ReΣ/∂ω |<sub>ω→0</sub></i><br><br>"
            "• <b>What it is:</b> Ratio of the renormalized quasiparticle mass m* to the bare band mass m.<br>"
            "• <b>Physical Meaning:</b> Quantifies electronic inertia due to the many-body Kondo dressing cloud.<br>"
            "• <b>Observable Consequences:</b><br>"
            "  - Flattens the quasiparticle dispersion near E<sub>F</sub> (v<sub>F</sub>* = v<sub>F</sub> / [m*/m]).<br>"
            "  - Proportional to the Sommerfeld electronic specific heat coefficient γ<sub>C</sub> ∝ m*/m."
        )
        r2_lay.addWidget(self.lbl_live_mass)

        h_lay.addLayout(r2_lay)
        lay.addWidget(self.header_frame)

        # Alias for backward compatibility with test suites
        self.ctrl_frame = self.header_frame

        # =====================================================================
        # 2. INTERACTIVE MATPLOTLIB CANVAS
        # =====================================================================
        self.fig = Figure(figsize=(7, 5), dpi=100)
        self.fig.patch.set_facecolor("#ffffff")
        self.canvas = FigureCanvasQTAgg(self.fig)

        # Hidden toolbar instance retained for full backwards compatibility
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setVisible(False)

        lay.addWidget(self.canvas, 1)

        # Connect interactive mouse navigation events on canvas (Zoom on scroll, Pan on drag)
        self.canvas.mpl_connect("scroll_event", self._on_canvas_scroll)
        self.canvas.mpl_connect("button_press_event", self._on_canvas_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_canvas_motion)
        self.canvas.mpl_connect("button_release_event", self._on_canvas_release)

        self._render_placeholder()

    def set_output_dir(self, out_dir: str):
        self.out_dir = out_dir
        self.scan_caches()

    def _auto_resync_if_needed(self):
        """Silently checks if new cache files appeared in results/cache/ or results/data/ and resyncs if so."""
        try:
            results_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(self.out_dir)
            current_files = set()
            for d in (cache_dir, data_dir):
                if os.path.isdir(d):
                    for f in os.listdir(d):
                        if f.endswith(".npz") and (f.startswith("sigma_base") or f.startswith("chi0_")):
                            current_files.add(f)
            if hasattr(self, "_last_scanned_files") and current_files != self._last_scanned_files:
                curr_data = self.cb_cache_file.currentData()
                self.scan_caches()
                if curr_data:
                    for i in range(self.cb_cache_file.count()):
                        if self.cb_cache_file.itemData(i) == curr_data:
                            self.cb_cache_file.setCurrentIndex(i)
                            break
        except Exception:
            pass

    def _on_mu_filter_changed(self, text: str):
        if getattr(self, "_suppress_mu_filter", False):
            return
        self._populate_cache_dropdown()

    def _clear_mu_filter(self):
        if hasattr(self, "cb_filter_mu"):
            self.cb_filter_mu.blockSignals(True)
            self.cb_filter_mu.setCurrentIndex(0)
            if self.cb_filter_mu.lineEdit():
                self.cb_filter_mu.lineEdit().clear()
            self.cb_filter_mu.blockSignals(False)
            self._populate_cache_dropdown()

    def _update_mu_filter_options(self):
        """Populates cb_filter_mu with distinct mu values discovered for the active mode category."""
        if not hasattr(self, "cb_filter_mu"):
            return
        if self.active_mode in ["rpa_susc", "static_susc"]:
            target_cat = "chi0_static"
        elif self.active_mode == "dynamic_susc":
            target_cat = "chi0_dynamic"
        else:
            target_cat = "sigma"
        mu_vals = set()
        for c in self.scanned_caches:
            if c["category"] == target_cat and c["mu"] is not None:
                mu_vals.add(round(c["mu"], 2))
        sorted_mus = sorted(list(mu_vals))

        curr_text = self.cb_filter_mu.currentText().strip()
        self._suppress_mu_filter = True
        self.cb_filter_mu.blockSignals(True)
        self.cb_filter_mu.clear()
        self.cb_filter_mu.addItem("")  # Blank item by default (implies all mu)
        for m in sorted_mus:
            self.cb_filter_mu.addItem(f"{m:.2f}")

        # Preserve user's typed value if they were searching for something specific
        if curr_text:
            self.cb_filter_mu.setEditText(curr_text)
        else:
            self.cb_filter_mu.setCurrentIndex(0)
            if self.cb_filter_mu.lineEdit():
                self.cb_filter_mu.lineEdit().clear()
        self.cb_filter_mu.blockSignals(False)
        self._suppress_mu_filter = False

    def _populate_cache_dropdown(self):
        """Filters scanned caches by active mode category and mu filter text."""
        if self.active_mode in ["rpa_susc", "static_susc"]:
            target_cat = "chi0_static"
        elif self.active_mode == "dynamic_susc":
            target_cat = "chi0_dynamic"
        else:
            target_cat = "sigma"
        mode_caches = [c for c in self.scanned_caches if c["category"] == target_cat]

        mu_filter_text = self.cb_filter_mu.currentText().strip() if hasattr(self, "cb_filter_mu") else ""
        filtered = mode_caches
        is_filtering = bool(mu_filter_text)

        if is_filtering:
            try:
                target_mu = float(mu_filter_text)
                filtered = [c for c in mode_caches if c["mu"] is not None and abs(c["mu"] - target_mu) < 0.05]
            except ValueError:
                filtered = [c for c in mode_caches if c["mu"] is not None and mu_filter_text in str(c["mu"])]

        prev_data = self.cb_cache_file.currentData()
        self.cb_cache_file.blockSignals(True)
        self.cb_cache_file.clear()

        if filtered:
            self.cb_cache_file.setEnabled(True)
            for c in filtered:
                self.cb_cache_file.addItem(c["label"], c["fpath"])
                self.cb_cache_file.setItemData(
                    self.cb_cache_file.count() - 1,
                    f"{c['label']}\n{c['fpath']}",
                    Qt.ToolTipRole
                )
            sel_idx = 0
            for i in range(self.cb_cache_file.count()):
                if self.cb_cache_file.itemData(i) == prev_data:
                    sel_idx = i
                    break
            self.cb_cache_file.setCurrentIndex(sel_idx)
            self.cb_cache_file.blockSignals(False)
            self._on_cache_selected()
        else:
            self.cb_cache_file.setEnabled(False)
            if is_filtering:
                self.cb_cache_file.addItem(f"[ No cache for μ = {mu_filter_text} ]", None)
                if self.active_mode == "rpa_susc":
                    msg = (
                        f"⚡ No cache found for μ = {mu_filter_text} eV\n\n"
                        f"To generate this cache, run a calculation in the Susceptibility tab with μ = {mu_filter_text} eV.\n"
                        f"Once computed, it will automatically appear here."
                    )
                else:
                    msg = (
                        f"⚡ No cache found for μ = {mu_filter_text} eV\n\n"
                        f"To generate this cache, run a calculation in the Spectral Sweep tab with μ = {mu_filter_text} eV.\n"
                        f"Once computed, it will automatically appear here for real-time J_K exploration."
                    )
            else:
                self.cb_cache_file.addItem("[ No caches available ]", None)
                msg = None
            self.cb_cache_file.blockSignals(False)
            self._render_placeholder(msg)

    def scan_caches(self):
        """Scans results/cache/, results/data/, and legacy folders for base Sigma and bare Chi0 arrays."""
        results_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(self.out_dir)
        self.cached_files.clear()
        self.scanned_caches.clear()

        dirs_to_check = [
            cache_dir,
            data_dir,
            os.path.join(self.out_dir, "many_body_results", "susceptibility_results", "data"),
            os.path.join(self.out_dir, "many_body_results", "spectral_results", "data"),
            os.path.join(self.out_dir, "self_energy", "results", "cache"),
            os.path.join(self.out_dir, "self_energy", "results", "data"),
        ]

        seen_files = set()
        for d in dirs_to_check:
            if not os.path.isdir(d): continue
            for f in sorted(os.listdir(d)):
                if not f.endswith(".npz") or f in seen_files: continue
                full_p = os.path.join(d, f)
                ftype = None
                if f.startswith("sigma_base"): ftype = "sigma_base"
                elif f.startswith("chi0_static"): ftype = "chi0_static"
                elif f.startswith("chi0_dynamic"): ftype = "chi0_dynamic"
                if ftype:
                    seen_files.add(f)
                    self.cached_files[f] = (ftype, full_p)
                    lbl = format_smart_cache_label(f, ftype)
                    meta = parse_cache_metadata(f, ftype)
                    self.scanned_caches.append({
                        "fname": f,
                        "fpath": full_p,
                        "ftype": ftype,
                        "category": meta["category"],
                        "mu": meta["mu"],
                        "Jperp": meta["Jperp"],
                        "N": meta["N"],
                        "eta": meta["eta"],
                        "label": lbl,
                    })

        # Fallback to external global dirs only if nothing found in out_dir
        if len(self.scanned_caches) == 0:
            ext_dirs = [
                r"C:\Users\sruji\Projects\masters_thesis\many_body_results\susceptibility_results\data",
                r"C:\Users\sruji\Projects\masters_thesis\many_body_results\spectral_results\data",
                r"C:\Users\sruji\Projects\masters_thesis\self_energy\results\cache",
                r"C:\Users\sruji\Projects\masters_thesis\self_energy\results\data",
            ]
            for ed in ext_dirs:
                if not os.path.isdir(ed): continue
                for f in sorted(os.listdir(ed)):
                    if not f.endswith(".npz") or f in seen_files: continue
                    full_p = os.path.join(ed, f)
                    ftype = None
                    if f.startswith("sigma_base"): ftype = "sigma_base"
                    elif f.startswith("chi0_static"): ftype = "chi0_static"
                    elif f.startswith("chi0_dynamic"): ftype = "chi0_dynamic"
                    if ftype:
                        seen_files.add(f)
                        self.cached_files[f] = (ftype, full_p)
                        lbl = format_smart_cache_label(f, ftype)
                        meta = parse_cache_metadata(f, ftype)
                        self.scanned_caches.append({
                            "fname": f,
                            "fpath": full_p,
                            "ftype": ftype,
                            "category": meta["category"],
                            "mu": meta["mu"],
                            "Jperp": meta["Jperp"],
                            "N": meta["N"],
                            "eta": meta["eta"],
                            "label": lbl,
                        })

        self._last_scanned_files = seen_files.copy()
        self._update_mu_filter_options()
        self._populate_cache_dropdown()

    def _render_placeholder(self, msg: str = None):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        if msg is None:
            msg = (
                "⚡ No cache arrays found in results/cache/\n\n"
                "Run a calculation in the Spectral Sweep or Susceptibility tab to generate cache arrays.\n"
                "Once cached, this lab enables real-time 60 FPS continuous J_K scaling, BZ k-probing,\n"
                "and 2D quasiparticle weight Z(k) maps instantaneously!"
            )
        ax.text(
            0.5, 0.5,
            msg,
            horizontalalignment="center", verticalalignment="center",
            transform=ax.transAxes, color="#64748b", fontsize=10.5, linespacing=1.4
        )
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_frame_on(False)
        self.canvas.draw()

    def _on_cache_selected(self):
        fpath = self.cb_cache_file.currentData()
        if not fpath or not os.path.exists(fpath):
            return

        fname = os.path.basename(fpath)
        ftype, _ = self.cached_files.get(fname, ("unknown", fpath))

        if ftype == "sigma_base":
            self._load_base_sigma(fpath)
        elif ftype == "chi0_static":
            self._load_chi0_static(fpath)
        elif ftype == "chi0_dynamic":
            self._load_chi0_dynamic(fpath)
        self._recompute_and_render()

    def _load_base_sigma(self, fpath: str):
        """
        Robustly loads base self-energy foundations across all archive generations:
        1. 8-bit bit-groomed byte-shuffled 1/8th IBZ ('sig_re_shuf', 'sig_im_shuf', 'shape')
        2. Unshuffled 1/8th IBZ ('sig_re', 'sig_im', is_ibz=True)
        3. Full BZ flat ('sig_re', 'sig_im')
        4. Legacy 2-loop separate ('sig1_re' + 'sig3_re', 'sig1_im' + 'sig3_im')
        """
        try:
            import re
            with np.load(fpath) as d:
                is_ibz = bool(d.get("is_ibz", False))
                is_shuffled = bool(d.get("is_shuffled", False))
                N = int(d.get("N", 64))
                omega = d["omega"].astype(np.float64)
                t = float(d.get("t", 1.0))
                t1 = float(d.get("t1", 0.0))
                mu = float(d.get("mu", 1.0))
                eta = float(d.get("eta", 0.08))

                jp_match = re.search(r"Jperp_([0-9.]+)", os.path.basename(fpath)) or re.search(r"J_perp_([0-9.]+)", os.path.basename(fpath))
                if jp_match:
                    Jperp = float(jp_match.group(1))
                else:
                    Jperp = float(d.get("fixed_jperp", d.get("Jperp", d.get("J_perp", 6.0))))

                if is_shuffled and "sig_re_shuf" in d and "sig_im_shuf" in d:
                    orig_shape = tuple(d["shape"])
                    r_ibz = byte_unshuffle_f32(d["sig_re_shuf"], orig_shape)
                    i_ibz = byte_unshuffle_f32(d["sig_im_shuf"], orig_shape)
                    _, _, full_to_ibz = get_ibz_indices_and_map(N)
                    sig_re = LazyIBZArray(r_ibz, full_to_ibz, N)
                    sig_im = LazyIBZArray(i_ibz, full_to_ibz, N)
                elif is_ibz and "sig_re" in d and "sig_im" in d:
                    _, _, full_to_ibz = get_ibz_indices_and_map(N)
                    sig_re = LazyIBZArray(d["sig_re"].astype(np.float32), full_to_ibz, N)
                    sig_im = LazyIBZArray(d["sig_im"].astype(np.float32), full_to_ibz, N)
                elif "sig_re" in d and "sig_im" in d:
                    sig_re = d["sig_re"].astype(np.float32)
                    sig_im = d["sig_im"].astype(np.float32)
                elif "sig1_re" in d and "sig3_re" in d:
                    sig_re = (d["sig1_re"] + d["sig3_re"]).astype(np.float32)
                    sig_im = (d["sig1_im"] + d["sig3_im"]).astype(np.float32)
                else:
                    raise KeyError(f"Archive missing recognized self-energy keys: {list(d.keys())}")

                self.loaded_base_sigma = {
                    "fpath": fpath,
                    "N": N, "omega": omega, "t": t, "t1": t1, "mu": mu, "eta": eta,
                    "Jperp": Jperp,
                    "sig_re": sig_re, "sig_im": sig_im
                }
        except Exception as e:
            print(f"[CACHE LOAD ERROR] Failed loading {fpath}: {e}")
            if self.isVisible():
                QMessageBox.warning(self, "Cache Load Error", f"Could not load Base Sigma array:\n{e}")

    def _load_chi0_static(self, fpath: str):
        try:
            import re
            jp_match = re.search(r"Jperp_([0-9.]+)", os.path.basename(fpath)) or re.search(r"J_perp_([0-9.]+)", os.path.basename(fpath))
            with np.load(fpath) as d:
                if jp_match:
                    Jperp = float(jp_match.group(1))
                else:
                    Jperp = float(d.get("fixed_jperp", d.get("Jperp", d.get("J_perp", 6.0))))
                self.loaded_chi0_static = {
                    "fpath": fpath,
                    "chi0_grid": d["chi0_grid"],
                    "q_axis": d["q_axis"],
                    "N": int(d.get("N", 64)),
                    "mu": float(d.get("mu", 1.0)),
                    "t": float(d.get("t", 1.0)),
                    "Jperp": Jperp
                }
                if hasattr(self, "slider_jperp"):
                    self.slider_jperp.blockSignals(True)
                    self.slider_jperp.setValue(int(round(np.clip(Jperp * 10, 5, 120))))
                    self.slider_jperp.blockSignals(False)
                    self.current_Jperp = Jperp
                    self.lbl_jperp_val.setText(f"J_⊥ = {Jperp:.2f}")
        except Exception as e:
            print(f"[CACHE LOAD ERROR] Failed loading {fpath}: {e}")
            if self.isVisible():
                QMessageBox.warning(self, "Cache Load Error", f"Could not load Static Chi0 array:\n{e}")

    def _load_chi0_dynamic(self, fpath: str):
        try:
            import re
            jp_match = re.search(r"Jperp_([0-9.]+)", os.path.basename(fpath)) or re.search(r"J_perp_([0-9.]+)", os.path.basename(fpath))
            with np.load(fpath) as d:
                if jp_match:
                    Jperp = float(jp_match.group(1))
                else:
                    Jperp = float(d.get("fixed_jperp", d.get("Jperp", d.get("J_perp", 6.0))))
                K_val = float(d.get("K", 1.0))
                self.loaded_chi0_dynamic = {
                    "fpath": fpath,
                    "chi0_master": d["chi0_master"],
                    "Q_path_x": d["Q_path_x"],
                    "Q_path_y": d["Q_path_y"],
                    "omegas": d["omegas"],
                    "N": int(d.get("N", 100)),
                    "mu": float(d.get("mu", 1.0)),
                    "t": float(d.get("t", 1.0)),
                    "t1": float(d.get("t1", 0.0)),
                    "eta": float(d.get("eta", 0.01)),
                    "omega_max": float(d.get("omega_max", 10.0)),
                    "num_omegas": int(d.get("num_omegas", 600)),
                    "Jperp": Jperp,
                    "K": K_val,
                }
                if hasattr(self, "slider_jperp"):
                    self.slider_jperp.blockSignals(True)
                    self.slider_jperp.setValue(int(round(np.clip(Jperp * 10, 5, 120))))
                    self.slider_jperp.blockSignals(False)
                    self.current_Jperp = Jperp
                    self.lbl_jperp_val.setText(f"J_⊥ = {Jperp:.2f}")
                if hasattr(self, "cb_k"):
                    self.cb_k.blockSignals(True)
                    self.cb_k.setCurrentIndex(0 if K_val >= 0 else 1)
                    self.cb_k.blockSignals(False)
                    self.current_K = K_val
        except Exception as e:
            print(f"[CACHE LOAD ERROR] Failed loading {fpath}: {e}")
            if self.isVisible():
                QMessageBox.warning(self, "Cache Load Error", f"Could not load Dynamic Chi0 array:\n{e}")

    def _on_experiment_changed(self):
        idx = self.cb_experiment.currentIndex()
        if 0 <= idx < len(self.mode_order):
            self.active_mode = self.mode_order[idx]

        # Ensure internal button proxies NEVER appear as top-level windows
        self.btn_k_antinodal.setVisible(False)
        self.btn_k_nodal.setVisible(False)
        self.btn_k_center.setVisible(False)
        self.btn_k_corner.setVisible(False)

        # Update available mu values for the active mode and populate cache dropdown
        self._update_mu_filter_options()
        self._populate_cache_dropdown()

        self.current_mode.setup_ui()
        self._recompute_and_render()

    def _on_jk_slider_changed(self, val: int):
        self.current_JK = float(val) / 10.0
        self.lbl_jk_val.setText(f"J_K = {self.current_JK:.2f}")
        if self.slider_jk.isSliderDown():
            self._jk_render_timer.start(20)
        else:
            self._recompute_and_render()

    def _on_slice_slider_changed(self, val: int):
        self.current_omega_slice = float(val) / 100.0
        self.lbl_slice_val.setText(f"ω = {self.current_omega_slice:.2f} eV")
        if "energy_slice" in self.modes:
            self.modes["energy_slice"].show_slice_indicator = True
        if self.slider_slice.isSliderDown():
            self._slice_render_timer.start(20)
        else:
            self._recompute_and_render()

    def _on_jperp_slider_changed(self, val: int):
        self.current_Jperp = float(val) / 10.0
        self.lbl_jperp_val.setText(f"J_⊥ = {self.current_Jperp:.2f}")
        if self.slider_jperp.isSliderDown():
            self._jperp_render_timer.start(20)
        else:
            self._recompute_and_render()

    def _on_k_changed(self, idx: int):
        val = self.cb_k.currentData()
        self.current_K = float(val) if val is not None else 1.0
        self._recompute_and_render()

    def _flush_render(self):
        """Immediately executes pending debounced render on mouse release."""
        if hasattr(self, "_jk_render_timer") and self._jk_render_timer.isActive():
            self._jk_render_timer.stop()
        if hasattr(self, "_slice_render_timer") and self._slice_render_timer.isActive():
            self._slice_render_timer.stop()
        if hasattr(self, "_jperp_render_timer") and self._jperp_render_timer.isActive():
            self._jperp_render_timer.stop()
        self._recompute_and_render()

    def _on_wmax_changed(self, idx: int):
        val = 15.0 if idx == 1 else 8.0
        if "k_probe" in self.modes:
            self.modes["k_probe"].w_max = val
            self.modes["k_probe"]._user_xlim = None
        if "band_dispersion" in self.modes:
            self.modes["band_dispersion"].w_max = val
            self.modes["band_dispersion"]._user_ylim = None
        if self.active_mode in ["k_probe", "band_dispersion"]:
            self._recompute_and_render()
            self.sig_status_msg.emit(f"Spectral frequency window set to [-{val:.0f}, {val:.0f}] eV.")

    def _on_momentum_combo_changed(self, idx: int):
        self._user_xlim_kprobe = None
        self._user_ylim_a = None
        self._user_ylim_s = None
        if idx == 0:  # Antinodal (π, 0)
            self.container_custom_k.setVisible(False)
            self.current_kx = float(np.pi)
            self.current_ky = 0.0
            self._recompute_and_render()
        elif idx == 1:  # Nodal (π/2, π/2)
            self.container_custom_k.setVisible(False)
            self.current_kx = float(0.5 * np.pi)
            self.current_ky = float(0.5 * np.pi)
            self._recompute_and_render()
        elif idx == 2:  # Center Γ (0, 0)
            self.container_custom_k.setVisible(False)
            self.current_kx = 0.0
            self.current_ky = 0.0
            self._recompute_and_render()
        elif idx == 3:  # Corner M (π, π)
            self.container_custom_k.setVisible(False)
            self.current_kx = float(np.pi)
            self.current_ky = float(np.pi)
            self._recompute_and_render()
        elif idx == 4:  # Custom (kx, ky)...
            self.container_custom_k.setVisible(True)
            self.current_kx = float(self.spin_kx.value() * np.pi)
            self.current_ky = float(self.spin_ky.value() * np.pi)
            self._recompute_and_render()

    def _on_custom_k_spin_changed(self):
        if self.cb_momentum.currentIndex() == 4:
            self._user_xlim_kprobe = None
            self._user_ylim_a = None
            self._user_ylim_s = None
            self.current_kx = float(self.spin_kx.value() * np.pi)
            self.current_ky = float(self.spin_ky.value() * np.pi)
            self._recompute_and_render()

    def _set_momentum(self, kx: float, ky: float, sync_spinboxes: bool = True):
        """Sets current momentum k and synchronizes combo & spinbox UI without feedback loops."""
        self.current_kx = float(kx)
        self.current_ky = float(ky)
        self._user_xlim_kprobe = None
        self._user_ylim_a = None
        self._user_ylim_s = None

        # Normalize to [-pi, pi] for display and spinboxes
        kx_norm = (kx + np.pi) % (2.0 * np.pi) - np.pi
        ky_norm = (ky + np.pi) % (2.0 * np.pi) - np.pi

        if hasattr(self, "cb_momentum"):
            self.cb_momentum.blockSignals(True)
            if abs(abs(kx_norm) - np.pi) < 0.05 and abs(ky_norm) < 0.05:
                self.cb_momentum.setCurrentIndex(0)  # Antinodal
                self.container_custom_k.setVisible(False)
            elif abs(kx_norm - 0.5 * np.pi) < 0.05 and abs(ky_norm - 0.5 * np.pi) < 0.05:
                self.cb_momentum.setCurrentIndex(1)  # Nodal
                self.container_custom_k.setVisible(False)
            elif abs(kx_norm) < 0.05 and abs(ky_norm) < 0.05:
                self.cb_momentum.setCurrentIndex(2)  # Center
                self.container_custom_k.setVisible(False)
            elif abs(abs(kx_norm) - np.pi) < 0.05 and abs(abs(ky_norm) - np.pi) < 0.05:
                self.cb_momentum.setCurrentIndex(3)  # Corner
                self.container_custom_k.setVisible(False)
            else:
                self.cb_momentum.setCurrentIndex(4)  # Custom
                self.container_custom_k.setVisible(True)
            self.cb_momentum.blockSignals(False)

        if sync_spinboxes and hasattr(self, "spin_kx") and hasattr(self, "spin_ky"):
            self.spin_kx.blockSignals(True)
            self.spin_ky.blockSignals(True)
            self.spin_kx.setValue(round(max(-1.0, min(1.0, kx_norm / np.pi)), 2))
            self.spin_ky.setValue(round(max(-1.0, min(1.0, ky_norm / np.pi)), 2))
            self.spin_kx.blockSignals(False)
            self.spin_ky.blockSignals(False)

        self._recompute_and_render()

    def _on_canvas_press(self, event):
        """Initiates click/drag panning on spectral plots or k-probing on 2D maps."""
        if self.current_mode:
            self.current_mode.on_press(event)

    def _on_canvas_motion(self, event):
        """Translates/pans axes when clicking and dragging inside plot."""
        if self.current_mode:
            self.current_mode.on_motion(event)

    def _on_canvas_release(self, event):
        """Ends mouse drag pan operation."""
        if self.current_mode:
            self.current_mode.on_release(event)

    def _on_canvas_scroll(self, event):
        """Interactive mouse wheel zoom centered at cursor position."""
        if self.current_mode:
            self.current_mode.on_scroll(event)

    def _on_canvas_clicked(self, event):
        """Legacy helper forwarding to on_press."""
        if self.current_mode:
            self.current_mode.on_press(event)

    def _recompute_and_render(self):
        """Dispatches to the active analytical mode renderer."""
        if self.current_mode:
            self.current_mode.render()

    def _clear_pinned_points(self):
        """Clears pinned points from the active mode if supported."""
        if hasattr(self.current_mode, "clear_pinned_points"):
            self.current_mode.clear_pinned_points()

    # =========================================================================
    # QUICK CANVAS ACTIONS
    # =========================================================================
    def _reset_view(self):
        if self.current_mode:
            if hasattr(self.current_mode, "reset_view"):
                self.current_mode.reset_view()
            else:
                self.current_mode.fit_view()
        if self.active_mode in ["static_susc", "dynamic_susc", "rpa_susc"]:
            if hasattr(self, "slider_jperp"):
                self.slider_jperp.blockSignals(True)
                self.slider_jperp.setValue(60)
                self.slider_jperp.blockSignals(False)
                self.current_Jperp = 6.0
                self.lbl_jperp_val.setText("J_⊥ = 6.00")
            if hasattr(self, "cb_k"):
                self.cb_k.blockSignals(True)
                self.cb_k.setCurrentIndex(0)
                self.cb_k.blockSignals(False)
                self.current_K = 1.0
            self._recompute_and_render()

    def _fit_view(self):
        self._reset_view()

    def _copy_figure_to_clipboard(self):
        try:
            buf = io.BytesIO()
            self.fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
            buf.seek(0)
            img = QImage.fromData(buf.getvalue())
            clipboard = QApplication.clipboard()
            clipboard.setImage(img)
            self.sig_status_msg.emit("Figure copied to clipboard (300 DPI).")
        except Exception as e:
            QMessageBox.warning(self, "Copy Error", f"Could not copy figure to clipboard:\n{e}")

    def _save_figure_dialog(self):
        default_name = f"analytical_{self.active_mode}_JK_{self.current_JK:.1f}.png"
        fpath, _ = QFileDialog.getSaveFileName(
            self, "Save Analytical Figure",
            os.path.join(self.out_dir, default_name),
            "PNG Image (*.png);;PDF Document (*.pdf);;SVG Vector (*.svg)"
        )
        if fpath:
            try:
                self.fig.savefig(fpath, dpi=300, bbox_inches="tight")
                self.sig_status_msg.emit(f"Saved figure -> {os.path.basename(fpath)}")
            except Exception as e:
                QMessageBox.warning(self, "Save Error", f"Could not save figure:\n{e}")

    # =========================================================================
    # BACKWARD COMPATIBLE RENDER METHOD PROXIES
    # =========================================================================
    def _render_k_probe(self):
        self.modes["k_probe"].render()

    def _render_energy_slice(self):
        self.modes["energy_slice"].render()

    def _render_rpa_susc(self):
        self.modes["rpa_susc"].render()
