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

    # ---- basemap options (0.45.0) ----
    def _set_mode(self, mode):
        d = self.dock
        {"stream": d.radio_basemap_stream, "bundle": d.radio_basemap_bundle,
         "xyz": d.radio_basemap_xyz}[mode].setChecked(True)
        d._on_basemap_mode_changed()

    def test_basemap_controls_follow_mode(self):
        """Style row hides for XYZ; extract/source-type rows only in Download & clip;
        Latest only for Download & clip from a URL (daily builds cannot be streamed)."""
        d = self.dock
        self._set_mode("stream")
        self.assertFalse(d._basemap_style_widget.isHidden())
        self.assertTrue(d._basemap_extract_widget.isHidden())
        self.assertTrue(d.btn_basemap_latest.isHidden())
        self._set_mode("xyz")
        self.assertTrue(d._basemap_style_widget.isHidden())
        self.assertTrue(d.btn_basemap_latest.isHidden())
        self._set_mode("bundle")
        self.assertFalse(d._basemap_extract_widget.isHidden())
        self.assertFalse(d._basemap_srctype_widget.isHidden())
        d.radio_basemap_file.setChecked(True)
        self.assertTrue(d.btn_basemap_latest.isHidden())
        d.radio_basemap_url.setChecked(True)
        self.assertFalse(d.btn_basemap_latest.isHidden())
        # The CLI note only ever shows in Download & clip mode.
        self._set_mode("stream")
        self.assertTrue(d.lbl_pmtiles_cli.isHidden())

    def test_builtin_styles_resolve_to_shipped_files(self):
        import os
        d = self.dock
        for flavor in ("light", "dark", "white", "grayscale", "black"):
            d._set_basemap_style_choice(flavor)
            self.assertTrue(d.txt_basemap_style.isHidden(), flavor)
            self.assertTrue(os.path.isfile(d._resolved_basemap_style_path()), flavor)
        d._set_basemap_style_choice("custom")
        self.assertFalse(d.txt_basemap_style.isHidden())
        d.txt_basemap_style.setText("/tmp/my_style.json")
        self.assertEqual(d._resolved_basemap_style_path(), "/tmp/my_style.json")

    def _validate_with_basemap(self, mode, style_choice, custom_path="", source=None, answer=None):
        import tempfile
        from unittest import mock
        d = self.dock
        lyr = _layer("Polygon", "v")
        QgsProject.instance().addMapLayers([lyr])
        d.refresh_layer_list()
        d.layer_list.item(0).setSelected(True)
        d.txt_project_name.setText("webmap")
        d.txt_output_folder.setText(tempfile.gettempdir())
        d.basemap_group.setChecked(True)
        self._set_mode(mode)
        d.radio_basemap_url.setChecked(True)
        d.txt_basemap_source.setText(source or (
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png" if mode == "xyz"
            else "https://tiles.example.org/region.pmtiles"))
        d._set_basemap_style_choice(style_choice)
        d.txt_basemap_style.setText(custom_path)
        QMB = self.dockmod.QMessageBox
        with mock.patch.object(QMB, "warning") as warn, \
                mock.patch.object(QMB, "question", return_value=answer) as ask:
            ok = d._validate_export()
        d.basemap_group.setChecked(False)
        self.asked = [c.args[1] for c in ask.call_args_list]
        return ok, [c.args[1] for c in warn.call_args_list]

    def test_validation_builtin_style_ok(self):
        ok, warnings = self._validate_with_basemap("stream", "dark")
        self.assertTrue(ok, warnings)

    def test_validation_custom_style_missing_file(self):
        ok, warnings = self._validate_with_basemap("stream", "custom", "/nonexistent/style.json")
        self.assertFalse(ok)
        self.assertIn("Invalid Basemap Style", warnings)

    def test_validation_xyz_needs_no_style(self):
        """Bug fixed in 0.45.0: XYZ mode used to demand a style.json it never uses."""
        ok, warnings = self._validate_with_basemap("xyz", "custom", "")
        self.assertTrue(ok, warnings)

    def test_streaming_a_daily_build_asks_first(self):
        """Browsers cannot stream build.protomaps.com (no CORS), so exporting that asks first."""
        QMB = self.dockmod.QMessageBox
        build = "https://build.protomaps.com/20261003.pmtiles"
        ok, _ = self._validate_with_basemap("stream", "light", source=build,
                                            answer=QMB.StandardButton.No)
        self.assertFalse(ok)
        self.assertEqual(self.asked, ["Protomaps Build Cannot Be Streamed"])
        ok, _ = self._validate_with_basemap("stream", "light", source=build,
                                            answer=QMB.StandardButton.Yes)
        self.assertTrue(ok)
        # Clipping a daily build is the supported path: no question.
        ok, _ = self._validate_with_basemap("bundle", "light", source=build)
        self.assertTrue(ok)
        self.assertEqual(self.asked, [])

    def test_copy_extract_command(self):
        from qgis.core import QgsFeature, QgsGeometry
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtWidgets import QApplication
        d = self.dock
        lyr = _layer("Polygon", "area")
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromWkt("POLYGON((-70.3 43.6,-70.2 43.6,-70.2 43.7,-70.3 43.7,-70.3 43.6))"))
        lyr.dataProvider().addFeatures([f])
        lyr.updateExtents()
        QgsProject.instance().addMapLayers([lyr])
        d.refresh_layer_list()
        d.layer_list.item(0).setSelected(True)
        d.combo_extent_layer.setCurrentIndex(0)  # full extent of data
        d.spin_max_zoom.setValue(13)
        self._set_mode("bundle")
        d.radio_basemap_url.setChecked(True)
        d.txt_basemap_source.setText("https://build.protomaps.com/20261003.pmtiles")
        d._copy_extract_command()
        cmd = QApplication.clipboard().text()
        self.assertRegex(cmd, r"^pmtiles extract https://build\.protomaps\.com/20261003\.pmtiles "
                              r"basemap\.pmtiles --bbox=-70\.30\d*,43\.59\d*,-70\.19\d*,43\.70\d* --maxzoom=13$")
        # The command is also shown in a read-only, selectable field (user request, 0.45.0).
        self.assertFalse(d.txt_extract_cmd.isHidden())
        self.assertTrue(d.txt_extract_cmd.isReadOnly())
        self.assertEqual(d.txt_extract_cmd.text(), cmd)
        self.assertEqual(d.txt_extract_cmd.selectedText(), cmd)
        self.assertTrue(d.lbl_basemap_source_error.textInteractionFlags()
                        & Qt.TextInteractionFlag.TextSelectableByMouse)
        # Changing the zoom makes the shown command stale, so it is cleared and hidden.
        d.spin_max_zoom.setValue(12)
        self.assertTrue(d.txt_extract_cmd.isHidden())
        self.assertEqual(d.txt_extract_cmd.text(), "")
        # With no source entered, the command carries a placeholder and says so.
        d.txt_basemap_source.setText("")
        d._copy_extract_command()
        self.assertIn("YYYYMMDD", d.txt_extract_cmd.text())
        self.assertIn("placeholder", d.lbl_basemap_source_error.text())

    def test_style_choice_round_trips_through_config_file(self):
        import os
        import tempfile
        from unittest import mock
        d = self.dock
        path = os.path.join(tempfile.mkdtemp(), "cfg.toml")
        d._set_basemap_style_choice("grayscale")
        with mock.patch.object(self.dockmod.QFileDialog, "getSaveFileName", return_value=(path, "")):
            d._save_config()
        with open(path, encoding="utf-8") as fh:
            self.assertIn('style = "grayscale"', fh.read())
        d._set_basemap_style_choice("light")
        with mock.patch.object(self.dockmod.QFileDialog, "getOpenFileName", return_value=(path, "")):
            d._load_config()
        self.assertEqual(d._basemap_style_choice(), "grayscale")

    def test_pre_045_config_with_style_path_stays_custom(self):
        """A config saved before 0.45 has only style_path: it must load as a custom style."""
        import os
        import tempfile
        from unittest import mock
        d = self.dock
        path = os.path.join(tempfile.mkdtemp(), "old.toml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('[basemap]\nenabled = false\nstyle_path = "/srv/styles/mine.json"\n')
        d._set_basemap_style_choice("light")
        with mock.patch.object(self.dockmod.QFileDialog, "getOpenFileName", return_value=(path, "")):
            d._load_config()
        self.assertEqual(d._basemap_style_choice(), "custom")
        self.assertEqual(d.txt_basemap_style.text(), "/srv/styles/mine.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
