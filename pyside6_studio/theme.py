"""Theme stylesheets and styling definitions for Many-Body Studio Pro.
Modern Windows 11 Fluent / Slate aesthetics supporting Light and Dark modes.
Ensures crisp, transparent labels, perfectly masked card titles, and matching canvas backgrounds.
"""

LIGHT_THEME_QSS = """
QMainWindow, QWidget#CentralWidget, QSplitter {
    background-color: #f8fafc;
}

QWidget {
    color: #0f172a;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 13px;
}

/* Central interactive canvas viewport */
QGraphicsView {
    background-color: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
}

/* Explicit transparent backgrounds for text elements to prevent mismatched box highlights */
QLabel {
    background-color: transparent;
    background: transparent;
    color: #1e293b;
}

QCheckBox, QRadioButton {
    background-color: transparent;
    background: transparent;
    color: #1e293b;
    spacing: 6px;
}

QScrollArea {
    background-color: transparent;
    background: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
    background: transparent;
}

QToolBar {
    background: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    padding: 6px 10px;
    spacing: 8px;
}

QDockWidget {
    font-weight: 600;
    titlebar-close-icon: url(none);
    titlebar-normal-icon: url(none);
}
QDockWidget::title {
    background: #e2e8f0;
    padding: 7px 12px;
    border-radius: 5px;
    font-weight: 600;
    color: #334155;
}

QTabWidget::pane {
    border: 1px solid #e2e8f0;
    background: #ffffff;
    border-radius: 6px;
}
QTabBar::tab {
    background: #f1f5f9;
    color: #475569;
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #2563eb;
    font-weight: 600;
    border: 1px solid #e2e8f0;
    border-bottom: 1px solid #ffffff;
}
QTabBar::tab:hover:!selected {
    background: #e2e8f0;
    color: #0f172a;
}

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: 600;
    color: #0f172a;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 12px;
    background-color: #ffffff;
    color: #2563eb;
    font-weight: 700;
}
QGroupBox QLabel, QGroupBox QCheckBox, QGroupBox QRadioButton {
    background-color: transparent;
    background: transparent;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    padding: 5px 8px;
    color: #0f172a;
    selection-background-color: #2563eb;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1.5px solid #2563eb;
}

QPushButton, QToolButton {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 14px;
    color: #1e293b;
    font-weight: 500;
}
QPushButton:hover, QToolButton:hover {
    background: #e2e8f0;
    color: #0f172a;
}
QPushButton:pressed, QToolButton:pressed {
    background: #cbd5e1;
}

QPushButton#PrimaryBtn, QToolButton#PrimaryBtn {
    background: #2563eb;
    color: #ffffff;
    border: none;
    font-weight: 600;
}
QPushButton#PrimaryBtn:hover, QToolButton#PrimaryBtn:hover {
    background: #1d4ed8;
}

QPushButton#BtnCancel:enabled {
    background-color: #ef4444;
    color: #ffffff;
    border: 1px solid #dc2626;
    border-radius: 6px;
    font-weight: 700;
}
QPushButton#BtnCancel:enabled:hover {
    background-color: #dc2626;
}
QPushButton#BtnCancel:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    font-weight: 500;
}

QPushButton#ModeSimActive {
    background: #2563eb;
    color: #ffffff;
    font-weight: 700;
    border-radius: 6px;
    border: none;
    padding: 6px 14px;
}
QPushButton#ModePubActive {
    background: #7c3aed;
    color: #ffffff;
    font-weight: 700;
    border-radius: 6px;
    border: none;
    padding: 6px 14px;
}
QPushButton#ModeInactive {
    background: #f1f5f9;
    color: #64748b;
    font-weight: 600;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton#ModeInactive:hover {
    background: #e2e8f0;
    color: #0f172a;
}

QHeaderView::section {
    background: #f8fafc;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
    font-weight: 600;
    color: #475569;
}
QTableWidget, QTreeWidget, QTableView {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    gridline-color: #f1f5f9;
    color: #0f172a;
}
QTableWidget::item:selected, QTreeWidget::item:selected {
    background: #eff6ff;
    color: #1d4ed8;
}

QProgressBar {
    background: #e2e8f0;
    border-radius: 4px;
    text-align: center;
    height: 10px;
}
QProgressBar::chunk {
    background: #2563eb;
    border-radius: 4px;
}

QStatusBar {
    background: #ffffff;
    border-top: 1px solid #e2e8f0;
    color: #475569;
}
"""

