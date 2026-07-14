# MapSplat Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — basemap extract caching (0.35.0, Story 17)
- **Cached basemap extracts.** The clipped basemap is cached by `sha256(source + bbox + maxzoom)`
  under the active QGIS profile (`.../mapsplat/basemap_cache/`). A cache **hit** copies the previous
  extract instead of re-downloading — big speedup for repeat exports of the same area. Transient
  failures **retry 3×**, and `pmtiles extract` now runs with `--download-threads` for parallelism.
- New Advanced Options: a **Refresh basemap cache (re-download)** checkbox (bypasses a hit and
  re-caches) and a **Clear basemap cache** button (reports files + MB freed). Cache hits/misses are
  logged. Verified: the cache key is stable and sensitive to source and max-zoom changes.

### Added — MVT / XYZ tile layer pass-through (0.34.0, Story 18 Stage 1)
- **Tile-service layers now export (pass-through).** `QgsVectorTileLayer` (XYZ/MVT) and online XYZ
  raster layers (`wms` provider — OSM, imagery, any `{z}/{x}/{y}`) are referenced directly in
  `style.json` — a `type: "vector"` or `type: "raster"` source with the live URL template. **No data
  is downloaded**, so there is no provider ToS concern (Stages 2–3 for offline packaging remain).
  - Vector tile layers are now **selectable** in the layer list (previously disabled `[Other]`);
    online layers are tagged **🌐** so it's clear the exported map needs internet for them.
  - XYZ raster layers were previously selectable but **silently dropped** by the exporter — fixed.
  - A vector tile layer with a stored Mapbox-GL style (`mapbox-gl-style` custom property) is rendered
    with that style; without one, the source is referenced and flagged in the export summary (it needs
    styling in the target page — MapLibre can't infer per-source-layer layers).
  - Tile sources are inserted **below** the exported vector PMTiles layers. Verified headless: the
    generated raster+vector tile style loads in MapLibre with no validation errors and correct order.

### Added — export summary + PMTiles verify (0.33.0)
- **Partial-failure summary (Story 3).** In per-layer export mode, a layer that fails to tile is
  skipped (as before) but now recorded; at the end the exporter reports `N of M layer(s) OK` and the
  dock shows a summary dialog listing each failed layer with its reason, instead of the failure only
  appearing as a log line.
- **PMTiles verify after export (Story 14).** New *Verify PMTiles after export* checkbox in Advanced
  Options (off by default — it does a full tile read). When on, `pmtiles verify` runs on each written
  tile file (per-layer, single-file, and the basemap); failures are logged and folded into the export
  summary. Persisted in QgsSettings and TOML config.

### Added — graduated marker icons + dual-sprite fallback (0.32.0)
- **Graduated (range-based) SVG markers → per-class icons.** A graduated point renderer whose ranges
  are SVG markers now renders each range as its real sprite icon via a `step` `icon-image` over the
  class attribute (mirrors the categorized path), instead of falling back to circles. Per-range icons
  also populate the legend. Verified: the `step` expression maps values to the correct range icon at
  every boundary, and MapLibre renders a `step` `icon-image` with real sprites headlessly.
- **Dual-sprite fallback.** When a basemap + business sprite **array** is used and one URL is
  unreachable (typically the remote basemap sprite offline), the whole array previously failed and
  blanked our local business markers too. The viewer now catches the sprite load error and falls back
  to the local `mapsplat` sprite (via `setSprite`) so markers still render. Verified headless by
  breaking the basemap sprite URL: the business icon went unavailable→available after fallback and
  markers painted.
- **Copy-embed note accuracy.** The `<body>` block's NOTE now states the entire MAPSPLAT `<head>`
  block (MapLibre + PMTiles assets **and** the `<style>` rules; inline when bundled offline) must be
  present — the previous wording mentioned only the CDN tags. The BEGIN/END head+body demarcations
  were confirmed to bracket exactly the copyable content (no page-specific `<title>`/`<meta>` leak).
- **QGIS-4:** confirmed the `Qgis.MessageLevel` enum migration is a no-op — the plugin uses
  string-based log levels throughout and has zero `Qgis.*` enum references.

### Changed — toolbar polish + drawing interactions (0.31.0)
- **Consistent native-style tool buttons.** The custom map buttons (reset view, reset north, measure,
  draw, export) are now **29×29** with **black line-art SVG icons** (stroke `currentColor`, so they
  invert to white when a tool is active), matching MapLibre's own control buttons (e.g. the geolocate
  "find my location" button). Replaces the old mixed-size, multi-coloured emoji buttons.
