"""
MapSplat - Style Converter Tests

Tests for the QGIS to MapLibre style conversion.
"""

__version__ = "0.6.12"

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestStyleConverterHelpers(unittest.TestCase):
    """Test helper methods that don't require QGIS."""

    def test_sanitize_name_basic(self):
        """Test basic name sanitization."""
        from style_converter import StyleConverter

        converter = StyleConverter([], {})

        self.assertEqual(converter._sanitize_name("roads"), "roads")
        self.assertEqual(converter._sanitize_name("my roads"), "my_roads")
        self.assertEqual(converter._sanitize_name("Roads Layer"), "roads_layer")

    def test_sanitize_name_special_chars(self):
        """Test name sanitization with special characters."""
        from style_converter import StyleConverter

        converter = StyleConverter([], {})

        self.assertEqual(converter._sanitize_name("roads!@#$%"), "roads")
        self.assertEqual(converter._sanitize_name("my-roads"), "my_roads")
        self.assertEqual(converter._sanitize_name("roads (2024)"), "roads_2024")

    def test_sanitize_name_consecutive_underscores(self):
        """Test that consecutive underscores are collapsed."""
        from style_converter import StyleConverter

        converter = StyleConverter([], {})

        self.assertEqual(converter._sanitize_name("my  roads"), "my_roads")
        self.assertEqual(converter._sanitize_name("a___b"), "a_b")


class TestStyleConverterOutput(unittest.TestCase):
    """Test style converter output structure."""

    def test_convert_empty_layers(self):
        """Test conversion with no layers."""
        from style_converter import StyleConverter

        converter = StyleConverter([], {"project_name": "test"})
        style = converter.convert()

        self.assertEqual(style["version"], 8)
        self.assertIn("sources", style)
        self.assertIn("layers", style)
        self.assertIn("mapsplat", style["sources"])

    def test_convert_has_background_layer(self):
        """Test that output always has a background layer."""
        from style_converter import StyleConverter

        converter = StyleConverter([], {"project_name": "test"})
        style = converter.convert()

        background = next((l for l in style["layers"] if l["id"] == "background"), None)
        self.assertIsNotNone(background)
        self.assertEqual(background["type"], "background")


class TestMergeBusinessIntoBasemap(unittest.TestCase):
    """Test _merge_business_into_basemap logic (no QGIS required)."""

    def _make_basemap_style(self):
        return {
            "version": 8,
            "sources": {
                "protomaps": {
                    "type": "vector",
                    "url": "pmtiles://https://build.protomaps.com/20260217.pmtiles",
                }
            },
            "layers": [
                {"id": "background", "type": "background", "paint": {"background-color": "#fff"}},
                {"id": "water", "type": "fill", "source": "protomaps", "source-layer": "water"},
            ],
        }

    def _make_business_style(self):
        return {
            "version": 8,
            "sources": {
                "mapsplat": {
                    "type": "vector",
                    "url": "pmtiles://data/layers.pmtiles",
                }
            },
            "layers": [
                {"id": "background", "type": "background", "paint": {"background-color": "#eee"}},
                {"id": "roads-fill", "type": "fill", "source": "mapsplat", "source-layer": "roads"},
            ],
        }

    def _run_merge(self, basemap_style, business_style):
        """Run the merge logic extracted from exporter without QGIS."""
        import json, os, tempfile

        # Write basemap style to a temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(basemap_style, f)
            style_path = f.name

        try:
            # Replicate _merge_business_into_basemap logic inline
            with open(style_path, "r", encoding="utf-8") as f:
                result = json.load(f)

            for src_name, src in result.get("sources", {}).items():
                if src.get("type") == "vector" and "protomaps" in src.get("url", ""):
                    src["url"] = "pmtiles://data/basemap.pmtiles"
                    break

            result.setdefault("sources", {}).update(business_style.get("sources", {}))

            overlay_layers = [
                l for l in business_style.get("layers", []) if l.get("id") != "background"
            ]
            result.setdefault("layers", []).extend(overlay_layers)

            return result
        finally:
            os.unlink(style_path)

    def test_sources_merged(self):
        """Business sources are added to basemap sources."""
        result = self._run_merge(self._make_basemap_style(), self._make_business_style())
        self.assertIn("protomaps", result["sources"])
        self.assertIn("mapsplat", result["sources"])

    def test_background_not_duplicated(self):
        """Business background layer is NOT appended (basemap has its own)."""
        result = self._run_merge(self._make_basemap_style(), self._make_business_style())
        bg_layers = [l for l in result["layers"] if l["id"] == "background"]
        self.assertEqual(len(bg_layers), 1, "Should have exactly one background layer")

    def test_overlay_layers_appended(self):
        """Business overlay layers are appended after basemap layers."""
        result = self._run_merge(self._make_basemap_style(), self._make_business_style())
        layer_ids = [l["id"] for l in result["layers"]]
        # basemap layers come first, business layers appended at end
        self.assertIn("water", layer_ids)
        self.assertIn("roads-fill", layer_ids)
        self.assertGreater(layer_ids.index("roads-fill"), layer_ids.index("water"))

    def test_basemap_url_redirected_to_local(self):
        """Basemap protomaps remote URL is replaced with local pmtiles path."""
        result = self._run_merge(self._make_basemap_style(), self._make_business_style())
        protomaps_src = result["sources"].get("protomaps", {})
        self.assertEqual(protomaps_src.get("url"), "pmtiles://data/basemap.pmtiles")

    def test_business_layer_source_preserved(self):
        """Business layer source URL is preserved as-is."""
        result = self._run_merge(self._make_basemap_style(), self._make_business_style())
        mapsplat_src = result["sources"].get("mapsplat", {})
        self.assertEqual(mapsplat_src.get("url"), "pmtiles://data/layers.pmtiles")




