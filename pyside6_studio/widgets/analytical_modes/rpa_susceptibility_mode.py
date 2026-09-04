"""
rpa_susceptibility_mode.py
--------------------------
Mode 2: Static Magnetic Susceptibility χ_RPA(q).
Features:
  - Fast RPA spin susceptibility map from static χ0(q) cache.
  - Stoner instability gap tracking badge with critical instability warning.
  - Interactive click-to-probe q-point on the map.
"""

import numpy as np
from mpl_toolkits.axes_grid1 import make_axes_locatable
from pyside6_studio.widgets.analytical_modes.base_mode import BaseAnalyticalMode


class RpaSusceptibilityMode(BaseAnalyticalMode):
    """Mode 2: Static magnetic susceptibility χ_RPA(q) and Stoner instability gap."""

    mode_id = "rpa_susc"
    display_name = "Magnetic Susceptibility χ_RPA"
    required_cache_type = "chi0"

    def setup_ui(self):
        self.lab.container_mom.setVisible(False)
        self.lab.container_slice.setVisible(False)
        self.lab.lbl_map_tip.setVisible(True)
        if hasattr(self.lab, "container_wmax"):
            self.lab.container_wmax.setVisible(False)
        self.lab.lbl_live_z.setVisible(False)
        self.lab.lbl_live_gamma.setVisible(False)
        self.lab.lbl_live_mass.setVisible(False)

    def render(self):
        if not self.lab.loaded_chi0_static:
            self.lab._render_placeholder()
            return

        cs = self.lab.loaded_chi0_static
        chi0_grid = cs["chi0_grid"]
        q_axis = cs["q_axis"]
        N = cs["N"]

        # Compute Gamma_static for current J_K and J_perp=6.0, K=1.0
        J = 6.0
        JK = self.lab.current_JK
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
        ax.set_box_aspect(1)

        im = ax.imshow(
            sus_grid.T, origin="lower", extent=[q_axis[0], q_axis[-1], q_axis[0], q_axis[-1]],
            cmap="inferno", interpolation="nearest"
        )
        ax.set_xlabel(r"$q_x$", fontsize=10)
        ax.set_ylabel(r"$q_y$", fontsize=10)
        ax.set_title(
            rf"Static Magnetic Susceptibility $\chi_{{\mathrm{{RPA}}}}(\mathbf{{q}})$ ($J_K={JK:.1f}, J_\perp={J:.1f}$)",
            fontweight="bold", fontsize=11, pad=10
        )

        # Mark current probed q-point
        kx_disp = (self.lab.current_kx + np.pi) % (2.0 * np.pi) - np.pi
        ky_disp = (self.lab.current_ky + np.pi) % (2.0 * np.pi) - np.pi
        if q_axis[0] <= kx_disp <= q_axis[-1] and q_axis[0] <= ky_disp <= q_axis[-1]:
            ax.plot(kx_disp, ky_disp, marker="o", markersize=7, color="#38bdf8", markeredgecolor="#ffffff", markeredgewidth=1.5, zorder=5)
            offset_x = -0.25 if kx_disp > 1.2 else 0.2
            ha = "right" if kx_disp > 1.2 else "left"
            offset_y = -0.25 if ky_disp > 2.0 else (0.25 if ky_disp < -2.0 else 0.1)
            va = "top" if ky_disp > 2.0 else ("bottom" if ky_disp < -2.0 else "center")
            ax.text(
                kx_disp + offset_x, ky_disp + offset_y,
                rf"$\mathbf{{q}} = ({kx_disp/np.pi:.2f}\pi, {ky_disp/np.pi:.2f}\pi)$",
                color="#0284c7", fontweight="bold", fontsize=8.5, ha=ha, va=va,
                bbox=dict(boxstyle="round,pad=0.25", facecolor="#ffffff", edgecolor="#bae6fd", alpha=0.92, lw=0.9),
                zorder=6
            )

        min_denom = np.min(denom)
        status_txt = "⚠️ Critical Instability" if min_denom <= 0.05 else f"Instability Gap: {min_denom:.3f}"
        bg_color = "#dc2626" if min_denom <= 0.05 else "#15803d"
        ax.text(
            0.03, 0.94, status_txt, transform=ax.transAxes, color="#ffffff",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=bg_color, edgecolor="#ffffff", alpha=0.9, lw=1.0),
            fontweight="bold", fontsize=8.5
        )

        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="3.8%", pad=0.12)
        cbar = self.fig.colorbar(im, cax=cax)
        cbar.set_label(r"$\chi_{\mathrm{RPA}}(\mathbf{q})$", fontsize=9)
        cbar.ax.tick_params(labelsize=8)

        self.fig.tight_layout()
        self.canvas.draw()

    def on_press(self, event) -> bool:
        if event.xdata is None or event.ydata is None or event.button != 1:
            return False
        self.lab._set_momentum(event.xdata, event.ydata)
        return True
