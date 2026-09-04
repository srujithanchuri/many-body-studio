"""
energy_slice_mode.py
--------------------
Mode 1: Dual-Panel DOS and Fermi Surface [A(k, ω)].
Features:
  - Side-by-side visualization:
      * Left: 2D Brillouin Zone contour A(k, ω = ω_slice) with interactive hover crosshair
        and multi-point momentum pinning (P1, P2, ...).
      * Right: Full Integrated Density of States ρ(ω) vs ω with live slice indicator,
        interactive mouse tracker with curve intersection readout, and click-to-slice navigation.
  - Interactive controls:
      * Hover over 2D map: crosshair (kx, ky) tracks cursor with dynamic coordinate badge.
      * Single-click on 2D map: pins momentum point (can pin multiple points).
      * Right-click on 2D map: clears all pinned points.
      * Double-click on 2D map: jumps to Mode 0 (Spectral Function) at the probed point.
      * Hover over DOS: vertical guide line tracks mouse and snaps intersection dot to ρ(ω),
        displaying (ω, ρ) readout.
      * Click on DOS: sets energy slice ω_slice directly to clicked energy.
"""

import numpy as np
from mpl_toolkits.axes_grid1 import make_axes_locatable
from pyside6_studio.widgets.analytical_modes.base_mode import BaseAnalyticalMode
from pyside6_studio.core.cache_manager import get_ibz_indices_and_map, LazyIBZArray

try:
    from numba import njit, prange
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

if HAS_NUMBA:
    @njit(parallel=True, fastmath=True)
    def _compute_dos_numba_kernel(w_arr, xi_ibz, sr_ibz, si_ibz, weights, eta, inv_pi, scale_fac):
        Nw = len(w_arr)
        N_ibz = len(xi_ibz)
        dos = np.zeros(Nw, dtype=np.float32)
        for iw in prange(Nw):
            w_val = w_arr[iw]
            s = 0.0
            for ik in range(N_ibz):
                sr = sr_ibz[iw, ik] * scale_fac
                si = si_ibz[iw, ik] * scale_fac
                d_re = w_val - xi_ibz[ik] - sr
                d_im = si - eta
                denom = d_re * d_re + d_im * d_im
                if denom < 1e-12:
                    denom = 1e-12
                s += (-inv_pi * d_im / denom) * weights[ik]
            dos[iw] = s
        return dos

    # JIT warm-up on import so first slider scrub is instantaneous
    try:
        _compute_dos_numba_kernel(
            np.zeros(2, dtype=np.float32),
            np.zeros(2, dtype=np.float32),
            np.zeros((2, 2), dtype=np.float32),
            np.zeros((2, 2), dtype=np.float32),
            np.zeros(2, dtype=np.float32),
            np.float32(0.01),
            np.float32(1.0 / np.pi),
            np.float32(1.0),
        )
    except Exception:
        pass



