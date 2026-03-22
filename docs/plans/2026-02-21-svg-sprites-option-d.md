# SVG Sprite Rendering — Option D Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** For point layers using `QgsSingleSymbolRenderer` + `QgsSvgMarkerSymbolLayer`, render the SVG icon to a raster sprite atlas and emit a MapLibre `symbol` layer. All other point marker types (simple shapes, categorized/graduated SVG, font markers) keep their existing `circle` fallback.

**Architecture:** Two-phase approach in `StyleConverter.convert()`: (1) pre-scan layers to identify SVG single-symbol candidates and generate `sprites.png` + `sprites.json` in the output directory; (2) convert styles, emitting `symbol` layers for pre-rendered sprites and `circle` for everything else. Basemap overlay mode uses MapLibre 4.x multi-sprite array format so basemap and business sprites coexist cleanly.

**Tech Stack:** PyQGIS (`QgsSvgMarkerSymbolLayer`, `QgsApplication.svgCache()`, `QImage`, `QPainter`), MapLibre GL JS sprite format (PNG atlas + JSON manifest), Python `json`, `os` modules.

---

## Background: Test Pattern

Existing tests in `test/test_style_converter.py` never import `exporter.py` (which has QGIS top-level imports). For logic that lives in the exporter, tests replicate the algorithm inline (see `_run_merge()` in `TestMergeBusinessIntoBasemap`). Follow this pattern for new exporter logic tests.

The `StyleConverter` class can be imported directly in tests because its methods under test are pure Python (no QGIS calls at instantiation time).

---

## Task 1: Add `_compute_sprite_layout()` with tests

Pure-Python helper: given a dict of `{name: (width, height)}`, returns layout offsets for a single-row atlas plus total atlas dimensions. No QGIS dependency.

**Files:**
- Modify: `style_converter.py`
- Modify: `test/test_style_converter.py`

**Step 1: Write the failing test**

Add at the end of `test/test_style_converter.py` (before `if __name__ == "__main__":`):

```python
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
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest test/test_style_converter.py::TestComputeSpriteLayout -v
```

Expected: `AttributeError: 'StyleConverter' object has no attribute '_compute_sprite_layout'`

**Step 3: Add `import os` and implement `_compute_sprite_layout()`**

At the top of `style_converter.py`, add `import os` after the existing imports (around line 16, after `from qgis.core import ...`).

Add the method after `_sanitize_name()` (around line 856):

```python
def _compute_sprite_layout(self, sprite_sizes):
    """Compute x/y offsets for a single-row sprite atlas.

    :param sprite_sizes: dict mapping name -> (width, height) in pixels
    :returns: (manifest_dict, total_width, total_height)
              manifest_dict maps name -> {"x", "y", "width", "height", "pixelRatio"}
    """
    manifest = {}
    x = 0
    max_height = 0
    for name, (w, h) in sprite_sizes.items():
        manifest[name] = {
            "x": x,
            "y": 0,
            "width": w,
            "height": h,
            "pixelRatio": 1,
        }
        x += w
        max_height = max(max_height, h)
    return manifest, x, max_height
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest test/test_style_converter.py::TestComputeSpriteLayout -v
```

Expected: 5 PASS

**Step 5: Run all tests to confirm nothing broken**

```bash
python -m pytest test/ -v
```

Expected: All existing tests pass

**Step 6: Commit**

```bash
git add style_converter.py test/test_style_converter.py
git commit -m "feat: add _compute_sprite_layout() with tests"
```

---

## Task 2: Add `_build_symbol_layer_for_sprite()` and update the SVG marker branch

Pure-Python helper that constructs a MapLibre `symbol` layer dict for a sprite icon. Then wire it into `_marker_symbol_layer_to_maplibre()` so SVG layers with a pre-rendered sprite get a `symbol` layer instead of a `circle`.

**Files:**
- Modify: `style_converter.py`
- Modify: `test/test_style_converter.py`

**Step 1: Write the failing test**