class TestComputeSpriteLayout(unittest.TestCase):
    """Test atlas layout computation — pure Python, no QGIS required."""

    def _layout(self, sizes):
        from style_converter import StyleConverter
        return StyleConverter([], {})._compute_sprite_layout(sizes)

    def test_empty_input(self):
        manifest, w, h = self._layout({})
        self.assertEqual(manifest, {})
        self.assertEqual(w, 0)
        self.assertEqual(h, 0)

    def test_single_image(self):
        manifest, w, h = self._layout({"icon_a": (32, 32)})
        self.assertEqual(w, 32)
        self.assertEqual(h, 32)
        self.assertEqual(manifest["icon_a"], {
            "x": 0, "y": 0, "width": 32, "height": 32, "pixelRatio": 1
        })

    def test_two_images_placed_side_by_side(self):
        manifest, w, h = self._layout({"a": (32, 32), "b": (16, 16)})
        self.assertEqual(manifest["a"]["x"], 0)
        self.assertEqual(manifest["b"]["x"], 32)
        self.assertEqual(w, 48)
        self.assertEqual(h, 32)  # tallest image height

    def test_manifest_has_required_maplibre_fields(self):
        manifest, _, _ = self._layout({"x": (64, 64)})
        for field in ("x", "y", "width", "height", "pixelRatio"):
            self.assertIn(field, manifest["x"])

    def test_pixel_ratio_is_one(self):
        manifest, _, _ = self._layout({"z": (48, 48)})
        self.assertEqual(manifest["z"]["pixelRatio"], 1)



class TestBuildSymbolLayerForSprite(unittest.TestCase):
    """Test _build_symbol_layer_for_sprite — pure Python, no QGIS required."""

    def _make_converter(self):
        from style_converter import StyleConverter
        c = StyleConverter([], {})
        c._svg_sprite_map = {}
        c._single_file = True
        return c

    def _call(self, sprite_key="my_layer", source_layer="my_layer",
              source_name="mapsplat", layer_id="my_layer", size_px=30.0):
        c = self._make_converter()
        return c._build_symbol_layer_for_sprite(layer_id, sprite_key, source_name, source_layer, size_px)

    def test_layer_type_is_symbol(self):
        result = self._call()
        self.assertEqual(result["type"], "symbol")

    def test_icon_image_matches_sprite_key(self):
        result = self._call(sprite_key="my_layer")
        self.assertEqual(result["layout"]["icon-image"], "my_layer")

    def test_required_maplibre_fields_present(self):
        result = self._call()
        for field in ("id", "type", "source", "source-layer", "layout"):
            self.assertIn(field, result)

    def test_icon_size_is_one(self):
        result = self._call()
        self.assertEqual(result["layout"]["icon-size"], 1.0)

    def test_icon_allow_overlap_true(self):
        result = self._call()
        self.assertTrue(result["layout"]["icon-allow-overlap"])

    def test_source_and_source_layer_set_correctly(self):
        result = self._call(source_name="mapsplat", source_layer="my_layer")
        self.assertEqual(result["source"], "mapsplat")
        self.assertEqual(result["source-layer"], "my_layer")



class TestSpriteBasemapMerge(unittest.TestCase):
    """Test sprite handling in basemap merge — pure Python logic, no QGIS import.

    Policy: the local business sprite always wins.  Multi-sprite arrays with
    remote URLs are unreliable offline, so we override basemap["sprite"] with
    the local business sprite URL whenever one is present.  Business icon-image
    references are left as-is (no "biz:" prefix needed).
    """

    def _run_sprite_merge(self, basemap_sprite, business_sprite, overlay_layers=None):
        """Replicate the sprite-handling portion of _merge_business_into_basemap."""
        basemap = (
            {"sources": {}, "layers": [], "sprite": basemap_sprite}
            if basemap_sprite
            else {"sources": {}, "layers": []}
        )
        business = (
            {"sources": {}, "layers": overlay_layers or [], "sprite": business_sprite}
            if business_sprite
            else {"sources": {}, "layers": overlay_layers or []}
        )

        b_sprite = business.get("sprite")

        if b_sprite:
            basemap["sprite"] = b_sprite

        return basemap

    def test_no_sprites_no_sprite_key(self):
        result = self._run_sprite_merge(None, None)
        self.assertNotIn("sprite", result)

    def test_only_business_sprite_sets_sprite_directly(self):
        result = self._run_sprite_merge(None, "./sprites")
        self.assertEqual(result["sprite"], "./sprites")

    def test_both_sprites_business_wins(self):
        """When basemap also has a sprite, the local business sprite takes over."""
        result = self._run_sprite_merge(
            "https://example.com/basemap/sprites", "./sprites"
        )
        self.assertEqual(result["sprite"], "./sprites")

    def test_both_sprites_result_is_string_not_array(self):
        result = self._run_sprite_merge(
            "https://example.com/basemap/sprites", "./sprites"
        )
        self.assertIsInstance(result["sprite"], str)

    def test_icon_image_not_prefixed(self):
        """icon-image values are left unchanged (no 'biz:' prefix)."""
        overlay = [{"id": "icon_layer", "type": "symbol",
                    "layout": {"icon-image": "my_icon"}}]
        result = self._run_sprite_merge(
            "https://example.com/basemap/sprites", "./sprites",
            overlay_layers=overlay,
        )
        # icon-image is NOT mutated
        self.assertEqual(overlay[0]["layout"]["icon-image"], "my_icon")

    def test_only_basemap_sprite_left_unchanged(self):
        result = self._run_sprite_merge("https://example.com/basemap/sprites", None)
        self.assertEqual(result.get("sprite"), "https://example.com/basemap/sprites")


class TestQuadrantToAnchorMapping(unittest.TestCase):
    """Test module-level quadrant-position → MapLibre text-anchor lookup table."""

    def _dict(self):
        from style_converter import _QGIS_QUADRANT_TO_ANCHOR
        return _QGIS_QUADRANT_TO_ANCHOR

    def test_all_nine_quadrant_values_covered(self):
        d = self._dict()
        for i in range(9):
            self.assertIn(i, d, f"Quadrant {i} missing from mapping")

    def test_above_maps_to_bottom_anchor(self):
        # QuadrantAbove (1): label sits above the point → bottom of text box anchors to point
        self.assertEqual(self._dict()[1], "bottom")

    def test_over_maps_to_center(self):
        # QuadrantOver (4): label centred on the point
        self.assertEqual(self._dict()[4], "center")

    def test_below_maps_to_top_anchor(self):
        # QuadrantBelow (7): label sits below the point → top of text box anchors to point
        self.assertEqual(self._dict()[7], "top")

    def test_left_maps_to_right_anchor(self):
        # QuadrantLeft (3): label sits left of point → right edge of text at point
        self.assertEqual(self._dict()[3], "right")

    def test_right_maps_to_left_anchor(self):
        # QuadrantRight (5): label sits right of point → left edge of text at point
        self.assertEqual(self._dict()[5], "left")

    def test_above_left_maps_to_bottom_right(self):
        self.assertEqual(self._dict()[0], "bottom-right")

    def test_above_right_maps_to_bottom_left(self):
        self.assertEqual(self._dict()[2], "bottom-left")

    def test_below_left_maps_to_top_right(self):
        self.assertEqual(self._dict()[6], "top-right")

    def test_below_right_maps_to_top_left(self):
        self.assertEqual(self._dict()[8], "top-left")

    def test_all_values_are_valid_maplibre_anchors(self):
        valid = {
            "top", "bottom", "left", "right", "center",
            "top-left", "top-right", "bottom-left", "bottom-right",
        }
        for quadrant, anchor in self._dict().items():
            self.assertIn(
                anchor, valid,
                f"Quadrant {quadrant} → '{anchor}' is not a valid MapLibre anchor",
            )


