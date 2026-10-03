# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What MapSplat Does

MapSplat exports QGIS projects to self-contained static web map packages. It converts vector layers to PMTiles format, converts QGIS symbology to MapLibre GL Style JSON, and generates a standalone `index.html` viewer. Output is a directory containing `data/` (PMTiles), `lib/` (MapLibre assets), `index.html`, `style.json`, and a `serve.py` for local testing.

## Build & Deploy Commands

```bash
make help        # list targets
make check       # every publish gate: ruff + flake8, bandit, detect-secrets, headless tests
make build       # scripts/build_plugin.sh -> mapsplat.zip (self-verifying: required files present,
                 # no binaries/docs/cache/shell scripts)
make clean       # remove caches and built artefacts
make tag V=x.y.z # tag + push; CI builds the zip and the GitHub Release

# Install into a local QGIS 4 profile for testing (same file list as the release zip):
deploy.ps1       # PowerShell (Windows); deploy.ps1 -Profile <name>
deploy.bat       # CMD (Windows);        deploy.bat <profile>
# Linux/macOS: unzip mapsplat.zip into ~/.local/share/QGIS/QGIS4/profiles/default/python/plugins/
```

The release file list lives in `scripts/build_plugin.sh`; `deploy.ps1` and `deploy.bat` must list the
same files (`test/test_deploy_lists.py` fails if they drift). Icons load from a file path: no compiled
Qt resources (plugins.qgis.org rejects them).

Other scripts:

- `scripts/run_qgis_tests.sh`: QGIS-integration tests under QGIS's own Python (headless).
- `scripts/build_user_guide.sh`: regenerate `help/MapSplat_User_Guide.pdf` from `docs/USER_GUIDE.md`.
- `scripts/gen_basemap_styles.mjs`: regenerate `basemap_styles/*.json` from `@protomaps/basemaps`
  (instructions in the file header).

## Tests

```bash
make test                                   # headless suite CI runs (conftest.py mocks qgis)
uv run --no-project --with pytest python -m pytest test/ -q
bash scripts/run_qgis_tests.sh              # real QGIS 4 (needs QGIS installed; MAPSPLAT_QGIS_TEST=1)
```

`test/` holds both tiers. The headless suite covers pure-Python logic (style converter, layer order,
basemap helpers and shipped styles, config manager, viewer controls, deploy lists). `test_dock_qgis.py`
runs the dock against real layers and renderers; it is skipped unless `MAPSPLAT_QGIS_TEST=1`, which
`run_qgis_tests.sh` sets. A segfault kills that process, so judge it by the unittest OK/FAILED line.

## Module Architecture

| Module | Class / contents | Role |
|---|---|---|
| `__init__.py` | — | QGIS entry point; `classFactory(iface)` |
| `mapsplat.py` | `MapSplat` | Plugin lifecycle: toolbar, menu, dockwidget init |
| `mapsplat_dockwidget.py` | `MapSplatDockWidget` | All UI; validates settings, fires export |
| `exporter.py` | `MapSplatExporter(QObject)`, `generate_html_viewer()`, `sort_layers_by_tree_order()` | Orchestrates the export; writes the viewer |
| `style_converter.py` | `StyleConverter` | QGIS renderer → MapLibre Style JSON v8 |
| `config_manager.py` | `read_config()`, `write_config()` | Save/Load config files (TOML-like) |
| `log_utils.py` | `format_log_line()` | Log line formatting |
| `basemap_helpers.py` | constants + pure functions | Built-in Protomaps styles, latest daily build, `pmtiles extract` command, CORS/streamability checks |

Data shipped with the plugin: `help/` (PDF user guide, `basemaps.html` guide), `basemap_styles/`
(five Protomaps styles and their licence).

### Export Workflow (`exporter.py`)

1. Create output directories (`data/`, `lib/`)
2. Basemap: clip with `pmtiles extract` (Download & clip mode), or note a streamed / XYZ source
3. Export selected vector layers to GeoPackage via `QgsVectorFileWriter`
4. Convert GeoPackage → PMTiles via `ogr2ogr` subprocess (GDAL 3.8+ required)
5. Convert QGIS styles via `StyleConverter.convert()`; order layers to match the QGIS layer tree
6. Merge into the basemap style, add an XYZ basemap, or merge an imported `style.json`
7. Write `index.html`, `style.json`, MapLibre assets, `README.txt`, `serve.py`