Add after `TestComputeSpriteLayout` in `test/test_style_converter.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest test/test_style_converter.py::TestBuildSymbolLayerForSprite -v
```

Expected: `AttributeError: 'StyleConverter' object has no attribute '_build_symbol_layer_for_sprite'`

**Step 3: Implement `_build_symbol_layer_for_sprite()` in `style_converter.py`**

Add after `_marker_symbol_layer_to_maplibre()`:

```python
def _build_symbol_layer_for_sprite(self, layer_id, sprite_key, source_name, source_layer, size_px):
    """Build a MapLibre symbol layer referencing a pre-rendered sprite entry.

    :param layer_id: MapLibre layer ID string
    :param sprite_key: Key in the sprite manifest (sprites.json)
    :param source_name: PMTiles source name in the style
    :param source_layer: Source-layer name in PMTiles
    :param size_px: Original icon size in pixels (unused for now; kept for future icon-size scaling)
    :returns: MapLibre layer dict with type "symbol"
    """
    return {
        "id": layer_id,
        "type": "symbol",
        "source": source_name,
        "source-layer": source_layer,
        "layout": {
            "icon-image": sprite_key,
            "icon-size": 1.0,
            "icon-allow-overlap": True,
            "icon-ignore-placement": True,
        },
    }
```

**Step 4: Update the SVG branch of `_marker_symbol_layer_to_maplibre()`**

Replace the existing `elif isinstance(sym_layer, QgsSvgMarkerSymbolLayer):` block (lines ~424-440 in `style_converter.py`) with:

```python
elif isinstance(sym_layer, QgsSvgMarkerSymbolLayer):
    sprite_key = getattr(self, '_svg_sprite_map', {}).get(source_layer)
    size = self._convert_size(sym_layer.size(), sym_layer.sizeUnit())
    if sprite_key:
        # Single-symbol SVG with a pre-rendered sprite — emit symbol layer
        return self._build_symbol_layer_for_sprite(
            layer_id, sprite_key, source_name, source_layer, size
        )
    # Categorized/graduated SVG, or sprite generation failed — circle fallback
    self._log(
        f"Layer '{source_layer}': SVG marker approximated as circle "
        "(sprite only generated for single-symbol renderers)"
    )
    fill_color = sym_layer.fillColor() if hasattr(sym_layer, 'fillColor') else None
    return {
        "id": layer_id,
        "type": "circle",
        "source": source_name,
        "source-layer": source_layer,
        "paint": {
            "circle-color": fill_color.name() if fill_color else self.DEFAULT_POINT_COLOR,
            "circle-radius": max(2, size / 2),
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 1,
        },
    }
```

**Step 5: Run test to verify it passes**

```bash
python -m pytest test/test_style_converter.py::TestBuildSymbolLayerForSprite -v
```

Expected: 6 PASS

**Step 6: Run all tests**

```bash
python -m pytest test/ -v
```

Expected: All existing tests pass

**Step 7: Commit**

```bash
git add style_converter.py test/test_style_converter.py
git commit -m "feat: add _build_symbol_layer_for_sprite(), wire into SVG marker branch"
```

---

## Task 3: Add QGIS-dependent sprite generation methods

These methods call QGIS APIs and cannot be unit-tested. Manual testing is required inside QGIS.

**Files:**
- Modify: `style_converter.py`

**Step 1: Update `__init__()` to accept a log callback**

Replace the existing `__init__` signature and body:

```python
def __init__(self, layers, settings, log_callback=None):
    """Initialize converter.

    :param layers: List of QgsVectorLayer
    :param settings: Export settings dictionary
    :param log_callback: Optional callable(message: str) for logging; called during sprite generation
    """
    self.layers = layers
    self.settings = settings
    self._layer_counter = {}
    self._log_callback = log_callback
    self._svg_sprite_map = {}  # populated by _generate_sprites(); {source_layer: sprite_key}
```

**Step 2: Add `_log()` helper** (add before `_compute_sprite_layout`):

