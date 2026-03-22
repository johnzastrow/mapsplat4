# MapSplat Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## v0.6.16 — 2026-03-04

### Fixed
- **Scale→zoom constant corrected for MapLibre 512px tiles** — the previous
  constant (559,082,264) is the OGC/WMTS standard for 256×256 tiles, but
  MapLibre GL JS renders with 512×512 tiles, making every computed
  `minzoom`/`maxzoom` value 1 zoom level too high. Users had to zoom in one
  full extra level before scale-dependent layers appeared. Fixed by using
  279,541,132 (= 559,082,264 ÷ 2), the correct zoom-0 denominator for
  512-tile renderers.

## v0.6.15 — 2026-03-04

### Added
- **Scale-dependent visibility** — QGIS *Layer Properties → Rendering →
  Scale-based visibility* is now exported. `minimumScale()` (most-zoomed-out
  limit) maps to MapLibre `minzoom`; `maximumScale()` (most-zoomed-in limit)
  maps to `maxzoom`. Both are applied to every MapLibre symbol layer and the
  corresponding label layer. A scale of 0 in QGIS means no limit in that
  direction and the property is omitted from `style.json`. Zoom values are
  computed as `log2(559 082 264 / scale_denominator)` and clamped to [0, 24].
  13 new unit tests cover `_scale_to_zoom()` and `_get_zoom_range()`.

## v0.6.14 — 2026-03-04

### Added
- **Export extent layer** — new "Export extent" dropdown in the Export Options
  group. Pick any layer in the current QGIS project to use its bounding box as
  the export extent instead of the combined extent of all exported layers.
  Basemap extraction applies a +0.5 % padding to the chosen bbox so tiles are
  not clipped right at the data edge; the HTML viewer `fitBounds` call uses the
  raw bbox. The setting round-trips through Save/Load Config as
  `extent_layer_name` in `[export]`.

### Fixed
- **Label halo no longer always white** — `text-halo-color` and
  `text-halo-width` are now only written to `style.json` when the QGIS label's
  *Buffer* tab has "Draw text buffer" checked. Previously a white halo (`#ffffff`,
  1 px) was always emitted regardless of the QGIS setting.
- **Export opens Log tab** — clicking "Export Web Map" now switches to the Log
  tab (index 3). It was incorrectly switching to the Offline tab (index 2).

### Documentation
- **Label settings reference** — new "Label settings" subsection under Supported
  Symbology in README. Covers every exported text property with a QGIS→MapLibre
  mapping table, a font-variant note (Noto Sans Regular / Medium / Italic), a
  step-by-step guide for enabling the text buffer (halo) in QGIS, placement mode
  explanation, and an explicit list of unsupported label features (drop shadows,
  callouts, complex expressions, scale-based visibility, letter spacing).

## v0.6.13 — 2026-03-03

### Fixed
- **Legend color fidelity** — `getLayerColor()` in the HTML viewer now correctly
  unwraps literal CSS colors from MapLibre expression arrays (`match`, `step`,
  `interpolate`). Previously, categorized/graduated layers showed gray swatches
  because the array expression was assigned directly to `backgroundColor`.
  New `extractColorFromExpression()` helper walks any expression type to find the
  first usable color string.

### Added
- **Advanced Legend** — new "Advanced Legend" checkbox on the Viewer tab. When
  enabled, the layer-toggle legend renders one swatch + raw value label per
  category or class break, parsed from the paint expression in `style.json` at
  runtime. Works with `match` (categorized), `step` (graduated), and
  `interpolate` expressions. Hidden if only a single symbol is present.
- **Map Dimensions** — new "Map Dimensions" group on the Viewer tab with Width
  and Height spinboxes (0 = responsive full-window, the current default). Setting
  non-zero values pins the `<div id="map">` to exact pixel dimensions, making
  copy-paste embedding into existing pages easier.

### Changed
- **Export tab scroll** — the Layers, Export Options, Basemap Overlay, and Output
  groups are now wrapped in a `QScrollArea` so they scroll on small screens. Save
  Config, Load Config, the Export button, and the progress bar are pinned in a
  fixed strip below the scroll area and always visible.

## v0.6.12 — 2026-03-03

