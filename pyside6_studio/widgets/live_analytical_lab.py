"""Live Analytical Physics Lab for Many-Body Studio Pro.

Pillar 3: On-the-fly physics powered by cached foundation arrays (.npz in results/cache/):
1. Interactive Brillouin Zone k-Probe: Click or drag anywhere in [-π, π]² to evaluate A(k, ω), Re Σ, Im Σ in real time (< 1 ms).
2. Continuous J_K slider (0.1 to 12.0) with live 60 FPS analytical scaling.
3. 2D Quasiparticle Weight Map Z(k_x, k_y) across the full Brillouin Zone revealing mass enhancement hot spots.
4. Dynamic energy-sliced Fermi surface movie (slider for energy ω).
5. Live RPA static magnetic susceptibility χ_RPA(q_x, q_y) with real-time instability tracking.
"""

import os
import glob
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QFrame, QSplitter, QStackedWidget,
    QMessageBox, QGroupBox, QDoubleSpinBox
)

from pyside6_studio.core.config import DEFAULT_RESULTS_DIR
from pyside6_studio.core.cache_manager import normalize_results_dir, get_ibz_indices_and_map


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
        self.loaded_base_sigma: dict = {}
        self.loaded_chi0_static: dict = {}

        # Current physics state
        self.active_mode = "k_probe"  # "k_probe", "z_map", "energy_slice", "rpa_susc"
        self.current_kx = np.pi  # Antinodal by default
        self.current_ky = 0.0
        self.current_JK = 6.0
        self.current_omega_slice = 0.0

        self._build_ui()
        self.scan_caches()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # 1. TOP CACHE SELECTOR & EXPERIMENT MODE STRIP
        top_frame = QFrame()
        top_frame.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px;")
        t_lay = QHBoxLayout(top_frame)
        t_lay.setContentsMargins(6, 4, 6, 4)
        t_lay.setSpacing(10)

        t_lay.addWidget(QLabel("Cache Foundation:"))
        self.cb_cache_file = QComboBox()
        self.cb_cache_file.setMinimumWidth(320)
        self.cb_cache_file.currentIndexChanged.connect(self._on_cache_selected)
        t_lay.addWidget(self.cb_cache_file)

        btn_rescan = QPushButton("🔄 Rescan")
        btn_rescan.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        btn_rescan.clicked.connect(self.scan_caches)
        t_lay.addWidget(btn_rescan)

        t_lay.addSpacing(16)

        t_lay.addWidget(QLabel("Analytical Experiment:"))
        self.cb_experiment = QComboBox()
        self.cb_experiment.addItems([
            "🎯 Interactive BZ k-Probe [A(k, ω), Re Σ, Im Σ]",
            "🗺️ 2D Quasiparticle Weight Map Z(k) [Mass Hot Spots]",
            "🌊 Dynamic Energy-Sliced Fermi Surface A(kx, ky, ω)",
            "🧲 Live Static Magnetic Susceptibility χ_RPA(qx, qy)"
        ])
        self.cb_experiment.currentIndexChanged.connect(self._on_experiment_changed)
        t_lay.addWidget(self.cb_experiment)

        t_lay.addStretch()
        lay.addWidget(top_frame)

        # 2. INTERACTIVE CONTROLS BAR (J_K slider, Momentum presets, Energy slice)
        self.ctrl_frame = QFrame()
        self.ctrl_frame.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px;")
        c_lay = QVBoxLayout(self.ctrl_frame)
        c_lay.setContentsMargins(8, 6, 8, 6)
        c_lay.setSpacing(6)

        # Row 1: Continuous J_K Slider + Instant Scaling
        r_jk = QHBoxLayout()
        r_jk.addWidget(QLabel("Continuous J_K Coupling:"))
        self.slider_jk = QSlider(Qt.Horizontal)
        self.slider_jk.setRange(5, 120)  # 0.5 to 12.0
        self.slider_jk.setValue(60)       # 6.0 default
        self.slider_jk.valueChanged.connect(self._on_jk_slider_changed)
        r_jk.addWidget(self.slider_jk, 1)

        self.lbl_jk_val = QLabel("J_K = 6.00")
        self.lbl_jk_val.setStyleSheet("font-weight: 700; color: #1d4ed8; width: 70px;")
        r_jk.addWidget(self.lbl_jk_val)

        # Real-time metrics chip
        r_jk.addSpacing(20)
        self.lbl_live_z = QLabel("⚡ Z(k): —")
        self.lbl_live_z.setStyleSheet("font-weight: 700; color: #0891b2; font-size: 11px;")
        r_jk.addWidget(self.lbl_live_z)

        self.lbl_live_gamma = QLabel("⏱️ Γ(k): —")
        self.lbl_live_gamma.setStyleSheet("font-weight: 700; color: #d97706; font-size: 11px;")
        r_jk.addWidget(self.lbl_live_gamma)

        self.lbl_live_mass = QLabel("⚖️ m*/m: —")
        self.lbl_live_mass.setStyleSheet("font-weight: 700; color: #7c3aed; font-size: 11px;")
        r_jk.addWidget(self.lbl_live_mass)

        c_lay.addLayout(r_jk)

        # Row 2: Momentum Presets & Energy Slider
        self.r_sub = QHBoxLayout()

        # Momentum presets
        self.lbl_mom_title = QLabel("Momentum k:")
        self.r_sub.addWidget(self.lbl_mom_title)

        self.btn_k_antinodal = QPushButton("Antinodal (π, 0)")
        self.btn_k_antinodal.clicked.connect(lambda: self._set_momentum(np.pi, 0.0))
        self.r_sub.addWidget(self.btn_k_antinodal)

        self.btn_k_nodal = QPushButton("Nodal (π/2, π/2)")
        self.btn_k_nodal.clicked.connect(lambda: self._set_momentum(0.5 * np.pi, 0.5 * np.pi))
        self.r_sub.addWidget(self.btn_k_nodal)

        self.btn_k_center = QPushButton("Zone Center (0, 0)")
        self.btn_k_center.clicked.connect(lambda: self._set_momentum(0.0, 0.0))
        self.r_sub.addWidget(self.btn_k_center)

        self.btn_k_corner = QPushButton("Corner (π, π)")
        self.btn_k_corner.clicked.connect(lambda: self._set_momentum(np.pi, np.pi))
        self.r_sub.addWidget(self.btn_k_corner)

        self.r_sub.addSpacing(20)

        # Energy slice slider (for Fermi surface movie)
        self.lbl_slice_title = QLabel("Energy Slice ω:")
        self.lbl_slice_title.setVisible(False)
        self.r_sub.addWidget(self.lbl_slice_title)

        self.slider_slice = QSlider(Qt.Horizontal)
        self.slider_slice.setRange(-200, 200)  # -2.0 to 2.0 eV
        self.slider_slice.setValue(0)
        self.slider_slice.setVisible(False)
        self.slider_slice.valueChanged.connect(self._on_slice_slider_changed)
        self.r_sub.addWidget(self.slider_slice, 1)

        self.lbl_slice_val = QLabel("ω = 0.00 eV")
        self.lbl_slice_val.setVisible(False)
        self.r_sub.addWidget(self.lbl_slice_val)

        self.r_sub.addStretch()
        c_lay.addLayout(self.r_sub)

        lay.addWidget(self.ctrl_frame)

        # 3. INTERACTIVE MATPLOTLIB CANVAS
        self.fig = Figure(figsize=(7, 5), dpi=100)
        self.fig.patch.set_facecolor("#ffffff")
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px;")

        lay.addWidget(self.toolbar)
        lay.addWidget(self.canvas, 1)

        # Connect click event on canvas for interactive k-probing
        self.canvas.mpl_connect("button_press_event", self._on_canvas_clicked)

        self._render_placeholder()

    def set_output_dir(self, out_dir: str):
        self.out_dir = out_dir
        self.scan_caches()

    def scan_caches(self):
        """Scans results/cache/, results/data/, and legacy folders for base Sigma and bare Chi0 arrays."""
        results_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(self.out_dir)
        self.cached_files.clear()
        self.cb_cache_file.blockSignals(True)
        self.cb_cache_file.clear()

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
                if f.startswith("sigma_base"):
                    seen_files.add(f)
                    self.cached_files[f] = ("sigma_base", full_p)
                    self.cb_cache_file.addItem(f"⚡ Base Σ: {f}", full_p)
                elif f.startswith("chi0_static"):
                    seen_files.add(f)
                    self.cached_files[f] = ("chi0_static", full_p)
                    self.cb_cache_file.addItem(f"🧲 Static χ₀: {f}", full_p)
                elif f.startswith("chi0_dynamic"):
                    seen_files.add(f)
                    self.cached_files[f] = ("chi0_dynamic", full_p)
                    self.cb_cache_file.addItem(f"🌊 Dynamic χ₀: {f}", full_p)

        # Fallback to external global dirs only if nothing found in out_dir
        if self.cb_cache_file.count() == 0:
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
                    if f.startswith("sigma_base"):
                        seen_files.add(f)
                        self.cached_files[f] = ("sigma_base", full_p)
                        self.cb_cache_file.addItem(f"⚡ Base Σ: {f}", full_p)
                    elif f.startswith("chi0_static"):
                        seen_files.add(f)
                        self.cached_files[f] = ("chi0_static", full_p)
                        self.cb_cache_file.addItem(f"🧲 Static χ₀: {f}", full_p)
                    elif f.startswith("chi0_dynamic"):
                        seen_files.add(f)
                        self.cached_files[f] = ("chi0_dynamic", full_p)
                        self.cb_cache_file.addItem(f"🌊 Dynamic χ₀: {f}", full_p)

        self.cb_cache_file.blockSignals(False)

        if self.cb_cache_file.count() > 0:
            self._on_cache_selected()
        else:
            self._render_placeholder()

    def _render_placeholder(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.text(
            0.5, 0.5,
            "⚡ No cache foundation arrays found in results/cache/\n\n"
            "Run a spectral sweep or susceptibility calculation to generate base foundation arrays.\n"
            "Once cached, this lab enables real-time 60 FPS continuous J_K scaling, BZ k-probing,\n"
            "and 2D quasiparticle weight Z(k) maps instantaneously!",
            horizontalalignment="center", verticalalignment="center",
            transform=ax.transAxes, color="#64748b", fontsize=11
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
            if self.cb_experiment.currentIndex() == 3:
                self.cb_experiment.blockSignals(True)
                self.cb_experiment.setCurrentIndex(0)
                self.cb_experiment.blockSignals(False)
                self._on_experiment_changed()
                return
        elif ftype == "chi0_static":
            self._load_chi0_static(fpath)
            if self.cb_experiment.currentIndex() != 3:
                self.cb_experiment.blockSignals(True)
                self.cb_experiment.setCurrentIndex(3)
                self.cb_experiment.blockSignals(False)
                self._on_experiment_changed()
                return
        self._recompute_and_render()

    def _load_base_sigma(self, fpath: str):
        try:
            with np.load(fpath) as d:
                is_ibz = bool(d.get("is_ibz", False))
                N = int(d.get("N", 64))
                omega = d["omega"]
                t = float(d.get("t", 1.0))
                t1 = float(d.get("t1", 0.0))
                mu = float(d.get("mu", 1.0))
                eta = float(d.get("eta", 0.08))

                if is_ibz:
                    _, _, full_to_ibz = get_ibz_indices_and_map(N)
                    sig_re = d["sig_re"][:, full_to_ibz].astype(np.float64)
                    sig_im = d["sig_im"][:, full_to_ibz].astype(np.float64)
                else:
                    sig_re = d["sig_re"].astype(np.float64)
                    sig_im = d["sig_im"].astype(np.float64)

                self.loaded_base_sigma = {
                    "fpath": fpath,
                    "N": N, "omega": omega, "t": t, "t1": t1, "mu": mu, "eta": eta,
                    "sig_re": sig_re, "sig_im": sig_im
                }
        except Exception as e:
            QMessageBox.warning(self, "Cache Load Error", f"Could not load Base Sigma array:\n{e}")

    def _load_chi0_static(self, fpath: str):
        try:
            with np.load(fpath) as d:
                self.loaded_chi0_static = {
                    "fpath": fpath,
                    "chi0_grid": d["chi0_grid"],
                    "q_axis": d["q_axis"],
                    "N": int(d.get("N", 64)),
                    "mu": float(d.get("mu", 1.0)),
                    "t": float(d.get("t", 1.0))
                }
        except Exception as e:
            QMessageBox.warning(self, "Cache Load Error", f"Could not load Static Chi0 array:\n{e}")

    def _on_experiment_changed(self):
        idx = self.cb_experiment.currentIndex()
        if idx == 0: self.active_mode = "k_probe"
        elif idx == 1: self.active_mode = "z_map"
        elif idx == 2: self.active_mode = "energy_slice"
        else: self.active_mode = "rpa_susc"

        # Toggle UI controls visibility
        is_k = (self.active_mode == "k_probe")
        is_slice = (self.active_mode == "energy_slice")

        self.lbl_mom_title.setVisible(is_k)
        self.btn_k_antinodal.setVisible(is_k)
        self.btn_k_nodal.setVisible(is_k)
        self.btn_k_center.setVisible(is_k)
        self.btn_k_corner.setVisible(is_k)

        self.lbl_slice_title.setVisible(is_slice)
        self.slider_slice.setVisible(is_slice)
        self.lbl_slice_val.setVisible(is_slice)

        self._recompute_and_render()

    def _on_jk_slider_changed(self, val: int):
        self.current_JK = float(val) / 10.0
        self.lbl_jk_val.setText(f"J_K = {self.current_JK:.2f}")
        self._recompute_and_render()

    def _on_slice_slider_changed(self, val: int):
        self.current_omega_slice = float(val) / 100.0
        self.lbl_slice_val.setText(f"ω = {self.current_omega_slice:.2f} eV")
        self._recompute_and_render()

    def _set_momentum(self, kx: float, ky: float):
        self.current_kx = kx
        self.current_ky = ky
        self._recompute_and_render()

    def _on_canvas_clicked(self, event):
        """Allows clicking on 2D map to set momentum k."""
        if self.active_mode in ("z_map", "energy_slice") and event.xdata is not None and event.ydata is not None:
            self.current_kx = event.xdata
            self.current_ky = event.ydata
            # Switch to k-probe mode to view that clicked point!
            self.cb_experiment.setCurrentIndex(0)

    def _recompute_and_render(self):
        """Dispatches to the active analytical renderer."""
        if self.active_mode == "k_probe":
            self._render_k_probe()
        elif self.active_mode == "z_map":
            self._render_z_map()
        elif self.active_mode == "energy_slice":
            self._render_energy_slice()
        elif self.active_mode == "rpa_susc":
            self._render_rpa_susc()

    # =========================================================================
    # 1. INTERACTIVE BZ K-PROBE: A(k, ω), Re Σ, Im Σ
    # =========================================================================
    def _render_k_probe(self):
        if not self.loaded_base_sigma:
            self._render_placeholder()
            return

        bs = self.loaded_base_sigma
        N = bs["N"]
        omega = bs["omega"]
        t = bs["t"]
        t1 = bs["t1"]
        mu = bs["mu"]
        eta = bs["eta"]

        # Discretize kx, ky to mesh indices
        ikx = int(round((self.current_kx / (2.0 * np.pi)) * N)) % N
        iky = int(round((self.current_ky / (2.0 * np.pi)) * N)) % N
        kx_eff = (ikx / N) * 2.0 * np.pi
        ky_eff = (iky / N) * 2.0 * np.pi

        # Analytical scaling in < 0.1 ms
        scale_fac = self.current_JK ** 2
        sig_re_k = bs["sig_re"][:, ikx, iky] * scale_fac
        sig_im_k = bs["sig_im"][:, ikx, iky] * scale_fac

        # Bare dispersion
        xi_k = -2.0 * t * (np.cos(kx_eff) + np.cos(ky_eff)) - 4.0 * t1 * np.cos(kx_eff) * np.cos(ky_eff) - mu

        # Spectral function A(k, ω)
        denom = (omega - xi_k - sig_re_k) ** 2 + (sig_im_k - eta) ** 2
        A_k = -(1.0 / np.pi) * (sig_im_k - eta) / np.maximum(denom, 1e-12)

        # Quasiparticle Residue Z(k) and Lifetime
        idx_zero = np.argmin(np.abs(omega))
        z_k = None
        if 0 < idx_zero < len(omega) - 1:
            d_re = (sig_re_k[idx_zero + 1] - sig_re_k[idx_zero - 1]) / (omega[idx_zero + 1] - omega[idx_zero - 1])
            if 1.0 - d_re > 1e-4:
                z_k = 1.0 / (1.0 - d_re)

        gamma_k = np.abs(sig_im_k[idx_zero])
        if z_k and 0 < z_k < 10:
            self.lbl_live_z.setText(f"⚡ Z(k): {z_k:.3f}")
            self.lbl_live_mass.setText(f"⚖️ m*/m: {1.0/z_k:.2f}")
        else:
            self.lbl_live_z.setText("⚡ Z(k): —")
            self.lbl_live_mass.setText("⚖️ m*/m: —")

        self.lbl_live_gamma.setText(f"⏱️ Γ(k): {gamma_k:.3f} eV")

        # Render 2-panel plot: (Left: A(k, ω), Right: Re Σ & Im Σ)
        self.fig.clear()
        ax_a = self.fig.add_subplot(121)
        ax_s = self.fig.add_subplot(122)

        k_label = f"k = ({kx_eff/np.pi:.2f}π, {ky_eff/np.pi:.2f}π)"
        ax_a.axvline(0, color="#94a3b8", linestyle="--", linewidth=0.8)
        ax_a.axvline(xi_k, color="#dc2626", linestyle=":", linewidth=0.8, label=f"Bare $\\xi_k = {xi_k:.2f}$")
        ax_a.plot(omega, A_k, color="#2563eb", lw=2.0, label=f"$J_K = {self.current_JK:.1f}$")
        ax_a.set_xlabel(r"$\omega$ [eV]")
        ax_a.set_ylabel(r"$A(\mathbf{k}, \omega)$")
        ax_a.set_title(f"Spectral Function at {k_label}", fontweight="bold", fontsize=11)
        ax_a.grid(True, linestyle=":", alpha=0.35)
        ax_a.legend(frameon=True, fontsize=9)
        ax_a.set_xlim(-4.0, 4.0)

        ax_s.axvline(0, color="#94a3b8", linestyle="--", linewidth=0.8)
        ax_s.plot(omega, sig_re_k, color="#0891b2", lw=1.8, label=r"$\operatorname{Re}\Sigma$")
        ax_s.plot(omega, sig_im_k, color="#d97706", lw=1.8, label=r"$\operatorname{Im}\Sigma$")
        ax_s.set_xlabel(r"$\omega$ [eV]")
        ax_s.set_title(f"Self-Energy ({k_label})", fontweight="bold", fontsize=11)
        ax_s.grid(True, linestyle=":", alpha=0.35)
        ax_s.legend(frameon=True, fontsize=9)
        ax_s.set_xlim(-4.0, 4.0)

        self.fig.tight_layout()
        self.canvas.draw()

    # =========================================================================
    # 2. 2D QUASIPARTICLE WEIGHT MAP Z(kx, ky) OVER BRILLOUIN ZONE
    # =========================================================================
    def _render_z_map(self):
        if not self.loaded_base_sigma:
            self._render_placeholder()
            return

        bs = self.loaded_base_sigma
        N = bs["N"]
        omega = bs["omega"]
        scale_fac = self.current_JK ** 2

        idx_zero = np.argmin(np.abs(omega))
        d_omega = omega[idx_zero + 1] - omega[idx_zero - 1]
        d_re = (bs["sig_re"][idx_zero + 1, :, :] - bs["sig_re"][idx_zero - 1, :, :]) / d_omega * scale_fac

        denom = np.maximum(1.0 - d_re, 0.01)
        z_map = np.clip(1.0 / denom, 0.0, 1.0)

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        im = ax.imshow(
            z_map.T, origin="lower", extent=[-np.pi, np.pi, -np.pi, np.pi],
            cmap="viridis", vmin=0.0, vmax=1.0
        )
        ax.set_xlabel(r"$k_x$")
        ax.set_ylabel(r"$k_y$")
        ax.set_title(rf"Quasiparticle Weight $Z(\mathbf{{k}})$ Map across BZ ($J_K = {self.current_JK:.1f}$)", fontweight="bold")

        # Mark current probed k-point
        ax.plot(self.current_kx, self.current_ky, marker="o", markersize=8, color="#dc2626", markeredgecolor="#ffffff")
        ax.text(self.current_kx + 0.15, self.current_ky + 0.15, "Probed k", color="#dc2626", fontweight="bold", fontsize=9)

        self.fig.colorbar(im, ax=ax, label=r"Residue $Z(\mathbf{k}) \in (0, 1]$")
        self.fig.tight_layout()
        self.canvas.draw()

    # =========================================================================
    # 3. DYNAMIC ENERGY-SLICED FERMI SURFACE A(kx, ky, ω)
    # =========================================================================
    def _render_energy_slice(self):
        if not self.loaded_base_sigma:
            self._render_placeholder()
            return

        bs = self.loaded_base_sigma
        N = bs["N"]
        omega = bs["omega"]
        t = bs["t"]
        t1 = bs["t1"]
        mu = bs["mu"]
        eta = bs["eta"]
        scale_fac = self.current_JK ** 2

        # Nearest frequency index to current slice
        idx_slice = np.argmin(np.abs(omega - self.current_omega_slice))
        w_val = omega[idx_slice]

        # 2D dispersion grid
        kx = np.linspace(-np.pi, np.pi, N, endpoint=False)
        KX, KY = np.meshgrid(kx, kx)
        xi_grid = -2.0 * t * (np.cos(KX) + np.cos(KY)) - 4.0 * t1 * np.cos(KX) * np.cos(KY) - mu

        sig_re_slice = bs["sig_re"][idx_slice, :, :] * scale_fac
        sig_im_slice = bs["sig_im"][idx_slice, :, :] * scale_fac

        denom = (w_val - xi_grid - sig_re_slice) ** 2 + (sig_im_slice - eta) ** 2
        A_slice = -(1.0 / np.pi) * (sig_im_slice - eta) / np.maximum(denom, 1e-12)

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        im = ax.imshow(
            A_slice.T, origin="lower", extent=[-np.pi, np.pi, -np.pi, np.pi],
            cmap="inferno"
        )
        ax.set_xlabel(r"$k_x$")
        ax.set_ylabel(r"$k_y$")
        ax.set_title(rf"Constant Energy Contour $A(\mathbf{{k}}, \omega={w_val:.2f}\text{{ eV}})$ ($J_K = {self.current_JK:.1f}$)", fontweight="bold")

        self.fig.colorbar(im, ax=ax, label=r"$A(\mathbf{k}, \omega)$")
        self.fig.tight_layout()
        self.canvas.draw()

    # =========================================================================
    # 4. LIVE STATIC MAGNETIC SUSCEPTIBILITY χ_RPA(qx, qy)
    # =========================================================================
    def _render_rpa_susc(self):
        if not self.loaded_chi0_static:
            self._render_placeholder()
            return

        cs = self.loaded_chi0_static
        chi0_grid = cs["chi0_grid"]
        q_axis = cs["q_axis"]
        N = cs["N"]

        # Compute Gamma_static for current J_K and J_perp=6.0, K=1.0
        J = 6.0
        JK = self.current_JK
        K = 1.0

        QX, QY = np.meshgrid(q_axis, q_axis)
        k_axis = np.linspace(0, 2 * np.pi, N, endpoint=False)
        KX, KY = np.meshgrid(k_axis, k_axis)
        gamma_bz = 0.5 * (np.cos(KX) + np.cos(KY))

        q_param = 2.0 * K / J
        A_bz = J + 2.0 * gamma_bz
        B_bz = q_param * J * gamma_bz
        bos_bz = J * np.sqrt(np.abs(1.0 + 2.0 * q_param * gamma_bz))
        e1 = np.mean(-0.5 * B_bz / (bos_bz + 1e-12))
        e2 = np.mean(-0.5 + 0.5 * A_bz / (bos_bz + 1e-12))

        bos_q = J * np.sqrt(np.abs(1.0 + q_param * (np.cos(QX) + np.cos(QY))))
        Wq_norm = (J / (bos_q + 1e-12)) * (1.0 / 24.0) * (JK * (1.0 - e1 - 2.0 * e2)) ** 2
        Gamma_static = 2.0 * Wq_norm / (bos_q + 1e-12)

        denom = 1.0 - Gamma_static * chi0_grid
        sus_grid = np.real(chi0_grid / np.maximum(np.abs(denom), 0.005))

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        im = ax.imshow(
            sus_grid.T, origin="lower", extent=[q_axis[0], q_axis[-1], q_axis[0], q_axis[-1]],
            cmap="inferno"
        )
        ax.set_xlabel(r"$q_x$")
        ax.set_ylabel(r"$q_y$")
        ax.set_title(rf"Static Magnetic Susceptibility $\chi_{{\mathrm{{RPA}}}}(\mathbf{{q}})$ ($J_K={JK:.1f}, J_\perp=6.0$)", fontweight="bold")

        min_denom = np.min(denom)
        status_txt = "⚠️ Critical Instability" if min_denom <= 0.05 else f"Instability Gap: {min_denom:.3f}"
        ax.text(0.02, 0.95, status_txt, transform=ax.transAxes, color="#ffffff",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#dc2626" if min_denom <= 0.05 else "#16a34a", alpha=0.8),
                fontweight="bold", fontsize=9)

        self.fig.colorbar(im, ax=ax, label=r"$\chi_{\mathrm{RPA}}(\mathbf{q})$")
        self.fig.tight_layout()
        self.canvas.draw()