- **Right-click to finish.** Completing a drawn line/polygon or a measurement is now a **right-click**
  (context menu) instead of a double-click — a double-click added stray vertices before finishing.
- **Identify suppressed during tools.** While the measure or draw tool is active, the feature-identify
  **popups no longer fire on click**, so they don't get in the way of sketching. Popups resume when
  the tool is switched off. Verified headless: 29×29 SVG buttons, right-click commits a polygon, and
  no popup appears on click while a tool is active.

### Fixed — export now includes drawings + scale bar (0.30.1)
- **Exported JPG/PDF now reliably show drawn/measured features and a scale bar.** The export tool
  composites the WebGL map canvas onto a 2D canvas and reads it **synchronously inside a render
  frame** (instead of an async `toBlob`), so GL overlay layers — the draw and measure features —
  are always captured. A **scale bar** is painted onto the image (when the on-screen scale bar is
  on), computed with MapLibre's round-number heuristic. The legend/controls panel remains excluded
  (it is a separate HTML overlay, not part of the map canvas). Verified headless: the export image
  contained the drawn polygon and a bottom-left scale bar.

### Added — plugin tool framework, export tool, adjustable units/colours (0.30.0)
- **Interactive tools are now plugins.** Measure, Draw, and Export are self-registering objects on a
  small `MapSplatTools` host with a stable ctx (addButton/makePanel/download/activateExclusive/
  freshCanvas). Each tool uses only long-stable MapLibre APIs, so **upgrading MapLibre doesn't touch
  the tools** — swap the library and the plugins keep working. Buttons auto-stack (no per-tool pixel
  math); the host also enforces measure/draw mutual exclusion.
- **New Export tool** (Viewer tab → *Export tool*, off by default): save the current map image as
  **JPG or PDF**. Self-contained — the single-image PDF is assembled in-page (JPEG embedded via a
  `/DCTDecode` image XObject), no bundled PDF library. Enables `preserveDrawingBuffer` only when on.
- **Adjustable at runtime by the viewer:** the measure readout has a **units toggle**
  (metric + imperial / metric / imperial) and the draw tool has a **per-feature colour picker**
  (colour is stored per feature and round-trips to GeoJSON/KML, incl. a KML `<Style>`). Authors can
  set the starting defaults with `measure_units` / `draw_color`.
- Verified headless: all three tools register and run under the host; unit switching filters the
  readout correctly; two draw features exported with distinct colours; JPEG (valid `FF D8`) and PDF
  (`%PDF-1.4`…`%%EOF`, `/DCTDecode`) both produced from the live canvas.

### Added — draw/sketch tool with GeoJSON/KML export (0.29.0)
- **Optional on-map draw tool.** A pencil button (Viewer tab → *Draw/sketch tool*, off by default)
  lets viewers draw **points, lines, and polygons** (Point/Line/Polygon modes, Finish/Undo/Clear)
  and export the result as **GeoJSON or KML** via a client-side download — nothing is uploaded.
  Self-contained offline JS. A small tools coordinator keeps Measure and Draw **mutually exclusive**.
  Verified headless: drew all three geometry types, produced a valid GeoJSON FeatureCollection
  (closed polygon ring) and spec-correct KML, and confirmed activating one tool deactivates the other.

### Added — measure tool (0.28.0)
- **Optional on-map measure tool.** A ruler button (Viewer tab → *Measure tool*, off by default)
  lets viewers click to add points and read a live **geodesic distance**; double-click closes a
  polygon and adds **area**. Both are shown in **metric and imperial** (m/km/ha/km² and ft/mi/ac/mi²).
  Implemented as self-contained offline JS (haversine length + spherical-excess area) — no external
  library, no CDN. Verified headless: for a test quad the readout matched an independent geodesic
  calc to the decimal (perimeter 1477.06 m, area 13.508 ha).

### Added — plugin version in export log (0.27.6)
- The export log now records the MapSplat version — in the `--- Export run … (MapSplat x.y.z) ---`
  header and as the first `[INFO]` line — so a saved `export.log` is self-identifying and matches the
  `mapsplat:version` embedded in `style.json`.

### Fixed — no solid stand-in for marker/hash lines (0.27.5)
- **Decorative marker/hash lines no longer inject a solid line.** A QGIS line symbol can stack a
  marker line (symbols placed along the line, e.g. paw prints) or hash/tick line over a base line.
  These can't render as symbols-on-a-line in the web map, and the previous plain-solid fallback
  muddied the real line beneath it (a solid underlay under the dashed `wandering_cat` line). Those
  sublayers (`layerType()` `MarkerLine`/`HashLine`) are now omitted, so the intended dashed/simple
  line renders cleanly. Genuinely unsupported *simple* line types still get a solid colour stand-in.

