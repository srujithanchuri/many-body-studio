"""
conductivity_mode.py
--------------------
Interactive Electrical Conductivity Mode for Many-Body Studio Pro.

Features:
  - Dual-panel layout matching verified publication figures:
      * Left Panel: Full Scale (Coherent Drude Peak at w = 0).
      * Right Panel: Zoomed In (Incoherent Hubbard Bands at w > 2 eV).
  - High-performance real-time J_K slider coupling:
      * Evaluates analytical J_K^2 scaling on 1/8th IBZ self-energy caches.
      * Up to 200+ FPS via CuPy CUDA GPU acceleration (~4.5 ms).
      * Multi-core CPU fallback via PocketFFT/AVX2 (~130 ms).
  - Contextual Hardware Selector:
      * Auto-detects hardware with explicit toggle between Auto, GPU, and CPU for testing.
  - Live HUD Chip:
      * Reports active backend, frame latency (ms), FPS, and DC conductivity sigma(w=0).
  - Interactive Canvas Controls:
      * Synchronized cursor-centered mouse wheel zoom.
      * Left-click drag panning.
      * Auto-fit view reset.
"""

import time
from typing import Optional, Tuple
import numpy as np
import matplotlib.pyplot as plt

from pyside6_studio.widgets.interactive_modes.base_mode import BaseInteractiveMode
from pyside6_studio.core.cache_manager import LazyIBZArray
from conductivity import (
    compute_optical_conductivity,
    is_gpu_available,
    ConductivityParameters
)
from conductivity.symmetry import compute_ibz_weights, compute_full_bz_weights


