"""Presentation theme helpers for the main Many-Body Studio window.

The controller retains stable method names; this module owns only dynamic
styling/palette propagation and contains no simulation or queue logic.
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor

from pyside6_studio.theme import (
    LIGHT_THEME_QSS, DARK_THEME_QSS, create_light_palette, create_dark_palette,
)


def update_bottom_dock_theme(owner, is_dark: bool):
            if not hasattr(owner, "dock_bottom") or not hasattr(owner, "bottom_tabs"):
                return
            if is_dark:
                owner.dock_bottom.setStyleSheet("""
                    QDockWidget {
                        font-weight: 700;
                        font-size: 11px;
                    }
                    QDockWidget::title {
                        background: #1e293b;
                        padding: 4px 8px;
                        border-bottom: 1px solid #334155;
                        font-weight: 700;
                        font-size: 11px;
                        color: #94a3b8;
                    }
                """)
                owner.bottom_tabs.setStyleSheet("""
                    QTabWidget::pane {
                        border: 1px solid #334155;
                        border-radius: 6px;
                        background: #1e293b;
                        margin-top: -1px;
                    }
                    QTabBar::tab {
                        background: #0f172a;
                        color: #94a3b8;
                        border: 1px solid #334155;
                        border-bottom: 1px solid #334155;
                        border-top-left-radius: 6px;
                        border-top-right-radius: 6px;
                        padding: 6px 16px;
                        font-weight: 600;
                        font-size: 11px;
                        margin-right: 3px;
                    }
                    QTabBar::tab:selected {
                        background: #1e293b;
                        color: #60a5fa;
                        font-weight: 700;
                        border-color: #3b82f6;
                        border-bottom: 2px solid #2563eb;
                    }
                    QTabBar::tab:hover:!selected {
                        background: #1e293b;
                        color: #f8fafc;
                    }
                """)
                btn_style = """
                    QPushButton {
                        padding: 4px 11px;
                        background: #334155;
                        border: 1px solid #475569;
                        border-radius: 5px;
                        font-size: 11px;
                        font-weight: 600;
                        color: #f8fafc;
                    }
                    QPushButton:hover {
                        background: #475569;
                        border-color: #64748b;
                        color: #ffffff;
                    }
                """
                owner.lbl_queue_badge.setStyleSheet("""
                    QLabel {
                        background: #0f172a;
                        border: 1px solid #334155;
                        border-radius: 10px;
                        padding: 2px 10px;
                        font-size: 11px;
                        font-weight: 600;
                        color: #94a3b8;
                    }
                """)
                owner.table_queue.setStyleSheet("""
                    QTableWidget {
                        border: 1px solid #334155;
                        border-radius: 5px;
                        background-color: #1e293b;
                        alternate-background-color: #0f172a;
                        gridline-color: #334155;
                        selection-background-color: #1e3a8a;
                        selection-color: #f8fafc;
                        font-size: 11px;
                        color: #f8fafc;
                    }
                    QHeaderView::section {
                        background-color: #0f172a;
                        color: #94a3b8;
                        font-weight: 700;
                        font-size: 11px;
                        padding: 5px 8px;
                        border: none;
                        border-bottom: 2px solid #334155;
                        border-right: 1px solid #334155;
                    }
                """)
                owner.lbl_console_engine_status.setStyleSheet("""
                    QLabel {
                        background: #064e3b;
                        border: 1px solid #059669;
                        border-radius: 10px;
                        padding: 2px 10px;
                        font-size: 10px;
                        font-weight: 700;
                        color: #6ee7b7;
                    }
                """)
            else:
                owner.dock_bottom.setStyleSheet("""
                    QDockWidget {
                        font-weight: 700;
                        font-size: 11px;
                    }
                    QDockWidget::title {
                        background: #f1f5f9;
                        padding: 4px 8px;
                        border-bottom: 1px solid #cbd5e1;
                        font-weight: 700;
                        font-size: 11px;
                        color: #1e293b;
                    }
                """)
                owner.bottom_tabs.setStyleSheet("""
                    QTabWidget::pane {
                        border: 1px solid #cbd5e1;
                        border-radius: 6px;
                        background: #ffffff;
                        margin-top: -1px;
                    }
                    QTabBar::tab {
                        background: #f1f5f9;
                        color: #475569;
                        border: 1px solid #cbd5e1;
                        border-bottom: 1px solid #cbd5e1;
                        border-top-left-radius: 6px;
                        border-top-right-radius: 6px;
                        padding: 6px 16px;
                        font-weight: 600;
                        font-size: 11px;
                        margin-right: 3px;
                    }
                    QTabBar::tab:selected {
                        background: #ffffff;
                        color: #1d4ed8;
                        font-weight: 700;
                        border-color: #3b82f6;
                        border-bottom: 2px solid #2563eb;
                    }
                    QTabBar::tab:hover:!selected {
                        background: #e2e8f0;
                        color: #0f172a;
                    }
                """)
                btn_style = """
                    QPushButton {
                        padding: 4px 11px;
                        background: #ffffff;
                        border: 1px solid #cbd5e1;
                        border-radius: 5px;
                        font-size: 11px;
                        font-weight: 600;
                        color: #334155;
                    }
                    QPushButton:hover {
                        background: #f1f5f9;
                        border-color: #94a3b8;
                        color: #0f172a;
                    }
                """
                owner.lbl_queue_badge.setStyleSheet("""
                    QLabel {
                        background: #f8fafc;
                        border: 1px solid #cbd5e1;
                        border-radius: 10px;
                        padding: 2px 10px;
                        font-size: 11px;
                        font-weight: 600;
                        color: #475569;
                    }
                """)
                owner.table_queue.setStyleSheet("""
                    QTableWidget {
                        border: 1px solid #e2e8f0;
                        border-radius: 5px;
                        background-color: #ffffff;
                        alternate-background-color: #f8fafc;
                        gridline-color: #e2e8f0;
                        selection-background-color: #eff6ff;
                        selection-color: #1e293b;
                        font-size: 11px;
                        color: #0f172a;
                    }
                    QHeaderView::section {
                        background-color: #f1f5f9;
                        color: #334155;
                        font-weight: 700;
                        font-size: 11px;
                        padding: 5px 8px;
                        border: none;
                        border-bottom: 2px solid #cbd5e1;
                        border-right: 1px solid #e2e8f0;
                    }
                """)
                owner.lbl_console_engine_status.setStyleSheet("""
                    QLabel {
                        background: #ecfdf5;
                        border: 1px solid #a7f3d0;
                        border-radius: 10px;
                        padding: 2px 10px;
                        font-size: 10px;
                        font-weight: 700;
                        color: #065f46;
                    }
                """)

            for btn in [
                getattr(owner, "btn_pause", None),
                getattr(owner, "btn_add_to_queue", None),
                getattr(owner, "btn_clear", None),
                getattr(owner, "btn_clear_pending", None),
                getattr(owner, "btn_autoscroll", None),
                getattr(owner, "btn_copy_console", None),
                getattr(owner, "btn_clear_console", None),
            ]:
                if btn:
                    btn.setStyleSheet(btn_style)


def update_statusbar_theme(owner, is_dark: bool):
            sb = owner.statusBar()
            if is_dark:
                sb.setStyleSheet("QStatusBar { background: #0f172a; border-top: 1px solid #334155; padding: 2px 4px; }")
                if hasattr(owner, "lbl_status"):
                    owner.lbl_status.setStyleSheet("font-size: 11px; font-weight: 500; color: #94a3b8;")
                if hasattr(owner, "lbl_coords"):
                    owner.lbl_coords.setStyleSheet("""
                        QLabel {
                            background: #1e293b;
                            border: 1px solid #334155;
                            border-radius: 4px;
                            padding: 2px 8px;
                            font-family: 'Consolas', 'Cascadia Code', monospace;
                            font-size: 11px;
                            font-weight: 600;
                            color: #f8fafc;
                        }
                    """)
                if hasattr(owner, "lbl_hw_status"):
                    owner.lbl_hw_status.setStyleSheet("""
                        QLabel {
                            background: #064e3b;
                            border: 1px solid #059669;
                            border-radius: 4px;
                            padding: 2px 8px;
                            font-size: 11px;
                            font-weight: 600;
                            color: #6ee7b7;
                        }
                    """)
            else:
                sb.setStyleSheet("QStatusBar { background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 2px 4px; }")
                if hasattr(owner, "lbl_status"):
                    owner.lbl_status.setStyleSheet("font-size: 11px; font-weight: 500; color: #334155;")
                if hasattr(owner, "lbl_coords"):
                    owner.lbl_coords.setStyleSheet("""
                        QLabel {
                            background: #ffffff;
                            border: 1px solid #cbd5e1;
                            border-radius: 4px;
                            padding: 2px 8px;
                            font-family: 'Consolas', 'Cascadia Code', monospace;
                            font-size: 11px;
                            font-weight: 600;
                            color: #1e293b;
                        }
                    """)
                if hasattr(owner, "lbl_hw_status"):
                    owner.lbl_hw_status.setStyleSheet("""
                        QLabel {
                            background: #ecfdf5;
                            border: 1px solid #a7f3d0;
                            border-radius: 4px;
                            padding: 2px 8px;
                            font-size: 11px;
                            font-weight: 600;
                            color: #047857;
                        }
                    """)


def toggle_main_window_theme(owner):
            owner.is_dark = not owner.is_dark
            theme_qss = DARK_THEME_QSS if owner.is_dark else LIGHT_THEME_QSS
            theme_pal = create_dark_palette() if owner.is_dark else create_light_palette()
            owner.setStyleSheet(theme_qss)
            app_inst = QApplication.instance()
            if app_inst:
                app_inst.setPalette(theme_pal)
                app_inst.setStyleSheet(theme_qss)
            owner.canvas_left.set_theme(owner.is_dark)
            owner.canvas_right.set_theme(owner.is_dark)
            if hasattr(owner, "data_canvas"):
                owner.data_canvas.set_theme(owner.is_dark)
            if hasattr(owner, "explorer"):
                owner.explorer.set_theme(owner.is_dark)
            if hasattr(owner, "gallery"):
                owner.gallery.set_theme(owner.is_dark)
            if hasattr(owner, "interactive_plots"):
                owner.interactive_plots.set_theme(owner.is_dark)
            elif hasattr(owner, "live_lab"):
                owner.live_lab.set_theme(owner.is_dark)
            if hasattr(owner, "interactive_mode_nav"):
                owner.interactive_mode_nav.set_theme(owner.is_dark)
            owner._update_bottom_dock_theme(owner.is_dark)
            owner._update_statusbar_theme(owner.is_dark)
            study_col = QColor("#60a5fa") if owner.is_dark else QColor("#2563eb")
            snap_col = QColor("#94a3b8") if owner.is_dark else QColor("#475569")
            for r in range(owner.table_queue.rowCount()):
                it_s = owner.table_queue.item(r, 1)
                if it_s: it_s.setForeground(study_col)
                it_p = owner.table_queue.item(r, 2)
                if it_p: it_p.setForeground(snap_col)


