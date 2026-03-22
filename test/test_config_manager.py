"""
MapSplat - Config Manager Tests

Tests for config file read/write roundtrip and edge cases.
"""

__version__ = "0.6.1"

import os
import sys
import tempfile
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import read_config, write_config


def _sample_config():
    """Return a representative config dict for testing."""
    return {
        "export": {
            "project_name": "stations_project",
            "output_folder": "C:/Users/me/Downloads/MapSplat",
            "layer_names": ["Stations", "Roads"],
            "pmtiles_mode": "single",
            "max_zoom": 12,
            "export_style_json": True,
            "style_only": False,
            "imported_style_path": "",
            "write_log": False,
        },
        "basemap": {
            "enabled": False,
            "source_type": "file",
            "source": "C:/PMtiles/maine4.pmtiles",
            "style_path": "",
        },
        "viewer": {
            "scale_bar": True,
            "geolocate": True,
            "fullscreen": True,
            "coords": True,
            "zoom_display": True,
            "reset_view": True,
            "north_reset": True,
        },
    }


class TestWriteReadRoundtrip(unittest.TestCase):
    """Full roundtrip: write a config, read it back, assert equality."""

    def test_roundtrip(self):
        config = _sample_config()
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp:
            path = tmp.name
        try:
            write_config(path, config)
            loaded = read_config(path)
            self.assertEqual(loaded, config)
        finally:
            os.unlink(path)

    def test_file_is_human_readable(self):
        """Written file should contain comment lines and section headers."""
        config = _sample_config()
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False, mode="w") as tmp:
            path = tmp.name
        try:
            write_config(path, config)
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn("[export]", content)
            self.assertIn("[basemap]", content)
            self.assertIn("[viewer]", content)
            self.assertIn("# MapSplat Export Configuration", content)
            self.assertIn("# Project name", content)
        finally:
            os.unlink(path)


class TestAllTypes(unittest.TestCase):
    """All supported value types round-trip correctly."""

    def test_boolean_true(self):
        config = {"export": {"export_style_json": True}}
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp:
            path = tmp.name
        try:
            write_config(path, config)
            loaded = read_config(path)
            self.assertIs(loaded["export"]["export_style_json"], True)
        finally:
            os.unlink(path)

    def test_boolean_false(self):
        config = {"export": {"style_only": False}}
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp:
            path = tmp.name
        try:
            write_config(path, config)
            loaded = read_config(path)
            self.assertIs(loaded["export"]["style_only"], False)
        finally:
            os.unlink(path)

    def test_integer(self):
        config = {"export": {"max_zoom": 14}}
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp:
            path = tmp.name
        try:
            write_config(path, config)
            loaded = read_config(path)
            self.assertEqual(loaded["export"]["max_zoom"], 14)
            self.assertIsInstance(loaded["export"]["max_zoom"], int)
        finally:
            os.unlink(path)

    def test_string(self):
        config = {"export": {"project_name": "my_webmap"}}
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp:
            path = tmp.name
        try:
            write_config(path, config)
            loaded = read_config(path)
            self.assertEqual(loaded["export"]["project_name"], "my_webmap")
        finally:
            os.unlink(path)

    def test_empty_string(self):
        config = {"export": {"imported_style_path": ""}}
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp:
            path = tmp.name
        try:
            write_config(path, config)
            loaded = read_config(path)
            self.assertEqual(loaded["export"]["imported_style_path"], "")
        finally:
            os.unlink(path)

    def test_string_array(self):
        config = {"export": {"layer_names": ["Stations", "Roads", "Boundaries"]}}
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp:
            path = tmp.name
        try:
            write_config(path, config)
            loaded = read_config(path)
            self.assertEqual(loaded["export"]["layer_names"], ["Stations", "Roads", "Boundaries"])
        finally:
            os.unlink(path)

    def test_empty_array(self):
        config = {"export": {"layer_names": []}}
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp:
            path = tmp.name
        try:
            write_config(path, config)
            loaded = read_config(path)
            self.assertEqual(loaded["export"]["layer_names"], [])
        finally:
            os.unlink(path)

    def test_string_with_backslash(self):
        """Windows paths with backslashes survive roundtrip."""
        config = {"export": {"output_folder": "C:\\Users\\me\\Downloads"}}
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp:
            path = tmp.name
        try:
            write_config(path, config)
            loaded = read_config(path)
            self.assertEqual(loaded["export"]["output_folder"], "C:\\Users\\me\\Downloads")
        finally:
            os.unlink(path)


class TestLoadMissingKeys(unittest.TestCase):
    """Partial config with missing keys doesn't raise; returns subset."""

    def test_partial_config(self):
        """A file with only some keys loads without error."""
        content = "[export]\nproject_name = \"test\"\nmax_zoom = 8\n"
        with tempfile.NamedTemporaryFile(
            suffix=".toml", delete=False, mode="w", encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            path = tmp.name
        try:
            loaded = read_config(path)
            self.assertEqual(loaded["export"]["project_name"], "test")
            self.assertEqual(loaded["export"]["max_zoom"], 8)
            # Other keys are simply absent
            self.assertNotIn("output_folder", loaded["export"])
        finally:
            os.unlink(path)

    def test_missing_section(self):
        """A file with only [export] section loads without [basemap] or [viewer]."""
        content = "[export]\nproject_name = \"test\"\n"
        with tempfile.NamedTemporaryFile(
            suffix=".toml", delete=False, mode="w", encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            path = tmp.name
        try:
            loaded = read_config(path)
            self.assertIn("export", loaded)
            self.assertNotIn("basemap", loaded)
            self.assertNotIn("viewer", loaded)
        finally:
            os.unlink(path)


class TestInvalidFile(unittest.TestCase):
    """Non-existent file raises FileNotFoundError."""

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            read_config("/tmp/nonexistent_mapsplat_config_xyz.toml")


class TestCommentsInFile(unittest.TestCase):
    """Comment lines are ignored; values parse correctly."""

    def test_comments_ignored(self):
        content = (
            "# This is a comment\n"
            "[export]\n"
            "# Another comment\n"
            "project_name = \"my_project\"\n"
            "max_zoom = 10  # inline comment ignored for non-strings\n"
            "\n"
            "# Blank lines are also fine\n"
            "style_only = false\n"
        )
        with tempfile.NamedTemporaryFile(
            suffix=".toml", delete=False, mode="w", encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            path = tmp.name
        try:
            loaded = read_config(path)
            self.assertEqual(loaded["export"]["project_name"], "my_project")
            self.assertEqual(loaded["export"]["max_zoom"], 10)
            self.assertIs(loaded["export"]["style_only"], False)
        finally:
            os.unlink(path)

    def test_full_comment_block_at_top(self):
        """Files starting with comment headers (like written configs) parse correctly."""
        config = _sample_config()
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp:
            path = tmp.name
        try:
            write_config(path, config)
            # Re-read a file with all the comment headers written by write_config
            loaded = read_config(path)
            self.assertEqual(loaded["export"]["project_name"], "stations_project")
            self.assertEqual(loaded["basemap"]["enabled"], False)
            self.assertEqual(loaded["viewer"]["scale_bar"], True)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
