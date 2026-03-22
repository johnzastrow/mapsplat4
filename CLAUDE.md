# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What MapSplat Does

MapSplat exports QGIS projects to self-contained static web map packages. It converts vector layers to PMTiles format, converts QGIS symbology to MapLibre GL Style JSON, and generates a standalone `index.html` viewer. Output is a directory containing `data/` (PMTiles), `lib/` (MapLibre assets), `index.html`, `style.json`, and a `serve.py` for local testing.

## Build & Deploy Commands

```bash
# Compile Qt resources (must run before first use or after editing resources.qrc)
make compile   # runs: pyrcc5 -o resources.py resources.qrc

# Deploy plugin to default QGIS profile
make deploy    # copies to ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/mapsplat/

# Remove deployed plugin
make remove

# Create distributable ZIP
make package   # produces mapsplat.zip

# Clean compiled/cached files
make clean     # removes *.pyc, __pycache__, .pytest_cache, resources.py

# Windows deployment (alternative to Makefile)
deploy.bat     # CMD version
deploy.ps1     # PowerShell version
```

## Tests

```bash
make test                          # runs: python -m pytest test/ -v
python -m pytest test/ -v          # same
python -m pytest test/test_style_converter.py -v  # single file
python -m unittest discover test/  # without pytest
```

Tests are in `test/`. Only code that doesn't require a live QGIS instance is unit-tested (pure-Python helpers and style converter output structure). QGIS-dependent logic requires manual testing inside QGIS.

## Module Architecture

Five Python modules, clear separation of concerns:

| Module | Class | Role |
|---|---|---|
| `__init__.py` | — | QGIS entry point; `classFactory(iface)` |
| `mapsplat.py` | `MapSplat` | Plugin lifecycle: toolbar, menu, dockwidget init |
| `mapsplat_dockwidget.py` | `MapSplatDockWidget` | All UI; validates settings, fires export |
| `exporter.py` | `MapSplatExporter(QObject)` | Orchestrates full export workflow |
| `style_converter.py` | `StyleConverter` | QGIS renderer → MapLibre Style JSON v8 |

### Export Workflow (`exporter.py`)

1. Create output directories (`data/`, `lib/`)
2. Export selected vector layers to GeoPackage via `QgsVectorFileWriter`
3. Convert GeoPackage → PMTiles via `ogr2ogr` subprocess (GDAL 3.8+ required)
4. Delete intermediate GeoPackage
5. Convert QGIS styles via `StyleConverter.convert()`
6. Merge any imported `style.json`
7. Write `index.html`, `style.json`, MapLibre assets, `README.txt`, `serve.py`

Signals emitted: `progress(int)`, `log_message(str, str)`, `finished(bool, str)`.

All layers are auto-transformed to EPSG:3857 before export.

### Style Conversion (`style_converter.py`)

Supports: Single Symbol, Categorized, Graduated, Rule-based renderers.
Converts fill, line, marker symbol layers. Extracts labels (text field, font, halo).
Unit conversion constant: `MM_TO_PX = 3.78` (mm → pixels at 96 DPI).

Rule-based filter syntax supports: `=`, `!=`, `<`, `>`, `<=`, `>=`, `IS NULL`, `IS NOT NULL`.

### Qt5/Qt6 Compatibility

`mapsplat.py` includes shims for enum differences between Qt5/Qt6:
- `QAction` import location
- `RightDockWidgetArea`, `ItemIsEnabled`, `UserRole` enum scoping

Always use the compatibility pattern already in `mapsplat.py` when adding new Qt enum references.

## Runtime Settings Dictionary

All export options are passed as a dict from the UI to `MapSplatExporter`:

```python
settings = {
    "layer_ids": [],           # Selected QgsMapLayer IDs
    "output_folder": "",       # Base output directory
    "project_name": "",        # Output subdirectory name
    "single_file": True,       # True = one PMTiles, False = per-layer PMTiles
    "style_only": False,       # Skip data export, generate HTML/style only
    "export_style_json": True, # Write style.json to disk
    "imported_style_path": None, # Path to merge into generated style (standalone mode)
    "max_zoom": 6,             # Tile zoom max (4–18)
    # Basemap overlay mode (0.3.0+)
    "use_basemap": False,      # Enable basemap overlay mode
    "basemap_source_type": "url",  # "url" or "file"
    "basemap_source": "",      # URL or local path to source Protomaps .pmtiles
    "basemap_style_path": "",  # Path to Protomaps-compatible basemap style.json
}
```

### Basemap Overlay Mode (0.3.0+)

When `use_basemap` is True the export workflow adds two steps before style conversion:

1. **`_check_pmtiles_cli()`** — verifies the `pmtiles` CLI binary is on PATH.
2. **`_extract_basemap(output_dir, bounds)`** — runs `pmtiles extract <source> data/basemap.pmtiles --bbox=... --maxzoom=...` using the QProcess polling pattern; source may be a URL or a local path.
3. **`_merge_business_into_basemap(basemap_style_path, business_style_json)`** — loads the basemap style.json, redirects its remote protomaps tile URL to `pmtiles://data/basemap.pmtiles`, injects business data sources, appends overlay layers (skipping `background`).

Standalone mode (basemap unchecked) is fully backward-compatible.

## Versioning

Bump `__version__` in all five Python modules and `metadata.txt` together. Update `docs/CHANGELOG.md`. Follow semver: PATCH for fixes, MINOR for new features, MAJOR for breaking changes.