class TestAnchorDistDir(unittest.TestCase):
    """Test module-level anchor → outward-push direction table."""

    def _dict(self):
        from style_converter import _ANCHOR_DIST_DIR
        return _ANCHOR_DIST_DIR

    def test_all_nine_maplibre_anchors_covered(self):
        expected = {
            "top", "bottom", "left", "right", "center",
            "top-left", "top-right", "bottom-left", "bottom-right",
        }
        self.assertEqual(set(self._dict().keys()), expected)

    def test_all_directions_are_two_element_tuples(self):
        for anchor, direction in self._dict().items():
            self.assertIsInstance(direction, tuple, f"{anchor} value must be a tuple")
            self.assertEqual(len(direction), 2, f"{anchor} direction must have 2 components")

    def test_bottom_pushes_upward(self):
        _, dy = self._dict()["bottom"]
        self.assertLess(dy, 0, "bottom anchor: positive dist must push label up (negative y)")

    def test_top_pushes_downward(self):
        _, dy = self._dict()["top"]
        self.assertGreater(dy, 0, "top anchor: positive dist must push label down (positive y)")

    def test_left_pushes_rightward(self):
        dx, _ = self._dict()["left"]
        self.assertGreater(dx, 0, "left anchor: positive dist must push label right (positive x)")

    def test_right_pushes_leftward(self):
        dx, _ = self._dict()["right"]
        self.assertLess(dx, 0, "right anchor: positive dist must push label left (negative x)")

    def test_center_has_zero_direction(self):
        self.assertEqual(self._dict()["center"], (0, 0))

    def test_bottom_has_no_horizontal_component(self):
        dx, _ = self._dict()["bottom"]
        self.assertEqual(dx, 0)

    def test_top_has_no_horizontal_component(self):
        dx, _ = self._dict()["top"]
        self.assertEqual(dx, 0)

    def test_left_has_no_vertical_component(self):
        _, dy = self._dict()["left"]
        self.assertEqual(dy, 0)

    def test_right_has_no_vertical_component(self):
        _, dy = self._dict()["right"]
        self.assertEqual(dy, 0)


class TestGetLabelFont(unittest.TestCase):
    """Test _get_label_font() — no QGIS required, uses plain mocks."""

    def _converter(self):
        from style_converter import StyleConverter
        return StyleConverter([], {})

    def _text_format(self, bold=False, italic=False,
                     forced_bold=False, forced_italic=False,
                     has_forced_attrs=True):
        """Build a minimal mock QgsTextFormat for _get_label_font."""
        from unittest.mock import MagicMock
        font = MagicMock()
        font.bold.return_value = bold
        font.italic.return_value = italic
        tf = MagicMock()
        tf.font.return_value = font
        if has_forced_attrs:
            tf.forcedBold.return_value = forced_bold
            tf.forcedItalic.return_value = forced_italic
        else:
            tf.forcedBold.side_effect = AttributeError("QGIS < 3.26")
            tf.forcedItalic.side_effect = AttributeError("QGIS < 3.26")
        return tf

    def test_regular_font_returns_noto_sans_regular(self):
        result = self._converter()._get_label_font(self._text_format())
        self.assertEqual(result, ["Noto Sans Regular"])

    def test_bold_returns_noto_sans_medium(self):
        result = self._converter()._get_label_font(self._text_format(bold=True))
        self.assertEqual(result, ["Noto Sans Medium"])

    def test_italic_returns_noto_sans_italic(self):
        result = self._converter()._get_label_font(self._text_format(italic=True))
        self.assertEqual(result, ["Noto Sans Italic"])

    def test_bold_takes_priority_over_italic(self):
        result = self._converter()._get_label_font(
            self._text_format(bold=True, italic=True)
        )
        self.assertEqual(result, ["Noto Sans Medium"])

    def test_forced_bold_overrides_non_bold_font(self):
        tf = self._text_format(bold=False, forced_bold=True)
        self.assertEqual(self._converter()._get_label_font(tf), ["Noto Sans Medium"])

    def test_forced_italic_overrides_non_italic_font(self):
        tf = self._text_format(italic=False, forced_italic=True)
        self.assertEqual(self._converter()._get_label_font(tf), ["Noto Sans Italic"])

    def test_forced_bold_takes_priority_over_forced_italic(self):
        tf = self._text_format(forced_bold=True, forced_italic=True)
        self.assertEqual(self._converter()._get_label_font(tf), ["Noto Sans Medium"])

    def test_no_forced_attrs_falls_back_to_font_flags_bold(self):
        # QGIS < 3.26: forcedBold/forcedItalic raise AttributeError
        tf = self._text_format(bold=True, has_forced_attrs=False)
        self.assertEqual(self._converter()._get_label_font(tf), ["Noto Sans Medium"])

    def test_no_forced_attrs_falls_back_to_font_flags_italic(self):
        tf = self._text_format(italic=True, has_forced_attrs=False)
        self.assertEqual(self._converter()._get_label_font(tf), ["Noto Sans Italic"])

    def test_no_forced_attrs_regular_stays_regular(self):
        tf = self._text_format(bold=False, italic=False, has_forced_attrs=False)
        self.assertEqual(self._converter()._get_label_font(tf), ["Noto Sans Regular"])

    def test_returns_single_element_list(self):
        result = self._converter()._get_label_font(self._text_format())
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_returned_font_name_is_string(self):
        result = self._converter()._get_label_font(self._text_format())
        self.assertIsInstance(result[0], str)


