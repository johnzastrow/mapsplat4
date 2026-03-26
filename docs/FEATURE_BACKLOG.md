# MapSplat4 - Feature Backlog

Unordered list of desired usability improvements. Prioritization and implementation details are in [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md).

---

## Recently Completed

| Version | Feature | Story |
|---------|---------|-------|
| v0.7.0 | QGIS 4 / Qt6 compatibility | Phase 0 |
| v0.9.0 | Symbology warnings, tile count estimator | Story 10, 11 |
| v0.10.0 | Collapsible sections, extent clipping, current map view | Story 4 ext. |
| v0.11.0 | Persistent settings (QgsSettings), pmtiles missing dialog | Story 6, Story 3 |
| v0.12.0 | UI tab reorganization (Inputs/Options/Log) | — |
| v0.12.1 | Geometry distortion fix (ogr2ogr -s_srs) | — |
| v0.13.0 | Config load warning, attribution field, basemap URL validation, popup field customization | Story 6, 12, 13, Story 3 |

---

## QGIS4 Compatibility *(Complete before any other work)*

### Remove Qt5/Qt6 Compatibility Shims *(Phase 0)* ✅ *Done — v0.7.0*
- [x] Remove Qt5/Qt6 shims from `mapsplat.py` (no longer needed for Qt6-only)
- [x] Remove `QAction` import location shim
- [x] Remove `RightDockWidgetArea`, `ItemIsEnabled`, `UserRole` enum scoping shims

### Qgis.MessageLevel Enum Migration *(Phase 0)*
- [ ] Update all `Qgis.Info`, `Qgis.Warning`, `Qgis.Critical`, `Qgis.Success` to `Qgis.MessageLevel.Info`, etc.
- [ ] Files: `mapsplat_dockwidget.py`, `exporter.py`, `config_manager.py`, `log_utils.py`

### Qt Enum Scoping *(Phase 0)* ✅ *Done — v0.7.0*
- [x] Update `Qt.AlignCenter` → `Qt.AlignmentFlag.AlignCenter`
- [x] Update `Qt.UserRole` → `Qt.ItemDataRole.UserRole`
- [x] Update `Qt.red`, `Qt.darkGreen`, `Qt.darkYellow` → `Qt.GlobalColor.red`, etc.
- [x] Files: `mapsplat_dockwidget.py`

### Recompile Resources for Qt6 *(Phase 0)* ✅ *Done — v0.7.0*
- [x] Run `pyrcc6 -o resources.py resources.qrc`
- [x] Update Makefile: `pyrcc5` → `pyrcc6`

### Verify QGIS4 API Compatibility *(Phase 0)* ✅ *Done — in use*
- [x] Test `QgsVectorFileWriter` API unchanged
- [x] Test `QgsProject.instance()` behavior
- [x] Test `QgsMapLayer` properties and methods
- [x] Test layer tree API (`layerTreeRoot().layerOrder()`)

---

## UI Improvements

### Collapsible Advanced Options *(Story 4)* ✅ *Done — v0.7.1; extended v0.10.0*
- [x] Add collapsible "Advanced Options" section using `QToolButton` with arrow toggle (NOT QGroupBox — QGroupBox enables/disables, not collapses)
- [x] Target `chk_style_only` and `chk_save_log` specifically — these are the rarely-used controls creating clutter
- [x] Extended in v0.10.0: Export Options, Basemap Overlay, and Output sections are also collapsible with the same pattern; Basemap is collapsed by default

### Quick Presets for Map Dimensions *(Story 5)* ✅ *Done — v0.7.1*
- [x] Add dropdown with presets: "Full window (responsive)", "800x600", "800x900", "1024x768", "1920x1080", "Custom"
- [x] Preset selection updates width/height spinboxes
- [x] Manual spinbox edit switches combo to "Custom" automatically

### Open Output Folder Button *(Story 1)* ✅ *Done — v0.7.1*
- [x] Add "Open Folder" button to the **pinned footer** (alongside Export button) — appears after a successful export, stays visible until the next export starts
- [x] Do NOT put this in a success dialog — a dismissed dialog is gone; the pinned footer is persistent
- [x] Use `QDesktopServices.openUrl()` to open in file explorer

