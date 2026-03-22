# Point Marker Rendering: Approaches and Trade-offs

This document captures the design analysis for rendering QGIS point marker symbols
in the MapSplat web map export. It covers the capabilities of the current circle
approach, alternative approaches considered, and the rationale for how to scope
future work.

---

## Current Implementation

All QGIS point marker symbol layers are exported as MapLibre `circle` layer type.
The style converter (`style_converter.py`) extracts:

- `fillColor()` → `circle-color`
- `fillColor().alphaF()` → `circle-opacity`
- `size / 2` (converted to pixels) → `circle-radius`
- `strokeColor()` → `circle-stroke-color`
- `strokeWidth()` (converted to pixels) → `circle-stroke-width`
- `strokeColor().alphaF()` → `circle-stroke-opacity`

Categorized and graduated renderers emit MapLibre `match` and `step` expressions
so that each feature gets the correct color and size from its attribute value —
all within a single MapLibre layer.

---

## What the Circle Layer Can Actually Achieve

MapLibre's `circle` layer type is more capable than it might appear.

### Paint properties

| Property | MapLibre support | Currently extracted |
|---|---|---|
| `circle-color` | Full data expressions (`match`, `step`, `interpolate`) | ✅ |
| `circle-opacity` | Data expressions | ✅ |
| `circle-radius` | Data expressions | ✅ |
| `circle-stroke-color` | Data expressions | ✅ |
| `circle-stroke-width` | Data expressions | ✅ |
| `circle-stroke-opacity` | Data expressions | ✅ |
| `circle-blur` | 0 = sharp edge, 1 = fully feathered glow | ❌ not extracted |
| `circle-translate` | Pixel offset from point geometry | ❌ not extracted |
| `circle-pitch-scale` | `map` or `viewport` | ❌ not extracted |
| `circle-sort-key` | Controls per-feature draw order | ❌ not extracted |

### Visual effects achievable

**Color variation** — Because `circle-color` accepts full MapLibre expressions, the
existing categorized and graduated renderer support already produces correct per-feature
colors via `match` and `step`. Every distinct category value gets its exact QGIS fill color.

**Size variation** — Graduated renderers emit `step` expressions for `circle-radius`,
so features with different attribute values render at different sizes without any
additional layers.

**Stroke rings** — A colored stroke of controllable width around the circle. Combined
with a semi-transparent fill and a bright stroke, this produces a pin-ring effect
that reads well over both light and dark basemaps.

**Soft glow / heatmap-adjacent** — `circle-blur: 1.0` causes the circle to fade from
full color at center to transparent at the radius. Not currently extracted from QGIS
(QGIS has no direct equivalent), but could be emitted for specific renderer types.

**Compound effects via stacked symbol layers** — Because QGIS symbols can have multiple
symbol layers, and the converter's `_symbol_to_layers()` processes each separately, you
can already get a stacked effect: a large outer circle (stroke only) plus a small inner
filled circle, for example. The style converter handles this today.

**Selection / highlight halos** — A second circle layer at slightly larger radius with
low opacity creates a halo around each point. This can be added manually by importing
a style.json.

### Fundamental ceiling

**Shape.** `circle` is always a circle. QGIS `QgsSimpleMarkerSymbolLayer` supports
roughly 20+ distinct shapes:

```
Circle        Square        Diamond       Triangle (up/down)
Pentagon      Hexagon       Octagon       Star (4/5/6 points)
Arrow         Cross (+)     X cross (×)  Half circle
Third circle  Quarter circle  Arrowhead   And more
```

Every one of these currently maps to a MapLibre circle. A diamond-categorized layer
and a star layer both render as circles — only color and size differ. Orientation
(rotation) is also lost.

---

## Alternative Approaches Considered

### A. SVG Sprite Sheets (full)

**How it works:** Render each unique QGIS SVG marker to a raster PNG using
`QgsApplication.svgCache().svgAsImage()`. Pack them into a sprite atlas
(`sprites.png` + `sprites.json`). Reference via MapLibre `symbol` layer with
`icon-image`. Add `"sprite": "./sprites"` to style.json.

**Pros:**
- True fidelity for SVG markers — icons render as-designed
- MapLibre `symbol` layers support both `icon-image` and `text-field` in one layer
  (icon and label co-rendered cleanly)

