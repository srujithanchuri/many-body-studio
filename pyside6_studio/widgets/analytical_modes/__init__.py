"""
analytical_modes package
------------------------
Modular mode handlers for LiveAnalyticalLabWidget:
  - BaseAnalyticalMode: Abstract base class for all analytical modes.
  - EnergySliceMode: Mode 0 - Constant energy contour A(k, ω_slice) & integrated DOS.
  - SpectralFunctionMode: Mode 1 - A(k, ω) and self-energy Σ(k, ω) at probed momentum.
  - BandDispersionMode: Mode 2 - 2D Energy-Momentum band dispersion A(k_path, ω).
  - StaticSusceptibilityMode: Mode 3 - 2D Static RPA magnetic susceptibility χ_RPA(q).
  - DynamicSusceptibilityMode: Mode 4 - 2D Dynamic RPA spin excitation spectrum -Im χ_RPA(q, ω).
"""

from pyside6_studio.widgets.analytical_modes.base_mode import BaseAnalyticalMode
from pyside6_studio.widgets.analytical_modes.spectral_function_mode import SpectralFunctionMode
from pyside6_studio.widgets.analytical_modes.energy_slice_mode import EnergySliceMode
from pyside6_studio.widgets.analytical_modes.band_dispersion_mode import BandDispersionMode
from pyside6_studio.widgets.analytical_modes.rpa_susceptibility_mode import StaticSusceptibilityMode, RpaSusceptibilityMode
from pyside6_studio.widgets.analytical_modes.dynamic_susceptibility_mode import DynamicSusceptibilityMode

__all__ = [
    "BaseAnalyticalMode",
    "SpectralFunctionMode",
    "EnergySliceMode",
    "BandDispersionMode",
    "StaticSusceptibilityMode",
    "DynamicSusceptibilityMode",
    "RpaSusceptibilityMode",
]
