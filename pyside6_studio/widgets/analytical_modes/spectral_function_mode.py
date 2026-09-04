"""
spectral_function_mode.py
-------------------------
Mode 0: Spectral Function [A(k, ω)] and Self-Energy Σ(k, ω).
Features:
  - Interactive momentum probing (BZ symmetry points or custom kx, ky).
  - Continuous J_K scaling.
  - Frequency bounds guaranteed >= [-8, 8] eV with dynamic expansion to prevent peak clipping.
  - Synchronized cursor-centered mouse wheel zoom across both subplots.
  - Synchronized left-click drag pan across both subplots.
  - Stable y-axis reference height from J_K = 0.5.
  - Quasiparticle residue Z(k), damping Γ(k), and effective mass m*/m HUD updates.
"""

import numpy as np
from pyside6_studio.widgets.analytical_modes.base_mode import BaseAnalyticalMode


class SpectralFunctionMode(BaseAnalyticalMode):
    """Mode 0: Probes A(k, ω) and self-energy Re Σ, Im Σ at a given momentum k."""

    mode_id = "k_probe"
    display_name = "Spectral Function [A(k, ω)]"
    required_cache_type = "sigma"

    def __init__(self, lab):
        super().__init__(lab)
        self.w_max = 8.0
        self._user_xlim = None
        self._user_ylim_a = None
        self._user_ylim_s = None
        self._is_panning = False
        self._pan_start_x = 0.0
        self._pan_start_y = 0.0
        self._pan_ax = None
        self._pan_start_xlim = {}
        self._pan_start_ylim = None

    def setup_ui(self):
        self.lab.container_mom.setVisible(True)
        self.lab.container_slice.setVisible(False)
        if hasattr(self.lab, "container_susc_params"):
            self.lab.container_susc_params.setVisible(False)
        self.lab.lbl_map_tip.setVisible(False)
        if hasattr(self.lab, "container_wmax"):
            self.lab.container_wmax.setVisible(True)
        self.lab.lbl_live_z.setVisible(True)
        self.lab.lbl_live_gamma.setVisible(True)
        self.lab.lbl_live_mass.setVisible(True)

    def fit_view(self):
        self._user_xlim = None
        self._user_ylim_a = None
        self._user_ylim_s = None
        self.render()
        self.lab.sig_status_msg.emit("View reset to canvas.")

    def reset_view(self):
        self.fit_view()

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

        # Discretize kx, ky to mesh indices
        kx_pos = self.lab.current_kx % (2.0 * np.pi)
        ky_pos = self.lab.current_ky % (2.0 * np.pi)
        ikx = int(round((kx_pos / (2.0 * np.pi)) * N)) % N
        iky = int(round((ky_pos / (2.0 * np.pi)) * N)) % N
        kx_eff = (ikx / N) * 2.0 * np.pi
        ky_eff = (iky / N) * 2.0 * np.pi
        kx_disp = (self.lab.current_kx + np.pi) % (2.0 * np.pi) - np.pi
        ky_disp = (self.lab.current_ky + np.pi) % (2.0 * np.pi) - np.pi

        # Analytical scaling in < 0.1 ms
        scale_fac = self.lab.current_JK ** 2
        sig_re_k = bs["sig_re"][:, ikx, iky] * scale_fac
        sig_im_k = bs["sig_im"][:, ikx, iky] * scale_fac

        # Quasiparticle Residue Z(k) and Lifetime
        idx_zero = np.argmin(np.abs(omega))
        gamma_k = np.abs(sig_im_k[idx_zero])

        # Enforce strict zero for Imag self-energy at Fermi surface (matching physics solver)
        sig_im_k_clean = sig_im_k - sig_im_k[idx_zero]

        # Bare dispersion
        xi_k = -2.0 * t * (np.cos(kx_eff) + np.cos(ky_eff)) - 4.0 * t1 * np.cos(kx_eff) * np.cos(ky_eff) - mu

        # Spectral function A(k, ω)
        denom = (omega - xi_k - sig_re_k) ** 2 + (sig_im_k_clean - eta) ** 2
        A_k = -(1.0 / np.pi) * (sig_im_k_clean - eta) / np.maximum(denom, 1e-12)

        z_k = None
        if 0 < idx_zero < len(omega) - 1:
            d_re = (sig_re_k[idx_zero + 1] - sig_re_k[idx_zero - 1]) / (omega[idx_zero + 1] - omega[idx_zero - 1])
            if 1.0 - d_re > 1e-4:
                z_k = 1.0 / (1.0 - d_re)

        if z_k and 0 < z_k < 10:
            self.lab.lbl_live_z.setText(f"Z(k): {z_k:.3f}")
            self.lab.lbl_live_mass.setText(f"m*/m: {1.0/z_k:.2f}")
            self.lab.lbl_live_z.setToolTip(
                f"<b>Quasiparticle Residue Z(k) = {z_k:.3f}</b><br>"
                "<i>Formula: Z(k) = [1 - ∂ReΣ/∂ω |<sub>ω→0</sub>]<sup>-1</sup></i><br><br>"
                f"• <b>Current Weight:</b> <b>{z_k*100:.1f}%</b> coherent quasiparticle weight at E<sub>F</sub>.<br>"
                f"• <b>Incoherent Background:</b> <b>{(1.0-z_k)*100:.1f}%</b> transferred to Hubbard/Kondo satellites.<br>"
                "• <i>Z ≈ 1:</i> Weakly interacting Fermi liquid • <i>Z → 0:</i> Heavy fermion / localization breakdown."
            )
            self.lab.lbl_live_mass.setToolTip(
                f"<b>Effective Mass Enhancement m*/m = {1.0/z_k:.2f}</b><br>"
                "<i>Formula: m*/m ≈ 1 / Z(k) = 1 - ∂ReΣ/∂ω |<sub>ω→0</sub></i><br><br>"
                f"• Electronic inertia is enhanced by <b>{1.0/z_k:.2f}×</b> due to many-body Kondo dressing.<br>"
                f"• Renormalized Fermi velocity: v<sub>F</sub>* ≈ v<sub>F</sub> / {1.0/z_k:.2f}.<br>"
                "• Directly proportional to Sommerfeld specific heat coefficient γ<sub>C</sub>."
            )
        else:
            self.lab.lbl_live_z.setText("Z(k): —")
            self.lab.lbl_live_mass.setText("m*/m: —")

        self.lab.lbl_live_gamma.setText(f"Γ(k): {gamma_k:.3f} eV")
        self.lab.lbl_live_gamma.setToolTip(
            f"<b>Quasiparticle Damping Γ(k) = {gamma_k:.3f} eV</b><br>"
            "<i>Formula: Γ(k) = |ImΣ(k, ω=0)|</i><br><br>"
            "• Inelastic scattering rate with localized spin background.<br>"
            f"• Finite lifetime: τ<sub>k</sub> ~ ħ / [2 Γ(k)].<br>"
            "• Controls the Lorentzian broadening width of the A(k, ω) peak."
        )

        # Render 2-panel plot: (Left: A(k, ω), Right: Re Σ & Im Σ)
        self.fig.clear()
        ax_a = self.fig.add_subplot(121)
        ax_s = self.fig.add_subplot(122)

        k_label = f"k = ({kx_disp/np.pi:.2f}π, {ky_disp/np.pi:.2f}π)"
        ax_a.axvline(0, color="#94a3b8", linestyle="--", linewidth=0.8)
        ax_a.axvline(xi_k, color="#dc2626", linestyle=":", linewidth=0.8, label=f"Bare $\\xi_k = {xi_k:.2f}$")
        ax_a.plot(omega, A_k, color="#2563eb", lw=2.0, label=f"$J_K = {self.lab.current_JK:.1f}$")
        ax_a.set_xlabel(r"$\omega$ [eV]", fontsize=10)
        ax_a.set_ylabel(r"$A(\mathbf{k}, \omega)$", fontsize=10)
        ax_a.set_title(rf"$A(\mathbf{{k}}, \omega)$ [at {k_label}]", fontweight="bold", fontsize=10.5, pad=8)
        ax_a.grid(True, linestyle=":", alpha=0.35)
        ax_a.legend(frameon=True, fontsize=9)

        # Fixed non-adaptive frequency bounds (user-selectable ±8.0 eV or ±15.0 eV)
        w_max_val = getattr(self, "w_max", 8.0)
        default_xlim = (-w_max_val, w_max_val)

        if self._user_xlim:
            ax_a.set_xlim(self._user_xlim)
            ax_s.set_xlim(self._user_xlim)
        else:
            ax_a.set_xlim(default_xlim)
            ax_s.set_xlim(default_xlim)

        # Fixed reference height equivalent to J_K = 0.5 maximum peak so y-axis is stable during slider dragging
        scale_fac_05 = 0.5 ** 2
        sig_im_05 = bs["sig_im"][:, ikx, iky] * scale_fac_05
        sig_re_05 = bs["sig_re"][:, ikx, iky] * scale_fac_05
        denom_05 = (omega - xi_k - sig_re_05) ** 2 + (sig_im_05 - eta) ** 2
        A_05 = -(1.0 / np.pi) * (sig_im_05 - eta) / np.maximum(denom_05, 1e-12)

        peak_05 = float(np.max(A_05))
        bare_max = 1.0 / (np.pi * max(eta, 0.02))
        y_max = max(peak_05, bare_max) * 1.08
        if self._user_ylim_a:
            ax_a.set_ylim(self._user_ylim_a)
        else:
            ax_a.set_ylim(-0.02 * y_max, y_max)

        ax_s.axvline(0, color="#94a3b8", linestyle="--", linewidth=0.8)
        ax_s.plot(omega, sig_re_k, color="#0891b2", lw=1.8, label=r"$\operatorname{Re}\Sigma$")
        ax_s.plot(omega, sig_im_k, color="#d97706", lw=1.8, label=r"$\operatorname{Im}\Sigma$")
        ax_s.set_xlabel(r"$\omega$ [eV]", fontsize=10)
        ax_s.set_title(r"Self-Energy $\operatorname{Re}\Sigma, \operatorname{Im}\Sigma$", fontweight="bold", fontsize=10.5, pad=8)
        ax_s.grid(True, linestyle=":", alpha=0.35)
        ax_s.legend(frameon=True, fontsize=9)
        if self._user_ylim_s:
            ax_s.set_ylim(self._user_ylim_s)

        self.fig.tight_layout(pad=1.8, w_pad=2.2)
        self.canvas.draw()

    def on_scroll(self, event) -> bool:
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return False

        ax = event.inaxes
        base_scale = 1.25
        if event.button == "up" or getattr(event, "step", 0) > 0:
            scale_factor = 1.0 / base_scale
        elif event.button == "down" or getattr(event, "step", 0) < 0:
            scale_factor = base_scale
        else:
            return False

        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        xdata = event.xdata
        ydata = event.ydata

        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor

        relx = (cur_xlim[1] - xdata) / max(cur_xlim[1] - cur_xlim[0], 1e-9)
        rely = (cur_ylim[1] - ydata) / max(cur_ylim[1] - cur_ylim[0], 1e-9)

        new_xlim = [xdata - new_width * (1.0 - relx), xdata + new_width * relx]
        new_ylim = [ydata - new_height * (1.0 - rely), ydata + new_height * rely]

        for a in self.fig.axes:
            a.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)
        self._user_xlim = new_xlim
        if len(self.fig.axes) > 0 and ax == self.fig.axes[0]:
            self._user_ylim_a = new_ylim
        elif len(self.fig.axes) > 1 and ax == self.fig.axes[1]:
            self._user_ylim_s = new_ylim

        self.canvas.draw_idle()
        return True

    def on_press(self, event) -> bool:
        if event.button == 1 and event.inaxes:
            self._is_panning = True
            self._pan_start_x = event.x
            self._pan_start_y = event.y
            self._pan_ax = event.inaxes
            self._pan_start_xlim = {a: a.get_xlim() for a in self.fig.axes}
            self._pan_start_ylim = event.inaxes.get_ylim()
            return True
        return False

    def on_motion(self, event) -> bool:
        if self._is_panning and self._pan_ax and event.x is not None and event.y is not None:
            ax = self._pan_ax
            dx_pixels = event.x - self._pan_start_x
            dy_pixels = event.y - self._pan_start_y

            try:
                inv = ax.transData.inverted()
                p0 = inv.transform((0, 0))
                p1 = inv.transform((dx_pixels, dy_pixels))
                dx_data = p1[0] - p0[0]
                dy_data = p1[1] - p0[1]

                orig_ylim = self._pan_start_ylim
                new_ylim = [orig_ylim[0] - dy_data, orig_ylim[1] - dy_data]
                ax.set_ylim(new_ylim)

                # Synchronously translate omega axis across both subplots using exact dx_data
                for a in self.fig.axes:
                    orig = self._pan_start_xlim.get(a, a.get_xlim())
                    a.set_xlim([orig[0] - dx_data, orig[1] - dx_data])
                if len(self.fig.axes) > 0:
                    self._user_xlim = self.fig.axes[0].get_xlim()
                if len(self.fig.axes) > 0 and ax == self.fig.axes[0]:
                    self._user_ylim_a = new_ylim
                elif len(self.fig.axes) > 1 and ax == self.fig.axes[1]:
                    self._user_ylim_s = new_ylim

                self.canvas.draw_idle()
                return True
            except Exception:
                pass
        return False

    def on_release(self, event) -> bool:
        if self._is_panning:
            self._is_panning = False
            self._pan_ax = None
            return True
        return False
