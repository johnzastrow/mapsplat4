# MapSplat - Requirements Specification

**Version:** 0.6.16
**Date:** 2026-03-22
**Note:** Updated to reflect current implementation state. Original v0.1.1 spec (Feb 2026) is preserved in git history.

## Overview

**MapSplat** is a QGIS 4 plugin that exports QGIS projects to self-contained, static web map packages using PMTiles format. The output can be hosted on any web server or cloud storage that supports HTTP Range Requests.

---

## Core Requirements

### Target Platform

| Requirement | Value |
|-------------|-------|
| Minimum QGIS Version | 4.0+ |
| Minimum GDAL Version | 3.8+ (native PMTiles support required) |
| Python Version | 3.12+ (as bundled with QGIS 4) |
| Qt Version | Qt6 |

### Output Format

| Component | Format |
|-----------|--------|
| Vector data | PMTiles (.pmtiles) |
| Raster basemaps | PMTiles (.pmtiles) via `pmtiles extract` CLI |
| Styling | MapLibre Style JSON v8 (.json) |
| Viewer | Self-contained HTML + MapLibre GL JS v4.7.1 |
| Projection | EPSG:3857 (Web Mercator) |

---

## Functional Requirements

### FR-1: Layer Selection

- User can select which layers to export from current QGIS project
- Support for vector layers (points, lines, polygons)
- Select All / Select None buttons; layer count indicator ("X of Y layers selected")
- User can choose export mode:
  - Single PMTiles file (all layers as separate source-layers)
  - Separate PMTiles file per layer
- Export extent: any layer's bounding box may be used as the export extent instead of the combined extent

### FR-2: Symbology Conversion

**Supported renderers:**

| Renderer Type | Support Level |
|---------------|---------------|
| Single Symbol (fill, line, marker) | Full |
| Categorized | Full — MapLibre `match` expressions with null-category handling |
| Graduated | Full — MapLibre `interpolate` expressions for smooth transitions |
| Rule-based | Full — filter expression conversion (=, !=, <, >, <=, >=, IS NULL, IS NOT NULL) |
| SVG markers (single symbol) | Full — raster sprite atlas (sprites.png + sprites.json) |
| SVG markers (categorized/graduated) | Fallback to color-correct circle; logged |
| Simple marker shapes (square, diamond, etc.) | Fallback to circle with correct color/size |
| Font markers | Fallback to circle |
| Labels | Full — see FR-7 |
| Heatmap | Fallback |
| Point Displacement | Fallback |

**Scale-dependent visibility:** `minScale`/`maxScale` are converted to MapLibre `minzoom`/`maxzoom` using `log2(279541132 / scale_denominator)` (corrected for MapLibre 512px tiles). Clamped to [0, 24].

**Fallback behavior:** Unsupported symbology extracts the darkest available color from the symbol. User is notified; export proceeds.

### FR-3: CRS Handling

- Automatic reprojection to EPSG:3857 (Web Mercator)
- Source layers in any CRS are transformed automatically
- No user intervention required for CRS conversion

### FR-4: Style Management

- Export generates MapLibre Style JSON v8
- User can choose whether to output separate `style.json` file
- **Import capability:** User can import existing `style.json` for roundtripping via Maputnik
- Imported styles are merged/applied to export
- **Style-only export:** Skip data conversion, regenerate HTML/style from existing PMTiles

### FR-5: Output Package

Generated output folder structure:

```
[project_name]_webmap/
├── index.html              # Self-contained viewer with demarcation comments for embed copy
├── style.json              # MapLibre style (optional)
├── data/
│   ├── layers.pmtiles      # Vector data (or per-layer files)
│   └── basemap.pmtiles     # Basemap PMTiles (basemap overlay mode)
├── lib/
│   ├── maplibre-gl.js      # Bundled MapLibre (offline mode)
│   └── maplibre-gl.css
├── sprites.png             # Sprite atlas (only when SVG single-symbol layers present)
├── sprites.json
├── serve.py                # Local HTTP server with Range request support
└── README.txt              # Deployment instructions
```

### FR-6: Viewer Features