### Added — dashed categorized/graduated lines (0.27.4)
- **Categorized and graduated line layers now render dashes.** Previously only single-symbol lines
  got a `line-dasharray`; class-based line layers always rendered solid. `line-dasharray` cannot be
  data-driven in MapLibre (arrays can't be read from feature properties), so the layer carries one
  **representative** dash — the most common pattern across the classes (`_pick_dash`), while
  color/width/opacity stay fully data-driven per class. Reuses the width-correct normalization and
  Qt-preset handling from 0.27.3.

### Fixed — dashed line rendering (0.27.3)
- **Dashed lines render at the correct scale.** MapLibre's `line-dasharray` is specified in units of
  **line width**, but the converter was emitting **absolute pixels** (the code comment even said
  "normalize to line width" but didn't) — so dashes came out ~3-4x too large (the poorly-rendered
  `wandering_cat` line). New `_line_dash` helper divides the QGIS dash lengths by the line width, and
  also converts the **Qt preset pen styles** (Dash/Dot/DashDot/DashDotDot), which were previously
  ignored and rendered solid. Malformed (odd-length) dash arrays are dropped.

### Fixed — vertical legend layout (0.27.2)
- Per-class legend entries (marker icons / class swatches) now wrap onto their own full-width line
  **below** the layer row instead of being laid out to the right of it (`display:flex` was putting
  them in the same row, stretching the legend wide). The legend panel is capped at 280px and scrolls
  vertically when tall.

### Fixed — marker legend classes always show (0.27.1)
- Per-class marker icons now render in the legend even when the **advanced legend** option is off.
  A categorized marker layer's per-class icons are essential to reading the layer, so they're no
  longer gated behind that toggle (which still controls the colour-inferred class breakdowns for
  fill/line layers). Fixes "categories don't appear for Points of Disinterest — just a single marker".

### Added — legend: per-class icons, QGIS groups, collapsing (0.27.0)
- **Per-class marker icons in the legend.** A categorized point layer with SVG markers now shows each
  class's actual icon + label (embedded as data URLs in `metadata["mapsplat:legend-classes"]` on the
  symbol layer); previously it showed nothing useful. `buildLegendEntries`/`makeLayerSwatch` render
  these icon rows.
- **QGIS layer-tree groups.** Groups (e.g. `My Layers`) are captured via `_build_legend_groups`
  (`layerTreeRoot`) into `metadata["mapsplat:legend-groups"]` (preserved through the basemap merge)
  and rendered as **collapsible `<details>` sections, collapsed by default**. Ungrouped and basemap
  layers stay at the top level.
- **Collapsing long class lists.** A layer with **more than 6** class entries wraps them in a
  collapsible "N classes" toggle (collapsed by default), keeping the legend compact.
- Verified with a headless Chromium render: the group collapses, per-class icons appear, and the
  many-class toggle collapses.

### Added — dual basemap+business sprites & serve.py banner (0.26.0)
- **Basemap icons and business marker icons now coexist.** When the basemap ships its own sprite
  (shields, POIs), MapSplat combines it with the business sprite via a MapLibre **sprite array**:
  the basemap keeps its icons under the `default` namespace and our icons live under `mapsplat:`
  (icon-image references and the sprite-icons metadata are prefixed to match). Previously the
  business sprite *replaced* the basemap's, dropping basemap icons. If the basemap has no sprite,
  ours is used directly as before. (Note: a MapLibre sprite array fails as a whole if one sprite URL
  is unreachable — normally fine, but a very flaky remote basemap sprite could stall business icons.)
- **`serve.py` prints a startup banner** — the serve.py path, the folder it's serving, the project
  name, the **MapSplat version** that built the export, a layer/data-source summary, and a loud
  **warning when the folder is in the Trash** (the classic "stale zombie server" gotcha). The export
  style now records `mapsplat:version` / `mapsplat:project` in `metadata` for this.

### Added / Fixed — categorized SVG markers + MapLibre-5 sprite URL (0.25.0)
- **Categorized point layers with SVG markers now render their real markers.** A categorized
  marker renderer used to collapse to plain circles; MapSplat now renders **one sprite icon per
  class** (crash-safe via `QSvgRenderer`, not `symbolPreviewPixmap`, which segfaults headless) and
  emits a `symbol` layer with a data-driven `icon-image` `match`, so each class shows its own icon.
  Non-SVG marker classes still use the circle fallback.
