# MapSplat Development Plan

**Version:** 0.1.1
**Last Updated:** 2026-02-16

## Overview

MapSplat is a QGIS plugin that exports projects to self-contained static web maps using PMTiles format and MapLibre GL JS.

---

## Development Phases

### Phase 1: Core Export Functionality (v0.1.x - v0.3.x)

**Goal:** Reliable export of vector layers with basic symbology to working web maps.

#### v0.1.x - Proof of Concept (Current)
- [x] Plugin scaffold and UI framework
- [x] Dockable widget with layer selection
- [x] Basic export pipeline (GeoPackage → PMTiles)
- [x] Style converter skeleton
- [ ] Validate ogr2ogr PMTiles generation
- [ ] Bundle MapLibre GL JS assets for offline use
- [ ] End-to-end testing with sample data

#### v0.2.x - Symbology Completeness
- [ ] Improve single symbol extraction (opacity, stroke width)
- [ ] Complete categorized renderer support
- [ ] Complete graduated renderer support
- [ ] Handle null/empty category values
- [ ] Zoom-level based styling (minzoom/maxzoom)
- [ ] Line dash patterns
- [ ] Basic fill patterns (hatching)

#### v0.3.x - Multi-Layer & Options
- [ ] Separate PMTiles per layer option
- [ ] Layer ordering control
- [ ] Layer visibility toggles in viewer
- [ ] Configurable zoom range (min/max zoom)
- [ ] Configurable tile simplification

---

### Phase 2: Raster Support (v0.4.x - v0.5.x)

**Goal:** Export raster layers as basemap tiles.

#### v0.4.x - Raster Tiles
- [ ] Raster layer detection and selection
- [ ] Raster to PMTiles conversion
- [ ] Raster/vector layer ordering
- [ ] Raster opacity support

#### v0.5.x - External Basemaps
- [ ] Configure external basemap URLs (OSM, etc.)
- [ ] Basemap switcher in viewer
- [ ] Attribution handling

---

### Phase 3: Advanced Features (v0.6.x - v0.8.x)

**Goal:** Polish and professional features.

#### v0.6.x - Style Roundtripping
- [ ] Robust style.json import
- [ ] Style merge strategies (replace, merge, overlay)
- [ ] Preserve imported layer ordering
- [ ] Style validation

#### v0.7.x - Viewer Enhancements
- [ ] Legend generation
- [ ] Layer control panel
- [ ] Fullscreen toggle
- [ ] Share/embed code generation
- [ ] Print view

#### v0.8.x - Performance & Polish
- [ ] Progress reporting improvements
- [ ] Cancellation support
- [ ] Large dataset handling
- [ ] Memory optimization
- [ ] Error recovery

---

### Phase 4: Direct Publishing (v0.9.x - v1.0.x)

**Goal:** Optional direct upload to web servers (stretch goal).

#### v0.9.x - Upload Integration
- [ ] SFTP/SCP upload option
- [ ] Credential storage (secure)
- [ ] Upload progress tracking
- [ ] Incremental updates

#### v1.0.0 - Production Release
- [ ] Comprehensive testing
- [ ] Documentation complete
- [ ] Plugin repository submission
- [ ] Performance benchmarks

---

## Architecture Decisions

### Data Flow

```
QGIS Project
    │
    ▼
┌─────────────────┐
│  Layer Selection │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Export to GPKG  │  (QgsVectorFileWriter)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Convert to      │  (ogr2ogr -f PMTiles)
│  PMTiles         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Style Conversion│  (StyleConverter)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Generate HTML   │  (Templates)
│  Viewer          │
└────────┬────────┘
         │
         ▼
    Output Folder
```

### Key Design Choices

1. **ogr2ogr for PMTiles**: Use GDAL's native PMTiles driver (3.8+) rather than bundling Tippecanoe. Simpler dependency management.

2. **Intermediate GeoPackage**: Export to GPKG first, then convert to PMTiles. Allows CRS transformation and data validation before tiling.

3. **Template-based HTML**: Generate HTML from templates rather than building DOM. Easier to maintain and customize.

4. **Style Fallbacks**: Unsupported symbology falls back to defaults rather than failing. Users get output even if not perfect.

5. **Offline-First**: Bundle MapLibre assets locally. Web maps should work without internet.

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| QGIS | 3.40+ | Host environment |
| GDAL | 3.8+ | PMTiles driver |
| PyQt5 | (bundled) | UI framework |
| MapLibre GL JS | 4.x | Web rendering |
| PMTiles JS | 3.x | Tile protocol |

---

## Testing Strategy

### Unit Tests
- Style converter color extraction
- Name sanitization
- Bounds calculation

### Integration Tests
- Full export pipeline with sample layers
- Various renderer types
- CRS transformation

### Manual Testing
- UI responsiveness
- Generated viewer functionality
- Cross-browser compatibility

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| GDAL version too old | Check version at startup, warn user |
| Large datasets timeout | Configurable timeout, progress feedback |
| Complex symbology loss | Clear documentation, fallback behavior |
| Web server CORS issues | README with CORS configuration guides |

---

## Milestones

| Version | Target | Description |
|---------|--------|-------------|
| 0.1.0 | Done | Plugin scaffold |
| 0.2.0 | TBD | Complete symbology support |
| 0.3.0 | TBD | Multi-layer options |
| 0.5.0 | TBD | Raster support |
| 0.7.0 | TBD | Viewer enhancements |
| 1.0.0 | TBD | Production release |
