"""
MapSplat - Style Converter Module

This module converts QGIS layer styles to MapLibre GL Style JSON format.

Supported renderers:
- Single Symbol (fill, line, marker)
- Categorized
- Graduated
- Rule-based

Supported style properties:
- Fill/stroke colors and opacity
- Line width, dash patterns, cap/join styles
- Marker size, color, stroke
- Labels (text field, font, size, color, halo, placement)
- Multiple symbol layers
"""

__version__ = "0.6.16"

import math
import os
from qgis.core import (
    QgsVectorLayer,
    QgsSingleSymbolRenderer,
    QgsCategorizedSymbolRenderer,
    QgsGraduatedSymbolRenderer,
    QgsRuleBasedRenderer,
    QgsSymbol,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
    QgsSvgMarkerSymbolLayer,
    QgsFontMarkerSymbolLayer,
    QgsLinePatternFillSymbolLayer,
    QgsPointPatternFillSymbolLayer,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsUnitTypes,
    Qgis,
)

# Try to import labeling classes (may vary by QGIS version)
try:
    from qgis.core import QgsVectorLayerSimpleLabeling
except ImportError:
    QgsVectorLayerSimpleLabeling = None

# Quadrant index (QgsPalLayerSettings.QuadrantPosition) → MapLibre text-anchor
_QGIS_QUADRANT_TO_ANCHOR = {
    0: "bottom-right",  # QuadrantAboveLeft
    1: "bottom",        # QuadrantAbove
    2: "bottom-left",   # QuadrantAboveRight
    3: "right",         # QuadrantLeft
    4: "center",        # QuadrantOver
    5: "left",          # QuadrantRight
    6: "top-right",     # QuadrantBelowLeft
    7: "top",           # QuadrantBelow
    8: "top-left",      # QuadrantBelowRight
}

# Direction to push label outward (in em units) per anchor value
_ANCHOR_DIST_DIR = {
    "bottom":       (0,  -1),
    "top":          (0,   1),
    "right":        (-1,  0),
    "left":         (1,   0),
    "bottom-left":  (1,  -1),
    "bottom-right": (-1, -1),
    "top-left":     (1,   1),
    "top-right":    (-1,  1),
    "center":       (0,   0),
}