```python
def _log(self, message):
    """Emit a log message via callback if one was provided."""
    if self._log_callback:
        self._log_callback(message)
```

**Step 3: Add `_is_svg_single_symbol()` detection** (add before `_log`):

```python
def _is_svg_single_symbol(self, layer):
    """Return True if a layer uses a single-symbol renderer with an SVG marker.

    :param layer: QgsVectorLayer
    :returns: bool
    """
    renderer = layer.renderer()
    if not isinstance(renderer, QgsSingleSymbolRenderer):
        return False
    symbol = renderer.symbol()
    if symbol is None or symbol.symbolLayerCount() == 0:
        return False
    return isinstance(symbol.symbolLayer(0), QgsSvgMarkerSymbolLayer)
```

**Step 4: Add `_render_svg_to_qimage()`** (add after `_is_svg_single_symbol`):

```python
def _render_svg_to_qimage(self, svg_path, size_px, fill_color, stroke_color, stroke_width_px):
    """Rasterize an SVG marker via the QGIS SVG cache.

    :param svg_path: Absolute path to SVG file (or QGIS resource path)
    :param size_px: Output image dimension in pixels (square)
    :param fill_color: QColor for SVG fill
    :param stroke_color: QColor for SVG stroke
    :param stroke_width_px: Stroke width in pixels
    :returns: QImage on success, None on failure
    """
    try:
        from qgis.core import QgsApplication
        cache = QgsApplication.svgCache()
        img, success = cache.svgAsImage(
            svg_path,
            float(size_px),
            fill_color,
            stroke_color,
            float(stroke_width_px),
            1.0,  # widthScaleFactor
        )
        if success and not img.isNull():
            return img
        # Retry without color substitution (some SVGs ignore fill/stroke params)
        img, success = cache.svgAsImage(svg_path, float(size_px), fill_color, stroke_color, 0.0, 1.0)
        if success and not img.isNull():
            return img
        return None
    except Exception as e:
        self._log(f"SVG render failed for '{svg_path}': {e}")
        return None
```

**Step 5: Add `_generate_sprites()` orchestrator** (add after `_render_svg_to_qimage`):

```python
def _generate_sprites(self, output_dir):
    """Render SVG single-symbol point layers to a sprite atlas.

    Writes sprites.png and sprites.json to output_dir.
    Populates self._svg_sprite_map with {source_layer_name: sprite_key} for
    each layer successfully rendered.

    :param output_dir: Directory to write sprite files (same level as index.html)
    :returns: True if at least one sprite was generated
    """
    import json as _json
    from qgis.PyQt.QtGui import QImage, QPainter
    from qgis.PyQt.QtCore import Qt

    images = {}
    for layer in self.layers:
        if layer.geometryType() != 0:  # points only
            continue
        if not self._is_svg_single_symbol(layer):
            continue

        renderer = layer.renderer()
        symbol = renderer.symbol()
        sym_layer = symbol.symbolLayer(0)

        svg_path = sym_layer.path()
        size_px = max(16, int(self._convert_size(sym_layer.size(), sym_layer.sizeUnit())))

        img = self._render_svg_to_qimage(
            svg_path,
            size_px,
            sym_layer.fillColor(),
            sym_layer.strokeColor(),
            self._convert_size(sym_layer.strokeWidth(), sym_layer.strokeWidthUnit()),
        )

        source_layer = self._sanitize_name(layer.name())
        if img and not img.isNull():
            images[source_layer] = img
            self._svg_sprite_map[source_layer] = source_layer
            self._log(f"Rendered sprite for '{layer.name()}' ({size_px}px)")
        else:
            self._log(f"Warning: could not render SVG for '{layer.name()}', using circle fallback")

    if not images:
        return False

    # Compute atlas layout
    sizes = {name: (img.width(), img.height()) for name, img in images.items()}
    manifest, total_w, total_h = self._compute_sprite_layout(sizes)

    # Compose atlas image
    atlas = QImage(max(total_w, 1), max(total_h, 1), QImage.Format_ARGB32)
    atlas.fill(Qt.transparent)
    painter = QPainter(atlas)
    for name, entry in manifest.items():
        painter.drawImage(entry["x"], entry["y"], images[name])
    painter.end()

    # Write sprites.png and sprites.json
    atlas_path = os.path.join(output_dir, "sprites.png")
    json_path = os.path.join(output_dir, "sprites.json")
    atlas.save(atlas_path)
    with open(json_path, "w", encoding="utf-8") as f:
        _json.dump(manifest, f, indent=2)

    self._log(f"Wrote sprite atlas: {len(images)} icon(s) → {atlas_path}")
    return True
```