class TestExpressionConversion(unittest.TestCase):
    """Test _convert_qgis_expression_to_maplibre — pure Python regex logic."""

    def _convert(self, expr):
        from style_converter import StyleConverter
        return StyleConverter([], {})._convert_qgis_expression_to_maplibre(expr)

    def test_empty_string_returns_none(self):
        self.assertIsNone(self._convert(""))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(self._convert("   "))

    def test_none_returns_none(self):
        self.assertIsNone(self._convert(None))

    def test_equality_string_value(self):
        result = self._convert('"type" = \'road\'')
        self.assertEqual(result, ["==", ["get", "type"], "road"])

    def test_equality_integer_value(self):
        result = self._convert('"population" = 1000')
        self.assertEqual(result, ["==", ["get", "population"], 1000.0])

    def test_equality_decimal_value(self):
        result = self._convert('"ratio" = 0.5')
        self.assertEqual(result, ["==", ["get", "ratio"], 0.5])

    def test_greater_than(self):
        result = self._convert('"speed" > 50')
        self.assertEqual(result, [">", ["get", "speed"], 50.0])

    def test_less_than(self):
        result = self._convert('"speed" < 30')
        self.assertEqual(result, ["<", ["get", "speed"], 30.0])

    def test_greater_than_or_equal(self):
        result = self._convert('"rank" >= 3')
        self.assertEqual(result, [">=", ["get", "rank"], 3.0])

    def test_less_than_or_equal(self):
        result = self._convert('"rank" <= 5')
        self.assertEqual(result, ["<=", ["get", "rank"], 5.0])

    def test_not_equal_string_value(self):
        result = self._convert('"status" != \'closed\'')
        self.assertEqual(result, ["!=", ["get", "status"], "closed"])

    def test_is_not_null(self):
        result = self._convert('"name" IS NOT NULL')
        self.assertEqual(result, ["has", "name"])

    def test_is_null(self):
        result = self._convert('"name" IS NULL')
        self.assertEqual(result, ["!", ["has", "name"]])

    def test_is_not_null_case_insensitive(self):
        result = self._convert('"name" is not null')
        self.assertEqual(result, ["has", "name"])

    def test_is_null_case_insensitive(self):
        result = self._convert('"name" is null')
        self.assertEqual(result, ["!", ["has", "name"]])

    def test_negative_number(self):
        result = self._convert('"elevation" > -100')
        self.assertEqual(result, [">", ["get", "elevation"], -100.0])

    def test_complex_and_expression_returns_none(self):
        result = self._convert('"a" = 1 AND "b" = 2')
        self.assertIsNone(result)

    def test_field_name_with_underscore(self):
        result = self._convert('"my_field" = \'val\'')
        self.assertEqual(result, ["==", ["get", "my_field"], "val"])

    def test_result_is_list_for_valid_expression(self):
        result = self._convert('"type" = \'road\'')
        self.assertIsInstance(result, list)

    def test_get_expression_is_list_with_field_name(self):
        result = self._convert('"type" = \'road\'')
        self.assertEqual(result[1], ["get", "type"])


class TestCategorizedMatchExpression(unittest.TestCase):
    """Test match-expression structure from _convert_categorized.

    Patches QgsSimpleFillSymbolLayer with a real Python class so that
    isinstance() checks inside _convert_categorized work without QGIS.
    """

    # Real Python class used as the patched symbol-layer type
    class _FakeFillSL:
        def __init__(self, fill_hex="#ff0000", stroke_hex="#000000", alpha=1.0):
            self._fill_hex = fill_hex
            self._stroke_hex = stroke_hex
            self._alpha = alpha

        def fillColor(self):
            from unittest.mock import MagicMock
            c = MagicMock()
            c.name.return_value = self._fill_hex
            c.alphaF.return_value = self._alpha
            return c

        def strokeColor(self):
            from unittest.mock import MagicMock
            c = MagicMock()
            c.name.return_value = self._stroke_hex
            c.alphaF.return_value = 1.0
            return c

    def _make_symbol(self, sl):
        from unittest.mock import MagicMock
        sym = MagicMock()
        sym.symbolLayerCount.return_value = 1
        sym.symbolLayer.return_value = sl
        return sym

    def _make_category(self, value, sl, active=True):
        from unittest.mock import MagicMock
        cat = MagicMock()
        cat.renderState.return_value = active
        cat.value.return_value = value
        cat.symbol.return_value = self._make_symbol(sl)
        return cat

    def _make_layer(self, attr, categories):
        from unittest.mock import MagicMock
        renderer = MagicMock()
        renderer.classAttribute.return_value = attr
        renderer.categories.return_value = categories
        layer = MagicMock()
        layer.name.return_value = "test_layer"
        layer.geometryType.return_value = 2  # Polygon
        layer.renderer.return_value = renderer
        return layer

    def _convert(self, layer):
        from unittest.mock import patch
        import style_converter as sc
        from style_converter import StyleConverter
        c = StyleConverter([], {})
        c._layer_counter = {}
        c._single_file = True
        with patch.object(sc, "QgsSimpleFillSymbolLayer", self._FakeFillSL):
            return c._convert_categorized(
                layer, layer.renderer(), "test_layer", 2, "mapsplat"
            )

    def test_null_category_uses_coalesce_sentinel_as_match_input(self):
        """Null-value categories must use coalesce(get(attr), '__null__') as match input."""
        null_cat = self._make_category(None, self._FakeFillSL())
        layer = self._make_layer("type", [null_cat])
        result = self._convert(layer)
        fill_expr = result[0]["paint"]["fill-color"]
        # ["match", <input>, "__null__", <color>, <fallback>]
        match_input = fill_expr[1]
        self.assertEqual(match_input, ["coalesce", ["get", "type"], "__null__"])

    def test_null_category_color_keyed_under_sentinel(self):
        """Null category fill color appears in the match expression under '__null__'."""
        null_cat = self._make_category(None, self._FakeFillSL(fill_hex="#aabbcc"))
        layer = self._make_layer("type", [null_cat])
        result = self._convert(layer)
        fill_expr = result[0]["paint"]["fill-color"]
        self.assertIn("__null__", fill_expr)
        idx = fill_expr.index("__null__")
        self.assertEqual(fill_expr[idx + 1], "#aabbcc")

    def test_regular_category_uses_bare_get_as_match_input(self):
        """Regular-value categories use bare ['get', attr] — no coalesce."""
        cat = self._make_category("road", self._FakeFillSL())
        layer = self._make_layer("type", [cat])
        result = self._convert(layer)
        fill_expr = result[0]["paint"]["fill-color"]
        self.assertEqual(fill_expr[1], ["get", "type"])

    def test_catchall_category_becomes_match_fallback(self):
        """Catch-all category (value == '') is the final fallback in the match expression."""
        regular = self._make_category("road", self._FakeFillSL(fill_hex="#111111"))
        catchall = self._make_category("", self._FakeFillSL(fill_hex="#999999"))
        layer = self._make_layer("type", [regular, catchall])
        result = self._convert(layer)
        fill_expr = result[0]["paint"]["fill-color"]
        # Last element of match expression is the fallback
        self.assertEqual(fill_expr[-1], "#999999")

    def test_no_catchall_gives_unmatched_features_zero_opacity(self):
        """Without a catch-all, the opacity fallback must be 0 (hidden)."""
        cat = self._make_category("road", self._FakeFillSL())
        layer = self._make_layer("type", [cat])
        result = self._convert(layer)
        opacity_expr = result[0]["paint"]["fill-opacity"]
        self.assertEqual(opacity_expr[-1], 0.0)

    def test_inactive_categories_are_excluded(self):
        """Categories with renderState=False must not appear in the match expression."""
        active = self._make_category("road", self._FakeFillSL(fill_hex="#ff0000"))
        inactive = self._make_category("rail", self._FakeFillSL(fill_hex="#0000ff"), active=False)
        layer = self._make_layer("type", [active, inactive])
        result = self._convert(layer)
        fill_expr = result[0]["paint"]["fill-color"]
        self.assertNotIn("#0000ff", fill_expr)

    def test_output_is_fill_layer(self):
        cat = self._make_category("road", self._FakeFillSL())
        layer = self._make_layer("type", [cat])
        result = self._convert(layer)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "fill")

    def test_output_references_correct_source_layer(self):
        cat = self._make_category("road", self._FakeFillSL())
        layer = self._make_layer("type", [cat])
        result = self._convert(layer)
        self.assertEqual(result[0]["source-layer"], "test_layer")


