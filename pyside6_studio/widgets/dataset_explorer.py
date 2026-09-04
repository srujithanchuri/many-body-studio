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

    mu_m = re.search(r"mu[_=]?([0-9]+(?:\.[0-9]+)?)", base)
    if mu_m:
        try: params["mu"] = float(mu_m.group(1))
        except ValueError: pass

    t_m = re.search(r"(?:^|[^0-9a-zA-Z])t[_=]?([0-9]+(?:\.[0-9]+)?)", base)
    if t_m:
        try: params["t"] = float(t_m.group(1))
        except ValueError: pass

    t1_m = re.search(r"t1[_=]?([0-9]+(?:\.[0-9]+)?)", base)
    if t1_m:
        try: params["t1"] = float(t1_m.group(1))
        except ValueError: pass

    k_m = re.search(r"(?:^|[^0-9a-zA-Z])K[_=]?([0-9]+(?:\.[0-9]+)?)", base)
    if k_m:
        try: params["K"] = float(k_m.group(1))
        except ValueError: pass

    n_m = re.search(r"N[_=]?(\d+)", base)
    if n_m:
        try: params["N"] = int(n_m.group(1))
        except ValueError: pass

    nw_m = re.search(r"(?:Nw|num_omega|w)[_=]?(\d+)", base)
    if nw_m:
        try: params["num_omega"] = int(nw_m.group(1))
        except ValueError: pass

    eta_m = re.search(r"eta[_=]?([0-9]+(?:\.[0-9]+)?)", base)
    if eta_m:
        try: params["eta"] = float(eta_m.group(1))
        except ValueError: pass

    jp_m = re.search(r"(?:J_perp|Jperp|fixed_J)[_=]?([0-9]+(?:\.[0-9]+)?)", base)
    if jp_m:
        try: params["fixed_jperp"] = float(jp_m.group(1))
        except ValueError: pass

    jk_m = re.search(r"(?:J_K|JK|fixed_JK)[_=]?([0-9]+(?:\.[0-9]+)?)", base)
    if jk_m:
        try: params["fixed_jk"] = float(jk_m.group(1))
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
            for k in ["mu", "t", "t1", "K", "N", "num_omega", "omega_max", "eta", "fixed_coupling", "sweep_mode"]:
                if k in files:
                    val = data[k]
                    if isinstance(val, np.ndarray) and val.size == 1:
                        meta[k] = val.item()
                    elif not isinstance(val, np.ndarray):
                        meta[k] = val

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


