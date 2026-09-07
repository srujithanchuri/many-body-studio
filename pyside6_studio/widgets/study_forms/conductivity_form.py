"""Study parameter form builder."""

def build_conductivity_form(window):
    from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QPushButton, QCheckBox, QSizePolicy
    from .form_helpers import study_widget_types
    ModernCard, ModernComboBox = study_widget_types()
    self = window
    # 2e. Electrical / Optical Conductivity parameters
    grp_cond = ModernCard("Electrical / Optical Conductivity Sweep σ(ω)")
    grp_cond.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
    gcond = QVBoxLayout(grp_cond)
    gcond.setSpacing(5)

    gcond.addWidget(QLabel("Sweep Target:"))
    self.cb_cond_mode = ModernComboBox()
    self.cb_cond_mode.addItems(["Kondo Coupling (J_K)", "Interlayer Coupling (J_⊥)"])
    self.cb_cond_mode.currentIndexChanged.connect(self._on_cond_sweep_mode_change)
    gcond.addWidget(self.cb_cond_mode)

    gcond.addWidget(QLabel("Coupling Values Across Curves (comma-separated):"))
    self.edit_cond_vals = QLineEdit("0.0, 3.0, 6.0, 9.0")
    gcond.addWidget(self.edit_cond_vals)

    h_cond_row = QHBoxLayout()
    self.lbl_cond_fixed = QLabel("Fixed Interlayer Coupling (J_⊥):")
    self.lbl_cond_fixed.setStyleSheet("font-weight: 600;")
    h_cond_row.addWidget(self.lbl_cond_fixed)
    h_cond_row.addStretch()

    self.spin_cond_fixed = QDoubleSpinBox()
    self.spin_cond_fixed.setRange(0.0, 50.0)
    self.spin_cond_fixed.setValue(6.0)
    self.spin_cond_fixed.setSingleStep(0.5)
    self.spin_cond_fixed.setFixedWidth(100)
    h_cond_row.addWidget(self.spin_cond_fixed)
    gcond.addLayout(h_cond_row)

    self.lbl_cond_fixed_desc = QLabel("Constant value of J_⊥ held fixed while sweeping J_K across curves")
    self.lbl_cond_fixed_desc.setStyleSheet("color: #64748b; font-size: 11px;")
    self.lbl_cond_fixed_desc.setWordWrap(True)
    gcond.addWidget(self.lbl_cond_fixed_desc)

    h_cond_cut = QHBoxLayout()
    lbl_wactive = QLabel("Active Cutoff ω_max (eV):")
    lbl_wactive.setToolTip("Restricts Kubo bubble integration to active energy window for 2x calculation speedup")
    h_cond_cut.addWidget(lbl_wactive)
    h_cond_cut.addStretch()

    self.spin_cond_wactive = QDoubleSpinBox()
    self.spin_cond_wactive.setRange(1.0, 100.0)
    self.spin_cond_wactive.setValue(20.0)
    self.spin_cond_wactive.setSingleStep(5.0)
    self.spin_cond_wactive.setFixedWidth(100)
    self.spin_cond_wactive.setToolTip("Active frequency cutoff window in eV (default: 20.0)")
    h_cond_cut.addWidget(self.spin_cond_wactive)
    gcond.addLayout(h_cond_cut)

    return grp_cond
