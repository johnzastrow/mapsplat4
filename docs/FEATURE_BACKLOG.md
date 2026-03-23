# MapSplat4 - Feature Backlog

Unordered list of desired usability improvements. Prioritization and implementation details are in [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md).

---

## QGIS4 Compatibility *(Complete before any other work)*

### Remove Qt5/Qt6 Compatibility Shims *(Phase 0)*
- [ ] Remove Qt5/Qt6 shims from `mapsplat.py` (no longer needed for Qt6-only)
- [ ] Remove `QAction` import location shim
- [ ] Remove `RightDockWidgetArea`, `ItemIsEnabled`, `UserRole` enum scoping shims

### Qgis.MessageLevel Enum Migration *(Phase 0)*
- [ ] Update all `Qgis.Info`, `Qgis.Warning`, `Qgis.Critical`, `Qgis.Success` to `Qgis.MessageLevel.Info`, etc.
- [ ] Files: `mapsplat_dockwidget.py`, `exporter.py`, `config_manager.py`, `log_utils.py`

### Qt Enum Scoping *(Phase 0)*
- [ ] Update `Qt.AlignCenter` → `Qt.AlignmentFlag.AlignCenter`
- [ ] Update `Qt.UserRole` → `Qt.ItemDataRole.UserRole`
- [ ] Update `Qt.red`, `Qt.darkGreen`, `Qt.darkYellow` → `Qt.GlobalColor.red`, etc.
- [ ] Files: `mapsplat_dockwidget.py`

### Recompile Resources for Qt6 *(Phase 0)*
- [ ] Run `pyrcc6 -o resources.py resources.qrc`
- [ ] Update Makefile: `pyrcc5` → `pyrcc6`

### Verify QGIS4 API Compatibility *(Phase 0)*
- [ ] Test `QgsVectorFileWriter` API unchanged
- [ ] Test `QgsProject.instance()` behavior
- [ ] Test `QgsMapLayer` properties and methods
- [ ] Test layer tree API (`layerTreeRoot().layerOrder()`)

---

## UI Improvements

### Collapsible Advanced Options *(Story 4)*
- [ ] Add collapsible "Advanced Options" section using `QToolButton` with arrow toggle (NOT QGroupBox — QGroupBox enables/disables, not collapses)
- [ ] Target `chk_style_only` and `chk_save_log` specifically — these are the rarely-used controls creating clutter
- [ ] Do NOT add this to the basemap section — it is already a checkable QGroupBox and handles its own visibility correctly
- [ ] Reduce Export tab vertical height on smaller screens

### Quick Presets for Map Dimensions *(Story 5)*
- [ ] Add dropdown with presets: "Full window (responsive)", "800x600", "1024x768", "1920x1080", "Custom"
- [ ] Preset selection updates width/height spinboxes

### Open Output Folder Button *(Story 1)*
- [ ] Add "Open Folder" button to the **pinned footer** (alongside Export button) — appears after a successful export, stays visible until the next export starts
- [ ] Do NOT put this in a success dialog — a dismissed dialog is gone; the pinned footer is persistent
- [ ] Use `QDesktopServices.openUrl()` to open in file explorer

### Better Progress Feedback *(Story 1)*
- [ ] Add status text label showing current operation
- [ ] Display: "Exporting layer 2 of 5: Roads", "Converting to PMTiles", "Generating style.json"
- [ ] Show layer-by-layer progress in separate-file mode

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

### Validate Basemap URL *(Story 3)*
- [ ] Validate basemap URL/file on **focus-out** (NOT on text change — text change fires on every keystroke and would issue an HTTP request per character)
- [ ] Show error immediately if URL unreachable or file missing
- [ ] Prevent export from starting with invalid basemap config

### pmtiles CLI Missing Dialog *(Story 3)*
- [ ] Show QMessageBox with install instructions (not just log)
- [ ] Include link to releases page: https://github.com/protomaps/go-pmtiles/releases

### Export Summary for Partial Failures *(Story 3)*
- [ ] Track which layers succeeded/failed
- [ ] Show summary dialog: "3 of 5 layers exported successfully"
- [ ] List failed layers with error reasons

---

## Configuration

### Persist All Settings *(Story 6)*
- [ ] Resolve `QSettings` vs `QgsSettings` first — the codebase currently uses `QSettings("MapSplat", "MapSplat")` but should use `QgsSettings` (respects QGIS profile isolation). Migrate `last_output_folder` key before adding new ones.
- [ ] Save/restore: export mode, zoom level, style options, all 7 viewer checkboxes, offline bundling toggle, label placement mode
- [ ] Validate restored settings (e.g., layer still exists in project)

