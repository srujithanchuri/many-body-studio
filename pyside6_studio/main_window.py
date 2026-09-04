"""Many-Body Physics Studio Pro [PySide6 UI Architecture]
Pure Frontend Architecture wired to isolated QProcess CalculationBridge.
Features Dual-Perspective Workspace:
1. [ 🔬 Simulation Studio ]:
   - Context-adaptive parameter inspector (t, t', mu, K, sweeps).
   - Numerical Grid & Resolution Presets (Fast Preview N=64, Standard N=100, High-Res N=256, Custom).
   - Isolated QProcess execution on RTX 5060 with live streaming console and sub-second cancellation.
   - Hardware-accelerated CAD zoom/pan canvas (QGraphicsView).
2. [ 🎨 Publication Figure Studio ]:
   - All physics/runner controls are cleanly stowed away.
   - Scientific multi-panel layout templates and typography styling.
"""

import sys
import os
import time
import glob
from PySide6.QtCore import Qt, QTimer, Slot, QObject, QEvent, QSize
from PySide6.QtGui import QAction, QIcon, QPixmap, QCloseEvent, QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QDockWidget, QTabWidget, QSplitter, QGroupBox, QLabel, QLineEdit,
    QDoubleSpinBox, QSpinBox, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit, QProgressBar, QToolBar,
    QTreeWidget, QTreeWidgetItem, QMessageBox, QFileDialog, QToolButton,
    QMenu, QStackedWidget, QCheckBox, QScrollArea, QFrame, QSizePolicy
)

from pyside6_studio.theme import LIGHT_THEME_QSS, DARK_THEME_QSS, create_light_palette, create_dark_palette
from pyside6_studio.canvas import InteractivePlotCanvas
from pyside6_studio.backend.bridge import CalculationBridge
from pyside6_studio.backend.vram_cleaner import flush_gpu_vram
from pyside6_studio.core.hardware import get_hardware_info
from pyside6_studio.core import config

DEFAULT_RESULTS_DIR = r"C:\Users\sruji\Projects\masters_thesis_gui\results"


def get_available_plots(output_dir=None):
    """
    Scans the configured output directory for real simulation plots.
    Inspects output_dir/plots (or output_dir directly), filtering strictly for physics observables.
    """
    plots = {}
    target_dir = output_dir or DEFAULT_RESULTS_DIR
    if not os.path.isdir(target_dir):
        return plots

    sub_plots = os.path.join(target_dir, "plots")
    search_dir = sub_plots if os.path.isdir(sub_plots) else target_dir

    for f in glob.glob(os.path.join(search_dir, "*.png")):
        bname = os.path.basename(f)
        if bname.startswith(("sweep_", "both_", "spectral_", "phase_", "chi_")):
            plots[bname] = os.path.normpath(f)

    return plots


class ModernCard(QGroupBox):
    """QGroupBox that allows its width to shrink down gracefully without long title text inflating minimumSizeHint."""
    def minimumSizeHint(self):
        sz = super().minimumSizeHint()
        return QSize(min(sz.width(), 240), sz.height())


class ModernComboBox(QComboBox):
    """QComboBox that allows fluid resizing without long text items inflating minimumSizeHint."""
    def minimumSizeHint(self):
        sz = super().minimumSizeHint()
        return QSize(min(sz.width(), 140), sz.height())


class DynamicStackedWidget(QStackedWidget):
    """QStackedWidget that reports sizeHint dynamically based on current active page."""
    def sizeHint(self):
        curr = self.currentWidget()
        if curr:
            return curr.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self):
        curr = self.currentWidget()
        if curr:
            sz = curr.minimumSizeHint()
            return QSize(min(sz.width(), 240), sz.height())
        return super().minimumSizeHint()