class DatasetExplorerWidget(QWidget):
    """Modern Research Workspace & Dataset Explorer dock widget."""

    sig_view_plot = Signal(str)
    sig_explore_data = Signal(str, dict)
    sig_compare = Signal(str)
    sig_open_cache_dialog = Signal()

    def __init__(self, out_dir: str = DEFAULT_RESULTS_DIR, parent=None):
        super().__init__(parent)
        self.out_dir = out_dir
        self.active_filter = "all"  # "all", "studies", "cache"
        self._runs_data = []
        self._selected_item_data = None

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
        self.btn_refresh.setToolTip("Refresh datasets and plots from disk")
        self.btn_refresh.setFixedWidth(32)
        self.btn_refresh.clicked.connect(self.refresh)
        top_bar.addWidget(self.btn_refresh)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("🔍 Filter runs, params (e.g. mu=1.0)...")
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.edit_search)

        self.btn_open_folder = QPushButton("📂")
        self.btn_open_folder.setToolTip("Open results folder in Windows Explorer")
        self.btn_open_folder.setFixedWidth(32)
        self.btn_open_folder.clicked.connect(self._open_results_folder)
        top_bar.addWidget(self.btn_open_folder)

        self.btn_cache_mgr = QPushButton("🧹")
        self.btn_cache_mgr.setToolTip("Open Cache Manager")
        self.btn_cache_mgr.setFixedWidth(32)
        self.btn_cache_mgr.clicked.connect(self.sig_open_cache_dialog.emit)
        top_bar.addWidget(self.btn_cache_mgr)

        main_layout.addLayout(top_bar)

        # 2. Segmented Category Filter Pills
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(4)
        self.btn_group_filter = QButtonGroup(self)

        self.btn_filter_all = QPushButton("All")
        self.btn_filter_studies = QPushButton("📈 Studies")
        self.btn_filter_cache = QPushButton("📦 Cache")

        for idx, btn in enumerate([self.btn_filter_all, self.btn_filter_studies, self.btn_filter_cache]):
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    padding: 3px 8px;
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

        self.btn_filter_all.setChecked(True)
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
        self.lbl_card_title = QLabel("Select a run or dataset")
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
        self.btn_view_plot.setToolTip("View publication figure in presentation canvas")
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
        """Updates inspector card and filter styling dynamically based on theme."""
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
        results_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(self.out_dir)

        # 1. Collect all files
        plots = [p for p in glob.glob(os.path.join(plots_dir, "*.*")) if p.lower().endswith((".png", ".pdf", ".svg"))]
        data_files = [d for d in glob.glob(os.path.join(data_dir, "*.npz"))]
        cache_files = [c for c in glob.glob(os.path.join(cache_dir, "*.npz"))]

        runs = {}

        # Group 1: Spectral Sweeps
        for p in plots:
            base = os.path.basename(p)
            if base.startswith(("sweep_DOS_", "sweep_FS_", "sweep_Path_")):
                suffix = re.sub(r"^sweep_(DOS|FS|Path)_", "", base)
                suffix = os.path.splitext(suffix)[0]
                run_key = f"spectral_sweep_{suffix}"
                if run_key not in runs:
                    runs[run_key] = {
                        "category": "Spectral Sweep",
                        "study_type": "Spectral Sweep",
                        "key": run_key,
                        "title": f"Spectral Sweep ({suffix})",
                        "plots": {},
                        "data": None,
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
                        "category": "Spectral Sweep",
                        "study_type": "Spectral Sweep",
                        "key": run_key,
                        "title": f"Spectral Sweep ({suffix})",
                        "plots": {},
                        "data": d,
                        "mtime": os.path.getmtime(d),
                        "total_size": os.path.getsize(d)
                    }

        # Group 2: Quasiparticle Spectral Function A(k, w)
        for p in plots:
            base = os.path.basename(p)
            if base.startswith(("both_", "spectral_only_", "self_energy_only_")):
                s_key = re.sub(r"^(both|spectral_only|self_energy_only)_", "", base)
                s_key = os.path.splitext(s_key)[0]
                run_key = f"spectral_func_{s_key}"
                if run_key not in runs:
                    runs[run_key] = {
                        "category": "Spectral Function",
                        "study_type": "Spectral Function",
                        "key": run_key,
                        "title": f"Spectral Function ({s_key})",
                        "plots": {},
                        "data": None,
                        "mtime": os.path.getmtime(p),
                        "total_size": 0
                    }
                runs[run_key]["plots"]["Composite Figure"] = p
                runs[run_key]["total_size"] += os.path.getsize(p)

        for d in data_files:
            base = os.path.basename(d)
            if base.startswith(("both_", "spectral_only_", "self_energy_only_")):
                s_key = re.sub(r"^(both|spectral_only|self_energy_only)_", "", base)
                s_key = re.sub(r"_eta_[0-9.]+", "", s_key).replace(".npz", "")
                run_key = f"spectral_func_{s_key}"
                if run_key in runs:
                    runs[run_key]["data"] = d
                    runs[run_key]["total_size"] += os.path.getsize(d)
                else:
                    runs[run_key] = {
                        "category": "Spectral Function",
                        "study_type": "Spectral Function",
                        "key": run_key,
                        "title": f"Spectral Function ({s_key})",
                        "plots": {},
                        "data": d,
                        "mtime": os.path.getmtime(d),
                        "total_size": os.path.getsize(d)
                    }

        # Group 3: Phase Diagrams
        for p in plots:
            base = os.path.basename(p)
            if base.startswith("phase_diagram_"):
                suffix = base.replace("phase_diagram_", "").replace(".png", "").replace(".pdf", "")
                run_key = f"phase_diagram_{suffix}"
                if run_key not in runs:
                    runs[run_key] = {
                        "category": "Phase Diagram",
                        "study_type": "Phase Diagram",
                        "key": run_key,
                        "title": f"Phase Diagram ({suffix})",
                        "plots": {"Phase Boundary": p},
                        "data": None,
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
                        "mtime": os.path.getmtime(d),
                        "total_size": os.path.getsize(d)
                    }

        # Group 4: Susceptibility
        for p in plots:
            base = os.path.basename(p)
            if "static" in base or "dynamic" in base:
                if "phase_diagram" not in base and not base.startswith("sweep_DOS"):
                    run_key = f"susc_{base}"
                    runs[run_key] = {
                        "category": "Susceptibility",
                        "study_type": "Susceptibility",
                        "key": run_key,
                        "title": f"Susceptibility: {base}",
                        "plots": {"Map": p},
                        "data": None,
                        "mtime": os.path.getmtime(p),
                        "total_size": os.path.getsize(p)
                    }

        for d in data_files:
            base = os.path.basename(d)
            if ("static" in base or "dynamic" in base) and not base.startswith("sweep_data"):
                matched = False
                for rk, rdata in list(runs.items()):
                    if rdata["category"] == "Susceptibility" and os.path.splitext(base)[0] in rk:
                        rdata["data"] = d
                        rdata["total_size"] += os.path.getsize(d)
                        matched = True
                        break
                if not matched:
                    run_key = f"susc_{base}"
                    runs[run_key] = {
                        "category": "Susceptibility",
                        "study_type": "Susceptibility",
                        "key": run_key,
                        "title": f"Susceptibility Array: {base}",
                        "plots": {},
                        "data": d,
                        "mtime": os.path.getmtime(d),
                        "total_size": os.path.getsize(d)
                    }

        # Catch-all for remaining unassigned plots or data
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
                    "mtime": os.path.getmtime(p),
                    "total_size": os.path.getsize(p)
                }

        self._runs_data = list(runs.values())
        self._cache_files = cache_files
        self._populate_tree()

    def _populate_tree(self):
        """Populates the QTreeWidget based on active category filter and search query."""
        search_query = self.edit_search.text().strip().lower()
        self.tree.clear()

        # 1. Observable Studies Section
        if self.active_filter in ("all", "studies"):
            grp_studies = QTreeWidgetItem(self.tree, ["📈 OBSERVABLE STUDIES & FIGURES"])
            grp_studies.setExpanded(True)
            font = grp_studies.font(0)
            font.setBold(True)
            grp_studies.setFont(0, font)

            category_nodes = {}

            # Sort runs by newest first
            sorted_runs = sorted(self._runs_data, key=lambda x: x["mtime"], reverse=True)

            for run in sorted_runs:
                # Filter by search query (normalize underscores and spaces)
                plot_bases = " ".join(os.path.basename(p) for p in run["plots"].values())
                data_base = os.path.basename(run["data"]) if run["data"] else ""
                search_target = f"{run['title']} {run['category']} {run['key']} {plot_bases} {data_base}".lower()
                norm_target = search_target.replace("_", " ")
                norm_query = search_query.replace("_", " ")
                if search_query and (search_query not in search_target and norm_query not in norm_target):
                    continue

                cat = run["category"]
                if cat not in category_nodes:
                    cnode = QTreeWidgetItem(grp_studies, [f"📂 {cat}"])
                    cnode.setExpanded(True)
                    category_nodes[cat] = cnode

                # Format human readable date
                t_str = time.strftime("%b %d, %H:%M", time.localtime(run["mtime"]))
                run_node = QTreeWidgetItem(category_nodes[cat], [f"📁 {run['title']} ({t_str})"])
                run_node.setData(0, Qt.UserRole, {"type": "run", "data": run})

                # Add child plot items
                for ptype, ppath in run["plots"].items():
                    p_size = format_bytes(os.path.getsize(ppath)) if os.path.exists(ppath) else ""
                    pitem = QTreeWidgetItem(run_node, [f"🖼️ {ptype} [{p_size}]"])
                    pitem.setData(0, Qt.UserRole, {"type": "plot", "path": ppath, "run": run})

                # Add child data array item
                if run["data"] and os.path.exists(run["data"]):
                    d_size = format_bytes(os.path.getsize(run["data"]))
                    ditem = QTreeWidgetItem(run_node, [f"🔢 Raw Numerical Array [{d_size}]"])
                    ditem.setData(0, Qt.UserRole, {"type": "data", "path": run["data"], "run": run})

        # 2. Cache Foundations Section
        if self.active_filter in ("all", "cache"):
            grp_cache = QTreeWidgetItem(self.tree, ["📦 COMPUTATIONAL CACHE FOUNDATIONS"])
            grp_cache.setExpanded(True)
            font = grp_cache.font(0)
            font.setBold(True)
            grp_cache.setFont(0, font)

            sorted_cache = sorted(self._cache_files, key=lambda x: os.path.getmtime(x), reverse=True)
            for cpath in sorted_cache:
                cname = os.path.basename(cpath)
                if search_query and search_query not in cname.lower():
                    continue

                if cname.startswith("sigma_base_full"):
                    ctype = "Base Σ (Full BZ)"
                elif cname.startswith("sigma_base_point"):
                    ctype = "Base Σ (Point k)"
                elif cname.startswith("chi0_static"):
                    ctype = "Static χ₀ Bubble"
                elif cname.startswith("chi0_dynamic"):
                    ctype = "Dynamic χ₀ Bubble"
                else:
                    ctype = "Foundation Array"

                csize = format_bytes(os.path.getsize(cpath)) if os.path.exists(cpath) else ""
                citem = QTreeWidgetItem(grp_cache, [f"⚡ {ctype}: {cname} [{csize}]"])
                citem.setData(0, Qt.UserRole, {"type": "cache", "path": cpath, "name": cname, "ctype": ctype})

    def _on_search_changed(self, text: str):
        self._populate_tree()

    def _on_filter_changed(self, btn_id: int):
        if btn_id == 0:
            self.active_filter = "all"
        elif btn_id == 1:
            self.active_filter = "studies"
        else:
            self.active_filter = "cache"
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
        elif itype in ("data", "cache"):
            meta = read_npz_metadata(data["path"])
            self.sig_explore_data.emit(data["path"], meta)
        elif itype == "run":
            # Auto open primary plot or data
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
            self.lbl_card_badge.setText("PUBLICATION PLOT")
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
            # Check if companion data exists
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
            self.lbl_card_badge.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background-color: #dcfce7; color: #166534;")
            self.lbl_card_badge.setVisible(True)
            self.lbl_card_stats.setText(f"Size: {size}  •  Modified: {mtime}")

            param_strs = []
            for k in ["mu", "t", "t1", "K", "N", "num_omega", "eta", "fixed_coupling"]:
                if k in meta:
                    param_strs.append(f"<b>{k}:</b> {meta[k]}")
            if "array_keys" in meta:
                param_strs.append(f"<b>Arrays:</b> {len(meta['array_keys'])}")

            if param_strs:
                self.lbl_card_params.setText("  |  ".join(param_strs))
                self.lbl_card_params.setVisible(True)
            else:
                self.lbl_card_params.setVisible(False)

            has_plots = bool(item_data.get("run", {}).get("plots"))
            self.btn_view_plot.setEnabled(has_plots)
            self.btn_explore_data.setEnabled(True)
            self.btn_compare.setEnabled(True)
            self.btn_reveal.setEnabled(True)
            self.btn_delete.setEnabled(True)

        elif itype == "cache":
            path = item_data["path"]
            base = item_data["name"]
            size = format_bytes(os.path.getsize(path)) if os.path.exists(path) else "0 B"
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path))) if os.path.exists(path) else ""
            meta = read_npz_metadata(path)

            self.lbl_card_title.setText(base)
            self.lbl_card_badge.setText(item_data["ctype"])
            self.lbl_card_badge.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background-color: #cffafe; color: #0e7490;")
            self.lbl_card_badge.setVisible(True)
            self.lbl_card_stats.setText(f"Size: {size}  •  Modified: {mtime}")

            param_strs = [f"<b>{k}:</b> {meta[k]}" for k in ["mu", "t", "t1", "K", "N", "num_omega", "eta"] if k in meta]
            if param_strs:
                self.lbl_card_params.setText("  |  ".join(param_strs))
                self.lbl_card_params.setVisible(True)
            else:
                self.lbl_card_params.setVisible(False)

            self.btn_view_plot.setEnabled(False)
            self.btn_explore_data.setEnabled(True)
            self.btn_compare.setEnabled(False)
            self.btn_reveal.setEnabled(True)
            self.btn_delete.setEnabled(True)

        elif itype == "run":
            run = item_data["data"]
            self.lbl_card_title.setText(run["title"])
            self.lbl_card_badge.setText(run["category"].upper())
            self.lbl_card_badge.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background-color: #f3e8ff; color: #7e22ce;")
            self.lbl_card_badge.setVisible(True)

            num_p = len(run["plots"])
            has_d = "1 dataset" if run["data"] else "No dataset"
            tot_size = format_bytes(run["total_size"])
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(run["mtime"]))
            self.lbl_card_stats.setText(f"{num_p} plot(s), {has_d} ({tot_size})  •  {mtime}")

            target_path = run["data"] or (next(iter(run["plots"].values())) if run["plots"] else None)
            meta = read_npz_metadata(target_path) if target_path else {}
            param_strs = [f"<b>{k}:</b> {meta[k]}" for k in ["mu", "t", "t1", "K", "N", "eta"] if k in meta]
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
            run = self._selected_item_data["data"]
            if run["plots"]:
                p = next(iter(run["plots"].values()))
                self.sig_view_plot.emit(p)
        elif itype == "data":
            run = self._selected_item_data.get("run", {})
            if run and run.get("plots"):
                p = next(iter(run["plots"].values()))
                self.sig_view_plot.emit(p)

    def _on_action_explore_data(self):
        if not self._selected_item_data:
            return
        itype = self._selected_item_data.get("type")
        d_path = None
        if itype in ("data", "cache"):
            d_path = self._selected_item_data["path"]
        elif itype == "run":
            d_path = self._selected_item_data["data"].get("data")
        elif itype == "plot":
            d_path = self._selected_item_data.get("run", {}).get("data")

        if d_path and os.path.exists(d_path):
            meta = read_npz_metadata(d_path)
            self.sig_explore_data.emit(d_path, meta)
        else:
            QMessageBox.information(self, "No Numerical Data", "This run does not contain a saved .npz dataset.")

    def _on_action_compare(self):
        if not self._selected_item_data:
            return
        itype = self._selected_item_data.get("type")
        if itype == "plot":
            self.sig_compare.emit(self._selected_item_data["path"])
        elif itype == "run":
            run = self._selected_item_data["data"]
            if run["plots"]:
                p = next(iter(run["plots"].values()))
                self.sig_compare.emit(p)

    def _on_action_reveal(self):
        if not self._selected_item_data:
            return
        target = None
        itype = self._selected_item_data.get("type")
        if itype in ("plot", "data", "cache"):
            target = self._selected_item_data["path"]
        elif itype == "run":
            run = self._selected_item_data["data"]
            if run["plots"]:
                target = next(iter(run["plots"].values()))
            elif run["data"]:
                target = run["data"]

        if target and os.path.exists(target):
            try:
                os.system(f'explorer /select,"{os.path.normpath(target)}"')
            except Exception as e:
                QMessageBox.warning(self, "Explorer Error", str(e))

    def _on_action_delete(self):
        if not self._selected_item_data:
            return
        itype = self._selected_item_data.get("type")
        files_to_delete = []

        if itype in ("plot", "data", "cache"):
            files_to_delete.append(self._selected_item_data["path"])
            prompt = f"Are you sure you want to permanently delete:\n{os.path.basename(self._selected_item_data['path'])}?"
        elif itype == "run":
            run = self._selected_item_data["data"]
            files_to_delete.extend(run["plots"].values())
            if run["data"]:
                files_to_delete.append(run["data"])
            prompt = f"Are you sure you want to permanently delete all {len(files_to_delete)} files in run:\n'{run['title']}'?"
        else:
            return

        res = QMessageBox.question(self, "Confirm Delete", prompt, QMessageBox.Yes | QMessageBox.No)
        if res == QMessageBox.Yes:
            for f in files_to_delete:
                if os.path.isfile(f):
                    try:
                        os.remove(f)
                    except Exception as e:
                        QMessageBox.warning(self, "Delete Error", f"Failed to delete {os.path.basename(f)}: {e}")
            self.refresh()
            self.lbl_card_title.setText("Select a run or dataset")
            self.lbl_card_badge.setVisible(False)
            self.lbl_card_stats.setText("No selection")
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
        elif itype in ("data", "cache"):
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
