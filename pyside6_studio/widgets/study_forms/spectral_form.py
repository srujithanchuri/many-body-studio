"""Study parameter form builder."""

def build_spectral_form(window):
    from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QPushButton, QCheckBox, QSizePolicy
    from .form_helpers import study_widget_types
    ModernCard, ModernComboBox = study_widget_types()
    self = window
    # 2a. Spectral Sweep parameters
    grp_se = ModernCard("Spectral Sweep (DOS / FS / Path) Parameters")
    grp_se.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
    gse = QVBoxLayout(grp_se)
    gse.setSpacing(5)
    gse.addWidget(QLabel("Sweep Target:"))
    self.cb_se_mode = ModernComboBox()
    self.cb_se_mode.addItems(["Kondo Coupling (J_K)", "Interlayer Coupling (J_⊥)"])
    self.cb_se_mode.currentIndexChanged.connect(self._on_se_sweep_mode_change)
    gse.addWidget(self.cb_se_mode)

    gse.addWidget(QLabel("Coupling Values Across Subplots (comma-separated):"))
    self.edit_se_vals = QLineEdit("3.0, 6.0, 9.0")
    gse.addWidget(self.edit_se_vals)

    h_se_row = QHBoxLayout()
    self.lbl_se_fixed = QLabel("Fixed Interlayer Coupling (J_⊥):")
    self.lbl_se_fixed.setStyleSheet("font-weight: 600;")
    h_se_row.addWidget(self.lbl_se_fixed)
    h_se_row.addStretch()

    self.spin_se_fixed = QDoubleSpinBox()
    self.spin_se_fixed.setRange(0.0, 50.0)
    self.spin_se_fixed.setValue(6.0)
    self.spin_se_fixed.setSingleStep(0.5)
    self.spin_se_fixed.setFixedWidth(100)
    h_se_row.addWidget(self.spin_se_fixed)
    gse.addLayout(h_se_row)

    self.lbl_se_fixed_desc = QLabel("Constant value of J_⊥ held fixed while sweeping J_K across columns")
    self.lbl_se_fixed_desc.setStyleSheet("color: #64748b; font-size: 11px;")
    self.lbl_se_fixed_desc.setWordWrap(True)
    gse.addWidget(self.lbl_se_fixed_desc)
    return grp_se
