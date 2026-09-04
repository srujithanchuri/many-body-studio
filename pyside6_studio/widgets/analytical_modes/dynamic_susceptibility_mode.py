"""
dynamic_susceptibility_mode.py
------------------------------
Mode: Interactive Energy-Momentum Dynamic RPA Susceptibility [-Im χ_RPA(q, ω)].

Features:
  - Vectorized live evaluation of -Im χ_RPA(q, ω) along Γ(0,0) -> X(π,0) -> M(π,π) -> Γ(0,0).
  - Continuous 60 FPS slider scaling of J_K and J_perp.
  - Overlaid collective triplon excitation dispersion Ω(q) (cyan dotted curve).
  - Exact source aspect ratio, high-symmetry path partitioning, and vertical guide lines.
  - Interactive wheel zoom and drag panning.
"""

import numpy as np
import matplotlib.colors as mcolors
from matplotlib import ticker

from pyside6_studio.widgets.analytical_modes.base_mode import BaseAnalyticalMode


class DynamicSusceptibilityMode(BaseAnalyticalMode):
    """Mode: Interactive Energy-Momentum Dynamic RPA Susceptibility [-Im χ_RPA(q, ω)]."""

    mode_id = "dynamic_susc"
    display_name = "Dynamic Susceptibility [χ(q, ω)]"
    required_cache_type = "chi0_dynamic"

    def __init__(self, lab):
        super().__init__(lab)
        self.w_max: float = 10.0

        # Viewport zoom / pan tracking
        self._user_xlim = None
        self._user_ylim = None
        self._pan_start = None

        # Matplotlib persistent artist handles for in-place 60 FPS updates
        self.ax_dyn = None
        self.im_dyn = None
        self.line_triplon = None
        self.cbar = None
        self.title_artist = None

    def setup_ui(self):
        self.lab.container_mom.setVisible(False)
        self.lab.container_slice.setVisible(False)
        self.lab.lbl_map_tip.setVisible(True)
        self.lab.lbl_map_tip.setText(
            "💡 Tip: Dynamic susceptibility along Γ(0,0) → X(π,0) → M(π,π) → Γ(0,0) • Scroll to zoom, drag to pan"
        )
        if hasattr(self.lab, "container_wmax"):
            self.lab.container_wmax.setVisible(False)
        self.lab.lbl_live_z.setVisible(False)
        self.lab.lbl_live_gamma.setVisible(False)
        self.lab.lbl_live_mass.setVisible(False)

    def fit_view(self):
        self._user_xlim = None
        self._user_ylim = None
        self.render()
        self.lab.sig_status_msg.emit("Dynamic susceptibility view reset to full path.")

    def reset_view(self):
        self.fit_view()

    def render(self):
        dyn_data = getattr(self.lab, "loaded_chi0_dynamic", None)
        if not dyn_data or "chi0_master" not in dyn_data:
            self.lab._render_placeholder(
                "⚡ No Dynamic χ₀ cache loaded.\n\n"
                "Please select a Dynamic χ₀ array from the Cache dropdown above, or compute one in\n"
                "the Susceptibility tab to unlock real-time collective spin excitation spectra!"
            )
            return

        chi0_master = dyn_data["chi0_master"]
        Q_path_x = dyn_data["Q_path_x"]
        Q_path_y = dyn_data["Q_path_y"]
        omegas = dyn_data["omegas"]
        N = dyn_data.get("N", 100)
        eta = dyn_data.get("eta", 0.01)

        J = float(dyn_data.get("Jperp", 6.0))
        JK = float(self.lab.current_JK)
        K_coupling = float(dyn_data.get("K", 1.0))

        # 1. Compute bosonic background & triplon dispersion Ω(q)
        k_axis_bos = np.linspace(0, 2 * np.pi, N, endpoint=False)
        KX_BOS, KY_BOS = np.meshgrid(k_axis_bos, k_axis_bos)
        gamma_bz_bos = 0.5 * (np.cos(KX_BOS) + np.cos(KY_BOS))
        gam_path = 0.5 * (np.cos(Q_path_x) + np.cos(Q_path_y))

        q_param = 2.0 * K_coupling / J
        bos_path = J * np.sqrt(np.abs(1.0 + (4.0 * K_coupling / J) * gam_path))

        A_bz_bos = J + 2.0 * gamma_bz_bos
        B_bz_bos = q_param * J * gamma_bz_bos
        bos_bz_bos = J * np.sqrt(np.abs(1.0 + 2.0 * q_param * gamma_bz_bos))
        e1_dyn = np.mean(-0.5 * B_bz_bos / (bos_bz_bos + 1e-12))
        e2_dyn = np.mean(-0.5 + 0.5 * A_bz_bos / (bos_bz_bos + 1e-12))

        # 2. Ultra-fast Vectorized RPA evaluation (<10 ms)
        Mq_sq = (J / (bos_path[None, :] + 1e-12)) * ((JK * (1.0 - e1_dyn - 2.0 * e2_dyn)) ** 2) / 24.0
        w_grid = omegas[:, None]
        Gamma1 = -Mq_sq / (w_grid - bos_path[None, :] + 1j * eta)
        Gamma2 = -Mq_sq / (-w_grid - bos_path[None, :] + 1j * eta)
        denom = 1.0 - (Gamma1 + Gamma2) * chi0_master
        chi_full = chi0_master / np.where(np.abs(denom) < 1e-4, 1e-4, denom)
        spectral_map = np.imag(chi_full)
        spectral_map = np.nan_to_num(spectral_map, nan=0.0, posinf=0.0, neginf=0.0)
        spectral_map = np.maximum(spectral_map, 0.0)

        num_q = len(Q_path_x)
        w_min = float(omegas[0])
        w_max = float(omegas[-1])
        self.w_max = w_max

        vmax = float(np.percentile(spectral_map, 99.2)) if spectral_map.size > 0 else 1.0
        if vmax <= 1e-5:
            vmax = 1.0

        # High-symmetry path tick positions matching source sweeper.py
        # Path segments: Γ(0,0) -> X(π,0) -> M(π,π) -> Γ(0,0)
        ticks = [0, N - 1, 2 * (N - 1), num_q - 1]
        tick_labels = [r"$\Gamma(0,0)$", r"$X(\pi,0)$", r"$M(\pi,\pi)$", r"$\Gamma(0,0)$"]

        # Check if in-place artist update is possible
        can_update_inplace = (
            self.ax_dyn is not None
            and self.im_dyn is not None
            and self.line_triplon is not None
            and len(self.fig.axes) >= 1
            and getattr(self.im_dyn, 'get_array', lambda: None)() is not None
            and self.im_dyn.get_array().shape == spectral_map.shape
        )

        if can_update_inplace:
            self.im_dyn.set_data(spectral_map)
            self.im_dyn.set_clim(vmin=0, vmax=vmax)
            self.line_triplon.set_data(np.arange(num_q), bos_path)
            default_ylim = (w_min, w_max)
            self.ax_dyn.set_ylim(self._user_ylim if self._user_ylim is not None else default_ylim)
            if getattr(self, "title_artist", None) is not None:
                self.title_artist.set_text(
                    rf"Dynamic Susceptibility $-\mathrm{{Im}}\chi(\mathbf{{q}}, \omega)$ along Path ($J_K = {JK:.2f}, J_\perp = {J:.1f}$)"
                )
            self.canvas.draw_idle()
            return

        # Full figure rebuild: Symmetrically centered single-panel layout matching source code
        self.fig.clear()

        gs = self.fig.add_gridspec(
            1, 2, width_ratios=[1.0, 0.026],
            left=0.08, right=0.91, bottom=0.11, top=0.90, wspace=0.025
        )
        self.ax_dyn = self.fig.add_subplot(gs[0, 0])
        cax = self.fig.add_subplot(gs[0, 1])

        extent = [0, num_q - 1, w_min, w_max]
        self.im_dyn = self.ax_dyn.imshow(
            spectral_map,
            origin="lower",
            extent=extent,
            cmap="magma",
            aspect="auto",
            vmin=0,
            vmax=vmax,
            interpolation="nearest"
        )

        # Overlay cyan dotted triplon dispersion
        self.line_triplon = self.ax_dyn.plot(
            np.arange(num_q), bos_path,
            color="cyan", linestyle=":", linewidth=2.0,
            label=r"$\Omega(\mathbf{q})$ (triplon)"
        )[0]

        # High-symmetry path dividers & ticks
        self.ax_dyn.set_xticks(ticks)
        self.ax_dyn.set_xticklabels(tick_labels, fontsize=9.5)
        for xt in ticks:
            self.ax_dyn.axvline(x=xt, color="white", linestyle="--", alpha=0.35, linewidth=0.85)

        self.ax_dyn.set_xlabel(r"$\mathbf{q}\ \mathrm{path}$", fontsize=10.5, labelpad=6)
        self.ax_dyn.set_ylabel(r"$\omega\ [\mathrm{eV}]$", fontsize=10.5, labelpad=6)

        default_xlim = (0, num_q - 1)
        default_ylim = (w_min, w_max)
        self.ax_dyn.set_xlim(self._user_xlim if self._user_xlim is not None else default_xlim)
        self.ax_dyn.set_ylim(self._user_ylim if self._user_ylim is not None else default_ylim)

        self.title_artist = self.fig.suptitle(
            rf"Dynamic Susceptibility $-\mathrm{{Im}}\chi(\mathbf{{q}}, \omega)$ along Path ($J_K = {JK:.2f}, J_\perp = {J:.1f}$)",
            fontweight="bold", fontsize=12, y=0.96
        )
        self.ax_dyn.legend(loc="upper right", fontsize=9.5, framealpha=0.85)

        # Colorbar
        self.cbar = self.fig.colorbar(self.im_dyn, cax=cax)
        self.cbar.set_label(r"$-\mathrm{Im}\chi(\mathbf{q}, \omega)$", fontsize=10)
        self.cbar.ax.tick_params(labelsize=8.5)

        self.canvas.draw()

    def on_scroll(self, event) -> bool:
        if event.inaxes != self.ax_dyn or event.xdata is None or event.ydata is None:
            return False

        scale_factor = 0.85 if event.button == "up" else 1.18
        cur_xlim = self.ax_dyn.get_xlim()
        cur_ylim = self.ax_dyn.get_ylim()

        x_left = event.xdata - (event.xdata - cur_xlim[0]) * scale_factor
        x_right = event.xdata + (cur_xlim[1] - event.xdata) * scale_factor
        y_bottom = event.ydata - (event.ydata - cur_ylim[0]) * scale_factor
        y_top = event.ydata + (cur_ylim[1] - event.ydata) * scale_factor

        self._user_xlim = (x_left, x_right)
        self._user_ylim = (y_bottom, y_top)
        self.ax_dyn.set_xlim(self._user_xlim)
        self.ax_dyn.set_ylim(self._user_ylim)
        self.canvas.draw_idle()
        return True

    def on_press(self, event) -> bool:
        if event.inaxes == self.ax_dyn and event.button in [1, 2]:
            self._pan_start = (event.xdata, event.ydata)
            return True
        return False

    def on_motion(self, event) -> bool:
        if self._pan_start is not None and event.inaxes == self.ax_dyn:
            if event.xdata is None or event.ydata is None:
                return False
            dx = event.xdata - self._pan_start[0]
            dy = event.ydata - self._pan_start[1]
            cur_xlim = self.ax_dyn.get_xlim()
            cur_ylim = self.ax_dyn.get_ylim()

            self._user_xlim = (cur_xlim[0] - dx, cur_xlim[1] - dx)
            self._user_ylim = (cur_ylim[0] - dy, cur_ylim[1] - dy)
            self.ax_dyn.set_xlim(self._user_xlim)
            self.ax_dyn.set_ylim(self._user_ylim)
            self.canvas.draw_idle()
            return True
        return False

    def on_release(self, event) -> bool:
        if self._pan_start is not None:
            self._pan_start = None
            return True
        return False
