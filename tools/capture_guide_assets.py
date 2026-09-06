import os
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

sys.stdout.reconfigure(encoding='utf-8')

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPen, QBrush, QRegion

from pyside6_studio.main_window import UnifiedWorkbenchWindow
from pyside6_studio.widgets.compute_cache_dialog import ComputeCacheDialog

def render_high_res(widget, rect=None, scale=2):
    """Renders widget to a crisp high-res 2x Retina pixmap."""
    w = rect.width() if rect else widget.width()
    h = rect.height() if rect else widget.height()
    pix = QPixmap(int(w * scale), int(h * scale))
    pix.fill(Qt.transparent)
    pix.setDevicePixelRatio(scale)
    
    if rect:
        widget.render(pix, QPoint(0, 0), QRegion(rect))
    else:
        widget.render(pix, QPoint(0, 0))
    return pix

def draw_badge(p: QPainter, x: int, y: int, number_str: str, bg_color: str = "#2563eb") -> None:
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    radius = 11
    p.setBrush(QBrush(QColor(bg_color)))
    p.setPen(QPen(QColor("#ffffff"), 1.8))
    p.drawEllipse(QPoint(x, y), radius, radius)
    p.setPen(QColor("#ffffff"))
    font = QFont("Arial", 10, QFont.Bold)
    p.setFont(font)
    rect = QRect(x - radius, y - radius, radius * 2, radius * 2)
    p.drawText(rect, Qt.AlignCenter, str(number_str))

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = UnifiedWorkbenchWindow()
    win.resize(1440, 960)
    win.show()
    for _ in range(20):
        app.processEvents()
        time.sleep(0.02)

    assets_dir = os.path.join(str(project_root), "docs", "assets")
    os.makedirs(assets_dir, exist_ok=True)

    # -------------------------------------------------------------
    # 1. Capture Interactive Plots Header INCLUDING VIEWPORT LINE
    # -------------------------------------------------------------
    win.set_canvas_mode(1)
    for _ in range(10):
        app.processEvents()
        time.sleep(0.01)

    cc = win.central_container
    ip = win.interactive_plots
    
    h_frame_bottom = ip.header_frame.mapTo(cc, QPoint(0, ip.header_frame.height())).y() + 6
    w_crop = min(1100, cc.width())
    crop_rect = QRect(0, 0, w_crop, h_frame_bottom)

    pix_ip = render_high_res(cc, crop_rect, scale=2)

    p = QPainter(pix_ip)
    # Badge 1: On Viewport button "[ ⚡ Interactive Plots ]"
    pos_vp_tab = win.btn_canvas_lab.mapTo(cc, QPoint(win.btn_canvas_lab.width() - 4, 0))
    draw_badge(p, pos_vp_tab.x(), pos_vp_tab.y(), "1", "#2563eb")

    # Badge 2: Mode combobox
    pos_mode = ip.cb_experiment.mapTo(cc, QPoint(ip.cb_experiment.width() - 4, 0))
    draw_badge(p, pos_mode.x(), pos_mode.y(), "2", "#2563eb")

    # Badge 3: Cache combobox
    pos_cache = ip.cb_cache_file.mapTo(cc, QPoint(ip.cb_cache_file.width() - 4, 0))
    draw_badge(p, pos_cache.x(), pos_cache.y(), "3", "#0891b2")

    # Badge 4: Compute Cache button
    pos_btn = ip.btn_compute_cache.mapTo(cc, QPoint(ip.btn_compute_cache.width() - 2, 0))
    draw_badge(p, pos_btn.x(), pos_btn.y(), "4", "#0891b2")

    # Badge 5: J_K Slider
    pos_jk = ip.slider_jk.mapTo(cc, QPoint(ip.slider_jk.width() - 4, 0))
    draw_badge(p, pos_jk.x(), pos_jk.y(), "5", "#2563eb")
    p.end()

    p1 = os.path.join(assets_dir, "doc_interactive_header.png")
    pix_ip.save(p1, "PNG")
    print(f"Captured high-res: {p1}")

    # -------------------------------------------------------------
    # 2. Capture Compute Cache Dialog (High-Res)
    # -------------------------------------------------------------
    dlg = ComputeCacheDialog(parent=win)
    dlg.resize(460, 340)
    dlg.show()
    for _ in range(10):
        app.processEvents()
        time.sleep(0.01)

    pix_dlg = render_high_res(dlg, scale=2)
    p = QPainter(pix_dlg)
    pos_cat = dlg.cb_category.mapTo(dlg, QPoint(dlg.cb_category.width() - 6, -2))
    draw_badge(p, pos_cat.x(), pos_cat.y(), "1", "#0891b2")

    pos_mu = dlg.spin_mu.mapTo(dlg, QPoint(dlg.spin_mu.width() - 6, -2))
    draw_badge(p, pos_mu.x(), pos_mu.y(), "2", "#2563eb")

    pos_run = dlg.btn_run.mapTo(dlg, QPoint(dlg.btn_run.width() - 4, -2))
    draw_badge(p, pos_run.x(), pos_run.y(), "3", "#0891b2")
    p.end()

    p2 = os.path.join(assets_dir, "doc_compute_cache_dialog.png")
    pix_dlg.save(p2, "PNG")
    dlg.close()
    print(f"Captured high-res: {p2}")

    # -------------------------------------------------------------
    # 3. Capture Right Panel Inspector (High-Res)
    # -------------------------------------------------------------
    win.set_canvas_mode(0)
    win.dock_inspector.setMinimumWidth(340)
    win.dock_inspector.setMaximumWidth(360)
    for _ in range(10):
        app.processEvents()
        time.sleep(0.01)

    pix_insp = render_high_res(win.dock_inspector, scale=2)
    p = QPainter(pix_insp)
    pos_study = win.cb_active_study.mapTo(win.dock_inspector, QPoint(win.cb_active_study.width() - 6, -2))
    draw_badge(p, pos_study.x(), pos_study.y(), "1", "#2563eb")

    pos_cbadge = win.lbl_cache_badge.mapTo(win.dock_inspector, QPoint(win.lbl_cache_badge.width() - 10, -2))
    draw_badge(p, pos_cbadge.x(), pos_cbadge.y(), "2", "#0891b2")

    pos_preset = win.cb_preset.mapTo(win.dock_inspector, QPoint(win.cb_preset.width() - 6, -2))
    draw_badge(p, pos_preset.x(), pos_preset.y(), "3", "#2563eb")
    p.end()

    p3 = os.path.join(assets_dir, "doc_right_panel_inspector.png")
    pix_insp.save(p3, "PNG")
    print(f"Captured high-res: {p3}")

    # -------------------------------------------------------------
    # 4. Capture Left Gallery Modes (High-Res, No Cutoff, No Empty Space)
    # -------------------------------------------------------------
    g = win.gallery
    col_w = 260
    g.setFixedWidth(col_w)
    
    # 1 full card + tags height: exactly 310px
    crop_h = 315

    g.btn_view_cards.click()
    for _ in range(8):
        app.processEvents()
    pix_cards = render_high_res(g, QRect(0, 0, col_w, crop_h), scale=2)

    g.btn_view_list.click()
    for _ in range(8):
        app.processEvents()
    pix_list = render_high_res(g, QRect(0, 0, col_w, crop_h), scale=2)

    pad = 12
    gap = 16
    header_bar_h = 30
    total_w = col_w * 2 + gap + (pad * 2)
    total_h = crop_h + header_bar_h + (pad * 2)

    scale = 2
    pix_final = QPixmap(int(total_w * scale), int(total_h * scale))
    pix_final.fill(Qt.transparent)
    pix_final.setDevicePixelRatio(scale)

    p = QPainter(pix_final)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)

    # Frame card
    p.setPen(QPen(QColor("#e2e8f0"), 1.5))
    p.setBrush(QBrush(QColor("#f8fafc")))
    p.drawRoundedRect(1, 1, total_w - 2, total_h - 2, 8, 8)

    # Headers
    font_title = QFont("Arial", 10, QFont.Bold)
    p.setFont(font_title)
    p.setPen(QColor("#0f172a"))
    p.drawText(pad + 4, pad + 18, "🖼️ Thumbnail Cards Mode")
    p.drawText(pad + col_w + gap + 4, pad + 18, "📋 Compact List Mode")

    # Draw columns
    x1 = pad
    y1 = pad + header_bar_h
    x2 = pad + col_w + gap
    y2 = y1

    p.drawPixmap(x1, y1, pix_cards)
    p.drawPixmap(x2, y2, pix_list)

    # Borders around columns
    p.setPen(QPen(QColor("#cbd5e1"), 1.2))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(x1, y1, col_w, crop_h, 6, 6)
    p.drawRoundedRect(x2, y2, col_w, crop_h, 6, 6)

    # Callout Badges
    pos_toggle = g.btn_view_cards.mapTo(g, QPoint(g.btn_view_cards.width() - 2, -2))
    draw_badge(p, x1 + pos_toggle.x(), y1 + pos_toggle.y(), "1", "#2563eb")

    pos_search = g.edit_search.mapTo(g, QPoint(g.edit_search.width() - 10, -2))
    draw_badge(p, x1 + pos_search.x(), y1 + pos_search.y(), "2", "#0891b2")

    p.end()

    p4 = os.path.join(assets_dir, "doc_left_gallery_modes.png")
    pix_final.save(p4, "PNG")
    print(f"Captured high-res: {p4}")

    # -------------------------------------------------------------
    # 5. Capture Central Viewport & Toolbar (High-Res)
    # -------------------------------------------------------------
    win.set_canvas_mode(0)
    for _ in range(8):
        app.processEvents()
    
    pix_viewport = render_high_res(win.central_container, scale=2)
    p = QPainter(pix_viewport)
    pos_vp = win.btn_canvas_figure.mapTo(win.central_container, QPoint(win.btn_canvas_figure.width() - 4, 0))
    draw_badge(p, pos_vp.x(), pos_vp.y(), "1", "#2563eb")

    cw = win.central_container.width()
    ch = win.central_container.height()
    draw_badge(p, int(cw * 0.5), int(ch * 0.5), "2", "#2563eb")
    p.end()

    p5 = os.path.join(assets_dir, "doc_plot_viewer.png")
    pix_viewport.save(p5, "PNG")
    print(f"Captured high-res: {p5}")

    win.close()
    print("\nAll assets generated at 2x Retina resolution!")

if __name__ == "__main__":
    main()
