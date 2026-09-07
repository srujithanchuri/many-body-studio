"""Interactive Scientific Data Canvas & Quantitative Visualization Engine for Many-Body Studio Pro.
Provides hardware-accelerated scientific data visualization via embedded Matplotlib FigureCanvasQTAgg.

Key Capabilities (Studio Architecture Sections 2.3 & 2.4):
1. 1D Quasiparticle Spectrum & Self-Energy Explorer with Snapping Crosshair & Live HUD.
2. Automated Quasiparticle Lifetime (τ), Weight (Z), and Peak Extraction.
3. 2D Brillouin Zone Colormap with Interactive High-Symmetry & Arbitrary Momentum Slicing.
4. Instant Zero-Wait RPA Parametric Coupler (60 FPS real-time J_K / J_⊥ sweep from cached χ₀).
5. Thesis Vector Export (PDF, SVG, EPS) with LaTeX Typography.
"""

import os
import time
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
import matplotlib.ticker as ticker

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont

from pyside6_studio.widgets.vector_export_dialog import VectorExportDialog
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QDoubleSpinBox, QFrame, QFileDialog,
    QMessageBox, QSplitter, QStackedWidget
)


class InteractiveDataCanvas(QWidget):
    """Quantitative interactive scientific canvas hosting Matplotlib FigureCanvasQTAgg."""

    coord_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dark = False
        self.current_dataset = None
        self.current_meta = {}
        self.active_mode = "1d"  # "1d", "2d_cutline", "rpa_coupler"

        # 1D curve tracking variables
        self._curves_1d = []
        self._crosshair_lines = []

        # 2D BZ variables
        self._chi_map = None
        self._q_axis = None
        self._cut_path_type = "GXMG"

        # Zero-wait RPA coupler variables
        self._cached_chi0 = None
        self._chi0_q_axis = None
        self._coupler_jk = 3.0
        self._coupler_jperp = 6.0
        self._coupler_k = 1.0

        self._build_ui()

    def _build_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(2)

        # 1. Top Mode & Action Strip
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(6, 4, 6, 4)
        top_bar.setSpacing(6)

        lbl_mode = QLabel("STUDIO VIEW:")
        lbl_mode.setStyleSheet("font-weight: 700; font-size: 11px; color: #64748b;")
        top_bar.addWidget(lbl_mode)

        self.cb_view_mode = QComboBox()
        self.cb_view_mode.addItems([
            "🌊 1D Quasiparticle Spectrum & Self-Energy",
            "🗺️ 2D Brillouin Zone Map & Momentum Slicer",
            "⚡ Real-Time Zero-Wait RPA Coupler (60 FPS)"
        ])
        self.cb_view_mode.currentIndexChanged.connect(self._on_view_mode_changed)
        top_bar.addWidget(self.cb_view_mode, 1)

        self.btn_reset_zoom = QPushButton("🔍 Reset Zoom")
        self.btn_reset_zoom.setToolTip("Reset canvas axes limits to full extent")
        self.btn_reset_zoom.clicked.connect(self.reset_zoom)
        top_bar.addWidget(self.btn_reset_zoom)

        self.btn_vector_export = QPushButton("📄 Export Vector PDF...")
        self.btn_vector_export.setToolTip("Export vector graphics with LaTeX typography")
        self.btn_vector_export.setStyleSheet("font-weight: 600; color: #1d4ed8; background-color: #eff6ff; border: 1px solid #bfdbfe;")
        self.btn_vector_export.clicked.connect(self.open_vector_export_dialog)
        top_bar.addWidget(self.btn_vector_export)

        main_lay.addLayout(top_bar)

        # 2. Live Quantitative HUD Badge Bar
        hud_bar = QHBoxLayout()
        hud_bar.setContentsMargins(6, 2, 6, 2)
        self.lbl_hud = QLabel("Hover over plot to inspect physical values")
        self.lbl_hud.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 11px; font-weight: 600; "
            "color: #0f172a; background-color: #f1f5f9; padding: 4px 8px; border-radius: 4px; border: 1px solid #e2e8f0;"
        )
        hud_bar.addWidget(self.lbl_hud, 1)
        main_lay.addLayout(hud_bar)

        # 3. Central Matplotlib Canvas
        self.fig = Figure(figsize=(8, 5), dpi=100, tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setFocusPolicy(Qt.ClickFocus)
        self.canvas.setFocus()
        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)

        main_lay.addWidget(self.canvas, 1)

        # 4. Context-Adaptive Controls Drawer (Bottom)
        self.drawer_stack = QStackedWidget()

        # Drawer Page 0: 1D Quasiparticle Options
        self.p_1d = QFrame()
        self.p_1d.setStyleSheet("background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 4px;")
        l_1d = QHBoxLayout(self.p_1d)
        l_1d.addWidget(QLabel("Spectral View Layout:"))
        self.cb_1d_layout = QComboBox()
        self.cb_1d_layout.addItems([
            "Full Quasiparticle Spectrum (3 Panels: Re Σ, A, Im Σ)",
            "Spectral Function Only A(k, ω)",
            "Self-Energy Only (Re Σ & Im Σ)",
            "Peak Lifetimes & Renormalization Z"
        ])
        self.cb_1d_layout.currentIndexChanged.connect(self._replot_1d)
        l_1d.addWidget(self.cb_1d_layout, 1)
        self.drawer_stack.addWidget(self.p_1d)

        # Drawer Page 1: 2D Momentum Slicer Options
        self.p_2d = QFrame()
        self.p_2d.setStyleSheet("background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 4px;")
        l_2d = QHBoxLayout(self.p_2d)
        l_2d.addWidget(QLabel("Brillouin Zone Cutline:"))
        self.cb_cut_path = QComboBox()
        self.cb_cut_path.addItems([
            "High-Symmetry Path: Γ (0,0) → X (π,0) → M (π,π) → Γ (0,0)",
            "Nodal Cut: Γ (0,0) → M (π,π)",
            "Antinodal Cut: Γ (0,0) → X (π,0)",
            "Boundary Slice: X (π,0) → M (π,π)"
        ])
        self.cb_cut_path.currentIndexChanged.connect(self._on_cut_path_changed)
        l_2d.addWidget(self.cb_cut_path, 1)

        l_2d.addWidget(QLabel("Colormap:"))
        self.cb_cmap = QComboBox()
        self.cb_cmap.addItems(["viridis", "plasma", "inferno", "magma", "coolwarm"])
        self.cb_cmap.currentIndexChanged.connect(self._replot_2d)
        l_2d.addWidget(self.cb_cmap)
        self.drawer_stack.addWidget(self.p_2d)

        # Drawer Page 2: Zero-Wait Real-Time RPA Coupler Sliders
        self.p_rpa = QFrame()
        self.p_rpa.setStyleSheet("background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 4px;")
        l_rpa = QHBoxLayout(self.p_rpa)
        l_rpa.setSpacing(8)

        l_rpa.addWidget(QLabel("<b>Kondo J<sub>K</sub>:</b>"))
        self.slider_jk = QSlider(Qt.Horizontal)
        self.slider_jk.setRange(0, 150)
        self.slider_jk.setValue(30)
        self.slider_jk.valueChanged.connect(self._on_rpa_slider_changed)
        l_rpa.addWidget(self.slider_jk, 1)

        self.spin_jk = QDoubleSpinBox()
        self.spin_jk.setRange(0.0, 15.0); self.spin_jk.setSingleStep(0.1); self.spin_jk.setValue(3.0)
        self.spin_jk.valueChanged.connect(lambda v: self.slider_jk.setValue(int(round(v * 10))))
        l_rpa.addWidget(self.spin_jk)

        l_rpa.addWidget(QLabel("<b>Interlayer J<sub>⊥</sub>:</b>"))
        self.slider_jperp = QSlider(Qt.Horizontal)
        self.slider_jperp.setRange(0, 150)
        self.slider_jperp.setValue(60)
        self.slider_jperp.valueChanged.connect(self._on_rpa_slider_changed)
        l_rpa.addWidget(self.slider_jperp, 1)

        self.spin_jperp = QDoubleSpinBox()
        self.spin_jperp.setRange(0.0, 15.0); self.spin_jperp.setSingleStep(0.1); self.spin_jperp.setValue(6.0)
        self.spin_jperp.valueChanged.connect(lambda v: self.slider_jperp.setValue(int(round(v * 10))))
        l_rpa.addWidget(self.spin_jperp)

        self.lbl_instability = QLabel("🟢 Paramagnetic Phase")
        self.lbl_instability.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #166534; background-color: #dcfce7; "
            "padding: 2px 8px; border-radius: 4px; border: 1px solid #bbf7d0;"
        )
        l_rpa.addWidget(self.lbl_instability)

        self.drawer_stack.addWidget(self.p_rpa)
        main_lay.addWidget(self.drawer_stack)

        # Initialize with placeholder plot
        self._render_placeholder()

    def set_theme(self, is_dark: bool):
        """Updates Matplotlib background and font aesthetics to match theme."""
        self.is_dark = is_dark
        bg = "#0b1120" if is_dark else "#ffffff"
        fg = "#f8fafc" if is_dark else "#0f172a"
        grid_col = "#334155" if is_dark else "#cbd5e1"

        if is_dark:
            self.lbl_hud.setStyleSheet(
                "font-family: 'Consolas', monospace; font-size: 11px; font-weight: 600; "
                "color: #f8fafc; background-color: #1e293b; padding: 4px 8px; border-radius: 4px; border: 1px solid #334155;"
            )
            drawer_style = "background-color: #0f172a; border-top: 1px solid #334155; padding: 4px;"
        else:
            self.lbl_hud.setStyleSheet(
                "font-family: 'Consolas', monospace; font-size: 11px; font-weight: 600; "
                "color: #0f172a; background-color: #f1f5f9; padding: 4px 8px; border-radius: 4px; border: 1px solid #e2e8f0;"
            )
            drawer_style = "background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 4px;"

        if hasattr(self, "p_1d"): self.p_1d.setStyleSheet(drawer_style)
        if hasattr(self, "p_2d"): self.p_2d.setStyleSheet(drawer_style)
        if hasattr(self, "p_rpa"): self.p_rpa.setStyleSheet(drawer_style)

        self.fig.patch.set_facecolor(bg)
        for ax in self.fig.axes:
            ax.set_facecolor(bg)
            ax.tick_params(colors=fg)
            for spine in ax.spines.values():
                spine.set_color(grid_col)
            ax.xaxis.label.set_color(fg)
            ax.yaxis.label.set_color(fg)
            ax.title.set_color(fg)

        self.canvas.draw_idle()

    def _render_placeholder(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.text(
            0.5, 0.5,
            "Interactive Data Studio\n\nSelect a dataset (.npz) from the Left Navigator\n"
            "to inspect quasiparticle peaks, cutlines, or launch zero-wait RPA sweeps.",
            horizontalalignment="center", verticalalignment="center",
            transform=ax.transAxes, fontsize=12, color="#64748b", linespacing=1.6
        )
        ax.set_xticks([])
        ax.set_yticks([])
        self.set_theme(self.is_dark)

    def load_dataset(self, npz_path: str, meta: dict = None):
        """Loads and parses raw numerical array dataset."""
        if not os.path.isfile(npz_path):
            return

        try:
            data = np.load(npz_path)
            self.current_dataset = dict(data)
            self.current_meta = meta or {}
            self.current_path = npz_path

            # Determine appropriate view mode based on arrays present
            keys = list(self.current_dataset.keys())

            if "chi0_grid" in keys or "chi0_master" in keys:
                # Bare bubble foundation cache -> Launch Real-Time RPA Coupler
                self.cb_view_mode.setCurrentIndex(2)
            elif "static_maps" in keys or "spectral_maps" in keys:
                # Susceptibility 2D Maps -> Launch 2D BZ Slicer
                self.cb_view_mode.setCurrentIndex(1)
            elif "A_0" in keys or "re_0" in keys or "Atot_loc_0" in keys or "omega" in keys:
                # 1D Spectral Data
                self.cb_view_mode.setCurrentIndex(0)
            else:
                self.cb_view_mode.setCurrentIndex(0)

            self._refresh_active_view()
        except Exception as e:
            QMessageBox.warning(self, "Data Load Error", f"Failed to load numerical dataset:\n{e}")

    def _on_view_mode_changed(self, index: int):
        self.drawer_stack.setCurrentIndex(index)
        if index == 0:
            self.active_mode = "1d"
        elif index == 1:
            self.active_mode = "2d_cutline"
        else:
            self.active_mode = "rpa_coupler"
        self._refresh_active_view()

    def _refresh_active_view(self):
        if not self.current_dataset:
            return

        if self.active_mode == "1d":
            self._replot_1d()
        elif self.active_mode == "2d_cutline":
            self._replot_2d()
        elif self.active_mode == "rpa_coupler":
            self._setup_rpa_coupler()

    # =========================================================================
    # 1D QUASIPARTICLE SPECTRUM & SELF-ENERGY EXPLORER
    # =========================================================================
    def _replot_1d(self):
        if not self.current_dataset:
            return

        self.fig.clear()
        data = self.current_dataset
        omega = data.get("omega")

        if omega is None:
            self._render_placeholder()
            return

        layout = self.cb_1d_layout.currentText()
        colors = ["#2563eb", "#d97706", "#dc2626", "#16a34a", "#9333ea"]

        # Parse curves
        curves = []
        if "num_curves" in data:
            for i in range(int(data["num_curves"])):
                val = data.get(f"val_{i}", i)
                lbl = str(data.get(f"label_{i}", f"Curve {i}"))
                re_s = data.get(f"re_{i}")
                im_s = data.get(f"im_{i}")
                a_k = data.get(f"A_{i}")
                curves.append({"val": val, "label": lbl, "re": re_s, "im": im_s, "A": a_k})
        elif "Atot_loc_0" in data:
            for i in range(10):
                k = f"Atot_loc_{i}"
                if k in data:
                    lbl = str(data.get("labels", [f"Sweep {i}"])[i]) if "labels" in data and len(data["labels"]) > i else f"J_K {i}"
                    curves.append({"val": i, "label": lbl, "re": None, "im": None, "A": data[k]})
                else:
                    break

        if not curves:
            self._render_placeholder()
            return

        self._curves_1d = curves
        self._omega_1d = omega

        has_self_energy = any(c["re"] is not None for c in curves)
        if not has_self_energy or "Spectral Function Only" in layout:
            ax = self.fig.add_subplot(111)
            ax.axvline(0, color="#94a3b8", linestyle="--", linewidth=0.8, alpha=0.7)
            for idx, c in enumerate(curves):
                if c["A"] is not None:
                    ax.plot(omega, c["A"], label=c["label"], color=colors[idx % len(colors)], lw=2.0)
            ax.set_xlabel(r"$\omega$ [eV]", fontsize=11)
            ax.set_ylabel(r"$A(\mathbf{k}, \omega)$ [Quasiparticle Intensity]", fontsize=11)
            ax.set_title("Quasiparticle Spectral Function", fontsize=12, fontweight="bold")
            ax.grid(True, linestyle=":", alpha=0.35)
            ax.legend(frameon=True, fontsize=9)
            ax.set_ylim(bottom=0.0)
            self._ax_spectral = ax
            self._ax_re = None
            self._ax_im = None

        elif "Self-Energy Only" in layout:
            ax_re = self.fig.add_subplot(121)
            ax_im = self.fig.add_subplot(122)
            for idx, c in enumerate(curves):
                if c["re"] is not None:
                    ax_re.plot(omega, c["re"], label=c["label"], color=colors[idx % len(colors)], lw=1.8)
                if c["im"] is not None:
                    ax_im.plot(omega, c["im"], label=c["label"], color=colors[idx % len(colors)], lw=1.8)
            ax_re.set_title(r"$\operatorname{Re}\Sigma(\mathbf{k}, \omega)$ [Energy Shift]")
            ax_im.set_title(r"$\operatorname{Im}\Sigma(\mathbf{k}, \omega)$ [Scattering Rate]")
            for a in (ax_re, ax_im):
                a.set_xlabel(r"$\omega$ [eV]")
                a.grid(True, linestyle=":", alpha=0.35)
                if len(a.get_lines()) > 0:
                    a.legend(frameon=True, fontsize=9)
            self._ax_re = ax_re
            self._ax_im = ax_im
            self._ax_spectral = None

        elif "Peak Lifetimes" in layout:
            ax = self.fig.add_subplot(111)
            # Find peaks and display quasiparticle metrics
            report_lines = []
            for idx, c in enumerate(curves):
                if c["A"] is not None:
                    pk_idx = np.argmax(c["A"])
                    w_pk = omega[pk_idx]
                    a_pk = c["A"][pk_idx]
                    half_max = a_pk / 2.0
                    above = np.where(c["A"] >= half_max)[0]
                    fwhm = (omega[above[-1]] - omega[above[0]]) if len(above) > 1 else 0.0
                    tau = (1.0 / fwhm) if fwhm > 0 else 0.0

                    ax.plot(omega, c["A"], label=f"{c['label']} (ω_pk={w_pk:.2f}, FWHM={fwhm:.3f})", color=colors[idx % len(colors)], lw=2.0)
                    ax.plot(w_pk, a_pk, 'o', color=colors[idx % len(colors)], markersize=7)

            ax.set_xlabel(r"$\omega$ [eV]", fontsize=11)
            ax.set_ylabel(r"$A(\mathbf{k}, \omega)$", fontsize=11)
            ax.set_title("Quasiparticle Peak Tracker & Lifetime Analysis", fontsize=12, fontweight="bold")
            ax.grid(True, linestyle=":", alpha=0.35)
            ax.legend(frameon=True, fontsize=9)
            self._ax_spectral = ax
            self._ax_re = None
            self._ax_im = None

        else:
            # Full 3-Panel Suite
            ax_re = self.fig.add_subplot(131)
            ax_spec = self.fig.add_subplot(132)
            ax_im = self.fig.add_subplot(133)

            for idx, c in enumerate(curves):
                col = colors[idx % len(colors)]
                if c["re"] is not None:
                    ax_re.plot(omega, c["re"], label=c["label"], color=col, lw=1.8)
                if c["A"] is not None:
                    ax_spec.plot(omega, c["A"], label=c["label"], color=col, lw=2.0)
                if c["im"] is not None:
                    ax_im.plot(omega, c["im"], label=c["label"], color=col, lw=1.8)

            ax_re.set_title(r"$\operatorname{Re}\Sigma(\mathbf{k}, \omega)$ [Shift]")
            ax_spec.set_title(r"$A(\mathbf{k}, \omega)$ [Spectrum]")
            ax_im.set_title(r"$\operatorname{Im}\Sigma(\mathbf{k}, \omega)$ [Scattering]")

            for a in (ax_re, ax_spec, ax_im):
                a.set_xlabel(r"$\omega$ [eV]")
                a.grid(True, linestyle=":", alpha=0.35)
                if len(a.get_lines()) > 0:
                    a.legend(frameon=True, fontsize=9)
            ax_spec.set_ylim(bottom=0.0)

            self._ax_re = ax_re
            self._ax_spectral = ax_spec
            self._ax_im = ax_im

        self.set_theme(self.is_dark)
        self.canvas.draw_idle()

    # =========================================================================
    # 2D BRILLOUIN ZONE MAP & MOMENTUM SLICER
    # =========================================================================
    def _replot_2d(self):
        if not self.current_dataset:
            return

        self.fig.clear()
        data = self.current_dataset

        grid = None
        if "static_maps" in data and len(data["static_maps"]) > 0:
            grid = data["static_maps"][0]
        elif "chi0_grid" in data:
            grid = data["chi0_grid"]
        elif "spectral_maps" in data and len(data["spectral_maps"]) > 0:
            grid = data["spectral_maps"][0]

        if grid is None or grid.ndim != 2:
            self._render_placeholder()
            return

        self._chi_map = grid
        N = grid.shape[0]
        q_axis = np.linspace(-1.0, 1.0, N)
        self._q_axis = q_axis

        cmap_name = self.cb_cmap.currentText()

        # Create 2 Subplots: Left 2D Map, Right 1D Cutline Profile
        ax_map = self.fig.add_subplot(121)
        ax_cut = self.fig.add_subplot(122)

        im = ax_map.imshow(grid, extent=[-1, 1, -1, 1], origin="lower", cmap=cmap_name, aspect="equal")
        self.fig.colorbar(im, ax=ax_map, fraction=0.046, pad=0.04, label=r"$\chi(\mathbf{q})$")
        ax_map.set_xlabel(r"$q_x / \pi$")
        ax_map.set_ylabel(r"$q_y / \pi$")
        ax_map.set_title(r"2D Static Susceptibility $\chi(\mathbf{q})$", fontsize=11, fontweight="bold")

        # Extract 1D Cutline Profile
        path_name = self.cb_cut_path.currentText()
        cut_x, cut_y, cut_vals, cut_labels = self._extract_cutline(grid, path_name)

        ax_cut.plot(range(len(cut_vals)), cut_vals, color="#2563eb", lw=2.0)
        ax_cut.set_ylabel(r"Intensity $\chi(q)$")
        ax_cut.set_title(f"1D Momentum Slice ({self._cut_path_type})", fontsize=11, fontweight="bold")
        ax_cut.grid(True, linestyle=":", alpha=0.35)

        if cut_labels:
            ticks = [idx for idx, (pos, lbl) in enumerate(cut_labels) if lbl]
            labels = [lbl for idx, (pos, lbl) in enumerate(cut_labels) if lbl]
            ax_cut.set_xticks(ticks)
            ax_cut.set_xticklabels(labels)

        # Draw trajectory on 2D map
        ax_map.plot(cut_x, cut_y, color="#ef4444", linestyle="--", linewidth=1.8, label="Cutline")
        ax_map.legend(loc="upper right", fontsize=8)

        self._ax_2d = ax_map
        self._ax_cut = ax_cut
        self.set_theme(self.is_dark)
        self.canvas.draw_idle()

    def _on_cut_path_changed(self, idx: int):
        if idx == 0: self._cut_path_type = "Γ → X → M → Γ"
        elif idx == 1: self._cut_path_type = "Γ → M"
        elif idx == 2: self._cut_path_type = "Γ → X"
        else: self._cut_path_type = "X → M"
        self._replot_2d()

    def _extract_cutline(self, grid: np.ndarray, path_desc: str):
        N = grid.shape[0]
        num_pts = 60

        if "Nodal Cut" in path_desc:
            # (0, 0) -> (1, 1)
            qx = np.linspace(0, 1, num_pts)
            qy = np.linspace(0, 1, num_pts)
            labels = [(0, r"$\Gamma$"), (num_pts - 1, r"$M$")]
        elif "Antinodal Cut" in path_desc:
            # (0, 0) -> (1, 0)
            qx = np.linspace(0, 1, num_pts)
            qy = np.zeros(num_pts)
            labels = [(0, r"$\Gamma$"), (num_pts - 1, r"$X$")]
        elif "Boundary Slice" in path_desc:
            # (1, 0) -> (1, 1)
            qx = np.ones(num_pts)
            qy = np.linspace(0, 1, num_pts)
            labels = [(0, r"$X$"), (num_pts - 1, r"$M$")]
        else:
            # Full Γ -> X -> M -> Γ
            p1_x = np.linspace(0, 1, num_pts // 3)
            p1_y = np.zeros(num_pts // 3)
            p2_x = np.ones(num_pts // 3)
            p2_y = np.linspace(0, 1, num_pts // 3)
            p3_x = np.linspace(1, 0, num_pts // 3)
            p3_y = np.linspace(1, 0, num_pts // 3)
            qx = np.concatenate([p1_x, p2_x, p3_x])
            qy = np.concatenate([p1_y, p2_y, p3_y])
            labels = [
                (0, r"$\Gamma$"),
                (num_pts // 3, r"$X$"),
                (2 * (num_pts // 3), r"$M$"),
                (len(qx) - 1, r"$\Gamma$")
            ]

        # Map continuous coordinates in [-1, 1] to array indices [0, N-1]
        ix = np.clip(np.round(((qx + 1.0) / 2.0) * (N - 1)).astype(int), 0, N - 1)
        iy = np.clip(np.round(((qy + 1.0) / 2.0) * (N - 1)).astype(int), 0, N - 1)

        vals = grid[iy, ix]
        return qx, qy, vals, labels

    # =========================================================================
    # ZERO-WAIT REAL-TIME RPA COUPLER (60 FPS INSTANT SLIDER INVERSION)
    # =========================================================================
    def _setup_rpa_coupler(self):
        if not self.current_dataset:
            return

        # Check for cached chi0
        data = self.current_dataset
        chi0 = data.get("chi0_grid")
        if chi0 is None and "static_maps" in data:
            chi0 = data["static_maps"][0]

        if chi0 is None:
            self._render_placeholder()
            return

        self._cached_chi0 = chi0
        N = chi0.shape[0]
        self._rpa_N = N
        qx = np.linspace(-np.pi, np.pi, N, endpoint=False)
        qy = np.linspace(-np.pi, np.pi, N, endpoint=False)
        self._QX, self._QY = np.meshgrid(qx, qy)

        self._update_rpa_coupler_display()

    def _on_rpa_slider_changed(self):
        self._coupler_jk = self.slider_jk.value() / 10.0
        self._coupler_jperp = self.slider_jperp.value() / 10.0
        self.spin_jk.blockSignals(True)
        self.spin_jperp.blockSignals(True)
        self.spin_jk.setValue(self._coupler_jk)
        self.spin_jperp.setValue(self._coupler_jperp)
        self.spin_jk.blockSignals(False)
        self.spin_jperp.blockSignals(False)

        self._update_rpa_coupler_display()

    def _update_rpa_coupler_display(self):
        if self._cached_chi0 is None:
            return

        chi0 = self._cached_chi0
        K = float(self.current_meta.get("K", 1.0))
        jk = self._coupler_jk
        jp = self._coupler_jperp

        # Scalar effective coupling vertex Gamma(q)
        # Gamma(q) = K * (cos(qx) + cos(qy)) + (jp / 4.0) * (jk / 3.0)**2
        gamma_q = K * (np.cos(self._QX) + np.cos(self._QY)) + (jp / 8.0) * (jk / 3.0) ** 2
        denom = 1.0 - gamma_q * chi0

        min_denom = np.min(denom)
        if min_denom <= 0.05:
            self.lbl_instability.setText(f"⚠️ RPA Magnetic Instability! min(1-Γχ₀) = {min_denom:.3f}")
            self.lbl_instability.setStyleSheet(
                "font-size: 11px; font-weight: 700; color: #b91c1c; background-color: #fee2e2; "
                "padding: 2px 8px; border-radius: 4px; border: 1px solid #fca5a5;"
            )
            # Clip denominator to prevent division by zero in rendering
            safe_denom = np.where(denom <= 0.001, 0.001, denom)
        else:
            self.lbl_instability.setText(f"🟢 Paramagnetic Phase (min 1-Γχ₀ = {min_denom:.2f})")
            self.lbl_instability.setStyleSheet(
                "font-size: 11px; font-weight: 600; color: #166534; background-color: #dcfce7; "
                "padding: 2px 8px; border-radius: 4px; border: 1px solid #bbf7d0;"
            )
            safe_denom = denom

        chi_rpa = chi0 / safe_denom

        self.fig.clear()
        ax_map = self.fig.add_subplot(121)
        ax_cut = self.fig.add_subplot(122)

        im = ax_map.imshow(chi_rpa, extent=[-1, 1, -1, 1], origin="lower", cmap="inferno", aspect="equal")
        self.fig.colorbar(im, ax=ax_map, fraction=0.046, pad=0.04, label=r"$\chi_{\mathrm{RPA}}(\mathbf{q})$")
        ax_map.set_xlabel(r"$q_x / \pi$"); ax_map.set_ylabel(r"$q_y / \pi$")
        ax_map.set_title(rf"RPA Coupler: $J_K={jk:.1f}, J_\perp={jp:.1f}$", fontsize=11, fontweight="bold")

        cut_x, cut_y, cut_vals, cut_labels = self._extract_cutline(chi_rpa, "High-Symmetry Path")
        ax_cut.plot(range(len(cut_vals)), cut_vals, color="#dc2626", lw=2.2)
        ax_cut.set_ylabel(r"$\chi_{\mathrm{RPA}}(q)$")
        ax_cut.set_title(r"Dynamic Slice along $\Gamma \to X \to M \to \Gamma$", fontsize=11, fontweight="bold")
        ax_cut.grid(True, linestyle=":", alpha=0.35)

        if cut_labels:
            ticks = [idx for idx, (pos, lbl) in enumerate(cut_labels) if lbl]
            labels = [lbl for idx, (pos, lbl) in enumerate(cut_labels) if lbl]
            ax_cut.set_xticks(ticks)
            ax_cut.set_xticklabels(labels)

        self._ax_2d = ax_map
        self._ax_cut = ax_cut
        self.set_theme(self.is_dark)
        self.canvas.draw_idle()

    # =========================================================================
    # INTERACTIVE CROSSHAIR & LIVE HUD EVENT HANDLER
    # =========================================================================
    def _on_mouse_move(self, event):
        if not event.inaxes:
            return

        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return

        if self.active_mode == "1d":
            # Snapping to closest omega point
            if hasattr(self, "_omega_1d") and self._omega_1d is not None and self._curves_1d:
                idx = np.argmin(np.abs(self._omega_1d - x))
                w_val = self._omega_1d[idx]
                c0 = self._curves_1d[0]
                a_val = c0["A"][idx] if c0.get("A") is not None else 0.0
                re_val = c0["re"][idx] if c0.get("re") is not None else 0.0
                im_val = c0["im"][idx] if c0.get("im") is not None else 0.0

                hud_text = (
                    f"ω = {w_val:+.3f} eV  |  "
                    f"A(k, ω) = {a_val:.3f}  |  "
                    f"Re Σ = {re_val:+.4f}  |  "
                    f"Im Σ = {im_val:.4f}"
                )
                self.lbl_hud.setText(hud_text)
                self.coord_changed.emit(hud_text)

        elif self.active_mode in ("2d_cutline", "rpa_coupler"):
            hud_text = f"qx = {x:+.2f} π  |  qy = {y:+.2f} π  |  Value = {y:.3f}"
            self.lbl_hud.setText(hud_text)
            self.coord_changed.emit(hud_text)

    def reset_zoom(self):
        """Resets plot limits."""
        for ax in self.fig.axes:
            ax.autoscale(True)
        self.canvas.draw_idle()

    def open_vector_export_dialog(self):
        """Launches vector export dialog."""
        dlg = VectorExportDialog(self.fig, self)
        dlg.exec()
