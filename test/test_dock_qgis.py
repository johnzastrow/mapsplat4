"""QGIS-integration tests for the dock's layer-list / symbology code.

These exercise the real QGIS objects (layers + renderers) that the pure-Python
suite can't, and that segfaulted QGIS in the field. They MUST run under QGIS's
own Python — use ``scripts/run_qgis_tests.sh``. They auto-skip when QGIS isn't
importable, so the ordinary ``pytest`` run stays green without QGIS.

Regression coverage:
- ``park_polygons`` crash: ``_get_symbology_warning`` on a categorized/graduated/
  rule renderer used to dereference symbols owned by temporary containers →
  use-after-free segfault. Fixed by cloning; guarded here.
- blank layer list: ``refresh_layer_list`` must populate from ``mapLayers()``.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Only run under REAL QGIS Python (scripts/run_qgis_tests.sh sets this). The ordinary
# pytest suite mocks `qgis` via conftest, so an import check isn't enough to tell the
# two apart — gate on the explicit env var instead.
_RUN = os.environ.get("MAPSPLAT_QGIS_TEST") == "1"
if _RUN:
    try:
        from qgis.core import (
            QgsApplication, QgsProject, QgsVectorLayer,
            QgsSingleSymbolRenderer, QgsCategorizedSymbolRenderer, QgsRendererCategory,
            QgsGraduatedSymbolRenderer, QgsRendererRange, QgsRuleBasedRenderer,
            QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol,
        )
    except Exception:  # pragma: no cover - depends on interpreter
        _RUN = False


class _FakeIface:
    """Minimal QgisInterface stand-in — the dock only stores it + reads these."""
    def mapCanvas(self):
        return None

    def activeLayer(self):
        return None


def _sym(geom):
    return {"Polygon": QgsFillSymbol, "LineString": QgsLineSymbol,
            "Point": QgsMarkerSymbol}[geom].createSimple({})


def _layer(geom, name):
    return QgsVectorLayer(f"{geom}?crs=EPSG:4326&field=cat:string", name, "memory")


@unittest.skipUnless(_RUN, "set MAPSPLAT_QGIS_TEST=1; run via scripts/run_qgis_tests.sh")
class DockQgisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qgs = QgsApplication([], True)
        cls.qgs.initQgis()
        import mapsplat4.mapsplat_dockwidget as dockmod  # package-qualified relative imports
        cls.dockmod = dockmod
        cls.dock = dockmod.MapSplatDockWidget(_FakeIface())

    @classmethod
    def tearDownClass(cls):
        QgsProject.instance().removeAllMapLayers()
        cls.qgs.exitQgis()

    def setUp(self):
        QgsProject.instance().removeAllMapLayers()

    # ---- renderer fixtures (symbols come from temporaries — the crash surface) ----
    def _categorized(self, geom):
        cats = [QgsRendererCategory(v, _sym(geom), v) for v in ("a", "b", "c")]
        return QgsCategorizedSymbolRenderer("cat", cats)

    def _graduated(self, geom):
        ranges = [QgsRendererRange(lo, hi, _sym(geom), f"{lo}-{hi}")
                  for lo, hi in ((0, 1), (1, 2))]
        return QgsGraduatedSymbolRenderer("cat", ranges)

    def _rule(self, geom):
        root = QgsRuleBasedRenderer.Rule(None)
        root.appendChild(QgsRuleBasedRenderer.Rule(_sym(geom), 0, 0, '"cat" = \'a\''))
        return QgsRuleBasedRenderer(root)

    def _all_fixtures(self):
        """One layer per (geometry, renderer) we introspect — incl. the exact repro."""
        out = []
        for geom in ("Polygon", "LineString", "Point"):
            single = _layer(geom, f"{geom}_single")
            single.setRenderer(QgsSingleSymbolRenderer(_sym(geom)))
            out.append(single)
            cat = _layer(geom, "park_polygons" if geom == "Polygon" else f"{geom}_cat")
            cat.setRenderer(self._categorized(geom))
            out.append(cat)
            grad = _layer(geom, f"{geom}_grad")
            grad.setRenderer(self._graduated(geom))
            out.append(grad)
            rule = _layer(geom, f"{geom}_rule")
            rule.setRenderer(self._rule(geom))
            out.append(rule)
        return out

    # ------------------------------------------------------------------ tests
    def test_symbology_warning_never_crashes(self):
        """The park_polygons regression: introspecting any renderer must not segfault.
        A crash would kill the whole process, so simply returning is the assertion."""
        for lyr in self._all_fixtures():
            self.assertTrue(lyr.isValid(), lyr.name())
            result = self.dock._get_symbology_warning(lyr)
            self.assertTrue(result is None or isinstance(result, tuple), lyr.name())

    def test_layer_list_populates_from_maplayers(self):
        """Blank-list regression: every valid layer shows up in the list widget."""
        fixtures = self._all_fixtures()
        QgsProject.instance().addMapLayers(fixtures)
        self.dock.refresh_layer_list()
        self.assertEqual(self.dock.layer_list.count(), len(fixtures))

    def test_geometry_prefixes(self):
        """geometryType() enum (QGIS 4) is normalised to the right [Point]/[Line]/[Polygon]."""
        layers = {
            "Point": _layer("Point", "pt"),
            "LineString": _layer("LineString", "ln"),
            "Polygon": _layer("Polygon", "pg"),
        }
        QgsProject.instance().addMapLayers(list(layers.values()))
        self.dock.refresh_layer_list()
        texts = [self.dock.layer_list.item(i).text()
                 for i in range(self.dock.layer_list.count())]
        self.assertTrue(any(t.startswith("[Point]") for t in texts))
        self.assertTrue(any(t.startswith("[Line]") for t in texts))
        self.assertTrue(any(t.startswith("[Polygon]") for t in texts))

    def test_refresh_with_selection_no_crash(self):
        """Phase 1 / Pitfall 4 regression: refreshing (e.g. the Refresh button) while
        layers are SELECTED must not crash — clear() with a live selection used to fire
        itemSelectionChanged mid-mutation into slots reading half-deleted items."""
        QgsProject.instance().addMapLayers(self._all_fixtures())
        self.dock.refresh_layer_list()
        for i in range(min(4, self.dock.layer_list.count())):
            self.dock.layer_list.item(i).setSelected(True)
        self.dock.refresh_layer_list()   # the crash trigger
        self.dock.refresh_layer_list()   # and again
        self.assertGreater(self.dock.layer_list.count(), 0)
        # selection is preserved across refresh
        self.assertGreater(len(self.dock.layer_list.selectedItems()), 0)

    def test_readiness_gating(self):
        """Phase 1: readiness reflects the required fields and gates the Export button."""
        import tempfile
        if not hasattr(self.dock, "_run_readiness"):
            self.skipTest("tabs build has no readiness")
        QgsProject.instance().addMapLayers(self._all_fixtures())
        self.dock.refresh_layer_list()
        self.dock.txt_project_name.setText("")
        self.dock.txt_output_folder.setText("")
        self.dock.layer_list.clearSelection()
        ready, missing = self.dock._run_readiness()
        self.assertFalse(ready)
        self.assertEqual(set(missing), {"select a layer", "name the project", "set an output folder"})
        self.dock.layer_list.item(0).setSelected(True)
        self.dock.txt_project_name.setText("webmap")
        self.dock.txt_output_folder.setText(tempfile.gettempdir())
        ready, missing = self.dock._run_readiness()
        self.assertTrue(ready, missing)


if __name__ == "__main__":
    unittest.main(verbosity=2)