### Config Load Warnings for Missing Layers *(Story 6)*
- [ ] Show clear warning when loading config with missing layers
- [ ] List which layers were not found in current project

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

### Inline Help Tooltips *(Story 9)*
- [ ] Audit existing tooltips first — `spin_max_zoom` and `chk_style_only` already have tooltips; do not duplicate
- [ ] Add tooltip to `combo_export_mode` (single vs separate files)
- [ ] Add tooltip to `combo_extent_layer` (what bounding box is used for)
- [ ] Add tooltip to basemap source inputs (URL format, what pmtiles extract does)
- [ ] Add tooltip to basemap style input (what the style.json is for)
- [ ] Add tooltip to dimension preset dropdown (when implemented)
- [ ] Add tooltips to viewer control checkboxes explaining what each control does in the web map

---

## High-Value Additions

### Zoom Level Tile Count Estimator *(Story 10)*
- [ ] Add a live label below `spin_max_zoom`: "~N tiles · est. X MB"
- [ ] Recalculate on zoom change and on layer selection change
- [ ] Compute tile count from combined selected-layer bounding box + zoom: `4^zoom × bbox_fraction_of_world`
- [ ] Estimate size as `tile_count × avg_bytes_per_tile` (conservative constant, e.g. 3–5 KB/tile)
- [ ] Show "select layers to estimate" when no layers are selected
- [ ] All math runs on `QgsRectangle` — no external dependencies

### Per-Layer Symbology Warnings *(Story 11)*
- [ ] After layer list is populated, inspect each layer's renderer type via `QgsVectorLayer.renderer()`
- [ ] Add ⚠ icon to `QListWidgetItem` for layers using: categorized/graduated SVG markers, font markers, complex rule-based expressions, heatmap, point displacement
- [ ] Set tooltip on item explaining the specific limitation (e.g. "SVG markers will render as circles")
- [ ] Re-run check when project layers change

### Popup Field Customization *(Story 12)*
- [ ] Add "Configure Popup Fields..." button or context menu item on layer list items
- [ ] Open dialog showing all fields for the selected layer with checkboxes (default: all checked)
- [ ] Store visible-field selections per layer in config file (new `[popup]` section)
- [ ] Pass visible-field config to `generate_html_viewer()` and filter popup HTML accordingly
- [ ] "Show all / hide all" toggle in dialog
- [ ] Restore selections from config on load
- [ ] **Requires Story 6 first** (config file infrastructure needed for per-layer storage)

### Attribution Field *(Story 13)*
- [ ] Add "Attribution" text field to Viewer tab
- [ ] Default to any attribution found on exported layers via `QgsMapLayer.attribution()`; join multiple with " | "
- [ ] Pass attribution string to `generate_html_viewer()`
- [ ] Add `maplibregl.AttributionControl({ customAttribution: "..." })` to generated viewer when non-empty
- [ ] Save/restore in config file under `[viewer]`

### PMTiles Verify After Export *(Story 14)*
- [ ] After PMTiles creation, run `pmtiles verify` on the output file(s)
- [ ] If verify fails, show error dialog with details from stderr
- [ ] Log verification result to export log
- [ ] Add checkbox "Verify PMTiles after export" in Advanced Options (default: checked)
- [ ] Run verify for each PMTiles file in separate-file mode

### PMTiles Convert (Raster Support) *(Story 15)*
- [ ] Detect raster layers in selection and prompt: "Convert raster layers to PMTiles?"
- [ ] Use `gdal_translate` to convert raster → GeoTIFF
- [ ] Use `pmtiles convert` to convert GeoTIFF → PMTiles
- [ ] Place raster PMTiles below vector layers in style.json
- [ ] Show progress: "Converting raster: 50%"
- [ ] Add to UI: checkbox "Include raster layers" in Export Options
- [ ] Error handling: if GDAL raster support missing, show message with install link

---

## Documentation

### Quick Start Guide *(Deferred)*
- [ ] Create quick start section in README
- [ ] 5 steps from install to first export
- [ ] Include troubleshooting for common issues

### Video Tutorial *(Deferred)*
- [ ] Record screen capture of full workflow
- [ ] Host on YouTube or embed in docs