**Step 6: No automated test. Manual test procedure:**

Inside QGIS after deploying the plugin:
1. Load a vector point layer with a custom SVG marker (single symbol renderer)
2. Run MapSplat export with that layer selected
3. Verify the output directory contains `sprites.png` and `sprites.json`
4. Open `sprites.json` — confirm it has one entry with correct `x`, `y`, `width`, `height` fields
5. Open the exported map in a browser (`python serve.py`) — the point should render as the SVG icon, not a circle

**Step 7: Commit**

```bash
git add style_converter.py
git commit -m "feat: add QGIS SVG sprite generation methods (_is_svg_single_symbol, _render_svg_to_qimage, _generate_sprites)"
```

---

## Task 4: Update `convert()` to generate sprites and add sprite key

Add `output_dir` parameter to `convert()`. Before converting layers, call `_generate_sprites()` to populate `self._svg_sprite_map`. Add `"sprite": "./sprites"` to the style if sprites were generated.

**Files:**
- Modify: `style_converter.py`

**Step 1: Update `convert()` signature and body**

Change the `convert` method signature from:

```python
def convert(self, single_file=True):
```

to:

```python
def convert(self, single_file=True, output_dir=None):
```

At the start of `convert()`, after `self._single_file = single_file`, add:

```python
    self._svg_sprite_map = {}  # reset for each convert() call

    # Pre-generate sprites for SVG single-symbol point layers
    has_sprites = False
    if output_dir:
        try:
            has_sprites = self._generate_sprites(output_dir)
        except Exception as e:
            self._log(f"Sprite generation skipped: {e}")
```

After building the `style` dict (after the `"layers": [{"id": "background", ...}]` section), add the sprite key:

```python
    if has_sprites:
        style["sprite"] = "./sprites"
```

The rest of `convert()` is unchanged (the layer loop, label loop, return).

**Step 2: No new test needed.** The `TestStyleConverterOutput.test_convert_empty_layers` and `test_convert_has_background_layer` tests pass because `output_dir=None` (default) skips sprite generation. Run them to confirm:

```bash
python -m pytest test/test_style_converter.py::TestStyleConverterOutput -v
```

Expected: 2 PASS

**Step 3: Run all tests**

```bash
python -m pytest test/ -v
```

Expected: All pass

**Step 4: Commit**

```bash
git add style_converter.py
git commit -m "feat: update convert() to accept output_dir and add sprite key to style"
```

---

## Task 5: Update `exporter.py` — pass `output_dir`, update log callback, handle multi-sprite basemap

**Files:**
- Modify: `exporter.py`
- Modify: `test/test_style_converter.py`

### Part A: Update `exporter.py`

**Step 1: Update `StyleConverter` instantiation in `_do_export()`**

Find this block (around line 189):

```python
        style_converter = StyleConverter(layers["vector"], self.settings)
        style_json = style_converter.convert(single_file=single_file)
```

Replace with:

```python
        style_converter = StyleConverter(
            layers["vector"],
            self.settings,
            log_callback=lambda msg: self.log_message.emit(msg, "info"),
        )
        style_json = style_converter.convert(
            single_file=single_file,
            output_dir=output_dir if not style_only else None,
        )
```

(`output_dir` is already defined earlier in `_do_export()` as the main export directory.)