class TestGraduatedInterpolateExpression(unittest.TestCase):
    """Test interpolate-expression structure from _convert_graduated (polygon case).

    Patches QgsSimpleFillSymbolLayer with a real Python class so isinstance works.
    """

    class _FakeFillSL:
        def __init__(self, fill_hex="#ff0000", alpha=1.0):
            self._fill_hex = fill_hex
            self._alpha = alpha

        def fillColor(self):
            from unittest.mock import MagicMock
            c = MagicMock()
            c.name.return_value = self._fill_hex
            c.alphaF.return_value = self._alpha
            return c

    def _make_range(self, lower, color_hex, upper=None):
        from unittest.mock import MagicMock
        sl = self._FakeFillSL(fill_hex=color_hex)
        sym = MagicMock()
        sym.symbolLayerCount.return_value = 1
        sym.symbolLayer.return_value = sl
        r = MagicMock()
        r.lowerValue.return_value = lower
        r.upperValue.return_value = upper if upper is not None else lower + 100
        r.symbol.return_value = sym
        return r

    def _make_layer(self, attr, ranges):
        from unittest.mock import MagicMock
        renderer = MagicMock()
        renderer.classAttribute.return_value = attr
        renderer.ranges.return_value = ranges
        layer = MagicMock()
        layer.name.return_value = "pop_layer"
        layer.geometryType.return_value = 2
        layer.renderer.return_value = renderer
        return layer

    def _convert(self, layer):
        from unittest.mock import patch
        import style_converter as sc
        from style_converter import StyleConverter
        c = StyleConverter([], {})
        c._layer_counter = {}
        c._single_file = True
        with patch.object(sc, "QgsSimpleFillSymbolLayer", self._FakeFillSL):
            return c._convert_graduated(
                layer, layer.renderer(), "pop_layer", 2, "mapsplat"
            )

    def test_output_is_fill_type(self):
        ranges = [self._make_range(0, "#aaaaaa"), self._make_range(100, "#333333")]
        result = self._convert(self._make_layer("pop", ranges))
        self.assertEqual(result[0]["type"], "fill")

    def test_fill_color_is_interpolate_expression(self):
        ranges = [self._make_range(0, "#aaaaaa", upper=100), self._make_range(100, "#333333", upper=200)]
        result = self._convert(self._make_layer("pop", ranges))
        fill_expr = result[0]["paint"]["fill-color"]
        self.assertIsInstance(fill_expr, list)
        self.assertEqual(fill_expr[0], "interpolate")

    def test_interpolate_uses_linear_and_get(self):
        ranges = [self._make_range(0, "#aaaaaa", upper=100), self._make_range(100, "#333333", upper=200)]
        result = self._convert(self._make_layer("pop", ranges))
        fill_expr = result[0]["paint"]["fill-color"]
        # ["interpolate", ["linear"], ["get", attr], stop1, val1, ...]
        self.assertEqual(fill_expr[1], ["linear"])
        self.assertEqual(fill_expr[2], ["get", "pop"])

    def test_first_stop_at_lower_value(self):
        ranges = [self._make_range(0, "#aaaaaa", upper=100), self._make_range(100, "#333333", upper=200)]
        result = self._convert(self._make_layer("pop", ranges))
        fill_expr = result[0]["paint"]["fill-color"]
        # Index 3 is first stop (lowerValue of first range), index 4 is its color
        self.assertEqual(fill_expr[3], 0)
        self.assertEqual(fill_expr[4], "#aaaaaa")

    def test_capping_stop_at_upper_value(self):
        ranges = [self._make_range(0, "#aaaaaa", upper=100), self._make_range(100, "#333333", upper=200)]
        result = self._convert(self._make_layer("pop", ranges))
        fill_expr = result[0]["paint"]["fill-color"]
        # Last two entries: capping stop at upperValue of last range with last range color
        self.assertEqual(fill_expr[-2], 200)
        self.assertEqual(fill_expr[-1], "#333333")

    def test_empty_ranges_produces_default_style(self):
        from unittest.mock import MagicMock
        layer = self._make_layer("pop", [])
        result = self._convert(layer)
        # Falls back to default fill style — should not raise and must return a list
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)


