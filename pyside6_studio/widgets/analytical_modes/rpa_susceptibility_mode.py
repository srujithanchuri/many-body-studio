"""
rpa_susceptibility_mode.py
--------------------------
Mode: Static Magnetic Susceptibility χ_RPA(q).

Features:
  - Fast RPA spin susceptibility map from static χ0(q) cache.
  - Stoner instability gap tracking badge with critical instability warning.
  - Interactive click-to-probe q-point on the map.
  - Symmetrically centered 1:1 square Brillouin Zone aspect ratio.
  - High-performance in-place updates for real-time 60 FPS J_K slider scaling.
"""

import numpy as np
from mpl_toolkits.axes_grid1 import make_axes_locatable
from pyside6_studio.widgets.analytical_modes.base_mode import BaseAnalyticalMode


class StaticSusceptibilityMode(BaseAnalyticalMode):
    """Mode: Static magnetic susceptibility χ_RPA(q) and Stoner instability gap."""

    mode_id = "static_susc"
    display_name = "Static Susceptibility [χ(q)]"
    required_cache_type = "chi0_static"

    def __init__(self, lab):
        super().__init__(lab)
        # Persistent artist handles for in-place 60 FPS slider updates
        self.ax_susc = None
        self.im_susc = None
        self.cbar = None
        self.pt_probe = None
        self.txt_probe = None
        self.txt_gap = None
        self.title_artist = None

    def setup_ui(self):
        self.lab.container_mom.setVisible(False)
        self.lab.container_slice.setVisible(False)
        self.lab.lbl_map_tip.setVisible(True)
        self.lab.lbl_map_tip.setText(
            "💡 Tip: Click anywhere in the Brillouin Zone to probe wavevector q • Drag J_K to track Stoner instability"
        )
        if hasattr(self.lab, "container_wmax"):
            self.lab.container_wmax.setVisible(False)
        self.lab.lbl_live_z.setVisible(False)
        self.lab.lbl_live_gamma.setVisible(False)
        self.lab.lbl_live_mass.setVisible(False)

    def render(self):
        if not self.lab.loaded_chi0_static:
            self.lab._render_placeholder(
                "⚡ No Static χ₀ cache loaded.\n\n"
                "Please select a Static χ₀ array from the Cache dropdown above, or compute one in\n"
                "the Susceptibility tab to unlock real-time Stoner instability and BZ peak maps!"
            )
            return

        cs = self.lab.loaded_chi0_static
        chi0_grid = cs["chi0_grid"]
        q_axis = cs["q_axis"]
        N = cs["N"]

        # Compute Gamma_static for current J_K and J_perp=6.0, K=1.0
        J = float(cs.get("Jperp", 6.0))
        JK = float(self.lab.current_JK)
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

        min_denom = float(np.min(denom))
        status_txt = "⚠️ Critical Instability" if min_denom <= 0.05 else f"Instability Gap: {min_denom:.3f}"
        bg_color = "#dc2626" if min_denom <= 0.05 else "#15803d"

        # Check probed q-point coordinates
        kx_disp = (self.lab.current_kx + np.pi) % (2.0 * np.pi) - np.pi
        ky_disp = (self.lab.current_ky + np.pi) % (2.0 * np.pi) - np.pi
        in_bounds = (q_axis[0] <= kx_disp <= q_axis[-1]) and (q_axis[0] <= ky_disp <= q_axis[-1])

        # Check if in-place artist update is possible
        can_update_inplace = (
            self.ax_susc is not None
            and self.im_susc is not None
            and len(self.fig.axes) >= 1
            and getattr(self.im_susc, "get_array", lambda: None)() is not None
            and self.im_susc.get_array().shape == sus_grid.T.shape
        )

        if can_update_inplace:
            self.im_susc.set_data(sus_grid.T)
            self.im_susc.set_clim(vmin=float(np.nanmin(sus_grid)), vmax=float(np.nanmax(sus_grid)))

            if self.txt_gap is not None:
                self.txt_gap.set_text(status_txt)
                self.txt_gap.set_bbox(dict(boxstyle="round,pad=0.3", facecolor=bg_color, edgecolor="#ffffff", alpha=0.9, lw=1.0))

            if self.pt_probe is not None and self.txt_probe is not None:
                if in_bounds:
                    self.pt_probe.set_data([kx_disp], [ky_disp])
                    self.pt_probe.set_visible(True)
                    offset_x = -0.25 if kx_disp > 1.2 else 0.2
                    ha = "right" if kx_disp > 1.2 else "left"
                    offset_y = -0.25 if ky_disp > 2.0 else (0.25 if ky_disp < -2.0 else 0.1)
                    va = "top" if ky_disp > 2.0 else ("bottom" if ky_disp < -2.0 else "center")
                    self.txt_probe.set_position((kx_disp + offset_x, ky_disp + offset_y))
                    self.txt_probe.set_text(rf"$\mathbf{{q}} = ({kx_disp/np.pi:.2f}\pi, {ky_disp/np.pi:.2f}\pi)$")
                    self.txt_probe.set_ha(ha)
                    self.txt_probe.set_va(va)
                    self.txt_probe.set_visible(True)
                else:
                    self.pt_probe.set_visible(False)
                    self.txt_probe.set_visible(False)

            if getattr(self, "title_artist", None) is not None:
                self.title_artist.set_text(
                    rf"Static Magnetic Susceptibility $\chi_{{\mathrm{{RPA}}}}(\mathbf{{q}})$ ($J_K={JK:.2f}, J_\perp={J:.1f}$)"
                )
            self.canvas.draw_idle()
            return

        # Full figure rebuild: 1:1 square Brillouin zone aspect ratio matching source code
        self.fig.clear()
        self.ax_susc = self.fig.add_subplot(111)
        self.ax_susc.set_box_aspect(1)

        self.im_susc = self.ax_susc.imshow(
            sus_grid.T, origin="lower", extent=[q_axis[0], q_axis[-1], q_axis[0], q_axis[-1]],
            cmap="inferno", interpolation="nearest"
        )
        self.ax_susc.set_xlabel(r"$q_x$", fontsize=10.5, labelpad=6)
        self.ax_susc.set_ylabel(r"$q_y$", fontsize=10.5, labelpad=6)
        self.title_artist = self.ax_susc.set_title(
            rf"Static Magnetic Susceptibility $\chi_{{\mathrm{{RPA}}}}(\mathbf{{q}})$ ($J_K={JK:.2f}, J_\perp={J:.1f}$)",
            fontweight="bold", fontsize=11.5, pad=10
        )

        # Mark current probed q-point
        if in_bounds:
            self.pt_probe = self.ax_susc.plot(
                kx_disp, ky_disp, marker="o", markersize=7, color="#38bdf8",
                markeredgecolor="#ffffff", markeredgewidth=1.5, zorder=5
            )[0]
            offset_x = -0.25 if kx_disp > 1.2 else 0.2
            ha = "right" if kx_disp > 1.2 else "left"
            offset_y = -0.25 if ky_disp > 2.0 else (0.25 if ky_disp < -2.0 else 0.1)
            va = "top" if ky_disp > 2.0 else ("bottom" if ky_disp < -2.0 else "center")
            self.txt_probe = self.ax_susc.text(
                kx_disp + offset_x, ky_disp + offset_y,
                rf"$\mathbf{{q}} = ({kx_disp/np.pi:.2f}\pi, {ky_disp/np.pi:.2f}\pi)$",
                color="#0284c7", fontweight="bold", fontsize=8.5, ha=ha, va=va,
                bbox=dict(boxstyle="round,pad=0.25", facecolor="#ffffff", edgecolor="#bae6fd", alpha=0.92, lw=0.9),
                zorder=6
            )
        else:
            self.pt_probe = self.ax_susc.plot([], [], marker="o", markersize=7, color="#38bdf8")[0]
            self.txt_probe = self.ax_susc.text(0, 0, "", visible=False)

        self.txt_gap = self.ax_susc.text(
            0.03, 0.94, status_txt, transform=self.ax_susc.transAxes, color="#ffffff",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=bg_color, edgecolor="#ffffff", alpha=0.9, lw=1.0),
            fontweight="bold", fontsize=8.5
        )

        divider = make_axes_locatable(self.ax_susc)
        cax = divider.append_axes("right", size="3.8%", pad=0.14)
        self.cbar = self.fig.colorbar(self.im_susc, cax=cax)
        self.cbar.set_label(r"$\chi_{\mathrm{RPA}}(\mathbf{q})$", fontsize=9.5)
        self.cbar.ax.tick_params(labelsize=8.5)

        self.fig.tight_layout()
        self.canvas.draw()

    def on_press(self, event) -> bool:
        if event.xdata is None or event.ydata is None or event.button != 1:
            return False
        self.lab._set_momentum(event.xdata, event.ydata)
        return True


# Backward-compatible alias
RpaSusceptibilityMode = StaticSusceptibilityMode
