"""
MapSplat - ogr2ogr PMTiles arguments

Regression test for exports failing with "Cannot find OGR field for Arrow array ogc_fid": ogr2ogr's
Arrow write path (GDAL 3.12) cannot handle a layer whose attributes include a field literally named
``ogc_fid``. MapSplat turns that path off for its PMTiles conversion.
"""

__version__ = "0.1.0"

import json
import os
import shutil
import subprocess  # nosec B404 - runs the local ogr2ogr only, with fixed arguments
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exporter import ogr2ogr_pmtiles_args  # noqa: E402


class TestArgs(unittest.TestCase):
    def test_arrow_api_disabled_before_driver_options(self):
        args = ogr2ogr_pmtiles_args("out.pmtiles", "in.gpkg", 13)
        i = args.index("--config")
        self.assertEqual(args[i:i + 3], ["--config", "OGR2OGR_USE_ARROW_API", "NO"])
        self.assertLess(i, args.index("-f"))

    def test_zoom_crs_and_paths(self):
        args = ogr2ogr_pmtiles_args("/o/out.pmtiles", "/i/in.gpkg", 11)
        self.assertIn("MAXZOOM=11", args)
        self.assertEqual(args[args.index("-s_srs") + 1], "EPSG:3857")
        self.assertEqual(args[-2:], ["/o/out.pmtiles", "/i/in.gpkg"])


@unittest.skipUnless(shutil.which("ogr2ogr"), "needs GDAL's ogr2ogr")
class TestRealConversion(unittest.TestCase):
    """Run the real ogr2ogr on a GeoPackage layer that has an ``ogc_fid`` attribute."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mapsplat_ogr_")
        src = os.path.join(self.tmp, "in.geojson")
        with open(src, "w", encoding="utf-8") as fh:
            json.dump({"type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {"ogc_fid": i, "name": f"pond {i}"},
                 "geometry": {"type": "Polygon", "coordinates": [[
                     [-7822700 + i * 100, 5431800], [-7822600 + i * 100, 5431800],
                     [-7822600 + i * 100, 5431900], [-7822700 + i * 100, 5431800]]]}}
                for i in range(3)]}, fh)
        self.gpkg = os.path.join(self.tmp, "layers.gpkg")
        subprocess.run(["ogr2ogr", "-f", "GPKG", "-a_srs", "EPSG:3857", "-nln", "ponds",  # nosec B603 B607
                        self.gpkg, src], check=True, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_layer_with_ogc_fid_field_converts(self):
        out = os.path.join(self.tmp, "layers.pmtiles")
        res = subprocess.run(["ogr2ogr", *ogr2ogr_pmtiles_args(out, self.gpkg, 10)],  # nosec B603 B607
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("ERROR", res.stderr)
        info = subprocess.run(["ogrinfo", "-so", out, "ponds"],  # nosec B603 B607
                              capture_output=True, text=True).stdout
        self.assertIn("ogc_fid", info)  # the attribute itself is kept


if __name__ == "__main__":
    unittest.main()
