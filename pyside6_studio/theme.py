"""Theme stylesheets and styling definitions for Many-Body Studio Pro.
Modern Windows 11 Fluent / Slate aesthetics supporting Light and Dark modes.
Ensures crisp, transparent labels, perfectly masked card titles, and matching canvas backgrounds.
"""

import os

ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "icons").replace("\\", "/")

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

QCheckBox {
    background-color: transparent;
    background: transparent;
    color: #1e293b;
    spacing: 8px;
    font-size: 12px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1.5px solid #94a3b8;
    border-radius: 4px;
    background-color: #ffffff;
}
QCheckBox::indicator:hover {
    border-color: #2563eb;
    background-color: #f8fafc;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border: 1.5px solid #2563eb;
    image: url("@ICONS_DIR@/checkbox_checked_light.png");
}
QCheckBox::indicator:checked:hover {
    background-color: #1d4ed8;
    border-color: #1d4ed8;
}

QRadioButton {
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

QMainWindow::separator {
    width: 2px;
    height: 2px;
    background: #e2e8f0;
}
QMainWindow::separator:hover {
    background: #3b82f6;
}

QSplitter::handle {
    background: #e2e8f0;
}
QSplitter::handle:hover {
    background: #3b82f6;
}

QDockWidget {
    font-weight: 600;
    titlebar-close-icon: url(none);
    titlebar-normal-icon: url(none);
}
QDockWidget::title {
    background: #e2e8f0;
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 11px;
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
    padding: 6px 14px;
    margin-right: 2px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    font-weight: 500;
    font-size: 12px;
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
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-top: 4px;
    padding: 22px 8px 8px 8px;
    font-weight: 600;
    color: #0f172a;
}
QGroupBox::title {
    subcontrol-origin: padding;
    subcontrol-position: top left;
    padding-top: 4px;
    padding-left: 2px;
    background-color: transparent;
    background: transparent;
    color: #2563eb;
    font-weight: 700;
    font-size: 11px;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    background-color: transparent;
    color: #0f172a;
    padding: 6px 20px 6px 10px;
    border-radius: 4px;
    font-size: 12px;
}
QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QDialog, QMessageBox {
    background-color: #ffffff;
    color: #0f172a;
}
QMessageBox QLabel {
    color: #0f172a;
    background: transparent;
}
QMessageBox QPushButton {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 5px 16px;
    min-width: 60px;
    color: #0f172a;
    font-weight: 500;
}
QMessageBox QPushButton:hover {
    background: #e2e8f0;
}

QToolTip {
    background-color: #0f172a;
    color: #ffffff;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 4px 8px;
}
QGroupBox QLabel, QGroupBox QCheckBox, QGroupBox QRadioButton {
    background-color: transparent;
    background: transparent;
}

QLineEdit {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    padding: 5px 8px;
    color: #0f172a;
    selection-background-color: #2563eb;
}
QLineEdit:focus {
    border: 1.5px solid #2563eb;
}

QComboBox {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    padding: 5px 24px 5px 8px;
    color: #0f172a;
    selection-background-color: #2563eb;
}
QComboBox:focus {
    border: 1.5px solid #2563eb;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left: none;
}
QComboBox::down-arrow {
    image: url("@ICONS_DIR@/combo_down_light.png");
    width: 10px;
    height: 10px;
    margin-right: 6px;
}
QComboBox#StudyDropdown {
    font-weight: 700;
    color: #1d4ed8;
    background: #f0f7ff;
    border: 1.5px solid #93c5fd;
    border-radius: 6px;
    padding: 6px 26px 6px 10px;
    font-size: 12px;
}
QComboBox#StudyDropdown:hover {
    border-color: #2563eb;
    background: #ffffff;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #0f172a;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}
