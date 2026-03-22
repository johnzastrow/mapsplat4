# MapSplat TODO List

**Version:** 0.6.12
**Last Updated:** 2026-03-03

---

## Priority Legend

- 🔴 **Critical** - Blocks basic functionality
- 🟠 **High** - Important for usability
- 🟡 **Medium** - Nice to have
- 🟢 **Low** - Future enhancement

---

## Open Items

### Critical

- [x] 🔴 **Bundle MapLibre GL JS assets for offline use** ✅ v0.6.6
  - New Offline tab; downloads maplibre-gl.js/css and pmtiles.js at export time
  - Falls back to CDN with warning if download fails

### High

- [x] 🟠 **Handle null category values in categorized renderer** ✅ v0.6.7
  - Null values coerced to `"__null__"` sentinel via `coalesce`; matched against null category style
  - File: `style_converter.py:_convert_categorized()`

- [x] 🟠 **Handle "all other values" catch-all category** ✅ v0.6.7
  - Catch-all category (empty-string value) used as `match` expression fallback
  - Unmatched features hidden (opacity 0) when no catch-all defined
  - File: `style_converter.py:_convert_categorized()`

- [x] 🟠 **Layer ordering control** ✅ v0.6.7
  - Layer panel order (top → bottom) now respected in style.json and layer list widget
  - `layerTreeRoot().layerOrder()` used in dockwidget; `reversed(self.layers)` in converter
  - File: `mapsplat_dockwidget.py`, `style_converter.py`

### Medium

- [x] 🟡 **Remember last output folder** ✅ v0.6.8
  - Stored in QSettings, restored on plugin open

- [x] 🟡 **Add layer count to UI** ✅ v0.6.8
  - "X of Y layers selected" label below layer list, updates on selection change

- [x] 🟡 **Validate output folder is writable** ✅ v0.6.8
  - `os.access(folder, os.W_OK)` check with descriptive error dialog

- [x] 🟡 **Support graduated color ramps** ✅ v0.6.10
  - `_convert_graduated()` now emits `["interpolate", ["linear"], ...]` for fill-color, line-color, and circle-color
  - Capping stop at `upperValue` of last range ensures full extent is covered

- [x] 🟡 **Support graduated size** ✅ v0.6.10
  - `fill-opacity`, `line-width`, and `circle-radius` all use `interpolate` expressions
  - File: `style_converter.py:_convert_graduated()`

- [ ] 🟡 **Add minzoom/maxzoom per layer**
  - Extract from QGIS scale-dependent visibility settings
  - Apply to MapLibre layer definition
  - File: `style_converter.py`

- [x] 🟡 **Robust style.json import** ✅ v0.6.8
  - Validates JSON parse, top-level object, version:8, and layers key
  - Malformed or wrong-version files rejected with descriptive dialog

- [ ] 🟡 **Map window pixel dimensions for embedding**
  - Add width × height spinboxes (or a preset dropdown) on the Viewer tab
  - Viewer HTML respects the chosen dimensions so the map fits in an existing page without manual CSS edits
  - Pair with the copy-paste embed section so the snippet is ready to drop in
  - File: `mapsplat_dockwidget.py`, `exporter.py:_get_html_template()`

- [ ] 🟠 **Reduce vertical height of the Export tab**
  - Export Options group is too tall on smaller screens, pushing Save/Load Config and Export buttons below the visible area
  - Options to investigate (pick best or combine):
    - Collapse the Export Options group into a `QGroupBox` with a toggle arrow (collapsed by default)
    - Convert multi-row checkbox stacks to a two-column grid layout
    - Move less-used options (Style-only, Log to file) into a collapsible "Advanced" section
    - Add a `QScrollArea` around the Export tab contents as a safety net for any screen size
  - File: `mapsplat_dockwidget.py`, possibly `mapsplat_dockwidget.ui`

- [ ] 🟡 **Legend generation**
  - Generate a proper legend panel from `style.json` layer colors/symbols
  - Currently only color swatches exist; no label-driven legend
  - File: `exporter.py:_get_html_template()`

- [ ] 🟡 **Basemap switcher in viewer**
  - Dropdown to switch between basemap styles at runtime
  - Remember selection in `localStorage`
  - File: `exporter.py:_get_html_template()`

### Low

- [ ] 🟢 **Raster layer export**
  - Export raster layers to PMTiles via `gdal_translate`
  - Rasters placed below vector layers in style.json
  - File: `exporter.py`, `mapsplat_dockwidget.py`

