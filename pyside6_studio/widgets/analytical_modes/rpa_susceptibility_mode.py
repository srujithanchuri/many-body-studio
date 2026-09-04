"""
rpa_susceptibility_mode.py
--------------------------
Mode: Static Magnetic Susceptibility χ_RPA(q).

Features:
  - Fast RPA spin susceptibility map from static χ0(q) cache.
  - Stoner instability gap tracking badge with critical instability warning.
  - Symmetrically centered 1:1 square Brillouin Zone aspect ratio matching source code.
  - Clean state on load: NO default pinned points.
  - Interactive hover crosshair with dynamic coordinate badge tracking cursor.
  - Multi-point wavevector pinning (P1, P2, ...) on left-click.
  - Right-click to clear pinned points.
  - High-performance in-place updates for real-time 60 FPS J_K slider scaling.
"""

import numpy as np
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from pyside6_studio.widgets.analytical_modes.base_mode import BaseAnalyticalMode


class StaticSusceptibilityMode(BaseAnalyticalMode):
    """Mode: Static magnetic susceptibility χ_RPA(q) and Stoner instability gap."""

    mode_id = "static_susc"
    display_name = "Static Susceptibility [χ(q)]"
    required_cache_type = "chi0_static"

    def __init__(self, lab):
        super().__init__(lab)
        self.pinned_points: list[tuple[float, float]] = []

        # Persistent artist handles for in-place 60 FPS slider updates
        self.ax_susc = None
        self.im_susc = None
        self.cbar = None
        self.txt_gap = None
        self.title_artist = None

        # Interactive hover crosshair handles
        self.crosshair_h = None
        self.crosshair_v = None
        self.crosshair_text = None
        self._pinned_artists: list = []

    def setup_ui(self):
        self.lab.container_mom.setVisible(False)
        self.lab.container_slice.setVisible(False)
        self.lab.lbl_map_tip.setVisible(True)
        self.lab.lbl_map_tip.setText(
            "💡 Tip: Hover to track wavevector q • Click to pin • Right-click to clear • Drag J_K for live RPA scaling"
        )
        if hasattr(self.lab, "container_wmax"):
            self.lab.container_wmax.setVisible(False)
        self.lab.lbl_live_z.setVisible(False)
        self.lab.lbl_live_gamma.setVisible(False)
        self.lab.lbl_live_mass.setVisible(False)

    def reset_view(self):
        self.clear_pinned_points()

    def fit_view(self):
        self.clear_pinned_points()

    def clear_pinned_points(self):
        """Clears all pinned q coordinates and re-renders the map."""
        self.pinned_points.clear()
        for artist in self._pinned_artists:
            try: artist.remove()
            except Exception: pass
        self._pinned_artists.clear()
        self.render()

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

            # Update Pinned Point Artists
            for artist in self._pinned_artists:
                try: artist.remove()
                except Exception: pass
            self._pinned_artists = []
            for idx, (px, py) in enumerate(self.pinned_points, 1):
                p_line, = self.ax_susc.plot(
                    px, py, marker="o", markersize=7.5,
                    color="#38bdf8", markeredgecolor="#ffffff", markeredgewidth=1.5, zorder=8
                )
                self._pinned_artists.append(p_line)
                offset_x = -0.22 if px > 1.2 else 0.22
                ha = "right" if px > 1.2 else "left"
                offset_y = -0.22 if py > 2.0 else (0.22 if py < -2.0 else 0.1)
                va = "top" if py > 2.0 else ("bottom" if py < -2.0 else "center")
                p_txt = self.ax_susc.text(
                    px + offset_x, py + offset_y,
                    rf"$P_{{{idx}}}({px/np.pi:.2f}\pi, {py/np.pi:.2f}\pi)$",
                    color="#0284c7", fontweight="bold", fontsize=8.0, ha=ha, va=va,
                    bbox=dict(boxstyle="round,pad=0.22", facecolor="#ffffff", edgecolor="#bae6fd", alpha=0.92, lw=0.9),
                    zorder=9
                )
                self._pinned_artists.append(p_txt)

            if getattr(self, "title_artist", None) is not None:
                self.title_artist.set_text(
                    rf"Static Magnetic Susceptibility $\chi_{{\mathrm{{RPA}}}}(\mathbf{{q}})$ ($J_K={JK:.2f}, J_\perp={J:.1f}$)"
                )
            self.canvas.draw_idle()
            return

        # Full figure rebuild: 1:1 square Brillouin zone aspect ratio matching source code
        self.fig.clear()
        self.ax_susc = self.fig.add_subplot(111)
        # Symmetrically enforce square aspect ratio matching source code
        self.ax_susc.set_box_aspect(1.0)

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

        # Interactive hover crosshair (initially hidden)
        self.crosshair_h = self.ax_susc.axhline(0, color="#ffffff", linestyle="--", linewidth=0.85, alpha=0.75, visible=False, zorder=6)
        self.crosshair_v = self.ax_susc.axvline(0, color="#ffffff", linestyle="--", linewidth=0.85, alpha=0.75, visible=False, zorder=6)
        self.crosshair_text = self.ax_susc.text(
            0, 0, "", color="#0284c7", fontweight="bold", fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="#ffffff", edgecolor="#bae6fd", alpha=0.92, lw=0.9),
            visible=False, zorder=7
        )

        # Render pinned points (empty on load - NO default point)
        self._pinned_artists = []
        for idx, (px, py) in enumerate(self.pinned_points, 1):
            p_line, = self.ax_susc.plot(
                px, py, marker="o", markersize=7.5,
                color="#38bdf8", markeredgecolor="#ffffff", markeredgewidth=1.5, zorder=8
            )
            self._pinned_artists.append(p_line)
            offset_x = -0.22 if px > 1.2 else 0.22
            ha = "right" if px > 1.2 else "left"
            offset_y = -0.22 if py > 2.0 else (0.22 if py < -2.0 else 0.1)
            va = "top" if py > 2.0 else ("bottom" if py < -2.0 else "center")
            p_txt = self.ax_susc.text(
                px + offset_x, py + offset_y,
                rf"$P_{{{idx}}}({px/np.pi:.2f}\pi, {py/np.pi:.2f}\pi)$",
                color="#0284c7", fontweight="bold", fontsize=8.0, ha=ha, va=va,
                bbox=dict(boxstyle="round,pad=0.22", facecolor="#ffffff", edgecolor="#bae6fd", alpha=0.92, lw=0.9),
                zorder=9
            )
            self._pinned_artists.append(p_txt)

        self.txt_gap = self.ax_susc.text(
            0.03, 0.94, status_txt, transform=self.ax_susc.transAxes, color="#ffffff",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=bg_color, edgecolor="#ffffff", alpha=0.9, lw=1.0),
            fontweight="bold", fontsize=8.5
        )

        # Colorbar glued directly to the right border of the 1:1 square box
        cax = inset_axes(
            self.ax_susc, width="3.5%", height="100%", loc="lower left",
            bbox_to_anchor=(1.02, 0.0, 1.0, 1.0), bbox_transform=self.ax_susc.transAxes,
            borderpad=0
        )
        self.cbar = self.fig.colorbar(self.im_susc, cax=cax)
        self.cbar.set_label(r"$\chi_{\mathrm{RPA}}(\mathbf{q})$", fontsize=9.5)
        self.cbar.ax.tick_params(labelsize=8.5)

        self.fig.subplots_adjust(left=0.08, right=0.92, bottom=0.11, top=0.90)
        self.canvas.draw()

    def on_motion(self, event) -> bool:
        """Tracks hover crosshair and dynamic q-coordinate badge across the 2D BZ map."""
        if self.ax_susc is None:
            return False

        if event.inaxes == self.ax_susc:
            qx = event.xdata
            qy = event.ydata
            if qx is not None and qy is not None:
                self.crosshair_h.set_ydata([qy, qy])
                self.crosshair_v.set_xdata([qx, qx])
                self.crosshair_h.set_visible(True)
                self.crosshair_v.set_visible(True)

                self.crosshair_text.set_text(rf"$\mathbf{{q}} = ({qx/np.pi:.2f}\pi, {qy/np.pi:.2f}\pi)$")
                offset_x = -0.25 if qx > 1.2 else 0.2
                ha = "right" if qx > 1.2 else "left"
                offset_y = -0.25 if qy > 2.0 else (0.25 if qy < -2.0 else 0.1)
                va = "top" if qy > 2.0 else ("bottom" if qy < -2.0 else "center")
                self.crosshair_text.set_position((qx + offset_x, qy + offset_y))
                self.crosshair_text.set_ha(ha)
                self.crosshair_text.set_va(va)
                self.crosshair_text.set_visible(True)
                self.canvas.draw_idle()
                return True
        else:
            changed = False
            if self.crosshair_h and self.crosshair_h.get_visible():
                self.crosshair_h.set_visible(False)
                changed = True
            if self.crosshair_v and self.crosshair_v.get_visible():
                self.crosshair_v.set_visible(False)
                changed = True
            if self.crosshair_text and self.crosshair_text.get_visible():
                self.crosshair_text.set_visible(False)
                changed = True
            if changed:
                self.canvas.draw_idle()

        return False

    def on_press(self, event) -> bool:
        """Handles map multi-point pinning and right-click clear (matching FS plot)."""
        if event.inaxes == self.ax_susc:
            if event.button == 3:
                # Right-click: clear all pinned points
                self.clear_pinned_points()
                return True
            elif event.button == 1 and event.xdata is not None and event.ydata is not None:
                # Single-click: pin coordinate
                qx = (event.xdata + np.pi) % (2.0 * np.pi) - np.pi
                qy = (event.ydata + np.pi) % (2.0 * np.pi) - np.pi
                self.pinned_points.append((qx, qy))
                self.lab._set_momentum(event.xdata, event.ydata)
                self.render()
                return True
        return False


# Backward-compatible alias
RpaSusceptibilityMode = StaticSusceptibilityMode