Signals emitted: `progress(int)`, `log_message(str, str)`, `finished(bool, str)`.

All layers are auto-transformed to EPSG:3857 before export.

### Style Conversion (`style_converter.py`)

Supports: Single Symbol, Categorized, Graduated, Rule-based renderers.
Converts fill, line, marker symbol layers. Extracts labels (text field, font, halo).
Unit conversion constant: `MM_TO_PX = 3.78` (mm → pixels at 96 DPI).

Rule-based filter syntax supports: `=`, `!=`, `<`, `>`, `<=`, `>=`, `IS NULL`, `IS NOT NULL`.
Each rule's own min/max scale becomes `minzoom`/`maxzoom`, narrowed by parent rules and intersected
with the layer's scale-based visibility (0.44.0).

### Qt6 only

This plugin targets QGIS 4 (Qt6). Always use fully scoped enums (`Qt.AlignmentFlag.AlignCenter`,
`QMessageBox.StandardButton.Yes`) and `.exec()`.

## Runtime Settings Dictionary

All export options are passed as a dict from the UI to `MapSplatExporter` (main keys):

```python
settings = {
    "layer_ids": [],             # Selected QgsMapLayer IDs
    "output_folder": "",         # Base output directory
    "project_name": "",          # Output subdirectory name
    "single_file": True,         # True = one PMTiles, False = per-layer PMTiles
    "style_only": False,         # Skip data export, generate HTML/style only
    "export_style_json": True,   # Write style.json to disk
    "imported_style_path": None, # Path to merge into generated style (no-basemap mode)
    "max_zoom": 6,               # Tile zoom max (4–18)
    "extent_layer_id": None,     # Layer whose extent bounds the export (None = data extent)
    "extent_bounds": None,       # [W, S, E, N] captured from the map view, when chosen
    # Basemap overlay
    "use_basemap": False,
    "basemap_mode": "stream",    # "bundle" (Download & clip) | "stream" | "xyz"
    "basemap_source_type": "url",  # "url" or "file" (bundle mode)
    "basemap_source": "",        # Protomaps build URL / local .pmtiles / XYZ template
    "basemap_style_path": "",    # Resolved style.json: a built-in basemap_styles/ file or a custom path
    "basemap_attribution": "",   # XYZ provider attribution
}
```

The dock resolves `basemap_style_path` from its *Basemap style* choice (`basemap_helpers.BUILTIN_FLAVORS`
or "custom"); the choice itself persists as `basemap_style_choice` in QgsSettings and as
`[basemap] style` in saved configs. Every user-facing option must persist in all three places:
QgsSettings, the config file (schema in `config_manager.py` + read + write), and this dict.

### Basemap Overlay

- **Download & clip (`bundle`)** — `_check_pmtiles_cli()`, then `_extract_basemap(output_dir, bounds)`
  runs `pmtiles extract <source> data/basemap.pmtiles --bbox=... --maxzoom=...` (QProcess polling;
  results cached by source + bbox + max zoom). The dock's *Copy extract command* uses
  `basemap_helpers.extract_command()` with the same bounds.
- **Stream (`stream`)** — the viewer reads a remote PMTiles live. It needs CORS on the host;
  Protomaps daily builds (`build.protomaps.com`) allow only `maps.protomaps.com`, so they cannot be
  streamed. The dock's *Test* probes CORS, and exporting a daily build in this mode asks first.
- **XYZ (`xyz`)** — `_add_xyz_basemap()` adds a raster source; no style or CLI needed.
- `_merge_business_into_basemap(basemap_style_path, business_style_json)` loads the basemap style,
  points its vector source at the clipped file or streamed URL, injects business sources and
  appends overlay layers (skipping `background`).

User-facing help: `help/basemaps.html`, opened by the **?** button beside *Basemap Overlay* and
published to https://johnzastrow.github.io/mapsplat4/basemaps.html by `.github/workflows/pages.yml`.

## Versioning

Bump `__version__` in `__init__.py`, `mapsplat.py`, `mapsplat_dockwidget.py`, `exporter.py` and
`basemap_helpers.py`, and `version=` in `metadata.txt` together (`config_manager.py`, `log_utils.py`
and `style_converter.py` keep their own module versions). Add entries to `docs/CHANGELOG.md` and the
`changelog=` in `metadata.txt`. Follow semver: PATCH for fixes, MINOR for new features, MAJOR for
breaking changes. Rebuild the PDF guide when `docs/USER_GUIDE.md` changes.