**Cons — the color × shape explosion problem:**
The categorized/graduated renderer uses a single MapLibre layer with a `match`
expression to handle all category colors. With sprites, each unique
**(SVG path + fill color + stroke color)** combination needs its own sprite entry.
A categorized layer with 20 categories and one SVG = 20 separate sprites.
The elegant data-expression approach is lost.

**Raster scaling blurriness:**
Circles are vector and stay crisp at every zoom level. Sprites are rasterized at
one fixed pixel size and get blurry when MapLibre upscales them at higher zooms.

**`icon-color` limitation:**
MapLibre's `icon-color` only works on SDF-encoded sprites (Signed Distance Field —
a special grayscale encoding). Regular PNG sprites ignore `icon-color`. Colors must
be baked into the sprite at export time; they cannot be driven by data expressions.

**Style-only re-export is broken:**
The existing "Style only (skip data export)" mode re-generates style.json without
re-running ogr2ogr. With sprites, re-generating the style also requires re-rendering
all PNG icons. Fast style iteration is no longer possible.

**Basemap overlay complexity:**
MapLibre 4.x supports a multi-sprite array format:
```json
"sprite": [
  {"id": "default", "url": "<basemap sprite url>"},
  {"id": "biz",     "url": "./sprites"}
]
```
In this mode, business icons must be referenced as `"biz:icon_name"` in `icon-image`.
This requires the style converter to know the sprite ID prefix at generation time,
and the basemap merge step to detect and preserve the basemap's sprite URL.

### B. SDF Sprite Sheets

Pre-render shapes and SVGs as SDF (Signed Distance Field) bitmaps. SDF sprites
support `icon-color` expressions, so color can be driven by data at render time.

**Additional cons:**
- Generating SDF images requires computing a distance field transform, which is
  non-trivial in pure Python/PyQt with no additional libraries.
- SDF is primarily useful for simple shapes (not photographic SVGs).
- Complex SVG imagery does not encode well as SDF.

### C. Unicode Text Icons (no sprite needed)

Map QGIS simple marker shapes to Unicode characters (● ■ ▲ ◆ ★ ✕) and emit them
as MapLibre `symbol` layers with `text-field`. Apply QGIS fill color via `text-color`.

**Pros:** No sprite generation; no PNG files; color data expressions work naturally.

**Cons:** Rendering quality depends entirely on the glyphs URL / font stack in the
style. Shapes look different across fonts. Limited set of available shapes. SVGs
cannot be handled this way.

### D. Scoped SVG Sprites (single-symbol layers only)

Generate sprites **only for single-symbol SVG layers** — one sprite per layer,
not per category color variant. Categorized/graduated layers with SVG markers fall
back to color-correct circles.

**Pros:**
- Sprite sheet stays small (at most one entry per point layer)
- Categorized color expressions remain intact
- `icon-color` limitation doesn't matter (one color per sprite)
- Style-only export still works (one re-render per layer, not 20)

**Cons:**
- Categorized SVG layers don't get their actual icon shape
- Multi-symbol layers (stacked SVGs) only partially handled

---

## Recommended Scope for Future Implementation

The scoped approach (D) has the best risk/reward profile:

1. **`QgsSimpleMarkerSymbolLayer`** (all shapes) → keep as `circle`. The color,
   size, stroke, and opacity are all correctly extracted. Shape fidelity is lost
   but the data-expression approach is preserved.

2. **`QgsSvgMarkerSymbolLayer` with single-symbol renderer** → generate one sprite
   entry per layer, emit MapLibre `symbol` layer with `icon-image`. Full icon fidelity.

3. **`QgsSvgMarkerSymbolLayer` with categorized/graduated renderer** → fall back to
   color-correct `circle`. Log a note that shape is approximated.

4. **`QgsFontMarkerSymbolLayer`** → keep as `circle` (or render glyph to sprite
   as a future extension).

5. **Basemap overlay mode** → for SVG sprites, use MapLibre 4.x multi-sprite array
   format so basemap and business sprites coexist cleanly.

6. **Labels** → keep as separate symbol layers (current approach works well; MapLibre
   handles z-ordering between point and label layers correctly).