- **Fixed: MapLibre GL JS 5 rejects a relative `sprite` URL** (`Invalid sprite URL "./sprites", must
  be absolute`). This silently broke **all** sprite icons — including single-symbol SVG markers. The
  viewer now resolves the sprite URL to absolute (`new URL(sprite, location.href)`) before creating
  the map, for both embedded and fetched styles. Verified with a headless render (icons load and the
  markers paint).
- Per-class icon names are recorded in `metadata["mapsplat:sprite-icons"]` so the
  `styleimagemissing` handler doesn't clobber them.

### Fixed — serve.py no-cache (0.24.2)
- **`serve.py` now sends `Cache-Control: no-store` (and `Pragma`/`Expires`) on every response.**
  Browsers were caching `style.json`, `index.html`, and tiles across exports, so after re-exporting
  a project a changed/added layer would look **missing** until a hard refresh — the flip-flopping
  "lost layers" behaviour. The data and style were always correct on disk (confirmed by a headless
  render); this makes the local preview always reflect the latest export.

### Added — style-build logging (0.24.1)
- The dock **Log** tab now reports the style build: each layer as it's converted (renderer type →
  number of style layers + label, and the source name), a **warning when a renderer produces 0
  layers** (would-be-invisible), the sprite/pattern counts, and a final `Style built` / `Final style`
  summary listing the data sources. Makes "missing layer" reports diagnosable at a glance.

