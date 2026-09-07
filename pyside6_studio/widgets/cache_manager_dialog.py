"""Cache manager dialog for reusable computational foundation arrays."""

import os
import time

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QHeaderView,
    QAbstractItemView, QPushButton, QMessageBox, QTableWidgetItem,
)

from pyside6_studio.core.cache_manager import (
    normalize_results_dir,
    get_cache_stats,
    purge_cache,
)


class CacheManagerDialog(QDialog):
    """Inspects and manages reusable computational foundation arrays in results/cache/."""
    def __init__(self, parent=None, out_dir=None):
        super().__init__(parent)
        self.setWindowTitle("Smart Cache Manager • Many-Body Studio Beta v1")
        self.setMinimumSize(700, 420)
        self.out_dir = out_dir
        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lbl_title = QLabel("📦 Reusable Computational Foundations")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        lay.addWidget(lbl_title)

        lbl_desc = QLabel(
            "The Smart Caching Engine stores reusable foundations (Base Σ at J_K=1.0 and bare bubbles χ₀)\n"
            "in the 'results/cache/' directory. Changing (t, t1, mu, K, J_perp, N, Nw, wmax, eta) invalidates these foundations.\n"
            "Scaling J_K utilizes the analytical J_K² scaling law without recomputing convolutions."
        )
        lbl_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        lbl_desc.setWordWrap(True)
        lay.addWidget(lbl_desc)

        self.lbl_stats = QLabel("Total Cache: 0 files (0 KB)")
        self.lbl_stats.setStyleSheet("font-weight: 600; color: #0891b2;")
        lay.addWidget(self.lbl_stats)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Foundation File", "Size", "Type", "Last Modified"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        lay.addWidget(self.table)

        h_btns = QHBoxLayout()
        self.btn_clear = QPushButton("🗑️ Clear Cache")
        self.btn_clear.setStyleSheet("background-color: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; font-weight: 600; padding: 4px 10px;")
        self.btn_clear.clicked.connect(self._clear_cache)
        h_btns.addWidget(self.btn_clear)

        self.btn_open_folder = QPushButton("📂 Open Cache Folder")
        self.btn_open_folder.setStyleSheet("padding: 4px 10px;")
        self.btn_open_folder.clicked.connect(self._open_folder)
        h_btns.addWidget(self.btn_open_folder)

        h_btns.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("padding: 4px 14px;")
        btn_close.clicked.connect(self.accept)
        h_btns.addWidget(btn_close)

        lay.addLayout(h_btns)

    def refresh_data(self):
        stats = get_cache_stats(self.out_dir)
        self.lbl_stats.setText(f"Total Cache: {stats['total_files']} files ({stats['formatted_size']}) in {stats['cache_dir']}")

        self.table.setRowCount(0)
        for row, itm in enumerate(stats["items"]):
            self.table.insertRow(row)
            name = itm["name"]
            if name.startswith("sigma_base_full"):
                ftype = "Base Σ (Full BZ)"
            elif name.startswith("sigma_base_point"):
                ftype = "Point Σ (Single k)"
            elif name.startswith("chi0_static"):
                ftype = "Static χ₀ Bubble"
            elif name.startswith("chi0_dynamic"):
                ftype = "Dynamic χ₀ Bubble"
            else:
                ftype = "Cache Array"

            mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(itm["mtime"]))

            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(itm["size_str"]))
            self.table.setItem(row, 2, QTableWidgetItem(ftype))
            self.table.setItem(row, 3, QTableWidgetItem(mtime_str))

    def _clear_cache(self):
        res = QMessageBox.question(
            self, "Clear Cache",
            "Are you sure you want to purge all reusable foundation arrays from results/cache/?\n\n"
            "This will not delete finished plots or observable datasets.",
            QMessageBox.Yes | QMessageBox.No
        )
        if res == QMessageBox.Yes:
            cnt = purge_cache(self.out_dir)
            QMessageBox.information(self, "Cache Cleared", f"Removed {cnt} cached foundation files.")
            self.refresh_data()
            if self.parent() and hasattr(self.parent(), "_update_cache_badge"):
                self.parent()._update_cache_badge()

    def _open_folder(self):
        results_dir, plots_dir, data_dir, cache_dir = normalize_results_dir(self.out_dir)
        if os.path.isdir(cache_dir):
            try:
                os.startfile(cache_dir)
            except Exception as e:
                QMessageBox.warning(self, "Open Folder Error", str(e))
