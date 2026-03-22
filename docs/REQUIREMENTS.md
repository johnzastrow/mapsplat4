# MapSplat - Requirements Specification

**Version:** 0.1.1
**Date:** 2026-02-16

## Overview

**MapSplat** is a QGIS plugin that exports QGIS projects to self-contained, static web map packages using PMTiles format. The output can be hosted on any web server or cloud storage that supports HTTP Range Requests.

---

## Core Requirements

### Target Platform

| Requirement | Value |
|-------------|-------|
| Minimum QGIS Version | 3.40+ (LTR) |
| Minimum GDAL Version | 3.8+ (native PMTiles support required) |
| Python Version | 3.9+ (as bundled with QGIS 3.40) |
| Target Qt Version | Qt5 (Qt6/QGIS 4.x compatibility as future goal) |

### Output Format

| Component | Format |
|-----------|--------|
| Vector data | PMTiles (.pmtiles) |
| Raster basemaps | PMTiles (.pmtiles) |
| Styling | MapLibre Style JSON (.json) |
| Viewer | Self-contained HTML + bundled MapLibre GL JS |
| Projection | EPSG:3857 (Web Mercator) |

---

## Functional Requirements

### FR-1: Layer Selection

- User can select which layers to export from current QGIS project
- Support for vector layers (points, lines, polygons)
- Support for raster layers (as basemap tiles)
- User can choose export mode:
  - Single PMTiles file (all layers as separate source-layers)
  - Separate PMTiles file per layer

### FR-2: Symbology Conversion

**Supported renderers (Phase 1):**

| Renderer Type | Support Level |
|---------------|---------------|
| Single Symbol | Full |
| Categorized | Full |
| Graduated | Full |
| Rule-based | Fallback to default |
| Heatmap | Fallback to default |
| Point Displacement | Fallback to default |
| Labels | Not supported in Phase 1 |

**Fallback behavior:** Unsupported symbology falls back to simple default style (solid fill/stroke with reasonable colors). User is notified but export proceeds.

### FR-3: CRS Handling

- Automatic reprojection to EPSG:3857 (Web Mercator)
- Source layers in any CRS are transformed automatically
- No user intervention required for CRS conversion

### FR-4: Style Management

- Export generates MapLibre Style JSON file
- User can choose whether to output separate `style.json` file
- **Import capability:** User can import existing `style.json` to reuse/roundtrip styles edited in Maputnik
- Imported styles are merged/applied to export

### FR-5: Output Package

Generated output folder structure:
```
[project_name]_webmap/
├── index.html              # Self-contained viewer
├── style.json              # MapLibre style (optional, user choice)
├── data/
│   ├── layers.pmtiles      # Vector data (or multiple files)
│   └── basemap.pmtiles     # Raster basemap (if included)
├── lib/
│   └── maplibre-gl.js      # Bundled MapLibre (offline capable)
│   └── maplibre-gl.css
└── README.txt              # Deployment instructions
```

### FR-6: Viewer Features

The generated `index.html` should include:
- Full-screen map display
- Layer visibility toggles
- Basic zoom controls
- Click-to-identify feature popups (showing attributes)
- Optional: basemap switcher (if external basemaps configured)

---

## User Interface Requirements

### UI-1: Plugin Interface

- **Type:** Dockable widget panel
- **Location:** Default to right dock area
- Persistent during QGIS session
- Collapsible/expandable

### UI-2: Widget Components

1. **Layer list** - Checkboxes to select layers for export
2. **Export mode selector** - Single file vs. separate files
3. **Style options:**
   - Export separate style.json (checkbox)
   - Import existing style.json (button)
4. **Output settings:**
   - Output folder selector
   - Project name (for folder naming)
5. **Export button** - Triggers export process
6. **Progress indicator** - Shows export progress
7. **Log/status area** - Shows warnings, errors, completion status

### UI-3: Feedback

- Progress bar during export
- Clear error messages for:
  - GDAL version too old
  - Unsupported layer types
  - Write permission errors
- Summary of what was exported and any fallbacks applied

---

## Non-Functional Requirements

### NFR-1: Performance

- Export of typical project (5-10 layers, <100MB data) should complete in under 60 seconds
- UI should remain responsive during export (background processing)

### NFR-2: Offline Capability

- Generated web map works without internet connection
- MapLibre GL JS is bundled locally (not CDN)
- All assets self-contained in output folder

### NFR-3: Portability

- Output folder can be copied to any static web server
- No server-side code required
- Works with: nginx, Apache, Caddy, S3, GitHub Pages, etc.

---

## Development Approach

### Iteration Plan

**v0.1.0 - Proof of Concept**
- Basic UI scaffold
- Single vector layer export to PMTiles
- Single symbol renderer only
- Minimal HTML viewer

**v0.2.0 - Core Symbology**
- Categorized renderer support
- Graduated renderer support
- Multi-layer export

**v0.3.0 - Raster Support**
- Raster layer export as PMTiles
- Basemap integration

**v0.4.0 - Style Roundtripping**
- Export style.json
- Import style.json from Maputnik
- Style merge/override capability

**v0.5.0 - Polish**
- Feature popups in viewer
- Layer toggles
- Error handling improvements
- Documentation

---

## Dependencies

### Required (bundled with QGIS 3.40+)

- PyQt5
- GDAL 3.8+ (for PMTiles driver)
- Python 3.9+

### Bundled in Plugin

- MapLibre GL JS (for offline viewer)
- HTML/CSS templates

### Optional External Tools

- Tippecanoe (for advanced tile generation - future)

---

## Out of Scope (Phase 1)

- Direct upload to web servers (Phase 2)
- Label/text rendering
- 3D terrain/buildings
- Time-based animations
- Vector tile styling of external tile sources
- Print/export to static image

---

## Open Questions (to resolve during development)

1. How to handle very large datasets? (tile size limits, zoom level configuration)
2. Should zoom extent be auto-calculated from layer bounds?
3. Attribution handling - how to preserve/display data attribution?
4. How to handle layer ordering in the web map?