def _make_mock_color(hex_val, r, g, b, alpha=1.0):
    """Helper: build a mock QColor with the given properties."""
    from unittest.mock import MagicMock
    c = MagicMock()
    c.name.return_value = hex_val
    c.isValid.return_value = True
    c.red.return_value = r
    c.green.return_value = g
    c.blue.return_value = b
    c.alphaF.return_value = alpha
    return c


class TestExtractDarkestColor(unittest.TestCase):
    """Test _extract_darkest_color() — pure Python, no QGIS types needed."""

    def _call(self, sym_layer):
        from style_converter import StyleConverter
        return StyleConverter([], {})._extract_darkest_color(sym_layer)

    def test_returns_none_when_no_color_methods(self):
        class _NoColor:
            pass
        self.assertIsNone(self._call(_NoColor()))

    def test_returns_color_when_only_color_accessor_present(self):
        class _HasColor:
            def color(self):
                return _make_mock_color("#336699", 51, 102, 153)
        self.assertEqual(self._call(_HasColor()), "#336699")

    def test_picks_darkest_of_two_colors(self):
        class _TwoColors:
            def color(self):
                return _make_mock_color("#888888", 136, 136, 136)  # mid-gray
            def color2(self):
                return _make_mock_color("#ffffff", 255, 255, 255)  # white
        self.assertEqual(self._call(_TwoColors()), "#888888")

    def test_ignores_invalid_color(self):
        from unittest.mock import MagicMock
        invalid = MagicMock()
        invalid.isValid.return_value = False

        class _Mixed:
            def color(self):
                return invalid
            def fillColor(self):
                return _make_mock_color("#112233", 17, 34, 51)
        self.assertEqual(self._call(_Mixed()), "#112233")

    def test_black_beats_gray(self):
        class _BlackAndGray:
            def color(self):
                return _make_mock_color("#000000", 0, 0, 0)
            def color2(self):
                return _make_mock_color("#aaaaaa", 170, 170, 170)
        self.assertEqual(self._call(_BlackAndGray()), "#000000")


class TestUnsupportedFillFallback(unittest.TestCase):
    """Unsupported fill symbol layer types (e.g. gradient) should not return None.

    Instead they should produce a fill layer using the darkest available color,
    never the hardcoded default blue.
    """

    class _FakeFillSL:    pass     # stands in for QgsSimpleFillSymbolLayer
    class _FakeLinePat:  pass     # stands in for QgsLinePatternFillSymbolLayer
    class _FakePointPat: pass     # stands in for QgsPointPatternFillSymbolLayer

    class _FakeGradientSL:
        """Gray-to-white gradient — neither _FakeFillSL nor a pattern."""
        def color(self):
            return _make_mock_color("#888888", 136, 136, 136)   # gray (start)
        def color2(self):
            return _make_mock_color("#ffffff", 255, 255, 255)   # white (end)

    def _call(self, sym_layer):
        from unittest.mock import patch
        import style_converter as sc
        from style_converter import StyleConverter
        c = StyleConverter([], {})
        with patch.object(sc, "QgsSimpleFillSymbolLayer", self._FakeFillSL), \
             patch.object(sc, "QgsLinePatternFillSymbolLayer", self._FakeLinePat), \
             patch.object(sc, "QgsPointPatternFillSymbolLayer", self._FakePointPat):
            return c._fill_symbol_layer_to_maplibre(
                sym_layer, "test_layer", "source_layer", "mapsplat"
            )

    def test_unsupported_fill_returns_a_layer_not_none(self):
        result = self._call(self._FakeGradientSL())
        self.assertIsNotNone(result)

    def test_unsupported_fill_returns_fill_type(self):
        result = self._call(self._FakeGradientSL())
        self.assertEqual(result["type"], "fill")

    def test_unsupported_fill_does_not_use_default_blue(self):
        result = self._call(self._FakeGradientSL())
        self.assertNotEqual(result["paint"]["fill-color"], "#3388ff")

    def test_unsupported_fill_uses_darkest_of_available_colors(self):
        # Gray (#888888) is darker than white (#ffffff)
        result = self._call(self._FakeGradientSL())
        self.assertEqual(result["paint"]["fill-color"], "#888888")


class TestUnsupportedLineFallback(unittest.TestCase):
    """Unsupported line symbol layer types should produce a line layer, not None."""

    class _FakeLineSL: pass   # stands in for QgsSimpleLineSymbolLayer

    class _FakeArrowSL:
        """Simulates an arrow line symbol layer with a color."""
        def color(self):
            return _make_mock_color("#442200", 68, 34, 0)   # dark brown

    def _call(self, sym_layer):
        from unittest.mock import patch
        import style_converter as sc
        from style_converter import StyleConverter
        c = StyleConverter([], {})
        with patch.object(sc, "QgsSimpleLineSymbolLayer", self._FakeLineSL):
            return c._line_symbol_layer_to_maplibre(
                sym_layer, "test_layer", "source_layer", "mapsplat"
            )

    def test_unsupported_line_returns_a_layer_not_none(self):
        result = self._call(self._FakeArrowSL())
        self.assertIsNotNone(result)

    def test_unsupported_line_returns_line_type(self):
        result = self._call(self._FakeArrowSL())
        self.assertEqual(result["type"], "line")

    def test_unsupported_line_uses_extracted_color(self):
        result = self._call(self._FakeArrowSL())
        self.assertEqual(result["paint"]["line-color"], "#442200")


