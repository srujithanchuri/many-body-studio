"""Automated E2E Test Suite for Many-Body Studio Pro.

Configures headless offscreen environment and test path resolutions.
"""

import os
import sys

# Guarantee headless offscreen mode for all Qt tests
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Configure module resolution paths
_TESTS_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)
_STUDIO_DIR = os.path.join(_PROJECT_ROOT, "pyside6_studio")

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _STUDIO_DIR not in sys.path:
    sys.path.insert(0, _STUDIO_DIR)
