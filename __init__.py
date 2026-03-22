"""
MapSplat - QGIS Plugin for exporting projects to static web maps

This plugin exports QGIS projects to self-contained web map packages
using PMTiles format and MapLibre GL JS for rendering.
"""

__version__ = "0.6.12"


def classFactory(iface):
    """Load MapSplat class from file mapsplat.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .mapsplat import MapSplat
    return MapSplat(iface)
