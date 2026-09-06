"""Build razor-sharp Many-Body Studio application icons from Concept 3 (The Dyson Sigma).

Overhauls the vector geometry for high-DPI contrast and zero-blur downscaling:
  - Bolds the Sigma stroke from 4.5 to 6.5 for crisp 2px physical rendering on 16x16 / 20x20.
  - Removes murky radial glow filter that caused blurry smudging.
  - Adds native fractional DPI resolutions (20x20 for 125% Windows scaling, 24x24 for 150%).
  - Outputs vector SVG, per-resolution PNGs, master 512x512 PNG, and Windows ICO.
"""

import os
import sys
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QColor
from PySide6.QtCore import QByteArray, Qt, QRectF
from PySide6.QtSvg import QSvgRenderer
from PIL import Image

SVG_CONTENT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="grad-bg-3" x1="0" y1="0" x2="0" y2="64" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#0c213d"/>
      <stop offset="100%" stop-color="#050d1a"/>
    </linearGradient>
    <linearGradient id="grad-sig" x1="20" y1="16" x2="46" y2="48" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#7dd3fc"/>
      <stop offset="100%" stop-color="#0284c7"/>
    </linearGradient>
  </defs>

  <!-- Crisp rounded app tile background -->
  <rect x="3" y="3" width="58" height="58" rx="14" fill="url(#grad-bg-3)" stroke="#38bdf8" stroke-width="2.5"/>

  <!-- Bold, razor-sharp Sigma (Σ) backbone -->
  <path d="M 46,16 L 20,16 L 33,32 L 20,48 L 46,48" 
        stroke="url(#grad-sig)" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>

  <!-- High-contrast quantum interaction nodes -->
  <circle cx="20" cy="16" r="4.2" fill="#7dd3fc"/>
  <circle cx="46" cy="16" r="4.2" fill="#0284c7"/>
  <circle cx="33" cy="32" r="5.2" fill="#ffffff" stroke="#0284c7" stroke-width="1.8"/>
  <circle cx="20" cy="48" r="4.2" fill="#7dd3fc"/>
  <circle cx="46" cy="48" r="4.2" fill="#0284c7"/>
</svg>
"""

# Windows DPI Scale Matrix:
# 100% -> 16, 32
# 125% -> 20, 40 (Standard for 1080p laptops)
# 150% -> 24, 48
# 175% -> 28, 56
# 200% -> 32, 64
RENDER_SIZES = [16, 20, 24, 28, 32, 40, 48, 64, 128, 256, 512]
ICO_SIZES = [(16, 16), (20, 20), (24, 24), (28, 28), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]

def main():
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication(sys.argv)

    gui_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icons_dir = os.path.join(gui_root, "pyside6_studio", "resources", "icons")
    os.makedirs(icons_dir, exist_ok=True)

    svg_path = os.path.join(icons_dir, "app_icon.svg")
    master_png_path = os.path.join(icons_dir, "app_icon.png")
    ico_path = os.path.join(icons_dir, "app_icon.ico")

    # 1. Save Vector SVG
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(SVG_CONTENT)
    print(f"[OK] Wrote SVG: {svg_path}")

    # 2. Render each size directly from vector with native subpixel anti-aliasing
    renderer = QSvgRenderer(QByteArray(SVG_CONTENT.encode("utf-8")))

    for s in RENDER_SIZES:
        image = QImage(s, s, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        renderer.render(painter, QRectF(0, 0, s, s))
        painter.end()

        # Save individual size PNGs
        if s in [16, 20, 24, 32, 48, 64, 256]:
            size_png = os.path.join(icons_dir, f"app_icon_{s}.png")
            image.save(size_png, "PNG")

        if s == 512:
            image.save(master_png_path, "PNG")
            print(f"[OK] Rendered Master PNG: {master_png_path} ({s}x{s})")

    # 3. Generate multi-resolution Windows ICO containing all native sizes
    master_img = Image.open(master_png_path)
    master_img.save(ico_path, format="ICO", sizes=ICO_SIZES)
    print(f"[OK] Generated Windows ICO: {ico_path} with sizes {ICO_SIZES}")

if __name__ == "__main__":
    main()