### Fixed
- **Unsupported symbol layer types no longer render as default blue** — fill handlers for gradient fills, shape-burst fills, and other unrecognized QGIS fill types now extract the darkest available color from the symbol layer's `color()`, `fillColor()`, or `color2()` accessors instead of falling back to the hardcoded `#3388ff` default. The same improvement applies to unrecognized line and marker symbol layer types. A new `_extract_darkest_color()` helper picks the lowest-luminance color by perceived brightness (`0.299R + 0.587G + 0.114B`).

## v0.6.11 — 2026-03-03

### Fixed
- **`serve.py` 403 on root URL** — navigating to `http://localhost:8000/` now serves `index.html` instead of returning "Directory listing not allowed". The handler checks for `index.html` inside a directory path before refusing.

## v0.6.10 — 2026-03-03

### Changed
- **Graduated renderer uses `interpolate` expressions** — `_convert_graduated()` now emits `["interpolate", ["linear"], ["get", attr], ...]` for polygon `fill-color`/`fill-opacity`, line `line-color`/`line-width`, and point `circle-color`/`circle-radius`. Each expression includes stops at `lowerValue` of every range plus a capping stop at `upperValue` of the last range, producing smooth color and size transitions instead of discrete jumps.

## v0.6.9 — 2026-03-03

### Added
- **Label placement mode** — new "Label placement" combo in the Viewer tab's Map Controls group. "Match QGIS (exact positions)" uses quadrant/offset/dist to set `text-anchor` and `text-offset` in ems; "Auto-place (avoid overlaps)" emits `text-variable-anchor` + `text-radial-offset` so MapLibre chooses a collision-free position.
- **Bold/italic font selection** — `_convert_labels()` now picks Noto Sans Medium (bold), Noto Sans Italic, or Noto Sans Regular based on `QgsTextFormat.font().bold()/italic()` and `forcedBold()/forcedItalic()` (QGIS 3.26+).
- **Quadrant-aware point label placement** — `quadrantPosition` (0–8) maps to a MapLibre `text-anchor` value; `xOffset`/`yOffset`/`dist` are converted to ems and applied as `text-offset`.
- **Line label placement modes** — Curved placement → `symbol-placement: line` with `text-max-angle: 45` and `text-keep-upright`; Horizontal placement → `symbol-placement: line-center`; `repeatDistance` → `symbol-spacing`.
- **Text and halo opacity** — `text-opacity` emitted when `QgsTextFormat.opacity() < 1`; halo color encoded as `rgba(r,g,b,a)` when `buffer.opacity() < 1`.
- **Capitalization** — `text-transform: uppercase/lowercase` from `QgsTextFormat.capitalization()`.
- **Line height** — `text-line-height` emitted when `QgsTextFormat.lineHeight()` differs from 1.0 by more than 0.05.
- **Word wrap** — `text-max-width` set from `QgsPalLayerSettings.autoWrapLength` when non-zero.
- **Multiline alignment** — `text-justify` (left/center/right) from `QgsPalLayerSettings.multilineAlign`.
- **`label_placement_mode` config key** — saved/restored in TOML config under `[viewer]`.

## v0.6.8 — 2026-03-03

