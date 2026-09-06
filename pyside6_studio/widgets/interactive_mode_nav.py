"""Interactive Mode Navigation Dock Widget for Many-Body Studio.

Provides visual card-based navigation for the 6 exact interactive physics modes:
1. Spectral Function
2. Fermi Surface / DOS
3. Band Dispersion
4. Static Susceptibility
5. Dynamic Susceptibility
6. Electrical Conductivity
"""

from PySide6.QtCore import Qt, Signal, QObject, QEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy
)


class InteractiveModeCard(QFrame):
    """Clickable card representing an interactive physics mode in the Left Dock."""
    sig_clicked = Signal(str)

    def __init__(self, mode_id: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.mode_id = mode_id
        self.title_text = title
        self.subtitle_text = subtitle
        self.is_selected = False
        self.is_dark = False

        self.setObjectName("InteractiveModeCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 7, 8, 7)
        lay.setSpacing(3)

        # Top row: Title + Selection indicator dot
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-weight: 700; font-size: 11px; background: transparent;")
        top_row.addWidget(self.lbl_title, 1)

        self.lbl_dot = QLabel("●")
        self.lbl_dot.setStyleSheet("font-size: 9px; color: #3b82f6; background: transparent;")
        self.lbl_dot.setVisible(False)
        top_row.addWidget(self.lbl_dot)

        lay.addLayout(top_row)

        # Subtitle description
        self.lbl_sub = QLabel(subtitle)
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setStyleSheet("font-size: 10px; color: #64748b; background: transparent; line-height: 1.2;")
        lay.addWidget(self.lbl_sub)

        self._update_colors()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.sig_clicked.emit(self.mode_id)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        if self.is_selected == selected:
            return
        self.is_selected = selected
        self.lbl_dot.setVisible(selected)
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self._update_colors()

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        self.style().unpolish(self)
        self.style().polish(self)
        self._update_colors()

    def _update_colors(self):
        if self.is_dark:
            title_col = "#93c5fd" if self.is_selected else "#e2e8f0"
            sub_col = "#94a3b8" if self.is_selected else "#64748b"
            dot_col = "#60a5fa" if self.is_selected else "transparent"
        else:
            title_col = "#1d4ed8" if self.is_selected else "#0f172a"
            sub_col = "#475569" if self.is_selected else "#64748b"
            dot_col = "#2563eb" if self.is_selected else "transparent"

        self.lbl_title.setStyleSheet(f"font-weight: 700; font-size: 11px; color: {title_col}; background: transparent;")
        self.lbl_sub.setStyleSheet(f"font-size: 10px; color: {sub_col}; background: transparent; line-height: 1.2;")
        self.lbl_dot.setStyleSheet(f"font-size: 9px; color: {dot_col}; background: transparent;")


class InteractiveModeNavWidget(QWidget):
    """Left dock panel displaying the 6 interactive mode cards."""
    sig_mode_selected = Signal(str)

    MODE_DEFINITIONS = [
        ("k_probe", "Spectral Function", "A(k, ω) spectral density & self-energy at probed k-points."),
        ("energy_slice", "Fermi Surface / DOS", "Brillouin zone constant energy contours & density of states."),
        ("band_dispersion", "Band Dispersion", "Renormalized quasiparticle dispersion E(k) along Γ-X-M-Γ."),
        ("static_susc", "Static Susceptibility", "Static RPA spin susceptibility χ_RPA(q) 2D momentum map."),
        ("dynamic_susc", "Dynamic Susceptibility", "Dynamical spin fluctuations χ''(q, ω) along high-symmetry paths."),
        ("conductivity", "Electrical Conductivity", "Optical and DC conductivity σ(ω) transport curves."),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dark = False
        self.cards: dict[str, InteractiveModeCard] = {}
        self._current_mode_id = "k_probe"

        self._build_ui()

    def _build_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        self.header_frame = QFrame()
        h_lay = QHBoxLayout(self.header_frame)
        h_lay.setContentsMargins(8, 6, 8, 6)

        self.lbl_header = QLabel("SELECT OBSERVABLE MODE")
        self.lbl_header.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; letter-spacing: 0.5px;")
        h_lay.addWidget(self.lbl_header)
        h_lay.addStretch()

        self.lbl_count = QLabel("6 Modes")
        self.lbl_count.setStyleSheet("font-size: 10px; font-weight: 600; color: #3b82f6;")
        h_lay.addWidget(self.lbl_count)

        root_lay.addWidget(self.header_frame)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        container_lay = QVBoxLayout(container)
        container_lay.setContentsMargins(6, 4, 6, 8)
        container_lay.setSpacing(5)

        for mode_id, title, subtitle in self.MODE_DEFINITIONS:
            card = InteractiveModeCard(mode_id, title, subtitle, parent=self)
            card.sig_clicked.connect(self._on_card_clicked)
            container_lay.addWidget(card)
            self.cards[mode_id] = card

        container_lay.addStretch()
        self.scroll.setWidget(container)
        root_lay.addWidget(self.scroll, 1)

        self.set_selected_mode("k_probe")

    def _on_card_clicked(self, mode_id: str):
        self.set_selected_mode(mode_id)
        self.sig_mode_selected.emit(mode_id)

    def set_selected_mode(self, mode_id: str):
        if self._current_mode_id == mode_id:
            if mode_id in self.cards and not self.cards[mode_id].is_selected:
                self.cards[mode_id].set_selected(True)
            return
        old_mode_id = self._current_mode_id
        self._current_mode_id = mode_id
        if old_mode_id in self.cards:
            self.cards[old_mode_id].set_selected(False)
        if mode_id in self.cards:
            self.cards[mode_id].set_selected(True)

    def get_selected_mode(self) -> str:
        return self._current_mode_id

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        if is_dark:
            self.setStyleSheet("background-color: #0c1322;")
            self.header_frame.setStyleSheet("background-color: #0f172a; border-bottom: 1px solid #1e293b;")
            self.lbl_header.setStyleSheet("font-size: 10px; font-weight: 700; color: #94a3b8; letter-spacing: 0.5px;")
        else:
            self.setStyleSheet("background-color: #f8fafc;")
            self.header_frame.setStyleSheet("background-color: #f1f5f9; border-bottom: 1px solid #e2e8f0;")
            self.lbl_header.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; letter-spacing: 0.5px;")

        for card in self.cards.values():
            card.set_theme(is_dark)
