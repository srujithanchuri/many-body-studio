"""Study parameter form builder."""

def build_spectral_function_form(window):
    from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QPushButton, QCheckBox, QSizePolicy
    from .form_helpers import study_widget_types
    ModernCard, ModernComboBox = study_widget_types()
    self = window
    # 2b. Spectral Function A(k, omega) parameters
    grp_spec = ModernCard("Quasiparticle Spectral Function A(k, ω) && Self-Energy")
    grp_spec.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
    gsp = QVBoxLayout(grp_spec)
    gsp.setSpacing(5)

    gsp.addWidget(QLabel("Sweep Target:"))
    self.cb_spec_mode = ModernComboBox()
    self.cb_spec_mode.addItems(["Kondo Coupling (J_K)", "Interlayer Coupling (J_⊥)"])
    self.cb_spec_mode.currentIndexChanged.connect(self._on_spec_sweep_mode_change)
    gsp.addWidget(self.cb_spec_mode)

    gsp.addWidget(QLabel("Coupling Values (comma-separated):"))
    self.edit_spec_vals = QLineEdit("3.0, 6.0, 9.0")
    gsp.addWidget(self.edit_spec_vals)

    h_spec_row = QHBoxLayout()
    self.lbl_spec_fixed = QLabel("Fixed Interlayer Coupling (J_⊥):")
    self.lbl_spec_fixed.setStyleSheet("font-weight: 600;")
    h_spec_row.addWidget(self.lbl_spec_fixed)
    h_spec_row.addStretch()

    self.spin_spec_fixed = QDoubleSpinBox()
    self.spin_spec_fixed.setRange(0.0, 50.0)
    self.spin_spec_fixed.setValue(6.0)
    self.spin_spec_fixed.setSingleStep(0.5)
    self.spin_spec_fixed.setFixedWidth(100)
    h_spec_row.addWidget(self.spin_spec_fixed)
    gsp.addLayout(h_spec_row)

    self.lbl_spec_fixed_desc = QLabel("Constant value held fixed while sweeping coupling")
    self.lbl_spec_fixed_desc.setStyleSheet("color: #64748b; font-size: 11px;")
    self.lbl_spec_fixed_desc.setWordWrap(True)
    gsp.addWidget(self.lbl_spec_fixed_desc)

    gsp.addWidget(QLabel("Target Momentum (k):"))
    self.cb_mom = ModernComboBox()
    self.cb_mom.addItems([
        "Antinodal k_F (π, 0)",
        "Nodal k_F (π/2, π/2)",
        "Zone Center Γ (0, 0)",
        "Zone Corner M (π, π)",
        "Custom (kx, ky)..."
    ])
    self.cb_mom.currentIndexChanged.connect(self._on_mom_choice_changed)
    gsp.addWidget(self.cb_mom)

    # Custom k container (only visible when "Custom (kx, ky)..." is selected)
    self.box_custom_k = QWidget()
    lay_ck = QVBoxLayout(self.box_custom_k)
    lay_ck.setContentsMargins(0, 2, 0, 2)
    lay_ck.addWidget(QLabel("Custom Momentum (kx, ky) in units of π:"))
    self.edit_custom_k = QLineEdit("1.0, 0.0")
    lay_ck.addWidget(self.edit_custom_k)
    gsp.addWidget(self.box_custom_k)
    self.box_custom_k.setVisible(False)

    gsp.addWidget(QLabel("Observables Layout:"))
    self.cb_layout = ModernComboBox()
    self.cb_layout.addItems([
        "Both (Re Σ, A, Im Σ) [3 Panels]",
        "Self-Energy Only (Re Σ & Im Σ) [2 Panels]",
        "Spectral Function Only A(k, ω) [1 Panel]"
    ])
    gsp.addWidget(self.cb_layout)
    return grp_spec