class StyleConverter:
    """Converts QGIS styles to MapLibre style JSON."""

    # Default colors for fallback
    DEFAULT_FILL_COLOR = "#3388ff"
    DEFAULT_LINE_COLOR = "#333333"
    DEFAULT_POINT_COLOR = "#ff6600"
    DEFAULT_TEXT_COLOR = "#000000"
    DEFAULT_HALO_COLOR = "#ffffff"

    # Unit conversion (mm to pixels at 96 DPI)
    MM_TO_PX = 3.78

    def __init__(self, layers, settings, log_callback=None):
        """Initialize converter.

        :param layers: List of QgsVectorLayer
        :param settings: Export settings dictionary
        :param log_callback: Optional callable(message: str) for logging during sprite generation
        """
        self.layers = layers
        self.settings = settings
        self._layer_counter = {}
        self._log_callback = log_callback
        self._svg_sprite_map = {}  # populated by _generate_sprites(); {source_layer: sprite_key}

    def _log(self, message):
        """Emit a log message via callback if one was provided."""
        if self._log_callback:
            self._log_callback(message)

    def convert(self, single_file=True, output_dir=None):
        """Convert all layers to MapLibre style JSON.

        :param single_file: If True, all layers share one PMTiles source.
                           If False, each layer has its own PMTiles file.
        :param output_dir: If provided, SVG single-symbol point layers are rendered
                           to a sprite atlas (sprites.png + sprites.json) in this
                           directory and the style gets a "sprite" key.
        :returns: Style JSON dictionary
        """
        self._single_file = single_file

        self._svg_sprite_map = {}  # reset for each convert() call

        # Pre-generate sprites for SVG single-symbol point layers
        has_sprites = False
        if output_dir:
            try:
                has_sprites = self._generate_sprites(output_dir)
            except Exception as e:
                self._log(f"Sprite generation skipped: {e}")

        if single_file:
            sources = {
                "mapsplat": {
                    "type": "vector",
                    "url": "pmtiles://data/layers.pmtiles"
                }
            }
        else:
            sources = {}
            for layer in self.layers:
                source_name = self._sanitize_name(layer.name())
                sources[source_name] = {
                    "type": "vector",
                    "url": f"pmtiles://data/{source_name}.pmtiles"
                }

        style = {
            "version": 8,
            "name": self.settings.get("project_name", "MapSplat Export"),
            "sources": sources,
            "glyphs": "https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf",
            "layers": [
                {
                    "id": "background",
                    "type": "background",
                    "paint": {
                        "background-color": "#f8f9fa"
                    }
                }
            ]
        }

        if has_sprites:
            style["sprite"] = "./sprites"

        # Convert each layer.  QGIS panel order is top-to-bottom (top layer renders on top),
        # but MapLibre's style["layers"] array is bottom-to-top (first entry = bottom).
        # Reversing self.layers maps QGIS panel order correctly to MapLibre rendering order.
        for layer in reversed(self.layers):
            minzoom, maxzoom = self._get_zoom_range(layer)
            layer_styles = self._convert_layer(layer)
            for ls in layer_styles:
                if minzoom is not None:
                    ls["minzoom"] = minzoom
                if maxzoom is not None:
                    ls["maxzoom"] = maxzoom
            style["layers"].extend(layer_styles)

            # Add labels if enabled
            label_layer = self._convert_labels(layer)
            if label_layer:
                if minzoom is not None:
                    label_layer["minzoom"] = minzoom
                if maxzoom is not None:
                    label_layer["maxzoom"] = maxzoom
                style["layers"].append(label_layer)

        return style

    def _convert_layer(self, layer):
        """Convert a single layer to MapLibre layer definitions.

        :param layer: QgsVectorLayer
        :returns: List of MapLibre layer dictionaries
        """
        renderer = layer.renderer()
        source_layer = self._sanitize_name(layer.name())
        geom_type = layer.geometryType()

        if self._single_file:
            source_name = "mapsplat"
        else:
            source_name = source_layer

        # Reset layer counter for this source layer
        self._layer_counter[source_layer] = 0

        # Dispatch based on renderer type
        if isinstance(renderer, QgsSingleSymbolRenderer):
            return self._convert_single_symbol(layer, renderer, source_layer, geom_type, source_name)
        elif isinstance(renderer, QgsCategorizedSymbolRenderer):
            return self._convert_categorized(layer, renderer, source_layer, geom_type, source_name)
        elif isinstance(renderer, QgsGraduatedSymbolRenderer):
            return self._convert_graduated(layer, renderer, source_layer, geom_type, source_name)
        elif isinstance(renderer, QgsRuleBasedRenderer):
            return self._convert_rule_based(layer, renderer, source_layer, geom_type, source_name)
        else:
            return self._create_default_style(layer, source_layer, geom_type, source_name)

    def _get_label_font(self, text_format):
        """Select the appropriate Noto Sans variant based on bold/italic flags.

        :param text_format: QgsTextFormat
        :returns: List with one font name string (MapLibre text-font)
        """
        bold = text_format.font().bold()
        italic = text_format.font().italic()
        try:
            bold = bold or text_format.forcedBold()
            italic = italic or text_format.forcedItalic()
        except AttributeError:
            pass
        if bold:
            return ["Noto Sans Medium"]
        elif italic:
            return ["Noto Sans Italic"]
        return ["Noto Sans Regular"]

    @staticmethod
    def _scale_to_zoom(scale_denom):
        """Convert a QGIS scale denominator to a MapLibre zoom level.

        MapLibre GL JS uses 512×512 tiles, so the zoom-0 scale denominator is
        half the OGC/WMTS 256-tile value (559,082,264 → 279,541,132).
        Using the 256-tile constant would produce zoom values 1 level too high,
        requiring the user to zoom in further than the QGIS setting intends.

        Reference: OGC WMTS 256-tile zoom-0 denominator = 559,082,264 at
        0.28 mm/px.  MapLibre 512-tile equivalent = 559,082,264 / 2 = 279,541,132.

        :param scale_denom: QGIS scale denominator (e.g. 50000 for 1:50 000).
        :returns: Zoom level clamped to [0, 24], rounded to 2 decimal places,
                  or None if scale_denom is <= 0.
        """
        if scale_denom <= 0:
            return None
        zoom = math.log2(279541132.014 / scale_denom)
        return round(max(0.0, min(24.0, zoom)), 2)

    def _get_zoom_range(self, layer):
        """Return (minzoom, maxzoom) for a layer from QGIS scale-based visibility.

        QGIS ``minimumScale()`` is the most-zoomed-out limit (largest scale
        denominator) and maps to MapLibre ``minzoom`` (smallest zoom number).
        QGIS ``maximumScale()`` is the most-zoomed-in limit (smallest scale
        denominator) and maps to MapLibre ``maxzoom`` (largest zoom number).

        :param layer: QgsMapLayer
        :returns: Tuple (minzoom, maxzoom) where each element is a float or
                  None if that limit is not set.  Both are None when
                  ``hasScaleBasedVisibility()`` is False.
        """
        if not layer.hasScaleBasedVisibility():
            return (None, None)
        minzoom = self._scale_to_zoom(layer.minimumScale())
        maxzoom = self._scale_to_zoom(layer.maximumScale())
        return (minzoom, maxzoom)

    def _convert_labels(self, layer):
        """Convert layer labels to MapLibre symbol layer.

        Reads placement mode, quadrant, offsets, bold/italic, opacity,
        capitalization, line height, word-wrap, and multiline alignment
        from QgsPalLayerSettings / QgsTextFormat.

        :param layer: QgsVectorLayer
        :returns: MapLibre layer dictionary or None
        """
        if not layer.labelsEnabled():
            return None

        labeling = layer.labeling()
        if labeling is None:
            return None

        source_layer = self._sanitize_name(layer.name())
        source_name = "mapsplat" if self._single_file else source_layer

        try:
            settings = labeling.settings()
        except Exception:
            return None

        if settings is None:
            return None

        # Extract text field
        field_name = settings.fieldName
        if not field_name:
            return None

        clean_field = field_name.strip().replace('"', '').replace("'", "")
        text_field = ["to-string", ["get", clean_field]]

        # Text format
        text_format = settings.format()

        font_stack = self._get_label_font(text_format)
        font_size = self._convert_size(text_format.size(), text_format.sizeUnit())
        if font_size < 8:
            font_size = 12
        font_size_px = max(font_size, 8)
        text_color = text_format.color().name()

        # Halo / buffer
        buffer_settings = text_format.buffer()
        halo_color = None
        halo_width = None
        if buffer_settings.enabled():
            halo = buffer_settings.color()
            try:
                halo_opacity = buffer_settings.opacity()
            except AttributeError:
                halo_opacity = halo.alphaF()
            halo_width = max(1, self._convert_size(buffer_settings.size(), buffer_settings.sizeUnit()))
            if halo_opacity < 1.0:
                halo_color = (
                    f"rgba({halo.red()},{halo.green()},{halo.blue()},{halo_opacity:.3f})"
                )
            else:
                halo_color = halo.name()

        # Label placement mode from export settings ("exact" or "auto")
        label_placement_mode = self.settings.get("label_placement_mode", "exact")

        layout = {
            "visibility": "visible",
            "text-field": text_field,
            "text-font": font_stack,
            "text-size": font_size,
            "text-allow-overlap": False,
            "text-ignore-placement": False,
            "text-optional": True,
            "text-padding": 2,
        }

        paint = {"text-color": text_color}
        if halo_color is not None:
            paint["text-halo-color"] = halo_color
            paint["text-halo-width"] = halo_width

        # Text opacity
        try:
            opacity = text_format.opacity()
            if opacity < 1.0:
                paint["text-opacity"] = opacity
        except AttributeError:
            pass

        # Capitalization → text-transform
        try:
            cap = text_format.capitalization()
            cap_map = {1: "uppercase", 2: "lowercase"}
            if cap in cap_map:
                layout["text-transform"] = cap_map[cap]
        except AttributeError:
            pass

        # Line height (only emit if meaningfully different from 1.0)
        try:
            lh = text_format.lineHeight()
            if abs(lh - 1.0) > 0.05:
                layout["text-line-height"] = round(lh, 2)
        except AttributeError:
            pass

        # Word wrap
        wrap_len = getattr(settings, 'autoWrapLength', 0)
        if wrap_len > 0:
            layout["text-max-width"] = wrap_len

        # Multiline alignment (0=Left, 1=Center, 2=Right, 3=FollowPlacement)
        ml_align = getattr(settings, 'multilineAlign', 1)
        align_map = {0: "left", 1: "center", 2: "right"}
        layout["text-justify"] = align_map.get(ml_align, "center")

        # Geometry-specific placement
        geom_type = layer.geometryType()
        placement = int(getattr(settings, 'placement', 0))

        if geom_type == 1:  # Line
            # Curved (4) → symbol-placement: line
            # Line (2)   → symbol-placement: line
            # Horizontal (5) → symbol-placement: line-center
            if placement == 5:
                layout["symbol-placement"] = "line-center"
            else:
                layout["symbol-placement"] = "line"
                if placement == 4:  # Curved
                    layout["text-max-angle"] = 45
                    layout["text-keep-upright"] = True
            layout["text-rotation-alignment"] = "map"
            repeat = getattr(settings, 'repeatDistance', 0)
            if repeat > 0:
                repeat_unit = getattr(
                    settings, 'repeatDistanceUnit', QgsUnitTypes.RenderMillimeters
                )
                spacing_px = self._convert_size(repeat, repeat_unit)
                layout["symbol-spacing"] = max(50, int(spacing_px))
            else:
                layout["symbol-spacing"] = 250

        elif geom_type == 2:  # Polygon — centroid placement
            layout["symbol-placement"] = "point"
            layout["text-anchor"] = "center"

        elif geom_type == 0:  # Point
            if label_placement_mode == "auto":
                layout["text-variable-anchor"] = [
                    "top", "bottom", "left", "right",
                    "top-left", "top-right", "bottom-left", "bottom-right",
                ]
                dist = getattr(settings, 'dist', 0)
                dist_unit = getattr(
                    settings, 'distUnits', QgsUnitTypes.RenderMillimeters
                )
                dist_px = self._convert_size(dist, dist_unit)
                dist_ems = dist_px / font_size_px
                if dist_ems > 0:
                    layout["text-radial-offset"] = dist_ems
            else:  # exact mode
                quadrant = int(getattr(settings, 'quadrantPosition', 1))
                anchor = _QGIS_QUADRANT_TO_ANCHOR.get(quadrant, "bottom")
                layout["text-anchor"] = anchor

                offset_unit = getattr(
                    settings, 'offsetUnits', QgsUnitTypes.RenderMillimeters
                )
                offset_x = self._convert_size(
                    getattr(settings, 'xOffset', 0), offset_unit
                )
                offset_y = self._convert_size(
                    getattr(settings, 'yOffset', 0), offset_unit
                )
                dist = self._convert_size(
                    getattr(settings, 'dist', 0),
                    getattr(settings, 'distUnits', QgsUnitTypes.RenderMillimeters),
                )
                dx, dy = _ANCHOR_DIST_DIR.get(anchor, (0, 0))
                offset_ems = [
                    offset_x / font_size_px + dx * (dist / font_size_px),
                    offset_y / font_size_px + dy * (dist / font_size_px),
                ]
                if offset_ems != [0.0, 0.0]:
                    layout["text-offset"] = offset_ems

        return {
            "id": f"{source_layer}_labels",
            "type": "symbol",
            "source": source_name,
            "source-layer": source_layer,
            "layout": layout,
            "paint": paint,
        }

    def _convert_single_symbol(self, layer, renderer, source_layer, geom_type, source_name):
        """Convert single symbol renderer with all symbol layers."""
        symbol = renderer.symbol()
        return self._symbol_to_layers(symbol, source_layer, source_layer, geom_type, source_name)

    def _symbol_to_layers(self, symbol, layer_id_base, source_layer, geom_type, source_name, filter_expr=None):
        """Convert a symbol (potentially with multiple symbol layers) to MapLibre layers.

        :param symbol: QgsSymbol
        :param layer_id_base: Base ID for the layer
        :param source_layer: Source layer name in PMTiles
        :param geom_type: Geometry type (0=point, 1=line, 2=polygon)
        :param source_name: PMTiles source name
        :param filter_expr: Optional MapLibre filter expression
        :returns: List of MapLibre layer dictionaries
        """
        layers = []

        if symbol is None:
            return self._create_default_style(None, source_layer, geom_type, source_name)

        # Process each symbol layer (bottom to top)
        for i in range(symbol.symbolLayerCount()):
            sym_layer = symbol.symbolLayer(i)

            # Generate unique layer ID
            self._layer_counter[source_layer] = self._layer_counter.get(source_layer, 0) + 1
            count = self._layer_counter[source_layer]
            layer_id = f"{layer_id_base}" if count == 1 else f"{layer_id_base}_{count}"

            ml_layer = None

            if geom_type == 2:  # Polygon
                ml_layer = self._fill_symbol_layer_to_maplibre(sym_layer, layer_id, source_layer, source_name)
            elif geom_type == 1:  # Line
                ml_layer = self._line_symbol_layer_to_maplibre(sym_layer, layer_id, source_layer, source_name)
            elif geom_type == 0:  # Point
                ml_layer = self._marker_symbol_layer_to_maplibre(sym_layer, layer_id, source_layer, source_name)

            if ml_layer:
                if filter_expr:
                    ml_layer["filter"] = filter_expr
                layers.append(ml_layer)

        return layers if layers else self._create_default_style(None, source_layer, geom_type, source_name)

    def _fill_symbol_layer_to_maplibre(self, sym_layer, layer_id, source_layer, source_name):
        """Convert a fill symbol layer to MapLibre layer."""
        if isinstance(sym_layer, QgsSimpleFillSymbolLayer):
            fill_color = sym_layer.fillColor()
            stroke_color = sym_layer.strokeColor()
            stroke_width = self._convert_size(sym_layer.strokeWidth(), sym_layer.strokeWidthUnit())

            # Extract opacity
            fill_opacity = fill_color.alphaF()
            stroke_opacity = stroke_color.alphaF()

            result = {
                "id": layer_id,
                "type": "fill",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "fill-color": fill_color.name(),
                    "fill-opacity": fill_opacity,
                }
            }

            # Add outline as separate line layer if stroke is visible
            if stroke_width > 0 and stroke_opacity > 0:
                result["paint"]["fill-outline-color"] = stroke_color.name()

            return result

        # Unsupported fill type (gradient, shape-burst, pattern, etc.) —
        # extract the darkest available color rather than using a hardcoded default.
        color = self._extract_darkest_color(sym_layer)
        opacity = 0.5 if isinstance(sym_layer, (QgsLinePatternFillSymbolLayer,
                                                 QgsPointPatternFillSymbolLayer)) else 0.7
        return {
            "id": layer_id,
            "type": "fill",
            "source": source_name,
            "source-layer": source_layer,
            "paint": {
                "fill-color": color if color else self.DEFAULT_FILL_COLOR,
                "fill-opacity": opacity,
            }
        }

    def _line_symbol_layer_to_maplibre(self, sym_layer, layer_id, source_layer, source_name):
        """Convert a line symbol layer to MapLibre layer."""
        if isinstance(sym_layer, QgsSimpleLineSymbolLayer):
            color = sym_layer.color()
            width = self._convert_size(sym_layer.width(), sym_layer.widthUnit())
            opacity = color.alphaF()

            result = {
                "id": layer_id,
                "type": "line",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "line-color": color.name(),
                    "line-width": max(0.5, width),
                    "line-opacity": opacity,
                }
            }

            # Line cap
            pen_cap = sym_layer.penCapStyle()
            cap_map = {0: "flat", 1: "square", 2: "round"}  # Qt.FlatCap, SquareCap, RoundCap
            if pen_cap in cap_map:
                result["layout"] = result.get("layout", {})
                result["layout"]["line-cap"] = cap_map[pen_cap]

            # Line join
            pen_join = sym_layer.penJoinStyle()
            join_map = {0: "miter", 1: "bevel", 2: "round"}  # Qt.MiterJoin, BevelJoin, RoundJoin
            if pen_join in join_map:
                result["layout"] = result.get("layout", {})
                result["layout"]["line-join"] = join_map[pen_join]

            # Dash pattern
            if sym_layer.useCustomDashPattern():
                dash_vector = sym_layer.customDashVector()
                if dash_vector:
                    # Convert from mm to pixels, normalize to line width
                    dash_array = [self._convert_size(d, sym_layer.customDashPatternUnit()) for d in dash_vector]
                    if dash_array and all(d > 0 for d in dash_array):
                        result["paint"]["line-dasharray"] = dash_array

            return result

        # Unsupported line type — extract best available color.
        color = self._extract_darkest_color(sym_layer)
        return {
            "id": layer_id,
            "type": "line",
            "source": source_name,
            "source-layer": source_layer,
            "paint": {
                "line-color": color if color else self.DEFAULT_LINE_COLOR,
                "line-width": 1,
            }
        }

    def _marker_symbol_layer_to_maplibre(self, sym_layer, layer_id, source_layer, source_name):
        """Convert a marker symbol layer to MapLibre layer."""
        if isinstance(sym_layer, QgsSimpleMarkerSymbolLayer):
            fill_color = sym_layer.fillColor()
            stroke_color = sym_layer.strokeColor()
            size = self._convert_size(sym_layer.size(), sym_layer.sizeUnit())
            stroke_width = self._convert_size(sym_layer.strokeWidth(), sym_layer.strokeWidthUnit())

            fill_opacity = fill_color.alphaF()
            stroke_opacity = stroke_color.alphaF()

            return {
                "id": layer_id,
                "type": "circle",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "circle-color": fill_color.name(),
                    "circle-opacity": fill_opacity,
                    "circle-radius": max(2, size / 2),  # Size is diameter, radius for MapLibre
                    "circle-stroke-color": stroke_color.name(),
                    "circle-stroke-width": stroke_width,
                    "circle-stroke-opacity": stroke_opacity,
                }
            }

        elif isinstance(sym_layer, QgsSvgMarkerSymbolLayer):
            sprite_key = self._svg_sprite_map.get(source_layer)
            size = self._convert_size(sym_layer.size(), sym_layer.sizeUnit())
            if sprite_key:
                # Single-symbol SVG with a pre-rendered sprite — emit symbol layer
                return self._build_symbol_layer_for_sprite(
                    layer_id, sprite_key, source_name, source_layer, size
                )
            # Categorized/graduated SVG, or sprite generation not run — circle fallback
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

        elif isinstance(sym_layer, QgsFontMarkerSymbolLayer):
            # Font markers - use circle fallback
            color = sym_layer.color()
            size = self._convert_size(sym_layer.size(), sym_layer.sizeUnit())

            return {
                "id": layer_id,
                "type": "circle",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "circle-color": color.name(),
                    "circle-radius": max(2, size / 2),
                    "circle-stroke-color": "#ffffff",
                    "circle-stroke-width": 1,
                }
            }

        # Unsupported marker type — extract best available color.
        extracted = self._extract_darkest_color(sym_layer)
        return {
            "id": layer_id,
            "type": "circle",
            "source": source_name,
            "source-layer": source_layer,
            "paint": {
                "circle-color": extracted if extracted else self.DEFAULT_POINT_COLOR,
                "circle-radius": 6,
                "circle-stroke-color": "#ffffff",
                "circle-stroke-width": 1,
            }
        }

    def _build_symbol_layer_for_sprite(self, layer_id, sprite_key, source_name, source_layer, size_px):
        """Build a MapLibre symbol layer referencing a pre-rendered sprite entry.

        :param layer_id: MapLibre layer ID string
        :param sprite_key: Key in the sprite manifest (sprites.json)
        :param source_name: PMTiles source name in the style
        :param source_layer: Source-layer name in PMTiles
        :param size_px: Original icon size in pixels (reserved for future icon-size scaling)
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


    def _convert_categorized(self, layer, renderer, source_layer, geom_type, source_name):
        """Convert categorized symbol renderer.

        Handles:
        - Regular categories (value is not None and not "")
        - Null category (value is None): mapped to "__null__" sentinel via coalesce
        - Catch-all category (value == ""): used as the match expression fallback
        - Unmatched features are hidden (opacity 0) when no catch-all is defined
        """
        attr_name = renderer.classAttribute()

        # Separate categories by role; skip inactive or empty symbols
        null_cat = None
        catchall_cat = None
        regular_cats = []
        for cat in renderer.categories():
            if not cat.renderState():
                continue
            symbol = cat.symbol()
            if not symbol or symbol.symbolLayerCount() == 0:
                continue
            value = cat.value()
            if value is None:
                null_cat = cat
            elif value == "":
                catchall_cat = cat
            else:
                regular_cats.append(cat)

        if not regular_cats and null_cat is None and catchall_cat is None:
            return self._create_default_style(layer, source_layer, geom_type, source_name)

        # When a null category exists, coerce null attribute values to a sentinel string so
        # MapLibre's match expression can handle them (match does not support null literals).
        if null_cat is not None:
            match_input = ["coalesce", ["get", attr_name], "__null__"]
        else:
            match_input = ["get", attr_name]

        def _build_match(pairs, fallback):
            """Return a match expression, or the bare fallback if no label-output pairs exist."""
            if not pairs:
                return fallback
            expr = ["match", match_input]
            for label, val in pairs:
                expr.extend([label, val])
            expr.append(fallback)
            return expr

        layers = []

        if geom_type == 2:  # Polygon
            fill_pairs, outline_pairs, opacity_pairs = [], [], []
            for cat in regular_cats:
                sl = cat.symbol().symbolLayer(0)
                if isinstance(sl, QgsSimpleFillSymbolLayer):
                    fill_pairs.append((cat.value(), sl.fillColor().name()))
                    outline_pairs.append((cat.value(), sl.strokeColor().name()))
                    opacity_pairs.append((cat.value(), sl.fillColor().alphaF()))
            if null_cat is not None:
                sl = null_cat.symbol().symbolLayer(0)
                if isinstance(sl, QgsSimpleFillSymbolLayer):
                    fill_pairs.append(("__null__", sl.fillColor().name()))
                    outline_pairs.append(("__null__", sl.strokeColor().name()))
                    opacity_pairs.append(("__null__", sl.fillColor().alphaF()))
            if catchall_cat is not None:
                sl = catchall_cat.symbol().symbolLayer(0)
                if isinstance(sl, QgsSimpleFillSymbolLayer):
                    fill_fb = sl.fillColor().name()
                    outline_fb = sl.strokeColor().name()
                    opacity_fb = sl.fillColor().alphaF()
                else:
                    fill_fb, outline_fb, opacity_fb = self.DEFAULT_FILL_COLOR, self.DEFAULT_LINE_COLOR, 0.0
            else:
                fill_fb, outline_fb, opacity_fb = self.DEFAULT_FILL_COLOR, self.DEFAULT_LINE_COLOR, 0.0
            layers.append({
                "id": source_layer,
                "type": "fill",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "fill-color": _build_match(fill_pairs, fill_fb),
                    "fill-opacity": _build_match(opacity_pairs, opacity_fb),
                    "fill-outline-color": _build_match(outline_pairs, outline_fb),
                }
            })

        elif geom_type == 1:  # Line
            color_pairs, width_pairs, opacity_pairs = [], [], []
            for cat in regular_cats:
                sl = cat.symbol().symbolLayer(0)
                if isinstance(sl, QgsSimpleLineSymbolLayer):
                    color_pairs.append((cat.value(), sl.color().name()))
                    width_pairs.append((cat.value(), self._convert_size(sl.width(), sl.widthUnit())))
                    opacity_pairs.append((cat.value(), sl.color().alphaF()))
            if null_cat is not None:
                sl = null_cat.symbol().symbolLayer(0)
                if isinstance(sl, QgsSimpleLineSymbolLayer):
                    color_pairs.append(("__null__", sl.color().name()))
                    width_pairs.append(("__null__", self._convert_size(sl.width(), sl.widthUnit())))
                    opacity_pairs.append(("__null__", sl.color().alphaF()))
            if catchall_cat is not None:
                sl = catchall_cat.symbol().symbolLayer(0)
                if isinstance(sl, QgsSimpleLineSymbolLayer):
                    color_fb = sl.color().name()
                    width_fb = self._convert_size(sl.width(), sl.widthUnit())
                    opacity_fb = sl.color().alphaF()
                else:
                    color_fb, width_fb, opacity_fb = self.DEFAULT_LINE_COLOR, 2, 0.0
            else:
                color_fb, width_fb, opacity_fb = self.DEFAULT_LINE_COLOR, 2, 0.0
            layers.append({
                "id": source_layer,
                "type": "line",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "line-color": _build_match(color_pairs, color_fb),
                    "line-width": _build_match(width_pairs, width_fb),
                    "line-opacity": _build_match(opacity_pairs, opacity_fb),
                }
            })

        elif geom_type == 0:  # Point
            color_pairs, radius_pairs, stroke_pairs, opacity_pairs = [], [], [], []
            for cat in regular_cats:
                sl = cat.symbol().symbolLayer(0)
                if isinstance(sl, QgsSimpleMarkerSymbolLayer):
                    color_pairs.append((cat.value(), sl.fillColor().name()))
                    radius_pairs.append((cat.value(), self._convert_size(sl.size(), sl.sizeUnit()) / 2))
                    stroke_pairs.append((cat.value(), sl.strokeColor().name()))
                    opacity_pairs.append((cat.value(), sl.fillColor().alphaF()))
            if null_cat is not None:
                sl = null_cat.symbol().symbolLayer(0)
                if isinstance(sl, QgsSimpleMarkerSymbolLayer):
                    color_pairs.append(("__null__", sl.fillColor().name()))
                    radius_pairs.append(("__null__", self._convert_size(sl.size(), sl.sizeUnit()) / 2))
                    stroke_pairs.append(("__null__", sl.strokeColor().name()))
                    opacity_pairs.append(("__null__", sl.fillColor().alphaF()))
            if catchall_cat is not None:
                sl = catchall_cat.symbol().symbolLayer(0)
                if isinstance(sl, QgsSimpleMarkerSymbolLayer):
                    color_fb = sl.fillColor().name()
                    radius_fb = self._convert_size(sl.size(), sl.sizeUnit()) / 2
                    stroke_fb = sl.strokeColor().name()
                    opacity_fb = sl.fillColor().alphaF()
                else:
                    color_fb, radius_fb, stroke_fb, opacity_fb = self.DEFAULT_POINT_COLOR, 6, "#ffffff", 0.0
            else:
                color_fb, radius_fb, stroke_fb, opacity_fb = self.DEFAULT_POINT_COLOR, 6, "#ffffff", 0.0
            layers.append({
                "id": source_layer,
                "type": "circle",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "circle-color": _build_match(color_pairs, color_fb),
                    "circle-radius": _build_match(radius_pairs, radius_fb),
                    "circle-stroke-color": _build_match(stroke_pairs, stroke_fb),
                    "circle-stroke-width": 1,
                    "circle-opacity": _build_match(opacity_pairs, opacity_fb),
                }
            })

        return layers if layers else self._create_default_style(layer, source_layer, geom_type, source_name)

    def _convert_graduated(self, layer, renderer, source_layer, geom_type, source_name):
        """Convert graduated symbol renderer."""
        layers = []
        attr_name = renderer.classAttribute()
        ranges = renderer.ranges()

        if not ranges:
            return self._create_default_style(layer, source_layer, geom_type, source_name)

        if geom_type == 2:  # Polygon
            fill_expr = ["interpolate", ["linear"], ["get", attr_name]]
            opacity_expr = ["interpolate", ["linear"], ["get", attr_name]]

            for r in ranges:
                sym = r.symbol()
                if sym and sym.symbolLayerCount() > 0:
                    sym_layer = sym.symbolLayer(0)
                    if isinstance(sym_layer, QgsSimpleFillSymbolLayer):
                        fill_expr.extend([r.lowerValue(), sym_layer.fillColor().name()])
                        opacity_expr.extend([r.lowerValue(), sym_layer.fillColor().alphaF()])

            # Capping stop: upperValue of last range keeps last color/opacity
            if len(ranges) > 0:
                last_r = ranges[-1]
                last_sym = last_r.symbol()
                if last_sym and last_sym.symbolLayerCount() > 0:
                    last_sl = last_sym.symbolLayer(0)
                    if isinstance(last_sl, QgsSimpleFillSymbolLayer):
                        fill_expr.extend([last_r.upperValue(), last_sl.fillColor().name()])
                        opacity_expr.extend([last_r.upperValue(), last_sl.fillColor().alphaF()])

            layers.append({
                "id": source_layer,
                "type": "fill",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "fill-color": fill_expr,
                    "fill-opacity": opacity_expr,
                    "fill-outline-color": "#333333"
                }
            })

        elif geom_type == 1:  # Line
            line_expr = ["interpolate", ["linear"], ["get", attr_name]]
            width_expr = ["interpolate", ["linear"], ["get", attr_name]]

            for r in ranges:
                sym = r.symbol()
                if sym and sym.symbolLayerCount() > 0:
                    sym_layer = sym.symbolLayer(0)
                    if isinstance(sym_layer, QgsSimpleLineSymbolLayer):
                        line_expr.extend([r.lowerValue(), sym_layer.color().name()])
                        width_expr.extend([r.lowerValue(), self._convert_size(sym_layer.width(), sym_layer.widthUnit())])

            # Capping stop
            if len(ranges) > 0:
                last_r = ranges[-1]
                last_sym = last_r.symbol()
                if last_sym and last_sym.symbolLayerCount() > 0:
                    last_sl = last_sym.symbolLayer(0)
                    if isinstance(last_sl, QgsSimpleLineSymbolLayer):
                        line_expr.extend([last_r.upperValue(), last_sl.color().name()])
                        width_expr.extend([last_r.upperValue(), self._convert_size(last_sl.width(), last_sl.widthUnit())])

            layers.append({
                "id": source_layer,
                "type": "line",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "line-color": line_expr,
                    "line-width": width_expr
                }
            })

        elif geom_type == 0:  # Point
            color_expr = ["interpolate", ["linear"], ["get", attr_name]]
            radius_expr = ["interpolate", ["linear"], ["get", attr_name]]

            for r in ranges:
                sym = r.symbol()
                if sym and sym.symbolLayerCount() > 0:
                    sym_layer = sym.symbolLayer(0)
                    if isinstance(sym_layer, QgsSimpleMarkerSymbolLayer):
                        color_expr.extend([r.lowerValue(), sym_layer.fillColor().name()])
                        radius_expr.extend([r.lowerValue(), self._convert_size(sym_layer.size(), sym_layer.sizeUnit()) / 2])

            # Capping stop
            if len(ranges) > 0:
                last_r = ranges[-1]
                last_sym = last_r.symbol()
                if last_sym and last_sym.symbolLayerCount() > 0:
                    last_sl = last_sym.symbolLayer(0)
                    if isinstance(last_sl, QgsSimpleMarkerSymbolLayer):
                        color_expr.extend([last_r.upperValue(), last_sl.fillColor().name()])
                        radius_expr.extend([last_r.upperValue(), self._convert_size(last_sl.size(), last_sl.sizeUnit()) / 2])

            layers.append({
                "id": source_layer,
                "type": "circle",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "circle-color": color_expr,
                    "circle-radius": radius_expr,
                    "circle-stroke-color": "#ffffff",
                    "circle-stroke-width": 1
                }
            })

        return layers if layers else self._create_default_style(layer, source_layer, geom_type, source_name)

    def _convert_rule_based(self, layer, renderer, source_layer, geom_type, source_name):
        """Convert rule-based renderer to multiple filtered layers."""
        layers = []
        root_rule = renderer.rootRule()

        self._process_rule(root_rule, layers, source_layer, geom_type, source_name, 0)

        return layers if layers else self._create_default_style(layer, source_layer, geom_type, source_name)

    def _process_rule(self, rule, layers, source_layer, geom_type, source_name, depth):
        """Recursively process rule-based renderer rules."""
        # Process this rule if it has a symbol
        if rule.symbol():
            filter_expr = self._convert_qgis_expression_to_maplibre(rule.filterExpression())
            rule_layers = self._symbol_to_layers(
                rule.symbol(),
                f"{source_layer}_rule{len(layers)}",
                source_layer,
                geom_type,
                source_name,
                filter_expr
            )
            layers.extend(rule_layers)

        # Process child rules
        for child in rule.children():
            if child.active():
                self._process_rule(child, layers, source_layer, geom_type, source_name, depth + 1)

    def _convert_qgis_expression_to_maplibre(self, expr_str):
        """Convert a QGIS filter expression to MapLibre filter.

        :param expr_str: QGIS expression string
        :returns: MapLibre filter array or None
        """
        if not expr_str or expr_str.strip() == "":
            return None

        expr_str = expr_str.strip()

        # Use fullmatch so that partial matches (e.g. the start of an AND expression)
        # don't silently return a result for an expression we can't fully convert.
        import re

        # Pattern for: "field" = 'value'
        match = re.fullmatch(r'"([^"]+)"\s*=\s*\'([^\']+)\'', expr_str)
        if match:
            return ["==", ["get", match.group(1)], match.group(2)]

        # Pattern for: "field" = number
        match = re.fullmatch(r'"([^"]+)"\s*=\s*(-?\d+\.?\d*)', expr_str)
        if match:
            return ["==", ["get", match.group(1)], float(match.group(2))]

        # Pattern for: "field" > number
        match = re.fullmatch(r'"([^"]+)"\s*>\s*(-?\d+\.?\d*)', expr_str)
        if match:
            return [">", ["get", match.group(1)], float(match.group(2))]

        # Pattern for: "field" < number
        match = re.fullmatch(r'"([^"]+)"\s*<\s*(-?\d+\.?\d*)', expr_str)
        if match:
            return ["<", ["get", match.group(1)], float(match.group(2))]

        # Pattern for: "field" >= number
        match = re.fullmatch(r'"([^"]+)"\s*>=\s*(-?\d+\.?\d*)', expr_str)
        if match:
            return [">=", ["get", match.group(1)], float(match.group(2))]

        # Pattern for: "field" <= number
        match = re.fullmatch(r'"([^"]+)"\s*<=\s*(-?\d+\.?\d*)', expr_str)
        if match:
            return ["<=", ["get", match.group(1)], float(match.group(2))]

        # Pattern for: "field" != 'value'
        match = re.fullmatch(r'"([^"]+)"\s*!=\s*\'([^\']+)\'', expr_str)
        if match:
            return ["!=", ["get", match.group(1)], match.group(2)]

        # Pattern for: "field" IS NOT NULL
        match = re.fullmatch(r'"([^"]+)"\s+IS\s+NOT\s+NULL', expr_str, re.IGNORECASE)
        if match:
            return ["has", match.group(1)]

        # Pattern for: "field" IS NULL
        match = re.fullmatch(r'"([^"]+)"\s+IS\s+NULL', expr_str, re.IGNORECASE)
        if match:
            return ["!", ["has", match.group(1)]]

        # Complex expressions not yet supported - return None (no filter)
        return None

    def _create_default_style(self, layer, source_layer, geom_type, source_name):
        """Create default fallback style for unsupported renderers."""
        if geom_type == 2:  # Polygon
            return [{
                "id": source_layer,
                "type": "fill",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "fill-color": self.DEFAULT_FILL_COLOR,
                    "fill-opacity": 0.5,
                    "fill-outline-color": "#1a5276"
                }
            }]
        elif geom_type == 1:  # Line
            return [{
                "id": source_layer,
                "type": "line",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "line-color": self.DEFAULT_LINE_COLOR,
                    "line-width": 2
                }
            }]
        elif geom_type == 0:  # Point
            return [{
                "id": source_layer,
                "type": "circle",
                "source": source_name,
                "source-layer": source_layer,
                "paint": {
                    "circle-color": self.DEFAULT_POINT_COLOR,
                    "circle-radius": 6,
                    "circle-stroke-color": "#ffffff",
                    "circle-stroke-width": 1
                }
            }]

        return []

    def _extract_darkest_color(self, sym_layer):
        """Try to extract the darkest usable color from an unsupported symbol layer.

        Tries common color accessor methods (color, fillColor, color2) and returns
        the hex name of the darkest one by perceived luminance.  Returns None if no
        valid color can be found.

        :param sym_layer: Any QgsSymbolLayer (or duck-typed equivalent)
        :returns: Hex color string like '#336699', or None
        """
        candidates = []
        for attr_name in ("color", "fillColor", "color2"):
            try:
                c = getattr(sym_layer, attr_name)()
                if c and c.isValid():
                    candidates.append(c)
            except (AttributeError, TypeError):
                pass
        if not candidates:
            return None

        def _luminance(c):
            return 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()

        return min(candidates, key=_luminance).name()

    def _convert_size(self, size, unit):
        """Convert a size value from QGIS units to pixels.

        :param size: Size value
        :param unit: QgsUnitTypes unit
        :returns: Size in pixels
        """
        if size is None:
            return 0

        # Handle different unit types
        try:
            if unit == QgsUnitTypes.RenderMillimeters:
                return size * self.MM_TO_PX
            elif unit == QgsUnitTypes.RenderPixels:
                return size
            elif unit == QgsUnitTypes.RenderPoints:
                return size * 1.33  # Points to pixels
            elif unit == QgsUnitTypes.RenderInches:
                return size * 96  # Inches to pixels at 96 DPI
            elif unit == QgsUnitTypes.RenderMapUnits:
                # Map units are tricky - use a rough approximation
                return size * 0.1
            else:
                return size * self.MM_TO_PX  # Default to mm
        except Exception:
            return size * self.MM_TO_PX

    def _sanitize_name(self, name):
        """Sanitize layer name for use as source-layer.

        :param name: Original name
        :returns: Sanitized name
        """
        sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
        while "__" in sanitized:
            sanitized = sanitized.replace("__", "_")
        return sanitized.strip("_").lower()

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

            def _call(stroke_w):
                result = cache.svgAsImage(
                    svg_path, float(size_px), fill_color, stroke_color, float(stroke_w), 1.0
                )
                # PyQGIS binding may return (QImage, bool) or just QImage depending on version
                if isinstance(result, tuple):
                    return result[0]
                return result

            img = _call(stroke_width_px)
            if img and not img.isNull():
                return img
            # Retry without color substitution (some SVGs ignore fill/stroke params)
            img = _call(0.0)
            return img if img and not img.isNull() else None
        except Exception as e:
            self._log(f"SVG render failed for '{svg_path}': {e}")
            return None

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
        images_2x = {}
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
            fill_color = sym_layer.fillColor()
            stroke_color = sym_layer.strokeColor()
            stroke_width = self._convert_size(sym_layer.strokeWidth(), sym_layer.strokeWidthUnit())

            img = self._render_svg_to_qimage(svg_path, size_px, fill_color, stroke_color, stroke_width)
            img_2x = self._render_svg_to_qimage(svg_path, size_px * 2, fill_color, stroke_color, stroke_width)

            source_layer = self._sanitize_name(layer.name())
            if img and not img.isNull():
                images[source_layer] = img
                self._svg_sprite_map[source_layer] = source_layer
                self._log(f"Rendered sprite for '{layer.name()}' ({size_px}px)")
            else:
                self._log(
                    f"Warning: could not render SVG for '{layer.name()}', using circle fallback"
                )
            if img_2x and not img_2x.isNull():
                images_2x[source_layer] = img_2x

        if not images:
            return False

        # Compute atlas layout
        sizes = {name: (img.width(), img.height()) for name, img in images.items()}
        manifest, total_w, total_h = self._compute_sprite_layout(sizes)

        # Compose atlas image
        atlas = QImage(max(total_w, 1), max(total_h, 1), QImage.Format_ARGB32)
        if atlas.isNull():
            self._log("Warning: failed to allocate sprite atlas image")
            return False
        atlas.fill(Qt.transparent)
        painter = QPainter(atlas)
        for name, entry in manifest.items():
            painter.drawImage(entry["x"], entry["y"], images[name])
        painter.end()

        # Write sprites.png and sprites.json
        atlas_path = os.path.join(output_dir, "sprites.png")
        json_path = os.path.join(output_dir, "sprites.json")
        if not atlas.save(atlas_path):
            self._log(f"Warning: failed to write sprite atlas to '{atlas_path}'")
            return False
        with open(json_path, "w", encoding="utf-8") as f:
            _json.dump(manifest, f, indent=2)

        self._log(f"Wrote sprite atlas: {len(images)} icon(s) → {atlas_path}")

        # Write @2x sprite files — MapLibre 4.x on high-DPI displays requests these
        # first and does not fall back to 1x when they are missing.
        if images_2x:
            sizes_2x = {name: (img.width(), img.height()) for name, img in images_2x.items()}
            manifest_2x, total_w_2x, total_h_2x = self._compute_sprite_layout(sizes_2x)
            for entry in manifest_2x.values():
                entry["pixelRatio"] = 2
            atlas_2x = QImage(max(total_w_2x, 1), max(total_h_2x, 1), QImage.Format_ARGB32)
            if not atlas_2x.isNull():
                atlas_2x.fill(Qt.transparent)
                painter_2x = QPainter(atlas_2x)
                for name, entry in manifest_2x.items():
                    painter_2x.drawImage(entry["x"], entry["y"], images_2x[name])
                painter_2x.end()
                atlas_2x_path = os.path.join(output_dir, "sprites@2x.png")
                json_2x_path = os.path.join(output_dir, "sprites@2x.json")
                if atlas_2x.save(atlas_2x_path):
                    with open(json_2x_path, "w", encoding="utf-8") as f:
                        _json.dump(manifest_2x, f, indent=2)
                    self._log(f"Wrote @2x sprite atlas → {atlas_2x_path}")

        return True

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

