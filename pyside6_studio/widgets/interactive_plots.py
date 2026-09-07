"""Interactive Plots Studio for Many-Body Studio Pro.

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
    QSizePolicy, QToolButton, QMenu
)

from pyside6_studio.core.config import DEFAULT_RESULTS_DIR
from pyside6_studio.core.cache_manager import (
    normalize_results_dir,
    get_ibz_indices_and_map,
    byte_unshuffle_f32,
    LazyIBZArray
)
from pyside6_studio.widgets.interactive_modes import (
    BaseInteractiveMode,
    SpectralFunctionMode,
    EnergySliceMode,
    BandDispersionMode,
    StaticSusceptibilityMode,
    DynamicSusceptibilityMode,
    RpaSusceptibilityMode,
    ElectricalConductivityMode,
)
from pyside6_studio.widgets.foundation_cache_dialog import FoundationCacheDialog
from pyside6_studio.widgets.interactive_plot_theme import apply_interactive_plot_theme


def format_smart_cache_label(fname: str, ftype: str) -> str:
    """
    Creates concise, human-friendly, physics-rich cache labels that consume minimal space.
    - For Sigma (self-energy): Displays mu, J_perp, K, and N: Σ (μ=0.0, J⊥=6.0, K=1.0, N=100)
    - For Static/Dynamic Susceptibility: Displays mu and N: Static χ₀ (μ=1.0, N=100)
    """
    import re
    if ftype == "sigma_base" or fname.startswith("sigma_base"):
        jp_match = re.search(r"Jperp_([0-9.]+)", fname) or re.search(r"J_perp_([0-9.]+)", fname)
        k_match = re.search(r"(?<![a-zA-Z])(?<![jJ]_)[kK]_([0-9.-]+)", fname) or re.search(r"(?<![a-zA-Z])(?<![jJ]_)[kK]([0-9.-]+)", fname)
        n_match = re.search(r"N_([0-9]+)", fname) or re.search(r"N([0-9]+)", fname)
        mu_match = re.search(r"mu_([0-9.-]+)", fname) or re.search(r"mu([0-9.-]+)", fname)
        parts = []
        if mu_match:
            try: parts.append(f"μ={float(mu_match.group(1)):.1f}")
            except ValueError: parts.append(f"μ={mu_match.group(1)}")
        if jp_match:
            try: parts.append(f"J⊥={float(jp_match.group(1)):.1f}")
            except ValueError: parts.append(f"J⊥={jp_match.group(1)}")
        if k_match:
            try: parts.append(f"K={float(k_match.group(1)):.1f}")
            except ValueError: parts.append(f"K={k_match.group(1)}")
        if n_match:
            parts.append(f"N={n_match.group(1)}")
        param_str = f" ({', '.join(parts)})" if parts else ""
        return f"Σ{param_str}"

    elif ftype == "chi0_static" or fname.startswith("chi0_static"):
        n_match = re.search(r"N_([0-9]+)", fname) or re.search(r"N([0-9]+)", fname)
        mu_match = re.search(r"mu_([0-9.-]+)", fname) or re.search(r"mu([0-9.-]+)", fname)
        parts = []
        if mu_match:
            try: parts.append(f"μ={float(mu_match.group(1)):.1f}")
            except ValueError: parts.append(f"μ={mu_match.group(1)}")
        if n_match:
            parts.append(f"N={n_match.group(1)}")
        param_str = f" ({', '.join(parts)})" if parts else ""
        return f"Static χ₀{param_str}"

    elif ftype == "chi0_dynamic" or fname.startswith("chi0_dynamic"):
        n_match = re.search(r"N_([0-9]+)", fname) or re.search(r"N([0-9]+)", fname)
        mu_match = re.search(r"mu_([0-9.-]+)", fname) or re.search(r"mu([0-9.-]+)", fname)
        parts = []
        if mu_match:
            try: parts.append(f"μ={float(mu_match.group(1)):.1f}")
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
        "K": None,
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
    k_match = re.search(r"(?<![a-zA-Z])(?<![jJ]_)[kK]_([0-9.-]+)", fname) or re.search(r"(?<![a-zA-Z])(?<![jJ]_)[kK]([0-9.-]+)", fname)
    if k_match:
        try: meta["K"] = float(k_match.group(1))
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


from pyside6_studio.widgets.interactive_plot_controls import ModernComboBox, build_interactive_plot_ui


class InteractivePlotsWidget(QWidget):
    """
    On-The-Fly Theoretical Physics Lab.
    Uses cached Base Sigma or Bare Chi0 to evaluate physical observables instantaneously.
    """
    sig_status_msg = Signal(str)
    sig_send_to_sweeper = Signal(dict)

    def __init__(self, out_dir: str = DEFAULT_RESULTS_DIR, parent=None):
        super().__init__(parent)
        self.setObjectName("InteractivePlotsWidget")
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
        self.conductivity_device = "auto"

        # Modular Analytical Mode Handlers
        self.modes: dict[str, BaseInteractiveMode] = {
            "k_probe": SpectralFunctionMode(self),
            "energy_slice": EnergySliceMode(self),
            "band_dispersion": BandDispersionMode(self),
            "rpa_susc": StaticSusceptibilityMode(self),
            "static_susc": StaticSusceptibilityMode(self),
            "dynamic_susc": DynamicSusceptibilityMode(self),
            "conductivity": ElectricalConductivityMode(self),
        }
        self.mode_order = ["k_probe", "energy_slice", "band_dispersion", "static_susc", "dynamic_susc", "conductivity"]
        # Inherit theme from parent window or application palette
        is_dark = False
        if parent and hasattr(parent, "is_dark"):
            is_dark = parent.is_dark
        else:
            app = QApplication.instance()
            if app:
                is_dark = getattr(app, "is_dark", False) or (app.palette().window().color().lightness() < 128)
        self.is_dark = is_dark

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

    def _themed_draw(self, *args, **kwargs):
        self.apply_theme_to_fig()
        return self._orig_canvas_draw(*args, **kwargs)

    def _themed_draw_idle(self, *args, **kwargs):
        self.apply_theme_to_fig()
        return self._orig_canvas_draw_idle(*args, **kwargs)

    def apply_theme_to_fig(self):
        """Applies dark or light theme to Matplotlib Figure, axes, spines, labels, and legends."""
        if not hasattr(self, "fig"):
            return
        is_dark = getattr(self, "is_dark", False)
        bg = "#0b1120" if is_dark else "#ffffff"
        fg = "#f8fafc" if is_dark else "#0f172a"
        grid_col = "#334155" if is_dark else "#cbd5e1"
        ax_bg = "#0f172a" if is_dark else "#ffffff"

        self.fig.patch.set_facecolor(bg)
        if hasattr(self.fig, "_suptitle") and self.fig._suptitle:
            self.fig._suptitle.set_color(fg)

        for ax in self.fig.axes:
            ax.set_facecolor(ax_bg)
            ax.tick_params(colors=fg, which="both")
            for spine in ax.spines.values():
                spine.set_color(grid_col)
            if ax.xaxis and ax.xaxis.label:
                ax.xaxis.label.set_color(fg)
            if ax.yaxis and ax.yaxis.label:
                ax.yaxis.label.set_color(fg)
            if ax.title:
                ax.title.set_color(fg)

            for txt in ax.texts:
                orig_col = txt.get_color()
                bbox = txt.get_bbox_patch()
                if is_dark:
                    if bbox:
                        fc = bbox.get_facecolor()
                        if hasattr(fc, "__len__") and len(fc) >= 3 and fc[0] > 0.85 and fc[1] > 0.85 and fc[2] > 0.85:
                            bbox.set_facecolor("#1e293b")
                            bbox.set_edgecolor("#334155")
                    if orig_col in ("#0f172a", "#1e293b", "#000000", "black", "k", "#0284c7", "#0369a1", "#065f46"):
                        txt.set_color("#38bdf8")
                    elif orig_col in ("#64748b", "#475569"):
                        txt.set_color("#94a3b8")
                else:
                    if orig_col in ("#f8fafc", "#e2e8f0", "#ffffff", "white", "w"):
                        txt.set_color("#0f172a")

            leg = ax.get_legend()
            if leg:
                frame = leg.get_frame()
                if frame:
                    frame.set_facecolor("#1e293b" if is_dark else "#ffffff")
                    frame.set_edgecolor(grid_col)
                for t in leg.get_texts():
                    t.set_color(fg)
                if leg.get_title():
                    leg.get_title().set_color(fg)

    def set_theme(self, is_dark: bool):
        apply_interactive_plot_theme(self, is_dark)

    @property
    def current_mode(self) -> BaseInteractiveMode:
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
        build_interactive_plot_ui(self)

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
            val_str = f"{m:.1f}" if m == round(m, 1) else f"{m:g}"
            self.cb_filter_mu.addItem(val_str)

        # Preserve user's typed value only if it exists in the active mode's caches
        valid_mus = [f"{m:.1f}" if m == round(m, 1) else f"{m:g}" for m in sorted_mus]
        if curr_text and curr_text in valid_mus:
            self.cb_filter_mu.setEditText(curr_text)
        else:
            self.cb_filter_mu.setCurrentIndex(0)
            if self.cb_filter_mu.lineEdit():
                self.cb_filter_mu.lineEdit().clear()
        self.cb_filter_mu.blockSignals(False)
        self._suppress_mu_filter = False

    def _populate_cache_dropdown(self, load_cache: bool = True, render: bool = True):
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
            if load_cache:
                self._on_cache_selected(render=render)
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
                        "K": meta["K"],
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
                "▶ No matching cache found in results/cache/\n\n"
                "Click [ ▶ Compute Cache ] in the toolbar above to directly evaluate\n"
                "a self-energy Σ or bare χ₀ array in ~0.3s.\n\n"
                "Once evaluated, explore 60 FPS J_K scaling, k-probing,\n"
                "and RPA instabilities instantaneously without running batch sweeps!"
            )
        txt_col = "#94a3b8" if getattr(self, "is_dark", False) else "#64748b"
        ax.text(
            0.5, 0.5,
            msg,
            horizontalalignment="center", verticalalignment="center",
            transform=ax.transAxes, color=txt_col, fontsize=10.5, linespacing=1.4
        )
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_frame_on(False)
        self.canvas.draw_idle()

    def _open_compute_cache_dialog(self):
        """Opens the in-situ compute cache dialog for the active mode."""
        target_cat = "sigma_base"
        if self.active_mode in ["rpa_susc", "static_susc"]:
            target_cat = "chi0_static"
        elif self.active_mode == "dynamic_susc":
            target_cat = "chi0_dynamic"

        curr_mu = 0.0
        try:
            mu_txt = self.cb_filter_mu.currentText().strip()
            if mu_txt:
                curr_mu = float(mu_txt)
        except Exception:
            curr_mu = 0.0

        self._foundation_dlg = FoundationCacheDialog(
            parent=self,
            out_dir=self.out_dir,
            default_category=target_cat,
            default_mu=curr_mu,
            default_jperp=self.current_Jperp,
            default_k=getattr(self, "current_K", 1.0)
        )
        self._foundation_dlg.sig_cache_generated.connect(self._on_foundation_cache_generated)
        self._foundation_dlg.show()

    def _quick_synthesize_foundation(self, category: str, N: int):
        """Quickly opens and configures FoundationCacheDialog with selected preset."""
        curr_mu = 0.0
        try:
            mu_txt = self.cb_filter_mu.currentText().strip()
            if mu_txt:
                curr_mu = float(mu_txt)
        except Exception:
            curr_mu = 0.0

        self._foundation_dlg = FoundationCacheDialog(
            parent=self,
            out_dir=self.out_dir,
            default_category=category,
            default_mu=curr_mu,
            default_jperp=self.current_Jperp,
            default_k=getattr(self, "current_K", 1.0)
        )
        if N == 100:
            self._foundation_dlg.cb_n.setCurrentIndex(0)
        elif N == 256:
            self._foundation_dlg.cb_n.setCurrentIndex(1)
        elif N == 64:
            self._foundation_dlg.cb_n.setCurrentIndex(2)

        self._foundation_dlg.sig_cache_generated.connect(self._on_foundation_cache_generated)
        self._foundation_dlg.show()

    def _on_foundation_cache_generated(self, cache_path: str):
        """Rescans cache list and auto-selects newly generated cache array."""
        self.scan_caches()
        if cache_path:
            target_base = os.path.basename(cache_path)
            for i in range(self.cb_cache_file.count()):
                item_p = self.cb_cache_file.itemData(i)
                if item_p == cache_path or (item_p and target_base in os.path.basename(str(item_p))):
                    self.cb_cache_file.setCurrentIndex(i)
                    break
        self.sig_status_msg.emit("⚡ Cache ready & loaded into Interactive Plots.")

    def _on_send_to_sweeper(self):
        """Dispatches active exploration parameters to Simulation Studio Parameter Dock."""
        active_mu = 0.0
        if self.loaded_base_sigma and "mu" in self.loaded_base_sigma:
            try: active_mu = float(self.loaded_base_sigma["mu"])
            except Exception: pass
        elif hasattr(self, "cb_filter_mu"):
            try: active_mu = float(self.cb_filter_mu.currentText().strip())
            except Exception: pass

        params = {
            "mu": active_mu,
            "JK": float(self.current_JK),
            "Jperp": float(self.current_Jperp),
            "K": float(self.current_K),
            "active_mode": self.active_mode
        }
        if self.loaded_base_sigma and "N" in self.loaded_base_sigma:
            try: params["N"] = int(self.loaded_base_sigma["N"])
            except Exception: pass
        elif self.loaded_chi0_static and "N" in self.loaded_chi0_static:
            try: params["N"] = int(self.loaded_chi0_static["N"])
            except Exception: pass

        self.sig_send_to_sweeper.emit(params)
        self.sig_status_msg.emit(f"🚀 Sent parameters (μ={params['mu']:.1f}, J_K={params['JK']:.2f}, J_⊥={params['Jperp']:.1f}) to Simulation Studio Parameter Dock.")

    def _on_cache_selected(self, render: bool = True):
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
        if render:
            self._recompute_and_render()

    def _load_base_sigma(self, fpath: str):
        """
        Robustly loads base self-energy foundations across all archive generations:
        1. 8-bit bit-groomed byte-shuffled 1/8th IBZ ('sig_re_shuf', 'sig_im_shuf', 'shape')
        2. Unshuffled 1/8th IBZ ('sig_re', 'sig_im', is_ibz=True)
        3. Full BZ flat ('sig_re', 'sig_im')
        4. Legacy 2-loop separate ('sig1_re' + 'sig3_re', 'sig1_im' + 'sig3_im')
        """
        if self.loaded_base_sigma and self.loaded_base_sigma.get("fpath") == fpath:
            return
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

                k_match = re.search(r"(?<![a-zA-Z])(?<![jJ]_)[kK]_([0-9.-]+)", os.path.basename(fpath)) or re.search(r"(?<![a-zA-Z])(?<![jJ]_)[kK]([0-9.-]+)", os.path.basename(fpath))
                if k_match:
                    try: K_val = float(k_match.group(1))
                    except ValueError: K_val = float(d.get("K", 1.0))
                else:
                    K_val = float(d.get("K", 1.0))
                self.current_K = K_val

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
                    "Jperp": Jperp, "K": K_val,
                    "sig_re": sig_re, "sig_im": sig_im
                }
        except Exception as e:
            print(f"[CACHE LOAD ERROR] Failed loading {fpath}: {e}")
            if self.isVisible():
                QMessageBox.warning(self, "Cache Load Error", f"Could not load Base Sigma array:\n{e}")

    def _load_chi0_static(self, fpath: str):
        if self.loaded_chi0_static and self.loaded_chi0_static.get("fpath") == fpath:
            return
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
                    self.slider_jperp.setValue(int(round(np.clip(Jperp * 100, 401, 1200))))
                    self.slider_jperp.blockSignals(False)
                    self.current_Jperp = Jperp
                    self.lbl_jperp_val.setText(f"J_⊥ = {Jperp:.2f}")
        except Exception as e:
            print(f"[CACHE LOAD ERROR] Failed loading {fpath}: {e}")
            if self.isVisible():
                QMessageBox.warning(self, "Cache Load Error", f"Could not load Static Chi0 array:\n{e}")

    def _load_chi0_dynamic(self, fpath: str):
        if self.loaded_chi0_dynamic and self.loaded_chi0_dynamic.get("fpath") == fpath:
            return
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
                    self.slider_jperp.setValue(int(round(np.clip(Jperp * 100, 401, 1200))))
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

        # Hide conductivity controls by default (shown by conductivity_mode.setup_ui)
        if hasattr(self, "container_conductivity"):
            self.container_conductivity.setVisible(False)
        if hasattr(self, "lbl_conductivity_stats"):
            self.lbl_conductivity_stats.setVisible(False)

        # Update available mu values for the active mode and populate cache dropdown without duplicate render
        self._update_mu_filter_options()
        self._populate_cache_dropdown(load_cache=True, render=False)

        self.current_mode.setup_ui()
        self._recompute_and_render()

    def _on_device_changed(self, idx: int):
        val = self.cb_device.currentData()
        self.conductivity_device = str(val) if val is not None else "auto"
        if self.active_mode == "conductivity":
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
        self.current_Jperp = float(val) / 100.0
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
                self.slider_jperp.setValue(600)
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

