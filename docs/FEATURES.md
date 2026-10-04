# MapSplat Features

Current as of **v0.45.0**. For how to use these, see the [User Guide](USER_GUIDE.md); for what isn't
supported, see [Limitations](LIMITATIONS.md).

---

## Export

- **Vector layers → PMTiles** — selected vector layers are tiled in one step (`ogr2ogr -f PMTiles`).
- **Single file or per-layer** — combine everything in one `.pmtiles`, or produce one per layer.
- **Auto-reprojection** — every layer is reprojected to Web Mercator (EPSG:3857) on export.
- **Layer order follows QGIS** — the exported stack matches your QGIS layer tree in both PMTiles
  modes; the top layer in the panel renders on top, and online base layers stay at the bottom.
  Rearrange in QGIS and the export follows.
- **Export summary** — a per-run report of which layers succeeded/failed, with reasons.
- **Optional PMTiles verification** — run `pmtiles verify` on each written file (Advanced Options, Inputs tab).

## Style conversion

- **Renderers** — Single Symbol, Categorized, Graduated, and Rule-based renderers → MapLibre GL
  Style JSON. Categorized/graduated polygon fills become data-driven `match`/`step` expressions.
- **Scale-dependent visibility** — a layer's scale range, and each rule's own min/max scale in a
  rule-based style (narrowed by parent rules), become MapLibre zoom ranges, so zoom-banded rules
  (e.g. OS Open Zoomstack's National / Regional / Local) appear only in their band.
- **Labels** — text field, font, size, colour, halo, placement, and offsets from QGIS label settings.
- **Dashed & styled lines** — custom dash patterns and Qt preset dashes, width-correct; marker/hash
  decorative lines are omitted rather than approximated as a solid line.
- **Hatch / pattern fills** — rendered as real `fill-pattern` tiles where possible.
- **SVG marker icons** — single-symbol, **categorized**, and **graduated** SVG markers export as
  MapLibre symbol layers backed by a raster sprite sheet, with per-class icons in the legend.
- **Style round-tripping** — export `style.json`, edit in [Maputnik](https://maputnik.github.io/),
  re-import.

## Raster layers

- **Tile rasters to PMTiles** — opt-in (*Include raster layers*): local rasters are reprojected and
  tiled (`gdalwarp → gdal_translate -of MBTiles → gdaladdo → pmtiles convert`) and shown below your
  vectors. RGB/RGBA and paletted rasters are supported. Needs GDAL's MBTiles driver.

## Tile-service layers (MVT / XYZ)

- **Pass-through** — `QgsVectorTileLayer` (MVT) and online XYZ/WMS raster layers are referenced live
  in the style (they stream live — see [Hosting](HOSTING.md)).
- **Use the layer's own style** — a vector-tile layer added with a **Style URL** has that Mapbox-GL
  style fetched and applied at export time (e.g. Carto/MapTiler basemaps render without extra setup).
- **Local MBTiles → bundled PMTiles** — a local `.mbtiles` vector-tile layer is converted to PMTiles
  and bundled for offline use, with its GL style from the layer or the MBTiles metadata.

## Basemap

- **Protomaps** — overlay your data on a Protomaps basemap: **download & clip** your area into the
  export from the latest daily build (**Latest** button) or a local `.pmtiles`, or **stream** a
  PMTiles file you host with CORS.
- **Built-in styles** — Protomaps Light, Dark, White, Grayscale and Black ship with the plugin; or
  use any Protomaps-compatible `style.json`.
- **Setup helpers** — a bundled step-by-step basemap guide (**?** button; also
  [online](https://johnzastrow.github.io/mapsplat4/basemaps.html)), **Copy extract command** for
  clipping once yourself, a note when the `pmtiles` tool is missing, and a **Test** button that
  checks a URL is reachable and, for streaming, that browsers may read it (CORS).
- **XYZ raster basemap** — OpenStreetMap, Carto, OpenTopoMap, Esri World Imagery, or a custom
  `{z}/{x}/{y}` URL, with attribution added automatically.
- **Extract cache** — clipped basemap extracts are cached (by source + extent + zoom); repeat exports
  reuse them. Refresh/Clear from Advanced Options on the Inputs tab.

## The viewer (`index.html`)

- **Self-contained** MapLibre + PMTiles page — click-to-identify popups, your QGIS styling reproduced.
- **Layer list** — collapsible groups matching your QGIS layer tree (incl. QGIS **groups** like
  "My Layers"), interleaved with ungrouped layers in the same order as the QGIS panel; the basemap
  and vector-tile bases in their own collapsible sections at the bottom.
- **Per-layer and per-group on/off toggles** — a checkbox on each layer *and* each group header.
- **Resilient loading** — layers are added individually, so one invalid layer can't blank the map.
- **Configurable controls** (Viewer tab) — scale bar, geolocate, fullscreen, coordinate & zoom
  readouts, reset-view, north-up, label placement, advanced legend, attribution, background, size.
- **Favicon** — the MapSplat mark is set as the page icon.
- **Embeddable** — clearly marked `BEGIN`/`END` copy-paste `<head>`/`<body>` blocks.
- **Built-in dev server** — `serve.py` handles the HTTP Range requests PMTiles need.

## On-map tools (optional, Viewer tab)

- **Measure** — geodesic distance (click) and area (right-click to close); metric + imperial, with a
  runtime units toggle.
- **Draw / sketch** — points, lines, polygons with a per-feature colour picker; export to
  **GeoJSON or KML** (client-side download).
- **Annotate** — place **text labels** (small / medium / large, any colour, white outline,
  draggable) and draw **arrows** (click points; the arrowhead follows the last segment). Annotations
  are included in images saved with the Export tool.
- **Export image** — save the current map as **JPG or PDF** (includes drawings, annotations and a
  scale bar).

## Config save / load

- **Save Config… / Load Config…** — persist every setting (layers, output, PMTiles mode, zoom,
  basemap, viewer controls) to a human-editable **TOML** file.
- **Portable** — layers are stored by name (not runtime IDs), so a config works across sessions and
  machines. Every key has an inline comment.

## Hosting & compatibility

- **QGIS 4 (Qt6)** only.
- **Static hosting** — everything bundled is PMTiles, served by any Range-capable static host
  (Caddy, nginx, `serve.py`, S3/CloudFront). See [Hosting](HOSTING.md).