class TestUnsupportedMarkerFallback(unittest.TestCase):
    """Unsupported marker symbol layer types should produce a circle layer, not None."""

    class _FakeSimpleMarker:   pass   # QgsSimpleMarkerSymbolLayer
    class _FakeSvgMarker:      pass   # QgsSvgMarkerSymbolLayer
    class _FakeFontMarker:     pass   # QgsFontMarkerSymbolLayer

    class _FakeRasterMarkerSL:
        """Simulates a raster-image marker with a tint color."""
        def color(self):
            return _make_mock_color("#1a1a2e", 26, 26, 46)   # very dark blue

    def _call(self, sym_layer):
        from unittest.mock import patch
        import style_converter as sc
        from style_converter import StyleConverter
        c = StyleConverter([], {})
        with patch.object(sc, "QgsSimpleMarkerSymbolLayer", self._FakeSimpleMarker), \
             patch.object(sc, "QgsSvgMarkerSymbolLayer", self._FakeSvgMarker), \
             patch.object(sc, "QgsFontMarkerSymbolLayer", self._FakeFontMarker):
            return c._marker_symbol_layer_to_maplibre(
                sym_layer, "test_layer", "source_layer", "mapsplat"
            )

    def test_unsupported_marker_returns_a_layer_not_none(self):
        result = self._call(self._FakeRasterMarkerSL())
        self.assertIsNotNone(result)

    def test_unsupported_marker_returns_circle_type(self):
        result = self._call(self._FakeRasterMarkerSL())
        self.assertEqual(result["type"], "circle")

    def test_unsupported_marker_uses_extracted_color(self):
        result = self._call(self._FakeRasterMarkerSL())
        self.assertEqual(result["paint"]["circle-color"], "#1a1a2e")


class TestGraduatedLineInterpolateExpression(unittest.TestCase):
    """Test interpolate-expression structure from _convert_graduated (line case).

    Patches QgsSimpleLineSymbolLayer with a real Python class so isinstance works.
    """

    class _FakeLineSL:
        def __init__(self, color_hex="#0000ff", width_val=2.0):
            self._color_hex = color_hex
            self._width_val = width_val

        def color(self):
            from unittest.mock import MagicMock
            c = MagicMock()
            c.name.return_value = self._color_hex
            return c

        def width(self):
            return self._width_val

        def widthUnit(self):
            return 0  # RenderMillimeters

    def _make_range(self, lower, color_hex, width_val=2.0, upper=None):
        from unittest.mock import MagicMock
        sl = self._FakeLineSL(color_hex=color_hex, width_val=width_val)
        sym = MagicMock()
        sym.symbolLayerCount.return_value = 1
        sym.symbolLayer.return_value = sl
        r = MagicMock()
        r.lowerValue.return_value = lower
        r.upperValue.return_value = upper if upper is not None else lower + 100
        r.symbol.return_value = sym
        return r

    def _make_layer(self, attr, ranges):
        from unittest.mock import MagicMock
        renderer = MagicMock()
        renderer.classAttribute.return_value = attr
        renderer.ranges.return_value = ranges
        layer = MagicMock()
        layer.name.return_value = "road_layer"
        layer.geometryType.return_value = 1  # Line
        layer.renderer.return_value = renderer
        return layer

    def _convert(self, layer):
        from unittest.mock import patch
        import style_converter as sc
        from style_converter import StyleConverter
        c = StyleConverter([], {})
        c._layer_counter = {}
        c._single_file = True
        with patch.object(sc, "QgsSimpleLineSymbolLayer", self._FakeLineSL):
            return c._convert_graduated(
                layer, layer.renderer(), "road_layer", 1, "mapsplat"
            )

    def test_output_is_line_type(self):
        ranges = [self._make_range(0, "#0000ff", upper=50), self._make_range(50, "#ff0000", upper=100)]
        result = self._convert(self._make_layer("speed", ranges))
        self.assertEqual(result[0]["type"], "line")

    def test_line_color_is_interpolate_expression(self):
        ranges = [self._make_range(0, "#0000ff", upper=50), self._make_range(50, "#ff0000", upper=100)]
        result = self._convert(self._make_layer("speed", ranges))
        color_expr = result[0]["paint"]["line-color"]
        self.assertIsInstance(color_expr, list)
        self.assertEqual(color_expr[0], "interpolate")

    def test_line_width_is_interpolate_expression(self):
        ranges = [self._make_range(0, "#0000ff", width_val=1.0, upper=50),
                  self._make_range(50, "#ff0000", width_val=3.0, upper=100)]
        result = self._convert(self._make_layer("speed", ranges))
        width_expr = result[0]["paint"]["line-width"]
        self.assertIsInstance(width_expr, list)
        self.assertEqual(width_expr[0], "interpolate")

    def test_line_interpolate_structure(self):
        ranges = [self._make_range(0, "#0000ff", upper=50), self._make_range(50, "#ff0000", upper=100)]
        result = self._convert(self._make_layer("speed", ranges))
        color_expr = result[0]["paint"]["line-color"]
        self.assertEqual(color_expr[1], ["linear"])
        self.assertEqual(color_expr[2], ["get", "speed"])

    def test_line_capping_stop(self):
        ranges = [self._make_range(0, "#0000ff", upper=50), self._make_range(50, "#ff0000", upper=100)]
        result = self._convert(self._make_layer("speed", ranges))
        color_expr = result[0]["paint"]["line-color"]
        self.assertEqual(color_expr[-2], 100)
        self.assertEqual(color_expr[-1], "#ff0000")


