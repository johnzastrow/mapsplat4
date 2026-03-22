"""
Pytest configuration for MapSplat tests.

Installs a mock qgis package into sys.modules so that style_converter.py
can be imported and tested outside of a live QGIS environment.
All QGIS classes become simple MagicMock objects; tests that exercise
pure-Python logic (no actual renderer calls) work correctly.
"""

import sys
from unittest.mock import MagicMock


def _install_qgis_mocks():
    """Insert stub modules for qgis.core and qgis.gui before any test imports."""
    qgis = MagicMock()
    qgis.core = MagicMock()
    qgis.gui = MagicMock()
    qgis.PyQt = MagicMock()
    qgis.PyQt.QtCore = MagicMock()
    qgis.PyQt.QtGui = MagicMock()
    qgis.PyQt.QtWidgets = MagicMock()

    sys.modules.setdefault("qgis", qgis)
    sys.modules.setdefault("qgis.core", qgis.core)
    sys.modules.setdefault("qgis.gui", qgis.gui)
    sys.modules.setdefault("qgis.PyQt", qgis.PyQt)
    sys.modules.setdefault("qgis.PyQt.QtCore", qgis.PyQt.QtCore)
    sys.modules.setdefault("qgis.PyQt.QtGui", qgis.PyQt.QtGui)
    sys.modules.setdefault("qgis.PyQt.QtWidgets", qgis.PyQt.QtWidgets)


_install_qgis_mocks()
