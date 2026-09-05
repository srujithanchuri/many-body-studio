"""
pyside6_studio.widgets
----------------------
Reusable UI viewports and workbenches:
- InteractivePlotCanvas: High-DPI QGraphicsView raster/vector canvas.
- PlotGalleryWidget: Left thumbnail card and compact list visual gallery browser.
- DatasetExplorerWidget: Left dock dataset tree scanner with metadata inspection cards.
- InteractiveDataCanvas: Dynamic multi-curve dataset slice plotter.
- InteractivePlotsWidget / LiveAnalyticalLabWidget: 60 FPS real-time J_K coupler and analytical modes.
"""

from pyside6_studio.canvas import InteractivePlotCanvas
from pyside6_studio.widgets.gallery_browser import PlotGalleryWidget, parse_plot_metadata
from pyside6_studio.widgets.dataset_explorer import DatasetExplorerWidget
from pyside6_studio.widgets.data_plotter import InteractiveDataCanvas
from pyside6_studio.widgets.live_analytical_lab import (
    LiveAnalyticalLabWidget,
    InteractivePlotsWidget,
)

__all__ = [
    "InteractivePlotCanvas",
    "PlotGalleryWidget",
    "parse_plot_metadata",
    "DatasetExplorerWidget",
    "InteractiveDataCanvas",
    "LiveAnalyticalLabWidget",
    "InteractivePlotsWidget",
]
