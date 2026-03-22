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
- [ ] Add collapsible "Advanced Options" section for less-frequently-used settings
- [ ] Group style_only, save_log, basemap options under toggle
- [ ] Reduce Export tab vertical height on smaller screens

### Quick Presets for Map Dimensions *(Story 5)*
- [ ] Add dropdown with presets: "Full window (responsive)", "800x600", "1024x768", "1920x1080", "Custom"
- [ ] Preset selection updates width/height spinboxes

### Open Output Folder Button *(Story 1)*
- [ ] Add "Open Folder" button to success dialog after export
- [ ] Use `QDesktopServices.openUrl()` to open in file explorer

### Better Progress Feedback *(Story 1)*
- [ ] Add status text label showing current operation
- [ ] Display: "Exporting layer 2 of 5: Roads", "Converting to PMTiles", "Generating style.json"
- [ ] Show layer-by-layer progress in separate-file mode

### Auto-Launch Viewer After Export *(Story 2)*
- [ ] Add checkbox "Open in browser after export"
- [ ] Run `serve.py` or open `index.html` after completion
- [ ] Remember preference in settings

---

## Error Handling

### Validate Basemap URL in Real-Time *(Story 3)*
- [ ] Validate basemap URL/file on text change or before export
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
- [ ] Save/restore: export mode, zoom level, style options, viewer settings
- [ ] Follow existing pattern used for `last_output_folder`
- [ ] Restore settings on dockwidget initialization

### Config Load Warnings for Missing Layers *(Story 6)*
- [ ] Show clear warning when loading config with missing layers
- [ ] List which layers were not found in current project

---

## Features

### Scale-Dependent Visibility Support *(Story 7)*
- [ ] Read `scaleDependentVisibility`, `minScale`, `maxScale` from QGIS layers
- [ ] Apply as `minzoom`/`maxzoom` in MapLibre layer definitions
- [ ] Update style_converter.py to handle layer visibility

### Copy Embed Code Button *(Story 2)*
- [ ] Add button to Viewer tab to copy HTML embed snippet
- [ ] Copies BEGIN/END demarcated section to clipboard

---

## Accessibility

### Keyboard Shortcuts *(Story 8)*
- [ ] Ctrl+E: Export
- [ ] Ctrl+A: Select All layers
- [ ] Ctrl+S: Save Config
- [ ] Add to tooltips

### Inline Help Tooltips *(Story 9)*
- [ ] Add tooltip to combo_export_mode (single vs separate files)
- [ ] Add tooltip to chk_style_only
- [ ] Add tooltip to basemap inputs
- [ ] Add tooltip to dimension presets

---

## Documentation

### Quick Start Guide *(Deferred)*
- [ ] Create quick start section in README
- [ ] 5 steps from install to first export
- [ ] Include troubleshooting for common issues

### Video Tutorial *(Deferred)*
- [ ] Record screen capture of full workflow
- [ ] Host on YouTube or embed in docs
