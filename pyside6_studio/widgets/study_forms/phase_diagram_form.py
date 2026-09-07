"""Study parameter form builder."""

def build_phase_diagram_form(window):
    from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QPushButton, QCheckBox, QSizePolicy
    from .form_helpers import study_widget_types
    ModernCard, ModernComboBox = study_widget_types()
    self = window
    # 2c. Phase Diagram parameters
    grp_pd = ModernCard("Phase Boundary Bisection Search")
    grp_pd.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
    gpd = QVBoxLayout(grp_pd)
    gpd.setSpacing(5)
    h_min = QHBoxLayout(); h_min.addWidget(QLabel("J_K min:")); h_min.addStretch(); self.s_min = QDoubleSpinBox(); self.s_min.setValue(0.0); self.s_min.setFixedWidth(100); h_min.addWidget(self.s_min); gpd.addLayout(h_min)
    h_max = QHBoxLayout(); h_max.addWidget(QLabel("J_K max:")); h_max.addStretch(); self.s_max = QDoubleSpinBox(); self.s_max.setValue(12.0); self.s_max.setFixedWidth(100); h_max.addWidget(self.s_max); gpd.addLayout(h_max)
    h_pts = QHBoxLayout(); h_pts.addWidget(QLabel("Points:")); h_pts.addStretch(); self.s_pts = QSpinBox(); self.s_pts.setValue(200); self.s_pts.setFixedWidth(100); h_pts.addWidget(self.s_pts); gpd.addLayout(h_pts)
    btn_pre = QPushButton("⚡ Precompute Bare χ₀ (Bubble)")
    btn_pre.clicked.connect(self._on_precompute_bubble)
    gpd.addWidget(btn_pre)
    self.param_stack.addWidget(grp_pd)
    return addWidget
