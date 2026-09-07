"""Many-Body Studio [Beta v1 - PySide6 UI Architecture]
Pure Frontend Architecture wired to isolated QProcess CalculationBridge.
Features Unified Simulation Studio with Dual Analytical Viewports:
1. [ 📊 Plot Viewer ]:
   - Hardware-accelerated CAD zoom/pan canvas (QGraphicsView).
   - Side-by-side comparison splitter and high-resolution export.
2. [ ⚡ Interactive Plots ]:
   - Real-time 60 FPS Brillouin zone probe, Fermi surface slicing, and dispersion.
   - Dynamic parameter tuning with instant foundation caching.
(Note: Legacy standalone Figure Composer workspace was scrapped in favor of direct analytical viewports).
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
    QMenu, QStackedWidget, QCheckBox, QScrollArea, QFrame, QSizePolicy,
)

from pyside6_studio.theme import LIGHT_THEME_QSS, DARK_THEME_QSS, create_light_palette, create_dark_palette
from pyside6_studio.canvas import InteractivePlotCanvas
from pyside6_studio.backend.bridge import CalculationBridge
from pyside6_studio.backend.vram_cleaner import flush_gpu_vram
from pyside6_studio.core.hardware import get_hardware_info
from pyside6_studio.core.cache_manager import (
    normalize_results_dir,
    check_cache_status,
    get_cache_stats,
    purge_cache
)
from pyside6_studio.core import config
from pyside6_studio.widgets.dataset_explorer import DatasetExplorerWidget
from pyside6_studio.widgets.data_plotter import InteractiveDataCanvas, VectorExportDialog
from pyside6_studio.widgets.gallery_browser import PlotGalleryWidget
from pyside6_studio.widgets.interactive_plots import InteractivePlotsWidget
from pyside6_studio.widgets.interactive_mode_nav import InteractiveModeNavWidget
from pyside6_studio.widgets.job_queue import JobQueueWidget
from pyside6_studio.core.metadata import parse_plot_metadata
from pyside6_studio.widgets.cache_manager_dialog import CacheManagerDialog
from pyside6_studio.main_window_theme import update_bottom_dock_theme, update_statusbar_theme, toggle_main_window_theme
from pyside6_studio.widgets.study_forms.spectral_form import build_spectral_form
from pyside6_studio.widgets.study_forms.self_energy_form import build_spectral_function_form
from pyside6_studio.widgets.study_forms.phase_diagram_form import build_phase_diagram_form
from pyside6_studio.widgets.study_forms.susceptibility_form import build_susceptibility_form
from pyside6_studio.widgets.study_forms.conductivity_form import build_conductivity_form

if getattr(sys, 'frozen', False):
    DEFAULT_RESULTS_DIR = os.path.join(os.path.dirname(sys.executable), "results")
else:
    DEFAULT_RESULTS_DIR = getattr(config, "DEFAULT_RESULTS_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results"))


def get_available_plots(output_dir=None):
    """
    Scans the configured output directory for real simulation plots.
    Inspects output_dir/plots (or output_dir directly), filtering strictly for physics observables.
    """
    plots = {}
    target_dir = output_dir or DEFAULT_RESULTS_DIR
    results_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(target_dir)

    if os.path.isdir(plots_dir):
        for f in glob.glob(os.path.join(plots_dir, "*.png")):
            bname = os.path.basename(f)
            if bname.startswith(("sweep_", "both_", "spectral_", "phase_", "chi_")):
                plots[bname] = os.path.normpath(f)

    return plots


class ModernCard(QGroupBox):
    """QGroupBox that allows its width to shrink down gracefully without long title text inflating minimumSizeHint."""
    def __init__(self, title="", parent=None):
        clean_title = title.replace("&", "&&") if ("&" in title and "&&" not in title) else title
        super().__init__(clean_title, parent)

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
    STUDY_COND = "🔌 Electrical Conductivity Sweep σ(ω)"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Many-Body Studio")
        from pyside6_studio.core.icon_utils import get_app_icon
        app_icon = get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self.resize(1440, 900)
        self.setMinimumSize(1024, 600)

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
        self.current_view_plot_path = None
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

        # Simulation Queue and Batch Execution
        self.queued_param_list = []
        self.active_queue_row = -1
        self._active_job_info = None
        self._last_progress_pct = 0
        self._last_progress_step = ""

        self._build_toolbar()
        self._build_central_workspace()
        self._build_navigator_dock()
        self._build_inspector_dock()
        self._build_bottom_drawer_dock()
        self._build_statusbar()

        self.dock_nav.setMinimumWidth(240)
        self.dock_nav.setMaximumWidth(320)

        # Ensure docks start with proper comfortable widths & dynamic bottom height, defaulting to Interactive Plots
        self._adjust_bottom_dock_height()
        self.resizeDocks([self.dock_nav, self.dock_inspector], [260, 350], Qt.Horizontal)
        QTimer.singleShot(0, lambda: (
            self._adjust_bottom_dock_height(),
            self.resizeDocks([self.dock_nav, self.dock_inspector], [260, 350], Qt.Horizontal),
            self.set_canvas_mode(1)
        ))

        # Setup Smart Cache invalidation debounced timer
        self.cache_timer = QTimer(self)
        self.cache_timer.setSingleShot(True)
        self.cache_timer.setInterval(120)
        self.cache_timer.timeout.connect(self._update_cache_badge)
        self._wire_cache_check_signals()

        # Wire Output Directory text change to dynamically re-populate datasets & plots
        self.edit_out_dir.textChanged.connect(self.refresh_dataset_tree)
        self.refresh_dataset_tree()

        # Initialize default state - default directly to Interactive Plots viewport
        self.set_active_study(self.STUDY_SE)
        self.set_perspective("simulation")
        self.set_canvas_mode(1)
        self._update_cache_badge()
        self._update_execution_buttons(is_running=False)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_docks_initially_sized", False):
            self._docks_initially_sized = True
            self._adjust_bottom_dock_height()
            self.resizeDocks([self.dock_nav, self.dock_inspector], [260, 350], Qt.Horizontal)
            self.set_canvas_mode(1)

    # =========================================================================
    # TOOLBAR & MODE SWITCHER
    # =========================================================================
    def _build_toolbar(self):
        self.tb = QToolBar("Main Controls", self)
        self.tb.setMovable(False)
        self.addToolBar(self.tb)

        # 1. Viewport Switcher Segmented Control
        vp_container = QWidget()
        vp_lay = QHBoxLayout(vp_container)
        vp_lay.setContentsMargins(0, 0, 0, 0)
        vp_lay.setSpacing(4)

        lbl_vp = QLabel("Viewport:")
        lbl_vp.setObjectName("ToolbarVpLabel")
        vp_lay.addWidget(lbl_vp)

        self.btn_canvas_lab = QPushButton("🔬 Interactive Plots")
        self.btn_canvas_lab.setObjectName("BtnVpInteractive")
        self.btn_canvas_lab.setCheckable(True)
        self.btn_canvas_lab.setChecked(True)
        self.btn_canvas_lab.setCursor(Qt.PointingHandCursor)
        self.btn_canvas_lab.clicked.connect(lambda: self.set_canvas_mode(1))
        self.btn_canvas_interactive = self.btn_canvas_lab
        vp_lay.addWidget(self.btn_canvas_lab)

        self.btn_canvas_figure = QPushButton("📊 Plot Viewer")
        self.btn_canvas_figure.setObjectName("BtnVpViewer")
        self.btn_canvas_figure.setCheckable(True)
        self.btn_canvas_figure.setChecked(False)
        self.btn_canvas_figure.setCursor(Qt.PointingHandCursor)
        self.btn_canvas_figure.clicked.connect(lambda: self.set_canvas_mode(0))
        self.btn_canvas_plot = self.btn_canvas_figure
        vp_lay.addWidget(self.btn_canvas_figure)

        self.tb.addWidget(vp_container)

        # 2. Expanding Spacer pushes execution controls directly above Simulation Setup dock
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.tb.addWidget(spacer)

        # 3. Simulation Setup Execution Actions (Right side above Simulation Setup Dock)
        self.btn_run = QToolButton()
        self.btn_run.setObjectName("BtnRun")
        self.btn_run.setText("▶ Run Study")
        self.btn_run.setToolTip(f"Run {self.active_study} (Click arrow for other studies)")
        self.btn_run.setPopupMode(QToolButton.MenuButtonPopup)
        self.btn_run.setFixedWidth(145)
        self.btn_run.clicked.connect(self.run_simulation_ui)

        menu_run = QMenu(self.btn_run)
        menu_run.addAction(self.STUDY_SE).triggered.connect(lambda: self._select_and_run(self.STUDY_SE))
        menu_run.addAction(self.STUDY_SPEC).triggered.connect(lambda: self._select_and_run(self.STUDY_SPEC))
        menu_run.addAction(self.STUDY_PD).triggered.connect(lambda: self._select_and_run(self.STUDY_PD))
        menu_run.addAction(self.STUDY_SUSC).triggered.connect(lambda: self._select_and_run(self.STUDY_SUSC))
        menu_run.addAction(self.STUDY_COND).triggered.connect(lambda: self._select_and_run(self.STUDY_COND))
        self.btn_run.setMenu(menu_run)
        self.action_run = self.tb.addWidget(self.btn_run)

        # Dedicated Cancel / Stop button
        self.btn_cancel = QPushButton("⏹ Stop")
        self.btn_cancel.setObjectName("BtnCancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setFixedWidth(90)
        self.btn_cancel.clicked.connect(self.cancel_simulation_ui)
        self.action_cancel = self.tb.addWidget(self.btn_cancel)

        self.btn_queue = QPushButton("➕ Queue")
        self.btn_queue.setObjectName("BtnQueue")
        self.btn_queue.setToolTip("Add current active study parameters to the batch execution queue")
        self.btn_queue.setFixedWidth(85)
        self.btn_queue.clicked.connect(self.add_to_queue)
        self.action_queue = self.tb.addWidget(self.btn_queue)

        self.btn_split = QPushButton("⚏ Split View (Compare)", parent=self)
        self.btn_split.setCheckable(True)
        self.btn_split.toggled.connect(self.toggle_split_view)
        self.btn_split.setVisible(False)
        self.action_split = None

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
        layout.setSpacing(4)

        self.central_view_stack = QStackedWidget()

        # Page 0: CAD Plot Viewer Canvas (QGraphicsView)
        self.figure_view_container = QWidget()
        fig_lay = QVBoxLayout(self.figure_view_container)
        fig_lay.setContentsMargins(0, 0, 0, 0)
        fig_lay.setSpacing(4)

        # Action bar for Plot Viewer (matching the old GUI baseline)
        fig_toolbar = QHBoxLayout()
        fig_toolbar.setContentsMargins(4, 2, 4, 2)
        fig_toolbar.setSpacing(6)

        fig_toolbar.addWidget(QLabel("Active Plot:"))
        self.cb_active_plot = ModernComboBox()
        self.cb_active_plot.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_active_plot.setMinimumContentsLength(14)
        self.cb_active_plot.setMinimumWidth(140)
        self.cb_active_plot.currentIndexChanged.connect(self._on_active_plot_changed)
        fig_toolbar.addWidget(self.cb_active_plot)

        btn_style = "QPushButton { padding: 3px 8px; font-size: 11px; font-weight: 500; }"

        btn_fit_fig = QPushButton("Reset")
        btn_fit_fig.setToolTip("Reset zoom and restore image within viewport")
        btn_fit_fig.setStyleSheet(btn_style)
        btn_fit_fig.clicked.connect(self.reset_active_zoom)
        fig_toolbar.addWidget(btn_fit_fig)

        btn_copy_fig = QPushButton("Copy")
        btn_copy_fig.setToolTip("Copy current image to clipboard")
        btn_copy_fig.setStyleSheet(btn_style)
        btn_copy_fig.clicked.connect(self.copy_current_plot_to_clipboard)
        fig_toolbar.addWidget(btn_copy_fig)

        btn_export_fig = QPushButton("Export")
        btn_export_fig.setToolTip("Export plot image to disk")
        btn_export_fig.setStyleSheet(btn_style)
        btn_export_fig.clicked.connect(self.export_current_plot)
        fig_toolbar.addWidget(btn_export_fig)

        btn_open_fig = QPushButton("Folder")
        btn_open_fig.setToolTip("Open output directory in file explorer")
        btn_open_fig.setStyleSheet(btn_style)
        btn_open_fig.clicked.connect(self.open_output_folder)
        fig_toolbar.addWidget(btn_open_fig)

        fig_toolbar.addStretch()
        fig_lay.addLayout(fig_toolbar)

        self.view_splitter = QSplitter(Qt.Horizontal)
        self.canvas_left = InteractivePlotCanvas()
        self.canvas_left.coord_changed.connect(self._on_left_coord)
        self.view_splitter.addWidget(self.canvas_left)

        self.canvas_right = InteractivePlotCanvas()
        self.canvas_right.coord_changed.connect(self._on_right_coord)
        self.canvas_right.setVisible(False)
        self.view_splitter.addWidget(self.canvas_right)

        fig_lay.addWidget(self.view_splitter, 1)
        self.central_view_stack.addWidget(self.figure_view_container)

        # Page 1: Interactive Plots (Real-time 60 FPS BZ probe, Fermi surfaces & continuous J_K scaling)
        out_dir = self.edit_out_dir.text().strip() if hasattr(self, "edit_out_dir") else DEFAULT_RESULTS_DIR
        self.interactive_plots = InteractivePlotsWidget(out_dir=out_dir, parent=self)
        self.analytical_lab = self.interactive_plots  # Alias for backward compatibility
        self.live_lab = self.interactive_plots        # Alias for backward compatibility
        self.interactive_plots.sig_send_to_sweeper.connect(self._on_receive_interactive_parameters)
        self.interactive_plots.cb_experiment.currentIndexChanged.connect(self._on_interactive_experiment_changed)
        self.central_view_stack.addWidget(self.interactive_plots)
        self.central_view_stack.setCurrentIndex(1)

        layout.addWidget(self.central_view_stack, 1)
        self.setCentralWidget(self.central_container)

    def set_canvas_mode(self, mode_idx: int):
        """Switches between Plot Viewer (0) and Interactive Plots (1)."""
        self.central_view_stack.setCurrentIndex(mode_idx)
        self.btn_canvas_figure.setChecked(mode_idx == 0)
        self.btn_canvas_lab.setChecked(mode_idx == 1)
        if hasattr(self, "action_split") and self.action_split:
            self.action_split.setVisible(mode_idx == 0)
        if hasattr(self, "nav_stack") and self.nav_stack.count() > 1:
            if mode_idx == 0:
                self.nav_stack.setCurrentIndex(0)
                self.dock_nav.setWindowTitle("🖼️ Plot Gallery Browser")
            else:
                self.nav_stack.setCurrentIndex(1)
                self.dock_nav.setWindowTitle("🔬 Interactive Modes")

    def copy_current_plot_to_clipboard(self):
        if hasattr(self, "current_view_plot_path") and self.current_view_plot_path and os.path.exists(self.current_view_plot_path):
            pix = QPixmap(self.current_view_plot_path)
            if not pix.isNull():
                QApplication.clipboard().setPixmap(pix)
                self.lbl_status.setText("Current plot image copied to clipboard!")
                return
        if hasattr(self, "canvas_left") and self.canvas_left.current_pixmap:
            QApplication.clipboard().setPixmap(self.canvas_left.current_pixmap)
            self.lbl_status.setText("Current plot image copied to clipboard!")

    def open_output_folder(self):
        out_dir = self.edit_out_dir.text().strip() if hasattr(self, "edit_out_dir") else DEFAULT_RESULTS_DIR
        results_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(out_dir)
        target = plots_dir if os.path.isdir(plots_dir) else results_dir
        if os.path.isdir(target):
            try:
                os.startfile(target)
            except Exception as e:
                QMessageBox.warning(self, "Open Folder Error", str(e))

    def _on_active_plot_changed(self, index: int):
        if not hasattr(self, "cb_active_plot") or index < 0:
            return
        plot_path = self.cb_active_plot.itemData(index)
        if plot_path and os.path.exists(plot_path):
            self.current_view_plot_path = plot_path
            self.canvas_left.load_image(plot_path)
            self.lbl_status.setText(f"Viewing Plot: {os.path.basename(plot_path)}")
            if hasattr(self, "gallery"):
                self.gallery.select_plot(plot_path)

    # =========================================================================
    # LEFT DOCK: PLOT GALLERY BROWSER & INTERACTIVE MODE NAV
    # =========================================================================
    def _build_navigator_dock(self):
        self.dock_nav = QDockWidget("🖼️ Plot Gallery Browser", self)
        self.dock_nav.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock_nav.setMinimumWidth(240)

        self.nav_stack = QStackedWidget()

        # Page 0: Visual Plot Gallery Browser (for Plot Viewer)
        out_dir = self.edit_out_dir.text().strip() if hasattr(self, "edit_out_dir") else DEFAULT_RESULTS_DIR
        self.gallery = PlotGalleryWidget(out_dir=out_dir, parent=self)
        self.gallery.sig_plot_selected.connect(self._on_gallery_plot_selected)
        self.nav_stack.addWidget(self.gallery)

        # Page 1: Interactive Mode Navigation Cards (for Interactive Plots)
        self.interactive_mode_nav = InteractiveModeNavWidget(parent=self)
        self.interactive_mode_nav.sig_mode_selected.connect(self._on_interactive_mode_nav_selected)
        self.nav_stack.addWidget(self.interactive_mode_nav)
        self.nav_stack.setCurrentIndex(1)
        self.dock_nav.setWindowTitle("🔬 Interactive Modes")

        self.dock_nav.setWidget(self.nav_stack)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_nav)

    def _on_interactive_mode_nav_selected(self, mode_id: str):
        """Switches the active experiment in InteractivePlotsWidget when user clicks a left dock card."""
        if hasattr(self, "interactive_plots") and hasattr(self.interactive_plots, "mode_order"):
            if mode_id in self.interactive_plots.mode_order:
                idx = self.interactive_plots.mode_order.index(mode_id)
                if self.interactive_plots.cb_experiment.currentIndex() != idx:
                    self.interactive_plots.cb_experiment.setCurrentIndex(idx)

    def _on_interactive_experiment_changed(self, idx: int):
        """Synchronizes the left dock card selection when the experiment dropdown changes."""
        if hasattr(self, "interactive_mode_nav") and hasattr(self, "interactive_plots") and hasattr(self.interactive_plots, "mode_order"):
            if 0 <= idx < len(self.interactive_plots.mode_order):
                mode_id = self.interactive_plots.mode_order[idx]
                self.interactive_mode_nav.set_selected_mode(mode_id)

    def _on_gallery_plot_selected(self, plot_path: str):
        self.current_view_plot_path = plot_path

        self.set_canvas_mode(0)
        self.canvas_left.load_image(plot_path)
        self.lbl_status.setText(f"Viewing Plot: {os.path.basename(plot_path)}")

        # Synchronize active plot combobox
        if hasattr(self, "cb_active_plot"):
            for i in range(self.cb_active_plot.count()):
                if self.cb_active_plot.itemData(i) == plot_path:
                    self.cb_active_plot.blockSignals(True)
                    self.cb_active_plot.setCurrentIndex(i)
                    self.cb_active_plot.blockSignals(False)
                    break

    def _on_explorer_compare(self, path: str):
        self.set_canvas_mode(0)
        self.btn_split.setChecked(True)
        if path.lower().endswith((".png", ".pdf", ".svg")):
            self.canvas_right.load_image(path)
        self.lbl_status.setText(f"Comparison View: Loaded {os.path.basename(path)}")

    # =========================================================================
    # RIGHT DOCK: SIMULATION SETUP (WITH VERTICAL SCROLL AREA)
    # =========================================================================
    def _build_inspector_dock(self):
        self.dock_inspector = QDockWidget("⚙️ Simulation Setup", self)
        self.dock_inspector.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock_inspector.setMinimumWidth(320)

        # Wrap in QScrollArea so cards never overlap or clip beneath the bottom execution center
        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setFrameShape(QFrame.NoFrame)
        self.inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.inspector_scroll.setMinimumWidth(240)

        self.inspector_stack = QStackedWidget()

        # PAGE 1: Simulation Setup
        panel_sim = QWidget()
        lay_sim = QVBoxLayout(panel_sim)
        lay_sim.setContentsMargins(4, 4, 4, 4)
        lay_sim.setSpacing(5)

        # 1. Active Study Switcher
        grp_selector = ModernCard("Active Calculation Study")
        sel_lay = QVBoxLayout(grp_selector)
        self.cb_active_study = ModernComboBox()
        self.cb_active_study.setObjectName("StudyDropdown")
        self.cb_active_study.addItems([self.STUDY_SE, self.STUDY_SPEC, self.STUDY_PD, self.STUDY_SUSC, self.STUDY_COND])
        self.cb_active_study.currentTextChanged.connect(self.set_active_study)
        sel_lay.addWidget(self.cb_active_study)
        lay_sim.addWidget(grp_selector)

        # 1b. Computation & Cache Status Card
        grp_cache = ModernCard("Computation & Cache Status")
        gc = QVBoxLayout(grp_cache)
        gc.setSpacing(6)

        self.lbl_cache_badge = QLabel("Checking Cache...")
        self.lbl_cache_badge.setStyleSheet(
            "padding: 6px 10px; border-radius: 6px; font-weight: 600; font-size: 11px; "
            "background-color: rgba(100, 116, 139, 0.12); color: #64748b; border: 1px solid rgba(100, 116, 139, 0.35);"
        )
        self.lbl_cache_badge.setWordWrap(True)
        gc.addWidget(self.lbl_cache_badge)

        h_cache_ctrl = QHBoxLayout()
        self.chk_force_recompute = QCheckBox("Force Recompute")
        self.chk_force_recompute.setToolTip("Bypass results/cache/ and recalculate all convolutions from scratch (will take longer).")
        self.chk_force_recompute.stateChanged.connect(self._schedule_cache_check)
        h_cache_ctrl.addWidget(self.chk_force_recompute)

        self.btn_cache_mgr = QPushButton("🧹 Cache (0 MB)")
        self.btn_cache_mgr.setFixedWidth(125)
        self.btn_cache_mgr.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        self.btn_cache_mgr.clicked.connect(self._open_cache_manager)
        h_cache_ctrl.addWidget(self.btn_cache_mgr)
        gc.addLayout(h_cache_ctrl)

        lay_sim.addWidget(grp_cache)

        # 2. Study-specific stacked parameters
        self.param_stack = DynamicStackedWidget()
        self.param_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        self.param_stack.addWidget(build_spectral_form(self))

        self.param_stack.addWidget(build_spectral_function_form(self))

        self.param_stack.addWidget(build_phase_diagram_form(self))

        self.param_stack.addWidget(build_susceptibility_form(self))

        self.param_stack.addWidget(build_conductivity_form(self))

        lay_sim.addWidget(self.param_stack)

        # 3. Compute & Solver Backend Card (Matching Original GUI Architecture)
        grp_solver = ModernCard("Compute && Solver Backend")
        gsolv = QVBoxLayout(grp_solver)
        gsolv.setSpacing(4)

        h_solv = QHBoxLayout()
        h_solv.addWidget(QLabel("Solver Backend:"))
        self.cb_solver_choice = ModernComboBox()
        hw_info = get_hardware_info()
        if hw_info.get("is_gpu"):
            dev_name = hw_info.get("name", "NVIDIA GPU")
            self.cb_solver_choice.addItems([
                f"CUDA GPU ({dev_name})",
                "CPU 64-bit (NumPy / SciPy)"
            ])
            self.cb_solver_choice.setCurrentIndex(0)
        else:
            self.cb_solver_choice.addItems([
                "CPU 64-bit (NumPy / SciPy)",
                "CUDA GPU (Unavailable - No GPU / CuPy)"
            ])
            self.cb_solver_choice.setCurrentIndex(0)
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
        self.lbl_hw_badge = QLabel()
        self.lbl_hw_badge.setWordWrap(True)
        gsolv.addWidget(self.lbl_hw_badge)
        self._on_solver_backend_changed(self.cb_solver_choice.currentIndex())
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

        # 5. Hamiltonian Parameters
        grp_model = ModernCard("Hamiltonian Parameters")
        gm = QVBoxLayout(grp_model)
        gm.setSpacing(4)

        # 5a. Nearest-Neighbor Hopping (t)
        h1 = QHBoxLayout()
        self.lbl_t = QLabel("Hopping (t):")
        self.lbl_t.setStyleSheet("font-weight: 600;")
        h1.addWidget(self.lbl_t)
        h1.addStretch()
        self.spin_t = QDoubleSpinBox()
        self.spin_t.setMinimum(0.01)
        self.spin_t.setValue(1.0)
        self.spin_t.setSingleStep(0.1)
        self.spin_t.setFixedWidth(100)
        h1.addWidget(self.spin_t)
        gm.addLayout(h1)

        # 5b. Next-Nearest-Neighbor Hopping (t')
        h2 = QHBoxLayout()
        self.lbl_t1 = QLabel("Next-Nearest (t'):")
        self.lbl_t1.setStyleSheet("font-weight: 600;")
        h2.addWidget(self.lbl_t1)
        h2.addStretch()
        self.spin_t1 = QDoubleSpinBox()
        self.spin_t1.setRange(-10.0, 10.0)
        self.spin_t1.setValue(0.0)
        self.spin_t1.setSingleStep(0.05)
        self.spin_t1.setFixedWidth(100)
        h2.addWidget(self.spin_t1)
        gm.addLayout(h2)

        # 5c. Chemical Potential (μ)
        h3 = QHBoxLayout()
        self.lbl_mu = QLabel("Chemical Potential (μ):")
        self.lbl_mu.setStyleSheet("font-weight: 600;")
        h3.addWidget(self.lbl_mu)
        h3.addStretch()
        self.spin_mu = QDoubleSpinBox()
        self.spin_mu.setRange(-20.0, 20.0)
        self.spin_mu.setValue(1.0)
        self.spin_mu.setSingleStep(0.1)
        self.spin_mu.setFixedWidth(100)
        h3.addWidget(self.spin_mu)
        gm.addLayout(h3)

        # 5d. Intralayer Exchange (K)
        h4 = QHBoxLayout()
        self.lbl_k = QLabel("Intralayer Exchange (K):")
        self.lbl_k.setStyleSheet("font-weight: 600;")
        h4.addWidget(self.lbl_k)
        h4.addStretch()
        self.spin_k = QDoubleSpinBox()
        self.spin_k.setRange(-10.0, 10.0)
        self.spin_k.setValue(1.0)
        self.spin_k.setSingleStep(0.5)
        self.spin_k.setFixedWidth(100)
        h4.addWidget(self.spin_k)
        gm.addLayout(h4)

        # Scientific tooltips on labels and spinboxes
        tip_t = (
            "Nearest-Neighbor Hopping / Kinetic Energy (t):\n"
            "Conduction electron hopping between adjacent square lattice sites: "
            "ε₀(k) = -2t(cos kx + cos ky).\n"
            "Sets the fundamental energy scale and bare conduction bandwidth W = 8t."
        )
        tip_t1 = (
            "Next-Nearest-Neighbor Hopping (t'):\n"
            "Diagonal hopping amplitude across square lattice plaquettes: -4t' cos(kx) cos(ky).\n"
            "Breaks particle-hole symmetry and shifts the van Hove singularity away from half-filling."
        )
        tip_mu = (
            "Chemical Potential (μ):\n"
            "Controls conduction electron band filling and Fermi surface volume: ξ(k) = ε(k) - μ.\n"
            "At t'=0, μ=0 corresponds to half-filling (n=1). Positive μ indicates electron-doping; negative μ indicates hole-doping."
        )
        tip_k = (
            "Intralayer Exchange Coupling (K):\n"
            "Direct in-plane Heisenberg spin-spin exchange in the Mott insulator layer: "
            "H_K = K Σ_<i,j> S_i · S_j.\n"
            "K > 0 favors antiferromagnetic (AFM) ordering; K < 0 favors ferromagnetic (FM) alignment."
        )

        self.lbl_t.setToolTip(tip_t); self.spin_t.setToolTip(tip_t)
        self.lbl_t1.setToolTip(tip_t1); self.spin_t1.setToolTip(tip_t1)
        self.lbl_mu.setToolTip(tip_mu); self.spin_mu.setToolTip(tip_mu)
        self.lbl_k.setToolTip(tip_k); self.spin_k.setToolTip(tip_k)

        lay_sim.addWidget(grp_model)

        # 6. Output Directory Card
        grp_out = ModernCard("Results Output Directory")
        gout = QVBoxLayout(grp_out)
        gout.setSpacing(4)
        h_out = QHBoxLayout()
        self.edit_out_dir = QLineEdit(DEFAULT_RESULTS_DIR)
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
            self.refresh_dataset_tree()
            self._update_cache_badge()

    def _open_cache_manager(self):
        out_dir = self.edit_out_dir.text().strip() if hasattr(self, "edit_out_dir") else DEFAULT_RESULTS_DIR
        dlg = CacheManagerDialog(self, out_dir=out_dir)
        dlg.exec_()
        self._update_cache_badge()

    def _schedule_cache_check(self, *args):
        if hasattr(self, "cache_timer"):
            self.cache_timer.start()

    def _update_cache_badge(self):
        if not hasattr(self, "lbl_cache_badge"):
            return
            
        out_dir = self.edit_out_dir.text().strip() if hasattr(self, "edit_out_dir") else DEFAULT_RESULTS_DIR
        
        # Update Cache Manager button text with live cache size
        stats = get_cache_stats(out_dir)
        if hasattr(self, "btn_cache_mgr"):
            self.btn_cache_mgr.setText(f"🧹 Cache ({stats['formatted_size']})")
            self.btn_cache_mgr.setToolTip(f"{stats['total_files']} foundation files ({stats['total_bytes']} bytes) in results/cache/")

        if hasattr(self, "chk_force_recompute") and self.chk_force_recompute.isChecked():
            self.lbl_cache_badge.setText("Force Recompute (Ignoring Cache)")
            self.lbl_cache_badge.setStyleSheet(
                "padding: 6px 10px; border-radius: 6px; font-weight: 600; font-size: 11px; "
                "background-color: rgba(217, 119, 6, 0.12); color: #d97706; border: 1px solid rgba(217, 119, 6, 0.35);"
            )
            self.lbl_cache_badge.setToolTip("Force Recompute is active. All reusable foundations in results/cache/ will be ignored and computed from scratch, which will take longer.")
            return

        # Build current params dictionary
        study = self.active_study
        is_cond = ("cond" in str(study).lower() or "conductivity" in str(study).lower())
        fixed_jperp_val = float(self.spin_cond_fixed.value()) if (is_cond and hasattr(self, "spin_cond_fixed")) else (float(self.spin_se_fixed.value()) if hasattr(self, "spin_se_fixed") else 6.0)

        params = {
            "t": float(self.spin_t.value()),
            "t1": float(self.spin_t1.value()),
            "mu": float(self.spin_mu.value()),
            "K": float(self.spin_k.value()),
            "N": int(self.spin_n.value()),
            "num_omega": int(self.spin_nw.value()),
            "omega_max": float(self.spin_wmax.value()),
            "eta": float(self.spin_eta.value()),
            "sweep_mode": self.cb_se_mode.currentText() if hasattr(self, "cb_se_mode") else "",
            "jk_values": self.edit_se_vals.text().strip() if hasattr(self, "edit_se_vals") else "",
            "fixed_jperp": fixed_jperp_val,
            "cond_sweep_mode": self.cb_cond_mode.currentText() if hasattr(self, "cb_cond_mode") else "",
            "cond_sweep_vals": self.edit_cond_vals.text().strip() if hasattr(self, "edit_cond_vals") else "",
            "w_active_max": float(self.spin_cond_wactive.value()) if hasattr(self, "spin_cond_wactive") else 5.0,
            "spec_sweep_mode": self.cb_spec_mode.currentText() if hasattr(self, "cb_spec_mode") else "",
            "spec_sweep_vals": self.edit_spec_vals.text().strip() if hasattr(self, "edit_spec_vals") else "",
            "spec_fixed_coupling": float(self.spin_spec_fixed.value()) if hasattr(self, "spin_spec_fixed") else 6.0,
            "spec_momentum": self.cb_mom.currentText() if hasattr(self, "cb_mom") else "",
            "spec_custom_k": self.edit_custom_k.text().strip() if hasattr(self, "edit_custom_k") else "",
            "JK_min": float(self.s_min.value()) if hasattr(self, "s_min") else 0.0,
            "JK_max": float(self.s_max.value()) if hasattr(self, "s_max") else 12.0,
            "JK_pts": int(self.s_pts.value()) if hasattr(self, "s_pts") else 200,
            "run_static": bool(self.chk_static.isChecked()) if hasattr(self, "chk_static") else True,
            "run_dynamic": bool(self.chk_dynamic.isChecked()) if hasattr(self, "chk_dynamic") else True,
            "susc_sweep_vals": self.edit_susc_vals.text().strip() if hasattr(self, "edit_susc_vals") else "",
            "fixed_J": float(self.spin_se_fixed.value()) if hasattr(self, "spin_se_fixed") else 6.0
        }

        res = check_cache_status(study, params, out_dir)
        text = res["badge_text"]
        details = res["details"]
        state = res.get("state", "cold")

        if state == "cached":
            color = "#16a34a"
            bg_col = "rgba(22, 163, 74, 0.12)"
            border_col = "rgba(22, 163, 74, 0.35)"
        elif state == "partial":
            color = "#d97706"
            bg_col = "rgba(217, 119, 6, 0.12)"
            border_col = "rgba(217, 119, 6, 0.35)"
        else:
            color = "#64748b"
            bg_col = "rgba(100, 116, 139, 0.12)"
            border_col = "rgba(100, 116, 139, 0.35)"

        self.lbl_cache_badge.setText(text)
        self.lbl_cache_badge.setStyleSheet(
            f"padding: 6px 10px; border-radius: 6px; font-weight: 600; font-size: 11px; "
            f"background-color: {bg_col}; color: {color}; border: 1px solid {border_col};"
        )
        self.lbl_cache_badge.setToolTip(details)

    def _wire_cache_check_signals(self):
        """Connects all parameter inputs to debounced cache badge update."""
        spinboxes = [
            self.spin_t, self.spin_t1, self.spin_mu, self.spin_k,
            self.spin_n, self.spin_nw, self.spin_wmax, self.spin_eta,
            self.spin_se_fixed, self.spin_spec_fixed,
            self.s_min, self.s_max, self.s_pts
        ]
        if hasattr(self, "spin_cond_fixed"):
            spinboxes.append(self.spin_cond_fixed)
        if hasattr(self, "spin_cond_wactive"):
            spinboxes.append(self.spin_cond_wactive)

        for sp in spinboxes:
            sp.valueChanged.connect(self._schedule_cache_check)

        combos = [self.cb_preset, self.cb_se_mode, self.cb_spec_mode, self.cb_mom, self.cb_solver_choice]
        if hasattr(self, "cb_cond_mode"):
            combos.append(self.cb_cond_mode)

        for cb in combos:
            cb.currentIndexChanged.connect(self._schedule_cache_check)

        line_edits = [self.edit_se_vals, self.edit_spec_vals, self.edit_custom_k, self.edit_susc_vals]
        if hasattr(self, "edit_cond_vals"):
            line_edits.append(self.edit_cond_vals)

        for le in line_edits:
            le.textChanged.connect(self._schedule_cache_check)

        for chk in [self.chk_static, self.chk_dynamic, self.chk_force_recompute]:
            chk.stateChanged.connect(self._schedule_cache_check)

    def refresh_dataset_tree(self):
        """Refreshes the Plot Gallery and active plot comboboxes from the active output directory."""
        out_dir = self.edit_out_dir.text().strip() if hasattr(self, "edit_out_dir") else DEFAULT_RESULTS_DIR
        self.plots = get_available_plots(out_dir)

        if hasattr(self, "gallery"):
            self.gallery.set_output_dir(out_dir)

        if hasattr(self, "interactive_plots"):
            self.interactive_plots.set_output_dir(out_dir)

        # Update Active Plot combobox in Plot Viewer toolbar
        if hasattr(self, "cb_active_plot") and hasattr(self, "gallery"):
            self.cb_active_plot.blockSignals(True)
            self.cb_active_plot.clear()
            for p in self.gallery.all_plots:
                title, params_str, _, _, fname = parse_plot_metadata(p)
                disp = f"{title} [{params_str}]" if params_str else title
                self.cb_active_plot.addItem(disp, p)
            self.cb_active_plot.blockSignals(False)

            if self.gallery.all_plots:
                cur = self.current_view_plot_path if self.current_view_plot_path in self.gallery.all_plots else self.gallery.all_plots[0]
                self.current_view_plot_path = cur
                self.canvas_left.load_image(cur)
                # Select in combobox
                for i in range(self.cb_active_plot.count()):
                    if self.cb_active_plot.itemData(i) == cur:
                        self.cb_active_plot.blockSignals(True)
                        self.cb_active_plot.setCurrentIndex(i)
                        self.cb_active_plot.blockSignals(False)
                        break

    def _get_active_solver_choice(self) -> str:
        """Returns 'gpu' if CUDA GPU is actively selected and available, else 'cpu'."""
        if not hasattr(self, "cb_solver_choice"):
            return "cpu"
        txt = self.cb_solver_choice.currentText()
        if "CUDA GPU" in txt and "Unavailable" not in txt:
            return "gpu"
        return "cpu"

    def _on_solver_backend_changed(self, index):
        """Updates UI and hardware badge when toggling between GPU and CPU."""
        if self._get_active_solver_choice() == "gpu":
            self.box_cpu_limit.setVisible(False)
            hw = get_hardware_info()
            dev_name = hw.get("name", "NVIDIA GPU")
            self.lbl_hw_badge.setText(f"⚡ GPU Active: {dev_name} (64-bit CuPy)")
            self.lbl_hw_badge.setStyleSheet(
                "color: #15803d; font-weight: 600; font-size: 11px; padding: 6px 8px; "
                "background: #dcfce7; border: 1px solid #bbf7d0; border-radius: 5px;"
            )
        else:
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

    def _on_cond_sweep_mode_change(self, index):
        """Updates fixed coupling title and default value for Electrical Conductivity Sweep."""
        if index == 0:  # Kondo Coupling (J_K)
            self.lbl_cond_fixed.setText("Fixed Interlayer Coupling (J_⊥):")
            self.lbl_cond_fixed_desc.setText("Constant value of J_⊥ held fixed while sweeping J_K across curves")
            self.spin_cond_fixed.setValue(6.0)
        else:  # Interlayer Coupling (J_⊥)
            self.lbl_cond_fixed.setText("Fixed Kondo Coupling (J_K):")
            self.lbl_cond_fixed_desc.setText("Constant value of J_K held fixed while sweeping J_⊥ across curves")
            self.spin_cond_fixed.setValue(3.0)

    def _on_susc_sweep_mode_change(self, index):
        """Updates fixed coupling title and default value for RPA Spin Susceptibility Sweep."""
        if index == 0:  # Kondo Coupling (J_K)
            self.lbl_susc_fixed.setText("Fixed Interlayer Coupling (J_⊥):")
            self.lbl_susc_fixed_desc.setText("Constant value of J_⊥ held fixed while sweeping J_K across subplots")
            self.spin_susc_fixed.setValue(6.0)
            if self.edit_susc_vals.text().strip() in ["4.5, 6.0, 8.0", ""]:
                self.edit_susc_vals.setText("3.0, 6.0, 9.0")
        else:  # Interlayer Coupling (J_⊥)
            self.lbl_susc_fixed.setText("Fixed Kondo Coupling (J_K):")
            self.lbl_susc_fixed_desc.setText("Constant value of J_K held fixed while sweeping J_⊥ across subplots")
            self.spin_susc_fixed.setValue(6.0)
            if self.edit_susc_vals.text().strip() in ["3.0, 6.0, 9.0", ""]:
                self.edit_susc_vals.setText("4.5, 6.0, 8.0")

    def _on_mom_choice_changed(self, index):
        """Shows custom momentum vector edit field only when Custom is chosen."""
        self.box_custom_k.setVisible(index == 4)

    # =========================================================================
    # BOTTOM DOCK: EXECUTION CENTER (QUEUE & LIVE CONSOLE)
    # =========================================================================
    def _update_bottom_dock_theme(self, is_dark: bool):
        update_bottom_dock_theme(self, is_dark)

    def _update_statusbar_theme(self, is_dark: bool):
        update_statusbar_theme(self, is_dark)

    def _build_bottom_drawer_dock(self):
        self.dock_bottom = QDockWidget("⚡ Execution Center", self)
        self.dock_bottom.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.dock_bottom.setMaximumHeight(450)

        self.bottom_tabs = QTabWidget()

        # Tab 1: Batch Queue
        self.queue_widget = JobQueueWidget(
            self,
            on_start=self.start_queue,
            on_pause=self.pause_queue,
            on_add=self.add_to_queue,
            on_clear=self.clear_queue,
            on_clear_pending=self.clear_pending_queue,
            on_cancel_all=self.cancel_all_queue,
            on_cancel_active=self.cancel_simulation_ui,
            on_remove_row=self._remove_queued_row,
            on_resize=self._adjust_bottom_dock_height,
        )

        # Compatibility aliases preserve the existing main-window/test contract.
        self.btn_start = self.queue_widget.btn_start
        self.btn_pause = self.queue_widget.btn_pause
        self.btn_add_to_queue = self.queue_widget.btn_add_to_queue
        self.btn_clear = self.queue_widget.btn_clear
        self.btn_clear_pending = self.queue_widget.btn_clear_pending
        self.btn_cancel_all = self.queue_widget.btn_cancel_all
        self.lbl_queue_badge = self.queue_widget.lbl_queue_badge
        self.table_queue = self.queue_widget.table_queue
        self.bottom_tabs.addTab(self.queue_widget, "📋 Queue (0)")

        # Tab 2: Console
        console_tab = QWidget()
        cl = QVBoxLayout(console_tab)
        cl.setContentsMargins(6, 6, 6, 6)
        cl.setSpacing(6)

        # Console Action Bar
        crow = QHBoxLayout()
        crow.setContentsMargins(0, 0, 0, 0)
        crow.setSpacing(6)

        self.lbl_console_engine_status = QLabel("🟢 Engine Ready [Idle]")
        crow.addWidget(self.lbl_console_engine_status)

        crow.addStretch(1)

        self.btn_autoscroll = QPushButton("⬇ Auto-scroll: ON")
        self.btn_autoscroll.setCheckable(True)
        self.btn_autoscroll.setChecked(True)
        self.btn_autoscroll.setToolTip("Automatically follow live execution log output")
        self.btn_autoscroll.toggled.connect(self._on_autoscroll_toggled)
        crow.addWidget(self.btn_autoscroll)

        self.btn_copy_console = QPushButton("📋 Copy Console")
        self.btn_copy_console.setToolTip("Copy entire console output to clipboard")
        self.btn_copy_console.clicked.connect(self._copy_console_to_clipboard)
        crow.addWidget(self.btn_copy_console)

        self.btn_clear_console = QPushButton("🗑 Clear")
        self.btn_clear_console.setToolTip("Clear console history")
        self.btn_clear_console.clicked.connect(self._clear_console)
        crow.addWidget(self.btn_clear_console)

        cl.addLayout(crow)

        self.txt_console = QTextEdit()
        self.txt_console.setReadOnly(True)
        self.txt_console.setMinimumHeight(60)
        self.txt_console.setStyleSheet("""
            QTextEdit {
                background-color: #090d16;
                color: #f8fafc;
                font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.4;
                border: 1px solid #1e293b;
                border-radius: 5px;
                padding: 8px;
            }
        """)
        self.txt_console.append("<span style='color: #38bdf8; font-family: Consolas, monospace; font-weight: bold;'>Windows PowerShell [Studio Calculation Engine]</span>")
        hw = get_hardware_info()
        hw_label = hw["name"] if hw.get("is_gpu") else "Multi-Core CPU"
        self.txt_console.append(f"<span style='color: #94a3b8; font-family: Consolas, monospace;'>Ready. {hw_label} QProcess execution bridge initialized.</span><br>")
        cl.addWidget(self.txt_console)
        self.bottom_tabs.addTab(console_tab, "💻 Live Console")

        self._update_bottom_dock_theme(self.is_dark)

        self.dock_bottom.setWidget(self.bottom_tabs)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)

    def _on_autoscroll_toggled(self, checked: bool):
        self.btn_autoscroll.setText(f"⬇ Auto-scroll: {'ON' if checked else 'OFF'}")

    def _copy_console_to_clipboard(self):
        text = self.txt_console.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.lbl_status.setText("📋 Console output copied to clipboard.")

    def _clear_console(self):
        self.txt_console.clear()
        self.txt_console.append("<span style='color: #38bdf8; font-family: Consolas, monospace; font-weight: bold;'>Windows PowerShell [Studio Calculation Engine]</span>")
        hw = get_hardware_info()
        hw_label = hw["name"] if hw.get("is_gpu") else "Multi-Core CPU"
        self.txt_console.append(f"<span style='color: #94a3b8; font-family: Consolas, monospace;'>Ready. {hw_label} QProcess execution bridge initialized.</span><br>")

    def _build_statusbar(self):
        sb = self.statusBar()

        self.lbl_status = QLabel("● Ready. [Simulation Studio Active]")
        self.lbl_status.setMinimumWidth(0)

        self.lbl_coords = QLabel("Pointer: (kx = --, ky = --)")

        # Hardware status indicator pill
        hw_info = get_hardware_info()
        self.lbl_hw_status = QLabel()
        if hw_info.get("is_gpu"):
            dev_name = hw_info.get("name", "CUDA GPU")
            dev_clean = dev_name.replace("GeForce ", "").replace(" Laptop GPU", "")
            self.lbl_hw_status.setText(f"● GPU: {dev_clean} Detected")
            self.lbl_hw_status.setToolTip(f"CUDA GPU Acceleration Available: {hw_info.get('name')}\nTotal VRAM: {hw_info.get('total_vram_gb')} GB")
        else:
            self.lbl_hw_status.setText("● CPU Mode")
            self.lbl_hw_status.setToolTip("No CUDA GPU detected. Computations will run on multi-threaded CPU.")

        self._update_statusbar_theme(self.is_dark)

        sb.addWidget(self.lbl_status, 1)
        sb.addPermanentWidget(self.lbl_coords)
        sb.addPermanentWidget(self.lbl_hw_status)

    # =========================================================================
    # PERSPECTIVE / VIEWPORT MANAGEMENT
    # =========================================================================
    def set_perspective(self, mode="simulation"):
        """Ensures Simulation Studio active state.
        (Note: Standalone Figure Composer workspace has been scrapped in favor of
        integrated dual analytical viewports: Plot Viewer & Interactive Plots).
        """
        self.current_perspective = "simulation"
        self.action_run.setVisible(True)
        self.action_cancel.setVisible(True)
        self.action_queue.setVisible(True)
        if self.action_split:
            self.action_split.setVisible(True)
        self.dock_bottom.show()
        if hasattr(self, "central_view_stack") and self.central_view_stack.currentIndex() == 1:
            self.nav_stack.setCurrentIndex(1)
            self.dock_nav.setWindowTitle("🔬 Interactive Modes")
        else:
            self.nav_stack.setCurrentIndex(0)
            self.dock_nav.setWindowTitle("🖼️ Plot Gallery Browser")
        self.inspector_stack.setCurrentIndex(0)
        self.dock_inspector.setWindowTitle("⚙️ Simulation Setup")
        self.lbl_status.setText("Simulation Studio Ready.")

    def export_current_plot(self):
        """Exports currently loaded plot to disk in user-specified location."""
        if not hasattr(self, "current_view_plot_path") or not self.current_view_plot_path or not os.path.exists(self.current_view_plot_path):
            QMessageBox.warning(self, "Export Failed", "No plot is currently displayed to export.")
            return

        base = os.path.basename(self.current_view_plot_path)
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export Current Plot", base, "PNG Images (*.png);;All Files (*.*)"
        )
        if dest:
            try:
                import shutil
                shutil.copy2(self.current_view_plot_path, dest)
                self.lbl_status.setText(f"Exported plot to: {os.path.basename(dest)}")
                QMessageBox.information(self, "Export Successful", f"Plot successfully saved to:\n\n{dest}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export plot:\n{str(e)}")

    # =========================================================================
    # SIMULATION ACTIONS & QPROCESS BRIDGE WIRING
    # =========================================================================
    def set_active_study(self, study_name):
        self.active_study = study_name
        self.btn_run.setText("▶ Run Calculation")
        self.btn_run.setToolTip(f"Run {study_name} (Click arrow for study choices)")
        if self.cb_active_study.currentText() != study_name:
            self.cb_active_study.setCurrentText(study_name)

        study_map = {self.STUDY_SE: 0, self.STUDY_SPEC: 1, self.STUDY_PD: 2, self.STUDY_SUSC: 3, self.STUDY_COND: 4}
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
            elif study_name == self.STUDY_SUSC: p = self.plots.get("sweep_JK_fixed_J_6.0_mu_1.00_static.png")
            elif study_name == self.STUDY_COND:
                p = None
                for fname, fpath in self.plots.items():
                    if "conductivity" in fname.lower():
                        p = fpath
                        break
            else: p = None
            if p and os.path.exists(p):
                self.current_view_plot_path = p
                self.canvas_left.load_image(p)
                if hasattr(self, "gallery"):
                    self.gallery.select_plot(p)
                if hasattr(self, "cb_active_plot"):
                    for i in range(self.cb_active_plot.count()):
                        if self.cb_active_plot.itemData(i) == p:
                            self.cb_active_plot.blockSignals(True)
                            self.cb_active_plot.setCurrentIndex(i)
                            self.cb_active_plot.blockSignals(False)
                            break

        self._schedule_cache_check()

    def _select_and_run(self, study_name):
        self.set_active_study(study_name)
        self.run_simulation_ui()

    def _on_nav_selected(self, item, col):
        text = item.text(0)
        if text in (self.STUDY_SE, self.STUDY_SPEC, self.STUDY_PD, self.STUDY_SUSC, self.STUDY_COND):
            self.set_active_study(text)
        elif text in self.plots:
            self.canvas_left.load_image(self.plots[text])
            self.lbl_status.setText(f"Viewing Dataset: {text}")

    def _extract_active_study_params(self) -> tuple[dict | None, str, str]:
        """Extracts and validates simulation parameters from current UI controls without dispatching."""
        out_dir = self.edit_out_dir.text().strip()
        if not out_dir:
            out_dir = os.path.join(GUI_ROOT, "results")

        solver_choice = self._get_active_solver_choice()
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
            "force_recompute": bool(self.chk_force_recompute.isChecked()) if hasattr(self, "chk_force_recompute") else False,
            "output_dir": out_dir
        }

        if self.active_study == self.STUDY_SE:
            raw_sweep = self.edit_se_vals.text().strip()
            if not raw_sweep:
                QMessageBox.warning(self, "Validation Error", "Sweep values cannot be empty")
                return None, "", ""
            try:
                sweep_vals = [float(x.strip()) for x in raw_sweep.split(",") if x.strip()]
                if not sweep_vals:
                    raise ValueError("No valid numeric values in sweep list")
            except Exception as e:
                QMessageBox.warning(self, "Validation Error", f"Invalid sweep values: {e}")
                return None, "", ""

            params = {
                **common_params,
                "task": "spectral_sweep",
                "sweep_mode": self.cb_se_mode.currentText(),
                "jk_values": sweep_vals,
                "fixed_jperp": float(self.spin_se_fixed.value())
            }
            summary = f"Sweep: [{self.edit_se_vals.text()}], J_⊥={self.spin_se_fixed.value():.1f}, μ={self.spin_mu.value():.1f}, N={self.spin_n.value()}"

        elif self.active_study == self.STUDY_SPEC:
            raw_sweep = self.edit_spec_vals.text().strip()
            if not raw_sweep:
                QMessageBox.warning(self, "Validation Error", "Sweep coupling values cannot be empty")
                return None, "", ""
            try:
                sweep_vals = [float(x.strip()) for x in raw_sweep.split(",") if x.strip()]
                if not sweep_vals:
                    raise ValueError("No valid numeric values in sweep list")
            except Exception as e:
                QMessageBox.warning(self, "Validation Error", f"Invalid sweep values: {e}")
                return None, "", ""

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
            summary = f"k={self.cb_mom.currentText().split()[0]}, [{self.edit_spec_vals.text()}], J_⊥={self.spin_spec_fixed.value():.1f}, N={self.spin_n.value()}"

        elif self.active_study == self.STUDY_PD:
            params = {
                **common_params,
                "task": "phase_diagram",
                "JK_min": float(self.s_min.value()),
                "JK_max": float(self.s_max.value()),
                "JK_pts": int(self.s_pts.value())
            }
            summary = f"Bisection J_K ∈ [{self.s_min.value():.1f}, {self.s_max.value():.1f}], pts={self.s_pts.value()}, μ={self.spin_mu.value():.1f}"

        elif self.active_study == self.STUDY_SUSC:
            raw_sweep = self.edit_susc_vals.text().strip()
            if not raw_sweep:
                QMessageBox.warning(self, "Validation Error", "Susceptibility coupling values cannot be empty")
                return None, "", ""
            try:
                sweep_vals = [float(x.strip()) for x in raw_sweep.split(",") if x.strip()]
                if not sweep_vals:
                    raise ValueError("No valid numeric values in sweep list")
            except Exception as e:
                QMessageBox.warning(self, "Validation Error", f"Invalid sweep values: {e}")
                return None, "", ""

            if not self.chk_static.isChecked() and not self.chk_dynamic.isChecked():
                QMessageBox.warning(self, "Validation Error", "Please select at least one mode: Static χ(q) or Dynamic χ(q, ω)")
                return None, "", ""

            is_jk = not ("Interlayer" in self.cb_susc_mode.currentText() or "J_⊥" in self.cb_susc_mode.currentText())
            fixed_val = float(self.spin_susc_fixed.value())
            params = {
                **common_params,
                "task": "susceptibility",
                "run_static": bool(self.chk_static.isChecked()),
                "run_dynamic": bool(self.chk_dynamic.isChecked()),
                "susc_sweep_mode": "JK" if is_jk else "J",
                "susc_sweep_vals": sweep_vals,
                "fixed_J": fixed_val if is_jk else None,
                "fixed_JK": fixed_val if not is_jk else None
            }
            modes = []
            if self.chk_static.isChecked(): modes.append("Static χ(q)")
            if self.chk_dynamic.isChecked(): modes.append("Dynamic χ(q,ω)")
            mode_str = "+".join(modes) if modes else "None"
            sweep_tag = "J_K" if is_jk else "J_⊥"
            fixed_tag = "J_⊥" if is_jk else "J_K"
            summary = f"{mode_str}, {sweep_tag}=[{self.edit_susc_vals.text()}], fixed {fixed_tag}={fixed_val:.1f}, N={self.spin_n.value()}"

        elif self.active_study == self.STUDY_COND:
            raw_sweep = self.edit_cond_vals.text().strip()
            if not raw_sweep:
                QMessageBox.warning(self, "Validation Error", "Conductivity coupling values cannot be empty")
                return None, "", ""
            try:
                sweep_vals = [float(x.strip()) for x in raw_sweep.split(",") if x.strip()]
                if not sweep_vals:
                    raise ValueError("No valid numeric values in sweep list")
            except Exception as e:
                QMessageBox.warning(self, "Validation Error", f"Invalid sweep values: {e}")
                return None, "", ""

            is_jk = not ("Interlayer" in self.cb_cond_mode.currentText() or "J_⊥" in self.cb_cond_mode.currentText())
            params = {
                **common_params,
                "task": "conductivity_sweep",
                "cond_sweep_mode": "JK" if is_jk else "J_perp",
                "cond_sweep_vals": sweep_vals,
                "fixed_jperp": float(self.spin_cond_fixed.value()),
                "fixed_jk": float(self.spin_cond_fixed.value()),
                "w_active_max": float(self.spin_cond_wactive.value())
            }
            mode_tag = "J_K" if is_jk else "J_⊥"
            fixed_tag = "J_⊥" if is_jk else "J_K"
            summary = f"Conductivity {mode_tag} sweep [{self.edit_cond_vals.text()}], fixed {fixed_tag}={self.spin_cond_fixed.value():.1f}, μ={self.spin_mu.value():.1f}, N={self.spin_n.value()}"
        else:
            QMessageBox.warning(self, "Unknown Study", f"Unrecognized calculation study: {self.active_study}")
            return None, "", ""

        return params, self.active_study, summary

    def run_simulation_ui(self):
        """Starts real calculation via isolated QProcess bridge or enqueues if engine is busy."""
        params, study_name, summary = self._extract_active_study_params()
        if not params:
            return
        self.run_or_queue_job(params, study_name=study_name, summary=summary)

    def add_to_queue(self):
        """Extracts active study parameters and appends job directly to execution queue without hijacking console."""
        params, study_name, summary = self._extract_active_study_params()
        if not params:
            return

        if hasattr(self, "bridge") and self.bridge.is_running():
            # Engine is busy: Use run_or_queue_job to promote active job to row 0 and add this job to row 1+
            self.run_or_queue_job(params, study_name=study_name, summary=summary)
            return

        # Engine is idle: User specifically requested adding to queue without running immediately
        solver_choice = params.get("solver_choice", "gpu")
        row = self._create_queue_row(study_name, summary, solver_choice, status="⏳ Queued")
        if not hasattr(self, "queued_param_list"):
            self.queued_param_list = []
        self.queued_param_list.append({
            "params": params,
            "study": study_name,
            "summary": summary,
            "row_idx": row
        })
        self.lbl_status.setText(f"➕ Added {study_name} as Job #{row + 1} to batch queue.")
        self.bottom_tabs.setCurrentIndex(0)  # Always stay on / switch to Queue tab
        self._adjust_bottom_dock_height()

    def _create_queue_row(self, study_name: str, summary: str, solver_choice: str, status: str = "⏳ Queued") -> int:
        """Compatibility wrapper; row presentation lives in JobQueueWidget."""
        return self.queue_widget.create_row(study_name, summary, solver_choice, status)
    def run_or_queue_job(self, params: dict, study_name: str = None, summary: str = None) -> str:
        """Central serialization gateway: starts execution immediately if idle without queue clutter, or enqueues and promotes if busy."""
        if not study_name:
            if params.get("task") in ("foundation_cache", "compute_cache"):
                cat = params.get("cache_category", "sigma_base")
                study_name = "Self-Energy Σ" if "sigma" in cat else "Bare χ₀"
            else:
                study_name = self.active_study

        if not summary:
            if params.get("task") in ("foundation_cache", "compute_cache"):
                cat = params.get("cache_category", "sigma_base")
                summary = f"{cat}, μ={params.get('mu', 0.0):.2f}, N={params.get('N', 100)}"
                if "sigma" in cat:
                    summary += f", J_⊥={params.get('fixed_jperp', 6.0):.2f}, K={params.get('K', 1.0):.1f}"
            else:
                summary = f"μ={params.get('mu', 0.0):.2f}, N={params.get('N', 100)}"

        solver_choice = params.get("solver_choice", "gpu")

        if hasattr(self, "bridge") and self.bridge.is_running():
            # Engine is busy:
            # If the currently active running job has not been added to table_queue, promote it as Row 0 (Position #1)
            if getattr(self, "active_queue_row", -1) == -1 and getattr(self, "_active_job_info", None):
                row0 = self._create_queue_row(
                    self._active_job_info.get("study", "Calculation"),
                    self._active_job_info.get("summary", ""),
                    self._active_job_info.get("solver_choice", "gpu"),
                    status="🔄 Running..."
                )
                self.active_queue_row = row0
                prog0 = self.table_queue.cellWidget(row0, 4)
                if prog0:
                    pct = getattr(self, "_last_progress_pct", 0)
                    if pct > 0:
                        prog0.setRange(0, 100)
                        prog0.setValue(pct)
                    else:
                        prog0.setRange(0, 0)
                step0 = getattr(self, "_last_progress_step", "")
                if step0 and step0 != "Starting...":
                    self.table_queue.setItem(row0, 5, QTableWidgetItem(f"🔄 {step0}"))

            # Now append this new job as the next row (Position #2, Position #3, etc.)
            row = self._create_queue_row(study_name, summary, solver_choice, status="⏳ Queued")
            if not hasattr(self, "queued_param_list"):
                self.queued_param_list = []
            self.queued_param_list.append({
                "params": params,
                "study": study_name,
                "summary": summary,
                "row_idx": row
            })
            self.lbl_status.setText(f"➕ Queued {study_name} (Job #{row + 1})")
            self.bottom_tabs.setCurrentIndex(0)  # Switch to Queue tab so user sees both running & queued!
            self._adjust_bottom_dock_height()
            return "queued"

        # Engine is idle: Fresh standalone run WITHOUT adding to queue list!
        # Clear past completed/cancelled rows so queue starts clean
        if hasattr(self, "queued_param_list"):
            self.queued_param_list.clear()
        self.table_queue.setRowCount(0)
        self.active_queue_row = -1
        self._active_job_info = {
            "params": params,
            "study": study_name,
            "summary": summary,
            "solver_choice": solver_choice
        }
        self._last_progress_pct = 0
        self._last_progress_step = "Starting..."

        if params.get("task") in ("foundation_cache", "compute_cache"):
            self._foundation_requested = True
        else:
            self._foundation_requested = False

        self.bottom_tabs.setCurrentIndex(1)  # Switch to Live Console for active run
        self._adjust_bottom_dock_height()

        try:
            self._update_execution_buttons(is_running=True)
            self.bridge.start_calculation(params)
            return "running"
        except RuntimeError as e:
            self._foundation_requested = False
            self._active_job_info = None
            self._update_execution_buttons(is_running=False)
            QMessageBox.warning(self, "Execution Warning", str(e))
            return "error"

    def run_or_queue_foundation_job(self, params: dict) -> str:
        """Runs a compute cache job directly if engine is idle, or queues it if busy."""
        cat = params.get("cache_category", "sigma_base")
        study_name = "Self-Energy Σ" if "sigma" in cat else "Bare χ₀"
        summary = f"{cat}, μ={params.get('mu', 0.0):.2f}, N={params.get('N', 100)}"
        if "sigma" in cat:
            summary += f", J_⊥={params.get('fixed_jperp', 6.0):.2f}"
        return self.run_or_queue_job(params, study_name=study_name, summary=summary)

    run_or_queue_cache_job = run_or_queue_foundation_job  # Canonical alias

    def _on_precompute_bubble(self):
        """Precomputes and caches the bare bubble chi0 on the selected backend."""
        out_dir = self.edit_out_dir.text().strip() or os.path.join(GUI_ROOT, "results")
        solver_choice = self._get_active_solver_choice()
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
            "force_recompute": bool(self.chk_force_recompute.isChecked()) if hasattr(self, "chk_force_recompute") else False,
            "output_dir": out_dir,
            "run_static": True,
            "run_dynamic": False,
            "susc_sweep_mode": "JK",
            "susc_sweep_vals": [1.0],
            "fixed_J": 6.0
        }
        self.run_or_queue_job(params, study_name="Precompute χ₀ Bubble", summary=f"Bare bubble χ₀, μ={params['mu']:.1f}, N={params['N']}")

    def run_foundation_cache_ui(self):
        """Directly synthesizes base self-energy or bare susceptibility foundation caches and auto-switches to Interactive Plots."""
        out_dir = self.edit_out_dir.text().strip() or os.path.join(GUI_ROOT, "results")
        solver_choice = self._get_active_solver_choice()
        cpu_limit = self.cb_cpu_limit.currentText().split()[0] if hasattr(self, "cb_cpu_limit") else "80%"

        target_category = "sigma_base" if ("Spectral" in self.active_study or "Self" in self.active_study or "Conductivity" in self.active_study) else "chi0_static"
        fixed_jp = float(self.spin_cond_fixed.value()) if "Conductivity" in self.active_study else float(self.spin_se_fixed.value())

        params = {
            "task": "foundation_cache",
            "cache_category": target_category,
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
            "fixed_jperp": fixed_jp,
            "force_recompute": bool(self.chk_force_recompute.isChecked()) if hasattr(self, "chk_force_recompute") else False,
            "output_dir": out_dir,
        }

        self.run_or_queue_foundation_job(params)

    def _on_receive_interactive_parameters(self, params: dict):
        """Pre-fills Simulation Studio Parameter Dock with parameters discovered in Interactive Plots."""
        mu_val = params.get("mu", 0.0)
        jk_val = params.get("JK", 6.0)
        jperp_val = params.get("Jperp", 6.0)
        k_val = params.get("K", 1.0)
        n_val = params.get("N", None)

        if hasattr(self, "spin_mu"):
            self.spin_mu.setValue(mu_val)
        if hasattr(self, "spin_k"):
            self.spin_k.setValue(k_val)
        if hasattr(self, "spin_se_fixed"):
            self.spin_se_fixed.setValue(jperp_val)
        if hasattr(self, "edit_se_vals"):
            self.edit_se_vals.setText(str(round(jk_val, 3)))
        if hasattr(self, "edit_susc_vals") and hasattr(self, "spin_susc_fixed") and hasattr(self, "cb_susc_mode"):
            is_susc_jk = not ("Interlayer" in self.cb_susc_mode.currentText() or "J_⊥" in self.cb_susc_mode.currentText())
            if is_susc_jk:
                self.edit_susc_vals.setText(str(round(jk_val, 3)))
                self.spin_susc_fixed.setValue(jperp_val)
            else:
                self.edit_susc_vals.setText(str(round(jperp_val, 3)))
                self.spin_susc_fixed.setValue(jk_val)
        elif hasattr(self, "edit_susc_vals"):
            self.edit_susc_vals.setText(str(round(jk_val, 3)))
        if hasattr(self, "edit_cond_vals"):
            self.edit_cond_vals.setText(str(round(jk_val, 3)))
        if hasattr(self, "spin_cond_fixed"):
            self.spin_cond_fixed.setValue(jperp_val)
        if n_val is not None and hasattr(self, "spin_n"):
            self.spin_n.setValue(int(n_val))

        active_mode = str(params.get("active_mode", "")).lower()
        if "conductivity" in active_mode:
            self.set_active_study(self.STUDY_COND)
        elif "susceptibility" in active_mode or "rpa" in active_mode:
            self.set_active_study(self.STUDY_SUSC)

        # Switch perspective to Simulation Studio and viewport to Plot Viewer CAD
        self.set_perspective("simulation")
        self.set_canvas_mode(0)
        self.lbl_status.setText(f"🚀 Loaded parameters from Interactive Plots: μ={mu_val:.2f}, J_K={jk_val:.2f}, J_⊥={jperp_val:.2f}")

    def _update_execution_buttons(self, is_running: bool):
        """Updates Run and Cancel/Stop buttons cleanly and forces Qt stylesheet re-evaluation."""
        if is_running:
            self.btn_run.setEnabled(False)
            self.btn_run.setText("⏳ Running...")
            self.btn_cancel.setEnabled(True)
            self.btn_cancel.setText("⏹ Stop")
        else:
            self.btn_run.setEnabled(True)
            self.btn_run.setText("▶ Run Study")
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.setText("⏹ Stop")
        if hasattr(self, "btn_dock_foundation"):
            self.btn_dock_foundation.setEnabled(not is_running)
        if hasattr(self, "btn_dock_sweep"):
            self.btn_dock_sweep.setEnabled(not is_running)
        for btn in (self.btn_run, self.btn_cancel):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

        # Update any open FoundationCacheDialog or subdialogs
        for w in QApplication.topLevelWidgets():
            if hasattr(w, "update_engine_state"):
                try:
                    w.update_engine_state(is_running)
                except Exception:
                    pass

    def cancel_simulation_ui(self):
        """Cancels ONLY the currently active running calculation and automatically advances to the next queued job."""
        if hasattr(self, "_foundation_requested"):
            self._foundation_requested = False

        if not hasattr(self, "bridge") or not self.bridge.is_running():
            self._update_execution_buttons(is_running=False)
            return

        self._cancelling_active_only = True

        # Mark active queue table row as Cancelled
        if hasattr(self, "active_queue_row") and 0 <= self.active_queue_row < self.table_queue.rowCount():
            prog = self.table_queue.cellWidget(self.active_queue_row, 4)
            if prog:
                prog.setRange(0, 100)
                prog.setValue(0)
            item_cancel = QTableWidgetItem("⏹ Cancelled")
            item_cancel.setTextAlignment(Qt.AlignCenter)
            item_cancel.setForeground(QColor("#ef4444"))
            self.table_queue.setItem(self.active_queue_row, 5, item_cancel)

        # Keep buttons in stopping feedback
        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳ Stopping...")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("⏳ Stopping...")
        if hasattr(self, "btn_dock_foundation"):
            self.btn_dock_foundation.setEnabled(False)
        if hasattr(self, "btn_dock_sweep"):
            self.btn_dock_sweep.setEnabled(False)
        for btn in (self.btn_run, self.btn_cancel):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

        self.lbl_status.setText("⏳ Stopping active calculation & purging GPU VRAM...")
        self.txt_console.append(
            f"<div style='color: #ffff00; font-family: Consolas, monospace; font-weight: bold; margin: 4px 0;'>"
            f"[{time.strftime('%H:%M:%S')}] ⏹ [CANCEL ACTIVE] Terminating active calculation..."
            f"</div>"
        )
        sb = self.txt_console.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())
        QApplication.processEvents()

        self.bridge.cancel_calculation()

    def cancel_all_queue(self):
        """Aborts active calculation, purges queued list, and cancels all pending jobs in the execution queue."""
        self._cancelling_active_only = False
        if hasattr(self, "_foundation_requested"):
            self._foundation_requested = False

        if hasattr(self, "queued_param_list"):
            self.queued_param_list.clear()

        # Mark all running and queued rows as Cancelled
        for r in range(self.table_queue.rowCount()):
            st_item = self.table_queue.item(r, 5)
            if st_item and any(k in st_item.text() for k in ["Queued", "Running", "Pending", "Solving", "🔄", "⏳"]):
                st_item.setText("⏹ Cancelled")
                st_item.setForeground(QColor("#ef4444"))
                prog = self.table_queue.cellWidget(r, 4)
                if prog:
                    prog.setRange(0, 100)
                    prog.setValue(0)

        self.lbl_status.setText("⏹ All calculations cancelled and batch queue purged.")
        self.txt_console.append(
            f"<div style='color: #ef4444; font-family: Consolas, monospace; font-weight: bold; margin: 4px 0;'>"
            f"[{time.strftime('%H:%M:%S')}] ⏹ [CANCEL ALL] Aborted active job and purged all queued calculations."
            f"</div>"
        )
        sb = self.txt_console.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

        if hasattr(self, "lbl_console_engine_status"):
            self.lbl_console_engine_status.setText("🟢 Engine Ready [Idle]")
            self.lbl_console_engine_status.setStyleSheet("""
                QLabel {
                    background: #ecfdf5;
                    border: 1px solid #a7f3d0;
                    border-radius: 10px;
                    padding: 2px 10px;
                    font-size: 10px;
                    font-weight: 700;
                    color: #065f46;
                }
            """)

        if hasattr(self, "bridge") and self.bridge.is_running():
            self.btn_run.setEnabled(False)
            self.btn_run.setText("⏳ Stopping...")
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.setText("⏳ Stopping...")
            self.bridge.cancel_calculation()
        else:
            self._update_execution_buttons(is_running=False)

    def _on_queue_table_context_menu(self, pos):
        """Compatibility wrapper for the queue widget context menu."""
        self.queue_widget._on_context_menu(pos)
    def _remove_queued_row(self, row: int):
        """Remove a queue row while preserving execution-state ownership in the main window."""
        if 0 <= row < self.table_queue.rowCount():
            item = self.table_queue.item(row, 5)
            status = item.text() if item else ""
            if any(k in status for k in ["Running", "Solving", "🔄"]):
                self.cancel_simulation_ui()
                return
            if hasattr(self, "queued_param_list"):
                self.queued_param_list = [job for job in self.queued_param_list if job.get("row_idx") != row]
                for job in self.queued_param_list:
                    if job.get("row_idx", 0) > row:
                        job["row_idx"] -= 1
            self.table_queue.removeRow(row)
            if hasattr(self, "active_queue_row") and self.active_queue_row > row:
                self.active_queue_row -= 1
            self.queue_widget.renumber()
            self._adjust_bottom_dock_height()
    def _on_calc_started(self):
        self._update_execution_buttons(is_running=True)
        hw = get_hardware_info()
        dev_name = hw.get("name", "CUDA GPU")
        backend_name = dev_name if self._get_active_solver_choice() == "gpu" else "Host CPU"
        self.lbl_status.setText(f"⏳ Running: Initializing {backend_name} solver for {self.active_study}...")
        if hasattr(self, "lbl_console_engine_status"):
            self.lbl_console_engine_status.setText("🔵 Engine Active [Running...]")
            self.lbl_console_engine_status.setStyleSheet("""
                QLabel {
                    background: #eff6ff;
                    border: 1px solid #bfdbfe;
                    border-radius: 10px;
                    padding: 2px 10px;
                    font-size: 10px;
                    font-weight: 700;
                    color: #1d4ed8;
                }
            """)
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
        if getattr(self, "btn_autoscroll", None) is None or self.btn_autoscroll.isChecked():
            sb = self.txt_console.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())

    def _on_calc_status(self, message: str):
        """Displays accurate, informative physics execution stage without fake percentages."""
        if message:
            self._last_progress_step = message
            self.lbl_status.setText(f"⏳ Running: {message}")

    def _on_calc_progress(self, percent: int, step: str):
        """Updates status cleanly and updates real progress in the active queue table row."""
        self._last_progress_pct = percent
        if step:
            self._last_progress_step = step
            self.lbl_status.setText(f"⏳ Running: {step}")
        if hasattr(self, "active_queue_row") and 0 <= self.active_queue_row < self.table_queue.rowCount():
            prog = self.table_queue.cellWidget(self.active_queue_row, 4)
            if prog:
                if percent > 0:
                    prog.setRange(0, 100)
                    prog.setValue(percent)
                else:
                    prog.setRange(0, 0)
            st_text = f"🔄 {step}" if step else (f"🔄 Solving ({percent}%)" if percent > 0 else "🔄 Running...")
            self.table_queue.setItem(self.active_queue_row, 5, QTableWidgetItem(st_text))

    def _on_calc_completed(self, payload: dict):
        self._update_execution_buttons(is_running=False)
        self.lbl_status.setText(f"✅ Completed: {self.active_study} finished • Loaded into viewport.")
        if hasattr(self, "lbl_console_engine_status"):
            self.lbl_console_engine_status.setText("🟢 Engine Ready [Idle]")
            self.lbl_console_engine_status.setStyleSheet("""
                QLabel {
                    background: #ecfdf5;
                    border: 1px solid #a7f3d0;
                    border-radius: 10px;
                    padding: 2px 10px;
                    font-size: 10px;
                    font-weight: 700;
                    color: #065f46;
                }
            """)
        self.txt_console.append(
            f"<div style='color: #4ade80; font-family: Consolas, monospace; font-weight: bold; margin: 4px 0;'>"
            f"[{time.strftime('%H:%M:%S')}] ✅ Calculation completed successfully."
            f"</div>"
        )

        # Mark active queue table row as completed
        if hasattr(self, "active_queue_row") and 0 <= self.active_queue_row < self.table_queue.rowCount():
            prog = self.table_queue.cellWidget(self.active_queue_row, 4)
            if prog:
                prog.setRange(0, 100)
                prog.setValue(100)
            item_done = QTableWidgetItem("✅ Completed")
            item_done.setTextAlignment(Qt.AlignCenter)
            item_done.setForeground(QColor("#16a34a"))
            self.table_queue.setItem(self.active_queue_row, 5, item_done)

        self._active_job_info = None
        self._last_progress_pct = 0
        self._last_progress_step = ""

        all_plots = payload.get("all_plots", [])
        primary_plot = payload.get("plot_path", "")
        data_path = payload.get("data_path", "")
        if not all_plots and primary_plot:
            all_plots = [primary_plot]

        self.refresh_dataset_tree()
        self._update_cache_badge()
        if hasattr(self, "interactive_plots") and self.interactive_plots:
            self.interactive_plots.scan_caches()
            if data_path:
                self.interactive_plots._on_foundation_cache_generated(data_path)
        if hasattr(self, "gallery") and self.gallery:
            self.gallery.refresh_gallery()

        if getattr(self, "_foundation_requested", False):
            self._foundation_requested = False
            self.lbl_status.setText("⚡ Cache ready! Switched to Interactive Plots.")
            self.set_canvas_mode(1)

        if primary_plot and os.path.exists(primary_plot):
            self.current_view_plot_path = primary_plot
            self.canvas_left.load_image(primary_plot)
            self.canvas_left.fit_in_view()
            if hasattr(self, "gallery") and self.gallery:
                self.gallery.select_plot(primary_plot)
            if hasattr(self, "cb_active_plot"):
                for i in range(self.cb_active_plot.count()):
                    if self.cb_active_plot.itemData(i) == primary_plot:
                        self.cb_active_plot.blockSignals(True)
                        self.cb_active_plot.setCurrentIndex(i)
                        self.cb_active_plot.blockSignals(False)
                        break

        if data_path and os.path.exists(data_path) and hasattr(self, "data_canvas"):
            self.data_canvas.load_dataset(data_path)

        # Advance to next queued job if available
        if not self._launch_next_queued_job():
            QTimer.singleShot(4000, self._reset_status_to_ready)

    def _reset_status_to_ready(self):
        """Resets status bar to default Ready state when idle."""
        if hasattr(self, "bridge") and not self.bridge.is_running():
            self.lbl_status.setText("Ready. [Simulation Studio Active]")

    def _launch_next_queued_job(self) -> bool:
        """Pops and launches the next queued calculation job in the batch sequence. Returns True if a job started."""
        if getattr(self, "_queue_paused", False):
            self._update_execution_buttons(is_running=False)
            self.lbl_status.setText("⏸ Batch queue paused. Click 'Run All Pending' to resume.")
            return False

        if not getattr(self, "queued_param_list", None) or len(self.queued_param_list) == 0:
            self._update_execution_buttons(is_running=False)
            self.active_queue_row = -1
            self._active_job_info = None
            return False

        next_job = self.queued_param_list.pop(0)
        next_params = next_job["params"]
        next_study = next_job.get("study", "Calculation")

        row_idx = next_job.get("row_idx", None)
        if row_idx is None or row_idx >= self.table_queue.rowCount() or "Queued" not in (self.table_queue.item(row_idx, 5).text() if self.table_queue.item(row_idx, 5) else ""):
            for r in range(self.table_queue.rowCount()):
                st_item = self.table_queue.item(r, 5)
                if st_item and any(k in st_item.text() for k in ["Queued", "Pending", "⏳"]):
                    row_idx = r
                    break

        if row_idx is not None and row_idx < self.table_queue.rowCount():
            self.active_queue_row = row_idx
            item_run = QTableWidgetItem("🔄 Running...")
            item_run.setTextAlignment(Qt.AlignCenter)
            item_run.setForeground(QColor("#2563eb"))
            self.table_queue.setItem(row_idx, 5, item_run)
            prog = self.table_queue.cellWidget(row_idx, 4)
            if prog:
                prog.setRange(0, 0)

        self._active_job_info = {
            "params": next_params,
            "study": next_study,
            "summary": next_job.get("summary", ""),
            "solver_choice": next_params.get("solver_choice", "gpu")
        }
        self._last_progress_pct = 0
        self._last_progress_step = "Starting..."

        if next_params.get("task") == "foundation_cache":
            self._foundation_requested = True
        else:
            self._foundation_requested = False

        try:
            self._update_execution_buttons(is_running=True)
            self.lbl_status.setText(f"⚡ Running queued job: {next_study}...")
            self.txt_console.append(
                f"<div style='color: #38bdf8; font-family: Consolas, monospace; font-weight: bold; margin: 4px 0;'>"
                f"[{time.strftime('%H:%M:%S')}] ⚡ [BATCH QUEUE] Launching next job: {next_study}"
                f"</div>"
            )
            self.bridge.start_calculation(next_params)
            return True
        except Exception as e:
            self._update_execution_buttons(is_running=False)
            if row_idx is not None and row_idx < self.table_queue.rowCount():
                self.table_queue.setItem(row_idx, 5, QTableWidgetItem("❌ Error"))
            self.lbl_status.setText(f"❌ Failed to launch queued job: {e}")
            return self._launch_next_queued_job()

    def _on_calc_error(self, error_msg: str):
        self._update_execution_buttons(is_running=False)
        self.lbl_status.setText(f"❌ Error: {error_msg}")
        if hasattr(self, "active_queue_row") and 0 <= self.active_queue_row < self.table_queue.rowCount():
            prog = self.table_queue.cellWidget(self.active_queue_row, 4)
            if prog:
                prog.setRange(0, 100)
                prog.setValue(0)
            item_err = QTableWidgetItem("❌ Failed")
            item_err.setTextAlignment(Qt.AlignCenter)
            item_err.setForeground(QColor("#dc2626"))
            self.table_queue.setItem(self.active_queue_row, 5, item_err)
        self._active_job_info = None
        self._last_progress_pct = 0
        self._last_progress_step = ""
        self.txt_console.append(
            f"<div style='color: #ff6b68; font-family: Consolas, monospace; font-weight: bold; margin: 4px 0;'>"
            f"[{time.strftime('%H:%M:%S')}] ❌ [ERROR] {error_msg}"
            f"</div>"
        )

        # Advance to next queued job if available
        if not self._launch_next_queued_job():
            QTimer.singleShot(6000, self._reset_status_to_ready)

    def _on_calc_cancelled(self):
        self._update_execution_buttons(is_running=False)
        self.lbl_status.setText("⏹ Stopped: Calculation cancelled • GPU VRAM released.")
        self._active_job_info = None
        self._last_progress_pct = 0
        self._last_progress_step = ""
        self.txt_console.append(
            f"<div style='color: #ffff00; font-family: Consolas, monospace; font-weight: bold; margin: 4px 0;'>"
            f"[{time.strftime('%H:%M:%S')}] ✅ [STOPPED] Process terminated cleanly. VRAM cache flushed to 0 MB."
            f"</div>"
        )
        sb = self.txt_console.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

        # If user cancelled active only and there are more jobs waiting in queue, automatically advance!
        if getattr(self, "_cancelling_active_only", False) and getattr(self, "queued_param_list", None) and len(self.queued_param_list) > 0:
            self._cancelling_active_only = False
            self.txt_console.append(
                f"<div style='color: #38bdf8; font-family: Consolas, monospace; font-weight: bold; margin: 4px 0;'>"
                f"[{time.strftime('%H:%M:%S')}] ⚡ Advancing to next queued job in batch..."
                f"</div>"
            )
            self._launch_next_queued_job()
            return

        self._cancelling_active_only = False
        QTimer.singleShot(2500, self._reset_status_to_ready)

    def closeEvent(self, event: QCloseEvent):
        """Guarantees child process termination upon window closing."""
        if hasattr(self, "cache_timer"):
            self.cache_timer.stop()
        if hasattr(self, "bridge"):
            self.bridge.kill_hard()
        if hasattr(self, "wheel_filter") and QApplication.instance():
            try:
                QApplication.instance().removeEventFilter(self.wheel_filter)
            except Exception:
                pass
        event.accept()

    def _adjust_bottom_dock_height(self):
        """Resize Execution Center and refresh queue widget presentation state."""
        n_rows = self.table_queue.rowCount()
        base_h = 165
        row_h = 30
        max_allowed = min(420, int(self.height() * 0.50))
        desired_h = min(max_allowed, base_h + max(1, n_rows) * row_h)
        self.dock_bottom.setMaximumHeight(max_allowed + 30)
        self.resizeDocks([self.dock_bottom], [desired_h], Qt.Vertical)
        if hasattr(self, "queue_widget"):
            self.queue_widget.update_badge()
            self.bottom_tabs.setTabText(0, f"📋 Queue ({n_rows})")

    def start_queue(self):
        """Starts batch queue execution if idle with remaining queued jobs."""
        self._queue_paused = False
        if self.bridge.is_running():
            return
        if not self._launch_next_queued_job():
            self.run_simulation_ui()

    def pause_queue(self):
        """Pauses batch queue execution after current running job finishes."""
        self._queue_paused = True
        self.lbl_status.setText("⏸ Batch queue paused. Active job will complete.")
        self.txt_console.append(
            f"<div style='color: #fcd34d; font-family: Consolas, monospace; font-weight: bold; margin: 4px 0;'>"
            f"[{time.strftime('%H:%M:%S')}] ⏸ [BATCH QUEUE] Paused. Active calculation will complete, remaining jobs held."
            f"</div>"
        )

    def clear_queue(self):
        """Removes all finished entries; queue presentation is owned by JobQueueWidget."""
        jobs = getattr(self, "queued_param_list", [])
        active = getattr(self, "active_queue_row", -1)
        self.queued_param_list, self.active_queue_row, removed = self.queue_widget.clear_finished(jobs, active)
        if removed > 0:
            self.lbl_status.setText(f"Cleared {removed} finished job(s) from batch queue.")
        else:
            self.lbl_status.setText("No finished jobs to clear from batch queue.")
    def clear_pending_queue(self):
        """Clears pending queue entries while preserving active and finished records."""
        jobs = getattr(self, "queued_param_list", [])
        active = getattr(self, "active_queue_row", -1)
        self.queued_param_list, self.active_queue_row, removed = self.queue_widget.clear_pending(jobs, active)
        if removed > 0:
            self.lbl_status.setText(f"Cleared {removed} pending job(s) from batch queue.")
        else:
            self.lbl_status.setText("No pending jobs to clear from batch queue.")
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
        toggle_main_window_theme(self)

    def reset_active_zoom(self):
        if hasattr(self, "central_view_stack") and self.central_view_stack.currentIndex() == 0 and hasattr(self, "data_canvas"):
            self.data_canvas.reset_zoom()
        else:
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