### What this achieves

- SVG icons for single-symbol point layers: ✅ exact fidelity
- Color-correct circles for all other point layers: ✅ already working
- Data-driven colors for categorized/graduated layers: ✅ preserved
- No sprite sheet generated when no SVG single-symbol layers present: ✅ no overhead
- Style-only export continues to work: ✅ (re-renders only single-sprite per layer)
- Basemap overlay: ✅ via multi-sprite array

---

## Alternative Web Mapping Toolkits with PMTiles Support

MapLibre GL JS is not the only option. This section surveys the other toolkits that
can consume PMTiles, their integration maturity, and — critically — whether they offer
better point marker styling than MapLibre.

### PMTiles support summary

| Toolkit | PMTiles support | Type | Status |
|---|---|---|---|
| **MapLibre GL JS** | Yes — `addProtocol` + pmtiles npm package | First-class, official | Active, recommended by Protomaps |
| **OpenLayers** | Yes — `ol-pmtiles` plugin (`PMTilesVectorSource`, `PMTilesRasterSource`) | Third-party plugin | Active |
| **Deck.gl** | Yes — via `loaders.gl` v4.2+ `PMTilesSource` (April 2024) | loaders.gl module | Active but requires wiring with `MVTLayer` |
| **protomaps-leaflet** | Yes — canvas renderer for vector PMTiles | Leaflet plugin | **Maintenance mode — no new features** |
| **Mapbox GL JS** | Yes — community plugin `mapbox-pmtiles` | Unofficial plugin | Moderate activity |
| **Tangram.js** | **No** — open issue since 2021, not implemented | — | Active (v0.22.0, Dec 2024) but no PMTiles |
| **Leaflet (base)** | Raster PMTiles only via `leafletRasterLayer()` | pmtiles npm helper | Active, but no vector support natively |
| **Felt** | Internal use + accepts PMTiles URLs | Commercial platform | Not an embeddable SDK |

---

### MapLibre GL JS

The reference integration. Protomaps maintains the `pmtiles` npm package with a
first-class protocol handler:

```javascript
const protocol = new pmtiles.Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);
// Source URL: "pmtiles://https://example.com/data.pmtiles"
```

MapLibre automatically reads `minzoom`/`maxzoom` from the PMTiles archive header.

**Point icon system** — the `symbol` layer:

| Approach | Per-feature color? | Custom shapes? | Notes |
|---|---|---|---|
| Raster sprite sheet (`sprites.png` + `sprites.json`) | No (RGB baked in) | Yes — any PNG shape | Standard approach |
| Individual image via `map.addImage()` | No | Yes | Loaded at runtime from URL or canvas |
| SVG via `loadImage()` / `styleimagemissing` hook | No | Yes | Rasterized before storage — not retained as vector |
| SDF sprite (`sdf: true` in manifest) | **Yes** — `icon-color` accepts data expressions | Single-color mask only | Best option for recolorable icons |
| Data-driven `icon-image` | — | — | Supported since v0.35.0; `match`/`case` selects sprite by attribute |

**No toolkit renders icons as native WebGL vector geometry.** All icons ultimately
pass through a raster sprite pipeline. SDF is the closest thing — it preserves edge
sharpness and enables runtime recoloring but collapses to a single color channel.

---

### OpenLayers + ol-pmtiles

OpenLayers has had native vector tile support since 2014. The `ol-pmtiles` third-party
package bridges the PMTiles archive format to OL's existing tile source API:

```javascript
import { PMTilesVectorSource } from "ol-pmtiles";
const layer = new VectorTile({ source: new PMTilesVectorSource({ url: "..." }) });
```

**Point icon system** — `ol/style/Icon`:

