"""Vector figure export dialog used by the interactive data canvas."""

import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFrame, QFileDialog, QMessageBox, QTextEdit, QCheckBox
)

from matplotlib.figure import Figure

class VectorExportDialog(QDialog):
    """Dialog for configuring vector export with LaTeX snippets."""

    def __init__(self, fig: Figure, parent=None):
        super().__init__(parent)
        self.fig = fig
        self.setWindowTitle("Export Vector Figure (LaTeX Ready)")
        self.resize(560, 420)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lbl_desc = QLabel(
            "Export native vector graphics directly from raw numerical simulation data.\n"
            "Scales infinitely in thesis LaTeX documents without bitmap rasterization artifacts."
        )
        lbl_desc.setStyleSheet("color: #475569; font-size: 11px;")
        lay.addWidget(lbl_desc)

        # Settings Grid
        grid_frame = QFrame()
        grid_frame.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px;")
        g_lay = QVBoxLayout(grid_frame)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Export Format:"))
        self.cb_fmt = QComboBox()
        self.cb_fmt.addItems(["Vector PDF (*.pdf)", "Scalable Vector Graphics (*.svg)", "Encapsulated PostScript (*.eps)", "Ultra High-Res PNG (600 DPI) (*.png)"])
        r1.addWidget(self.cb_fmt, 1)
        g_lay.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("DPI Resolution:"))
        self.cb_dpi = QComboBox()
        self.cb_dpi.addItems(["300 DPI (Standard Print / Vector)", "600 DPI (Archival Ultra-Res)", "1200 DPI (Maximum Quality)"])
        r2.addWidget(self.cb_dpi, 1)
        g_lay.addLayout(r2)

        r3 = QHBoxLayout()
        self.chk_tight = QCheckBox("Tight Bounding Box (crop white margins)")
        self.chk_tight.setChecked(True)
        r3.addWidget(self.chk_tight)
        g_lay.addLayout(r3)

        lay.addWidget(grid_frame)

        # LaTeX Snippet Preview
        lay.addWidget(QLabel("LaTeX Code Snippet for Thesis:"))
        self.edit_latex = QTextEdit()
        self.edit_latex.setReadOnly(True)
        self.edit_latex.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; background: #ffffff; color: #0f172a;")
        self.edit_latex.setText(
            r"\begin{figure}[htbp]" + "\n"
            r"  \centering" + "\n"
            r"  \includegraphics[width=\columnwidth]{figures/quasiparticle_spectrum.pdf}" + "\n"
            r"  \caption{Quasiparticle spectral function $A(\mathbf{k}, \omega)$ and self-energy computed via Many-Body Studio Pro.}" + "\n"
            r"  \label{fig:spectral_quasiparticle}" + "\n"
            r"\end{figure}"
        )
        lay.addWidget(self.edit_latex)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.btn_copy_latex = QPushButton("📋 Copy LaTeX Snippet")
        self.btn_copy_latex.clicked.connect(self._copy_latex)
        btn_row.addWidget(self.btn_copy_latex)

        btn_row.addStretch()

        self.btn_save = QPushButton("💾 Save Vector Figure...")
        self.btn_save.setStyleSheet("background-color: #2563eb; color: #ffffff; font-weight: 600; padding: 6px 14px; border-radius: 4px;")
        self.btn_save.clicked.connect(self._save_file)
        btn_row.addWidget(self.btn_save)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        lay.addLayout(btn_row)

    def _copy_latex(self):
        from PySide6.QtGui import QClipboard, QGuiApplication
        cb = QGuiApplication.clipboard()
        cb.setText(self.edit_latex.toPlainText())
        QMessageBox.information(self, "Copied", "LaTeX figure snippet copied to clipboard!")

    def _save_file(self):
        idx = self.cb_fmt.currentIndex()
        if idx == 0: ext, f_filter = "pdf", "PDF Vector Document (*.pdf)"
        elif idx == 1: ext, f_filter = "svg", "Scalable Vector Graphics (*.svg)"
        elif idx == 2: ext, f_filter = "eps", "Encapsulated PostScript (*.eps)"
        else: ext, f_filter = "png", "High-Resolution Image (*.png)"

        out_path, _ = QFileDialog.getSaveFileName(self, "Save Vector Figure", f"figure.{ext}", f_filter)
        if not out_path:
            return

        dpi = 300 if self.cb_dpi.currentIndex() == 0 else (600 if self.cb_dpi.currentIndex() == 1 else 1200)
        bbox = "tight" if self.chk_tight.isChecked() else None

        try:
            self.fig.savefig(out_path, dpi=dpi, bbox_inches=bbox)
            rel_name = os.path.basename(out_path)
            self.edit_latex.setText(
                r"\begin{figure}[htbp]" + "\n"
                r"  \centering" + "\n"
                rf"  \includegraphics[width=\columnwidth]{{figures/{rel_name}}}" + "\n"
                r"  \caption{Many-body calculation results.}" + "\n"
                rf"  \label{{fig:{os.path.splitext(rel_name)[0]}}}" + "\n"
                r"\end{figure}"
            )
            QMessageBox.information(self, "Figure Exported", f"Successfully exported vector figure to:\n{out_path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save figure: {e}")
