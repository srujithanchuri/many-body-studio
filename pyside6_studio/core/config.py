"""Global configuration, paths, and resolution presets for Many-Body Studio Pro."""

import os
from dataclasses import dataclass

# Application Metadata
APP_NAME = "Many-Body Studio Pro"
APP_VERSION = "alpha-v3.5"
APP_RELEASE_TITLE = "Many-Body Studio Pro • Alpha v3.5"

# Base repository paths
STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI_REPO_ROOT = os.path.dirname(STUDIO_DIR)
DEFAULT_RESULTS_DIR = os.path.join(GUI_REPO_ROOT, "results")

# Locate physics repository root automatically via the installed package
try:
    import self_energy
    PHYSICS_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(self_energy.__file__)))
except Exception:
    PHYSICS_REPO_ROOT = r"C:\Users\sruji\Projects\masters_thesis"

# Physics results hierarchy
MANY_BODY_RESULTS = os.path.join(PHYSICS_REPO_ROOT, "many_body_results")
SPECTRAL_DIR = os.path.join(MANY_BODY_RESULTS, "spectral_results")
SPECTRAL_PLOTS_DIR = os.path.join(SPECTRAL_DIR, "plots")
SPECTRAL_DATA_DIR = os.path.join(SPECTRAL_DIR, "data")

SUSC_DIR = os.path.join(MANY_BODY_RESULTS, "susceptibility_results")
SUSC_PLOTS_DIR = os.path.join(SUSC_DIR, "plots")
SUSC_DATA_DIR = os.path.join(SUSC_DIR, "data")

# Resolution Presets
PRESETS = {
    "Fast Preview (N=64)": {
        "N": 64,
        "Nw": 2001,
        "w_max": 20.0,
        "eta": 0.08,
        "description": "Ultra-fast execution (~1-2s). Ideal for rapid testing and sanity checks."
    },
    "Standard (N=100)": {
        "N": 100,
        "Nw": 4801,
        "w_max": 40.0,
        "eta": 0.05,
        "description": "Thesis benchmark standard (~10-15s). Well-resolved spectral functions and Fermi surfaces."
    },
    "High-Res Production (N=256)": {
        "N": 256,
        "Nw": 8001,
        "w_max": 40.0,
        "eta": 0.03,
        "description": "Publication-grade resolution (~60-90s). Razor-sharp Fermi arcs and peak splitting."
    }
}

DEFAULT_HAMILTONIAN = {
    "t": 1.0,
    "t1": 0.0,
    "mu": 1.0,
    "K": 1.0,
    "JK": 6.0,
    "Jperp": 6.0
}