**Step 2: Update `_merge_business_into_basemap()` for multi-sprite array format**

After the existing code that appends overlay layers, add sprite handling. The updated method body becomes (replace `_merge_business_into_basemap` entirely):

```python
def _merge_business_into_basemap(self, basemap_style_path, business_style_json):
    """Merge business layer sources and styles on top of a basemap style.

    The basemap's remote tile URL is replaced with the local extracted file.
    Business layer sources are injected and layers appended (background excluded).
    If both styles have sprites, uses MapLibre 4.x multi-sprite array format.

    :param basemap_style_path: Path to Protomaps basemap style.json
    :param business_style_json: Style dict generated from QGIS layers
    :returns: Merged style dictionary
    """
    try:
        with open(basemap_style_path, "r", encoding="utf-8") as f:
            basemap = json.load(f)
    except Exception as e:
        self.log_message.emit(f"Failed to load basemap style: {e}", "error")
        return business_style_json

    # Update basemap's vector tile source URL to point to local extracted file
    for src_name, src in basemap.get("sources", {}).items():
        if src.get("type") == "vector" and "protomaps" in src.get("url", ""):
            src["url"] = "pmtiles://data/basemap.pmtiles"
            self.log_message.emit(
                f"  Updated basemap source '{src_name}' to local file", "info"
            )
            break

    # Inject business data sources
    basemap.setdefault("sources", {}).update(business_style_json.get("sources", {}))

    # Append business layers, skipping background (basemap provides its own)
    overlay_layers = [
        layer for layer in business_style_json.get("layers", [])
        if layer.get("id") != "background"
    ]
    basemap.setdefault("layers", []).extend(overlay_layers)

    self.log_message.emit(
        f"  Merged {len(overlay_layers)} business layer(s) into basemap style", "info"
    )

    # Handle sprites — use MapLibre 4.x multi-sprite array when both styles have sprites
    business_sprite = business_style_json.get("sprite")
    basemap_sprite = basemap.get("sprite")

    if business_sprite and basemap_sprite:
        # Both have sprites: build multi-sprite array
        # Basemap sprite may already be an array (e.g. from a previous merge); handle both
        if isinstance(basemap_sprite, str):
            basemap["sprite"] = [
                {"id": "default", "url": basemap_sprite},
                {"id": "biz", "url": business_sprite},
            ]
        elif isinstance(basemap_sprite, list):
            # Append biz entry if not already present
            if not any(e.get("id") == "biz" for e in basemap_sprite):
                basemap_sprite.append({"id": "biz", "url": business_sprite})
        # Prefix all icon-image layout refs in business overlay layers with "biz:"
        for layer in overlay_layers:
            layout = layer.get("layout", {})
            if "icon-image" in layout and not str(layout["icon-image"]).startswith("biz:"):
                layout["icon-image"] = "biz:" + layout["icon-image"]
        self.log_message.emit("  Using multi-sprite array for basemap + business icons", "info")
    elif business_sprite and not basemap_sprite:
        # Only business has sprites — set directly
        basemap["sprite"] = business_sprite

    return basemap
```

### Part B: Test the multi-sprite merge logic

The test replicates the sprite-handling algorithm inline (same pattern as existing `_run_merge`).

**Step 3: Write failing test**

Add after `TestMergeBusinessIntoBasemap` in `test/test_style_converter.py`:

