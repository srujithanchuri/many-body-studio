"""
analytical_modes package
------------------------
Modular mode handlers for LiveAnalyticalLabWidget:
  - BaseAnalyticalMode: Abstract base class for all analytical modes.
  - SpectralFunctionMode: Mode 0 - A(k, ω) and self-energy Σ(k, ω).
  - EnergySliceMode: Mode 1 - Constant energy contour A(k, ω_slice).
  - RpaSusceptibilityMode: Mode 2 - Static RPA magnetic susceptibility χ_RPA(q).
"""

from pyside6_studio.widgets.analytical_modes.base_mode import BaseAnalyticalMode
from pyside6_studio.widgets.analytical_modes.spectral_function_mode import SpectralFunctionMode
from pyside6_studio.widgets.analytical_modes.energy_slice_mode import EnergySliceMode
from pyside6_studio.widgets.analytical_modes.rpa_susceptibility_mode import RpaSusceptibilityMode

__all__ = [
    "BaseAnalyticalMode",
    "SpectralFunctionMode",
    "EnergySliceMode",
    "RpaSusceptibilityMode",
]