### Better Progress Feedback *(Story 1)* ✅ *Done — v0.7.1*
- [x] Add status text label showing current operation
- [x] Display: "Exporting layer 2 of 5: Roads", "Converting to PMTiles", "Generating style.json"
- [x] Show layer-by-layer progress in separate-file mode

### Copy Embed Code *(Story 2a)*
- [ ] Add "Copy Embed Code" button to Viewer tab
- [ ] Read the generated `index.html` from the last output directory
- [ ] Extract the BEGIN/END MAPSPLAT demarcated blocks (head + body) and copy to clipboard
- [ ] Show confirmation: "Embed code copied to clipboard"
- [ ] Disable button when no output has been generated yet this session

### Auto-Launch Viewer After Export *(Story 2b)*
- [ ] Design server lifecycle: start `serve.py` as a managed subprocess using `QProcess` (NOT `subprocess` — blocks QGIS; NOT open `index.html` — file:// breaks PMTiles)
- [ ] Display active port in the UI ("Serving at http://localhost:8000")
- [ ] Add Stop Server button; disable when server is not running
- [ ] Handle port-in-use error gracefully (try next port or prompt)
- [ ] Open `http://localhost:{port}` in browser once server is confirmed listening
- [ ] Add checkbox "Open in browser after export" to Export tab; persist in settings
- [ ] Stop server on plugin unload / QGIS exit

---

## Error Handling

### Validate Basemap URL *(Story 3)* ✅ *Done — v0.13.0*
- [x] Validate basemap URL/file on **focus-out** (NOT on text change — text change fires on every keystroke and would issue an HTTP request per character) — URL HEAD request + file existence check on focus-out
- [x] Show error immediately if URL unreachable or file missing — inline red error label
- [x] Prevent export from starting with invalid basemap config

### pmtiles CLI Missing Dialog *(Story 3)* ✅ *Done — v0.11.0*
- [x] Show QMessageBox with install instructions (not just log)
- [x] Include link to releases page: https://github.com/protomaps/go-pmtiles/releases

### Export Summary for Partial Failures *(Story 3)*
- [ ] Track which layers succeeded/failed
- [ ] Show summary dialog: "3 of 5 layers exported successfully"
- [ ] List failed layers with error reasons

---

## Configuration

### Persist All Settings *(Story 6)* ✅ *Done — v0.11.0*
- [x] Resolve `QSettings` vs `QgsSettings` first — the codebase currently uses `QSettings("MapSplat", "MapSplat")` but should use `QgsSettings` (respects QGIS profile isolation). Migrate `last_output_folder` key before adding new ones.
- [x] Save/restore: export mode, zoom level, style options, all 7 viewer checkboxes, offline bundling toggle, label placement mode
- [x] Validate restored settings (e.g., layer still exists in project)

### Config Load Warnings for Missing Layers *(Story 6)* ✅ *Done — v0.13.0*
- [x] Show clear warning when loading config with missing layers
- [x] List which layers were not found in current project

---

## Features

### Scale-Dependent Visibility Support *(Story 7)* ✅ *Done — v0.6.15/0.6.16*
- [x] Read `scaleDependentVisibility`, `minScale`, `maxScale` from QGIS layers
- [x] Apply as `minzoom`/`maxzoom` in MapLibre layer definitions
- [x] Zoom constant corrected to `279541132` (= 559082264 ÷ 2) for MapLibre 512px tiles

---

## Accessibility

### Keyboard Shortcuts *(Story 8)*
- [ ] `Ctrl+E`: Export
- [ ] `Ctrl+Shift+A`: Select All layers (`Ctrl+A` conflicts with QGIS "Select All Features" — use `Ctrl+Shift+A` instead)
- [ ] `Ctrl+Shift+S`: Save Config
- [ ] `Ctrl+1` / `Ctrl+2` / `Ctrl+3` / `Ctrl+4`: switch to Export / Viewer / Offline / Log tab
- [ ] Add shortcuts to tooltips
- [ ] Use `Qt.ShortcutContext.WidgetWithChildrenShortcut` context to ensure shortcuts fire only when the dock has focus

### Inline Help Tooltips *(Story 9)* ✅ *Done — v0.7.1*
- [x] Audit existing tooltips first — `spin_max_zoom` and `chk_style_only` already have tooltips; do not duplicate
- [x] Add tooltip to `combo_export_mode` (single vs separate files)
- [x] Add tooltip to `combo_extent_layer` (what bounding box is used for)
- [x] Add tooltip to basemap source inputs (URL format, what pmtiles extract does)
- [x] Add tooltip to basemap style input (what the style.json is for)
- [x] Add tooltip to dimension preset dropdown
- [x] Add tooltips to viewer control checkboxes explaining what each control does in the web map

---

## High-Value Additions

### Zoom Level Tile Count Estimator *(Story 10)* ✅ *Done — v0.9.0*
- [x] Add a live label below `spin_max_zoom`: "~N tiles · est. X MB"
- [x] Recalculate on zoom change and on layer selection change
- [x] Compute tile count from combined selected-layer bounding box + zoom: `4^zoom × bbox_fraction_of_world`
- [x] Estimate size as `tile_count × avg_bytes_per_tile` (4 KB/tile)
- [x] Show "select layers to estimate" when no layers are selected
- [x] All math runs on `QgsRectangle` / `QgsCoordinateTransform` — no external dependencies
- [x] Tooltip clarifies basemap tiles are excluded from estimate

### Per-Layer Symbology Warnings *(Story 11)* ✅ *Done — v0.9.0*
- [x] After layer list is populated, inspect each layer's renderer type via `QgsVectorLayer.renderer()`
- [x] Add ⚠ icon to `QListWidgetItem` for layers using: categorized/graduated SVG markers, font markers, heatmap, point displacement, point cluster
- [x] Set tooltip on item explaining the specific limitation (e.g. "SVG markers will render as circles")
- [x] Re-run check when project layers change (fires on every `refresh_layer_list` call)

### Popup Field Customization *(Story 12)* ✅ *Done — v0.13.0*
- [x] Add "Configure Popup Fields..." button or context menu item on layer list items — right-click context menu on layer list
- [x] Open dialog showing all fields for the selected layer with checkboxes (default: all checked) — dialog with per-field checkboxes
- [x] Store visible-field selections per layer in config file (new `[popup]` section) — persisted in `[popup]` config section
- [x] Pass visible-field config to `generate_html_viewer()` and filter popup HTML accordingly — filtered in HTML popup via `popupFieldConfig` JS constant
- [x] "Show all / hide all" toggle in dialog — Select All/None buttons
- [x] Restore selections from config on load
- [x] **Requires Story 6 first** (config file infrastructure needed for per-layer storage)

### Attribution Field *(Story 13)* ✅ *Done — v0.13.0*
- [x] Add "Attribution" text field to Viewer tab
- [x] Default to any attribution found on exported layers via `QgsMapLayer.attribution()`; join multiple with " | "
- [x] Pass attribution string to `generate_html_viewer()`
- [x] Add `maplibregl.AttributionControl({ customAttribution: "..." })` to generated viewer when non-empty
- [x] Save/restore in config file under `[viewer]` — saved under `[viewer] attribution`

### PMTiles Verify After Export *(Story 14)*
- [ ] After each PMTiles file is written (ogr2ogr produces PMTiles directly — no separate convert step), run `pmtiles verify {output_file}`
- [ ] If verify fails, show error dialog with details from stderr
- [ ] Log verification result to export log
- [ ] Add checkbox "Verify PMTiles after export" in Advanced Options (default: **unchecked** — verify does a full tile read and adds noticeable time on large exports)
- [ ] Run verify for each PMTiles file in separate-file mode and aggregate results

### PMTiles Convert (Raster Support) *(Story 15)*
- [ ] Detect raster layers in selection and prompt: "Convert raster layers to PMTiles?"
- [ ] Use `gdalwarp -t_srs EPSG:3857` to reproject raster to Web Mercator (required — QGIS layers can be any CRS)
- [ ] Use `gdal_translate` to produce intermediate GeoTIFF with correct NoData/alpha
- [ ] Use `pmtiles convert` to convert GeoTIFF → PMTiles
- [ ] Determine raster tile zoom range from layer pixel size (avoid over-sampled or blurry tiles)
- [ ] Handle multi-band rasters: RGB imagery vs single-band DEM vs indexed color (different MapLibre paint styles)
- [ ] Place raster PMTiles below vector layers in style.json using `"type": "raster"` source + paint layer (separate code path from vector style generation)
- [ ] Show progress: "Converting raster: 50%"
- [ ] Add to UI: checkbox "Include raster layers" in Export Options
- [ ] Error handling: if GDAL raster support missing, show message with install link
- [ ] Delete intermediate GeoTIFF after PMTiles conversion

### XYZ Tile Source Support *(Story 16)*

**Scope note:** XYZ URLs work directly as MapLibre sources without any conversion. Implement Mode A first; Mode B (offline bundling) is explicitly deferred — bulk-downloading tiles violates most providers' ToS and is a separate large feature.

**Mode A — Direct XYZ passthrough (implement first):**
- [ ] Add "XYZ Tiles" option to basemap UI (radio/tab: "Protomaps PMTiles" vs "XYZ Tiles")
- [ ] Accept standard XYZ tile URLs: `https://tile.openstreetmap.org/{z}/{x}/{y}.png`
- [ ] Support URL placeholders: `{z}`, `{x}`, `{y}`, `{r}` (retina)
- [ ] Add provider presets: OSM, MapTiler, Stadia, ESRI World Imagery (with custom URL option)
- [ ] Handle providers requiring API keys (prompt user for key; store in config — **requires Story 6**)
- [ ] Write MapLibre `{"type": "raster", "tiles": [...], "tileSize": 256}` source into style.json

**Mode B — Convert XYZ to PMTiles for offline (deferred):**
- [ ] Use `pmtiles convert --no-deduplication` to batch-convert tiles within data bounding box
- [ ] Enumerate tiles per zoom level; show download progress with cancel
- [ ] Verify provider terms of service permit bulk download before implementing presets

### Extract Remote PMTiles to Local *(Story 17)*
- [ ] Allow direct URL input for basemap source (existing Protomaps URL already works)
- [ ] Add progress indicator: "Downloading basemap tiles: X%"
- [ ] Support fetching tiles in parallel (configurable thread count via `--download-threads`)
- [ ] Cache downloaded PMTiles locally after first extract
- [ ] Cache key: `hash(source_url + bounds + maxzoom)` computed **at export time** (not at UI config time — bounds depend on selected layers)
- [ ] Add "Refresh cached basemap" button to re-download
- [ ] Handle network errors gracefully (retry 3×, then show error with "Skip basemap" option)
- [ ] Store cache in plugin settings directory (`~/.local/share/QGIS/QGIS4/profiles/default/python/plugins/mapsplat/cache/`)
- [ ] Log cache hits/misses for debugging
- [ ] *Note for future:* cache directory grows unboundedly with varying extents; add "Clear cache" button or size management in a follow-up

### MVT and XYZ Tile Layer Export *(Story 18)*

Export QGIS project layers that are themselves tile services — `QgsVectorTileLayer` (MVT/PBF
endpoints or local MBTiles) and `QgsRasterLayer` with an XYZ/WMS provider — so they appear
in the exported web map as they do in QGIS.

#### Background and current state

| QGIS class | Examples | Current status |
|---|---|---|
| `QgsVectorTileLayer` | MVT/PBF XYZ endpoints, local MBTiles | Disabled in layer list (`[Other]`) |
| `QgsRasterLayer` (XYZ provider) | OSM, ESRI imagery, any `{z}/{x}/{y}.png` | Shown as `[Raster]`, selectable, but silently dropped by exporter |
| `QgsRasterLayer` (WMS/WMTS) | ArcGIS Server, GeoServer | Same — selected but silently ignored |

Both `QgsVectorTileLayer` and XYZ raster sources can be referenced directly in MapLibre
`style.json` without any data conversion — MapLibre consumes them natively as `"type":
"vector"` or `"type": "raster"` sources. Local MBTiles vector tile sources can be converted
to PMTiles in a single `pmtiles convert` step (the tool is already on PATH for basemap use).

#### ⚠ Provider terms of service

**Bulk-downloading or re-serving third-party tile data is almost always prohibited.**
Before packaging any tile source for offline use, users must verify their provider's terms:
- OpenStreetMap tile servers (tile.openstreetmap.org): prohibit bulk download and
  redistribution of rendered tiles; use the OSM data export path instead.
- Stadia Maps, MapTiler, Thunderforest, ESRI: commercial licences; bulk download and
  rehosting are explicitly forbidden without a specific licence tier.
- Self-hosted sources (GeoServer, MapServer, pg_tileserv, your own PMTiles): no
  restriction — bulk packaging is fine.
- Protomaps daily builds: CC-BY licence; redistribution permitted with attribution.

The UI must surface a clear warning and require acknowledgment before any download step.
Pass-through mode (Mode A below) carries no ToS risk because no data is copied.

#### Capturing associated style JSON

For `QgsVectorTileLayer`:
- If the layer was imported from a Mapbox GL style URL, QGIS stores the original GL JSON
  in the layer's custom properties; retrieve and embed or link it.
- If styled manually in QGIS, use `QgsMapBoxGlStyleConverter` to export the QGIS renderer
  back to a GL style fragment (same direction MapSplat already uses for regular vector layers
  via `StyleConverter`).
- If the source service publishes a `style.json` URL (e.g. MapTiler, Protomaps), fetch
  and merge it (or reference it) at export time.

For `QgsRasterLayer` (XYZ/WMS):
- No GL style — just the source URL template plus raster paint properties:
  `raster-opacity` from QGIS layer opacity, optionally `raster-hue-rotate`,
  `raster-brightness-min/max` if the user has adjusted them.

---

#### Stage 1 — Pass-through: reference source URLs in style.json *(implement first)*

No data is downloaded or converted. The exported map requires internet access for these
layers. Highest value for lowest effort.

**Layer list changes:**
- [ ] Import `QgsVectorTileLayer` from `qgis.core`; detect it in `refresh_layer_list`
- [ ] Show detected layers as `[VectorTile]` in the list (enabled for selection)
- [ ] Detect `QgsRasterLayer` with XYZ or WMS/WMTS provider; show as `[XYZ Raster]` or
      `[WMS]` (currently shown as `[Raster]` but dropped by exporter — fix the exporter path)
- [ ] Add `🌐` suffix or `[Online]` tag on items whose source requires internet, so users
      know the exported map will not work offline for those layers

**Exporter changes (`exporter.py`):**
- [ ] Add `"tile"` key alongside `"vector"` and `"raster"` in `_get_selected_layers()`
  return dict; populate with `QgsVectorTileLayer` and XYZ raster instances
- [ ] For each `QgsVectorTileLayer`: write a `"type": "vector"` source into `style.json`
      using `layer.providerType()` / `dataProvider().dataSourceUri()` to extract the URL
      template; include `minzoom`/`maxzoom` from the layer source metadata if available
- [ ] For each XYZ `QgsRasterLayer`: write a `"type": "raster"` source + raster paint layer
      into `style.json`; read opacity from `layer.opacity()`
- [ ] Layer ordering: tile sources below exported PMTiles vector layers in `style.json`
      (consistent with how basemap overlay is ordered)

**Style / GL JSON capture:**
- [ ] For `QgsVectorTileLayer`: attempt to retrieve stored GL style from layer custom
      properties (`layer.customProperty("mapbox-gl-style")`); if present, merge layer
      definitions into output `style.json` instead of writing a generic source
- [ ] If no stored style: write a minimal style using `QgsMapBoxGlStyleConverter` output
      or a single `"background"` + catch-all fill/line layer as a placeholder
- [ ] For raster layers: write `{"raster-opacity": layer.opacity()}` paint block

**Config file support:**
- [ ] Save/restore tile layer selections by layer name in `[export]` section alongside
      regular layer names (same mechanism)
- [ ] Save the source type tag (`vector_tile` / `xyz_raster`) so load can match correctly

---

#### Stage 2 — Local MBTiles conversion *(medium effort, offline-capable)*

Applies only to `QgsVectorTileLayer` instances whose provider is `mbtiles` (local file —
no ToS concern). The file is already on disk; conversion is a single command.

- [ ] Detect `layer.providerType() == "mbtiles"` in the tile layer path
- [ ] Run `pmtiles convert {source.mbtiles} {output}/data/{layer_name}.pmtiles` using the
      existing `QProcess` polling pattern
- [ ] Write a `pmtiles://data/{layer_name}.pmtiles` source URL into `style.json`
      (same as regular exported layers)
- [ ] Include the GL style from the source MBTiles `metadata` table if present
      (`SELECT value FROM metadata WHERE name = 'style'`)
- [ ] Show conversion progress in the Log tab

---

#### Stage 3 — Download online tile sources to PMTiles *(large, ToS-gated)*

For **online** sources where the user has confirmed they hold a licence permitting bulk
download and redistribution.

- [ ] UI: "Package for offline" checkbox per tile layer; disabled by default with tooltip
      explaining ToS requirement
- [ ] Show explicit acknowledgment dialog: "By proceeding you confirm you have the right
      to download and redistribute tiles from [source URL]. Bulk downloading may violate
      your provider's terms of service." Require typed confirmation or checkbox.
- [ ] Show size estimate before download: enumerate tile count for export extent + max zoom
      (same formula as the tile estimator already implemented)
- [ ] For **raster XYZ**: use `gdal_translate -of MBTiles` to download tiles within the
      bounding box, then `pmtiles convert` to produce a PMTiles file;
      write as `"type": "raster"` source in `style.json`
- [ ] For **vector MVT**: use `pmtiles fetch` (if supported by the endpoint) or tile-by-tile
      download into MBTiles, then `pmtiles convert`; merge source GL style if obtainable
- [ ] Show download progress: "Downloading tile layer X: Z%"; support cancel
- [ ] On failure: fall back to pass-through URL (Mode A) with a warning in the log
- [ ] Attribution: always include provider attribution string in the MapLibre
      `AttributionControl` (required by virtually all tile provider licences)

---

#### Key QGIS API references

```python
# Detect vector tile layer
from qgis.core import QgsVectorTileLayer
isinstance(layer, QgsVectorTileLayer)
layer.providerType()          # "xyz", "mbtiles", "vtpk", "arcgismapserver"
layer.dataProvider().dataSourceUri()  # URL template or file path

# Extract stored GL style (if imported from a style URL)
layer.customProperty("mapbox-gl-style")  # may be None

# Detect XYZ raster provider
isinstance(layer, QgsRasterLayer)
layer.dataProvider().name()   # "wms" for both WMS and XYZ in QGIS
layer.dataProvider().dataSourceUri()  # contains "url=..." key-value string

# Raster paint properties
layer.opacity()               # 0.0–1.0; maps to MapLibre raster-opacity

# GL style export from QGIS renderer (for manually-styled vector tile layers)
from qgis.core import QgsMapBoxGlStyleConverter
converter = QgsMapBoxGlStyleConverter()
# (convert QGIS renderer → GL style fragment — API details TBD)
```

---

## Documentation

### Quick Start Guide *(Deferred)*
- [ ] Create quick start section in README
- [ ] 5 steps from install to first export
- [ ] Include troubleshooting for common issues

### Video Tutorial *(Deferred)*
- [ ] Record screen capture of full workflow
- [ ] Host on YouTube or embed in docs
