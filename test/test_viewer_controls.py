"""
MapSplat - Viewer Controls Tests

Tests that _get_html_template() conditionally includes each map control
based on the viewer_* settings dict keys.
"""

__version__ = "0.1.0"

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BOUNDS = [-95.0, 29.0, -90.0, 33.0]
STYLE = {}


def _make_html(overrides=None):
    """Return HTML from generate_html_viewer with all viewer controls enabled."""
    from exporter import generate_html_viewer
    settings = {
        "project_name": "test_map",
        "viewer_scale_bar": True,
        "viewer_geolocate": True,
        "viewer_fullscreen": True,
        "viewer_coords": True,
        "viewer_zoom_display": True,
        "viewer_reset_view": True,
        "viewer_north_reset": True,
    }
    if overrides:
        settings.update(overrides)
    return generate_html_viewer(settings, STYLE, BOUNDS)


class TestViewerControlsAllEnabled(unittest.TestCase):
    """When all viewer controls are True every token appears in the HTML."""

    def setUp(self):
        self.html = _make_html()

    def test_scale_bar_present(self):
        self.assertIn("ScaleControl", self.html)

    def test_geolocate_present(self):
        self.assertIn("GeolocateControl", self.html)

    def test_fullscreen_present(self):
        self.assertIn("FullscreenControl", self.html)

    def test_coords_display_present(self):
        self.assertIn("coords-display", self.html)

    def test_zoom_display_present(self):
        self.assertIn("zoom-display", self.html)

    def test_reset_view_present(self):
        self.assertIn("reset-view", self.html)

    def test_north_reset_present(self):
        self.assertIn("north-reset", self.html)


class TestViewerControlsIndividuallyDisabled(unittest.TestCase):
    """When a single viewer control is False its token is absent from the HTML."""

    def test_scale_bar_absent_when_disabled(self):
        html = _make_html({"viewer_scale_bar": False})
        self.assertNotIn("ScaleControl", html)

    def test_geolocate_absent_when_disabled(self):
        html = _make_html({"viewer_geolocate": False})
        self.assertNotIn("GeolocateControl", html)

    def test_fullscreen_absent_when_disabled(self):
        html = _make_html({"viewer_fullscreen": False})
        self.assertNotIn("FullscreenControl", html)

    def test_coords_display_absent_when_disabled(self):
        html = _make_html({"viewer_coords": False})
        self.assertNotIn("coords-display", html)

    def test_zoom_display_absent_when_disabled(self):
        html = _make_html({"viewer_zoom_display": False})
        self.assertNotIn("zoom-display", html)

    def test_reset_view_absent_when_disabled(self):
        html = _make_html({"viewer_reset_view": False})
        self.assertNotIn("reset-view", html)

    def test_north_reset_absent_when_disabled(self):
        html = _make_html({"viewer_north_reset": False})
        self.assertNotIn("north-reset", html)

    def test_disabling_one_control_leaves_others_intact(self):
        """Disabling scale bar does not remove other controls."""
        html = _make_html({"viewer_scale_bar": False})
        self.assertIn("GeolocateControl", html)
        self.assertIn("FullscreenControl", html)
        self.assertIn("coords-display", html)
        self.assertIn("zoom-display", html)
        self.assertIn("reset-view", html)
        self.assertIn("north-reset", html)


if __name__ == "__main__":
    unittest.main()