```python
class TestMultiSpriteBasemapMerge(unittest.TestCase):
    """Test sprite handling in basemap merge — pure Python logic, no QGIS import."""

    def _run_sprite_merge(self, basemap_sprite, business_sprite, overlay_layers=None):
        """Replicate the sprite-handling portion of _merge_business_into_basemap."""
        basemap = {"sources": {}, "layers": [], "sprite": basemap_sprite} if basemap_sprite else {"sources": {}, "layers": []}
        business = {"sources": {}, "layers": overlay_layers or [], "sprite": business_sprite} if business_sprite else {"sources": {}, "layers": overlay_layers or []}

        overlay = [l for l in business.get("layers", []) if l.get("id") != "background"]

        b_sprite = business.get("sprite")
        bm_sprite = basemap.get("sprite")

        if b_sprite and bm_sprite:
            if isinstance(bm_sprite, str):
                basemap["sprite"] = [
                    {"id": "default", "url": bm_sprite},
                    {"id": "biz", "url": b_sprite},
                ]
            elif isinstance(bm_sprite, list):
                if not any(e.get("id") == "biz" for e in bm_sprite):
                    bm_sprite.append({"id": "biz", "url": b_sprite})
            for layer in overlay:
                layout = layer.get("layout", {})
                if "icon-image" in layout and not str(layout["icon-image"]).startswith("biz:"):
                    layout["icon-image"] = "biz:" + layout["icon-image"]
        elif b_sprite and not bm_sprite:
            basemap["sprite"] = b_sprite

        return basemap

    def test_no_sprites_no_sprite_key(self):
        result = self._run_sprite_merge(None, None)
        self.assertNotIn("sprite", result)

    def test_only_business_sprite_sets_sprite_directly(self):
        result = self._run_sprite_merge(None, "./sprites")
        self.assertEqual(result["sprite"], "./sprites")

    def test_both_sprites_produces_array(self):
        result = self._run_sprite_merge(
            "https://example.com/basemap/sprites", "./sprites"
        )
        self.assertIsInstance(result["sprite"], list)
        self.assertEqual(len(result["sprite"]), 2)

    def test_multi_sprite_array_has_default_and_biz_ids(self):
        result = self._run_sprite_merge(
            "https://example.com/basemap/sprites", "./sprites"
        )
        ids = {e["id"] for e in result["sprite"]}
        self.assertIn("default", ids)
        self.assertIn("biz", ids)

    def test_multi_sprite_default_url_preserved(self):
        result = self._run_sprite_merge(
            "https://example.com/basemap/sprites", "./sprites"
        )
        default = next(e for e in result["sprite"] if e["id"] == "default")
        self.assertEqual(default["url"], "https://example.com/basemap/sprites")

    def test_icon_image_prefixed_with_biz(self):
        overlay = [{"id": "icon_layer", "type": "symbol",
                    "layout": {"icon-image": "my_icon"}}]
        result = self._run_sprite_merge(
            "https://example.com/basemap/sprites", "./sprites",
            overlay_layers=overlay
        )
        icon_layer = next(l for l in result["layers"] if l.get("id") == "icon_layer") \
            if "layers" in result else overlay[0]
        # The overlay dict is mutated in-place
        self.assertEqual(overlay[0]["layout"]["icon-image"], "biz:my_icon")

    def test_icon_image_not_double_prefixed(self):
        overlay = [{"id": "icon_layer", "type": "symbol",
                    "layout": {"icon-image": "biz:already_prefixed"}}]
        self._run_sprite_merge(
            "https://example.com/basemap/sprites", "./sprites",
            overlay_layers=overlay
        )
        self.assertEqual(overlay[0]["layout"]["icon-image"], "biz:already_prefixed")

    def test_basemap_array_sprite_gets_biz_appended(self):
        existing_array = [{"id": "default", "url": "https://example.com/sprites"}]
        basemap = {"sources": {}, "layers": [], "sprite": existing_array}
        business = {"sources": {}, "layers": [], "sprite": "./sprites"}

        b_sprite = business.get("sprite")
        bm_sprite = basemap.get("sprite")

        if b_sprite and isinstance(bm_sprite, list):
            if not any(e.get("id") == "biz" for e in bm_sprite):
                bm_sprite.append({"id": "biz", "url": b_sprite})

        self.assertEqual(len(basemap["sprite"]), 2)
        self.assertEqual(basemap["sprite"][1]["id"], "biz")
```

**Step 4: Run test to verify tests pass (they test pure logic)**

```bash
python -m pytest test/test_style_converter.py::TestMultiSpriteBasemapMerge -v
```

