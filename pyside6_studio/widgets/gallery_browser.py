"""Plot Gallery Browser for Many-Body Studio Pro.

Provides a visual-first, card-based browser for simulation plots:
1. High-contrast thumbnail previews (cached in memory with non-blocking async generation).
2. Human-readable physical observable titles (DOS, Fermi Surface, Band Dispersion, χ(q, ω), Phase Diagram).
3. Physics parameter tags (J_K Sweep, J_perp = 6.0, mu = 1.0, timestamp).
4. Two-tier filtering (Category + Observable Type) plus instant parameter search.
5. Detection of companion .npz datasets with [📊 Data Available] badge.
"""

import os
import re
import glob
import time
import datetime
from typing import Optional, Dict, List, Tuple

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QThread, QObject
from PySide6.QtGui import QPixmap, QImage, QColor, QFont, QIcon, QPainter, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QScrollArea, QFrame, QMenu,
    QMessageBox, QSizePolicy, QApplication, QButtonGroup, QToolButton
)

from pyside6_studio.core.config import DEFAULT_RESULTS_DIR
from pyside6_studio.core.cache_manager import normalize_results_dir
from pyside6_studio.widgets.dataset_explorer import parse_filename_parameters, SmartSearchMatcher


def parse_plot_metadata(filepath: str) -> Tuple[str, str, str, str, str]:
    """
    Parses a simulation plot filepath into clean, human-readable physics metadata.
    Returns: (title, params_str, category_tag, observable_type, raw_filename)
    """
    fname = os.path.basename(filepath)
    stem = os.path.splitext(fname)[0]

    # 1. Susceptibility Sweep: sweep_JK_fixed_J_6.0_mu_1.00_dynamic.png or sweep_J_fixed_JK_6.0_mu_1.00_dynamic.png
    m_susc = re.search(r'sweep_(JK|J_perp|Jperp|J)_fixed_(?:J|JK|J_perp|Jperp)_*([0-9.]+)_*mu_*([0-9.-]+)_*([a-zA-Z]+)', stem, re.IGNORECASE)
    if m_susc:
        mode, fixed_val, mu, kind = m_susc.groups()
        fixed_name = 'J_⊥' if mode.upper() in ('JK', 'J_K') else 'J_K'
        sweep_name = 'J_K Sweep' if mode.upper() in ('JK', 'J_K') else 'J_⊥ Sweep'
        is_dyn = kind.lower() == 'dynamic'
        kind_title = 'Dynamic Susceptibility χ(q, ω)' if is_dyn else 'Static Susceptibility χ(q, 0)'
        obs_type = 'Dynamic Susceptibility χ(q, ω)' if is_dyn else 'Static Susceptibility χ(q, 0)'
        params = [sweep_name, f'{fixed_name} = {fixed_val}', f'μ = {mu}']
        return kind_title, '  •  '.join(params), '🧲 Susceptibility', obs_type, fname

    # 2. Magnetic Phase Diagram: phase_diagram_mu1.00_AFM.png
    m_phase = re.search(r'phase_diagram_mu_*([0-9.-]+)_*([A-Z]+)', stem, re.IGNORECASE)
    if m_phase:
        mu, k_type = m_phase.groups()
        k_desc = 'K > 0 (AFM)' if k_type.upper() == 'AFM' else 'K < 0 (FM)'
        title = f'Magnetic Phase Diagram ({k_type.upper()})'
        params = [k_desc, f'μ = {mu}']
        return title, '  •  '.join(params), '🧲 Susceptibility', 'Magnetic Phase Diagram', fname

    # 3. Quasiparticle Spectral Function: both_JK_fixed_Jperp6.00_k_0.5_0.5_mu1.00.png or both_JK_k_1_0_mu_1.0.png
    m_spec = re.search(r'(both|spectral|self_energy)_(JK|Jperp)_*(?:fixed_)?(?:Jperp|JK)?_*([0-9.]*)_k_([0-9.]+)_([0-9.]+)_mu_*([0-9.-]+)', stem, re.IGNORECASE)
    if m_spec:
        obs, sweep_m, fixed_val, kx, ky, mu = m_spec.groups()
        obs_map = {
            'both': 'Quasiparticle Spectral A(k, ω) & Self-Energy',
            'spectral': 'Quasiparticle Spectral A(k, ω)',
            'self_energy': 'Self-Energy Re Σ & Im Σ'
        }
        title = obs_map.get(obs.lower(), 'Spectral Analysis')
        sweep_name = 'J_K Sweep' if 'JK' in sweep_m.upper() else 'J_⊥ Sweep'
        fixed_val_str = fixed_val if fixed_val else '6.0'
        fixed_name = 'J_⊥' if 'JK' in sweep_m.upper() else 'J_K'
        k_str = f'k = ({kx}π, {ky}π)' if ky != '0' else f'k = ({kx}π, 0)'
        if kx == '0' and ky == '0':
            k_str = 'k = (0, 0)'
        params = [sweep_name, f'{fixed_name} = {fixed_val_str}', k_str, f'μ = {mu}']
        return title, '  •  '.join(params), '🌊 Spectral', 'Quasiparticle Spectral A(k, ω)', fname

    # 4. Spectral Sweep Subplots: sweep_DOS_atJ_perp_6.0_mu_1.0.png or sweep_FS_... or sweep_Path_...
    m_se = re.search(r'sweep_(DOS|FS|Path)_at_*(J_perp|J_K|Jperp|JK)_*([0-9.]+)_*mu_*([0-9.-]+)', stem, re.IGNORECASE)
    if m_se:
        ptype, fixed_m, fixed_val, mu = m_se.groups()
        type_map = {
            'DOS': ('Density of States (DOS)', 'Density of States (DOS)'),
            'FS': ('Fermi Surface (FS)', 'Fermi Surface (FS)'),
            'PATH': ('Band Dispersion along High-Symmetry Path', 'Band Dispersion (Path)')
        }
        title, obs_type = type_map.get(ptype.upper(), (ptype, 'Spectral'))
        sweep_name = 'J_K Sweep' if 'perp' in fixed_m.lower() else 'J_⊥ Sweep'
        fixed_name = 'J_⊥' if 'perp' in fixed_m.lower() else 'J_K'
        params = [sweep_name, f'{fixed_name} = {fixed_val}', f'μ = {mu}']
        return title, '  •  '.join(params), '🌊 Spectral', obs_type, fname

    # 5. Composite sweeps: sweep_JK_vals_3.00_6.00_9.00_Jperp_6.00...png
    if 'sweep_jk' in stem.lower() or 'sweep_jperp' in stem.lower():
        title = 'Spectral Sweep Suite [DOS, FS, Path]'
        params = []
        jp_m = re.search(r'Jperp_([0-9.]+)', stem)
        if jp_m: params.append(f'J_⊥ = {jp_m.group(1)}')
        mu_m = re.search(r'mu_([0-9.-]+)', stem)
        if mu_m: params.append(f'μ = {mu_m.group(1)}')
        n_m = re.search(r'N_([0-9]+)', stem)
        if n_m: params.append(f'N = {n_m.group(1)}')
        return title, '  •  '.join(params) if params else 'Multi-Coupling Sweep', '🌊 Spectral', 'Band Dispersion (Path)', fname

    # Fallback
    clean_title = stem.replace('_', ' ').replace('-', ' ').title()
    cat = '🧲 Susceptibility' if any(k in filepath.lower() for k in ('susc', 'chi', 'phase')) else '🌊 Spectral'
    obs_type = 'Other Observable'
    return clean_title, '', cat, obs_type, fname


