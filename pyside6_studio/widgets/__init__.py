"""
pyside6_studio.widgets
----------------------
Reusable UI viewports and workbenches:
- InteractivePlotCanvas: High-DPI QGraphicsView raster/vector canvas.
- PlotGalleryWidget: Left thumbnail card and compact list visual gallery browser.
- DatasetExplorerWidget: Left dock dataset tree scanner with metadata inspection cards.
- InteractiveDataCanvas: Dynamic multi-curve dataset slice plotter.
- InteractivePlotsWidget: 60 FPS real-time J_K coupler and interactive plot modes.
"""

from pyside6_studio.canvas import InteractivePlotCanvas
from pyside6_studio.widgets.gallery_browser import PlotGalleryWidget, parse_plot_metadata
from pyside6_studio.widgets.dataset_explorer import DatasetExplorerWidget
from pyside6_studio.widgets.data_plotter import InteractiveDataCanvas
from pyside6_studio.widgets.interactive_plots import InteractivePlotsWidget
from pyside6_studio.widgets.interactive_mode_nav import InteractiveModeNavWidget

__all__ = [
    "InteractivePlotCanvas",
    "PlotGalleryWidget",
    "parse_plot_metadata",
    "DatasetExplorerWidget",
    "InteractiveDataCanvas",
    "InteractivePlotsWidget",
    "InteractiveModeNavWidget",
]