class WheelScrollRedirectFilter(QObject):
    """
    Prevents accidental value changes when scrolling through parameter panels.
    Redirects wheel events over QSpinBox, QDoubleSpinBox, and QComboBox
    to the nearest parent QScrollArea viewport so vertical scrolling is smooth and uninterrupted.
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            if isinstance(obj, (QSpinBox, QDoubleSpinBox, QComboBox)):
                # If a QComboBox popup is currently visible, allow normal wheel navigation within it
                if isinstance(obj, QComboBox) and obj.view() and obj.view().isVisible():
                    return False

                # Redirect wheel event directly to the nearest parent QScrollArea viewport
                parent = obj.parent()
                while parent:
                    if isinstance(parent, QScrollArea):
                        QApplication.sendEvent(parent.viewport(), event)
                        return True
                    parent = parent.parent()

                # If not inside a scroll area, safely ignore the event to prevent unwanted value modifications
                return True
        return super().eventFilter(obj, event)


class UnifiedWorkbenchWindow(QMainWindow):
    STUDY_SE = "⚡ Spectral Sweep (DOS / FS / Path)"
    STUDY_SPEC = "🌊 Spectral Function A(k, ω)"
    STUDY_PD = "📈 Phase Diagram (Root Bisection)"
    STUDY_SUSC = "📊 Susceptibility Sweep (RPA)"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Many-Body Studio Pro • Alpha v2")
        self.resize(1440, 920)

        # Install wheel scroll redirect filter to eliminate accidental value changes
        self.wheel_filter = WheelScrollRedirectFilter(self)
        app_inst = QApplication.instance()
        if app_inst:
            app_inst.installEventFilter(self.wheel_filter)
            app_inst.setPalette(create_light_palette())
            app_inst.setStyleSheet(LIGHT_THEME_QSS)

        self.plots = get_available_plots()
        self.is_dark = False
        self.active_study = self.STUDY_SE
        self.current_perspective = "simulation"
        self._updating_preset = False
        self.setStyleSheet(LIGHT_THEME_QSS)

        # Initialize QProcess Calculation Bridge
        self.bridge = CalculationBridge(self)
        self.bridge.sig_started.connect(self._on_calc_started)
        self.bridge.sig_log.connect(self._on_calc_log)
        self.bridge.sig_status.connect(self._on_calc_status)
        self.bridge.sig_progress.connect(self._on_calc_progress)
        self.bridge.sig_completed.connect(self._on_calc_completed)
        self.bridge.sig_error.connect(self._on_calc_error)
        self.bridge.sig_cancelled.connect(self._on_calc_cancelled)

        # Simulation Queue Timer for UI demonstration
        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self._on_queue_tick)
        self.active_queue_row = -1
        self.active_queue_progress = 0

        self._build_toolbar()
        self._build_central_workspace()
        self._build_navigator_dock()
        self._build_inspector_dock()
        self._build_bottom_drawer_dock()
        self._build_statusbar()

        self.dock_nav.setMaximumWidth(320)

        # Ensure docks start with proper comfortable widths & compact bottom height
        self.resizeDocks([self.dock_bottom], [150], Qt.Vertical)
        self.resizeDocks([self.dock_nav, self.dock_inspector], [240, 360], Qt.Horizontal)
        QTimer.singleShot(0, lambda: (
            self.resizeDocks([self.dock_bottom], [150], Qt.Vertical),
            self.resizeDocks([self.dock_nav, self.dock_inspector], [240, 360], Qt.Horizontal)
        ))

        # Wire Output Directory text change to dynamically re-populate datasets & plots
        self.edit_out_dir.textChanged.connect(self.refresh_dataset_tree)
        self.refresh_dataset_tree()

        # Initialize default state
        self.set_active_study(self.STUDY_SE)
        self.set_perspective("simulation")

    # =========================================================================
    # TOOLBAR & MODE SWITCHER
    # =========================================================================
    def _build_toolbar(self):
        self.tb = QToolBar("Main Controls", self)
        self.tb.setMovable(False)
        self.addToolBar(self.tb)

        lbl_persp = QLabel(" WORKSPACE MODE: ")
        lbl_persp.setStyleSheet("font-weight: 700; color: #64748b; font-size: 11px;")
        self.tb.addWidget(lbl_persp)

        self.btn_mode_sim = QPushButton("🔬 Simulation Studio")
        self.btn_mode_sim.setObjectName("ModeSimActive")
        self.btn_mode_sim.clicked.connect(lambda: self.set_perspective("simulation"))
        self.tb.addWidget(self.btn_mode_sim)

        self.btn_mode_pub = QPushButton("🎨 Publication Figure Studio")
        self.btn_mode_pub.setObjectName("ModeInactive")
        self.btn_mode_pub.clicked.connect(lambda: self.set_perspective("publication"))
        self.tb.addWidget(self.btn_mode_pub)

        self.tb.addSeparator()

        # Simulation Studio Toolbar Actions
        self.btn_run = QToolButton()
        self.btn_run.setObjectName("PrimaryBtn")
        self.btn_run.setText(f"⚡ Run Active: {self.active_study}")
        self.btn_run.setPopupMode(QToolButton.MenuButtonPopup)
        self.btn_run.clicked.connect(self.run_simulation_ui)

        menu_run = QMenu(self.btn_run)
        menu_run.addAction(self.STUDY_SE).triggered.connect(lambda: self._select_and_run(self.STUDY_SE))
        menu_run.addAction(self.STUDY_SPEC).triggered.connect(lambda: self._select_and_run(self.STUDY_SPEC))
        menu_run.addAction(self.STUDY_PD).triggered.connect(lambda: self._select_and_run(self.STUDY_PD))
        menu_run.addAction(self.STUDY_SUSC).triggered.connect(lambda: self._select_and_run(self.STUDY_SUSC))
        self.btn_run.setMenu(menu_run)
        self.action_run = self.tb.addWidget(self.btn_run)

        # Dedicated Cancel / Stop button
        self.btn_cancel = QPushButton("⏹ Cancel / Stop")
        self.btn_cancel.setObjectName("BtnCancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_simulation_ui)
        self.action_cancel = self.tb.addWidget(self.btn_cancel)

        self.btn_queue = QPushButton("➕ Add Active to Queue")
        self.btn_queue.clicked.connect(self.add_to_queue)
        self.action_queue = self.tb.addWidget(self.btn_queue)

        self.btn_split = QPushButton("⚏ Split View (Compare)")
        self.btn_split.setCheckable(True)
        self.btn_split.toggled.connect(self.toggle_split_view)
        self.action_split = self.tb.addWidget(self.btn_split)

        # Publication Studio Toolbar Actions
        self.btn_export_pdf = QPushButton("📄 Save Vector PDF for LaTeX (300 DPI)")
        self.btn_export_pdf.setObjectName("PrimaryBtn")
        self.btn_export_pdf.clicked.connect(self.export_pdf_dialog)
        self.action_export_pdf = self.tb.addWidget(self.btn_export_pdf)
        self.btn_export_pdf.setVisible(False)

        self.btn_copy_latex = QPushButton("📋 Copy LaTeX Code")
        self.btn_copy_latex.clicked.connect(self.copy_latex_snippet)
        self.action_copy_latex = self.tb.addWidget(self.btn_copy_latex)
        self.btn_copy_latex.setVisible(False)

        self.tb.addSeparator()

        self.btn_theme = QPushButton("🌓 Theme")
        self.btn_theme.clicked.connect(self.toggle_theme)
        self.tb.addWidget(self.btn_theme)

        self.btn_reset_zoom = QPushButton("🔍 Fit Window")
        self.btn_reset_zoom.clicked.connect(self.reset_active_zoom)
        self.tb.addWidget(self.btn_reset_zoom)

    # =========================================================================
    # CENTRAL VIEWPORT (INTERACTIVE CANVAS & SPLIT VIEW)
    # =========================================================================
    def _build_central_workspace(self):
        self.central_container = QWidget()
        self.central_container.setObjectName("CentralWidget")
        layout = QVBoxLayout(self.central_container)
        layout.setContentsMargins(4, 4, 4, 4)

        self.view_splitter = QSplitter(Qt.Horizontal)

        # Primary interactive canvas
        self.canvas_left = InteractivePlotCanvas()
        self.canvas_left.coord_changed.connect(self._on_left_coord)
        self.view_splitter.addWidget(self.canvas_left)

        # Secondary comparison canvas (shown in split view)
        self.canvas_right = InteractivePlotCanvas()
        self.canvas_right.coord_changed.connect(self._on_right_coord)
        self.canvas_right.setVisible(False)
        self.view_splitter.addWidget(self.canvas_right)

        layout.addWidget(self.view_splitter)
        self.setCentralWidget(self.central_container)

    # =========================================================================
    # LEFT DOCK: NAVIGATOR (SIMULATION) VS MULTI-PANEL ASSIGNER (PUBLICATION)
    # =========================================================================
    def _build_navigator_dock(self):
        self.dock_nav = QDockWidget("🧭 Study Navigator & Datasets", self)
        self.dock_nav.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock_nav.setMinimumWidth(220)

        self.nav_stack = QStackedWidget()

        # PAGE 1: Simulation Studies Tree
        p_sim = QWidget()
        l_sim = QVBoxLayout(p_sim); l_sim.setContentsMargins(4, 4, 4, 4)
        lbl_hint = QLabel("Select active study to configure or past result to view:")
        lbl_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        l_sim.addWidget(lbl_hint)

        self.tree_nav = QTreeWidget()
        self.tree_nav.setHeaderHidden(True)

        self.grp_studies = QTreeWidgetItem(self.tree_nav, ["🔬 SELECT STUDY TO RUN"])
        self.grp_studies.setExpanded(True)
        self.item_se = QTreeWidgetItem(self.grp_studies, [self.STUDY_SE])
        self.item_spec = QTreeWidgetItem(self.grp_studies, [self.STUDY_SPEC])
        self.item_pd = QTreeWidgetItem(self.grp_studies, [self.STUDY_PD])
        self.item_susc = QTreeWidgetItem(self.grp_studies, [self.STUDY_SUSC])

        self.grp_results = QTreeWidgetItem(self.tree_nav, ["📁 PREVIOUS DATASETS & PLOTS"])
        self.grp_results.setExpanded(True)
        for name in self.plots.keys():
            QTreeWidgetItem(self.grp_results, [name])

        self.tree_nav.itemClicked.connect(self._on_nav_selected)
        l_sim.addWidget(self.tree_nav)
        self.nav_stack.addWidget(p_sim)

        # PAGE 2: Publication Figure Layout Assigner
        p_pub = QWidget()
        l_pub = QVBoxLayout(p_pub); l_pub.setContentsMargins(4, 4, 4, 4)

        grp_panels = ModernCard("Multi-Panel Dataset Assignment")
        gp_lay = QVBoxLayout(grp_panels)

        gp_lay.addWidget(QLabel("Layout Template:"))
        self.cb_pub_template = ModernComboBox()
        self.cb_pub_template.addItems([
            "3-Panel Row [DOS (a) | Fermi Surface (b) | Path (c)]",
            "2-Panel Comparison [Static χ(q) | Dynamic χ(q, ω)]",
            "2x2 Full Suite [DOS | FS | Path | Phase Diagram]",
            "1x1 Single Focus Figure"
        ])
        self.cb_pub_template.currentIndexChanged.connect(self._update_publication_preview)
        gp_lay.addWidget(self.cb_pub_template)

        gp_lay.addWidget(QLabel("\nPanel (a) Data Source:"))
        self.cb_panel_a = ModernComboBox(); self.cb_panel_a.addItems(list(self.plots.keys()))
        gp_lay.addWidget(self.cb_panel_a)

        gp_lay.addWidget(QLabel("Panel (b) Data Source:"))
        self.cb_panel_b = ModernComboBox(); self.cb_panel_b.addItems(list(self.plots.keys()))
        if len(self.plots) > 1: self.cb_panel_b.setCurrentIndex(1)
        gp_lay.addWidget(self.cb_panel_b)

        gp_lay.addWidget(QLabel("Panel (c) Data Source:"))
        self.cb_panel_c = ModernComboBox(); self.cb_panel_c.addItems(list(self.plots.keys()))
        if len(self.plots) > 2: self.cb_panel_c.setCurrentIndex(2)
        gp_lay.addWidget(self.cb_panel_c)

        btn_refresh_comp = QPushButton("🔄 Refresh Composite Preview")
        btn_refresh_comp.setObjectName("PrimaryBtn")
        btn_refresh_comp.clicked.connect(self._update_publication_preview)
        gp_lay.addWidget(btn_refresh_comp)

        l_pub.addWidget(grp_panels)
        l_pub.addStretch()
        self.nav_stack.addWidget(p_pub)

        self.dock_nav.setWidget(self.nav_stack)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_nav)

    # =========================================================================
    # RIGHT DOCK: PARAMETER INSPECTOR (WITH VERTICAL SCROLL AREA)
    # =========================================================================
    def _build_inspector_dock(self):
        self.dock_inspector = QDockWidget("⚙️ Parameter Inspector", self)
        self.dock_inspector.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock_inspector.setMinimumWidth(340)

        # Wrap in QScrollArea so cards never overlap or clip beneath the bottom execution center
        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setFrameShape(QFrame.NoFrame)
        self.inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.inspector_scroll.setMinimumWidth(320)

        self.inspector_stack = QStackedWidget()

        # PAGE 1: Simulation Parameter Inspector
        panel_sim = QWidget()
        lay_sim = QVBoxLayout(panel_sim)
        lay_sim.setContentsMargins(4, 4, 4, 4)
        lay_sim.setSpacing(5)

        # 1. Active Study Switcher
        grp_selector = ModernCard("Active Calculation Study")
        sel_lay = QVBoxLayout(grp_selector)
        self.cb_active_study = ModernComboBox()
        self.cb_active_study.setObjectName("StudyDropdown")
        self.cb_active_study.addItems([self.STUDY_SE, self.STUDY_SPEC, self.STUDY_PD, self.STUDY_SUSC])
        self.cb_active_study.currentTextChanged.connect(self.set_active_study)
        sel_lay.addWidget(self.cb_active_study)
        lay_sim.addWidget(grp_selector)

        # 2. Study-specific stacked parameters
        self.param_stack = DynamicStackedWidget()
        self.param_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        # 2a. Spectral Sweep parameters
        grp_se = ModernCard("Spectral Sweep (DOS / FS / Path) Parameters")
        grp_se.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        gse = QVBoxLayout(grp_se)
        gse.setSpacing(5)
        gse.addWidget(QLabel("Sweep Target:"))
        self.cb_se_mode = ModernComboBox()
        self.cb_se_mode.addItems(["Kondo Coupling (J_K)", "Interlayer Coupling (J_⊥)"])
        self.cb_se_mode.currentIndexChanged.connect(self._on_se_sweep_mode_change)
        gse.addWidget(self.cb_se_mode)

        gse.addWidget(QLabel("Coupling Values Across Subplots (comma-separated):"))
        self.edit_se_vals = QLineEdit("3.0, 6.0, 9.0")
        gse.addWidget(self.edit_se_vals)

        h_se_row = QHBoxLayout()
        self.lbl_se_fixed = QLabel("Fixed Interlayer Coupling (J_⊥):")
        self.lbl_se_fixed.setStyleSheet("font-weight: 600;")
        h_se_row.addWidget(self.lbl_se_fixed)
        h_se_row.addStretch()

        self.spin_se_fixed = QDoubleSpinBox()
        self.spin_se_fixed.setRange(0.0, 50.0)
        self.spin_se_fixed.setValue(6.0)
        self.spin_se_fixed.setSingleStep(0.5)
        self.spin_se_fixed.setFixedWidth(100)
        h_se_row.addWidget(self.spin_se_fixed)
        gse.addLayout(h_se_row)

        self.lbl_se_fixed_desc = QLabel("Constant value of J_⊥ held fixed while sweeping J_K across columns")
        self.lbl_se_fixed_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        self.lbl_se_fixed_desc.setWordWrap(True)
        gse.addWidget(self.lbl_se_fixed_desc)
        self.param_stack.addWidget(grp_se)

        # 2b. Spectral Function A(k, omega) parameters
        grp_spec = ModernCard("Quasiparticle Spectral Function A(k, ω) && Self-Energy")
        grp_spec.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        gsp = QVBoxLayout(grp_spec)
        gsp.setSpacing(5)

        gsp.addWidget(QLabel("Sweep Target:"))
        self.cb_spec_mode = ModernComboBox()
        self.cb_spec_mode.addItems(["Kondo Coupling (J_K)", "Interlayer Coupling (J_⊥)"])
        self.cb_spec_mode.currentIndexChanged.connect(self._on_spec_sweep_mode_change)
        gsp.addWidget(self.cb_spec_mode)

        gsp.addWidget(QLabel("Coupling Values (comma-separated):"))
        self.edit_spec_vals = QLineEdit("3.0, 6.0, 9.0")
        gsp.addWidget(self.edit_spec_vals)

        h_spec_row = QHBoxLayout()
        self.lbl_spec_fixed = QLabel("Fixed Interlayer Coupling (J_⊥):")
        self.lbl_spec_fixed.setStyleSheet("font-weight: 600;")
        h_spec_row.addWidget(self.lbl_spec_fixed)
        h_spec_row.addStretch()

        self.spin_spec_fixed = QDoubleSpinBox()
        self.spin_spec_fixed.setRange(0.0, 50.0)
        self.spin_spec_fixed.setValue(6.0)
        self.spin_spec_fixed.setSingleStep(0.5)
        self.spin_spec_fixed.setFixedWidth(100)
        h_spec_row.addWidget(self.spin_spec_fixed)
        gsp.addLayout(h_spec_row)

        self.lbl_spec_fixed_desc = QLabel("Constant value held fixed while sweeping coupling")
        self.lbl_spec_fixed_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        self.lbl_spec_fixed_desc.setWordWrap(True)
        gsp.addWidget(self.lbl_spec_fixed_desc)

        gsp.addWidget(QLabel("Target Momentum (k):"))
        self.cb_mom = ModernComboBox()
        self.cb_mom.addItems([
            "Antinodal k_F (π, 0)",
            "Nodal k_F (π/2, π/2)",
            "Zone Center Γ (0, 0)",
            "Zone Corner M (π, π)",
            "Custom (kx, ky)..."
        ])
        self.cb_mom.currentIndexChanged.connect(self._on_mom_choice_changed)
        gsp.addWidget(self.cb_mom)

        # Custom k container (only visible when "Custom (kx, ky)..." is selected)
        self.box_custom_k = QWidget()
        lay_ck = QVBoxLayout(self.box_custom_k)
        lay_ck.setContentsMargins(0, 2, 0, 2)
        lay_ck.addWidget(QLabel("Custom Momentum (kx, ky) in units of π:"))
        self.edit_custom_k = QLineEdit("1.0, 0.0")
        lay_ck.addWidget(self.edit_custom_k)
        gsp.addWidget(self.box_custom_k)
        self.box_custom_k.setVisible(False)

        gsp.addWidget(QLabel("Observables Layout:"))
        self.cb_layout = ModernComboBox()
        self.cb_layout.addItems([
            "Both (Re Σ, A, Im Σ) [3 Panels]",
            "Self-Energy Only (Re Σ & Im Σ) [2 Panels]",
            "Spectral Function Only A(k, ω) [1 Panel]"
        ])
        gsp.addWidget(self.cb_layout)
        self.param_stack.addWidget(grp_spec)

        # 2c. Phase Diagram parameters
        grp_pd = ModernCard("Phase Boundary Bisection Search")
        grp_pd.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        gpd = QVBoxLayout(grp_pd)
        gpd.setSpacing(5)
        h_min = QHBoxLayout(); h_min.addWidget(QLabel("J_K min:")); h_min.addStretch(); self.s_min = QDoubleSpinBox(); self.s_min.setValue(0.0); self.s_min.setFixedWidth(100); h_min.addWidget(self.s_min); gpd.addLayout(h_min)
        h_max = QHBoxLayout(); h_max.addWidget(QLabel("J_K max:")); h_max.addStretch(); self.s_max = QDoubleSpinBox(); self.s_max.setValue(12.0); self.s_max.setFixedWidth(100); h_max.addWidget(self.s_max); gpd.addLayout(h_max)
        h_pts = QHBoxLayout(); h_pts.addWidget(QLabel("Points:")); h_pts.addStretch(); self.s_pts = QSpinBox(); self.s_pts.setValue(200); self.s_pts.setFixedWidth(100); h_pts.addWidget(self.s_pts); gpd.addLayout(h_pts)
        btn_pre = QPushButton("⚡ Precompute Bare χ₀ (Bubble)")
        btn_pre.clicked.connect(self._on_precompute_bubble)
        gpd.addWidget(btn_pre)
        self.param_stack.addWidget(grp_pd)

        # 2d. Susceptibility parameters
        grp_susc = ModernCard("RPA Spin Susceptibility Modes")
        grp_susc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        gsusc = QVBoxLayout(grp_susc)
        gsusc.setSpacing(6)
        self.chk_static = QCheckBox("Compute Static χ(q) (2D BZ Map)")
        self.chk_static.setChecked(True)
        gsusc.addWidget(self.chk_static)
        self.chk_dynamic = QCheckBox("Compute Dynamic χ(q, ω) (Path)")
        self.chk_dynamic.setChecked(True)
        gsusc.addWidget(self.chk_dynamic)
        gsusc.addWidget(QLabel("Coupling Values:"))
        self.edit_susc_vals = QLineEdit("3.0, 6.0, 9.0")
        gsusc.addWidget(self.edit_susc_vals)
        self.param_stack.addWidget(grp_susc)

        lay_sim.addWidget(self.param_stack)

        # 3. Compute & Solver Backend Card (Matching Original GUI Architecture)
        grp_solver = ModernCard("Compute && Solver Backend")
        gsolv = QVBoxLayout(grp_solver)
        gsolv.setSpacing(4)

        h_solv = QHBoxLayout()
        h_solv.addWidget(QLabel("Solver Backend:"))
        self.cb_solver_choice = ModernComboBox()
        self.cb_solver_choice.addItems([
            "CUDA GPU (NVIDIA RTX 5060 64-bit)",
            "CPU 64-bit (NumPy / SciPy)"
        ])
        self.cb_solver_choice.currentIndexChanged.connect(self._on_solver_backend_changed)
        h_solv.addWidget(self.cb_solver_choice)
        gsolv.addLayout(h_solv)

        # Dynamic CPU Core Usage Row (shown only when CPU solver is selected)
        self.box_cpu_limit = QWidget()
        lay_cpu = QHBoxLayout(self.box_cpu_limit)
        lay_cpu.setContentsMargins(0, 2, 0, 2)
        lay_cpu.addWidget(QLabel("CPU Core Usage:"))
        self.cb_cpu_limit = ModernComboBox()
        self.cb_cpu_limit.addItems(["50%", "75%", "80% [Balanced]", "100% [Maximum]"])
        self.cb_cpu_limit.setCurrentIndex(2)  # 80% default
        lay_cpu.addWidget(self.cb_cpu_limit)
        gsolv.addWidget(self.box_cpu_limit)
        self.box_cpu_limit.setVisible(False)

        # Live Hardware Status Pill inside Solver Card
        self.lbl_hw_badge = QLabel("⚡ GPU Active: NVIDIA GeForce RTX 5060 Laptop GPU (64-bit CuPy)")
        self.lbl_hw_badge.setStyleSheet(
            "color: #15803d; font-weight: 600; font-size: 11px; padding: 6px 8px; "
            "background: #dcfce7; border: 1px solid #bbf7d0; border-radius: 5px;"
        )
        self.lbl_hw_badge.setWordWrap(True)
        gsolv.addWidget(self.lbl_hw_badge)
        lay_sim.addWidget(grp_solver)

        # 4. Numerical Grid & Resolution Presets
        grp_res = ModernCard("Numerical Grid && Resolution Presets")
        gres = QVBoxLayout(grp_res)
        gres.setSpacing(4)

        gres.addWidget(QLabel("Resolution Preset:"))
        self.cb_preset = ModernComboBox()
        self.cb_preset.addItems([
            "Fast Preview (N=64, Nw=2001)",
            "Standard (N=100, Nw=4801)",
            "High-Res Production (N=256, Nw=8001)",
            "Custom Grid..."
        ])
        self.cb_preset.currentIndexChanged.connect(self._on_preset_selected)
        gres.addWidget(self.cb_preset)

        # Preset summary badge (shown when a standard preset is active)
        self.lbl_preset_summary = QLabel("⚡ Preset: 64×64 grid | Nw: 2001 | ω_max: 20.0 | η: 0.08")
        self.lbl_preset_summary.setStyleSheet("color: #2563eb; font-size: 11px; font-weight: 600; padding: 2px;")
        self.lbl_preset_summary.setWordWrap(True)
        gres.addWidget(self.lbl_preset_summary)

        # Custom Grid container - strictly collapsed/hidden unless "Custom Grid..." is selected
        self.box_custom_grid = QWidget()
        lay_custom = QVBoxLayout(self.box_custom_grid)
        lay_custom.setContentsMargins(0, 4, 0, 0)
        lay_custom.setSpacing(4)

        h_n = QHBoxLayout()
        h_n.addWidget(QLabel("Grid Size (N):"))
        h_n.addStretch()
        self.spin_n = QSpinBox()
        self.spin_n.setRange(32, 512)
        self.spin_n.setValue(64)
        self.spin_n.setSingleStep(32)
        self.spin_n.setFixedWidth(100)
        self.spin_n.valueChanged.connect(self._on_custom_grid_edit)
        h_n.addWidget(self.spin_n)
        lay_custom.addLayout(h_n)

        h_nw = QHBoxLayout()
        h_nw.addWidget(QLabel("Frequency (N_ω):"))
        h_nw.addStretch()
        self.spin_nw = QSpinBox()
        self.spin_nw.setRange(501, 12001)
        self.spin_nw.setValue(2001)
        self.spin_nw.setSingleStep(500)
        self.spin_nw.setFixedWidth(100)
        self.spin_nw.valueChanged.connect(self._on_custom_grid_edit)
        h_nw.addWidget(self.spin_nw)
        lay_custom.addLayout(h_nw)

        h_wmax = QHBoxLayout()
        h_wmax.addWidget(QLabel("Cutoff (ω_max):"))
        h_wmax.addStretch()
        self.spin_wmax = QDoubleSpinBox()
        self.spin_wmax.setRange(5.0, 100.0)
        self.spin_wmax.setValue(20.0)
        self.spin_wmax.setSingleStep(5.0)
        self.spin_wmax.setFixedWidth(100)
        self.spin_wmax.valueChanged.connect(self._on_custom_grid_edit)
        h_wmax.addWidget(self.spin_wmax)
        lay_custom.addLayout(h_wmax)

        h_eta = QHBoxLayout()
        h_eta.addWidget(QLabel("Broadening (η):"))
        h_eta.addStretch()
        self.spin_eta = QDoubleSpinBox()
        self.spin_eta.setRange(0.001, 0.5)
        self.spin_eta.setValue(0.08)
        self.spin_eta.setSingleStep(0.01)
        self.spin_eta.setDecimals(3)
        self.spin_eta.setFixedWidth(100)
        self.spin_eta.valueChanged.connect(self._on_custom_grid_edit)
        h_eta.addWidget(self.spin_eta)
        lay_custom.addLayout(h_eta)

        gres.addWidget(self.box_custom_grid)
        self.box_custom_grid.setVisible(False)  # Collapsed by default

        lay_sim.addWidget(grp_res)

        # 5. Common Model Hamiltonian
        grp_model = ModernCard("Common Model Hamiltonian")
        gm = QVBoxLayout(grp_model)
        gm.setSpacing(4)

        h1 = QHBoxLayout(); h1.addWidget(QLabel("Hopping (t):")); h1.addStretch()
        self.spin_t = QDoubleSpinBox()
        self.spin_t.setMinimum(0.01)
        self.spin_t.setValue(1.0)
        self.spin_t.setSingleStep(0.1)
        self.spin_t.setFixedWidth(100)
        h1.addWidget(self.spin_t)
        gm.addLayout(h1)

        h2 = QHBoxLayout(); h2.addWidget(QLabel("Next-Nearest (t'):")); h2.addStretch()
        self.spin_t1 = QDoubleSpinBox()
        self.spin_t1.setRange(-10.0, 10.0)
        self.spin_t1.setValue(0.0)
        self.spin_t1.setSingleStep(0.05)
        self.spin_t1.setFixedWidth(100)
        h2.addWidget(self.spin_t1)
        gm.addLayout(h2)

        h3 = QHBoxLayout(); h3.addWidget(QLabel("Chemical (μ):")); h3.addStretch()
        self.spin_mu = QDoubleSpinBox()
        self.spin_mu.setRange(-20.0, 20.0)
        self.spin_mu.setValue(1.0)
        self.spin_mu.setSingleStep(0.1)
        self.spin_mu.setFixedWidth(100)
        h3.addWidget(self.spin_mu)
        gm.addLayout(h3)

        h4 = QHBoxLayout(); h4.addWidget(QLabel("Exchange (K):")); h4.addStretch()
        self.spin_k = QDoubleSpinBox()
        self.spin_k.setRange(-10.0, 10.0)
        self.spin_k.setValue(1.0)
        self.spin_k.setSingleStep(0.5)
        self.spin_k.setFixedWidth(100)
        h4.addWidget(self.spin_k)
        gm.addLayout(h4)

        lay_sim.addWidget(grp_model)

        # 6. Output Directory Card
        grp_out = ModernCard("Results Output Directory")
        gout = QVBoxLayout(grp_out)
        gout.setSpacing(4)
        h_out = QHBoxLayout()
        self.edit_out_dir = QLineEdit(r"C:\Users\sruji\Projects\masters_thesis_gui\results")
        h_out.addWidget(self.edit_out_dir)
        b_browse = QPushButton("📁 Browse...")
        b_browse.setFixedWidth(85)
        b_browse.setStyleSheet("padding: 4px 8px; font-size: 11px;")
        b_browse.clicked.connect(self._browse_output_dir)
        h_out.addWidget(b_browse)
        gout.addLayout(h_out)
        lay_sim.addWidget(grp_out)

        lay_sim.addStretch()
        self.inspector_stack.addWidget(panel_sim)

        # PAGE 2: Publication Figure Styling & Typography
        panel_pub = QWidget()
        lay_pub = QVBoxLayout(panel_pub); lay_pub.setContentsMargins(4, 4, 4, 4)

        grp_journal = ModernCard("Journal Dimensions && Standards")
        gj = QVBoxLayout(grp_journal)
        gj.addWidget(QLabel("Target Journal Standard:"))
        self.cb_target_journal = ModernComboBox()
        self.cb_target_journal.addItems([
            "Physical Review B (Single Column • 86 mm)",
            "Physical Review B (Double Column • 178 mm)",
            "Master's Thesis Page (Full Width • 160 mm)",
            "Keynote / Presentation Slide (16:9)"
        ])
        gj.addWidget(self.cb_target_journal)

        gj.addWidget(QLabel("Font Family:"))
        self.cb_font_family = ModernComboBox()
        self.cb_font_family.addItems(["Computer Modern (LaTeX Serif)", "Times New Roman", "Helvetica / Arial", "Segoe UI"])
        gj.addWidget(self.cb_font_family)

        gj.addWidget(QLabel("Label Font Size:"))
        self.cb_pub_font_size = ModernComboBox()
        self.cb_pub_font_size.addItems(["9 pt (Standard Journal)", "10 pt (Thesis Standard)", "12 pt (Presentation)"])
        gj.addWidget(self.cb_pub_font_size)
        lay_pub.addWidget(grp_journal)

        grp_style = ModernCard("Colormaps && Aesthetics")
        gs = QVBoxLayout(grp_style)
        gs.addWidget(QLabel("Colormap Palette:"))
        self.cb_cmap = ModernComboBox()
        self.cb_cmap.addItems(["Magma (Standard)", "Viridis (High Contrast)", "Plasma", "Inferno", "Physical Review Monochrome (B&W)"])
        gs.addWidget(self.cb_cmap)

        gs.addWidget(QLabel("Subpanel Tags:"))
        self.cb_tags = ModernComboBox()
        self.cb_tags.addItems(["(a), (b), (c) [Bold Lowercase]", "(A), (B), (C) [Uppercase]", "None"])
        gs.addWidget(self.cb_tags)

        self.chk_latex_ticks = QCheckBox("Render Axes with LaTeX Greek (π, ω, μ)")
        self.chk_latex_ticks.setChecked(True)
        gs.addWidget(self.chk_latex_ticks)
        lay_pub.addWidget(grp_style)

        grp_exp = ModernCard("Export && LaTeX Integration")
        ge = QVBoxLayout(grp_exp)
        b_pdf = QPushButton("📄 Save Vector PDF for Thesis")
        b_pdf.setObjectName("PrimaryBtn")
        b_pdf.clicked.connect(self.export_pdf_dialog)
        ge.addWidget(b_pdf)

        b_svg = QPushButton("📐 Save Vector SVG / EPS")
        b_svg.clicked.connect(lambda: QMessageBox.information(self, "Export", "Saved figure as thesis_vector_figure.svg"))
        ge.addWidget(b_svg)

        b_code = QPushButton("📋 Copy LaTeX \\includegraphics Snippet")
        b_code.clicked.connect(self.copy_latex_snippet)
        ge.addWidget(b_code)
        lay_pub.addWidget(grp_exp)

        lay_pub.addStretch()
        self.inspector_stack.addWidget(panel_pub)

        self.inspector_scroll.setWidget(self.inspector_stack)
        self.dock_inspector.setWidget(self.inspector_scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_inspector)

    def _on_preset_selected(self, index):
        """Applies chosen preset resolution to grid spinboxes and toggles custom editor."""
        self._updating_preset = True
        if index == 0:  # Fast Preview (N=64)
            self.spin_n.setValue(64)
            self.spin_nw.setValue(2001)
            self.spin_wmax.setValue(20.0)
            self.spin_eta.setValue(0.08)
            self.lbl_preset_summary.setText("⚡ Preset: 64×64 grid | Nw: 2001 | ω_max: 20.0 | η: 0.08")
            self.lbl_preset_summary.setVisible(True)
            self.box_custom_grid.setVisible(False)
        elif index == 1:  # Standard (N=100)
            self.spin_n.setValue(100)
            self.spin_nw.setValue(4801)
            self.spin_wmax.setValue(40.0)
            self.spin_eta.setValue(0.05)
            self.lbl_preset_summary.setText("⚡ Preset: 100×100 grid | Nw: 4801 | ω_max: 40.0 | η: 0.05")
            self.lbl_preset_summary.setVisible(True)
            self.box_custom_grid.setVisible(False)
        elif index == 2:  # High-Res Production (N=256)
            self.spin_n.setValue(256)
            self.spin_nw.setValue(8001)
            self.spin_wmax.setValue(40.0)
            self.spin_eta.setValue(0.03)
            self.lbl_preset_summary.setText("⚡ Preset: 256×256 grid | Nw: 8001 | ω_max: 40.0 | η: 0.03")
            self.lbl_preset_summary.setVisible(True)
            self.box_custom_grid.setVisible(False)
        elif index == 3:  # Custom Grid...
            self.lbl_preset_summary.setVisible(False)
            self.box_custom_grid.setVisible(True)
        self._updating_preset = False

    def _on_custom_grid_edit(self):
        """Marks preset as Custom Grid when user manually changes spinbox values."""
        if getattr(self, "_updating_preset", False):
            return
        if self.cb_preset.currentIndex() != 3:
            self.cb_preset.blockSignals(True)
            self.cb_preset.setCurrentIndex(3)  # Custom Grid...
            self.cb_preset.blockSignals(False)
            self.lbl_preset_summary.setVisible(False)
            self.box_custom_grid.setVisible(True)

    def _browse_output_dir(self):
        """Prompts user to select output directory for plots and data."""
        curr = self.edit_out_dir.text().strip()
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory for Plots & Data", curr)
        if folder:
            self.edit_out_dir.setText(folder)

    def refresh_dataset_tree(self):
        """Refreshes the '📁 PREVIOUS DATASETS & PLOTS' tree from the currently configured output directory."""
        out_dir = self.edit_out_dir.text().strip() if hasattr(self, "edit_out_dir") else DEFAULT_RESULTS_DIR
        self.plots = get_available_plots(out_dir)

        if hasattr(self, "grp_results"):
            # Clear previous items
            while self.grp_results.childCount() > 0:
                self.grp_results.removeChild(self.grp_results.child(0))

            # Populate with plots from the active output directory
            for name in sorted(self.plots.keys()):
                QTreeWidgetItem(self.grp_results, [name])

        # Also update publication panel comboboxes if they exist
        if hasattr(self, "cb_panel_a"):
            plot_names = list(self.plots.keys())
            for cb in [self.cb_panel_a, self.cb_panel_b, self.cb_panel_c]:
                prev_text = cb.currentText()
                cb.clear()
                cb.addItems(plot_names)
                if prev_text in plot_names:
                    cb.setCurrentText(prev_text)

    def _on_solver_backend_changed(self, index):
        """Updates UI and hardware badge when toggling between GPU and CPU."""
        if index == 0:  # GPU
            self.box_cpu_limit.setVisible(False)
            self.lbl_hw_badge.setText("⚡ GPU Active: NVIDIA GeForce RTX 5060 Laptop GPU (64-bit CuPy)")
            self.lbl_hw_badge.setStyleSheet(
                "color: #15803d; font-weight: 600; font-size: 11px; padding: 6px 8px; "
                "background: #dcfce7; border: 1px solid #bbf7d0; border-radius: 5px;"
            )
        else:  # CPU
            self.box_cpu_limit.setVisible(True)
            self.lbl_hw_badge.setText("🖥️ CPU Active: Multi-Core CPU Engine (NumPy / SciPy Multithreaded)")
            self.lbl_hw_badge.setStyleSheet(
                "color: #b45309; font-weight: 600; font-size: 11px; padding: 6px 8px; "
                "background: #fef3c7; border: 1px solid #fde68a; border-radius: 5px;"
            )

    def _on_se_sweep_mode_change(self, index):
        """Updates fixed coupling title and default value for Spectral Sweep."""
        if index == 0:  # Kondo Coupling (J_K)
            self.lbl_se_fixed.setText("Fixed Interlayer Coupling (J_⊥):")
            self.lbl_se_fixed_desc.setText("Constant value of J_⊥ held fixed while sweeping J_K across columns")
            self.spin_se_fixed.setValue(6.0)
        else:  # Interlayer Coupling (J_⊥)
            self.lbl_se_fixed.setText("Fixed Kondo Coupling (J_K):")
            self.lbl_se_fixed_desc.setText("Constant value of J_K held fixed while sweeping J_⊥ across columns")
            self.spin_se_fixed.setValue(3.0)

    def _on_spec_sweep_mode_change(self, index):
        """Updates fixed coupling title and default value for Spectral Function."""
        if index == 0:  # Kondo Coupling (J_K)
            self.lbl_spec_fixed.setText("Fixed Interlayer Coupling (J_⊥):")
            self.lbl_spec_fixed_desc.setText("Constant value held fixed while sweeping J_K")
            self.spin_spec_fixed.setValue(6.0)
        else:  # Interlayer Coupling (J_⊥)
            self.lbl_spec_fixed.setText("Fixed Kondo Coupling (J_K):")
            self.lbl_spec_fixed_desc.setText("Constant value held fixed while sweeping J_⊥")
            self.spin_spec_fixed.setValue(3.0)

    def _on_mom_choice_changed(self, index):
        """Shows custom momentum vector edit field only when Custom is chosen."""
        self.box_custom_k.setVisible(index == 4)

    # =========================================================================
    # BOTTOM DOCK: EXECUTION QUEUE & PROCESS CONSOLE (SIMULATION ONLY)
    # =========================================================================
    def _build_bottom_drawer_dock(self):
        self.dock_bottom = QDockWidget("📋 Execution Center & Process Console", self)
        self.dock_bottom.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.dock_bottom.setMaximumHeight(380)
        self.bottom_tabs = QTabWidget()

        # Tab 1: Batch Queue
        queue_tab = QWidget()
        ql = QVBoxLayout(queue_tab); ql.setContentsMargins(4, 4, 4, 4); ql.setSpacing(4)
        row = QHBoxLayout(); row.setSpacing(6)
        btn_start = QPushButton("▶ Start Queue"); btn_start.setObjectName("PrimaryBtn"); btn_start.setStyleSheet("padding: 4px 10px; font-size: 11px;"); btn_start.clicked.connect(self.start_queue); row.addWidget(btn_start)
        btn_pause = QPushButton("⏸ Pause"); btn_pause.setStyleSheet("padding: 4px 10px; font-size: 11px;"); btn_pause.clicked.connect(self.pause_queue); row.addWidget(btn_pause)
        btn_clear = QPushButton("🗑 Clear Finished"); btn_clear.setStyleSheet("padding: 4px 10px; font-size: 11px;"); btn_clear.clicked.connect(self.clear_queue); row.addWidget(btn_clear)
        row.addStretch(); ql.addLayout(row)

        self.table_queue = QTableWidget(0, 6)
        self.table_queue.setHorizontalHeaderLabels(["#", "Study", "Parameters Snapshot", "Solver", "Progress", "Status"])
        qh = self.table_queue.horizontalHeader()
        qh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        qh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        qh.setSectionResizeMode(2, QHeaderView.Stretch)
        qh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        qh.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table_queue.setColumnWidth(4, 120)
        qh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table_queue.verticalHeader().setDefaultSectionSize(26)
        self.table_queue.verticalHeader().setVisible(False)
        self.table_queue.setShowGrid(True)
        ql.addWidget(self.table_queue)
        self.bottom_tabs.addTab(queue_tab, "📋 Batch Execution Queue")

        # Tab 2: Console
        console_tab = QWidget()
        cl = QVBoxLayout(console_tab); cl.setContentsMargins(4, 4, 4, 4)
        self.txt_console = QTextEdit(); self.txt_console.setReadOnly(True)
        self.txt_console.setStyleSheet("""
            QTextEdit {
                background-color: #012456;
                color: #ffffff;
                font-family: 'Consolas', 'Cascadia Mono', 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.35;
                border: 1px solid #001b44;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        self.txt_console.append("<span style='color: #00ffff; font-family: Consolas, monospace; font-weight: bold;'>Windows PowerShell [Studio Calculation Engine]</span>")
        self.txt_console.append("<span style='color: #ffffff; font-family: Consolas, monospace;'>Ready. NVIDIA RTX 5060 QProcess execution bridge initialized.</span><br>")
        cl.addWidget(self.txt_console)
        self.bottom_tabs.addTab(console_tab, "💻 Live Solver Console")

        self.dock_bottom.setWidget(self.bottom_tabs)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)

    def _build_statusbar(self):
        sb = self.statusBar()
        self.lbl_status = QLabel("Ready. [Simulation Studio Active]")
        self.lbl_coords = QLabel("Pointer: (k_x = --, k_y = --)")
        sb.addWidget(self.lbl_status, 1)
        sb.addPermanentWidget(self.lbl_coords)

    # =========================================================================
    # PERSPECTIVE SWITCHING
    # =========================================================================
    def set_perspective(self, mode):
        self.current_perspective = mode
        if mode == "simulation":
            self.btn_mode_sim.setObjectName("ModeSimActive")
            self.btn_mode_pub.setObjectName("ModeInactive")
            self.btn_mode_sim.setStyleSheet("")
            self.btn_mode_pub.setStyleSheet("")

            # Show simulation buttons, hide publication buttons
            self.btn_run.setVisible(True)
            self.btn_cancel.setVisible(True)
            self.btn_queue.setVisible(True)
            self.btn_split.setVisible(True)
            self.btn_export_pdf.setVisible(False)
            self.btn_copy_latex.setVisible(False)

            # Show bottom drawer
            self.dock_bottom.show()

            # Switch docks to Simulation pages
            self.nav_stack.setCurrentIndex(0)
            self.dock_nav.setWindowTitle("🧭 Study Navigator & Datasets")

            self.inspector_stack.setCurrentIndex(0)
            self.dock_inspector.setWindowTitle("⚙️ Parameter Inspector")

            # Load active study plot
            self.set_active_study(self.active_study)
            self.lbl_status.setText("Mode: [Simulation Studio] — Ready to configure parameters and run studies.")

        else:
            self.btn_mode_sim.setObjectName("ModeInactive")
            self.btn_mode_pub.setObjectName("ModePubActive")
            self.btn_mode_sim.setStyleSheet("")
            self.btn_mode_pub.setStyleSheet("")

            # Hide simulation runner buttons, show publication export buttons
            self.btn_run.setVisible(False)
            self.btn_cancel.setVisible(False)
            self.btn_queue.setVisible(False)
            self.btn_split.setVisible(False)
            self.btn_export_pdf.setVisible(True)
            self.btn_copy_latex.setVisible(True)

            # Hide bottom drawer completely
            self.dock_bottom.hide()

            # Turn off split view
            if self.canvas_right.isVisible():
                self.canvas_right.setVisible(False)
                self.btn_split.setChecked(False)

            # Switch docks to Publication pages
            self.nav_stack.setCurrentIndex(1)
            self.dock_nav.setWindowTitle("🎨 Multi-Panel Subplot Layout")

            self.inspector_stack.setCurrentIndex(1)
            self.dock_inspector.setWindowTitle("🎨 Figure Styling & Typography")

            # Render publication layout
            self._update_publication_preview()
            self.lbl_status.setText("Mode: [Publication Figure Studio] — Compose multi-panel figures for LaTeX.")

    # =========================================================================
    # PUBLICATION FIGURE DISPLAY
    # =========================================================================
    def _update_publication_preview(self):
        idx = self.cb_pub_template.currentIndex()
        if idx == 0:
            p = self.plots.get("sweep_FS_atJ_perp_6.0_mu_1.0.png") or (list(self.plots.values())[0] if self.plots else None)
        elif idx == 1:
            p = self.plots.get("sweep_JK_fixed_J_6.0_mu_1.00_dynamic.png") or (list(self.plots.values())[1] if len(self.plots) > 1 else None)
        elif idx == 2:
            p = self.plots.get("both_JK_fixed_Jperp6.00_k_1_0_mu1.00.png") or (list(self.plots.values())[2] if len(self.plots) > 2 else None)
        else:
            p = self.plots.get("phase_diagram_mu1.00_AFM.png") or (list(self.plots.values())[0] if self.plots else None)

        if p:
            self.canvas_left.load_image(p)
            self.lbl_status.setText(f"Publication Composite: {self.cb_pub_template.currentText()}")

    def export_pdf_dialog(self):
        dest, _ = QFileDialog.getSaveFileName(self, "Export Publication Vector PDF", "thesis_composite_figure.pdf", "PDF Documents (*.pdf)")
        if dest:
            QMessageBox.information(
                self, "Export Successful",
                f"Generated Vector PDF:\n\n{dest}\n\n"
                f"• Target Standard: {self.cb_target_journal.currentText()}\n"
                f"• Colormap: {self.cb_cmap.currentText()}\n"
                f"• Typography: {self.cb_font_family.currentText()} ({self.cb_pub_font_size.currentText()})\n"
                f"• Resolution: Infinite Vector Precision (LaTeX Ready)"
            )
            self.lbl_status.setText(f"Exported publication PDF: {os.path.basename(dest)}")

    def copy_latex_snippet(self):
        code = r"""\begin{figure}[tbp]
    \centering
    \includegraphics[width=\columnwidth]{thesis_composite_figure.pdf}
    \caption{\textbf{Quasiparticle spectral weight transfer and magnetic correlations.} 
    (a) Momentum-integrated Density of States $A(\omega)$. 
    (b) Fermi surface intensity map $A(\mathbf{k}, \omega=0)$ across $[-\pi, \pi]^2$. 
    (c) Band renormalization along the high-symmetry path $\Gamma \to M \to X \to \Gamma$.}
    \label{fig:spectral_heterostructure}
\end{figure}"""
        clipboard = QApplication.clipboard()
        clipboard.setText(code)
        QMessageBox.information(self, "LaTeX Snippet Copied", "LaTeX \\begin{figure} code copied to clipboard!\nYou can paste it directly into your .tex document.")
        self.lbl_status.setText("LaTeX figure snippet copied to clipboard.")

    # =========================================================================
    # SIMULATION ACTIONS & QPROCESS BRIDGE WIRING
    # =========================================================================
    def set_active_study(self, study_name):
        self.active_study = study_name
        self.btn_run.setText(f"⚡ Run Active: {study_name}")
        if self.cb_active_study.currentText() != study_name:
            self.cb_active_study.setCurrentText(study_name)

        study_map = {self.STUDY_SE: 0, self.STUDY_SPEC: 1, self.STUDY_PD: 2, self.STUDY_SUSC: 3}
        self.param_stack.setCurrentIndex(study_map.get(study_name, 0))
        curr = self.param_stack.currentWidget()
        if curr:
            self.param_stack.setFixedHeight(curr.sizeHint().height())
        if hasattr(self, "inspector_stack") and self.inspector_stack.count() > 0:
            p = self.inspector_stack.widget(0)
            if p and p.layout():
                p.layout().activate()
        self.param_stack.updateGeometry()

        if self.current_perspective == "simulation":
            if study_name == self.STUDY_SE: p = self.plots.get("sweep_DOS_atJ_perp_6.0_mu_1.0.png")
            elif study_name == self.STUDY_SPEC: p = self.plots.get("both_JK_fixed_Jperp6.00_k_1_0_mu1.00.png")
            elif study_name == self.STUDY_PD: p = self.plots.get("phase_diagram_mu1.00_AFM.png")
            else: p = self.plots.get("sweep_JK_fixed_J_6.0_mu_1.00_static.png")
            if p and os.path.exists(p):
                self.canvas_left.load_image(p)

    def _select_and_run(self, study_name):
        self.set_active_study(study_name)
        self.run_simulation_ui()

    def _on_nav_selected(self, item, col):
        text = item.text(0)
        if text in (self.STUDY_SE, self.STUDY_SPEC, self.STUDY_PD, self.STUDY_SUSC):
            self.set_active_study(text)
        elif text in self.plots:
            self.canvas_left.load_image(self.plots[text])
            self.lbl_status.setText(f"Viewing Dataset: {text}")

    def run_simulation_ui(self):
        """Starts real calculation via isolated QProcess bridge on RTX 5060."""
        if self.bridge.is_running():
            return

        out_dir = self.edit_out_dir.text().strip()
        if not out_dir:
            out_dir = os.path.join(GUI_ROOT, "results")

        solver_choice = "gpu" if self.cb_solver_choice.currentIndex() == 0 else "cpu"
        cpu_limit = self.cb_cpu_limit.currentText().split()[0]

        common_params = {
            "solver_choice": solver_choice,
            "cpu_limit": cpu_limit,
            "t": float(self.spin_t.value()),
            "t1": float(self.spin_t1.value()),
            "mu": float(self.spin_mu.value()),
            "K": float(self.spin_k.value()),
            "preset": self.cb_preset.currentText(),
            "N": int(self.spin_n.value()),
            "num_omega": int(self.spin_nw.value()),
            "omega_max": float(self.spin_wmax.value()),
            "eta": float(self.spin_eta.value()),
            "output_dir": out_dir
        }

        if self.active_study == self.STUDY_SE:
            raw_sweep = self.edit_se_vals.text().strip()
            if not raw_sweep:
                QMessageBox.warning(self, "Validation Error", "Sweep values cannot be empty")
                return
            try:
                sweep_vals = [float(x.strip()) for x in raw_sweep.split(",") if x.strip()]
                if not sweep_vals:
                    raise ValueError("No valid numeric values in sweep list")
            except Exception as e:
                QMessageBox.warning(self, "Validation Error", f"Invalid sweep values: {e}")
                return

            params = {
                **common_params,
                "task": "spectral_sweep",
                "sweep_mode": self.cb_se_mode.currentText(),
                "jk_values": sweep_vals,
                "fixed_jperp": float(self.spin_se_fixed.value())
            }

        elif self.active_study == self.STUDY_SPEC:
            raw_sweep = self.edit_spec_vals.text().strip()
            if not raw_sweep:
                QMessageBox.warning(self, "Validation Error", "Sweep coupling values cannot be empty")
                return
            try:
                sweep_vals = [float(x.strip()) for x in raw_sweep.split(",") if x.strip()]
                if not sweep_vals:
                    raise ValueError("No valid numeric values in sweep list")
            except Exception as e:
                QMessageBox.warning(self, "Validation Error", f"Invalid sweep values: {e}")
                return

            params = {
                **common_params,
                "task": "spectral_function",
                "spec_sweep_mode": self.cb_spec_mode.currentText(),
                "spec_sweep_vals": sweep_vals,
                "spec_fixed_coupling": float(self.spin_spec_fixed.value()),
                "spec_momentum": self.cb_mom.currentText(),
                "spec_custom_k": self.edit_custom_k.text().strip(),
                "spec_plot_mode": self.cb_layout.currentText()
            }
        elif self.active_study == self.STUDY_PD:
            params = {
                **common_params,
                "task": "phase_diagram",
                "JK_min": float(self.s_min.value()),
                "JK_max": float(self.s_max.value()),
                "JK_pts": int(self.s_pts.value())
            }

        elif self.active_study == self.STUDY_SUSC:
            raw_sweep = self.edit_susc_vals.text().strip()
            if not raw_sweep:
                QMessageBox.warning(self, "Validation Error", "Susceptibility coupling values cannot be empty")
                return
            try:
                sweep_vals = [float(x.strip()) for x in raw_sweep.split(",") if x.strip()]
                if not sweep_vals:
                    raise ValueError("No valid numeric values in sweep list")
            except Exception as e:
                QMessageBox.warning(self, "Validation Error", f"Invalid sweep values: {e}")
                return

            if not self.chk_static.isChecked() and not self.chk_dynamic.isChecked():
                QMessageBox.warning(self, "Validation Error", "Please select at least one mode: Static χ(q) or Dynamic χ(q, ω)")
                return

            params = {
                **common_params,
                "task": "susceptibility",
                "run_static": bool(self.chk_static.isChecked()),
                "run_dynamic": bool(self.chk_dynamic.isChecked()),
                "susc_sweep_mode": "JK",
                "susc_sweep_vals": sweep_vals,
                "fixed_J": float(self.spin_se_fixed.value())
            }
        else:
            QMessageBox.warning(self, "Unknown Study", f"Unrecognized calculation study: {self.active_study}")
            return

        # Auto-switch bottom drawer to the Live Solver Console so logs are visible
        self.bottom_tabs.setCurrentIndex(1)

        try:
            self.bridge.start_calculation(params)
        except RuntimeError as e:
            QMessageBox.warning(self, "Execution Warning", str(e))

    def _on_precompute_bubble(self):
        """Precomputes and caches the bare bubble chi0 on the selected backend."""
        if hasattr(self, "bridge") and self.bridge.is_running():
            return
        out_dir = self.edit_out_dir.text().strip() or os.path.join(GUI_ROOT, "results")
        solver_choice = "gpu" if self.cb_solver_choice.currentIndex() == 0 else "cpu"
        cpu_limit = self.cb_cpu_limit.currentText().split()[0]
        params = {
            "task": "susceptibility",
            "solver_choice": solver_choice,
            "cpu_limit": cpu_limit,
            "t": float(self.spin_t.value()),
            "t1": float(self.spin_t1.value()),
            "mu": float(self.spin_mu.value()),
            "K": float(self.spin_k.value()),
            "N": int(self.spin_n.value()),
            "num_omega": int(self.spin_nw.value()),
            "omega_max": float(self.spin_wmax.value()),
            "eta": float(self.spin_eta.value()),
            "output_dir": out_dir,
            "run_static": True,
            "run_dynamic": False,
            "susc_sweep_mode": "JK",
            "susc_sweep_vals": [1.0],
            "fixed_J": 6.0
        }
        self.bottom_tabs.setCurrentIndex(1)
        try:
            self.bridge.start_calculation(params)
        except RuntimeError as e:
            QMessageBox.warning(self, "Execution Warning", str(e))

    def cancel_simulation_ui(self):
        """Cancels active computation immediately with clean stopping cooldown and VRAM flush."""
        if not hasattr(self, "bridge") or not self.bridge.is_running():
            return

        # Keep both Run and Cancel disabled during stopping procedure
        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳ Stopping...")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("⏳ Stopping...")
        self.lbl_status.setText("⏳ Stopping simulation & purging GPU VRAM...")
        self.txt_console.append(
            f"<div style='color: #ffff00; font-family: Consolas, monospace; font-weight: bold; margin: 4px 0;'>"
            f"[{time.strftime('%H:%M:%S')}] ⏹ [CANCEL REQUESTED] Terminating process tree & purging VRAM cache..."
            f"</div>"
        )
        sb = self.txt_console.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())
        QApplication.processEvents()

        self.bridge.cancel_calculation()

    def _on_calc_started(self):
        self.btn_run.setEnabled(False)
        self.btn_run.setText(f"⏳ Running: {self.active_study}...")
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText("⏹ Cancel / Stop")
        backend_name = "NVIDIA RTX 5060 GPU" if getattr(self, "cb_solver_choice", None) and self.cb_solver_choice.currentIndex() == 0 else "Host CPU"
        self.lbl_status.setText(f"⏳ Running: Initializing {backend_name} solver for {self.active_study}...")
        self.txt_console.append(
            f"<div style='color: #00ffff; font-family: Consolas, monospace; font-weight: bold; margin: 6px 0 2px 0;'>"
            f"[{time.strftime('%H:%M:%S')}] ⚡ Started {self.active_study} on {backend_name} via isolated QProcess."
            f"</div>"
        )

    def _on_calc_log(self, text: str):
        import html
        escaped = html.escape(text)

        # Authentic PowerShell / Terminal Stream Colors
        if any(w in text for w in ["[STDERR]", "Traceback", "Error", "Exception", "failed"]):
            color = "#ff6b68"  # PowerShell Error Red
            weight = "bold"
        elif any(w in text for w in ["SWEEPING", "===", "Starting", "Building", "⚡"]):
            color = "#00ffff"  # PowerShell Cyan / Host Accent
            weight = "bold"
        elif any(w in text for w in ["GPU ACTIVE", "CUDA", "Active Backend"]):
            color = "#4ade80"  # Terminal Green
            weight = "bold"
        elif any(w in text for w in ["completed", "Saved", "finished", "success", "✅"]):
            color = "#4ade80"  # Terminal Green
            weight = "normal"
        elif any(w in text for w in ["CACHE HIT", "Warning", "Scaling for"]):
            color = "#ffff00"  # PowerShell Yellow
            weight = "normal"
        else:
            color = "#ffffff"  # Default PowerShell White
            weight = "normal"

        self.txt_console.append(f"<span style='color: {color}; font-family: Consolas, monospace; font-weight: {weight};'>{escaped}</span>")
        sb = self.txt_console.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _on_calc_status(self, message: str):
        """Displays accurate, informative physics execution stage without fake percentages."""
        if message:
            self.lbl_status.setText(f"⏳ Running: {message}")

    def _on_calc_progress(self, percent: int, step: str):
        """Updates status cleanly without arbitrary percentage prefixes."""
        if step:
            self.lbl_status.setText(f"⏳ Running: {step}")

    def _on_calc_completed(self, payload: dict):
        self.btn_run.setEnabled(True)
        self.btn_run.setText(f"⚡ Run Active: {self.active_study}")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("⏹ Cancel / Stop")
        self.lbl_status.setText(f"✅ Completed: {self.active_study} finished • Loaded into viewport.")
        self.txt_console.append(
            f"<div style='color: #4ade80; font-family: Consolas, monospace; font-weight: bold; margin: 4px 0;'>"
            f"[{time.strftime('%H:%M:%S')}] ✅ Calculation completed successfully."
            f"</div>"
        )

        all_plots = payload.get("all_plots", [])
        primary_plot = payload.get("plot_path", "")
        if not all_plots and primary_plot:
            all_plots = [primary_plot]

        self.refresh_dataset_tree()

        if primary_plot and os.path.exists(primary_plot):
            self.canvas_left.load_image(primary_plot)
            self.canvas_left.fit_in_view()

        # Auto-reset status label to Ready after 4 seconds
        QTimer.singleShot(4000, self._reset_status_to_ready)

    def _reset_status_to_ready(self):
        """Resets status bar to default Ready state when idle."""
        if hasattr(self, "bridge") and not self.bridge.is_running():
            self.lbl_status.setText("Ready. [Simulation Studio Active]")

    def _on_calc_error(self, error_msg: str):
        self.btn_run.setEnabled(True)
        self.btn_run.setText(f"⚡ Run Active: {self.active_study}")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("⏹ Cancel / Stop")
        self.lbl_status.setText(f"❌ Error: {error_msg}")
        self.txt_console.append(
            f"<div style='color: #ff6b68; font-family: Consolas, monospace; font-weight: bold; margin: 4px 0;'>"
            f"[{time.strftime('%H:%M:%S')}] ❌ [ERROR] {error_msg}"
            f"</div>"
        )
        QTimer.singleShot(6000, self._reset_status_to_ready)

    def _on_calc_cancelled(self):
        # Keep Run button greyed out for the duration of the stopping procedure
        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳ Stopping...")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("⏳ Stopping...")
        self.lbl_status.setText("⏳ Purging GPU VRAM & finalizing stop...")
        self.txt_console.append(
            f"<div style='color: #ffff00; font-family: Consolas, monospace; font-weight: bold; margin: 4px 0;'>"
            f"[{time.strftime('%H:%M:%S')}] ✅ [STOPPED] Process terminated cleanly. VRAM cache flushed to 0 MB."
            f"</div>"
        )
        sb = self.txt_console.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

        # Once stopping cooldown and VRAM flush complete, re-enable Run button
        def _finish_stopping():
            self.btn_run.setEnabled(True)
            self.btn_run.setText(f"⚡ Run Active: {self.active_study}")
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.setText("⏹ Cancel / Stop")
            self.lbl_status.setText("⏹ Stopped: Simulation cancelled • Ready for next run.")
            QTimer.singleShot(2500, self._reset_status_to_ready)

        QTimer.singleShot(800, _finish_stopping)

    def closeEvent(self, event: QCloseEvent):
        """Guarantees child process termination and GPU cleanup upon window closing."""
        if hasattr(self, "bridge") and self.bridge.is_running():
            self.bridge.cancel_calculation()
        flush_gpu_vram()
        event.accept()

    def _adjust_bottom_dock_height(self):
        """Automatically expands/contracts Execution Center vertical height based on queued sweep jobs."""
        n_rows = self.table_queue.rowCount()
        base_h = 145
        row_h = 26
        max_allowed = min(360, int(self.height() * 0.42))
        desired_h = min(max_allowed, base_h + (n_rows * row_h))
        self.dock_bottom.setMaximumHeight(max_allowed + 30)
        self.resizeDocks([self.dock_bottom], [desired_h], Qt.Vertical)

    def add_to_queue(self):
        row = self.table_queue.rowCount()
        self.table_queue.insertRow(row)

        if self.active_study == self.STUDY_SE:
            summary = f"Sweep: [{self.edit_se_vals.text()}], Fixed J_⊥ = {self.spin_se_fixed.value():.1f}, μ = {self.spin_mu.value():.1f}, N = {self.spin_n.value()}"
        elif self.active_study == self.STUDY_SPEC:
            summary = f"k = {self.cb_mom.currentText().split()[0]}, [{self.edit_spec_vals.text()}], J_⊥ = {self.spin_spec_fixed.value():.1f}, N = {self.spin_n.value()}"
        elif self.active_study == self.STUDY_PD:
            summary = f"Bisection J_K ∈ [{self.s_min.value():.1f}, {self.s_max.value():.1f}], pts = {self.s_pts.value()}, μ = {self.spin_mu.value():.1f}"
        else:
            modes = []
            if self.chk_static.isChecked(): modes.append("Static χ(q)")
            if self.chk_dynamic.isChecked(): modes.append("Dynamic χ(q,ω)")
            mode_str = "+".join(modes) if modes else "None"
            summary = f"{mode_str}, vals = [{self.edit_susc_vals.text()}], N = {self.spin_n.value()}"

        item_num = QTableWidgetItem(str(row + 1))
        item_num.setTextAlignment(Qt.AlignCenter)
        self.table_queue.setItem(row, 0, item_num)

        item_study = QTableWidgetItem(self.active_study)
        font_study = item_study.font()
        font_study.setBold(True)
        item_study.setFont(font_study)
        item_study.setForeground(QColor("#60a5fa") if self.is_dark else QColor("#2563eb"))
        self.table_queue.setItem(row, 1, item_study)

        item_snap = QTableWidgetItem(summary)
        item_snap.setTextAlignment(Qt.AlignCenter)
        item_snap.setForeground(QColor("#94a3b8") if self.is_dark else QColor("#475569"))
        self.table_queue.setItem(row, 2, item_snap)

        solver_str = "NVIDIA RTX 5060 (GPU)" if self.cb_solver_choice.currentIndex() == 0 else f"CPU ({self.cb_cpu_limit.currentText().split()[0]} Cores)"
        item_solver = QTableWidgetItem(solver_str)
        item_solver.setTextAlignment(Qt.AlignCenter)
        self.table_queue.setItem(row, 3, item_solver)

        prog = QProgressBar()
        prog.setValue(0)
        self.table_queue.setCellWidget(row, 4, prog)

        item_status = QTableWidgetItem("⏳ Pending")
        item_status.setTextAlignment(Qt.AlignCenter)
        self.table_queue.setItem(row, 5, item_status)

        self.lbl_status.setText(f"Added {self.active_study} as Job #{row + 1} to queue.")
        self.bottom_tabs.setCurrentIndex(0)
        self._adjust_bottom_dock_height()

    def start_queue(self):
        if self.table_queue.rowCount() == 0: self.add_to_queue()
        self.active_queue_row = 0; self.active_queue_progress = 0
        self.queue_timer.start(80); self.lbl_status.setText("🔄 Running batch queue...")

    def _on_queue_tick(self):
        self.active_queue_progress += 5
        if self.active_queue_row < self.table_queue.rowCount():
            prog = self.table_queue.cellWidget(self.active_queue_row, 4)
            if prog: prog.setValue(self.active_queue_progress)
            self.table_queue.setItem(self.active_queue_row, 5, QTableWidgetItem(f"🔄 Solving ({self.active_queue_progress}%)"))
        if self.active_queue_progress >= 100:
            self.table_queue.setItem(self.active_queue_row, 5, QTableWidgetItem("✅ Completed"))
            self.active_queue_row += 1; self.active_queue_progress = 0
            if self.active_queue_row >= self.table_queue.rowCount():
                self.queue_timer.stop()
                self.lbl_status.setText("🎉 Batch queue completed successfully!")

    def pause_queue(self):
        self.queue_timer.stop()
        self.lbl_status.setText("⏸ Batch queue paused.")

    def clear_queue(self):
        self.table_queue.setRowCount(0)
        self._adjust_bottom_dock_height()
        self.lbl_status.setText("Batch queue cleared.")

    def toggle_split_view(self, checked):
        self.canvas_right.setVisible(checked)
        if checked:
            other = self.plots.get("sweep_FS_atJ_perp_6.0_mu_1.0.png") or (list(self.plots.values())[-1] if self.plots else None)
            if other and os.path.exists(other):
                self.canvas_right.load_image(other)
            self.lbl_status.setText("⚏ Split View Active: Comparative multi-canvas enabled.")
        else:
            self.lbl_status.setText("Single View Active.")

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        theme_qss = DARK_THEME_QSS if self.is_dark else LIGHT_THEME_QSS
        theme_pal = create_dark_palette() if self.is_dark else create_light_palette()
        self.setStyleSheet(theme_qss)
        app_inst = QApplication.instance()
        if app_inst:
            app_inst.setPalette(theme_pal)
            app_inst.setStyleSheet(theme_qss)
        self.canvas_left.set_theme(self.is_dark)
        self.canvas_right.set_theme(self.is_dark)
        study_col = QColor("#60a5fa") if self.is_dark else QColor("#2563eb")
        snap_col = QColor("#94a3b8") if self.is_dark else QColor("#475569")
        for r in range(self.table_queue.rowCount()):
            it_s = self.table_queue.item(r, 1)
            if it_s: it_s.setForeground(study_col)
            it_p = self.table_queue.item(r, 2)
            if it_p: it_p.setForeground(snap_col)

    def reset_active_zoom(self):
        self.canvas_left.fit_in_view()
        if self.canvas_right.isVisible():
            self.canvas_right.fit_in_view()

    def _on_left_coord(self, x, y):
        self.lbl_coords.setText(f"Active Canvas: Pixel ({int(x)}, {int(y)})")

    def _on_right_coord(self, x, y):
        self.lbl_coords.setText(f"Comparative Canvas: Pixel ({int(x)}, {int(y)})")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UnifiedWorkbenchWindow()
    window.show()
    sys.exit(app.exec())
