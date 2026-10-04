"""
MapSplat - basemap helper and built-in style tests

Covers basemap_helpers (latest Protomaps build, extract command, built-in style paths), the
shipped basemap_styles/*.json files, and the bundled help/basemaps.html guide.
"""

__version__ = "0.1.0"

import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import basemap_helpers as bh  # noqa: E402


def _builds(*keys):
    return json.dumps([{"key": k, "size": 1, "uploaded": "2026-10-03T09:01:02Z"} for k in keys])


class TestLatestBuildUrl(unittest.TestCase):
    def test_picks_newest_regardless_of_order(self):
        data = _builds("20261002.pmtiles", "20261003.pmtiles", "20260801.pmtiles")
        self.assertEqual(bh.latest_build_url(data), "https://build.protomaps.com/20261003.pmtiles")

    def test_accepts_bytes(self):
        self.assertTrue(bh.latest_build_url(_builds("20261003.pmtiles").encode()).endswith(
            "/20261003.pmtiles"))

    def test_ignores_unexpected_keys(self):
        data = json.dumps([{"key": "20261003.pmtiles"}, {"key": "../evil.pmtiles"},
                           {"key": "99999999.pmtiles.bak"}, {"nokey": 1}, "junk"])
        self.assertEqual(bh.latest_build_url(data), "https://build.protomaps.com/20261003.pmtiles")

    def test_errors(self):
        for bad in ("not json", "{}", "[]", json.dumps([{"key": "latest.pmtiles"}])):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    bh.latest_build_url(bad)


class TestExtractCommand(unittest.TestCase):
    def test_matches_exporter_flags(self):
        cmd = bh.extract_command("https://build.protomaps.com/20261003.pmtiles",
                                 [-70.32, 43.62, -70.18, 43.72], 14)
        self.assertEqual(cmd, "pmtiles extract https://build.protomaps.com/20261003.pmtiles "
                              "basemap.pmtiles --bbox=-70.32,43.62,-70.18,43.72 --maxzoom=14")

    def test_rounds_to_six_decimals(self):
        cmd = bh.extract_command("src.pmtiles", [1.123456789, 2.0, 3.987654321, 4.5], 10)
        self.assertIn("--bbox=1.123457,2.0,3.987654,4.5", cmd)

    def test_quotes_paths_with_spaces(self):
        cmd = bh.extract_command("/data/My Maps/planet.pmtiles", [0, 0, 1, 1], 8, "out file.pmtiles")
        self.assertIn('"/data/My Maps/planet.pmtiles" "out file.pmtiles"', cmd)

    def test_clamps_to_web_mercator_world(self):
        # A zoomed-out map view can exceed the world; pmtiles would clip the wrong area.
        self.assertEqual(bh.clamp_bounds([-200, -95, 200, 95]), [-180.0, -85.0511, 180.0, 85.0511])
        self.assertEqual(bh.clamp_bounds([-70.3, 43.6, -70.2, 43.7]), [-70.3, 43.6, -70.2, 43.7])
        cmd = bh.extract_command("src.pmtiles", [-250.0, -89.9, 10.0, 89.9], 4)
        self.assertIn("--bbox=-180.0,-85.0511,10.0,85.0511", cmd)

    def test_rejects_inverted_bounds(self):
        with self.assertRaises(ValueError):
            bh.extract_command("src", [10, 0, 5, 1], 8)


class TestStreamability(unittest.TestCase):
    def test_daily_build_detection(self):
        self.assertTrue(bh.is_protomaps_daily_build("https://build.protomaps.com/20261003.pmtiles"))
        self.assertTrue(bh.is_protomaps_daily_build(" HTTPS://Build.Protomaps.com/x.pmtiles "))
        self.assertFalse(bh.is_protomaps_daily_build("https://maps.protomaps.com/builds/"))
        self.assertFalse(bh.is_protomaps_daily_build("https://example.org/build.protomaps.com.pmtiles"))
        self.assertFalse(bh.is_protomaps_daily_build("/data/planet.pmtiles"))
        self.assertFalse(bh.is_protomaps_daily_build(None))

    def test_cross_origin_header(self):
        self.assertTrue(bh.allows_cross_origin("*"))
        self.assertTrue(bh.allows_cross_origin(bh.CORS_PROBE_ORIGIN))
        # build.protomaps.com answers only its own viewer's origin, or nothing at all.
        self.assertFalse(bh.allows_cross_origin("https://maps.protomaps.com"))
        self.assertFalse(bh.allows_cross_origin(None))
        self.assertFalse(bh.allows_cross_origin(""))


class TestBuiltinStyles(unittest.TestCase):
    def test_every_flavor_ships_a_valid_style(self):
        for label, flavor in bh.BUILTIN_FLAVORS.items():
            with self.subTest(flavor=flavor):
                path = bh.builtin_style_path(flavor, ROOT)
                self.assertTrue(os.path.isfile(path), path)
                style = json.load(open(path, encoding="utf-8"))
                self.assertEqual(style["version"], 8)
                self.assertEqual(style["metadata"]["mapsplat:flavor"], flavor)
                # The exporter rewrites the first vector source with a URL to the chosen basemap.
                src = style["sources"]["protomaps"]
                self.assertEqual(src["type"], "vector")
                self.assertTrue(src["url"].startswith("pmtiles://"))
                self.assertIn("OpenStreetMap", src["attribution"])
                self.assertIn("{fontstack}", style["glyphs"])
                self.assertTrue(style["sprite"].endswith("/" + flavor))
                self.assertGreater(len(style["layers"]), 50)
                ids = [ly["id"] for ly in style["layers"]]
                self.assertEqual(len(ids), len(set(ids)), "duplicate layer ids")
                self.assertTrue(all(ly.get("source", "protomaps") == "protomaps" for ly in style["layers"]))

    def test_unknown_flavor_rejected(self):
        with self.assertRaises(ValueError):
            bh.builtin_style_path("neon", ROOT)

    def test_licence_ships_with_styles(self):
        text = open(os.path.join(ROOT, "basemap_styles", "LICENSE-protomaps-basemaps.md"),
                    encoding="utf-8").read()
        self.assertIn("BSD 3-Clause", text)


class TestGuide(unittest.TestCase):
    def setUp(self):
        self.html = open(os.path.join(ROOT, bh.GUIDE_RELATIVE_PATH), encoding="utf-8").read()

    def test_self_contained(self):
        # No scripts, stylesheets, fonts or images from elsewhere: it must work offline.
        self.assertNotRegex(self.html, r"<script|<link\b|@import|url\(|<img\b")

    def test_in_page_links_resolve(self):
        ids = set(re.findall(r'id="([^"]+)"', self.html))
        for target in re.findall(r'href="#([^"]+)"', self.html):
            self.assertIn(target, ids)

    def test_mentions_every_builtin_style_and_control(self):
        for label in bh.BUILTIN_FLAVORS:
            self.assertIn(label, self.html)
        for control in ("Latest", "Copy extract command", "Download &amp; clip offline",
                        "Stream from URL", "Custom style.json..."):
            self.assertIn(control, self.html)

    def test_online_url_in_guide(self):
        self.assertIn(bh.GUIDE_ONLINE_URL, self.html)


if __name__ == "__main__":
    unittest.main()
