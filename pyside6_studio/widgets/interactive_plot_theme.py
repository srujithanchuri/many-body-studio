"""Presentation theme helpers for Interactive Plots.

No numerical, cache, or physics behavior belongs here.
"""


def apply_interactive_plot_theme(owner, is_dark: bool):
            owner.is_dark = is_dark
            owner.setObjectName("InteractivePlotsWidget")
            owner.setStyleSheet(f"""
                #InteractivePlotsWidget {{
                    background-color: {'#0b1120' if is_dark else '#f8fafc'};
                }}
                QToolTip {{
                    background-color: #0f172a;
                    color: #ffffff;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }}
            """)

            if hasattr(owner, "header_frame"):
                h_bg = "#0f172a" if is_dark else "#f8fafc"
                h_border = "#1e293b" if is_dark else "#e2e8f0"
                owner.header_frame.setStyleSheet(f"""
                    QFrame#analytical_header_frame {{
                        background: {h_bg};
                        border: 1px solid {h_border};
                        border-radius: 8px;
                    }}
                """)

            # Label styling
            lbl_main_color = "#f1f5f9" if is_dark else "#1e293b"
            lbl_sub_color = "#cbd5e1" if is_dark else "#475569"
            lbl_tip_color = "#94a3b8" if is_dark else "#64748b"

            main_lbl_style = f"font-weight: 700; color: {lbl_main_color}; font-size: 11px; background: transparent;"
            sub_lbl_style = f"font-size: 10px; font-weight: 600; color: {lbl_sub_color}; background: transparent;"

            for lbl in ("lbl_mode", "lbl_mu", "lbl_cache", "lbl_jk", "lbl_mom_title", "lbl_slice_title", "lbl_jperp", "lbl_k", "lbl_device"):
                if hasattr(owner, lbl):
                    getattr(owner, lbl).setStyleSheet(main_lbl_style)

            for lbl in ("lbl_kx", "lbl_ky"):
                if hasattr(owner, lbl):
                    getattr(owner, lbl).setStyleSheet(sub_lbl_style)

            if hasattr(owner, "lbl_map_tip"):
                owner.lbl_map_tip.setStyleSheet(f"color: {lbl_tip_color}; font-size: 10px; font-style: italic; background: transparent;")

            # Comboboxes & Spinboxes
            cb_bg = "#1e293b" if is_dark else "#ffffff"
            cb_fg = "#f8fafc" if is_dark else "#0f172a"
            cb_border = "#334155" if is_dark else "#cbd5e1"
            cb_sel_bg = "#1e3a8a" if is_dark else "#eff6ff"
            cb_sel_fg = "#93c5fd" if is_dark else "#1d4ed8"

            combo_base = f"""
                QComboBox {{
                    padding: 2px 18px 2px 6px;
                    border: 1px solid {cb_border};
                    border-radius: 4px;
                    background: {cb_bg};
                    color: {cb_fg};
                    font-size: 11px;
                    min-height: 20px;
                }}
                QComboBox:hover {{ border-color: #3b82f6; }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 14px;
                    border-left: none;
                }}
                QComboBox QAbstractItemView {{
                    background: {cb_bg};
                    color: {cb_fg};
                    selection-background-color: {cb_sel_bg};
                    selection-color: {cb_sel_fg};
                    border: 1px solid {cb_border};
                }}
                QToolTip {{
                    background-color: #0f172a;
                    color: #ffffff;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }}
                QLineEdit {{
                    background: {cb_bg};
                    color: {cb_fg};
                    border: none;
                }}
            """

            if hasattr(owner, "cb_experiment"):
                owner.cb_experiment.setStyleSheet(combo_base + "QComboBox { font-weight: 600; min-width: 130px; max-width: 155px; }")
            if hasattr(owner, "cb_filter_mu"):
                owner.cb_filter_mu.setStyleSheet(combo_base + "QComboBox { min-width: 44px; max-width: 58px; font-weight: 600; padding: 2px 14px 2px 6px; }")
            if hasattr(owner, "cb_cache_file"):
                owner.cb_cache_file.setStyleSheet(combo_base + "QComboBox { min-width: 180px; max-width: 330px; font-weight: 600; }")
            if hasattr(owner, "cb_momentum"):
                owner.cb_momentum.setStyleSheet(combo_base + "QComboBox { min-width: 110px; max-width: 155px; font-weight: 600; }")
            if hasattr(owner, "cb_k"):
                owner.cb_k.setStyleSheet(combo_base + "QComboBox { min-width: 95px; max-width: 120px; font-weight: 600; }")
            if hasattr(owner, "cb_device"):
                owner.cb_device.setStyleSheet(combo_base + "QComboBox { min-width: 105px; max-width: 140px; font-weight: 600; }")

            spin_style = f"""
                QDoubleSpinBox {{
                    padding: 2px 3px;
                    border: 1px solid {cb_border};
                    border-radius: 4px;
                    background: {cb_bg};
                    color: {cb_fg};
                    font-size: 11px;
                    font-weight: 600;
                }}
                QDoubleSpinBox:hover {{ border-color: #3b82f6; }}
            """
            if hasattr(owner, "spin_kx"):
                owner.spin_kx.setStyleSheet(spin_style)
            if hasattr(owner, "spin_ky"):
                owner.spin_ky.setStyleSheet(spin_style)

            # Action Buttons
            if hasattr(owner, "btn_clear_mu"):
                owner.btn_clear_mu.setStyleSheet(f"""
                    QPushButton {{
                        padding: 1px 2px;
                        background: {'#1e293b' if is_dark else '#f1f5f9'};
                        border: 1px solid {cb_border};
                        border-radius: 4px;
                        font-size: 10px;
                        font-weight: bold;
                        color: {'#94a3b8' if is_dark else '#64748b'};
                        min-width: 16px;
                        max-width: 16px;
                        min-height: 20px;
                        max-height: 20px;
                    }}
                    QPushButton:hover {{ background: #fee2e2; border-color: #ef4444; color: #dc2626; }}
                """)

            btn_action_style = f"""
                QPushButton {{
                    padding: 2px 6px;
                    background: {'#1e293b' if is_dark else '#ffffff'};
                    border: 1px solid {cb_border};
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                    color: {'#cbd5e1' if is_dark else '#334155'};
                }}
                QPushButton:hover {{
                    background: {'#334155' if is_dark else '#eff6ff'};
                    border-color: #3b82f6;
                    color: {'#ffffff' if is_dark else '#1d4ed8'};
                }}
            """
            for b in ("btn_reset", "btn_copy", "btn_save"):
                if hasattr(owner, b):
                    getattr(owner, b).setStyleSheet(btn_action_style)

            # Sliders
            slider_style = f"""
                QSlider::groove:horizontal {{
                    height: 4px;
                    background: {'#334155' if is_dark else '#cbd5e1'};
                    border-radius: 2px;
                }}
                QSlider::sub-page:horizontal {{
                    background: {'#3b82f6' if is_dark else '#2563eb'};
                    border-radius: 2px;
                }}
                QSlider::handle:horizontal {{
                    background: {'#3b82f6' if is_dark else '#2563eb'};
                    border: 2px solid {'#0f172a' if is_dark else '#ffffff'};
                    width: 14px;
                    margin-top: -5px;
                    margin-bottom: -5px;
                    border-radius: 7px;
                }}
                QSlider::handle:horizontal:hover {{
                    background: {'#60a5fa' if is_dark else '#1d4ed8'};
                }}
            """
            for s in ("slider_jk", "slider_slice", "slider_jperp"):
                if hasattr(owner, s):
                    getattr(owner, s).setStyleSheet(slider_style)

            # Value & HUD chips
            if hasattr(owner, "lbl_jk_val"):
                owner.lbl_jk_val.setStyleSheet(f"""
                    QLabel {{
                        background: {'#1e293b' if is_dark else '#eff6ff'};
                        border: 1px solid {'#2563eb' if is_dark else '#bfdbfe'};
                        border-radius: 4px;
                        padding: 2px 6px;
                        font-weight: 700;
                        color: {'#60a5fa' if is_dark else '#1d4ed8'};
                        font-size: 11px;
                        min-width: 65px;
                    }}
                """)

            if hasattr(owner, "lbl_slice_val"):
                owner.lbl_slice_val.setStyleSheet(f"""
                    QLabel {{
                        background: {'#1e293b' if is_dark else '#fdf2f8'};
                        border: 1px solid {'#be185d' if is_dark else '#fbcfe8'};
                        border-radius: 4px;
                        padding: 2px 6px;
                        font-weight: 700;
                        color: {'#f472b6' if is_dark else '#be185d'};
                        font-size: 11px;
                        min-width: 75px;
                    }}
                """)

            if hasattr(owner, "lbl_jperp_val"):
                owner.lbl_jperp_val.setStyleSheet(f"""
                    QLabel {{
                        background: {'#1e293b' if is_dark else '#ecfeff'};
                        border: 1px solid {'#0891b2' if is_dark else '#a5f3fc'};
                        border-radius: 4px;
                        padding: 2px 6px;
                        font-weight: 700;
                        color: {'#22d3ee' if is_dark else '#0e7490'};
                        font-size: 11px;
                        min-width: 65px;
                    }}
                """)

            chip_z = f"""
                QLabel {{
                    background: {'#0f172a' if is_dark else '#ecfeff'};
                    border: 1px solid {'#0891b2' if is_dark else '#a5f3fc'};
                    border-radius: 4px;
                    padding: 2px 7px;
                    font-weight: 700;
                    color: {'#38bdf8' if is_dark else '#0e7490'};
                    font-size: 11px;
                }}
                QLabel:hover {{
                    background: {'#1e293b' if is_dark else '#cffafe'};
                    border-color: {'#38bdf8' if is_dark else '#0891b2'};
                }}
            """
            chip_g = f"""
                QLabel {{
                    background: {'#0f172a' if is_dark else '#fffbeb'};
                    border: 1px solid {'#d97706' if is_dark else '#fde68a'};
                    border-radius: 4px;
                    padding: 2px 7px;
                    font-weight: 700;
                    color: {'#fbbf24' if is_dark else '#b45309'};
                    font-size: 11px;
                }}
                QLabel:hover {{
                    background: {'#1e293b' if is_dark else '#fef3c7'};
                    border-color: {'#fbbf24' if is_dark else '#d97706'};
                }}
            """
            chip_m = f"""
                QLabel {{
                    background: {'#0f172a' if is_dark else '#f5f3ff'};
                    border: 1px solid {'#7c3aed' if is_dark else '#ddd6fe'};
                    border-radius: 4px;
                    padding: 2px 7px;
                    font-weight: 700;
                    color: {'#c084fc' if is_dark else '#6d28d9'};
                    font-size: 11px;
                }}
                QLabel:hover {{
                    background: {'#1e293b' if is_dark else '#ede9fe'};
                    border-color: {'#c084fc' if is_dark else '#7c3aed'};
                }}
            """
            if hasattr(owner, "lbl_live_z"):
                owner.lbl_live_z.setStyleSheet(chip_z)
            if hasattr(owner, "lbl_live_gamma"):
                owner.lbl_live_gamma.setStyleSheet(chip_g)
            if hasattr(owner, "lbl_live_mass"):
                owner.lbl_live_mass.setStyleSheet(chip_m)
            if hasattr(owner, "lbl_conductivity_stats"):
                owner.lbl_conductivity_stats.setStyleSheet(chip_z)

            # Matplotlib canvas background
            if hasattr(owner, "canvas"):
                owner.canvas.setStyleSheet(f"background: {'#0b1120' if is_dark else '#ffffff'}; border: none;")

            # Active dialog update
            if hasattr(owner, "_foundation_dlg") and owner._foundation_dlg and owner._foundation_dlg.isVisible():
                owner._foundation_dlg.set_theme(is_dark)

            # Re-apply to figure artists and redraw
            owner.apply_theme_to_fig()
            if hasattr(owner, "canvas"):
                owner.canvas.draw_idle()
