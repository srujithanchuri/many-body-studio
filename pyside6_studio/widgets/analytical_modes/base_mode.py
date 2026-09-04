"""
base_mode.py
-------------
Defines the abstract base class BaseAnalyticalMode for analytical lab modes.
Each mode encapsulates:
  1. Its own physics rendering logic (matplotlib plotting).
  2. Mode-specific contextual UI controls (e.g. momentum selector, energy slice slider).
  3. Interactive canvas handlers (scroll zoom, drag pan, click-to-probe).
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyside6_studio.widgets.live_analytical_lab import LiveAnalyticalLabWidget


class BaseAnalyticalMode(ABC):
    """Abstract base class for Live Analytical Lab modes."""

    mode_id: str = "base"
    display_name: str = "Base Mode"
    required_cache_type: str = "sigma"  # "sigma" or "chi0"

    def __init__(self, lab: "LiveAnalyticalLabWidget"):
        self.lab = lab

    @property
    def fig(self):
        return self.lab.fig

    @property
    def canvas(self):
        return self.lab.canvas

    @abstractmethod
    def setup_ui(self):
        """Configures contextual toolbar widgets (visibility, labels) for this mode."""
        pass

    @abstractmethod
    def render(self):
        """Performs analytical physics calculations and renders onto self.fig."""
        pass

    def fit_view(self):
        """Resets custom zoom/pan viewports to default auto-fit view."""
        pass

    def on_scroll(self, event) -> bool:
        """Handles mouse wheel scroll event on the canvas. Return True if handled."""
        return False

    def on_press(self, event) -> bool:
        """Handles mouse button press event on the canvas. Return True if handled."""
        return False

    def on_motion(self, event) -> bool:
        """Handles mouse drag motion event on the canvas. Return True if handled."""
        return False

    def on_release(self, event) -> bool:
        """Handles mouse button release event on the canvas. Return True if handled."""
        return False