QComboBox QAbstractItemView::item {
    min-height: 24px;
    padding: 4px 8px;
    border-radius: 4px;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #eff6ff;
    color: #1d4ed8;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QSpinBox, QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    padding: 4px 22px 4px 8px;
    color: #0f172a;
    selection-background-color: #2563eb;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid #2563eb;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #cbd5e1;
    border-bottom: 1px solid #cbd5e1;
    border-top-right-radius: 4px;
    background: #f8fafc;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background: #e2e8f0;
}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed {
    background: #cbd5e1;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url("@ICONS_DIR@/spin_up_light.png");
    width: 8px;
    height: 8px;
}
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {
    image: url("@ICONS_DIR@/spin_up_hover.png");
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid #cbd5e1;
    border-bottom-right-radius: 4px;
    background: #f8fafc;
}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: #e2e8f0;
}
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background: #cbd5e1;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url("@ICONS_DIR@/spin_down_light.png");
    width: 8px;
    height: 8px;
}
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {
    image: url("@ICONS_DIR@/spin_down_hover.png");
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

/* Modern Sleek Scrollbars */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px 0 2px 0;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}
QScrollBar::handle:vertical:pressed {
    background: #64748b;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    width: 0px;
    background: none;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0 2px 0 2px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #cbd5e1;
    min-width: 24px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #94a3b8;
}
QScrollBar::handle:horizontal:pressed {
    background: #64748b;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0px;
    width: 0px;
    background: none;
    border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
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

QCheckBox {
    background-color: transparent;
    background: transparent;
    color: #f1f5f9;
    spacing: 8px;
    font-size: 12px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1.5px solid #64748b;
    border-radius: 4px;
    background-color: #1e293b;
}
QCheckBox::indicator:hover {
    border-color: #60a5fa;
    background-color: #334155;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border: 1.5px solid #2563eb;
    image: url("@ICONS_DIR@/checkbox_checked_light.png");
}
QCheckBox::indicator:checked:hover {
    background-color: #3b82f6;
    border: 1.5px solid #3b82f6;
}

QRadioButton {
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

QMainWindow::separator {
    width: 2px;
    height: 2px;
    background: #334155;
}
QMainWindow::separator:hover {
    background: #60a5fa;
}

QSplitter::handle {
    background: #334155;
}
QSplitter::handle:hover {
    background: #60a5fa;
}

QDockWidget {
    font-weight: 600;
}
QDockWidget::title {
    background: #1e293b;
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 11px;
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
    padding: 6px 14px;
    margin-right: 2px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    font-weight: 500;
    font-size: 12px;
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
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 4px;
    padding: 22px 8px 8px 8px;
    font-weight: 600;
    color: #f1f5f9;
}
QGroupBox::title {
    subcontrol-origin: padding;
    subcontrol-position: top left;
    padding-top: 4px;
    padding-left: 2px;
    background-color: transparent;
    background: transparent;
    color: #60a5fa;
    font-weight: 700;
    font-size: 11px;
}

QMenu {
    background-color: #1e293b;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    background-color: transparent;
    color: #f8fafc;
    padding: 6px 20px 6px 10px;
    border-radius: 4px;
    font-size: 12px;
}
QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QDialog, QMessageBox {
    background-color: #1e293b;
    color: #f8fafc;
}
QMessageBox QLabel {
    color: #f8fafc;
    background: transparent;
}
QMessageBox QPushButton {
    background: #334155;
    border: 1px solid #475569;
    border-radius: 4px;
    padding: 5px 16px;
    min-width: 60px;
    color: #f8fafc;
    font-weight: 500;
}
QMessageBox QPushButton:hover {
    background: #475569;
}

QToolTip {
    background-color: #0f172a;
    color: #ffffff;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 4px 8px;
}
QGroupBox QLabel, QGroupBox QCheckBox, QGroupBox QRadioButton {
    background-color: transparent;
    background: transparent;
}

QLineEdit {
    background: #0f172a;
    border: 1px solid #475569;
    border-radius: 5px;
    padding: 5px 8px;
    color: #f8fafc;
    selection-background-color: #2563eb;
}
QLineEdit:focus {
    border: 1.5px solid #60a5fa;
}

QComboBox {
    background: #0f172a;
    border: 1px solid #475569;
    border-radius: 5px;
    padding: 5px 24px 5px 8px;
    color: #f8fafc;
    selection-background-color: #2563eb;
}
QComboBox:focus {
    border: 1.5px solid #60a5fa;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left: none;
}
QComboBox::down-arrow {
    image: url("@ICONS_DIR@/combo_down_dark.png");
    width: 10px;
    height: 10px;
    margin-right: 6px;
}
QComboBox#StudyDropdown {
    font-weight: 700;
    color: #60a5fa;
    background: #172554;
    border: 1.5px solid #2563eb;
    border-radius: 6px;
    padding: 6px 26px 6px 10px;
    font-size: 12px;
}
QComboBox#StudyDropdown:hover {
    border-color: #60a5fa;
    background: #1e293b;
}
QComboBox QAbstractItemView {
    background-color: #1e293b;
    color: #f8fafc;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}
QComboBox QAbstractItemView::item {
    min-height: 24px;
    padding: 4px 8px;
    border-radius: 4px;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #334155;
    color: #93c5fd;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QSpinBox, QDoubleSpinBox {
    background: #0f172a;
    border: 1px solid #475569;
    border-radius: 5px;
    padding: 4px 22px 4px 8px;
    color: #f8fafc;
    selection-background-color: #2563eb;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid #60a5fa;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #475569;
    border-bottom: 1px solid #475569;
    border-top-right-radius: 4px;
    background: #1e293b;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background: #334155;
}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed {
    background: #0f172a;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url("@ICONS_DIR@/spin_up_dark.png");
    width: 8px;
    height: 8px;
}
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {
    image: url("@ICONS_DIR@/spin_up_hover.png");
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid #475569;
    border-bottom-right-radius: 4px;
    background: #1e293b;
}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: #334155;
}
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background: #0f172a;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url("@ICONS_DIR@/spin_down_dark.png");
    width: 8px;
    height: 8px;
}
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {
    image: url("@ICONS_DIR@/spin_down_hover.png");
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

/* Modern Sleek Scrollbars */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px 0 2px 0;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #475569;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #64748b;
}
QScrollBar::handle:vertical:pressed {
    background: #94a3b8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    width: 0px;
    background: none;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0 2px 0 2px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #475569;
    min-width: 24px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #64748b;
}
QScrollBar::handle:horizontal:pressed {
    background: #94a3b8;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0px;
    width: 0px;
    background: none;
    border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}
