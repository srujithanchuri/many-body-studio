"""UI construction helpers for the Interactive Plots viewport.

The builder receives the owning InteractivePlotsWidget so its existing
attributes, callbacks, object names and compatibility aliases are preserved.
Physics/state logic remains in interactive_plots.py.
"""

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QFrame, QDoubleSpinBox, QSizePolicy,
)


class ModernComboBox(QComboBox):
    """QComboBox that prevents long item text from artificially inflating minimumSizeHint."""
    def __init__(self, parent=None, max_hint_width=180):
        super().__init__(parent)
        self._max_hint_width = max_hint_width
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(8)
        if self.view():
            self.view().setStyleSheet("""
                QToolTip {
                    background-color: #0f172a;
                    color: #ffffff;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
            """)

    def minimumSizeHint(self):
        sz = super().minimumSizeHint()
        return QSize(min(sz.width(), self._max_hint_width), sz.height())

    def sizeHint(self):
        sz = super().sizeHint()
        return QSize(min(sz.width(), self._max_hint_width), sz.height())



def build_interactive_plot_ui(owner):
            lay = QVBoxLayout(owner)
            lay.setContentsMargins(6, 6, 6, 6)
            lay.setSpacing(6)

            # =====================================================================
            # 1. UNIFIED TWO-ROW COMPACT CONTROL HEADER
            # =====================================================================
            owner.header_frame = QFrame()
            owner.header_frame.setObjectName("analytical_header_frame")
            owner.header_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            owner.header_frame.setStyleSheet("""
                QFrame#analytical_header_frame {
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                }
            """)
            h_lay = QVBoxLayout(owner.header_frame)
            h_lay.setContentsMargins(6, 4, 6, 4)
            h_lay.setSpacing(4)

            # Row 1: Mode + Foundation Cache + Quick Canvas Actions
            r1_lay = QHBoxLayout()
            r1_lay.setContentsMargins(0, 0, 0, 0)
            r1_lay.setSpacing(4)
            r1_lay.setAlignment(Qt.AlignVCenter)

            owner.lbl_mode = QLabel("Mode:")
            owner.lbl_mode.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
            r1_lay.addWidget(owner.lbl_mode)

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
                QToolTip {
                    background-color: #0f172a;
                    color: #ffffff;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
            """

            owner.cb_experiment = ModernComboBox(max_hint_width=155)
            owner.cb_experiment.setStyleSheet(combo_style + "QComboBox { font-weight: 600; min-width: 130px; max-width: 155px; }")
            owner.cb_experiment.setFixedWidth(150)
            owner.cb_experiment.addItems([
                owner.modes[m_id].display_name for m_id in owner.mode_order
            ])
            owner.cb_experiment.currentIndexChanged.connect(owner._on_experiment_changed)
            r1_lay.addWidget(owner.cb_experiment)

            r1_lay.addSpacing(6)

            # Chemical potential mu filter with pre-filled cached values and free-typing
            owner.lbl_mu = QLabel("μ:")
            owner.lbl_mu.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
            r1_lay.addWidget(owner.lbl_mu)

            owner.cb_filter_mu = QComboBox()
            owner.cb_filter_mu.setEditable(True)
            owner.cb_filter_mu.setInsertPolicy(QComboBox.NoInsert)
            owner.cb_filter_mu.setStyleSheet(combo_style + "QComboBox { min-width: 44px; max-width: 58px; font-weight: 600; padding: 2px 14px 2px 6px; }")
            owner.cb_filter_mu.setFixedWidth(56)
            owner.cb_filter_mu.addItem("")  # Blank default implies all mu
            if owner.cb_filter_mu.lineEdit():
                owner.cb_filter_mu.lineEdit().clear()
            owner.cb_filter_mu.setCurrentIndex(0)
            owner.cb_filter_mu.currentTextChanged.connect(owner._on_mu_filter_changed)
            r1_lay.addWidget(owner.cb_filter_mu)

            owner.btn_clear_mu = QPushButton("✕")
            owner.btn_clear_mu.setToolTip("Clear μ filter (show all caches)")
            owner.btn_clear_mu.setFixedSize(18, 22)
            owner.btn_clear_mu.setStyleSheet("""
                QPushButton {
                    padding: 1px 2px;
                    background: #f1f5f9;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                    color: #64748b;
                    min-width: 16px;
                    max-width: 16px;
                    min-height: 20px;
                    max-height: 20px;
                }
                QPushButton:hover { background: #fee2e2; border-color: #ef4444; color: #dc2626; }
            """)
            owner.btn_clear_mu.clicked.connect(owner._clear_mu_filter)
            r1_lay.addWidget(owner.btn_clear_mu)

            r1_lay.addSpacing(6)

            owner.lbl_cache = QLabel("Cache:")
            owner.lbl_cache.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
            r1_lay.addWidget(owner.lbl_cache)

            owner.cb_cache_file = ModernComboBox(max_hint_width=330)
            owner.cb_cache_file.setStyleSheet(combo_style + "QComboBox { min-width: 180px; max-width: 330px; font-weight: 600; }")
            owner.cb_cache_file.setMaximumWidth(330)
            if owner.cb_cache_file.view():
                owner.cb_cache_file.view().setMinimumWidth(310)
            owner.cb_cache_file.currentIndexChanged.connect(owner._on_cache_selected)
            r1_lay.addWidget(owner.cb_cache_file)

            # In-Situ Compute Cache Button (Direct Modal Launcher)
            owner.btn_compute_cache = QPushButton("▶ Compute Cache")
            owner.btn_compute_cache.setToolTip("Compute owner-energy or susceptibility cache for real-time exploration")
            owner.btn_compute_cache.setStyleSheet("""
                QPushButton {
                    padding: 2px 10px;
                    background: #0891b2;
                    border: 1px solid #0e7490;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 700;
                    color: #ffffff;
                    min-height: 20px;
                }
                QPushButton:hover { background: #0e7490; }
                QPushButton:pressed { background: #155e75; }
            """)
            owner.btn_compute_cache.clicked.connect(owner._open_compute_cache_dialog)
            r1_lay.addWidget(owner.btn_compute_cache)

            # Hidden rescan proxy button for full backwards compatibility
            owner.btn_rescan = QPushButton("🔄", parent=owner)
            owner.btn_rescan.setVisible(False)
            owner.btn_rescan.clicked.connect(owner.scan_caches)

            # Fixed frequency window (±8.0 eV)
            owner.w_max = 8.0

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
            owner.btn_reset = QPushButton("Reset")
            owner.btn_reset.setToolTip("Reset view, zoom, slice, and pinned coordinates to default")
            owner.btn_reset.setStyleSheet(btn_action_style)
            owner.btn_reset.setFixedWidth(46)
            owner.btn_reset.clicked.connect(owner._reset_view)
            owner.btn_fit = owner.btn_reset  # Backwards compatibility alias
            r1_lay.addWidget(owner.btn_reset)

            owner.btn_copy = QPushButton("Copy")
            owner.btn_copy.setToolTip("Copy high-resolution figure to clipboard (300 DPI)")
            owner.btn_copy.setStyleSheet(btn_action_style)
            owner.btn_copy.setFixedWidth(44)
            owner.btn_copy.clicked.connect(owner._copy_figure_to_clipboard)
            r1_lay.addWidget(owner.btn_copy)

            owner.btn_save = QPushButton("Save")
            owner.btn_save.setToolTip("Save figure (PNG, PDF, SVG)")
            owner.btn_save.setStyleSheet(btn_action_style)
            owner.btn_save.setFixedWidth(44)
            owner.btn_save.clicked.connect(owner._save_figure_dialog)
            r1_lay.addWidget(owner.btn_save)

            h_lay.addLayout(r1_lay)

            # Row 2: J_K Continuous Slider + Contextual Physics Controls + Live HUD Chips
            r2_lay = QHBoxLayout()
            r2_lay.setContentsMargins(0, 0, 0, 0)
            r2_lay.setSpacing(6)
            r2_lay.setAlignment(Qt.AlignVCenter)

            owner.lbl_jk = QLabel("J_K:")
            owner.lbl_jk.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
            r2_lay.addWidget(owner.lbl_jk)

            owner.slider_jk = QSlider(Qt.Horizontal)
            owner.slider_jk.setRange(5, 120)  # 0.5 to 12.0
            owner.slider_jk.setValue(60)       # 6.0 default
            owner.slider_jk.setFixedWidth(120)
            owner.slider_jk.setStyleSheet("""
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
            owner.slider_jk.valueChanged.connect(owner._on_jk_slider_changed)
            owner.slider_jk.sliderReleased.connect(owner._flush_render)
            r2_lay.addWidget(owner.slider_jk)

            owner.lbl_jk_val = QLabel("J_K = 6.00")
            owner.lbl_jk_val.setFixedHeight(24)
            owner.lbl_jk_val.setStyleSheet("""
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
            r2_lay.addWidget(owner.lbl_jk_val)

            r2_lay.addSpacing(8)

            # Contextual Sub-container: Momentum Dropdown & Custom k-point Spinboxes
            owner.container_mom = QWidget()
            mom_lay = QHBoxLayout(owner.container_mom)
            mom_lay.setContentsMargins(0, 0, 0, 0)
            mom_lay.setSpacing(5)
            mom_lay.setAlignment(Qt.AlignVCenter)

            owner.lbl_mom_title = QLabel("k:")
            owner.lbl_mom_title.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
            mom_lay.addWidget(owner.lbl_mom_title)

            owner.cb_momentum = ModernComboBox(max_hint_width=130)
            owner.cb_momentum.setStyleSheet(combo_style + "QComboBox { min-width: 110px; max-width: 155px; font-weight: 600; }")
            owner.cb_momentum.addItems([
                "Antinodal (π, 0)",
                "Nodal (π/2, π/2)",
                "Center Γ (0, 0)",
                "Corner M (π, π)",
                "Custom (kx, ky)..."
            ])
            owner.cb_momentum.currentIndexChanged.connect(owner._on_momentum_combo_changed)
            mom_lay.addWidget(owner.cb_momentum)

            # Custom k-point spinboxes (visible only when Custom is chosen)
            owner.container_custom_k = QWidget()
            ck_lay = QHBoxLayout(owner.container_custom_k)
            ck_lay.setContentsMargins(0, 0, 0, 0)
            ck_lay.setSpacing(3)
            ck_lay.setAlignment(Qt.AlignVCenter)

            owner.lbl_kx = QLabel("kx:")
            owner.lbl_kx.setStyleSheet("font-size: 10px; font-weight: 600; color: #475569;")
            ck_lay.addWidget(owner.lbl_kx)

            owner.spin_kx = QDoubleSpinBox()
            owner.spin_kx.setRange(-1.0, 1.0)
            owner.spin_kx.setSingleStep(0.05)
            owner.spin_kx.setValue(1.0)
            owner.spin_kx.setSuffix(" π")
            owner.spin_kx.setDecimals(2)
            owner.spin_kx.setFixedWidth(62)
            owner.spin_kx.setStyleSheet("""
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
            owner.spin_kx.valueChanged.connect(owner._on_custom_k_spin_changed)
            ck_lay.addWidget(owner.spin_kx)

            owner.lbl_ky = QLabel("ky:")
            owner.lbl_ky.setStyleSheet("font-size: 10px; font-weight: 600; color: #475569;")
            ck_lay.addWidget(owner.lbl_ky)

            owner.spin_ky = QDoubleSpinBox()
            owner.spin_ky.setRange(-1.0, 1.0)
            owner.spin_ky.setSingleStep(0.05)
            owner.spin_ky.setValue(0.0)
            owner.spin_ky.setSuffix(" π")
            owner.spin_ky.setDecimals(2)
            owner.spin_ky.setFixedWidth(62)
            owner.spin_ky.setStyleSheet(owner.spin_kx.styleSheet())
            owner.spin_ky.valueChanged.connect(owner._on_custom_k_spin_changed)
            ck_lay.addWidget(owner.spin_ky)

            owner.container_custom_k.setVisible(False)
            mom_lay.addWidget(owner.container_custom_k)

            # Retained hidden button proxies with parent=owner (never top-level windows!)
            owner.btn_k_antinodal = QPushButton("Antinodal (π, 0)", parent=owner)
            owner.btn_k_antinodal.clicked.connect(lambda: owner._set_momentum(np.pi, 0.0))
            owner.btn_k_antinodal.setVisible(False)

            owner.btn_k_nodal = QPushButton("Nodal (π/2, π/2)", parent=owner)
            owner.btn_k_nodal.clicked.connect(lambda: owner._set_momentum(0.5 * np.pi, 0.5 * np.pi))
            owner.btn_k_nodal.setVisible(False)

            owner.btn_k_center = QPushButton("Center Γ(0, 0)", parent=owner)
            owner.btn_k_center.clicked.connect(lambda: owner._set_momentum(0.0, 0.0))
            owner.btn_k_center.setVisible(False)

            owner.btn_k_corner = QPushButton("Corner M(π, π)", parent=owner)
            owner.btn_k_corner.clicked.connect(lambda: owner._set_momentum(np.pi, np.pi))
            owner.btn_k_corner.setVisible(False)

            r2_lay.addWidget(owner.container_mom)

            # Contextual Sub-container: Energy Slice Slider
            owner.container_slice = QWidget()
            slice_lay = QHBoxLayout(owner.container_slice)
            slice_lay.setContentsMargins(0, 0, 0, 0)
            slice_lay.setSpacing(6)
            slice_lay.setAlignment(Qt.AlignVCenter)

            owner.lbl_slice_title = QLabel("Energy Slice ω:")
            owner.lbl_slice_title.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
            slice_lay.addWidget(owner.lbl_slice_title)

            owner.slider_slice = QSlider(Qt.Horizontal)
            owner.slider_slice.setRange(-200, 200)  # -2.0 to 2.0 eV
            owner.slider_slice.setValue(0)
            owner.slider_slice.setFixedWidth(120)
            owner.slider_slice.setStyleSheet(owner.slider_jk.styleSheet())
            owner.slider_slice.valueChanged.connect(owner._on_slice_slider_changed)
            owner.slider_slice.sliderReleased.connect(owner._flush_render)
            slice_lay.addWidget(owner.slider_slice)

            owner.lbl_slice_val = QLabel("ω = 0.00 eV")
            owner.lbl_slice_val.setFixedHeight(24)
            owner.lbl_slice_val.setStyleSheet("""
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
            slice_lay.addWidget(owner.lbl_slice_val)
            owner.container_slice.setVisible(False)
            r2_lay.addWidget(owner.container_slice)

            # Contextual Sub-container: Susceptibility Parameters (J_perp slider + K AFM/FM dropdown)
            owner.container_susc_params = QWidget()
            susc_lay = QHBoxLayout(owner.container_susc_params)
            susc_lay.setContentsMargins(0, 0, 0, 0)
            susc_lay.setSpacing(6)
            susc_lay.setAlignment(Qt.AlignVCenter)

            owner.lbl_jperp = QLabel("J_⊥:")
            owner.lbl_jperp.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
            susc_lay.addWidget(owner.lbl_jperp)

            owner.slider_jperp = QSlider(Qt.Horizontal)
            owner.slider_jperp.setRange(401, 1200)  # 4.01 to 12.00
            owner.slider_jperp.setValue(600)        # 6.00 default
            owner.slider_jperp.setSingleStep(1)
            owner.slider_jperp.setPageStep(10)
            owner.slider_jperp.setFixedWidth(110)
            owner.slider_jperp.setStyleSheet(owner.slider_jk.styleSheet())
            owner.slider_jperp.valueChanged.connect(owner._on_jperp_slider_changed)
            owner.slider_jperp.sliderReleased.connect(owner._flush_render)
            susc_lay.addWidget(owner.slider_jperp)

            owner.lbl_jperp_val = QLabel("J_⊥ = 6.00")
            owner.lbl_jperp_val.setFixedHeight(24)
            owner.lbl_jperp_val.setStyleSheet("""
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
            susc_lay.addWidget(owner.lbl_jperp_val)

            susc_lay.addSpacing(4)

            owner.lbl_k = QLabel("K:")
            owner.lbl_k.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
            susc_lay.addWidget(owner.lbl_k)

            owner.cb_k = ModernComboBox(max_hint_width=110)
            owner.cb_k.setStyleSheet(combo_style + "QComboBox { min-width: 95px; max-width: 120px; font-weight: 600; }")
            owner.cb_k.addItem("+1 (AFM)", 1.0)
            owner.cb_k.addItem("-1 (FM)", -1.0)
            owner.cb_k.currentIndexChanged.connect(owner._on_k_changed)
            susc_lay.addWidget(owner.cb_k)

            owner.container_susc_params.setVisible(False)
            r2_lay.addWidget(owner.container_susc_params)

            # Contextual Sub-container: Electrical Conductivity Parameters (Device Selector)
            owner.container_conductivity = QWidget()
            cond_lay = QHBoxLayout(owner.container_conductivity)
            cond_lay.setContentsMargins(0, 0, 0, 0)
            cond_lay.setSpacing(5)
            cond_lay.setAlignment(Qt.AlignVCenter)

            owner.lbl_device = QLabel("Device:")
            owner.lbl_device.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
            cond_lay.addWidget(owner.lbl_device)

            owner.cb_device = ModernComboBox(max_hint_width=135)
            owner.cb_device.setStyleSheet(combo_style + "QComboBox { min-width: 105px; max-width: 140px; font-weight: 600; }")
            gpu_detected = False
            try:
                from conductivity import is_gpu_available
                gpu_detected = is_gpu_available()
            except Exception:
                pass
            auto_label = "Auto (GPU)" if gpu_detected else "Auto (CPU)"
            owner.cb_device.addItem(auto_label, "auto")
            owner.cb_device.addItem("GPU (CUDA)", "gpu")
            owner.cb_device.addItem("CPU (Multi-core)", "cpu")
            owner.cb_device.currentIndexChanged.connect(owner._on_device_changed)
            cond_lay.addWidget(owner.cb_device)

            owner.container_conductivity.setVisible(False)
            r2_lay.addWidget(owner.container_conductivity)

            # Contextual Tip for 2D Maps
            owner.lbl_map_tip = QLabel("💡 Tip: Click map to probe k • Double-click for A(k, ω)")
            owner.lbl_map_tip.setStyleSheet("color: #64748b; font-size: 10px; font-style: italic;")
            owner.lbl_map_tip.setWordWrap(True)
            owner.lbl_map_tip.setMinimumWidth(0)
            owner.lbl_map_tip.setVisible(False)
            r2_lay.addWidget(owner.lbl_map_tip)

            r2_lay.addStretch(1)

            # Live Physics HUD Chips (Clean, no noisy emoji icons, with rich explanatory tooltips)
            chip_style_z = "QLabel { background: #ecfeff; border: 1px solid #a5f3fc; border-radius: 4px; padding: 2px 7px; font-weight: 700; color: #0e7490; font-size: 11px; } QLabel:hover { background: #cffafe; border-color: #0891b2; }"
            chip_style_g = "QLabel { background: #fffbeb; border: 1px solid #fde68a; border-radius: 4px; padding: 2px 7px; font-weight: 700; color: #b45309; font-size: 11px; } QLabel:hover { background: #fef3c7; border-color: #d97706; }"
            chip_style_m = "QLabel { background: #f5f3ff; border: 1px solid #ddd6fe; border-radius: 4px; padding: 2px 7px; font-weight: 700; color: #6d28d9; font-size: 11px; } QLabel:hover { background: #ede9fe; border-color: #7c3aed; }"

            owner.lbl_live_z = QLabel("Z(k): —")
            owner.lbl_live_z.setStyleSheet(chip_style_z)
            owner.lbl_live_z.setFixedHeight(24)
            owner.lbl_live_z.setToolTip(
                "<b>Quasiparticle Residue Z(k) ∈ (0, 1]</b><br>"
                "<i>Formula: Z(k) = [1 - ∂ReΣ/∂ω |<sub>ω→0</sub>]<sup>-1</sup></i><br><br>"
                "• <b>What it is:</b> Coherent single-particle pole weight at the Fermi level.<br>"
                "• <b>Physical Meaning:</b> Fraction of the electron state behaving as a coherent quasiparticle.<br>"
                "• <b>Interpretation:</b><br>"
                "  - <i>Z ≈ 1:</i> Bare / weakly interacting Fermi liquid.<br>"
                "  - <i>Z ≪ 1:</i> Heavy fermion state formed by strong Kondo exchange coupling J<sub>K</sub>.<br>"
                "  - <i>Z → 0:</i> Complete quasiparticle breakdown / localized Mott insulating state."
            )
            r2_lay.addWidget(owner.lbl_live_z)

            owner.lbl_live_gamma = QLabel("Γ(k): —")
            owner.lbl_live_gamma.setStyleSheet(chip_style_g)
            owner.lbl_live_gamma.setFixedHeight(24)
            owner.lbl_live_gamma.setToolTip(
                "<b>Quasiparticle Damping / Scattering Rate Γ(k)</b><br>"
                "<i>Formula: Γ(k) = |ImΣ(k, ω=0)| [eV]</i><br><br>"
                "• <b>What it is:</b> Inelastic electronic scattering rate off the localized spin background.<br>"
                "• <b>Quasiparticle Lifetime:</b> τ<sub>k</sub> ~ ħ / [2 Γ(k)].<br>"
                "• <b>Physical Meaning:</b> Directly broadens the spectral function peak A(k, ω).<br>"
                "• In a strict Fermi liquid at T=0, Γ(0) → 0. Here, Kondo fluctuations introduce finite damping."
            )
            r2_lay.addWidget(owner.lbl_live_gamma)

            owner.lbl_live_mass = QLabel("m*/m: —")
            owner.lbl_live_mass.setStyleSheet(chip_style_m)
            owner.lbl_live_mass.setFixedHeight(24)
            owner.lbl_live_mass.setToolTip(
                "<b>Effective Mass Enhancement m*/m</b><br>"
                "<i>Formula: m*/m ≈ 1 / Z(k) = 1 - ∂ReΣ/∂ω |<sub>ω→0</sub></i><br><br>"
                "• <b>What it is:</b> Ratio of the renormalized quasiparticle mass m* to the bare band mass m.<br>"
                "• <b>Physical Meaning:</b> Quantifies electronic inertia due to the many-body Kondo dressing cloud.<br>"
                "• <b>Observable Consequences:</b><br>"
                "  - Flattens the quasiparticle dispersion near E<sub>F</sub> (v<sub>F</sub>* = v<sub>F</sub> / [m*/m]).<br>"
                "  - Proportional to the Sommerfeld electronic specific heat coefficient γ<sub>C</sub> ∝ m*/m."
            )
            r2_lay.addWidget(owner.lbl_live_mass)

            owner.lbl_conductivity_stats = QLabel("DC σ(0): —")
            owner.lbl_conductivity_stats.setStyleSheet(chip_style_z)
            owner.lbl_conductivity_stats.setFixedHeight(24)
            owner.lbl_conductivity_stats.setVisible(False)
            r2_lay.addWidget(owner.lbl_conductivity_stats)

            h_lay.addLayout(r2_lay)
            lay.addWidget(owner.header_frame)

            # Alias for backward compatibility with test suites
            owner.ctrl_frame = owner.header_frame

            # =====================================================================
            # 2. INTERACTIVE MATPLOTLIB CANVAS
            # =====================================================================
            owner.fig = Figure(figsize=(7, 5), dpi=100)
            owner.fig.patch.set_facecolor("#ffffff")
            owner.canvas = FigureCanvasQTAgg(owner.fig)

            owner._orig_canvas_draw = owner.canvas.draw
            owner._orig_canvas_draw_idle = owner.canvas.draw_idle
            owner.canvas.draw = owner._themed_draw
            owner.canvas.draw_idle = owner._themed_draw_idle

            # Hidden toolbar instance retained for full backwards compatibility
            owner.toolbar = NavigationToolbar2QT(owner.canvas, owner)
            owner.toolbar.setVisible(False)

            lay.addWidget(owner.canvas, 1)

            # Connect interactive mouse navigation events on canvas (Zoom on scroll, Pan on drag)
            owner.canvas.mpl_connect("scroll_event", owner._on_canvas_scroll)
            owner.canvas.mpl_connect("button_press_event", owner._on_canvas_press)
            owner.canvas.mpl_connect("motion_notify_event", owner._on_canvas_motion)
            owner.canvas.mpl_connect("button_release_event", owner._on_canvas_release)

            owner.set_theme(owner.is_dark)
            owner._render_placeholder()