- [ ] 🟢 **External basemap URL (non-Protomaps)**
  - Support OSM, Stadia, MapTiler XYZ tile URLs as basemap
  - Currently basemap overlay only supports Protomaps PMTiles format
  - File: `mapsplat_dockwidget.py`

- [ ] 🟢 **Share/embed code**
  - Generate iframe embed snippet
  - Copy-to-clipboard button in viewer
  - File: `exporter.py:_get_html_template()`

- [ ] 🟢 **Direct cloud upload**
  - Upload output folder directly to AWS S3 / Cloudflare R2 / SFTP
  - File: new `uploader.py`, `mapsplat_dockwidget.py`

- [ ] 🟢 **Preview in plugin before export**
  - Show a small embedded map preview of the current project
  - Complex — requires embedded browser widget

---

## Testing

- [ ] 🟠 **Expand unit tests for style_converter.py**
  - Categorized null/catch-all handling
  - Graduated color ramp expression generation
  - File: `test/test_style_converter.py`

- [ ] 🟠 **Integration test with sample data**
  - Create a test GeoPackage with known features and styles
  - Run full export, validate output directory structure and style.json
  - File: `test/test_exporter.py`

---

## Completed ✅

### Core
- [x] 🔴 Validate ogr2ogr PMTiles generation (GDAL 3.8+) — v0.1.0
- [x] 🟠 GDAL version check and PMTiles driver availability warning — v0.1.7
- [x] 🟠 Cancel button to abort long-running exports — v0.1.7
- [x] 🟡 Max zoom spinbox (4–18, default 6) — v0.1.7
- [x] 🟠 serve.py with HTTP Range request support — v0.1.7
- [x] serve.py --port and --no-browser flags — v0.6.5

### Symbology
- [x] 🟠 Improved label rendering — v0.6.9
  - Bold/italic font, quadrant-aware anchor/offset, text/halo opacity, capitalization, line height, word-wrap, multiline align
  - Label placement mode UI: exact QGIS positions or MapLibre auto-place
  - Line labels: Curved → `symbol-placement: line`; Horizontal → `line-center`
- [x] 🟠 Single Symbol renderer (fill, line, marker) — v0.1.0
- [x] 🟠 Categorized renderer — v0.1.0
- [x] 🟠 Categorized renderer null category handling — v0.6.7
- [x] 🟠 Categorized renderer catch-all category handling — v0.6.7
- [x] 🟠 Layer order matches QGIS panel order — v0.6.7
- [x] 🟠 Graduated renderer — v0.1.0
- [x] 🟠 Opacity extraction (fill, line, circle, stroke) — v0.2.0
- [x] 🟠 Line width unit conversion (mm → px) — v0.2.0
- [x] 🟠 Line dash patterns, cap/join styles — v0.2.0
- [x] 🟠 Multiple symbol layers per renderer — v0.2.0
- [x] 🟠 Labels (text field, font, size, color, halo, placement) — v0.2.0
- [x] 🟠 Rule-based renderer with filter expression conversion — v0.2.0
- [x] 🟠 SVG marker → sprite atlas export — v0.4.0

### Multi-layer & Options
- [x] 🟠 Separate PMTiles per layer mode — v0.1.9
- [x] 🟡 Layer visibility toggles in HTML viewer — v0.1.8
- [x] 🟡 Legend color swatches in layer panel — v0.1.8

### Viewer
- [x] 🟠 Tabbed dockwidget (Export / Viewer / Log tabs) — v0.5.0
- [x] 🟡 7 configurable viewer controls (scale bar, geolocate, fullscreen, coords, zoom, reset-view, north-reset) — v0.5.2
- [x] 🟡 Embeddable HTML with BEGIN/END copy-paste markers — v0.6.1

### Basemap
- [x] 🟠 Basemap overlay mode (Protomaps PMTiles, local or URL) — v0.3.0
- [x] 🟠 Basemap clipping to data extent via pmtiles CLI — v0.3.0
- [x] 🟠 Basemap + business layer style merge — v0.3.0

### Config & Logging
- [x] 🟠 Export log to file with timestamps and log levels — v0.5.1
- [x] 🟠 Config save/load (TOML, human-editable) — v0.6.0

### Style Roundtripping
- [x] 🟡 Export style.json + re-import from Maputnik — v0.2.2
- [x] 🟡 Style-only export (skip data, regenerate HTML/style) — v0.2.1

### Documentation
- [x] PLAN.md, TODO.md, CHANGELOG.md, README.md, REQUIREMENTS.md
- [x] README table of contents — v0.6.5
- [x] Deployment guides (GitHub Pages, Netlify, S3, Nginx, Caddy) — v0.6.4