"""

LIGHT_THEME_QSS = LIGHT_THEME_QSS.replace("@ICONS_DIR@", ICONS_DIR)
DARK_THEME_QSS = DARK_THEME_QSS.replace("@ICONS_DIR@", ICONS_DIR)

from PySide6.QtGui import QPalette, QColor

def create_light_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#f8fafc"))
    pal.setColor(QPalette.WindowText, QColor("#0f172a"))
    pal.setColor(QPalette.Base, QColor("#ffffff"))
    pal.setColor(QPalette.AlternateBase, QColor("#f1f5f9"))
    pal.setColor(QPalette.ToolTipBase, QColor("#0f172a"))
    pal.setColor(QPalette.ToolTipText, QColor("#ffffff"))
    pal.setColor(QPalette.Text, QColor("#0f172a"))
    pal.setColor(QPalette.Button, QColor("#f1f5f9"))
    pal.setColor(QPalette.ButtonText, QColor("#0f172a"))
    pal.setColor(QPalette.Highlight, QColor("#2563eb"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    return pal

def create_dark_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#0f172a"))
    pal.setColor(QPalette.WindowText, QColor("#f8fafc"))
    pal.setColor(QPalette.Base, QColor("#1e293b"))
    pal.setColor(QPalette.AlternateBase, QColor("#0f172a"))
    pal.setColor(QPalette.ToolTipBase, QColor("#0f172a"))
    pal.setColor(QPalette.ToolTipText, QColor("#ffffff"))
    pal.setColor(QPalette.Text, QColor("#f8fafc"))
    pal.setColor(QPalette.Button, QColor("#334155"))
    pal.setColor(QPalette.ButtonText, QColor("#f8fafc"))
    pal.setColor(QPalette.Highlight, QColor("#2563eb"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    return pal