class TestGraduatedPointInterpolateExpression(unittest.TestCase):
    """Test interpolate-expression structure from _convert_graduated (point case).

    Patches QgsSimpleMarkerSymbolLayer with a real Python class so isinstance works.
    """

    class _FakeMarkerSL:
        def __init__(self, color_hex="#00ff00", size_val=4.0):
            self._color_hex = color_hex
            self._size_val = size_val

        def fillColor(self):
            from unittest.mock import MagicMock
            c = MagicMock()
            c.name.return_value = self._color_hex
            return c

        def size(self):
            return self._size_val

        def sizeUnit(self):
            return 0  # RenderMillimeters

    def _make_range(self, lower, color_hex, size_val=4.0, upper=None):
        from unittest.mock import MagicMock
        sl = self._FakeMarkerSL(color_hex=color_hex, size_val=size_val)
        sym = MagicMock()
        sym.symbolLayerCount.return_value = 1
        sym.symbolLayer.return_value = sl
        r = MagicMock()
        r.lowerValue.return_value = lower
        r.upperValue.return_value = upper if upper is not None else lower + 100
        r.symbol.return_value = sym
        return r

    def _make_layer(self, attr, ranges):
        from unittest.mock import MagicMock
        renderer = MagicMock()
        renderer.classAttribute.return_value = attr
        renderer.ranges.return_value = ranges
        layer = MagicMock()
        layer.name.return_value = "city_layer"
        layer.geometryType.return_value = 0  # Point
        layer.renderer.return_value = renderer
        return layer

    def _convert(self, layer):
        from unittest.mock import patch
        import style_converter as sc
        from style_converter import StyleConverter
        c = StyleConverter([], {})
        c._layer_counter = {}
        c._single_file = True
        with patch.object(sc, "QgsSimpleMarkerSymbolLayer", self._FakeMarkerSL):
            return c._convert_graduated(
                layer, layer.renderer(), "city_layer", 0, "mapsplat"
            )

    def test_output_is_circle_type(self):
        ranges = [self._make_range(0, "#00ff00", upper=500), self._make_range(500, "#ff0000", upper=1000)]
        result = self._convert(self._make_layer("population", ranges))
        self.assertEqual(result[0]["type"], "circle")

    def test_circle_color_is_interpolate_expression(self):
        ranges = [self._make_range(0, "#00ff00", upper=500), self._make_range(500, "#ff0000", upper=1000)]
        result = self._convert(self._make_layer("population", ranges))
        color_expr = result[0]["paint"]["circle-color"]
        self.assertIsInstance(color_expr, list)
        self.assertEqual(color_expr[0], "interpolate")

    def test_circle_radius_is_interpolate_expression(self):
        ranges = [self._make_range(0, "#00ff00", size_val=4.0, upper=500),
                  self._make_range(500, "#ff0000", size_val=8.0, upper=1000)]
        result = self._convert(self._make_layer("population", ranges))
        radius_expr = result[0]["paint"]["circle-radius"]
        self.assertIsInstance(radius_expr, list)
        self.assertEqual(radius_expr[0], "interpolate")

    def test_circle_interpolate_structure(self):
        ranges = [self._make_range(0, "#00ff00", upper=500), self._make_range(500, "#ff0000", upper=1000)]
        result = self._convert(self._make_layer("population", ranges))
        color_expr = result[0]["paint"]["circle-color"]
        self.assertEqual(color_expr[1], ["linear"])
        self.assertEqual(color_expr[2], ["get", "population"])

    def test_circle_capping_stop(self):
        ranges = [self._make_range(0, "#00ff00", upper=500), self._make_range(500, "#ff0000", upper=1000)]
        result = self._convert(self._make_layer("population", ranges))
        color_expr = result[0]["paint"]["circle-color"]
        self.assertEqual(color_expr[-2], 1000)
        self.assertEqual(color_expr[-1], "#ff0000")


class TestScaleToZoom(unittest.TestCase):
    """Test _scale_to_zoom() scale-denominator → zoom conversion."""

    def setUp(self):
        from style_converter import StyleConverter
        self.sc = StyleConverter([], {})

    def test_zero_returns_none(self):
        self.assertIsNone(self.sc._scale_to_zoom(0))

    def test_negative_returns_none(self):
        self.assertIsNone(self.sc._scale_to_zoom(-100))

    def test_zoom_0_scale(self):
        # Denominator ~279,541,132 (512-tile constant) should give zoom ≈ 0
        zoom = self.sc._scale_to_zoom(279541132.014)
        self.assertAlmostEqual(zoom, 0.0, places=1)

    def test_zoom_10_scale(self):
        # Denominator = 279541132 / 2^10
        denom = 279541132.014 / (2 ** 10)
        zoom = self.sc._scale_to_zoom(denom)
        self.assertAlmostEqual(zoom, 10.0, places=1)

    def test_zoom_14_scale(self):
        denom = 279541132.014 / (2 ** 14)
        zoom = self.sc._scale_to_zoom(denom)
        self.assertAlmostEqual(zoom, 14.0, places=1)

    def test_clamped_to_zero(self):
        # Extremely small scale (huge denominator) clamps to 0
        zoom = self.sc._scale_to_zoom(1e12)
        self.assertEqual(zoom, 0.0)

    def test_clamped_to_24(self):
        # Extremely large scale (tiny denominator) clamps to 24
        zoom = self.sc._scale_to_zoom(0.001)
        self.assertEqual(zoom, 24.0)

    def test_returns_float(self):
        zoom = self.sc._scale_to_zoom(50000)
        self.assertIsInstance(zoom, float)


class TestGetZoomRange(unittest.TestCase):
    """Test _get_zoom_range() using mock layers."""

    def _make_layer(self, has_scale_vis, min_scale=0, max_scale=0):
        from unittest.mock import MagicMock
        layer = MagicMock()
        layer.hasScaleBasedVisibility.return_value = has_scale_vis
        layer.minimumScale.return_value = min_scale
        layer.maximumScale.return_value = max_scale
        return layer

    def setUp(self):
        from style_converter import StyleConverter
        self.sc = StyleConverter([], {})

    def test_no_scale_vis_returns_none_none(self):
        layer = self._make_layer(False)
        self.assertEqual(self.sc._get_zoom_range(layer), (None, None))

    def test_scale_vis_both_limits(self):
        # minimumScale (zoomed-out limit) = 500000 → small zoom (minzoom)
        # maximumScale (zoomed-in limit)  = 1000   → large zoom (maxzoom)
        layer = self._make_layer(True, min_scale=500000, max_scale=1000)
        minzoom, maxzoom = self.sc._get_zoom_range(layer)
        self.assertIsNotNone(minzoom)
        self.assertIsNotNone(maxzoom)
        self.assertLess(minzoom, maxzoom)

    def test_scale_vis_zero_min_gives_none_minzoom(self):
        # minimumScale = 0 means no zoomed-out limit
        layer = self._make_layer(True, min_scale=0, max_scale=1000)
        minzoom, maxzoom = self.sc._get_zoom_range(layer)
        self.assertIsNone(minzoom)
        self.assertIsNotNone(maxzoom)

    def test_scale_vis_zero_max_gives_none_maxzoom(self):
        # maximumScale = 0 means no zoomed-in limit
        layer = self._make_layer(True, min_scale=500000, max_scale=0)
        minzoom, maxzoom = self.sc._get_zoom_range(layer)
        self.assertIsNotNone(minzoom)
        self.assertIsNone(maxzoom)

    def test_minzoom_less_than_maxzoom_for_typical_range(self):
        # 1:500 000 (zoomed out) → small zoom; 1:5 000 (zoomed in) → large zoom
        layer = self._make_layer(True, min_scale=500000, max_scale=5000)
        minzoom, maxzoom = self.sc._get_zoom_range(layer)
        self.assertLess(minzoom, maxzoom)


if __name__ == "__main__":
    unittest.main()
