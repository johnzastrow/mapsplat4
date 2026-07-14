# Troubleshooting

Common issues and fixes. See also [Hosting](HOSTING.md), [Limitations](LIMITATIONS.md), and the
[User Guide](USER_GUIDE.md).

| Symptom | Cause & fix |
|---|---|
| **"pmtiles CLI not found"** on export | The `pmtiles` binary isn't on QGIS's PATH. Install it from the [go-pmtiles releases](https://github.com/protomaps/go-pmtiles/releases) and restart QGIS — or set the basemap to **Stream from URL** (no CLI needed). |
| **Map is blank / white** | PMTiles need HTTP **Range** requests, which `file://` doesn't provide. Don't open `index.html` directly — run `python serve.py` in the output folder and use the `http://localhost:…` URL. |
| **A layer is missing from the map** | Only layers that tiled successfully are included. Check the **export summary dialog** / the Log tab for the failed layer and its reason. If it was there a moment ago, you may be viewing a **stale server** — stop old `serve.py` processes and re-run. |
| **One layer breaks the whole map** | It won't — the viewer adds layers individually and skips any MapLibre rejects (see the browser console). If a layer is missing, that's why. |
| **Markers show as plain circles** | Per-class icons are rendered only for **SVG** markers (single-symbol, categorized, or graduated). Simple-marker (circle/square) symbols map to circles by design. |
| **Basemap doesn't appear** | Check the basemap **source URL/file** and that its **style** is set. In offline bundles, a bad sprite can blank icons — MapSplat falls back to your local sprite automatically. |
| **A vector-tile (Carto/MapTiler) layer is empty** | It needs a Mapbox-GL style. Add the layer in QGIS **with a Style URL** (MapSplat fetches and applies it), or the source is referenced but unstyled. The Log tab shows *"Fetching GL style…"* when it works. |
| **Raster layer doesn't export** | Enable **Include raster layers** (Export Options) — off by default. It needs GDAL's **MBTiles driver** (`gdal_translate --formats` should list `MBTiles`). Styled single-band rasters (DEMs) aren't supported yet. |
| **🌐-tagged layers are blank** | Vector-tile and online XYZ/WMS layers **stream live** — the exported map needs internet for them and they aren't served by your own host. See [Hosting](HOSTING.md). |
| **PMTiles "verify failed: MinZoom=0 does not match…"** | This is benign — GDAL always stamps `MinZoom=0` even when small features only tile at a higher zoom. MapSplat treats it as a pass with a note; the file is fine. |
| **Layer order looks wrong** | The map follows your **QGIS layer tree** — rearrange layers there and re-export. The Protomaps basemap always sits at the very bottom. |
| **The measure/draw/export tools aren't on the map** | They're **off by default**. Enable each in the **Viewer** tab before exporting. |
| **Slow re-exports of the same area** | Basemap extracts are cached (by source + extent + zoom). Use **Refresh basemap cache** to force a re-download, or **Clear basemap cache** to free disk (Advanced Options). |
| **Embedding into another page shows nothing** | Copy **both** the `<head>` and `<body>` MAPSPLAT blocks, and serve the page over **http with Range support** (see [Hosting](HOSTING.md)). |