class EnergySliceMode(BaseAnalyticalMode):
    """Mode 1: Dual-Panel DOS / Fermi Surface [A(k, ω)]."""

    mode_id = "energy_slice"
    display_name = "Fermi Surface / DOS"
    required_cache_type = "sigma"

    def __init__(self, lab):
        super().__init__(lab)
        self.pinned_points: list[tuple[float, float]] = []
        self.show_slice_indicator: bool = False

        # Cached DOS curve to ensure ultra-fast slider scrubbing
        self._cached_dos_key = None
        self._current_omega = None
        self._current_dos = None
        self._cached_y_max_dos = 0.35

        # Matplotlib interactive handles
        self.ax_map = None
        self.ax_dos = None
        self.crosshair_h = None
        self.crosshair_v = None
        self.crosshair_text = None
        self.dos_cursor_line = None
        self.dos_dot = None
        self.dos_annot = None

    def setup_ui(self):
        self.lab.container_mom.setVisible(False)
        self.lab.container_slice.setVisible(True)
        if hasattr(self.lab, "container_susc_params"):
            self.lab.container_susc_params.setVisible(False)
        self.lab.lbl_map_tip.setText(
            "💡 Tip: Click map to pin k • Right-click map clears • "
            "Click DOS to slice • Right-click DOS resets • Double-click map opens A(k, ω)"
        )
        self.lab.lbl_map_tip.setVisible(True)
        if hasattr(self.lab, "container_wmax"):
            self.lab.container_wmax.setVisible(False)
        self.lab.lbl_live_z.setVisible(False)
        self.lab.lbl_live_gamma.setVisible(False)
        self.lab.lbl_live_mass.setVisible(False)

    def reset_view(self):
        """Resets pinned points, hides slice indicator, and restores default viewports."""
        self.pinned_points.clear()
        self.show_slice_indicator = False
        if hasattr(self.lab, "slider_slice"):
            self.lab.slider_slice.blockSignals(True)
            self.lab.slider_slice.setValue(0)
            self.lab.slider_slice.blockSignals(False)
            self.lab.current_omega_slice = 0.0
            self.lab.lbl_slice_val.setText("ω = 0.00 eV")
        self.render()

    def fit_view(self):
        self.reset_view()

    def clear_pinned_points(self):
        """Clears all pinned k-space coordinates and re-renders the map."""
        self.pinned_points.clear()
        self.render()

    def render(self):
        if not self.lab.loaded_base_sigma:
            self.lab._render_placeholder()
            return

        bs = self.lab.loaded_base_sigma
        N = bs["N"]
        omega = bs["omega"]
        t = bs["t"]
        t1 = bs["t1"]
        mu = bs["mu"]
        eta = bs["eta"]
        scale_fac = self.lab.current_JK ** 2

        # -----------------------------------------------------------------
        # 1. 2D Map Slice Calculation: A(k, ω = ω_slice)
        # -----------------------------------------------------------------
        idx_slice = int(np.argmin(np.abs(omega - self.lab.current_omega_slice)))
        w_val = float(omega[idx_slice])

        # Cache bare dispersion grid (independent of JK and omega_slice)
        # Built on FFT grid [0, 2π) and fftshifted for display on [-π, π]
        if getattr(self, "_cached_xi_id", None) != (id(bs), N, t, t1, mu):
            k_fft = np.arange(N, dtype=np.float64) * (2.0 * np.pi / N)
            px, py = np.meshgrid(k_fft, k_fft, indexing="ij")
            xi_fft = -2.0 * t * (np.cos(px) + np.cos(py)) - 4.0 * t1 * (np.cos(px) * np.cos(py)) - mu
            self._cached_xi_grid = np.fft.fftshift(xi_fft)
            self._cached_xi_id = (id(bs), N, t, t1, mu)
        xi_grid = self._cached_xi_grid

        sig_r = bs["sig_re"]
        sig_i = bs["sig_im"]
        if sig_r.ndim == 2:
            sig_r = sig_r.reshape((len(omega), N, N))
            sig_i = sig_i.reshape((len(omega), N, N))

        # Enforce strict zero for Imag self-energy at Fermi surface (matching physics solver)
        w0_idx = int(np.argmin(np.abs(omega)))
        if getattr(self, "_cached_sig_id", None) != id(bs):
            if hasattr(sig_i, "_arr"):
                # Fast zero-copy path on 1/8th IBZ representation (< 5 ms, 0 GB RAM ballooning)
                clean_arr = sig_i._arr - sig_i._arr[w0_idx:w0_idx + 1, :]
                self._sig_im_clean = LazyIBZArray(clean_arr, sig_i._map, N)
                self._sig_i_ibz = clean_arr
                self._sig_r_ibz = sig_r._arr
            else:
                self._sig_im_clean = sig_i - sig_i[w0_idx:w0_idx + 1, :, :]
                self._sig_i_ibz = None
                self._sig_r_ibz = None
            self._cached_sig_id = id(bs)
        sig_i_clean = self._sig_im_clean

        sig_re_slice = np.fft.fftshift(sig_r[idx_slice, :, :] * scale_fac)
        sig_im_slice = np.fft.fftshift(sig_i_clean[idx_slice, :, :] * scale_fac)

        denom_slice = (w_val - xi_grid - sig_re_slice) ** 2 + (sig_im_slice - eta) ** 2
        A_slice = -(1.0 / np.pi) * (sig_im_slice - eta) / np.maximum(denom_slice, 1e-12)

        # -----------------------------------------------------------------
        # 2. Integrated Density of States Calculation: ρ(ω) = (1/N^2) Σ_k A(k, ω)
        # Full Brillouin Zone integration via 1/8th IBZ symmetry weights (zero subsampling)
        # -----------------------------------------------------------------
        is_dragging = getattr(self.lab, "slider_jk", None) is not None and self.lab.slider_jk.isSliderDown()
        cache_key = (id(bs), scale_fac, is_dragging if not HAS_NUMBA else False)
        if cache_key != self._cached_dos_key or self._current_dos is None:
            if getattr(self, "_cached_ibz_id", None) != (id(bs), N, t, t1, mu):
                rows, cols, full_to_ibz = get_ibz_indices_and_map(N)
                self._ibz_rows = rows
                self._ibz_cols = cols
                self._ibz_weights = np.bincount(full_to_ibz.ravel(), minlength=len(rows)).astype(np.float32)
                kx_ibz = np.array(rows, dtype=np.float32) * (2.0 * np.pi / N)
                ky_ibz = np.array(cols, dtype=np.float32) * (2.0 * np.pi / N)
                self._xi_ibz = -2.0 * t * (np.cos(kx_ibz) + np.cos(ky_ibz)) - 4.0 * t1 * (np.cos(kx_ibz) * np.cos(ky_ibz)) - mu
                if self._sig_r_ibz is None:
                    self._sig_r_ibz = np.ascontiguousarray(sig_r[:, rows, cols], dtype=np.float32)
                    self._sig_i_ibz = np.ascontiguousarray(sig_i_clean[:, rows, cols], dtype=np.float32)
                else:
                    self._sig_r_ibz = np.ascontiguousarray(self._sig_r_ibz, dtype=np.float32)
                    self._sig_i_ibz = np.ascontiguousarray(self._sig_i_ibz, dtype=np.float32)
                self._cached_ibz_id = (id(bs), N, t, t1, mu)

            xi_ibz = self._xi_ibz
            weights = self._ibz_weights
            sig_r_ibz = self._sig_r_ibz
            sig_i_ibz = self._sig_i_ibz
            Nw = len(omega)

            # Interactive drag throttle: only needed for fallback NumPy path.
            # With Numba JIT, full BZ integration on N=256, Nw=8001 executes in ~10 ms (60+ FPS),
            # eliminating any need for subsampling or striding during dragging.
            if not HAS_NUMBA and is_dragging and N >= 128 and Nw > 1200:
                mask_core = np.abs(omega) <= 3.0
                idx_core = np.where(mask_core)[0]
                idx_tails = np.where(~mask_core)[0][::6]
                drag_indices = np.sort(np.concatenate([idx_core, idx_tails]))
                w_eval = omega[drag_indices].astype(np.float32)
                sr_eval = sig_r_ibz[drag_indices]
                si_eval = sig_i_ibz[drag_indices]
            else:
                w_eval = omega.astype(np.float32)
                sr_eval = sig_r_ibz
                si_eval = sig_i_ibz

            Nw_eval = len(w_eval)
            w_weights = (weights / (N * N)).astype(np.float32)
            inv_pi = np.float32(1.0 / np.pi)

            dos_res = None
            if HAS_NUMBA:
                try:
                    w_f32 = np.ascontiguousarray(w_eval, dtype=np.float32)
                    xi_f32 = np.ascontiguousarray(xi_ibz, dtype=np.float32)
                    sr_f32 = np.ascontiguousarray(sr_eval, dtype=np.float32)
                    si_f32 = np.ascontiguousarray(si_eval, dtype=np.float32)
                    dos_res = _compute_dos_numba_kernel(
                        w_f32,
                        xi_f32,
                        sr_f32,
                        si_f32,
                        w_weights,
                        np.float32(eta),
                        inv_pi,
                        np.float32(scale_fac),
                    )
                except Exception:
                    dos_res = None

            if dos_res is None:
                # Vectorized NumPy multi-core fallback
                dos_res = np.zeros(Nw_eval, dtype=np.float32)
                chunk_size = 1500
                for start in range(0, Nw_eval, chunk_size):
                    end = min(start + chunk_size, Nw_eval)
                    w_c = w_eval[start:end, None]
                    sr = sr_eval[start:end] * scale_fac
                    si = si_eval[start:end] * scale_fac
                    denom = (w_c - xi_ibz[None, :] - sr) ** 2 + (si - eta) ** 2
                    A = -inv_pi * (si - eta) / np.maximum(denom, 1e-12)
                    dos_res[start:end] = A.dot(w_weights)

            self._current_dos = dos_res.astype(np.float64)
            self._current_omega = w_eval.astype(np.float64)
            self._cached_dos_key = cache_key

        # Compute and cache maximum DOS peak height at J_K = 0.5 for stable, fixed y-axis
        if getattr(self, "_cached_max_rho_id", None) != id(bs):
            scale_fac_05 = 0.5 ** 2
            mask_near_ef = np.abs(omega) <= 5.0
            w_near = omega[mask_near_ef].astype(np.float32)
            step_p = max(1, len(w_near) // 300)
            w_p = w_near[::step_p]
            sr_p = sig_r_ibz[mask_near_ef][::step_p] * scale_fac_05
            si_p = sig_i_ibz[mask_near_ef][::step_p] * scale_fac_05
            w_c_p = w_p[:, None]
            denom_p = (w_c_p - xi_ibz[None, :] - sr_p) ** 2 + (si_p - eta) ** 2
            A_p = -(1.0 / np.pi) * (si_p - eta) / np.maximum(denom_p, 1e-12)
            dos_05 = A_p.dot(w_weights)
            peak_05 = float(np.max(dos_05)) if len(dos_05) > 0 else 0.3
            self._cached_y_max_dos = max(peak_05 * 1.15, 0.25)
            self._cached_max_rho_id = id(bs)

        y_max_dos = self._cached_y_max_dos

        dos = self._current_dos
        omega_dos = self._current_omega
        rho_slice = float(np.interp(w_val, omega_dos, dos))

        # Always plot exact, un-decimated DOS vertices (eliminating artificial peak blunting on mouse release)
        w_disp, dos_disp = omega_dos, dos

        can_update_inplace = (
            self.ax_map is not None
            and self.ax_dos is not None
            and self.ax_map in self.fig.axes
            and self.ax_dos in self.fig.axes
            and getattr(self, "im", None) is not None
            and getattr(self.im, "get_array", lambda: None)() is not None
            and self.im.get_array().shape == A_slice.T.shape
        )

        w_max_dos = 15.0

        if can_update_inplace:
            # Ultra-fast in-place artist updates (avoids rebuilding the entire figure)
            self.im.set_data(A_slice.T)
            self.im.set_clim(vmin=float(np.min(A_slice)), vmax=float(np.max(A_slice)))
            self.ax_map.set_title(
                rf"Fermi Surface $A(\mathbf{{k}}, \omega={w_val:.2f}\text{{ eV}})$",
                fontweight="bold", fontsize=10.5, pad=8
            )

            # Update Pinned Point Artists
            for artist in getattr(self, "_pinned_artists", []):
                try: artist.remove()
                except Exception: pass
            self._pinned_artists = []
            for idx, (px, py) in enumerate(self.pinned_points, 1):
                px_disp = (px + np.pi) % (2.0 * np.pi) - np.pi
                py_disp = (py + np.pi) % (2.0 * np.pi) - np.pi
                p_line, = self.ax_map.plot(
                    px_disp, py_disp, marker="o", markersize=7.5,
                    color="#38bdf8", markeredgecolor="#ffffff", markeredgewidth=1.5, zorder=8
                )
                self._pinned_artists.append(p_line)
                offset_x = -0.22 if px_disp > 1.2 else 0.22
                ha = "right" if px_disp > 1.2 else "left"
                offset_y = -0.22 if py_disp > 2.0 else (0.22 if py_disp < -2.0 else 0.1)
                va = "top" if py_disp > 2.0 else ("bottom" if py_disp < -2.0 else "center")
                p_txt = self.ax_map.text(
                    px_disp + offset_x, py_disp + offset_y,
                    rf"$P_{{{idx}}}({px_disp/np.pi:.2f}\pi, {py_disp/np.pi:.2f}\pi)$",
                    color="#0284c7", fontweight="bold", fontsize=8.0, ha=ha, va=va,
                    bbox=dict(boxstyle="round,pad=0.22", facecolor="#ffffff", edgecolor="#bae6fd", alpha=0.92, lw=0.9),
                    zorder=9
                )
                self._pinned_artists.append(p_txt)

            # Update DOS line & fill
            self.line_dos.set_data(w_disp, dos_disp)
            if hasattr(self, "fill_dos") and self.fill_dos is not None:
                try: self.fill_dos.remove()
                except Exception: pass
            self.fill_dos = self.ax_dos.fill_between(w_disp, 0, dos_disp, color="#3b82f6", alpha=0.18)

            # Update slice indicator
            if self.show_slice_indicator:
                self.slice_line.set_xdata([w_val, w_val])
                self.slice_line.set_label(rf"$\omega_{{\text{{slice}}}} = {w_val:.2f}$ eV")
                self.slice_line.set_visible(True)
                self.slice_dot.set_data([w_val], [rho_slice])
                self.slice_dot.set_visible(True)
            else:
                self.slice_line.set_visible(False)
                self.slice_line.set_label("")
                self.slice_dot.set_visible(False)

            handles, labels = self.ax_dos.get_legend_handles_labels()
            filt = [(h, l) for h, l in zip(handles, labels) if l]
            if filt:
                self.ax_dos.legend([h for h, _ in filt], [l for _, l in filt], loc="upper right", fontsize=8.0, framealpha=0.9)

            self.ax_dos.set_ylim(bottom=0, top=y_max_dos)
            self.ax_dos.set_title(
                rf"Density of States ($J_K = {self.lab.current_JK:.1f}$)",
                fontweight="bold", fontsize=10.5, pad=8
            )
            self.canvas.draw_idle()
            return

        # -----------------------------------------------------------------
        # 3. Initial Full Matplotlib Layout Setup
        # -----------------------------------------------------------------
        self.fig.clear()
        ax_map, ax_dos = self.fig.subplots(1, 2, gridspec_kw={"width_ratios": [1.0, 1.35], "wspace": 0.34})
        self.ax_map = ax_map
        self.ax_dos = ax_dos
        ax_map.set_box_aspect(1)
        ax_dos.set_box_aspect(0.68)

        im = ax_map.imshow(
            A_slice.T, origin="lower", extent=[-np.pi, np.pi, -np.pi, np.pi],
            cmap="inferno", interpolation="nearest"
        )
        self.im = im
        self._rendered_N = N

        ticks = [-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi]
        tick_labels = [r"$-\pi$", r"$-\pi/2$", r"$0$", r"$\pi/2$", r"$\pi$"]
        ax_map.set_xticks(ticks)
        ax_map.set_xticklabels(tick_labels, fontsize=8.5)
        ax_map.set_yticks(ticks)
        ax_map.set_yticklabels(tick_labels, fontsize=8.5)
        ax_map.set_xlabel(r"$k_x$", fontsize=9.5)
        ax_map.set_ylabel(r"$k_y$", fontsize=9.5)
        ax_map.set_title(
            rf"Fermi Surface $A(\mathbf{{k}}, \omega={w_val:.2f}\text{{ eV}})$",
            fontweight="bold", fontsize=10.5, pad=8
        )

        ax_map.axhline(0, color="#ffffff", linestyle="--", linewidth=0.7, alpha=0.35)
        ax_map.axvline(0, color="#ffffff", linestyle="--", linewidth=0.7, alpha=0.35)

        # Draw Pinned Points
        self._pinned_artists = []
        for idx, (px, py) in enumerate(self.pinned_points, 1):
            px_disp = (px + np.pi) % (2.0 * np.pi) - np.pi
            py_disp = (py + np.pi) % (2.0 * np.pi) - np.pi
            p_line, = ax_map.plot(
                px_disp, py_disp, marker="o", markersize=7.5,
                color="#38bdf8", markeredgecolor="#ffffff", markeredgewidth=1.5, zorder=8
            )
            self._pinned_artists.append(p_line)
            offset_x = -0.22 if px_disp > 1.2 else 0.22
            ha = "right" if px_disp > 1.2 else "left"
            offset_y = -0.22 if py_disp > 2.0 else (0.22 if py_disp < -2.0 else 0.1)
            va = "top" if py_disp > 2.0 else ("bottom" if py_disp < -2.0 else "center")
            p_txt = ax_map.text(
                px_disp + offset_x, py_disp + offset_y,
                rf"$P_{{{idx}}}({px_disp/np.pi:.2f}\pi, {py_disp/np.pi:.2f}\pi)$",
                color="#0284c7", fontweight="bold", fontsize=8.0, ha=ha, va=va,
                bbox=dict(boxstyle="round,pad=0.22", facecolor="#ffffff", edgecolor="#bae6fd", alpha=0.92, lw=0.9),
                zorder=9
            )
            self._pinned_artists.append(p_txt)

        cbar = self.fig.colorbar(im, ax=ax_map, fraction=0.046, pad=0.04)
        cbar.set_label(r"$A(\mathbf{k}, \omega)$", fontsize=8.5)
        cbar.ax.tick_params(labelsize=8)

        # Hover Crosshairs on 2D Map
        self.crosshair_h = ax_map.axhline(0, color="#38bdf8", linestyle=":", linewidth=1.1, alpha=0.9, visible=False, zorder=10)
        self.crosshair_v = ax_map.axvline(0, color="#38bdf8", linestyle=":", linewidth=1.1, alpha=0.9, visible=False, zorder=10)
        self.crosshair_text = ax_map.text(
            0.03, 0.96, "", transform=ax_map.transAxes,
            color="#0369a1", fontsize=8.0, fontweight="bold", va="top",
            bbox=dict(boxstyle="round,pad=0.22", facecolor="#ffffff", edgecolor="#7dd3fc", alpha=0.92, lw=0.8),
            visible=False, zorder=11
        )

        # Right: 1D Density of States
        self.line_dos, = ax_dos.plot(w_disp, dos_disp, color="#2563eb", linewidth=1.8, label=r"$\rho(\omega)$")
        self.fill_dos = ax_dos.fill_between(w_disp, 0, dos_disp, color="#3b82f6", alpha=0.18)

        # Vertical line indicating active energy slice (cleared on DOS right-click)
        slice_lbl = rf"$\omega_{{\text{{slice}}}} = {w_val:.2f}$ eV" if self.show_slice_indicator else ""
        self.slice_line = ax_dos.axvline(
            w_val, color="#ef4444", linestyle="--", linewidth=1.5,
            label=slice_lbl,
            visible=self.show_slice_indicator
        )
        self.slice_dot = ax_dos.plot(
            [w_val], [rho_slice], marker="o", markersize=6, color="#ef4444", zorder=5,
            visible=self.show_slice_indicator
        )[0]

        # Fermi level reference
        ax_dos.axvline(0, color="#94a3b8", linestyle=":", linewidth=0.9, alpha=0.7)

        # Frequency range set to w_max = 15 eV as requested
        ax_dos.set_xlim(-w_max_dos, w_max_dos)
        ax_dos.set_ylim(bottom=0, top=y_max_dos)

        ax_dos.set_xlabel(r"$\omega\text{ [eV]}$", fontsize=9.5)
        ax_dos.set_ylabel(r"$\rho(\omega)\text{ [eV}^{-1}\text{]}$", fontsize=9.5)
        ax_dos.set_title(
            rf"Density of States ($J_K = {self.lab.current_JK:.1f}$)",
            fontweight="bold", fontsize=10.5, pad=8
        )
        ax_dos.grid(True, linestyle=":", alpha=0.45, color="#cbd5e1")
        handles, labels = ax_dos.get_legend_handles_labels()
        filt = [(h, l) for h, l in zip(handles, labels) if l]
        if filt:
            ax_dos.legend([h for h, _ in filt], [l for _, l in filt], loc="upper right", fontsize=8.0, framealpha=0.9)
        ax_dos.tick_params(labelsize=8.5)

        # Hover Tracker on DOS
        self.dos_cursor_line = ax_dos.axvline(
            0, color="#059669", linestyle=":", linewidth=1.2, visible=False, zorder=10
        )
        self.dos_dot = ax_dos.plot(
            [0], [0], marker="o", markersize=6.5,
            color="#10b981", markeredgecolor="#ffffff", markeredgewidth=1.4,
            visible=False, zorder=11
        )[0]
        self.dos_annot = ax_dos.annotate(
            "", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="#ffffff", edgecolor="#86efac", alpha=0.95, lw=0.8),
            fontsize=8.0, fontweight="bold", color="#065f46", visible=False, zorder=12
        )

        self.fig.subplots_adjust(left=0.08, right=0.96, bottom=0.12, top=0.92)
        self.canvas.draw_idle()

    def on_motion(self, event) -> bool:
        """Tracks hover crosshair on 2D map or curve intersection on DOS."""
        if self.ax_map is None or self.ax_dos is None:
            return False

        if event.inaxes == self.ax_map:
            # Hide DOS tracker
            if self.dos_cursor_line and self.dos_cursor_line.get_visible():
                self.dos_cursor_line.set_visible(False)
            if self.dos_dot and self.dos_dot.get_visible():
                self.dos_dot.set_visible(False)
            if self.dos_annot and self.dos_annot.get_visible():
                self.dos_annot.set_visible(False)

            # Show map crosshair
            kx = event.xdata
            ky = event.ydata
            if kx is not None and ky is not None:
                self.crosshair_h.set_ydata([ky, ky])
                self.crosshair_v.set_xdata([kx, kx])
                self.crosshair_h.set_visible(True)
                self.crosshair_v.set_visible(True)
                self.crosshair_text.set_text(rf"$\mathbf{{k}} = ({kx/np.pi:.2f}\pi, {ky/np.pi:.2f}\pi)$")
                self.crosshair_text.set_visible(True)
                self.canvas.draw_idle()
                return True

        elif event.inaxes == self.ax_dos:
            # Hide map crosshair
            if self.crosshair_h and self.crosshair_h.get_visible():
                self.crosshair_h.set_visible(False)
            if self.crosshair_v and self.crosshair_v.get_visible():
                self.crosshair_v.set_visible(False)
            if self.crosshair_text and self.crosshair_text.get_visible():
                self.crosshair_text.set_visible(False)

            # Show DOS tracker
            w_cur = event.xdata
            if w_cur is not None and self._current_omega is not None and self._current_dos is not None:
                rho_val = float(np.interp(w_cur, self._current_omega, self._current_dos))
                self.dos_cursor_line.set_xdata([w_cur, w_cur])
                self.dos_cursor_line.set_visible(True)
                self.dos_dot.set_data([w_cur], [rho_val])
                self.dos_dot.set_visible(True)
                self.dos_annot.xy = (w_cur, rho_val)
                self.dos_annot.set_text(f"ω = {w_cur:.2f} eV\nρ = {rho_val:.3f} eV⁻¹")
                self.dos_annot.set_visible(True)
                self.canvas.draw_idle()
                return True

        else:
            # Out of axes: hide both
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
            if self.dos_cursor_line and self.dos_cursor_line.get_visible():
                self.dos_cursor_line.set_visible(False)
                changed = True
            if self.dos_dot and self.dos_dot.get_visible():
                self.dos_dot.set_visible(False)
                changed = True
            if self.dos_annot and self.dos_annot.get_visible():
                self.dos_annot.set_visible(False)
                changed = True
            if changed:
                self.canvas.draw_idle()

        return False

    def on_press(self, event) -> bool:
        """Handles map pinning, right-click clear, double-click mode switch, and DOS click-to-slice."""
        if event.inaxes == self.ax_map:
            if event.button == 3:
                # Right-click: Clear all pinned points
                self.clear_pinned_points()
                return True
            elif event.button == 1:
                if getattr(event, "dblclick", False):
                    # Double click jumps to Spectral Function mode probed at this k
                    self.lab.cb_experiment.setCurrentIndex(0)
                    self.lab._set_momentum(event.xdata, event.ydata)
                    return True
                else:
                    # Single click pins coordinate and updates probed k
                    kx = (event.xdata + np.pi) % (2.0 * np.pi) - np.pi
                    ky = (event.ydata + np.pi) % (2.0 * np.pi) - np.pi
                    self.pinned_points.append((kx, ky))
                    self.lab._set_momentum(event.xdata, event.ydata)
                    return True

        elif event.inaxes == self.ax_dos:
            if event.button == 3:
                # Right-click in DOS: reset DOS, remove red slice line, reset to EF = 0
                self.show_slice_indicator = False
                self.lab.slider_slice.blockSignals(True)
                self.lab.slider_slice.setValue(0)
                self.lab.slider_slice.blockSignals(False)
                self.lab.current_omega_slice = 0.0
                self.lab.lbl_slice_val.setText("ω = 0.00 eV")
                self.render()
                return True
            elif event.button == 1 and event.xdata is not None:
                # Left-click on DOS snaps slice energy directly to clicked position and activates red line
                self.show_slice_indicator = True
                w_clicked = max(-2.0, min(2.0, float(event.xdata)))
                self.lab.slider_slice.setValue(int(round(w_clicked * 100)))
                return True

        return False