- Accepts a `src` URL including SVG files and `data:image/svg+xml` data URIs
- `color` option tints the icon — works well when SVG fill is white; less reliable with
  colored SVGs (known issue: [OL #7699](https://github.com/openlayers/openlayers/issues/7699))
- `offset` + `size` allow sprite sheet sub-rectangle selection
- **Style functions** (plain JavaScript callbacks) allow fully arbitrary per-feature
  icon selection and styling — more flexible than a declarative expression language

**WebGL point renderer** (`ol/layer/WebGLPoints`):
- Shader-based, efficient for large point datasets
- Style defined as a JSON object compiled into GLSL at runtime
- Supports `icon-src`, `icon-color` driven by feature attributes, `icon-scale`, `icon-rotation`
- Sprite sheet-based icons with data-driven selection: see the
  [Icon Sprites with WebGL example](https://openlayers.org/en/latest/examples/icon-sprite-webgl.html)

**Comparison to MapLibre:** OpenLayers' style function approach is more flexible for
complex per-feature logic (arbitrary JavaScript), but requires more code. MapLibre's
declarative expression language is more portable and easier to serialize. OL has no
SDF equivalent but SVG sources work and the WebGL shader supports color expressions.

---

### Deck.gl + loaders.gl PMTilesSource

Deck.gl added PMTiles support via `loaders.gl` v4.2 (April 2024):

```javascript
import { PMTilesSource } from "@loaders.gl/pmtiles";
// Wire into MVTLayer via the loaders prop
```

**Point icon system** — `IconLayer`:

- Works with raster images only at the layer level
- Two modes:
  - **Pre-packed sprite atlas:** `iconAtlas` (PNG) + `iconMapping` (JSON). `mask: true`
    flag enables single-channel (alpha mask) mode — enables per-feature color via `getColor`
  - **Auto-packing:** Individual URLs via `getIcon` — fetched and rasterized at runtime;
    accepts SVG URLs
- **`getColor` accessor:** Controls per-feature color only when `mask: true`. Without
  mask mode, `getColor` controls opacity only.
- `GeoJsonLayer` with `pointType: 'icon'` delegates to `IconLayer`; same constraints apply

**Comparison to MapLibre:** Deck.gl's `IconLayer` mask mode is equivalent to MapLibre
SDF sprites in capability. The deck.gl approach has richer 3D/visualization capabilities
(extruded points, WebGL2 instancing at scale), but the PMTiles wiring is less polished
than MapLibre's `addProtocol`.

---

### protomaps-leaflet (Maintenance Mode)

A canvas-based vector PMTiles renderer for Leaflet. **Now in official maintenance mode** —
the Protomaps team recommends MapLibre GL JS for all new projects.

**Point styling API:**

```javascript
// Paint rules — geometry rendering
new CircleSymbolizer({ radius, fill, stroke, width, opacity })
new IconSymbolizer({ name: "icon-name", sheet: spriteSheetObject })

// Label rules — collision-aware placement
new TextSymbolizer({ fill, stroke, width, ... })
new OffsetTextSymbolizer({ ... })
```

- `CircleSymbolizer`: canvas-drawn filled circles. Functional, no SDF, no data expressions
- `IconSymbolizer`: raster sprite sheet only; no SVG symbolizer exists; no `icon-color` equivalent
- Custom symbolizers can be implemented against the Canvas 2D API (JavaScript only)
- Style rules are plain JavaScript, making arbitrary data-driven behavior straightforward
  in code — but there is no declarative expression language

**Bottom line:** Weaker icon system than MapLibre. No SDF, no per-feature recoloring,
no SVG source. Suitable only for projects already locked into Leaflet.

---

### Mapbox GL JS + mapbox-pmtiles

Shares the same style spec lineage as MapLibre. PMTiles support via the community
plugin `mapbox-pmtiles` (`mapboxgl.Style.setSourceType()`).

Icon system is identical to MapLibre (shared spec ancestry) — raster sprites and SDF
sprites both work; `icon-color` expressions work on SDF sprites. In practice, Mapbox
GL JS requires an API token and has diverged from MapLibre; for PMTiles workflows
MapLibre is the better choice.

---

### Tangram.js

**Does not support PMTiles.** Open issue since May 2021; no implementation planned
as of v0.22.0 (December 2024). Tangram supports Z/X/Y URL templates for MVT binary
tiles but not the PMTiles archive format. Not viable for this project without
significant custom work.

---

### Cross-toolkit comparison for point icon styling

| Toolkit | SVG icons | Per-feature color | Shape variety | Sprite sheet | Blur / glow |
|---|---|---|---|---|---|
| **MapLibre GL JS** | Yes (rasterized) | Yes (SDF + `icon-color` expression) | Anything in sprite | Yes (raster + SDF) | `circle-blur` on circle layer |
| **OpenLayers** | Yes (native SVG URL, with tinting caveats) | Yes (style function or WebGL shader) | Anything in SVG/PNG | Yes (WebGL sprite) | Custom WebGL shader |
| **Deck.gl** | Yes (URL auto-packing, rasterized) | Yes (mask mode `getColor`) | Anything in atlas | Yes (raster, mask) | Custom shader |
| **protomaps-leaflet** | No | Via JS code logic | Circle only natively | Yes (raster) | No |
| **Mapbox GL JS** | Yes (rasterized) | Yes (SDF + `icon-color`) | Anything in sprite | Yes (raster + SDF) | `circle-blur` |
| **Tangram.js** | No (no PMTiles) | Via YAML/JS scene | Texture sprites | Yes (texture) | No |

---

### Key findings for MapSplat

1. **MapLibre GL JS remains the right choice** for MapSplat. It has the best PMTiles
   integration, the richest symbol layer spec, and the Protomaps ecosystem is built
   around it. No other toolkit offers a meaningfully better icon system.

2. **No toolkit renders icons as native scalable vectors at runtime.** Every toolkit
   rasterizes icons to bitmaps for GPU rendering. SDF is the highest-fidelity option
   for recolorable single-color icons; full-color multi-channel icons must be baked as PNG.

3. **OpenLayers has the most flexible per-feature styling** (arbitrary JavaScript style
   functions), but its PMTiles support is a third-party plugin and its SVG color tinting
   has documented edge-case issues. The flexibility advantage is less important in
   MapSplat's export scenario where styles are generated once at export time.

4. **Deck.gl's mask-mode `IconLayer`** is equivalent to MapLibre SDF in capability for
   point markers, but the overall PMTiles wiring is more complex and the ecosystem less
   mature for this use case.

5. **protomaps-leaflet is deprecated** and should not be considered for new development.

6. **SDF sprites remain the most promising path** for per-feature recolorable icons in
   MapLibre — a future feature for `QgsSimpleMarkerSymbolLayer` shapes if shape fidelity
   becomes a priority. SDF generation requires external tooling (`spritezero-cli --sdf`
   or equivalent) but the sprites once generated work cleanly with `icon-color` expressions.

---

## References

- MapLibre GL JS `circle` layer spec: https://maplibre.org/maplibre-style-spec/layers/#circle
- MapLibre GL JS `symbol` layer spec: https://maplibre.org/maplibre-style-spec/layers/#symbol
- MapLibre sprite format: https://maplibre.org/maplibre-style-spec/sprite/
- MapLibre multi-sprite support (v4.x): `"sprite"` as array of `{id, url}` objects
- QGIS `QgsSvgCache`: `QgsApplication.svgCache().svgAsImage(path, size, fill, stroke, strokeWidth, scaleFactor)`
- QGIS simple marker shapes: `QgsSimpleMarkerSymbolLayer.Shape` enum
- PMTiles for MapLibre GL: https://docs.protomaps.com/pmtiles/maplibre
- PMTiles for Leaflet: https://docs.protomaps.com/pmtiles/leaflet
- PMTiles for OpenLayers: https://docs.protomaps.com/pmtiles/openlayers
- protomaps-leaflet (maintenance mode): https://github.com/protomaps/protomaps-leaflet
- ol-pmtiles plugin: https://github.com/protomaps/PMTiles/tree/main/openlayers
- OpenLayers Icon API: https://openlayers.org/en/latest/apidoc/module-ol_style_Icon-Icon.html
- OpenLayers WebGL sprite example: https://openlayers.org/en/latest/examples/icon-sprite-webgl.html
- Deck.gl IconLayer: https://deck.gl/docs/api-reference/layers/icon-layer
- loaders.gl PMTiles (v4.2+): https://loaders.gl/docs/modules/pmtiles/formats/pmtiles
- mapbox-pmtiles community plugin: https://github.com/am2222/mapbox-pmtiles
- Tangram PMTiles issue (open since 2021): https://github.com/tangrams/tangram/issues/776
- MapML.js v0.14.0 PMTiles: https://www.w3.org/community/maps4html/2024/09/04/mapml-js-release-v0-14-0-css-and-pmtiles/