### Fixed — sprite icon render race (0.24.0)
- **SVG-marker point layers no longer render blank.** The viewer's `styleimagemissing` handler
  (added so *missing basemap* icons wouldn't stall rendering) was also adding an empty 1×1
  placeholder for **our own** sprite icons if MapLibre requested one before the sprite finished
  loading — permanently blanking that marker layer (the label still showed, since labels use
  glyphs, not the sprite). The converter now records our sprite icon names in
  `metadata["mapsplat:sprite-icons"]` (preserved through the basemap merge), and the handler
  **skips** those ids so the sprite always provides them.

### Fixed / Added — labels, background override, export robustness (0.23.0)
- **Label placement reads the real QGIS 4 settings.** The quadrant was read via a
  `quadrantPosition` attribute that no longer exists on QGIS 4's `QgsPalLayerSettings`, so it
  silently used the default (below-point). It now reads `pointSettings().quadrant()`, so a
  point label is pinned to the quadrant QGIS actually uses (e.g. centred). "Exact" placement
  mode uses `text-anchor` + `text-offset` (deterministic, no drift); "auto" mode uses
  `text-variable-anchor` to avoid overlaps. The QGIS Y offset (cartographic, +Y up) is negated
  to MapLibre's +Y-down convention.
- **Background colour override.** New optional field on the **Viewer** tab (and `background_color`
  in the config file). Blank leaves the basemap/default background unchanged; a hex value overrides
  both the generated background layer and the basemap's.
- **`serve.py` no longer crashes on a busy port** — it auto-advances through the next 20 ports and
  prints a clean message instead of a raw `Address already in use` traceback.
- **Invalid-CRS layers are skipped cleanly.** A layer with no valid CRS can't be placed on a web map;
  it's now skipped with a clear message instead of exporting geometry to the wrong location.

### Fixed / Added — draw order, hatch angles, robustness (0.22.0)
- **Polygon draw order follows QGIS.** When a categorized layer defines a feature *order by*
  expression (e.g. `"name" = 'park bounds' DESC` to push one class to the back), MapSplat now
  splits it into per-category fill layers ordered to match, so overlapping polygons stack exactly
  as in QGIS. Layers without an explicit order keep the single efficient match layer.
- **Hatch angle matches QGIS.** Hatches were mirrored (`\` instead of `/`) because the tile is drawn
  in image (y-down) coordinates; the angle is now negated so 45° draws `/` like QGIS.
- **Crosshatch support.** Every stacked `LinePatternFill` in a symbol is reproduced, so a 45°+135°
  pair renders as a real diamond grid instead of a single direction.
- **Background colour override.** New optional `background_color` setting; default leaves the
  supplied value unchanged (basemap keeps its own background).
- **Robustness against dangling sources.** A layer that fails to tile is no longer handed to the
  style converter, and `_prune_orphan_layers` drops any layer whose source is missing after merges —
  MapLibre rejects an entire style on a single `source not found`, which previously blanked the map.

### Added — real hatch/pattern fills (0.21.0)
- **QGIS hatch fills now render as actual MapLibre `fill-pattern` hatching**, replacing the
  semi-transparent-solid approximation from 0.20.0. At export time the converter renders a tileable
  power-of-two hatch PNG per distinct pattern (angle, spacing, line width, and colour taken from the
  QGIS `LinePatternFill`), writes them to `patterns/` in the export, and records them in the style's
  `metadata["mapsplat:patterns"]`.
- The viewer loads each pattern on MapLibre's `styleimagemissing` event (`loadImage` → `addImage`).
  Each hatched category is emitted as its **own filtered `fill-pattern` layer** stacked over the
  semi-transparent solid from 0.20.0 — so if an image ever fails to load, the fill degrades to the
  correct colour instead of blanking. Pattern metadata is preserved through the basemap merge.
- Spec-driven decisions (reviewed against the MapLibre style spec): no `fill-gradient` exists and
  `line-gradient` needs a GeoJSON `lineMetrics` source (unavailable for PMTiles), so gradient/
  shapeburst fills remain semi-transparent solids; `fill-pattern` tiles must be power-of-two.

### Fixed — categorized/graduated fidelity (0.20.0)
- **Categorized polygons/lines/points now render every class.** The converter only emitted a
  `match` pair when a category's *bottom* symbol layer was a plain `SimpleFill`/`SimpleLine`/
  `SimpleMarker`; any category whose bottom layer was a hatch (`LinePatternFill`), gradient
  (`ShapeburstFill`), etc. was silently dropped from the match and fell through to the default
  `fill-opacity: 0.0` — i.e. **invisible**. On a 6-class park layer only the one plain-fill class
  showed; the other five vanished. Now a pair is emitted for *every* rendered class.
- **Solid colours are sampled from the top-most visible fill layer, not layer 0.** `symbol.color()`
  returns only the bottom symbol layer, so a symbol with an orange fill stacked over a maroon fill
  came out maroon. New helpers walk the layer stack and take the top-most enabled colour, matching
  what QGIS actually draws. Fixes the pavilion class (was maroon `#48002c`, now orange `#d28945`).
- **Hatch/pattern fills are now see-through instead of opaque.** A hatch (`LinePatternFill`) is
  commonly stacked under an outline-only `SimpleFill` (brush = `NoBrush`). The converter was reading
  that NoBrush layer as an *opaque* solid, so a large hatched polygon (e.g. "park bounds") painted a
  solid block over everything inside it. Now `_polygon_fill_paint` skips NoBrush layers, renders a
  hatch as a **semi-transparent solid** in the pattern's ink colour (opacity ≈ the hatch's line
  density), and honours gradient/shapeburst alpha — so overlapping polygons stay visible, matching
  QGIS. (Real MapLibre `fill-pattern` hatching is a planned follow-up.) Also corrects "moms area"
  (was reading the NoBrush `#6b18e8`; now the shapeburst `#c24dc2` at its true ~0.67 alpha).
- **Graduated renderers** got the same treatment: dropped `interpolate` stops could leave an
  expression with fewer than two stops (an *invalid* MapLibre expression that breaks the whole layer).
  Every range now contributes a stop via the same helpers.
- Sizes stay **faithful to the source numbers** when QGIS specifies them — a real small-but-nonzero
  marker/line keeps its exact converted size; only a genuinely zero/missing value is bumped to a
  visible minimum (marker radius fallback 3 px, line/stroke hairline 1 px) so nothing silently
  vanishes. Point/line opacity now folds in the symbol-level opacity.

### Changed — viewer libraries (0.19.0)
- **Updated the generated viewer to MapLibre GL JS 5.24.0 and PMTiles JS 4.4.1** (from 4.7.1 / 3.2.0)
  so new users on the current versions are supported. The v5 breaking change is `addProtocol`
  (now Promise + AbortController), which pmtiles 4 implements; the standard
  `addProtocol("pmtiles", protocol.tile)` registration is unchanged. Verified end-to-end by exporting
  a real map and rendering the viewer (data layers + streamed Protomaps basemap) in a browser.

### Security / packaging (0.18.1)
- **Removed `install_pmtiles.sh` from the repo and zip.** The plugins.qgis.org scanner flags shell
  installers (it `wget`s a binary and `sudo mv`s it into `/usr/local/bin`), and it's now redundant —
  the CLI is only needed for the *optional offline* basemap mode, and the User Guide + in-app link
  cover installing it. The build's self-check now also **rejects any `.sh`** from the zip.

### Added — basemap without the CLI (0.18.0)
- **Basemap Overlay now has two modes:** **Stream from URL** (default — the viewer loads the basemap
  live from a remote PMTiles URL via range requests; **no `pmtiles` CLI, no install**) and **Download
  & clip offline** (the previous behaviour; clips+embeds for offline use, needs the CLI). Removes the
  biggest barrier to using a basemap, since most users won't have the CLI.
- A small **Test** button checks the basemap source is reachable (URL) or exists (file) before export.
- `basemap.mode` added to the Save/Load **config file** (schema + read + write) and to `QgsSettings`,
  so it round-trips. All new controls carry tooltips.

### Added — dock guidance & help (phase 3)
- In-dock **guidance**: a header intro line, "Required." subtitles under Layers and Output, and an
  empty-state hint when the project has no layers.
- **Help menu** in the dock header → *Open User Guide (PDF)* and *Online docs / source*.
- A bundled, professional **PDF User Guide** (`help/MapSplat_User_Guide.pdf`, generated from
  `docs/USER_GUIDE.md` via `scripts/build_user_guide.sh`) shipped inside the plugin.

## [0.15.0] — 2026-07-11

### Changed — dock UX redesign (phase 1)
- **Output fields (project name + folder) moved onto the Inputs tab**, beside Layers and Export, so a
  whole export configures on **one tab** — no more hopping to the Options tab to run.
- **Refresh button** in the Layers group; `refresh_layer_list` blocks signals during the clear/rebuild
  and **preserves the selection** across a refresh.
- **Zero-config start** — preselects the layers checked/visible in the Layers panel (or the active
  layer) and defaults the output folder to the project folder (else Documents).
- **Live readiness line + Export gating** — a calm blue message lists what's still missing and keeps
  Export disabled until layers + name + folder are set.
- **Version stamp** on the Log tab (`MapSplat vX.Y.Z`, read from metadata) to confirm the loaded build.

### Fixed — dock layer-list crashes & blank list
- **QGIS crash (segfault) when a layer uses a categorized / graduated / rule-based renderer.**
  `_get_symbology_warning` dereferenced symbols owned by the *temporary* category/range/rule
  containers returned by the renderer; once those were garbage-collected the symbol pointers dangled
  → use-after-free. Now **clones** each symbol. (Root-caused with a crash-surviving trace.)
- **Layer list appeared blank** for projects stored in a GeoPackage — `layerTreeRoot().layerOrder()`
  returns empty for them. Now reads from `mapLayers()`, skips invalid layers, and normalises
  `geometryType()` across the QGIS 3 (int) / QGIS 4 (enum) change.
- **Crash during project load** — the `layersAdded`/`layersRemoved` handlers rebuilt the list
  mid-teardown. They are now **debounced** so the refresh runs once, after the load settles.

### Added
- **QGIS-integration test tier** (`test/test_dock_qgis.py`, `scripts/run_qgis_tests.sh`) that
  exercises real layer/renderer objects under QGIS's own Python — including a regression for the
  categorized-polygon crash (proven to fail-fast without the fix). The pure-Python `pytest` suite
  skips it automatically.

## [0.13.1] — 2026-07-10

### Security
- Passes the plugins.qgis.org gates — **Bandit** (0 high/medium), **detect-secrets**, **flake8**.
- Hardened the two `urllib` calls (B310): the offline-asset download refuses non-`https` URLs; the
  basemap HEAD check is already scheme-restricted to `http`/`https`.

### Changed
- **Removed the bundled `go-pmtiles` binary** (17 MB) from the repo and zip — QGIS forbids binaries.
  Install it via `install_pmtiles.sh` or the in-app download link; core vector→PMTiles export uses
  **GDAL's PMTiles driver** (3.8+), so the CLI is only needed for the optional Basemap Overlay.
- **LICENSE corrected to GPL-2.0-or-later** (the previous file was go-pmtiles' BSD, carried over by
  mistake). `experimental=False`; added `qgisMaximumVersion=4.99`; trimmed the metadata changelog.
- Removed the unused compiled Qt resources (`resources.qrc`/`resources.py`) — the icon already loads
  from a file path.

### Added
- `scripts/build_plugin.sh` (self-verifying build), `Makefile`, and a standardized release workflow;
  `ruff.toml` + `setup.cfg` lint config.

## v0.13.0 — 2026-03-24

### Added
- **Config load warning for missing layers** — When loading a config file, any layer names listed under `[export] layer_names` that are not present in the current QGIS project are reported in a `QMessageBox.warning` dialog listing the missing names by bullet point.
- **Attribution field (Viewer tab)** — New text field in the Viewer tab for custom attribution text. The value is passed to MapLibre's `AttributionControl` (`customAttribution` option) at export time. Persisted in `QgsSettings` and in config files under `[viewer] attribution`.
- **Basemap URL/file validation** — When the basemap source field loses focus, the entered URL is checked with an HTTP HEAD request (3 s timeout) or the file path is checked with `os.path.isfile`. An inline red error label appears if the source is unreachable or missing; it clears when valid or when the basemap group is disabled.
- **Popup field customization dialog** — Right-clicking a vector layer in the Layers to Export list opens "Configure popup fields". A dialog with per-field checkboxes lets you choose which fields appear in the MapLibre feature click popup. Field selection is keyed by sanitized source-layer name, persisted in `self._popup_fields`, and written to/read from config files under the new `[popup]` section. Exported HTML filters popup entries via a `popupFieldConfig` JS constant looked up by `feature.sourceLayer`.

### Changed
- **Config file format** — New optional `[popup]` section (layer name → list of visible field names). New `[viewer] attribution` key. Existing config files without these keys continue to load correctly.
- `config_manager.py` — `write_config` now writes the `[popup]` section; `read_config` unquotes quoted TOML keys (needed for layer names with spaces). `write_config` docstring updated.

## v0.12.1 — 2026-03-24

### Fixed
- **Geometry distortion in exported tiles** — Added `-s_srs EPSG:3857` to the `ogr2ogr` command. The GeoPackage is always written by QGIS in EPSG:3857 via `QgsVectorFileWriter` with `options.ct`, but the CRS WKT stored by QGIS is not always recognised by GDAL as exactly EPSG:3857. Without an explicit source CRS, `ogr2ogr` was applying a non-identity Mercator→Mercator reprojection — treating already-projected metre coordinates as geographic degree inputs — producing the shearing/parallelogram distortion visible on polygon layers.

## v0.12.0 — 2026-03-24

### Changed
- **New "Inputs" tab** — Layers to Export, Advanced Options (collapsible), Save/Load Config, and Export button are now on a dedicated first tab called "Inputs". This makes the most-used controls immediately visible without scrolling.
- **"Options" tab** — The old "Export" tab is renamed "Options" and now contains only the collapsible Export Options, Basemap Overlay, and Output sections.
- **Progress moved to Log tab** — Progress bar, Cancel button, and export status label are now at the top of the Log tab. Clicking Export switches to Log tab, where you can see both the progress indicators and the live log in one place.

## v0.11.0 — 2026-03-23

### Added
- **Persistent settings via QgsSettings** — all UI state (export mode, zoom, all 7 viewer checkboxes, label placement, map dimensions, offline bundle, advanced legend, basemap source and style, output folder, last config directory) is now saved to QGIS's profile-scoped `QgsSettings` automatically. Settings are restored on plugin open. Loading a config file overrides persisted values and then re-saves them as the new persisted state. Migrated from `QSettings("MapSplat","MapSplat")` — profile isolation now works correctly.
- **pmtiles CLI missing dialog** — when Basemap Overlay is enabled and the `pmtiles` binary is not found on PATH, a clear `QMessageBox` appears before export starts with a link to the releases page. Previously only logged a message to the Log tab.

## v0.10.0 — 2026-03-23

### Added
- **Collapsible sections** — Export Options, Basemap Overlay, and Output sections on the Export tab now use the same arrow-toggle pattern as Advanced Options. Basemap is collapsed by default; Export Options and Output are expanded.
- **"Current map view" extent** — new option in the export extent dropdown that captures the QGIS canvas extent at export time. Set as the default selection. Canvas extent is transformed to EPSG:4326 on the main thread before the export worker starts.
- **Basemap size warning in tile estimate** — when the Basemap Overlay group is enabled, the tile estimate label appends "+ basemap (size unknown)" to remind that basemap tiles are not included in the estimate.

### Fixed
- **Legend / source-layer case preserved** — layer names with mixed case (e.g. `Cumberland_Points`) now appear with original capitalisation in the legend and style.json `source-layer` values. Both `_sanitize_layer_name` (exporter) and `_sanitize_name` (style converter) had a forced `.lower()` that is now removed.
- **SVG marker warning false positive** — Story 11 symbology warnings no longer flag layers using SVG markers; SVG markers are correctly exported as sprites. Only font markers, heatmap, point displacement, and point cluster renderers are flagged.
- **Config load refreshes layer list** — `_load_config` now calls `refresh_layer_list()` before applying settings so the layer list reflects the current project state.
- **Data clipped to export extent** — vector layers are spatially filtered to 200% of the export bounding box (50% expansion on each side) before the GeoPackage/ogr2ogr step via `QgsVectorFileWriter.SaveVectorOptions.filterExtent`. Large layers with global extent no longer send the entire dataset through the pipeline.

## v0.9.0 — 2026-03-23

### Added
- **Symbology warnings** (Story 11) — the layer list now shows a ⚠ warning icon on layers whose symbology won't translate well to PMTiles/MapLibre. Warns for: heatmap renderer, point displacement renderer, point cluster renderer, SVG markers, and font markers. Tooltip on each flagged item explains the specific limitation. Warnings refresh whenever the layer list is repopulated.
- **Tile count estimator** (Story 10) — a live label below the Max Zoom slider shows `~N tiles · est. X MB` based on the combined bounding box of all selected layers and the current zoom level. Updates on zoom change or selection change. Shows "Select layers to see tile estimate" when no layers are selected. Tooltip notes that basemap tiles are excluded from the estimate.

## v0.8.0 — 2026-03-23

### Added
- **Open Folder button** — appears in the pinned footer next to Export after a successful export; opens the output directory in the system file manager via `QDesktopServices`. Hides when the next export starts.
- **Export status label** — italic status text appears below the progress bar during export showing the current operation ("Processing layer 2/5: Roads", "Converting to PMTiles", etc.). Disappears on completion.
- **Collapsible Advanced Options** — `QToolButton` toggle collapses/expands a section containing "Style only" and "Save log" checkboxes, reducing Export tab height.
- **Map Dimension Presets** — dropdown with Full window, 800×600, 800×900, 1024×768, 1920×1080, Custom. Selecting a preset updates the spinboxes; editing a spinbox switches to Custom automatically.
- **Tooltips** — comprehensive tooltips added to all interactive controls: layer list, Select All/None, Export mode, Max zoom, Export style.json, Import style, Basemap group, URL/file radios, basemap source and style fields, Project name, Output folder, Save/Load config, Export/Open Folder/Cancel buttons, all seven viewer checkboxes, Label placement, Advanced Legend, Width/Height spinboxes, Offline bundle checkbox.
- **SVG legend icon** — point layers using SVG markers now show the actual rendered icon in the legend swatch. The icon is base64-encoded at export time and embedded in the layer's `metadata` in style.json; no runtime MapLibre internals required.
- **Legend layer picker fix** — icon symbol layers now take priority over label-only symbol layers when selecting the representative layer for a legend group, preventing label text-color from appearing as the swatch color.

> **Versioning note (from 2026-03-22):** Versions v0.5.x–v0.6.x used PATCH increments for many new features
> (labels, SVG sprites, advanced legend, scale visibility, offline bundling) that are MINOR under semver.
> From v0.7.0 onward, use MINOR for all additive features and PATCH only for bug fixes.

## v0.7.0 — 2026-03-23

### Changed
- **QGIS 4 / Qt6 only** — removed all Qt5/Qt6 compatibility shims. The plugin
  now requires QGIS 4 (Qt6) and will no longer load under QGIS 3 (Qt5).

### Removed
- `QAction` import try/except shim (`mapsplat.py`) — `QAction` is imported
  directly from `qgis.PyQt.QtGui` (its Qt6 location).
- `_RightDockWidgetArea` try/except shim (`mapsplat.py`) — replaced with direct
  `Qt.DockWidgetArea.RightDockWidgetArea`.
- `_ItemIsEnabled`, `_UserRole`, `_MultiSelection` try/except shims
  (`mapsplat_dockwidget.py`) — replaced with direct Qt6-scoped enums.
- Unused `Qgis` import from `mapsplat_dockwidget.py` and `style_converter.py`.

### Fixed
- `QFrame.NoFrame` → `QFrame.Shape.NoFrame` (Qt6 scoped enum).
- `QFrame.HLine` → `QFrame.Shape.HLine` (Qt6 scoped enum).
- `QFrame.Sunken` → `QFrame.Shadow.Sunken` (Qt6 scoped enum).

### Build
- `resources.py` must be (re)compiled with `pyrcc6` — run `make compile` inside
  the QGIS Python environment before deploying.

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
