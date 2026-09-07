"""Study parameter form builder."""

def build_susceptibility_form(window):
    from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QPushButton, QCheckBox, QSizePolicy
    from .form_helpers import study_widget_types
    ModernCard, ModernComboBox = study_widget_types()
    self = window
    # 2d. Susceptibility parameters
    grp_susc = ModernCard("RPA Spin Susceptibility Sweep Parameters")
    grp_susc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
    gsusc = QVBoxLayout(grp_susc)
    gsusc.setSpacing(5)
    self.chk_static = QCheckBox("Compute Static χ(q) (2D BZ Map)")
    self.chk_static.setChecked(True)
    gsusc.addWidget(self.chk_static)
    self.chk_dynamic = QCheckBox("Compute Dynamic χ(q, ω) (Path)")
    self.chk_dynamic.setChecked(True)
    gsusc.addWidget(self.chk_dynamic)

    gsusc.addWidget(QLabel("Sweep Target:"))
    self.cb_susc_mode = ModernComboBox()
    self.cb_susc_mode.addItems(["Kondo Coupling (J_K)", "Interlayer Coupling (J_⊥)"])
    self.cb_susc_mode.currentIndexChanged.connect(self._on_susc_sweep_mode_change)
    gsusc.addWidget(self.cb_susc_mode)

    self.lbl_susc_vals = QLabel("Coupling Values Across Subplots (comma-separated):")
    gsusc.addWidget(self.lbl_susc_vals)
    self.edit_susc_vals = QLineEdit("3.0, 6.0, 9.0")
    gsusc.addWidget(self.edit_susc_vals)

    h_susc_row = QHBoxLayout()
    self.lbl_susc_fixed = QLabel("Fixed Interlayer Coupling (J_⊥):")
    self.lbl_susc_fixed.setStyleSheet("font-weight: 600;")
    h_susc_row.addWidget(self.lbl_susc_fixed)
    h_susc_row.addStretch()

    self.spin_susc_fixed = QDoubleSpinBox()
    self.spin_susc_fixed.setRange(0.0, 50.0)
    self.spin_susc_fixed.setValue(6.0)
    self.spin_susc_fixed.setSingleStep(0.5)
    self.spin_susc_fixed.setFixedWidth(100)
    h_susc_row.addWidget(self.spin_susc_fixed)
    gsusc.addLayout(h_susc_row)

    self.lbl_susc_fixed_desc = QLabel("Constant value of J_⊥ held fixed while sweeping J_K across subplots")
    self.lbl_susc_fixed_desc.setStyleSheet("color: #64748b; font-size: 11px;")
    self.lbl_susc_fixed_desc.setWordWrap(True)
    gsusc.addWidget(self.lbl_susc_fixed_desc)

    self.param_stack.addWidget(grp_susc)
    return addWidget
