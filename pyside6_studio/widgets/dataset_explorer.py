"""Smart Research Navigator & Dataset Explorer for Many-Body Studio Pro.
Organizes simulations into grouped calculation runs (plots + raw numerical arrays),
provides real-time parameter searching, and displays an active run metadata card with action controls.
"""

import os
import re
import time
import glob
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTreeWidget, QTreeWidgetItem, QFrame,
    QMessageBox, QButtonGroup, QHeaderView, QMenu
)

from pyside6_studio.core.config import DEFAULT_RESULTS_DIR
from pyside6_studio.core.cache_manager import normalize_results_dir


def format_bytes(size: int) -> str:
    """Formats bytes into human-readable string."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.2f} MB"


def parse_filename_parameters(filename: str) -> dict:
    """Extracts physical parameters from standard filename conventions as fallback."""
    params = {}
    base = os.path.splitext(os.path.basename(filename))[0]

    mu_m = re.search(r"mu[_=]?([0-9]+(?:\.[0-9]+)?)", base, re.IGNORECASE)
    if mu_m:
        try: params["mu"] = float(mu_m.group(1))
        except ValueError: pass

    t_m = re.search(r"(?:^|[^0-9a-zA-Z])t[_=]?([0-9]+(?:\.[0-9]+)?)", base)
    if t_m:
        try: params["t"] = float(t_m.group(1))
        except ValueError: pass

    t1_m = re.search(r"t1[_=]?([0-9]+(?:\.[0-9]+)?)", base, re.IGNORECASE)
    if t1_m:
        try: params["t1"] = float(t1_m.group(1))
        except ValueError: pass

    k_m = re.search(r"(?:^|[^0-9a-zA-Z])K[_=]?([0-9]+(?:\.[0-9]+)?)", base)
    if k_m:
        try: params["K"] = float(k_m.group(1))
        except ValueError: pass

    n_m = re.search(r"(?:^|[^0-9a-zA-Z])N[_=]?(\d+)", base)
    if n_m:
        try: params["N"] = int(n_m.group(1))
        except ValueError: pass

    nw_m = re.search(r"(?:Nw|num_omega|w)[_=]?(\d+)", base, re.IGNORECASE)
    if nw_m:
        try: params["num_omega"] = int(nw_m.group(1))
        except ValueError: pass

    eta_m = re.search(r"eta[_=]?([0-9]+(?:\.[0-9]+)?)", base, re.IGNORECASE)
    if eta_m:
        try: params["eta"] = float(eta_m.group(1))
        except ValueError: pass

    jp_m = re.search(r"(?:J_perp|Jperp|fixed_J)[_=]?([0-9]+(?:\.[0-9]+)?)", base, re.IGNORECASE)
    if jp_m:
        try:
            val = float(jp_m.group(1))
            params["fixed_jperp"] = val
            params["jperp"] = val
        except ValueError: pass

    # Multi-value or single JK
    jk_vals_m = re.search(r"(?:J_K|JK)_vals_([0-9._]+)", base, re.IGNORECASE)
    if jk_vals_m:
        raw = jk_vals_m.group(1).split('_Jperp')[0]
        vals = []
        for v in raw.split('_'):
            try: vals.append(float(v))
            except ValueError: pass
        if vals:
            params["jk"] = vals
            params["fixed_jk"] = vals[0]
    else:
        jk_m = re.search(r"(?:J_K|JK|fixed_JK)[_=]?([0-9]+(?:\.[0-9]+)?)", base, re.IGNORECASE)
        if jk_m:
            try:
                val = float(jk_m.group(1))
                params["fixed_jk"] = val
                params["jk"] = [val]
            except ValueError: pass

    return params


def read_npz_metadata(npz_path: str) -> dict:
    """Quickly extracts model parameters and array summary from a .npz file."""
    meta = parse_filename_parameters(npz_path)
    if not os.path.isfile(npz_path):
        return meta

    try:
        with np.load(npz_path, mmap_mode="r") as data:
            files = list(data.files)
            meta["array_keys"] = files
            for k in ["mu", "t", "t1", "K", "N", "num_omega", "omega_max", "eta", "fixed_coupling", "sweep_mode", "is_ibz"]:
                if k in files:
                    val = data[k]
                    if isinstance(val, np.ndarray) and val.size == 1:
                        meta[k] = val.item()
                    elif not isinstance(val, np.ndarray):
                        meta[k] = val

            if "is_ibz" in files:
                meta["is_ibz"] = bool(data["is_ibz"])

            if "sig_re" in files:
                meta["array_dtype"] = str(data["sig_re"].dtype)
                meta["array_shape"] = tuple(data["sig_re"].shape)
            elif "sig1_re" in files:
                meta["array_dtype"] = str(data["sig1_re"].dtype)
                meta["array_shape"] = tuple(data["sig1_re"].shape)

            if "omega" in files:
                meta["omega_len"] = len(data["omega"])
            if "labels" in files:
                lbls = data["labels"]
                meta["labels"] = [str(x) for x in lbls]
            if "sweep_values" in files:
                meta["sweep_values"] = list(data["sweep_values"])
    except Exception:
        pass
    return meta


class SmartSearchMatcher:
    """Intelligent scientific query matcher supporting exact/approximate parameter matches and multi-token keywords."""

    @staticmethod
    def normalize_key(k: str) -> str:
        k = k.lower().strip()
        if k in ("mu", "μ"): return "mu"
        if k in ("jk", "j_k", "fixed_jk"): return "jk"
        if k in ("jperp", "j_perp", "fixed_j", "fixed_jperp", "jp"): return "jperp"
        if k in ("eta", "η"): return "eta"
        if k in ("n", "grid", "resolution"): return "n"
        if k in ("nw", "num_omega", "omega_pts"): return "num_omega"
        if k in ("t",): return "t"
        if k in ("t1", "t_prime", "tp"): return "t1"
        if k in ("k",): return "k"
        return k

    @classmethod
    def run_matches(cls, run: dict, query: str) -> bool:
        query = query.strip()
        if not query:
            return True

        # 1. Extract key=val or key:val patterns from query
        kv_pairs = re.findall(r"([a-zA-Z_μ]+)\s*[=:]\s*([0-9.]+|[a-zA-Z]+)", query)
        free_text = re.sub(r"([a-zA-Z_μ]+)\s*[=:]\s*([0-9.]+|[a-zA-Z]+)", " ", query).strip()
        words = free_text.split()

        run_params = run.get("params", {})
        corpus = run.get("search_corpus", "")

        # 2. Match Key-Value requirements
        for raw_k, raw_v in kv_pairs:
            norm_k = cls.normalize_key(raw_k)
            try:
                target_val = float(raw_v)
                is_num = True
            except ValueError:
                is_num = False

            matched_param = False
            for pkey, pval in run_params.items():
                if cls.normalize_key(pkey) == norm_k:
                    if is_num:
                        if isinstance(pval, list):
                            def _match_target(elem):
                                try:
                                    return abs(float(elem) - target_val) < 1e-3
                                except (ValueError, TypeError):
                                    return False
                            if any(_match_target(elem) for elem in pval):
                                matched_param = True
                                break
                        elif isinstance(pval, (int, float)):
                            if abs(float(pval) - target_val) < 1e-3:
                                matched_param = True
                                break
                    else:
                        if str(raw_v).lower() in str(pval).lower():
                            matched_param = True
                            break

            if not matched_param:
                fallback_patterns = [
                    f"{raw_k}_{raw_v}".lower(),
                    f"{raw_k} {raw_v}".lower(),
                    f"{raw_k}={raw_v}".lower(),
                    f"{norm_k}_{raw_v}".lower(),
                    f"{norm_k} {raw_v}".lower(),
                    f"{norm_k}={raw_v}".lower(),
                ]
                if not any(pat in corpus for pat in fallback_patterns):
                    return False

        # 3. Match Free Text words (AND logic)
        for w in words:
            w_lower = w.lower()
            try:
                w_float = float(w_lower)
                num_matched = False
                for pval in run_params.values():
                    if isinstance(pval, list):
                        def _match_w(elem):
                            try:
                                return abs(float(elem) - w_float) < 1e-3
                            except (ValueError, TypeError):
                                return False
                        if any(_match_w(elem) for elem in pval):
                            num_matched = True
                            break
                    elif isinstance(pval, (int, float)):
                        if abs(float(pval) - w_float) < 1e-3:
                            num_matched = True
                            break
                if num_matched:
                    continue
            except ValueError:
                pass

            if w_lower not in corpus and w_lower.replace("_", " ") not in corpus:
                return False

        return True


class DatasetExplorerWidget(QWidget):
    """Modern Research Workspace & Dataset Explorer dock widget."""

    sig_view_plot = Signal(str)
    sig_explore_data = Signal(str, dict)
    sig_compare = Signal(str)
    sig_open_cache_dialog = Signal()

    def __init__(self, out_dir: str = DEFAULT_RESULTS_DIR, parent=None):
        super().__init__(parent)
        self.out_dir = out_dir
        self.active_filter = "all"  # "all", "Sweeps", "Spectral", "Susceptibility", "Phase Diagram"
        self._runs_data = []
        self._selected_item_data = None
        self.is_dark = False

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(6)

        # 1. Top Utility Header
        top_bar = QHBoxLayout()
        top_bar.setSpacing(4)

        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setToolTip("Refresh study records from results folder")
        self.btn_refresh.setFixedWidth(32)
        self.btn_refresh.clicked.connect(self.refresh)
        top_bar.addWidget(self.btn_refresh)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("🔍 Filter: mu=1.0, J_K=3.0, DOS, AFM...")
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.edit_search)

        self.btn_open_folder = QPushButton("📂")
        self.btn_open_folder.setToolTip("Open results folder in Windows Explorer")
        self.btn_open_folder.setFixedWidth(32)
        self.btn_open_folder.clicked.connect(self._open_results_folder)
        top_bar.addWidget(self.btn_open_folder)

        main_layout.addLayout(top_bar)

        # 2. Segmented Category Filter Pills
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(3)
        self.btn_group_filter = QButtonGroup(self)

        self.pills = [
            ("All", "all"),
            ("📊 Sweeps", "Sweeps"),
            ("🔬 Spectral", "Spectral"),
            ("🧲 Susc", "Susceptibility"),
            ("🗺️ Phase", "Phase Diagram"),
        ]

        for idx, (label, tag) in enumerate(self.pills):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    padding: 3px 6px;
                    font-size: 11px;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    background: transparent;
                }
                QPushButton:checked {
                    background-color: #2563eb;
                    color: #ffffff;
                    border-color: #1d4ed8;
                    font-weight: 600;
                }
            """)
            self.btn_group_filter.addButton(btn, idx)
            filter_bar.addWidget(btn)
            if idx == 0:
                btn.setChecked(True)

        self.btn_group_filter.idClicked.connect(self._on_filter_changed)
        main_layout.addLayout(filter_bar)

        # 3. Hierarchical Run Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.itemClicked.connect(self._on_tree_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        main_layout.addWidget(self.tree, 1)

        # 4. Bottom Selection Inspector & Action Card
        self.card_inspector = QFrame()
        self.card_inspector.setObjectName("DatasetInspectorCard")
        self.card_inspector.setStyleSheet("""
            QFrame#DatasetInspectorCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        card_lay = QVBoxLayout(self.card_inspector)
        card_lay.setContentsMargins(6, 6, 6, 6)
        card_lay.setSpacing(5)

        # Card Title and Type Badge
        title_row = QHBoxLayout()
        self.lbl_card_title = QLabel("Select a study or dataset")
        self.lbl_card_title.setStyleSheet("font-weight: 700; font-size: 12px; color: #0f172a;")
        self.lbl_card_title.setWordWrap(True)
        title_row.addWidget(self.lbl_card_title, 1)

        self.lbl_card_badge = QLabel("")
        self.lbl_card_badge.setStyleSheet(
            "font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; "
            "background-color: #e2e8f0; color: #475569;"
        )
        self.lbl_card_badge.setVisible(False)
        title_row.addWidget(self.lbl_card_badge)
        card_lay.addLayout(title_row)

        # File stats (Size / Date)
        self.lbl_card_stats = QLabel("No selection")
        self.lbl_card_stats.setStyleSheet("font-size: 11px; color: #64748b;")
        card_lay.addWidget(self.lbl_card_stats)

        # Parameter pill grid
        self.lbl_card_params = QLabel("")
        self.lbl_card_params.setStyleSheet(
            "font-size: 11px; color: #334155; background-color: #f8fafc; "
            "border: 1px solid #f1f5f9; border-radius: 4px; padding: 4px;"
        )
        self.lbl_card_params.setWordWrap(True)
        self.lbl_card_params.setVisible(False)
        card_lay.addWidget(self.lbl_card_params)

        # Action Buttons Row
        self.btn_row = QHBoxLayout()
        self.btn_row.setSpacing(4)

        self.btn_view_plot = QPushButton("👁️ View Plot")
        self.btn_view_plot.setToolTip("View plot in Plot Viewer canvas")
        self.btn_view_plot.setStyleSheet("padding: 4px 8px; font-size: 11px; font-weight: 600;")
        self.btn_view_plot.clicked.connect(self._on_action_view_plot)
        self.btn_row.addWidget(self.btn_view_plot)

        self.btn_explore_data = QPushButton("🔬 Explore Data")
        self.btn_explore_data.setToolTip("Load raw numerical arrays into interactive data studio")
        self.btn_explore_data.setStyleSheet(
            "padding: 4px 8px; font-size: 11px; font-weight: 600; "
            "background-color: #2563eb; color: #ffffff; border: 1px solid #1d4ed8; border-radius: 4px;"
        )
        self.btn_explore_data.clicked.connect(self._on_action_explore_data)
        self.btn_row.addWidget(self.btn_explore_data)

        self.btn_compare = QPushButton("⚏ Compare")
        self.btn_compare.setToolTip("Load into comparative split viewport")
        self.btn_compare.setStyleSheet("padding: 4px 8px; font-size: 11px;")
        self.btn_compare.clicked.connect(self._on_action_compare)
        self.btn_row.addWidget(self.btn_compare)

        card_lay.addLayout(self.btn_row)

        # Extra utility actions
        extra_row = QHBoxLayout()
        extra_row.setSpacing(4)

        self.btn_reveal = QPushButton("📂 Reveal")
        self.btn_reveal.setStyleSheet("padding: 3px 6px; font-size: 10px;")
        self.btn_reveal.clicked.connect(self._on_action_reveal)
        extra_row.addWidget(self.btn_reveal)

        self.btn_delete = QPushButton("🗑️ Delete")
        self.btn_delete.setStyleSheet("padding: 3px 6px; font-size: 10px; color: #b91c1c; background-color: #fee2e2; border: 1px solid #fca5a5;")
        self.btn_delete.clicked.connect(self._on_action_delete)
        extra_row.addWidget(self.btn_delete)

        extra_row.addStretch()
        card_lay.addLayout(extra_row)

        self._set_actions_enabled(False)
        main_layout.addWidget(self.card_inspector)

    def set_theme(self, is_dark: bool):
        """Updates inspector card and styling dynamically based on theme."""
        self.is_dark = is_dark
        if is_dark:
            self.card_inspector.setStyleSheet("""
                QFrame#DatasetInspectorCard {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 6px;
                }
            """)
            self.lbl_card_title.setStyleSheet("font-weight: 700; font-size: 12px; color: #f8fafc;")
            self.lbl_card_stats.setStyleSheet("font-size: 11px; color: #94a3b8;")
            self.lbl_card_params.setStyleSheet(
                "font-size: 11px; color: #cbd5e1; background-color: #0f172a; "
                "border: 1px solid #334155; border-radius: 4px; padding: 4px;"
            )
        else:
            self.card_inspector.setStyleSheet("""
                QFrame#DatasetInspectorCard {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                    padding: 6px;
                }
            """)
            self.lbl_card_title.setStyleSheet("font-weight: 700; font-size: 12px; color: #0f172a;")
            self.lbl_card_stats.setStyleSheet("font-size: 11px; color: #64748b;")
            self.lbl_card_params.setStyleSheet(
                "font-size: 11px; color: #334155; background-color: #f8fafc; "
                "border: 1px solid #f1f5f9; border-radius: 4px; padding: 4px;"
            )

    def set_output_dir(self, out_dir: str):
        """Updates root results directory and triggers scan."""
        self.out_dir = out_dir
        self.refresh()

    def refresh(self):
        """Scans results folder and builds unified calculation run records."""
        results_dir, plots_dir, data_dir, _ = normalize_results_dir(self.out_dir)

        # 1. Collect strictly observable outputs: generated plots and observable datasets (no cache)
        plots = [p for p in glob.glob(os.path.join(plots_dir, "*.*")) if p.lower().endswith((".png", ".pdf", ".svg"))]
        data_files = [d for d in glob.glob(os.path.join(data_dir, "*.npz"))]

        runs = {}

        # Group 1: Spectral Sweeps (DOS, FS, Path)
        for p in plots:
            base = os.path.basename(p)
            if base.startswith(("sweep_DOS_", "sweep_FS_", "sweep_Path_")):
                suffix = re.sub(r"^sweep_(DOS|FS|Path)_", "", base)
                suffix = os.path.splitext(suffix)[0]
                run_key = f"spectral_sweep_{suffix}"
                if run_key not in runs:
                    runs[run_key] = {
                        "category": "Sweeps",
                        "study_type": "Spectral Sweep",
                        "key": run_key,
                        "title": f"Spectral Sweep ({suffix})",
                        "plots": {},
                        "data": None,
                        "additional_data": [],
                        "mtime": os.path.getmtime(p),
                        "total_size": 0
                    }
                ptype = "DOS" if "sweep_DOS" in base else ("Fermi Surface" if "sweep_FS" in base else "Dispersion Path")
                runs[run_key]["plots"][ptype] = p
                runs[run_key]["total_size"] += os.path.getsize(p)
                runs[run_key]["mtime"] = max(runs[run_key]["mtime"], os.path.getmtime(p))

        for d in data_files:
            base = os.path.basename(d)
            if base.startswith("sweep_data_"):
                suffix = base.replace("sweep_data_", "").replace(".npz", "")
                run_key = f"spectral_sweep_{suffix}"
                if run_key in runs:
                    runs[run_key]["data"] = d
                    runs[run_key]["total_size"] += os.path.getsize(d)
                else:
                    runs[run_key] = {
                        "category": "Sweeps",
                        "study_type": "Spectral Sweep",
                        "key": run_key,
                        "title": f"Spectral Sweep ({suffix})",
                        "plots": {},
                        "data": d,
                        "additional_data": [],
                        "mtime": os.path.getmtime(d),
                        "total_size": os.path.getsize(d)
                    }
            elif base.startswith("sweep_JK_vals_"):
                # Associate with matching spectral sweep by Jperp and mu if present
                matched = False
                for rk, rdata in runs.items():
                    if rdata["category"] == "Sweeps":
                        if ("Jperp_6.00" in base and "atJ_perp_6.0" in rk and "mu_1.0" in rk) or \
                           ("Jperp_5.00" in base and "atJ_perp_5.0" in rk and "mu_1.0" in rk):
                            rdata["additional_data"].append(d)
                            rdata["total_size"] += os.path.getsize(d)
                            matched = True
                            break
                if not matched:
                    runs[f"sweep_vals_{base}"] = {
                        "category": "Sweeps",
                        "study_type": "Sweep Array Dataset",
                        "key": f"sweep_vals_{base}",
                        "title": f"Sweep Data: {base[:32]}...",
                        "plots": {},
                        "data": d,
                        "additional_data": [],
                        "mtime": os.path.getmtime(d),
                        "total_size": os.path.getsize(d)
                    }

        # Group 2: Single Point Spectral Functions A(k, w) and Self-Energy
        for p in plots:
            base = os.path.basename(p)
            if base.startswith(("both_", "spectral_only_", "self_energy_only_")):
                base_no_ext = os.path.splitext(base)[0]
                s_key = re.sub(r"^(both|spectral_only|self_energy_only)_", "", base_no_ext)
                s_key = re.sub(r"_eta_[0-9]+(?:\.[0-9]+)?$", "", s_key)
                run_key = f"spectral_func_{s_key}"
                if run_key not in runs:
                    runs[run_key] = {
                        "category": "Spectral",
                        "study_type": "Spectral Function",
                        "key": run_key,
                        "title": f"Spectral Function ({s_key})",
                        "plots": {},
                        "data": None,
                        "additional_data": [],
                        "mtime": os.path.getmtime(p),
                        "total_size": 0
                    }
                ptype = "Composite Figure" if "both_" in base else ("Spectral A(k,w)" if "spectral_only" in base else "Self-Energy Σ")
                runs[run_key]["plots"][ptype] = p
                runs[run_key]["total_size"] += os.path.getsize(p)
                runs[run_key]["mtime"] = max(runs[run_key]["mtime"], os.path.getmtime(p))

        for d in data_files:
            base = os.path.basename(d)
            if base.startswith(("both_", "spectral_only_", "self_energy_only_")):
                base_no_ext = os.path.splitext(base)[0]
                s_key = re.sub(r"^(both|spectral_only|self_energy_only)_", "", base_no_ext)
                s_key = re.sub(r"_eta_[0-9]+(?:\.[0-9]+)?$", "", s_key)
                run_key = f"spectral_func_{s_key}"
                if run_key in runs:
                    runs[run_key]["data"] = d
                    runs[run_key]["total_size"] += os.path.getsize(d)
                else:
                    runs[run_key] = {
                        "category": "Spectral",
                        "study_type": "Spectral Function",
                        "key": run_key,
                        "title": f"Spectral Function ({s_key})",
                        "plots": {},
                        "data": d,
                        "additional_data": [],
                        "mtime": os.path.getmtime(d),
                        "total_size": os.path.getsize(d)
                    }

        # Group 3: Phase Diagrams
        for p in plots:
            base = os.path.basename(p)
            if base.startswith("phase_diagram_"):
                suffix = base.replace("phase_diagram_", "").replace(".png", "").replace(".pdf", "").replace(".svg", "")
                run_key = f"phase_diagram_{suffix}"
                if run_key not in runs:
                    runs[run_key] = {
                        "category": "Phase Diagram",
                        "study_type": "Phase Diagram",
                        "key": run_key,
                        "title": f"Phase Diagram ({suffix})",
                        "plots": {"Phase Boundary": p},
                        "data": None,
                        "additional_data": [],
                        "mtime": os.path.getmtime(p),
                        "total_size": os.path.getsize(p)
                    }

        for d in data_files:
            base = os.path.basename(d)
            if base.startswith("phase_diagram_"):
                suffix = base.replace("phase_diagram_", "").replace(".npz", "")
                run_key = f"phase_diagram_{suffix}"
                if run_key in runs:
                    runs[run_key]["data"] = d
                    runs[run_key]["total_size"] += os.path.getsize(d)
                else:
                    runs[run_key] = {
                        "category": "Phase Diagram",
                        "study_type": "Phase Diagram",
                        "key": run_key,
                        "title": f"Phase Diagram ({suffix})",
                        "plots": {},
                        "data": d,
                        "additional_data": [],
                        "mtime": os.path.getmtime(d),
                        "total_size": os.path.getsize(d)
                    }

        # Group 4: Susceptibility
        for p in plots:
            base = os.path.basename(p)
            if "static" in base or "dynamic" in base:
                if "phase_diagram" not in base and not base.startswith("sweep_DOS"):
                    base_no_ext = os.path.splitext(base)[0]
                    run_key = f"susc_{base_no_ext}"
                    runs[run_key] = {
                        "category": "Susceptibility",
                        "study_type": "Susceptibility Map",
                        "key": run_key,
                        "title": f"Susceptibility: {base_no_ext}",
                        "plots": {"Map": p},
                        "data": None,
                        "additional_data": [],
                        "mtime": os.path.getmtime(p),
                        "total_size": os.path.getsize(p)
                    }

        for d in data_files:
            base = os.path.basename(d)
            if ("static" in base or "dynamic" in base) and not base.startswith("sweep_data"):
                base_no_ext = os.path.splitext(base)[0]
                run_key = f"susc_{base_no_ext}"
                if run_key in runs:
                    runs[run_key]["data"] = d
                    runs[run_key]["total_size"] += os.path.getsize(d)
                else:
                    runs[run_key] = {
                        "category": "Susceptibility",
                        "study_type": "Susceptibility Array",
                        "key": run_key,
                        "title": f"Susceptibility: {base_no_ext}",
                        "plots": {},
                        "data": d,
                        "additional_data": [],
                        "mtime": os.path.getmtime(d),
                        "total_size": os.path.getsize(d)
                    }

        # Catch-all for any remaining unassigned plots
        handled_plots = set()
        for r in runs.values():
            handled_plots.update(r["plots"].values())
        for p in plots:
            if p not in handled_plots:
                base = os.path.basename(p)
                runs[f"custom_plot_{base}"] = {
                    "category": "Other Studies",
                    "study_type": "Custom Plot",
                    "key": f"custom_plot_{base}",
                    "title": base,
                    "plots": {"Figure": p},
                    "data": None,
                    "additional_data": [],
                    "mtime": os.path.getmtime(p),
                    "total_size": os.path.getsize(p)
                }

        # Catch-all for any remaining unassigned datasets
        handled_data = set()
        for r in runs.values():
            if r["data"]: handled_data.add(r["data"])
            handled_data.update(r.get("additional_data", []))
        for d in data_files:
            if d not in handled_data:
                base = os.path.basename(d)
                runs[f"custom_data_{base}"] = {
                    "category": "Other Studies",
                    "study_type": "Custom Dataset",
                    "key": f"custom_data_{base}",
                    "title": base,
                    "plots": {},
                    "data": d,
                    "additional_data": [],
                    "mtime": os.path.getmtime(d),
                    "total_size": os.path.getsize(d)
                }

        # Build metadata and search indices for each run
        for r in runs.values():
            self._build_run_metadata(r)

        self._runs_data = list(runs.values())
        self._populate_tree()

    def _build_run_metadata(self, run: dict):
        """Extracts physical parameters and compiles the comprehensive search index for a run."""
        plot_bases = [os.path.basename(p) for p in run["plots"].values()]
        data_bases = [os.path.basename(run["data"])] if run.get("data") else []
        data_bases += [os.path.basename(d) for d in run.get("additional_data", [])]

        combined_names = " ".join(plot_bases + data_bases)
        combined_text = f"{run['title']} {run['category']} {run['study_type']} {run['key']} {combined_names}"

        params = parse_filename_parameters(combined_text)

        # Read numerical metadata from primary dataset if available
        if run.get("data") and os.path.isfile(run["data"]):
            npz_meta = read_npz_metadata(run["data"])
            for k, v in npz_meta.items():
                if k not in params and isinstance(v, (int, float, list)):
                    params[k] = v

        run["params"] = params

        # Compile rich search corpus
        norm_text = combined_text.lower().replace("_", " ").replace("-", " ")
        param_tokens = []
        for k, v in params.items():
            if isinstance(v, list):
                for x in v:
                    int_str = f"{k}={int(x)}" if isinstance(x, float) and x.is_integer() else ""
                    param_tokens.extend([f"{k}={x}", f"{k}:{x}", f"{k} {x}", f"{k}_{x}"])
                    if int_str: param_tokens.append(int_str)
            elif isinstance(v, float):
                int_str = f"{k}={int(v)}" if v.is_integer() else ""
                param_tokens.extend([f"{k}={v}", f"{k}:{v}", f"{k} {v}", f"{k}_{v}"])
                if int_str: param_tokens.append(int_str)
            else:
                param_tokens.extend([f"{k}={v}", f"{k}:{v}", f"{k} {v}", f"{k}_{v}"])

        aliases = []
        if "fs" in norm_text or "fermi" in norm_text:
            aliases.extend(["fermi", "surface", "fermi surface"])
        if "dos" in norm_text:
            aliases.extend(["density of states", "dos"])
        if "path" in norm_text:
            aliases.extend(["dispersion", "band structure", "path"])
        if "afm" in norm_text:
            aliases.extend(["antiferromagnetic", "afm"])
        if "fm" in norm_text and "afm" not in norm_text:
            aliases.extend(["ferromagnetic", "fm"])

        run["search_corpus"] = f"{combined_text.lower()} {norm_text} {' '.join(param_tokens)} {' '.join(aliases)}".lower()

    def _populate_tree(self):
        """Populates the QTreeWidget based on active category filter and search query."""
        search_query = self.edit_search.text().strip()
        self.tree.clear()

        sorted_runs = sorted(self._runs_data, key=lambda x: x["mtime"], reverse=True)

        matching_runs = []
        for run in sorted_runs:
            # 1. Category filter
            if self.active_filter != "all" and run["category"] != self.active_filter:
                continue

            # 2. Search matcher
            if search_query and not SmartSearchMatcher.run_matches(run, search_query):
                continue

            matching_runs.append(run)

        # Empty state handling
        if not matching_runs:
            empty_item = QTreeWidgetItem(self.tree, [f"🔍 No runs match '{search_query}'" if search_query else "📁 No simulation records found"])
            empty_item.setForeground(0, QColor("#94a3b8"))
            if search_query:
                hint_item = QTreeWidgetItem(empty_item, ["💡 Tip: Search mu=1.0, J_K=3.0, DOS, AFM, N=64..."])
                hint_item.setForeground(0, QColor("#64748b"))
                empty_item.setExpanded(True)
            return

        category_nodes = {}
        for run in matching_runs:
            cat = run["category"]
            if cat not in category_nodes:
                cat_label = f"📊 {cat.upper()}" if cat == "Sweeps" else (
                    f"🔬 {cat.upper()}" if cat == "Spectral" else (
                        f"🧲 {cat.upper()}" if cat == "Susceptibility" else (
                            f"🗺️ {cat.upper()}" if cat == "Phase Diagram" else f"📁 {cat.upper()}"
                        )
                    )
                )
                cnode = QTreeWidgetItem(self.tree, [cat_label])
                cnode.setExpanded(True)
                font = cnode.font(0)
                font.setBold(True)
                cnode.setFont(0, font)
                category_nodes[cat] = cnode

            t_str = time.strftime("%b %d, %H:%M", time.localtime(run["mtime"]))
            run_node = QTreeWidgetItem(category_nodes[cat], [f"📁 {run['title']} ({t_str})"])
            run_node.setData(0, Qt.UserRole, {"type": "run", "data": run})

            # Add child plot items
            for ptype, ppath in run["plots"].items():
                p_size = format_bytes(os.path.getsize(ppath)) if os.path.exists(ppath) else ""
                pitem = QTreeWidgetItem(run_node, [f"🖼️ {ptype} [{p_size}]"])
                pitem.setData(0, Qt.UserRole, {"type": "plot", "path": ppath, "run": run})

            # Add primary numerical array
            if run["data"] and os.path.exists(run["data"]):
                d_size = format_bytes(os.path.getsize(run["data"]))
                ditem = QTreeWidgetItem(run_node, [f"🔢 Primary Data Array [{d_size}]"])
                ditem.setData(0, Qt.UserRole, {"type": "data", "path": run["data"], "run": run})

            # Add any additional companion arrays
            for addl in run.get("additional_data", []):
                if os.path.exists(addl):
                    a_base = os.path.basename(addl)
                    a_size = format_bytes(os.path.getsize(addl))
                    aitem = QTreeWidgetItem(run_node, [f"🔢 Companion: {a_base[:24]}... [{a_size}]"])
                    aitem.setData(0, Qt.UserRole, {"type": "data", "path": addl, "run": run})

        # Auto-expand matching runs if searching
        if search_query:
            self.tree.expandAll()
        else:
            for cat_node in category_nodes.values():
                cat_node.setExpanded(True)
                for i in range(cat_node.childCount()):
                    cat_node.child(i).setExpanded(False)

    def _on_search_changed(self, text: str):
        self._populate_tree()

    def _on_filter_changed(self, btn_id: int):
        if 0 <= btn_id < len(self.pills):
            self.active_filter = self.pills[btn_id][1]
        else:
            self.active_filter = "all"
        self._populate_tree()

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, col: int):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        self._selected_item_data = data
        self._update_inspector_card(data)

    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, col: int):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        itype = data.get("type")
        if itype == "plot":
            self.sig_view_plot.emit(data["path"])
        elif itype == "data":
            meta = read_npz_metadata(data["path"])
            self.sig_explore_data.emit(data["path"], meta)
        elif itype == "run":
            run = data["data"]
            if run["plots"]:
                first_plot = next(iter(run["plots"].values()))
                self.sig_view_plot.emit(first_plot)
            elif run["data"]:
                meta = read_npz_metadata(run["data"])
                self.sig_explore_data.emit(run["data"], meta)

    def _update_inspector_card(self, item_data: dict):
        """Populates the bottom selection card with parameter details."""
        itype = item_data.get("type")

        if itype == "plot":
            path = item_data["path"]
            base = os.path.basename(path)
            size = format_bytes(os.path.getsize(path)) if os.path.exists(path) else "0 B"
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path))) if os.path.exists(path) else ""
            meta = parse_filename_parameters(path)

            self.lbl_card_title.setText(base)
            self.lbl_card_badge.setText("PLOT FIGURE")
            self.lbl_card_badge.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background-color: #dbeafe; color: #1e40af;")
            self.lbl_card_badge.setVisible(True)
            self.lbl_card_stats.setText(f"Size: {size}  •  Modified: {mtime}")

            param_strs = [f"<b>{k}:</b> {v}" for k, v in meta.items()]
            if param_strs:
                self.lbl_card_params.setText("  |  ".join(param_strs))
                self.lbl_card_params.setVisible(True)
            else:
                self.lbl_card_params.setVisible(False)

            self.btn_view_plot.setEnabled(True)
            has_data = bool(item_data.get("run", {}).get("data"))
            self.btn_explore_data.setEnabled(has_data)
            self.btn_compare.setEnabled(True)
            self.btn_reveal.setEnabled(True)
            self.btn_delete.setEnabled(True)

        elif itype == "data":
            path = item_data["path"]
            base = os.path.basename(path)
            size = format_bytes(os.path.getsize(path)) if os.path.exists(path) else "0 B"
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path))) if os.path.exists(path) else ""
            meta = read_npz_metadata(path)

            self.lbl_card_title.setText(base)
            self.lbl_card_badge.setText("NUMERICAL DATASET")
            self.lbl_card_badge.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background-color: #fef3c7; color: #92400e;")
            self.lbl_card_badge.setVisible(True)
            self.lbl_card_stats.setText(f"Size: {size}  •  Modified: {mtime}")

            display_params = []
            if meta.get("is_bitgroomed"):
                display_params.append("<b>compression:</b> 1/8th IBZ (8-bit Groomed)")
            elif meta.get("is_ibz"):
                display_params.append("<b>compression:</b> 1/8th IBZ")

            for k in ["mu", "t", "t1", "K", "N", "num_omega", "eta", "fixed_jperp", "fixed_jk"]:
                if k in meta:
                    val = meta[k]
                    val_str = f"{val:.2f}" if isinstance(val, float) else str(val)
                    display_params.append(f"<b>{k}:</b> {val_str}")

            if display_params:
                self.lbl_card_params.setText("  |  ".join(display_params))
                self.lbl_card_params.setVisible(True)
            else:
                self.lbl_card_params.setVisible(False)

            self.btn_view_plot.setEnabled(bool(item_data.get("run", {}).get("plots")))
            self.btn_explore_data.setEnabled(True)
            self.btn_compare.setEnabled(False)
            self.btn_reveal.setEnabled(True)
            self.btn_delete.setEnabled(True)

        elif itype == "run":
            run = item_data["data"]
            size = format_bytes(run["total_size"])
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(run["mtime"]))

            self.lbl_card_title.setText(run["title"])
            self.lbl_card_badge.setText(run["study_type"].upper())
            self.lbl_card_badge.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background-color: #e0e7ff; color: #3730a3;")
            self.lbl_card_badge.setVisible(True)
            self.lbl_card_stats.setText(f"Total: {size}  •  Latest: {mtime}")

            param_strs = []
            for k, v in run.get("params", {}).items():
                if isinstance(v, list):
                    def _format_elem(x):
                        if isinstance(x, (float, np.floating)):
                            return f"{x:.2f}"
                        elif isinstance(x, (int, np.integer)):
                            return str(x)
                        try:
                            val_f = float(x)
                            return f"{val_f:.2f}"
                        except (ValueError, TypeError):
                            return str(x)
                    items_str = ", ".join(_format_elem(x) for x in v[:4])
                    val_str = f"[{items_str}...]" if len(v) > 4 else f"[{items_str}]"
                elif isinstance(v, (float, np.floating)):
                    val_str = f"{v:.2f}"
                else:
                    val_str = str(v)
                param_strs.append(f"<b>{k}:</b> {val_str}")

            if param_strs:
                self.lbl_card_params.setText("  |  ".join(param_strs))
                self.lbl_card_params.setVisible(True)
            else:
                self.lbl_card_params.setVisible(False)

            self.btn_view_plot.setEnabled(bool(run["plots"]))
            self.btn_explore_data.setEnabled(bool(run["data"]))
            self.btn_compare.setEnabled(bool(run["plots"]))
            self.btn_reveal.setEnabled(True)
            self.btn_delete.setEnabled(True)

    def _set_actions_enabled(self, enabled: bool):
        self.btn_view_plot.setEnabled(enabled)
        self.btn_explore_data.setEnabled(enabled)
        self.btn_compare.setEnabled(enabled)
        self.btn_reveal.setEnabled(enabled)
        self.btn_delete.setEnabled(enabled)

    def _on_action_view_plot(self):
        if not self._selected_item_data:
            return
        itype = self._selected_item_data.get("type")
        if itype == "plot":
            self.sig_view_plot.emit(self._selected_item_data["path"])
        elif itype == "run":
            plots = self._selected_item_data["data"]["plots"]
            if plots:
                first_plot = next(iter(plots.values()))
                self.sig_view_plot.emit(first_plot)
        elif itype == "data":
            run = self._selected_item_data.get("run", {})
            if run and run.get("plots"):
                first_plot = next(iter(run["plots"].values()))
                self.sig_view_plot.emit(first_plot)

    def _on_action_explore_data(self):
        if not self._selected_item_data:
            return
        itype = self._selected_item_data.get("type")
        if itype == "data":
            p = self._selected_item_data["path"]
            meta = read_npz_metadata(p)
            self.sig_explore_data.emit(p, meta)
        elif itype == "run":
            d = self._selected_item_data["data"]["data"]
            if d and os.path.exists(d):
                meta = read_npz_metadata(d)
                self.sig_explore_data.emit(d, meta)
        elif itype == "plot":
            run = self._selected_item_data.get("run", {})
            if run and run.get("data") and os.path.exists(run["data"]):
                meta = read_npz_metadata(run["data"])
                self.sig_explore_data.emit(run["data"], meta)

    def _on_action_compare(self):
        if not self._selected_item_data:
            return
        itype = self._selected_item_data.get("type")
        if itype == "plot":
            self.sig_compare.emit(self._selected_item_data["path"])
        elif itype == "run":
            plots = self._selected_item_data["data"]["plots"]
            if plots:
                first_plot = next(iter(plots.values()))
                self.sig_compare.emit(first_plot)

    def _on_action_reveal(self):
        if not self._selected_item_data:
            return
        path = None
        itype = self._selected_item_data.get("type")
        if itype in ("plot", "data"):
            path = self._selected_item_data.get("path")
        elif itype == "run":
            run = self._selected_item_data["data"]
            if run["plots"]:
                path = next(iter(run["plots"].values()))
            elif run["data"]:
                path = run["data"]

        if path and os.path.exists(path):
            norm_path = os.path.normpath(path)
            os.system(f'explorer /select,"{norm_path}"')

    def _on_action_delete(self):
        if not self._selected_item_data:
            return
        itype = self._selected_item_data.get("type")
        files_to_delete = []

        if itype == "run":
            run = self._selected_item_data["data"]
            files_to_delete.extend(list(run["plots"].values()))
            if run["data"]:
                files_to_delete.append(run["data"])
            files_to_delete.extend(run.get("additional_data", []))
            target_desc = f"all files in study '{run['title']}' ({len(files_to_delete)} files)"
        elif itype in ("plot", "data"):
            p = self._selected_item_data.get("path")
            if p:
                files_to_delete.append(p)
                target_desc = os.path.basename(p)

        if not files_to_delete:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to permanently delete {target_desc}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for f in files_to_delete:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except Exception as e:
                    QMessageBox.warning(self, "Deletion Failed", f"Could not delete {f}: {e}")
            self.refresh()
            self._selected_item_data = None
            self.lbl_card_title.setText("Select a study or dataset")
            self.lbl_card_badge.setVisible(False)
            self.lbl_card_stats.setText("Deleted successfully")
            self.lbl_card_params.setVisible(False)
            self._set_actions_enabled(False)

    def _open_results_folder(self):
        results_dir, _, _, _ = normalize_results_dir(self.out_dir)
        if os.path.isdir(results_dir):
            try:
                os.startfile(results_dir)
            except Exception as e:
                QMessageBox.warning(self, "Open Folder Error", str(e))

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        menu = QMenu(self)
        itype = data.get("type")

        if itype == "plot":
            menu.addAction("👁️ View Plot in Canvas", lambda: self.sig_view_plot.emit(data["path"]))
            menu.addAction("⚏ Send to Comparison Canvas", lambda: self.sig_compare.emit(data["path"]))
            if data.get("run", {}).get("data"):
                menu.addAction("🔬 Explore Numerical Data", lambda: self.sig_explore_data.emit(data["run"]["data"], read_npz_metadata(data["run"]["data"])))
        elif itype == "data":
            menu.addAction("🔬 Explore Numerical Data", lambda: self.sig_explore_data.emit(data["path"], read_npz_metadata(data["path"])))
        elif itype == "run":
            run = data["data"]
            if run["plots"]:
                p = next(iter(run["plots"].values()))
                menu.addAction("👁️ View Run Primary Plot", lambda: self.sig_view_plot.emit(p))
            if run["data"]:
                menu.addAction("🔬 Explore Run Numerical Data", lambda: self.sig_explore_data.emit(run["data"], read_npz_metadata(run["data"])))

        menu.addSeparator()
        menu.addAction("📂 Reveal in File Explorer", self._on_action_reveal)
        menu.addAction("🗑️ Delete", self._on_action_delete)

        menu.exec(self.tree.viewport().mapToGlobal(pos))