DARK_THEME_QSS = """
QMainWindow, QWidget#CentralWidget, QSplitter {
    background-color: #0f172a;
}

QWidget {
    color: #f8fafc;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 13px;
}

/* Central interactive canvas viewport */
QGraphicsView {
    background-color: #0b1120;
    border: 1px solid #334155;
    border-radius: 6px;
}

/* Explicit transparent backgrounds for text elements to prevent mismatched box highlights */
QLabel {
    background-color: transparent;
    background: transparent;
    color: #f1f5f9;
}

QCheckBox, QRadioButton {
    background-color: transparent;
    background: transparent;
    color: #f1f5f9;
    spacing: 6px;
}

QScrollArea {
    background-color: transparent;
    background: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
    background: transparent;
}

QToolBar {
    background: #1e293b;
    border-bottom: 1px solid #334155;
    padding: 6px 10px;
    spacing: 8px;
}

QDockWidget {
    font-weight: 600;
}
QDockWidget::title {
    background: #1e293b;
    padding: 7px 12px;
    border-radius: 5px;
    font-weight: 600;
    color: #94a3b8;
}

QTabWidget::pane {
    border: 1px solid #334155;
    background: #1e293b;
    border-radius: 6px;
}
QTabBar::tab {
    background: #0f172a;
    color: #94a3b8;
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background: #1e293b;
    color: #60a5fa;
    font-weight: 600;
    border: 1px solid #334155;
    border-bottom: 1px solid #1e293b;
}
QTabBar::tab:hover:!selected {
    background: #1e293b;
    color: #f8fafc;
}

QGroupBox {
    background-color: #1e293b;
    border: 1px solid #475569;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: 600;
    color: #f1f5f9;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 12px;
    background-color: #1e293b;
    color: #60a5fa;
    font-weight: 700;
}
QGroupBox QLabel, QGroupBox QCheckBox, QGroupBox QRadioButton {
    background-color: transparent;
    background: transparent;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #0f172a;
    border: 1px solid #475569;
    border-radius: 5px;
    padding: 5px 8px;
    color: #f8fafc;
    selection-background-color: #2563eb;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1.5px solid #60a5fa;
}

QPushButton, QToolButton {
    background: #334155;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 6px 14px;
    color: #f8fafc;
    font-weight: 500;
}
QPushButton:hover, QToolButton:hover {
    background: #475569;
}
QPushButton:pressed, QToolButton:pressed {
    background: #1e293b;
}

QPushButton#PrimaryBtn, QToolButton#PrimaryBtn {
    background: #2563eb;
    color: #ffffff;
    border: none;
    font-weight: 600;
}
QPushButton#PrimaryBtn:hover, QToolButton#PrimaryBtn:hover {
    background: #3b82f6;
}

QPushButton#BtnCancel:enabled {
    background-color: #ef4444;
    color: #ffffff;
    border: 1px solid #dc2626;
    border-radius: 6px;
    font-weight: 700;
}
QPushButton#BtnCancel:enabled:hover {
    background-color: #dc2626;
}
QPushButton#BtnCancel:disabled {
    background-color: #1e293b;
    color: #64748b;
    border: 1px solid #334155;
    border-radius: 6px;
    font-weight: 500;
}

QPushButton#ModeSimActive {
    background: #2563eb;
    color: #ffffff;
    font-weight: 700;
    border-radius: 6px;
    border: none;
    padding: 6px 14px;
}
QPushButton#ModePubActive {
    background: #8b5cf6;
    color: #ffffff;
    font-weight: 700;
    border-radius: 6px;
    border: none;
    padding: 6px 14px;
}
QPushButton#ModeInactive {
    background: #1e293b;
    color: #94a3b8;
    font-weight: 600;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton#ModeInactive:hover {
    background: #334155;
    color: #f8fafc;
}

QHeaderView::section {
    background: #0f172a;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #334155;
    font-weight: 600;
    color: #94a3b8;
}
QTableWidget, QTreeWidget, QTableView {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    gridline-color: #334155;
    color: #f8fafc;
}
QTableWidget::item:selected, QTreeWidget::item:selected {
    background: #1e3a8a;
    color: #93c5fd;
}

QProgressBar {
    background: #334155;
    border-radius: 4px;
    text-align: center;
    height: 10px;
}
QProgressBar::chunk {
    background: #3b82f6;
    border-radius: 4px;
}

QStatusBar {
    background: #1e293b;
    border-top: 1px solid #334155;
    color: #94a3b8;
}
"""
