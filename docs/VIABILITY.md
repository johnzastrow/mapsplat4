# Viability Assessment: MapSplat Plugin

**Date:** 2026-02-16
**Version:** 0.1.1

## Project Overview

The **MapSplat** project aims to create a QGIS plugin that exports QGIS projects with vector data and styling to web-ready formats (PMTiles) that can be served from simple static web servers or cloud storage.

### Goal

Provide an easy "Export as..." type function where a user exports a QGIS project with all of its data and styling to a collection of data, code, and configuration files that can be copied to a simple web server to create an interactive web map.

### Phased Approach

- **Phase 1:** Export to local filesystem (user uploads manually)
- **Phase 2:** Direct web server upload (stretch goal)

---

## Current State

**Files present:**
- `background.md` (~2000 lines) - Extensive research documentation
- `MapDrawer.png` - Potential icon

**No actual plugin code exists yet.** This is purely a research/design document at this stage.

---

## Viability Assessment

### Strengths

1. **Well-researched foundation** - The background document covers PMTiles format, web mapping libraries (MapLibre, Leaflet, OpenLayers), server configuration (Nginx, Caddy), CORS setup, and styling specifications thoroughly.

2. **Clear phased approach** - Starting with local export before tackling direct upload is pragmatic.

3. **Modern technology choice** - PMTiles is an excellent format for serverless/static hosting, requiring only HTTP Range Requests support.

4. **Realistic scope** - The "Export as..." metaphor with minimal clicks is achievable.

5. **Low hosting requirements** - Static file hosting (S3, GitHub Pages, any web server) is sufficient.

---

### Challenges & Concerns

| Challenge | Severity | Notes |
|-----------|----------|-------|
| **QGIS style → MapLibre style conversion** | High | QGIS uses QML/SLD styling; converting to MapLibre Style JSON is non-trivial. No existing complete solution. |
| **ogr2ogr/Tippecanoe dependency** | Medium | PMTiles generation requires external tools (GDAL 3.8+ for PMTiles, or Tippecanoe). Need to handle installation/availability. |
| **Symbol/labeling complexity** | High | QGIS has rich symbology (SVG markers, data-defined properties, label engines) that won't translate 1:1 to web maps. |
| **Raster support** | Medium | Background document focuses on vectors; raster handling adds complexity. |
| **No existing code** | - | Starting from scratch vs. building on existing plugins. |

---

### Technical Feasibility

| Component | Feasibility | Implementation Path |
|-----------|-------------|---------------------|
| Layer selection UI | Easy | Standard PyQGIS dialog |
| Export vectors to GeoPackage | Easy | `QgsVectorFileWriter` |
| Convert to PMTiles | Medium | Call `ogr2ogr -f PMTiles` or bundle Tippecanoe |
| Basic style export | Medium | Parse `QgsFeatureRenderer`, generate JSON |
| Complex symbology | Hard | Rule-based, graduated symbols need careful mapping |
| Generate HTML viewer | Easy | Template-based output |
| Direct upload to server | Medium | SFTP/SCP libraries in Python |

---

## Style Conversion Complexity

QGIS symbology types and their web conversion difficulty:

| QGIS Renderer Type | Web Conversion | Notes |
|--------------------|----------------|-------|
| Single Symbol (fill) | Easy | Direct mapping to MapLibre fill layer |
| Single Symbol (line) | Easy | Direct mapping to MapLibre line layer |
| Single Symbol (marker) | Medium | Simple markers OK; SVG markers problematic |
| Categorized | Medium | Translates to MapLibre `match` expressions |
| Graduated | Medium | Translates to MapLibre `step` or `interpolate` |
| Rule-based | Hard | Complex nested expressions |
| Point Displacement | Hard | No direct equivalent |
| Heatmap | Medium | MapLibre has heatmap layer type |
| Labels | Hard | Different engines, font handling, placement algorithms |

---

## Similar/Related Projects

Projects to reference for implementation patterns:

- **qgis2web** - Exports QGIS projects to Leaflet/OpenLayers (different approach but relevant for style conversion)
- **QGIS MapTiler Plugin** - Generates tiles from QGIS
- **qgis-vectortilelayer-plugin** - For consuming vector tiles

---

## Recommendation

### Verdict: **VIABLE with caveats**

The project is viable for **Phase 1** with these considerations:

1. **Start simple** - Focus on basic single-symbol and categorized renderers first. Don't try to support every QGIS symbology type initially.

2. **Leverage existing tools:**
   - Use `ogr2ogr` (bundled with QGIS) for PMTiles generation
   - Use existing style inspection via PyQGIS API

3. **Template-based output** - Generate a self-contained folder:
   ```
   output/
   ├── data.pmtiles
   ├── style.json
   ├── index.html
   └── README.txt
   ```

4. **Document limitations** - Be explicit about which symbology types are supported.

5. **Target QGIS 3.40+** - Modern QGIS has better APIs for style introspection.

---

## Next Steps (if proceeding)

1. Create plugin scaffold using Plugin Builder
2. Build minimal UI for layer selection
3. Implement basic GeoPackage → PMTiles export via ogr2ogr
4. Create simple style converter for fill/line/circle types
5. Generate template HTML with MapLibre

---

## Open Questions

- What is the minimum viable symbology support?
- Should raster layers be supported in Phase 1?
- What web mapping library should be the default (MapLibre vs Leaflet)?
- How to handle CRS transformations (source CRS → Web Mercator)?
- Should the plugin validate ogr2ogr/GDAL version availability?