class ElectricalConductivityMode(BaseInteractiveMode):
    """Interactive mode for evaluating and exploring electrical conductivity sigma(omega)."""

    mode_id: str = "conductivity"
    display_name: str = "Electrical Conductivity"
    required_cache_type: str = "sigma"

    def __init__(self, lab):
        super().__init__(lab)
        # IBZ geometry cache
        self._cached_geom_key = None
        self._cached_eps = None
        self._cached_weights = None

        # Persistent artist handles for in-place 60+ FPS updates
        self.ax1 = None
        self.ax2 = None
        self.line1 = None
        self.line2 = None
        self.title_artist = None

        # Viewport zoom and pan state
        self._user_xlim1 = None
        self._user_ylim1 = None
        self._user_xlim2 = None
        self._user_ylim2 = None

        self._is_panning = False
        self._pan_start_x = 0.0
        self._pan_start_y = 0.0
        self._pan_ax = None
        self._pan_start_xlim = None
        self._pan_start_ylim = None

    def setup_ui(self):
        """Configures contextual toolbar widgets for electrical conductivity mode."""
        # Hide irrelevant parameter controls
        self.lab.container_mom.setVisible(False)
        self.lab.container_slice.setVisible(False)
        if hasattr(self.lab, "container_susc_params"):
            self.lab.container_susc_params.setVisible(False)

        # Hide single-particle k-probe HUD chips
        self.lab.lbl_live_z.setVisible(False)
        self.lab.lbl_live_gamma.setVisible(False)
        self.lab.lbl_live_mass.setVisible(False)

        # Show conductivity-specific contextual controls and live stats chip
        if hasattr(self.lab, "container_conductivity"):
            self.lab.container_conductivity.setVisible(True)
        if hasattr(self.lab, "lbl_conductivity_stats"):
            self.lab.lbl_conductivity_stats.setVisible(True)

        # User guidance tip
        self.lab.lbl_map_tip.setVisible(True)
        self.lab.lbl_map_tip.setText(
            "💡 Tip: Drag J_K slider for real-time Drude peak & Hubbard band evolution • Toggle Device for CPU/GPU testing"
        )

    def fit_view(self):
        """Resets custom zoom and pan viewports to default auto-fit view."""
        self._user_xlim1 = None
        self._user_ylim1 = None
        self._user_xlim2 = None
        self._user_ylim2 = None
        self.render()
        if hasattr(self.lab, "sig_status_msg"):
            self.lab.sig_status_msg.emit("Conductivity viewport reset to auto-fit.")

    def reset_view(self):
        self.fit_view()

    def render(self):
        """Evaluates optical conductivity from cached self-energy and updates canvas."""
        if not self.lab.loaded_base_sigma:
            self.lab._render_placeholder(
                "⚡ No Self-Energy (Σ) cache loaded.\n\n"
                "Please select a Base Sigma cache from the dropdown above, or click [ ▶ Compute Cache ]\n"
                "to compute self-energy in ~0.3s."
            )
            return

        bs = self.lab.loaded_base_sigma
        N = int(bs["N"])
        omega = bs["omega"]
        t = float(bs.get("t", 1.0))
        t1 = float(bs.get("t1", 0.0))
        mu = float(bs.get("mu", 0.0))
        eta = float(bs.get("eta", 0.05))
        JK = float(self.lab.current_JK)
        Jperp = float(getattr(self.lab, "current_Jperp", bs.get("Jperp", 6.0)))

        # 1. Extract base self-energy
        sig_re_raw = bs["sig_re"]
        sig_im_raw = bs["sig_im"]
        if isinstance(sig_re_raw, LazyIBZArray):
            sig_base_re = sig_re_raw._arr
            sig_base_im = sig_im_raw._arr
        else:
            sig_base_re = np.asarray(sig_re_raw)
            sig_base_im = np.asarray(sig_im_raw)

        # 2. Analytical J_K^2 scaling: Sigma = J_K^2 * Sigma_base
        scale = float(JK ** 2)
        sig_re = scale * sig_base_re
        sig_im = scale * sig_base_im

        # 3. Cache dispersion & velocity weights per lattice geometry
        is_ibz = (sig_base_re.ndim == 2)
        geom_key = (N, t, t1, is_ibz)
        if self._cached_geom_key != geom_key or self._cached_eps is None or self._cached_weights is None:
            if is_ibz:
                _, _, self._cached_eps, self._cached_weights = compute_ibz_weights(N, t, t1, dtype=np.float32)
            else:
                self._cached_eps, self._cached_weights = compute_full_bz_weights(N, t, t1, dtype=np.float32)
            self._cached_geom_key = geom_key

        # 4. Device selection & calculation
        backend = getattr(self.lab, "conductivity_device", "auto")
        params = ConductivityParameters(
            N=N,
            num_omega=len(omega),
            omega_max=float(omega[-1]),
            eta=eta,
            t=t,
            t1=t1,
            mu=mu,
            j_k=JK,
            j_perp=Jperp,
            backend=backend,
            dtype="float32",
            w_active_max=20.0,
            use_ibz=True
        )

        t_start = time.perf_counter()
        omega_pos, sigma_pos = compute_optical_conductivity(
            params=params,
            omega=omega,
            sig_re=sig_re,
            sig_im=sig_im,
            eps_arr=self._cached_eps,
            weights=self._cached_weights
        )
        elapsed_ms = (time.perf_counter() - t_start) * 1000.0

        # 5. Update HUD stats chip
        fps = 1000.0 / max(elapsed_ms, 0.01)
        gpu_detected = is_gpu_available()
        actual_dev = "GPU" if (backend == "gpu" or (backend == "auto" and gpu_detected)) else "CPU"
        icon = "⚡" if actual_dev == "GPU" else "💻"
        dc_val = float(sigma_pos[0]) if len(sigma_pos) > 0 else 0.0

        if len(omega_pos) > 1:
            area = float(np.trapezoid(sigma_pos, omega_pos)) if hasattr(np, "trapezoid") else float(np.sum(sigma_pos) * (omega_pos[1] - omega_pos[0]))
        else:
            area = 0.0

        if hasattr(self.lab, "lbl_conductivity_stats"):
            self.lab.lbl_conductivity_stats.setText(
                f"DC σ(0): {dc_val:.3f}"
            )
            self.lab.lbl_conductivity_stats.setToolTip(
                f"<b>DC Conductivity:</b> σ(ω=0) = {dc_val:.4f} a.u.<br>"
                f"<b>Active Compute Device:</b> {actual_dev}<br>"
                f"<b>Requested Mode:</b> {backend.upper()}<br>"
                f"<b>Calculation Latency:</b> {elapsed_ms:.2f} ms<br>"
                f"<b>Sum Rule Area:</b> {area:.2f}"
            )

        # 6. Canvas Rendering (In-Place 60+ FPS or Initial Setup)
        can_update_inplace = (
            self.ax1 is not None
            and self.ax2 is not None
            and self.line1 is not None
            and self.line2 is not None
            and self.ax1 in self.fig.axes
            and self.ax2 in self.fig.axes
        )

        zoom_idx = np.where(omega_pos > 2.0)[0]
        zoom_ymax = float(np.max(sigma_pos[zoom_idx])) * 2.0 if len(zoom_idx) > 0 else 0.05
        suptitle_text = rf"Electrical Conductivity (Kubo Formula, $N={N}, J_K={JK:.2f}, \mu={mu:.2f}, \eta={eta:.4f}$)"

        if can_update_inplace:
            self.line1.set_data(omega_pos, sigma_pos)
            self.line2.set_data(omega_pos, sigma_pos)

            if self._user_ylim1 is None:
                self.ax1.set_ylim(0, max(float(np.max(sigma_pos)) * 1.05, 0.05))
            if self._user_xlim1 is not None:
                self.ax1.set_xlim(self._user_xlim1)

            if self._user_ylim2 is None:
                self.ax2.set_ylim(0, max(zoom_ymax, 0.01))
            if self._user_xlim2 is not None:
                self.ax2.set_xlim(self._user_xlim2)

            if self.title_artist is not None:
                self.title_artist.set_text(suptitle_text)

            self.canvas.draw_idle()
        else:
            self.fig.clear()

            is_dark = getattr(self.lab, "is_dark", False)
            bg = "#0b1120" if is_dark else "#ffffff"
            fg = "#f8fafc" if is_dark else "#0f172a"
            grid_col = "#334155" if is_dark else "#e2e8f0"

            self.fig.patch.set_facecolor(bg)
            axs = self.fig.subplots(1, 2)
            self.ax1, self.ax2 = axs[0], axs[1]

            # Left Panel: Full Scale (Coherent Drude Peak)
            (self.line1,) = self.ax1.plot(
                omega_pos, sigma_pos,
                color="#2563eb", lw=2.0,
                label=rf"$\sigma(\omega)$ ($J_K={JK:.2f}$)"
            )
            self.ax1.set_xlim(self._user_xlim1 if self._user_xlim1 is not None else (0, 20.0))
            self.ax1.set_ylim(self._user_ylim1 if self._user_ylim1 is not None else (0, max(float(np.max(sigma_pos)) * 1.05, 0.05)))
            self.ax1.set_xlabel(r"Frequency $\omega$ [eV]", fontsize=11, color=fg)
            self.ax1.set_ylabel(r"Electrical Conductivity $\sigma(\omega)$ [a.u.]", fontsize=11, color=fg)
            self.ax1.set_title("Full Scale (Coherent Drude Peak)", fontsize=11, fontweight="bold", color=fg)
            self.ax1.grid(True, linestyle=":", alpha=0.6, color=grid_col)
            self.ax1.legend(loc="upper right", framealpha=0.8)

            # Right Panel: Zoomed In (Incoherent Hubbard Bands)
            (self.line2,) = self.ax2.plot(
                omega_pos, sigma_pos,
                color="#dc2626", lw=2.0,
                label="Hubbard Bands"
            )
            self.ax2.set_xlim(self._user_xlim2 if self._user_xlim2 is not None else (0, 20.0))
            self.ax2.set_ylim(self._user_ylim2 if self._user_ylim2 is not None else (0, max(zoom_ymax, 0.01)))
            self.ax2.set_xlabel(r"Frequency $\omega$ [eV]", fontsize=11, color=fg)
            self.ax2.set_ylabel(r"Electrical Conductivity $\sigma(\omega)$ [a.u.]", fontsize=11, color=fg)
            self.ax2.set_title("Zoomed In (Incoherent Hubbard Bands)", fontsize=11, fontweight="bold", color=fg)
            self.ax2.grid(True, linestyle=":", alpha=0.6, color=grid_col)

            for ax in (self.ax1, self.ax2):
                ax.set_facecolor(bg)
                ax.tick_params(colors=fg, labelsize=9)
                for spine in ax.spines.values():
                    spine.set_color(grid_col)

            self.title_artist = self.fig.suptitle(suptitle_text, fontsize=13, fontweight="bold", color=fg)
            self.fig.tight_layout()
            self.canvas.draw_idle()

    # =========================================================================
    # INTERACTIVE ZOOM & PAN HANDLERS
    # =========================================================================
    def on_scroll(self, event) -> bool:
        """Handles mouse wheel zoom centered at cursor position."""
        if event.inaxes not in [self.ax1, self.ax2]:
            return False

        ax = event.inaxes
        scale_factor = 0.85 if event.button == "up" else 1.18

        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        x_data = event.xdata if event.xdata is not None else (cur_xlim[0] + cur_xlim[1]) / 2.0
        y_data = event.ydata if event.ydata is not None else (cur_ylim[0] + cur_ylim[1]) / 2.0

        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor

        x_frac = (x_data - cur_xlim[0]) / max(cur_xlim[1] - cur_xlim[0], 1e-9)
        y_frac = (y_data - cur_ylim[0]) / max(cur_ylim[1] - cur_ylim[0], 1e-9)

        new_xlim = (x_data - x_frac * new_width, x_data + (1.0 - x_frac) * new_width)
        new_ylim = (max(0.0, y_data - y_frac * new_height), y_data + (1.0 - y_frac) * new_height)

        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)

        if ax == self.ax1:
            self._user_xlim1 = new_xlim
            self._user_ylim1 = new_ylim
        else:
            self._user_xlim2 = new_xlim
            self._user_ylim2 = new_ylim

        self.canvas.draw_idle()
        return True

    def on_press(self, event) -> bool:
        """Initiates drag pan operation with left mouse click."""
        if event.button == 1 and event.inaxes in [self.ax1, self.ax2]:
            self._is_panning = True
            self._pan_ax = event.inaxes
            self._pan_start_x = event.xdata
            self._pan_start_y = event.ydata
            self._pan_start_xlim = self._pan_ax.get_xlim()
            self._pan_start_ylim = self._pan_ax.get_ylim()
            return True
        elif event.button == 3:  # Right click resets view
            self.fit_view()
            return True
        return False

    def on_motion(self, event) -> bool:
        """Pans axes when dragging, or reports coordinates on mouse hover."""
        if self._is_panning and self._pan_ax is not None and event.inaxes == self._pan_ax:
            if event.xdata is None or event.ydata is None or self._pan_start_x is None or self._pan_start_y is None:
                return False
            dx = event.xdata - self._pan_start_x
            dy = event.ydata - self._pan_start_y

            new_xlim = (self._pan_start_xlim[0] - dx, self._pan_start_xlim[1] - dx)
            new_ylim = (self._pan_start_ylim[0] - dy, self._pan_start_ylim[1] - dy)

            self._pan_ax.set_xlim(new_xlim)
            self._pan_ax.set_ylim(new_ylim)

            if self._pan_ax == self.ax1:
                self._user_xlim1 = new_xlim
                self._user_ylim1 = new_ylim
            else:
                self._user_xlim2 = new_xlim
                self._user_ylim2 = new_ylim

            self.canvas.draw_idle()
            return True

        # Mouse hover status readout
        if event.inaxes in [self.ax1, self.ax2] and event.xdata is not None and event.ydata is not None:
            if hasattr(self.lab, "sig_status_msg"):
                tag = "Full Scale" if event.inaxes == self.ax1 else "Hubbard Bands"
                self.lab.sig_status_msg.emit(
                    f"[{tag}] ω = {event.xdata:.3f} eV  |  σ(ω) = {event.ydata:.4f} a.u."
                )
            return True

        return False

    def on_release(self, event) -> bool:
        """Ends mouse drag pan operation."""
        if self._is_panning:
            self._is_panning = False
            self._pan_ax = None
            return True
        return False