The generated `index.html` includes:
- Full-screen map display
- Layer visibility toggles with legend swatches (color, shape adapts to geometry type)
- Advanced legend: per-category swatches parsed from `match`/`step`/`interpolate` expressions
- Basic zoom controls
- Click-to-identify feature popups (showing attributes)
- Map dimension controls: fixed pixel size or responsive full-window (default)
- Configurable map controls (7 checkboxes): scale bar, geolocate, fullscreen, coordinate display, zoom display, reset-view, north-up reset
- Label placement mode: match QGIS exact positions or MapLibre auto-placement
- `<!-- BEGIN MAPSPLAT -->` / `<!-- END MAPSPLAT -->` demarcation for embed copy

### FR-7: Labels

Labels are extracted from QGIS layer settings and converted to MapLibre symbol layers:

| Property | Support |
|---|---|
| Text field | Full |
| Font family, size, color | Full (Noto Sans Regular/Medium/Italic) |
| Bold / italic | Full |
| Halo (buffer) color, width, opacity | Full (only when QGIS buffer enabled) |
| Text opacity | Full |
| Capitalization (upper/lower) | Full |
| Line height | Full |
| Word wrap | Full |
| Multiline alignment | Full |
| Point label placement (quadrant + offset) | Full |
| Line label placement (curved/horizontal) | Full |
| Label placement auto (collision avoidance) | Full (`text-variable-anchor`) |

Unsupported: drop shadows, callouts, complex expressions, scale-based label visibility, letter spacing.

### FR-8: Basemap Overlay Mode

When enabled, combines a Protomaps basemap with QGIS business layers:

- Source: remote URL or local `.pmtiles` file
- Uses `pmtiles extract` CLI to download a region-clipped subset
- Merges basemap style.json with business layer style
- Business sources and layers injected into merged style
- Uses single local sprite (`./sprites`) for business icon layers

### FR-9: Configuration Save/Load

- TOML-format config files (human-editable)
- Stores `[export]`, `[basemap]`, and `[viewer]` sections
- Layers referenced by name (portable across sessions and machines)
- Unknown keys silently ignored for forward compatibility
- Warns when loaded config references layers not in current project

### FR-10: Offline Bundling

- Optional "Bundle JS/CSS for offline viewing" checkbox
- Downloads MapLibre GL JS, CSS, and pmtiles.js from unpkg.com at export time
- Falls back to CDN links with warning if download fails

---

## User Interface Requirements

### UI-1: Plugin Interface

- **Type:** Dockable widget panel
- **Location:** Default to right dock area
- Persistent during QGIS session

### UI-2: Widget Tabs

1. **Export tab** — layer list, export options, basemap overlay, output settings; wraps in QScrollArea on small screens; Save/Load Config and Export button pinned below scroll area
2. **Log tab** — timestamped log output; auto-shown when export starts
3. **Viewer tab** — 7 map control checkboxes, label placement mode, map dimensions
4. **Offline tab** — offline asset bundling toggle

### UI-3: Feedback

- Progress bar during export
- Current operation status text (stage + layer name)
- Per-layer success/failure tracking in separate-file mode
- Clear error messages: GDAL version, write permission, missing pmtiles CLI, invalid style.json import

---

## Non-Functional Requirements

### NFR-1: Performance

- Export of typical project (5–10 layers, <100 MB data) completes in under 60 seconds
- UI remains responsive during export (QProcess polling pattern — not blocking subprocess)

### NFR-2: Offline Capability

- Optional: MapLibre GL JS and pmtiles.js bundled locally
- Default: CDN links (unpkg.com)

### NFR-3: Portability

- Output folder can be copied to any static web server
- No server-side code required
- Works with: nginx, Apache, Caddy, S3, GitHub Pages, etc.

---

## Dependencies

### Required (bundled with QGIS 4)

- PyQt6 (via `qgis.PyQt`)
- GDAL 3.8+ (for PMTiles driver in ogr2ogr)
- Python 3.12+

### Optional External Tools

- `pmtiles` CLI — required only for basemap overlay mode (extract region from source PMTiles)

### Bundled in Plugin

- MapLibre GL JS v4.7.1 (offline mode)
- HTML/CSS templates
- `serve.py` — local HTTP server with Range request support

---

## Out of Scope

- Direct upload to web servers (Phase 2)
- 3D terrain/buildings
- Time-based animations
- Raster layer export (vector only)
- Complex QGIS expression functions in rule filters (AND/OR compound rules)
- Blend modes (not supported by MapLibre)