Expected: All pass (this is testing the algorithm, not the class method)

**Step 5: Run all tests**

```bash
python -m pytest test/ -v
```

Expected: All pass

**Step 6: Commit**

```bash
git add exporter.py test/test_style_converter.py
git commit -m "feat: pass output_dir to convert(), add multi-sprite basemap support with tests"
```

---

## Task 6: Version bump and changelog

**Files:**
- Modify: `style_converter.py` (line 20: `__version__ = "0.3.0"` → `"0.4.0"`)
- Modify: `exporter.py` (line 11: `__version__ = "0.3.0"` → `"0.4.0"`)
- Modify: `mapsplat.py` (find `__version__` → `"0.4.0"`)
- Modify: `mapsplat_dockwidget.py` (find `__version__` → `"0.4.0"`)
- Modify: `__init__.py` (find `__version__` → `"0.4.0"`)
- Modify: `metadata.txt` (find `version=0.3.0` → `version=0.4.0`)
- Modify: `docs/CHANGELOG.md` (add new section at top)

**Step 1: Update all `__version__` strings**

In each Python module, change `__version__ = "0.3.0"` to `__version__ = "0.4.0"`.

In `metadata.txt`, change `version=0.3.0` to `version=0.4.0`.

**Step 2: Add changelog entry**

At the top of `docs/CHANGELOG.md` (after the title), add:

```markdown
## v0.4.0 — 2026-02-21

### New features

- **SVG sprite rendering (Option D):** Point layers using a single-symbol renderer with `QgsSvgMarkerSymbolLayer` now export as MapLibre `symbol` layers backed by a raster sprite atlas (`sprites.png` + `sprites.json`). The SVG icon renders with full fidelity instead of a generic circle.
- **Sprite fallback for other point types:** Categorized/graduated SVG layers, simple marker shapes, and font marker layers continue to render as color-correct MapLibre `circle` layers. A log message notes when an SVG layer is approximated as a circle.
- **Multi-sprite basemap support:** When basemap overlay mode is active and business layers include sprites, the style uses the MapLibre 4.x multi-sprite array format (`"sprite": [{"id": "default", ...}, {"id": "biz", ...}]`). Business icon references are automatically prefixed with `"biz:"`.
- **`StyleConverter` log callback:** `StyleConverter.__init__()` now accepts an optional `log_callback` parameter for routing sprite generation messages to the QGIS log panel.

### Internal

- `StyleConverter.convert()` accepts a new optional `output_dir` parameter; when provided, sprite generation runs before style conversion.
- New pure-Python helpers: `_compute_sprite_layout()`, `_build_symbol_layer_for_sprite()`.
- New QGIS-dependent helpers: `_is_svg_single_symbol()`, `_render_svg_to_qimage()`, `_generate_sprites()`.
```

**Step 3: Run all tests one final time**

```bash
python -m pytest test/ -v
```

Expected: All pass

**Step 4: Commit**

```bash
git add style_converter.py exporter.py mapsplat.py mapsplat_dockwidget.py __init__.py metadata.txt docs/CHANGELOG.md
git commit -m "chore: bump version to 0.4.0, update changelog for SVG sprite support"
```

---

## Manual Testing Checklist

After completing all tasks, test inside QGIS:

- [ ] **Single SVG point layer:** Export → `sprites.png` and `sprites.json` appear in output; browser shows SVG icon
- [ ] **Categorized SVG point layer:** Export → no sprites generated; browser shows color-correct circles; log mentions "approximated as circle"
- [ ] **Simple marker point layer:** Export → no sprites; browser shows correct circle colors/sizes
- [ ] **Style-only export:** Run with a project that previously generated sprites → re-renders sprites correctly
- [ ] **Basemap overlay + SVG layer:** Merged style has `"sprite"` as array; browser renders both basemap icons and business SVG icons
- [ ] **No point layers:** Export succeeds; no `sprites.png` or `sprites.json` written; no `"sprite"` key in style