class ThumbnailCard(QFrame):
    """Visual card displaying a plot thumbnail, physical observable title, and metadata badges."""
    sig_selected = Signal(str)
    sig_view_fullscreen = Signal(str)
    sig_explore_data = Signal(str)

    def __init__(self, plot_path: str, data_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.plot_path = os.path.normpath(plot_path)
        self.data_path = os.path.normpath(data_path) if data_path else None
        self.is_selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("ThumbnailCard")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.title, self.params_str, self.cat_tag, self.obs_type, self.fname = parse_plot_metadata(self.plot_path)

        # Formatted timestamp
        try:
            mtime = os.path.getmtime(self.plot_path)
            self.time_str = datetime.datetime.fromtimestamp(mtime).strftime("%b %d, %H:%M")
        except Exception:
            self.time_str = ""

        self._build_ui()
        self.update_style()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        # 1. Thumbnail Image Container
        self.img_lbl = QLabel()
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setFixedHeight(120)
        self.img_lbl.setStyleSheet("""
            background: #0f172a;
            border-radius: 4px;
            border: 1px solid #e2e8f0;
        """)
        self.img_lbl.setText("⏳ Loading preview...")
        lay.addWidget(self.img_lbl)

        # 2. Prominent Physics Title
        self.lbl_title = QLabel(self.title)
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #0f172a;")
        lay.addWidget(self.lbl_title)

        # 3. Physical Parameters Row
        if self.params_str:
            lbl_p = QLabel(self.params_str)
            lbl_p.setWordWrap(True)
            lbl_p.setStyleSheet("font-size: 10px; color: #0284c7; font-weight: 600;")
            lay.addWidget(lbl_p)

        # 4. Bottom Row: Category Tag, Timestamp, and Data Badge
        b_row = QHBoxLayout()
        b_row.setContentsMargins(0, 2, 0, 0)
        b_row.setSpacing(4)

        lbl_cat = QLabel(f"{self.cat_tag} • {self.time_str}")
        lbl_cat.setStyleSheet("font-size: 9px; color: #64748b;")
        b_row.addWidget(lbl_cat)

        b_row.addStretch()

        lay.addLayout(b_row)

    def set_thumbnail_pixmap(self, pixmap: QPixmap):
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(280, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.img_lbl.setPixmap(scaled)
            self.img_lbl.setText("")

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update_style()

    def update_style(self):
        if self.is_selected:
            self.setStyleSheet("""
                #ThumbnailCard {
                    background-color: #eff6ff;
                    border: 2px solid #2563eb;
                    border-radius: 6px;
                }
            """)
            self.lbl_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #1d4ed8;")
        else:
            self.setStyleSheet("""
                #ThumbnailCard {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                }
                #ThumbnailCard:hover {
                    background-color: #f8fafc;
                    border-color: #94a3b8;
                }
            """)
            self.lbl_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #0f172a;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.sig_selected.emit(self.plot_path)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        a_view = menu.addAction("👁️ View Fullscreen")
        a_copy = menu.addAction("📋 Copy Image to Clipboard")
        menu.addSeparator()
        a_reveal = menu.addAction("📂 Reveal in File Explorer")

        chosen = menu.exec(event.globalPos())
        if chosen == a_view:
            self.sig_view_fullscreen.emit(self.plot_path)
        elif chosen == a_copy:
            pix = QPixmap(self.plot_path)
            if not pix.isNull():
                QApplication.clipboard().setPixmap(pix)
        elif chosen == a_reveal:
            os.system(f'explorer /select,"{self.plot_path}"')


class CompactRowCard(QFrame):
    """Compact high-density row item (~42px) for scanning multiple plots without scrolling."""
    sig_selected = Signal(str)
    sig_view_fullscreen = Signal(str)
    sig_explore_data = Signal(str)

    def __init__(self, plot_path: str, data_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.plot_path = os.path.normpath(plot_path)
        self.data_path = os.path.normpath(data_path) if data_path else None
        self.is_selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedHeight(44)
        self.setObjectName("CompactRowCard")

        self.title, self.params_str, self.cat_tag, self.obs_type, self.fname = parse_plot_metadata(self.plot_path)

        self._build_ui()
        self.update_style()

    def _build_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 3, 6, 3)
        lay.setSpacing(6)

        # Icon based on observable
        if "Phase" in self.title or "phase" in self.plot_path.lower():
            icon = "🗺️"
        elif "Susceptibility" in self.cat_tag or "χ" in self.title or "susc" in self.plot_path.lower():
            icon = "🧲"
        elif "DOS" in self.title:
            icon = "📈"
        elif "FS" in self.title or "Fermi" in self.title:
            icon = "🕸️"
        elif "Path" in self.title or "Dispersion" in self.title:
            icon = "⚡"
        else:
            icon = "🌊"

        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 13px;")
        lay.addWidget(lbl_icon)

        # Text column
        t_lay = QVBoxLayout()
        t_lay.setContentsMargins(0, 0, 0, 0)
        t_lay.setSpacing(1)

        self.lbl_title = QLabel(self.title)
        self.lbl_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #0f172a;")
        t_lay.addWidget(self.lbl_title)

        if self.params_str:
            self.lbl_p = QLabel(self.params_str)
            self.lbl_p.setStyleSheet("font-size: 9px; color: #0284c7; font-weight: 600;")
            t_lay.addWidget(self.lbl_p)

        lay.addLayout(t_lay, 1)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update_style()

    def update_style(self):
        if self.is_selected:
            self.setStyleSheet("""
                #CompactRowCard {
                    background-color: #eff6ff;
                    border: 1.5px solid #2563eb;
                    border-radius: 4px;
                }
            """)
            self.lbl_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #1d4ed8;")
        else:
            self.setStyleSheet("""
                #CompactRowCard {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 4px;
                }
                #CompactRowCard:hover {
                    background-color: #f8fafc;
                    border-color: #94a3b8;
                }
            """)
            self.lbl_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #0f172a;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.sig_selected.emit(self.plot_path)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        a_view = menu.addAction("👁️ View Fullscreen")
        a_copy = menu.addAction("📋 Copy Image to Clipboard")
        menu.addSeparator()
        a_reveal = menu.addAction("📂 Reveal in File Explorer")

        chosen = menu.exec(event.globalPos())
        if chosen == a_view:
            self.sig_view_fullscreen.emit(self.plot_path)
        elif chosen == a_copy:
            pix = QPixmap(self.plot_path)
            if not pix.isNull():
                QApplication.clipboard().setPixmap(pix)
        elif chosen == a_reveal:
            os.system(f'explorer /select,"{self.plot_path}"')


class PlotGalleryWidget(QWidget):
    """
    Visual Plot Gallery Browser.
    Left dock component displaying thumbnail cards, two-tier dropdown filters, and search.
    """
    sig_plot_selected = Signal(str)
    sig_data_selected = Signal(str)

    def __init__(self, out_dir: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.out_dir = out_dir or DEFAULT_RESULTS_DIR
        self._thumb_cache: Dict[str, Tuple[float, QPixmap]] = {}
        self.all_plots: List[str] = []
        self.card_widgets: Dict[str, QWidget] = {}
        self.active_plot_path: Optional[str] = None
        self.view_mode: str = "cards"
        self.active_category: str = "All"
        self.category_pills: Dict[str, QPushButton] = {}

        self._build_ui()
        self.refresh_gallery()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        # Compact Header Frame (< 85px)
        header = QFrame()
        header.setObjectName("GalleryHeader")
        header.setStyleSheet("""
            QFrame#GalleryHeader {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(6, 6, 6, 6)
        h_lay.setSpacing(4)

        # -------------------------------------------------------------
        # ROW 1: Modern Omnisearch Bar + Refresh Button
        # -------------------------------------------------------------
        r1 = QHBoxLayout()
        r1.setContentsMargins(0, 0, 0, 0)
        r1.setSpacing(4)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("🔍 Filter: mu=1.0, J_K=3.0, DOS, AFM...")
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.setFixedHeight(28)
        self.edit_search.setStyleSheet("""
            QLineEdit {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 14px;
                padding: 2px 10px;
                font-size: 11px;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 1.5px solid #2563eb;
                background: #ffffff;
            }
        """)
        self.edit_search.textChanged.connect(self._filter_and_render_cards)
        r1.addWidget(self.edit_search, 1)

        self.btn_refresh = QToolButton()
        self.btn_refresh.setText("🔄")
        self.btn_refresh.setToolTip("Refresh plot and data catalog")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setFixedSize(28, 28)
        self.btn_refresh.setStyleSheet("""
            QToolButton {
                background: #ffffff; border: 1px solid #cbd5e1;
                border-radius: 14px; font-size: 11px;
            }
            QToolButton:hover { background: #f1f5f9; border-color: #94a3b8; }
        """)
        self.btn_refresh.clicked.connect(self.refresh_gallery)
        r1.addWidget(self.btn_refresh)
        h_lay.addLayout(r1)

        # -------------------------------------------------------------
        # ROW 2: Horizontal Category Pills (One-Click Chips)
        # -------------------------------------------------------------
        pills_lay = QHBoxLayout()
        pills_lay.setContentsMargins(0, 0, 0, 0)
        pills_lay.setSpacing(6)

        self.pill_group = QButtonGroup(self)
        self.pill_group.setExclusive(True)

        categories = [
            ("All", "All"),
            ("🌊 Spectral", "Spectral"),
            ("🧲 Susceptibility", "Susceptibility"),
        ]

        pill_style = """
            QPushButton {
                padding: 3px 10px; border-radius: 11px; font-size: 11px; font-weight: 600;
                border: 1px solid #cbd5e1; background: #f1f5f9; color: #475569;
            }
            QPushButton:hover { background: #e2e8f0; color: #1e293b; }
            QPushButton:checked {
                background-color: #2563eb; color: #ffffff; border-color: #1d4ed8;
            }
        """

        for label, cat_key in categories:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(pill_style)
            if cat_key == "All":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, k=cat_key: self._on_category_pill_clicked(k))
            self.pill_group.addButton(btn)
            pills_lay.addWidget(btn)
            self.category_pills[cat_key] = btn

        pills_lay.addStretch()
        h_lay.addLayout(pills_lay)

        # -------------------------------------------------------------
        # ROW 3: Contextual Sub-Filter + Meta Count + View Mode Switcher
        # -------------------------------------------------------------
        r3 = QHBoxLayout()
        r3.setContentsMargins(0, 0, 0, 0)
        r3.setSpacing(4)

        self.lbl_count = QLabel("0 plots")
        self.lbl_count.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b;")

        self.cb_observable = QComboBox()
        self.cb_observable.setFixedHeight(24)
        self.cb_observable.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 1px 6px; font-size: 10.5px; background: #ffffff; color: #334155;
            }
            QComboBox::drop-down { border: none; }
        """)
        self._populate_observable_types("All")
        self.cb_observable.currentIndexChanged.connect(self._filter_and_render_cards)
        r3.addWidget(self.cb_observable, 1)
        r3.addWidget(self.lbl_count)

        # Dual View Mode Switcher: Cards [▦] vs List [☰]
        self.btn_view_cards = QToolButton()
        self.btn_view_cards.setText("▦")
        self.btn_view_cards.setToolTip("Visual Thumbnail Cards View")
        self.btn_view_cards.setCheckable(True)
        self.btn_view_cards.setChecked(True)
        self.btn_view_cards.setFixedSize(24, 24)

        self.btn_view_list = QToolButton()
        self.btn_view_list.setText("☰")
        self.btn_view_list.setToolTip("Compact Dense List View")
        self.btn_view_list.setCheckable(True)
        self.btn_view_list.setFixedSize(24, 24)

        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)
        self.view_group.addButton(self.btn_view_cards)
        self.view_group.addButton(self.btn_view_list)

        v_style = """
            QToolButton {
                border: 1px solid #cbd5e1; border-radius: 3px;
                background: #ffffff; font-size: 11px; color: #475569;
            }
            QToolButton:hover { background: #f1f5f9; }
            QToolButton:checked { background: #2563eb; color: #ffffff; border-color: #1d4ed8; }
        """
        self.btn_view_cards.setStyleSheet(v_style)
        self.btn_view_list.setStyleSheet(v_style)

        self.btn_view_cards.clicked.connect(lambda: self._set_view_mode("cards"))
        self.btn_view_list.clicked.connect(lambda: self._set_view_mode("list"))

        r3.addWidget(self.btn_view_cards)
        r3.addWidget(self.btn_view_list)
        h_lay.addLayout(r3)

        lay.addWidget(header)

        # Scroll Area for Cards / List Items
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.card_container = QWidget()
        self.card_lay = QVBoxLayout(self.card_container)
        self.card_lay.setSizeConstraint(QVBoxLayout.SetMinimumSize)
        self.card_lay.setContentsMargins(2, 2, 2, 2)
        self.card_lay.setSpacing(5)
        self.card_lay.addStretch()

        self.scroll.setWidget(self.card_container)
        lay.addWidget(self.scroll, 1)

    def _set_view_mode(self, mode: str):
        if self.view_mode != mode:
            self.view_mode = mode
            self.btn_view_cards.blockSignals(True)
            self.btn_view_list.blockSignals(True)
            self.btn_view_cards.setChecked(mode == "cards")
            self.btn_view_list.setChecked(mode == "list")
            self.btn_view_cards.blockSignals(False)
            self.btn_view_list.blockSignals(False)
            self._filter_and_render_cards()

    def _on_category_pill_clicked(self, cat_key: str):
        if cat_key in ("Spectral Results", "Spectral", "Sweeps"):
            norm_key = "Spectral"
        elif cat_key in ("Susceptibility Results", "Susceptibility", "Phase Diagram"):
            norm_key = "Susceptibility"
        else:
            norm_key = "All"

        self.active_category = norm_key
        for k, btn in self.category_pills.items():
            btn.blockSignals(True)
            btn.setChecked(k == norm_key)
            btn.blockSignals(False)
        self._populate_observable_types(norm_key)
        self._filter_and_render_cards()

    def _set_category_by_text(self, text: str):
        cat_map = {
            "All Categories": "All",
            "All": "All",
            "Spectral Results": "Spectral",
            "Spectral": "Spectral",
            "Susceptibility Results": "Susceptibility",
            "Susceptibility": "Susceptibility",
            "Sweeps": "Spectral",
            "Phase Diagram": "Susceptibility"
        }
        target = cat_map.get(text, "All")
        self._on_category_pill_clicked(target)

    @property
    def cb_category(self):
        class _CategoryAdapter:
            def __init__(self, outer):
                self.outer = outer
            def currentText(self):
                if self.outer.active_category == "All":
                    return "All Categories"
                if self.outer.active_category == "Spectral":
                    return "Spectral Results"
                if self.outer.active_category == "Susceptibility":
                    return "Susceptibility Results"
                return self.outer.active_category
            def setCurrentText(self, text):
                self.outer._set_category_by_text(text)
            def blockSignals(self, b):
                pass
        return _CategoryAdapter(self)

    def _on_category_changed(self):
        self._filter_and_render_cards()

    def set_output_dir(self, out_dir: str):
        self.out_dir = out_dir
        self.refresh_gallery()

    def _populate_observable_types(self, category: str):
        self.cb_observable.blockSignals(True)
        self.cb_observable.clear()
        if category in ("Spectral Results", "Spectral"):
            subcats = [
                "All Types",
                "Density of States (DOS)",
                "Fermi Surface (FS)",
                "Band Dispersion (Path)",
                "Quasiparticle Spectral A(k, ω)",
                "IBZ vs Full BZ DOS Comparison"
            ]
        elif category in ("Susceptibility Results", "Susceptibility", "Phase Diagram"):
            subcats = [
                "All Types",
                "Dynamic Susceptibility χ(q, ω)",
                "Static Susceptibility χ(q, 0)",
                "Magnetic Phase Diagram"
            ]
        else:
            subcats = [
                "All Types",
                "Density of States (DOS)",
                "Fermi Surface (FS)",
                "Band Dispersion (Path)",
                "Quasiparticle Spectral A(k, ω)",
                "Dynamic Susceptibility χ(q, ω)",
                "Static Susceptibility χ(q, 0)",
                "Magnetic Phase Diagram",
                "IBZ vs Full BZ DOS Comparison"
            ]
        self.cb_observable.addItems(subcats)
        self.cb_observable.blockSignals(False)

    def refresh_gallery(self):
        """Scans results/plots for all .png figures and pairs with results/data/*.npz."""
        results_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(self.out_dir)

        # Scan plots
        plot_files = []
        if os.path.isdir(plots_dir):
            for p in glob.glob(os.path.join(plots_dir, "*.png")):
                plot_files.append(os.path.normpath(p))

        # Also check backward-compatible subpaths in out_dir
        legacy_dirs = [
            os.path.join(self.out_dir, "many_body_results", "spectral_results", "plots"),
            os.path.join(self.out_dir, "many_body_results", "susceptibility_results", "plots"),
            os.path.join(self.out_dir, "self_energy", "results", "plots"),
        ]
        for ld in legacy_dirs:
            if os.path.isdir(ld):
                for p in glob.glob(os.path.join(ld, "*.png")):
                    norm = os.path.normpath(p)
                    if norm not in plot_files:
                        plot_files.append(norm)

        # Only check external global dirs as fallback if out_dir yielded nothing
        if not plot_files:
            for ext in [
                r"C:\Users\sruji\Projects\masters_thesis\self_energy\results\plots",
                r"C:\Users\sruji\Projects\masters_thesis\many_body_results\spectral_results\plots",
                r"C:\Users\sruji\Projects\masters_thesis\many_body_results\susceptibility_results\plots",
            ]:
                if os.path.isdir(ext):
                    for p in glob.glob(os.path.join(ext, "*.png")):
                        norm = os.path.normpath(p)
                        if norm not in plot_files:
                            plot_files.append(norm)

        # Sort newest first
        plot_files.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
        self.all_plots = plot_files

        # Map available .npz datasets for pairing across out_dir
        self.available_data = {}
        data_dirs_to_check = [
            data_dir,
            os.path.join(self.out_dir, "many_body_results", "spectral_results", "data"),
            os.path.join(self.out_dir, "many_body_results", "susceptibility_results", "data"),
            os.path.join(self.out_dir, "self_energy", "results", "data"),
        ]
        for dd in data_dirs_to_check:
            if os.path.isdir(dd):
                for d in glob.glob(os.path.join(dd, "*.npz")):
                    stem = os.path.splitext(os.path.basename(d))[0]
                    if stem not in self.available_data:
                        self.available_data[stem] = os.path.normpath(d)

        # Fallback to external global data dirs if none found
        if not self.available_data:
            for ext in [
                r"C:\Users\sruji\Projects\masters_thesis\self_energy\results\data",
                r"C:\Users\sruji\Projects\masters_thesis\many_body_results\spectral_results\data",
                r"C:\Users\sruji\Projects\masters_thesis\many_body_results\susceptibility_results\data",
            ]:
                if os.path.isdir(ext):
                    for d in glob.glob(os.path.join(ext, "*.npz")):
                        stem = os.path.splitext(os.path.basename(d))[0]
                        if stem not in self.available_data:
                            self.available_data[stem] = os.path.normpath(d)

        self._filter_and_render_cards()

    def _find_paired_data(self, plot_path: str) -> Optional[str]:
        """Finds corresponding .npz data file for a given plot."""
        stem = os.path.splitext(os.path.basename(plot_path))[0]
        if stem in self.available_data:
            return self.available_data[stem]

        # 1. Sweep subplot match: sweep_DOS_atJ_perp_... -> sweep_data_atJ_perp_...
        sub_pat = re.sub(r'sweep_(DOS|FS|Path)_', 'sweep_data_', stem, flags=re.IGNORECASE)
        if sub_pat in self.available_data:
            return self.available_data[sub_pat]

        # 2. Match companion multi-value sweeps: sweep_data_at... or sweep_JK_vals_...
        clean_stem = re.sub(r'_eta_[0-9.]+', '', stem)
        for dstem, dpath in self.available_data.items():
            clean_dstem = re.sub(r'_eta_[0-9.]+', '', dstem)
            if clean_stem == clean_dstem or clean_stem in clean_dstem or clean_dstem in clean_stem:
                return dpath

            # Check parameter overlap (e.g. J_perp=5.0 or 6.0 and mu=1.0)
            if 'j_perp_5.0' in clean_stem.lower() and 'j_perp_5.0' in clean_dstem.lower():
                return dpath
            if 'j_perp_6.0' in clean_stem.lower() and 'j_perp_6.0' in clean_dstem.lower():
                return dpath

        return None

    def _filter_and_render_cards(self):
        cat = self.active_category
        obs = self.cb_observable.currentText()
        query = self.edit_search.text().strip()

        filtered = []
        for p in self.all_plots:
            title, params_str, cat_tag, obs_type, fname = parse_plot_metadata(p)

            # Category filter: all spectral plots in Spectral, all susceptibility & phase diagrams in Susceptibility
            if cat in ("Spectral Results", "Spectral"):
                is_spectral = ("Spectral" in cat_tag) or any(k in p.lower() for k in ("spectral", "dos", "path", "fs", "both", "dispersion"))
                if not is_spectral:
                    continue
            elif cat in ("Susceptibility Results", "Susceptibility"):
                is_susc = ("Susceptibility" in cat_tag) or any(k in p.lower() for k in ("susc", "chi", "phase"))
                if not is_susc:
                    continue
            elif cat == "Phase Diagram":
                is_phase = ("Phase" in title) or ("Phase" in obs_type) or ("phase" in p.lower())
                if not is_phase:
                    continue

            # Observable Type filter
            if obs != "All Types":
                if obs.lower() not in obs_type.lower() and obs.lower() not in title.lower():
                    continue

            # Smart Search Matcher
            if query:
                params = parse_filename_parameters(p)
                corpus = f"{title} {params_str} {fname} {cat_tag} {obs_type}".lower()
                run_mock = {
                    "params": params,
                    "search_corpus": corpus
                }
                if not SmartSearchMatcher.run_matches(run_mock, query):
                    continue

            filtered.append(p)

        self.lbl_count.setText(f"{len(filtered)} plot{'s' if len(filtered) != 1 else ''}")

        # Cleanly remove and hide all previous widgets
        while self.card_lay.count():
            item = self.card_lay.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self.card_widgets.clear()

        if not filtered:
            if query:
                msg = f"🔍 No plots match '{query}'\n💡 Tip: Try mu=1.0, J_K=3.0, DOS, AFM..."
            else:
                msg = "No plots found matching current category filter."
            lbl_empty = QLabel(msg)
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet("color: #94a3b8; font-size: 11px; padding: 24px;")
            self.card_lay.addWidget(lbl_empty)
            self.card_lay.addStretch()
            return

        for p in filtered:
            data_p = self._find_paired_data(p)
            if self.view_mode == "list":
                card = CompactRowCard(plot_path=p, data_path=data_p, parent=self.card_container)
            else:
                card = ThumbnailCard(plot_path=p, data_path=data_p, parent=self.card_container)
                self._load_thumbnail(card, p)

            card.sig_selected.connect(self._on_card_selected)
            card.sig_view_fullscreen.connect(self.sig_plot_selected.emit)
            card.sig_explore_data.connect(self.sig_data_selected.emit)

            if self.active_plot_path and os.path.normcase(p) == os.path.normcase(self.active_plot_path):
                card.set_selected(True)

            self.card_lay.addWidget(card)
            self.card_widgets[p] = card

        self.card_lay.addStretch()

        if not self.active_plot_path and filtered:
            self._on_card_selected(filtered[0])

    def _load_thumbnail(self, card: ThumbnailCard, plot_path: str):
        try:
            mtime = os.path.getmtime(plot_path)
            if plot_path in self._thumb_cache:
                c_mtime, c_pix = self._thumb_cache[plot_path]
                if c_mtime == mtime:
                    card.set_thumbnail_pixmap(c_pix)
                    return

            pix = QPixmap(plot_path)
            if not pix.isNull():
                self._thumb_cache[plot_path] = (mtime, pix)
                card.set_thumbnail_pixmap(pix)
        except Exception:
            pass

    def _on_card_selected(self, plot_path: str):
        self.active_plot_path = plot_path
        for p, card in self.card_widgets.items():
            card.set_selected(os.path.normcase(p) == os.path.normcase(plot_path))
        self.sig_plot_selected.emit(plot_path)

    def select_plot(self, plot_path: str):
        norm = os.path.normpath(plot_path)
        if norm in self.card_widgets:
            self._on_card_selected(norm)