### Added
- **Layer count summary** — the layer list now shows "X of Y layers selected" below the Select All / Select None buttons, updating immediately on selection change and on project reload.
- **Remember last output folder** — the output folder is saved to `QSettings` whenever it changes and restored automatically the next time the plugin opens.
- **`serve.py --host` flag** — `--host ADDRESS` lets the server bind to a specific interface; defaults to `127.0.0.1` (loopback). Use `--host 0.0.0.0` for LAN or direct VPS access.
- **serve.py: threaded HTTP server** — uses `ThreadingMixIn` so concurrent requests (e.g. tile fetches while the map loads) no longer queue behind each other.
- **Hardened systemd unit in README** — dedicated `mapsplat` service user, file permission setup steps, and systemd security directives (`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, etc.).

### Fixed
- **Output folder writable check** — `_validate_export()` now checks `os.access(folder, os.W_OK)` and shows a clear error message before attempting an export into a read-only location.
- **Robust style.json import** — `_import_style()` now reads and validates the file before accepting it: checks that JSON parses, that the top level is an object, that `"version"` is `8`, and that a `"layers"` key exists. Malformed or wrong-version files are rejected with a descriptive dialog.
- **serve.py: improved Range request parsing** — correctly handles suffix ranges (`bytes=-N`), rejects multi-range requests, and closes the file handle on seek errors; directory listing requests return 403.
- **serve.py: hide server banner** — suppresses the default Python `Server:` response header.

## v0.6.7 — 2026-03-03

### Fixed
- **Null category values in categorized renderer** — categories whose value is `None` (the QGIS "NULL" category) are now rendered correctly. The MapLibre `match` expression wraps the attribute lookup with `coalesce(get(attr), "__null__")` so null feature values are matched against the null category's style instead of falling through to the default.
- **Catch-all category in categorized renderer** — the "all other values" category (empty-string value in QGIS) is now used as the `match` expression fallback. Features not matching any named category use the catch-all style. When no catch-all is defined, unmatched features are hidden (opacity 0) rather than receiving the hardcoded default color.
- **Layer rendering order** — the QGIS layer panel order (top layer renders on top) is now respected in the exported `style.json`. Previously, layers were appended in arbitrary order. The fix reverses `self.layers` when writing `style.json` entries and uses `layerTreeRoot().layerOrder()` instead of `mapLayers().values()` when populating the layer list widget.

## v0.6.6 — 2026-03-03

### Added
- **Offline asset bundling** — new "Offline" tab in the dockwidget with a "Bundle JS/CSS for offline viewing" checkbox. When checked, `maplibre-gl.js`, `maplibre-gl.css`, and `pmtiles.js` are downloaded from unpkg.com at export time and saved to `lib/`. The generated `index.html` references these local files so the viewer works without an internet connection. If the download fails, the export continues with CDN links and a warning is logged.

## v0.6.5 — 2026-03-02

### Added
- **`serve.py --port` and `--no-browser` flags** — `serve.py` now accepts `--port PORT` to listen on a non-default port, and `--no-browser` to suppress the automatic browser launch (useful for headless server deployments and Caddy/Nginx reverse-proxy setups).

## v0.6.4 — 2026-03-02

### Added
- **Caddy reverse-proxy instructions** — README now documents how to run `serve.py` behind stock Caddy for small deployments where rebuilding Caddy with the PMTiles module is not an option.

## v0.6.3 — 2026-03-02

### Changed
- **Simplified output path** — exports now write directly to `<output_folder>/<project_name>_webmap/` instead of the previous `<output_folder>/<project_name>/_webmap/`. One less level of nesting; the output folder name makes the project clear without an extra subdirectory.

## v0.6.2 — 2026-02-23

### Fixed
- **Output directory now includes project name** — export path is `<output_folder>/<project_name>/_webmap/` so different projects written to the same output folder never overwrite each other. Previously the path was just `<output_folder>/_webmap/`, which silently discarded the Project Name input.

### Changed
- **Toolbar icon** — `icon.png` replaced with a 32×32 PNG rendered from `docs/images/logo.svg` (the pink splat mark) via Inkscape. The new icon appears in the QGIS toolbar and Plugin Manager.

## v0.6.1 — 2026-02-23

### Changed
- **Fixed output directory name** — export always writes to `_webmap/` inside the chosen output folder instead of `{project_name}_webmap/`. The export log (when enabled) is also placed in `_webmap/export.log`.
- **Embeddable HTML** — `index.html` now contains `<!-- <----- BEGIN MAPSPLAT ... ----- -->` / `<!-- <----- END MAPSPLAT ... ----- -->` demarcation comments marking which `<head>` (CDN links + styles) and `<body>` (divs + script) blocks to copy when embedding the map in an existing page.
- **New logo** — the pink blob mark (`docs/images/logo.svg`) is inlined in the viewer info panel header alongside the project name. `README.md` updated to reference the new logo.

## v0.6.0 — 2026-02-23

### Added
- **Config file save/load** — "Save Config..." and "Load Config..." buttons above the Export button let users persist and restore all export settings between sessions.
- **`config_manager.py`** — new pure-Python module (no external dependencies) that writes human-editable TOML files with per-key comment headers and reads them back with type detection (bool, int, string, string array).
- Config files store all three setting groups: `[export]` (project name, output folder, layer names, PMTiles mode, zoom, style options, log flag), `[basemap]` (enabled, source type, source path, style path), and `[viewer]` (all 7 map-control checkboxes).
- Layer **names** (not runtime QGIS IDs) are stored in the config file so configs are portable across sessions and machines; names are matched back to the live layer list on load.
- Missing or unknown keys in hand-edited config files are silently ignored for forward compatibility.

## v0.5.11 — 2026-02-23

### Fixed
- **Label font request no longer 404** — MapLibre joins the `text-font` array
  elements with a comma and issues a single URL like
  `Noto Sans Regular,Noto Sans Medium/0-255.pbf`. The protomaps font server
  only hosts individual font files, so the combined-fontstack path returned 404.
  Changed to a single-element array `["Noto Sans Regular"]` so the URL matches
  what the server actually provides.

## v0.5.10 — 2026-02-23

### Fixed
- **Basemap overlay: basemap now renders again; POI labels also correct** —
  v0.5.9 changed the glyphs URL to `demotiles.maplibre.org/font/` which
  returns HTTP 404 for every font, including Noto Sans (used by the Protomaps
  basemap). `protomaps.github.io/basemaps-assets/fonts/` serves Noto Sans
  Regular and Noto Sans Medium with HTTP 200 and CORS headers. By pointing the
  glyphs URL back to the protomaps font server and changing the business label
  font from "Open Sans Regular" (unavailable there) to "Noto Sans Regular"
  (available), all glyph requests now resolve successfully. The v0.5.9 glyphs
  override is removed; the basemap's own URL is kept as-is.

## v0.5.9 — 2026-02-23

### Fixed
- **Basemap overlay: POI icons now render (glyphs root cause)** — the merged
  style inherited the basemap's `glyphs` URL
  (`protomaps.github.io/basemaps-assets/fonts/…`), which returns HTTP 404.
  In MapLibre 4.x a glyphs request failure stalls the entire symbol placement
  pipeline, preventing icon-only layers (POI markers) from rendering even when
  their sprite and PMTiles data load successfully. The fix overrides the merged
  style's `glyphs` key with the business style's working URL
  (`demotiles.maplibre.org`) so font loading succeeds and the symbol pipeline
  can proceed.

## v0.5.8 — 2026-02-23

### Fixed
- **Basemap overlay: business POI icons now render** — replacing the basemap
  sprite with the local `./sprites` URL causes MapLibre 4.x to fire
  `styleimagemissing` for every basemap icon key (shields, POIs, etc.). In
  MapLibre 4.x these unhandled events stall the symbol rendering queue, which
  prevents business-layer icons from appearing even though the data and sprite
  files load successfully. Added a `styleimagemissing` handler that immediately
  registers a 1×1 transparent placeholder for any missing key, unblocking the
  render queue.

## v0.5.7 — 2026-02-23

### Fixed
- **Basemap overlay: local `.pmtiles` sources now rewritten correctly** — the URL
  rewrite that redirects the basemap tile source to `pmtiles://data/basemap.pmtiles`
  previously only matched URLs containing "protomaps". Basemaps sourced from local
  files (e.g. `pmtiles://maine4.pmtiles`) were never rewritten, causing a 404 and
  blank map. The check now matches any vector source that has a URL.

## v0.5.6 — 2026-02-23

### Fixed
- **Release ZIP now includes all plugin modules** — CI workflow switched from
  an explicit file list to `*.py` glob; `log_utils.py` was previously missing
  from the package, causing a `ModuleNotFoundError` on plugin load.

## v0.5.5 — 2026-02-23

### Fixed
- **Basemap overlay mode: POI icons now render** — the generated `index.html`
  now fetches `style.json` at runtime and passes the parsed object to MapLibre
  instead of a URL string. Passing a URL string caused MapLibre to normalise
  `pmtiles://` source URLs against the style base URL, which silently prevented
  `querySourceFeatures` from seeing any features in the business layer when two
  PMTiles sources were present. Both basemap and overlay layers now render
  correctly.

---

## v0.5.4 — 2026-02-23

### Fixed
- **Viewer control overlap** — custom map controls (zoom display, coords display,
  reset-view, north-reset) now position themselves dynamically based on which
  MapLibre built-in controls are enabled. Bottom-left labels clear the scale bar
  (~36 px base when enabled, 8 px when not). Top-right buttons clear the stacked
  NavigationControl (96 px) + optional FullscreenControl and GeolocateControl
  (39 px each) before placing reset-view and north-reset.

---

## v0.5.3 — 2026-02-23

### Fixed
- **Basemap overlay mode: business layer icons now render** — replaced the
  MapLibre multi-sprite array (remote basemap sprite + local biz sprite) with
  a single local sprite. The multi-sprite approach silently failed when the
  remote Protomaps sprite was slow or unavailable, preventing all `biz:*`
  icon-image lookups. Now only the local `./sprites` file is used; basemap
  icon layers (road shields, arrows, POIs) will silently show no icon, but all
  fill/line/water/label layers and all business icons render correctly.

---

## v0.5.2 — 2026-02-22

### Added
- **Viewer tab** in the dockwidget with 7 map control checkboxes (all enabled by default)
- Map controls: scale bar, geolocate, fullscreen, coordinate display, zoom display, reset-view, north-up reset
- `generate_html_viewer()` module-level function in `exporter.py` (testable without Qt)
- Plugin `.gitignore` to exclude `__pycache__/`, `*.pyc`, `.pytest_cache/`, `resources.py`

---

## v0.5.1 — 2026-02-22

### Added
- Export log saved to `export.log` in the output folder (opt-in checkbox)
- `log_utils.py` with `format_log_line()` for timestamped log lines (INFO/WARNING/ERROR/SUCCESS)
- Log file appends across runs for persistent history

---

## v0.5.0 — 2026-02-22

### Changed
- **Tabbed dockwidget:** The panel now has two tabs — "Export" (all settings and controls) and "Log" (output log)
- Log auto-shown when export starts (UI switches to Log tab automatically)
- Removed expand/collapse toggle from the log area; log fills the tab naturally

---

## v0.4.0 — 2026-02-22

### New features

- **SVG sprite rendering (Option D):** Point layers using a single-symbol renderer with `QgsSvgMarkerSymbolLayer` now export as MapLibre `symbol` layers backed by a raster sprite atlas (`sprites.png` + `sprites.json`). The SVG icon renders with full fidelity instead of a generic circle.
- **Sprite fallback for other point types:** Categorized/graduated SVG layers, simple marker shapes, and font marker layers continue to render as color-correct MapLibre `circle` layers. A log message notes when an SVG layer is approximated as a circle.
- **Multi-sprite basemap support:** When basemap overlay mode is active and business layers include sprites, the style uses the MapLibre 4.x multi-sprite array format (`"sprite": [{"id": "default", ...}, {"id": "biz", ...}]`). Business icon references are automatically prefixed with `"biz:"`.
- **`StyleConverter` log callback:** `StyleConverter.__init__()` now accepts an optional `log_callback` parameter for routing sprite generation messages to the QGIS log panel.

### Internal

- `StyleConverter.convert()` accepts a new optional `output_dir` parameter; when provided, sprite generation runs before style conversion.
- New pure-Python helpers: `_compute_sprite_layout()`, `_build_symbol_layer_for_sprite()`.
- New QGIS-dependent helpers: `_is_svg_single_symbol()`, `_render_svg_to_qimage()`, `_generate_sprites()`.

---

## [0.3.0] - 2026-02-20

### Added
- **Basemap overlay mode** — combine a Protomaps basemap with QGIS business layers
  - New "Basemap Overlay" group box in the dockwidget (checkable; disabled by default)
  - Source type toggle: Remote URL or Local file (with Browse button)
  - Basemap style.json picker to load a Protomaps-compatible style
  - `_check_pmtiles_cli()` in exporter: verifies `pmtiles` CLI is available before extraction
  - `_extract_basemap()` in exporter: runs `pmtiles extract` (with bbox + maxzoom) using the
    same QProcess polling pattern as ogr2ogr; keeps UI responsive; supports cancellation
  - `_merge_business_into_basemap()` in exporter: loads basemap style, redirects remote tile
    source URL to `pmtiles://data/basemap.pmtiles`, injects business sources, appends overlay
    layers (excluding background)
- New settings keys: `use_basemap`, `basemap_source_type`, `basemap_source`, `basemap_style_path`

### Changed
- Style merge logic: when `use_basemap` is set, `_merge_business_into_basemap()` is used
  instead of `_merge_imported_style()`
- Standalone mode (basemap unchecked) is fully backward-compatible with all previous settings

### Output structure in basemap mode
```
output_dir/
├── index.html
├── style.json          (basemap style + business layers merged)
├── data/
│   ├── basemap.pmtiles (extracted from Protomaps)
│   └── layers.pmtiles  (business data)
├── lib/
├── README.txt
└── serve.py
```

## [0.2.2] - 2026-02-17

### Changed
- **HTML references external style.json** when "Export separate style.json" is enabled
  - Previously embedded full style inline AND exported separate file
  - Now HTML uses `style: './style.json'` for cleaner separation
  - Enables faster style iteration workflow: edit style.json, refresh browser
  - Self-contained mode (no style.json export) still embeds inline

## [0.2.1] - 2026-02-17

### Added
- **Style-only export option** - new checkbox to skip data conversion
  - Generates only style.json and HTML viewer
  - Much faster for iterating on styles
  - Use when PMTiles data already exists

### Fixed
- **Label rendering** - improved text field extraction
  - Use `to-string` expression to ensure values are strings
  - Standard Open Sans/Arial Unicode fonts for glyph compatibility
  - Default halo for better readability
  - Better label placement with padding and spacing
  - Point labels offset below markers

## [0.2.0] - 2026-02-17

### Added
- **Labels support** - extracts QGIS labels and converts to MapLibre symbol layers
  - Text field, font family, size, color
  - Halo/buffer settings (color, width)
  - Line placement for linear features
- **Rule-based renderer support** - converts filter expressions to MapLibre filters
  - Supports =, !=, <, >, <=, >= operators
  - Supports IS NULL, IS NOT NULL checks
  - Nested rules processed recursively
- **Opacity extraction** - reads actual alpha values from QGIS symbols
  - Fill opacity, line opacity, circle opacity
  - Stroke opacity for markers
- **Line dash patterns** - converts custom dash patterns to MapLibre line-dasharray
- **Line cap/join styles** - extracts pen cap (flat/square/round) and join (miter/bevel/round)
- **Multiple symbol layers** - processes all symbol layers, not just the first
  - Creates separate MapLibre layers for each symbol layer
- **Proper unit conversion** - handles mm, pixels, points, inches
- **Glyphs URL** - added default MapLibre font glyphs for label rendering

### Changed
- Categorized renderer now extracts opacity and line width per category
- Graduated renderer now extracts opacity and line width per range
- Marker symbols now extract stroke width and opacity

### Known Limitations
- SVG markers fall back to circles (sprite sheets not yet implemented)
- Font markers fall back to circles
- Fill patterns fall back to solid fills (needs sprite images)
- Complex QGIS expressions (AND/OR, functions) not converted
- Blend modes not supported by MapLibre

## [0.1.9] - 2026-02-17

### Added
- **Separate PMTiles per layer option** - new "PMTiles mode" dropdown in UI
  - "Single file (all layers)" - default, combines all layers into one PMTiles
  - "Separate files per layer" - creates individual PMTiles files for each layer
- Separate sources in style.json when using separate files mode

### Changed
- StyleConverter now accepts `single_file` parameter to control source generation
- Each layer references its own source when exporting separately

## [0.1.8] - 2026-02-17

### Added
- **Legend swatches** in layer controls panel
  - Color swatches show layer fill/line/circle colors
  - Swatch shape adapts to geometry type (square for fill, line for lines, circle for points)
  - Outline color shown on fill swatches when different from fill

### Fixed
- **serve.py Ctrl+C handling on Windows** - server now shuts down cleanly
  - Uses daemon thread approach instead of blocking serve_forever()
  - Proper shutdown sequence on keyboard interrupt
- **Layer control order** - layers now listed top-to-bottom matching map stacking
  - Top-most (visually on top) layers appear first in the legend

## [0.1.7] - 2026-02-17

### Added
- **Cancel button** to abort long-running exports
- **Max zoom control** in UI (spinbox, range 4-18, default 6)
- **serve.py** script in export output for local viewing
  - Custom HTTP server with Range request support (required for PMTiles)
  - Auto-opens browser on startup
- GDAL version check before conversion
- PMTiles driver availability check
- Layer listing before conversion (shows which layers will be processed)
- Progress updates during ogr2ogr conversion (elapsed time, output file size)
- Expandable log panel (Expand/Collapse button)

### Changed
- **Switched from QThread to QProcess** for ogr2ogr execution
  - UI now stays responsive during long exports
  - Proper cancellation support
- HTML viewer now uses **CDN for MapLibre assets** (unpkg.com)
  - maplibre-gl.js v4.7.1
  - maplibre-gl.css v4.7.1
  - pmtiles.js v3.2.0
- Default max zoom reduced from 14 to 6 (much faster exports)
- Removed maxBounds from map initialization (was causing errors)

### Fixed
- **QgsCoordinateTransformContext error** - was passing wrong type to options.ct
- **QGIS hanging during export** - replaced blocking subprocess with QProcess + processEvents
- **Console windows appearing on Windows** - added CREATE_NO_WINDOW flags
- **PMTiles "no content-length" error** - serve.py now supports HTTP Range requests
- **serve.py "read of closed file" error** - fixed file wrapper to keep file open

### Updated
- TODO.md with completed items and offline bundling feature description

## [0.1.6] - 2026-02-17

### Added
- `deploy.bat` for Windows Command Prompt deployment
- `deploy.ps1` for Windows PowerShell deployment
- Windows deployment instructions in README

### Changed
- README now includes platform-specific installation instructions (Linux/macOS/Windows)

## [0.1.5] - 2026-02-16

### Added
- Local viewing instructions in README
- Explanation of why `file://` protocol doesn't work with PMTiles
- Quick start commands for local servers:
  - Python (`python -m http.server`)
  - Node.js (`npx serve`)
  - PHP (`php -S`)
  - VS Code Live Server
  - PowerShell one-liner for Windows

## [0.1.4] - 2026-02-16

### Changed
- Consolidated duplicate README files into single top-level README.md
- Removed docs/README.md (redundant)

## [0.1.3] - 2026-02-16

### Added
- Comprehensive README.md in plugin root directory
- Detailed deployment instructions for multiple platforms:
  - GitHub Pages
  - Netlify / Vercel
  - AWS S3
  - nginx / Apache
- CORS configuration examples for nginx, Apache, and S3
- Troubleshooting guide for common issues
- Development and build instructions
- Project structure documentation

## [0.1.2] - 2026-02-16

### Added
- Qt6/QGIS 4.0 compatibility shims
- Try/except blocks for Qt5/Qt6 enum differences

### Fixed
- `QAction` import location (moved from QtWidgets to QtGui in Qt6)
- `Qt.RightDockWidgetArea` enum scoping for Qt6
- `Qt.ItemIsEnabled` enum scoping for Qt6
- `Qt.UserRole` enum scoping for Qt6
- `QListWidget.MultiSelection` enum scoping for Qt6

### Changed
- Plugin now compatible with both QGIS 3.x (Qt5) and QGIS 4.x (Qt6)

## [0.1.1] - 2026-02-16

### Added
- PLAN.md with development roadmap and architecture decisions
- TODO.md with prioritized task list
- Updated CHANGELOG.md with version tracking

### Changed
- Renamed plugin from "po" to "mapsplat"
- Updated all version references to 0.1.1

## [0.1.0] - 2026-02-16

### Added
- Initial plugin scaffold
- Dockable widget UI with layer selection
- Layer export to GeoPackage
- PMTiles generation via ogr2ogr
- Basic style conversion for:
  - Single symbol renderers (fill, line, circle)
  - Categorized renderers
  - Graduated renderers
- HTML viewer generation with MapLibre GL JS
- Feature click-to-identify popups
- Auto-reprojection to EPSG:3857 (Web Mercator)
- Style.json export option
- Style.json import for Maputnik roundtripping
- README generation with deployment instructions

### Known Limitations
- Labels not yet supported
- Rule-based renderers fall back to default style
- Complex symbology (SVG markers, patterns) not supported
- Raster export not yet implemented
- MapLibre assets not bundled (CDN fallback)
