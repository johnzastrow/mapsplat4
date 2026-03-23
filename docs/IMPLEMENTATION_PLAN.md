# MapSplat4 - Implementation Plan

## Overview

This plan converts MapSplat to QGIS4 and implements usability improvements in 4 phases.

**Backlog:** [FEATURE_BACKLOG.md](./FEATURE_BACKLOG.md)

---

## User Stories

### Phase 0: QGIS4 Conversion ✅ *Done — v0.7.0*

---

#### Story 0: Remove Qt5/Qt6 Compatibility Shims ✅

**Tasks:**
- [x] Remove `QAction` import location shim from `mapsplat.py`
- [x] Remove `RightDockWidgetArea`, `ItemIsEnabled`, `UserRole` enum scoping shims
- [x] Update imports to use Qt6-style directly

---

#### Story 0b: Qgis.MessageLevel Enum Migration ✅

**Tasks:**
- [x] Audited `mapsplat_dockwidget.py`, `exporter.py`, `config_manager.py`, `log_utils.py` — no old-style `Qgis.Info`/`Qgis.Warning` calls were present; these APIs were never used directly. Removed unused `Qgis` imports from `mapsplat_dockwidget.py` and `style_converter.py`.

---

#### Story 0c: Qt Enum Scoping ✅

**Tasks:**
- [x] `Qt.AlignCenter` — not present in codebase
- [x] `Qt.UserRole` shim → `Qt.ItemDataRole.UserRole` (direct, no try/except)
- [x] `Qt.red`/`Qt.darkGreen`/`Qt.darkYellow` — not present in codebase
- [x] `QFrame.NoFrame` → `QFrame.Shape.NoFrame`
- [x] `QFrame.HLine` → `QFrame.Shape.HLine`
- [x] `QFrame.Sunken` → `QFrame.Shadow.Sunken`
- [x] `_MultiSelection` shim → `QAbstractItemView.SelectionMode.MultiSelection` (direct)

---

#### Story 0d: Recompile Resources + Finalize ✅ *(partial)*

**Tasks:**
- [ ] Run `pyrcc6 -o resources.py resources.qrc` *(must run inside QGIS Python env: `make compile`)*
- [x] Verify Makefile uses `pyrcc6` (already done)
- [ ] Test export workflow in QGIS4
- [ ] Test layer selection and UI interactions
- [ ] Test config save/load
- [ ] Test viewer generation
- [x] Bump version: v0.7.0
- [x] Update CHANGELOG.md

**Estimation:** 4h

---

### Phase 1: Core UX (Est: 1-2 days)

---

#### Story 1: Open Output Folder + Progress Feedback

**As a** user
**I want** to quickly access my exported files and see what's happening during export
**So that** I can verify the output and understand progress

**Tasks:**
- [ ] Add "Open Folder" button to the **pinned footer** (alongside Export button) — appears after a successful export, stays visible until the next export starts; use `QDesktopServices.openUrl()`
- [ ] Add status text label showing current operation (layer name, stage) next to the progress bar
- [ ] Update progress messages in exporter.py to include layer names ("Exporting layer 2 of 5: Roads")
- [ ] Test on Windows (different path handling)

**Implementation Note:** Do NOT add the Open Folder button to a success dialog — a dismissed dialog is gone. The pinned footer is persistent and visible without extra interaction.

**Estimation:** 4h

---

#### Story 2a: Copy Embed Code

**As a** user
**I want** to copy the embed snippet for my map with one click
**So that** I can paste it into another page without manually finding the demarcation comments

**Tasks:**
- [ ] Add "Copy Embed Code" button to Viewer tab
- [ ] Read the generated `index.html` from the last output directory
- [ ] Extract the BEGIN/END MAPSPLAT demarcated blocks (head + body) and copy to clipboard
- [ ] Show confirmation: "Embed code copied to clipboard"
- [ ] Disable button when no output has been generated yet this session

**Estimation:** 2h

---

#### Story 2b: Auto-Launch Viewer After Export

**As a** user
**I want** to preview my export in a browser immediately after it completes
**So that** I can iterate on styling without manual steps

**Tasks:**
- [ ] Design server lifecycle: start `serve.py` as a managed subprocess (NOT just open `index.html` — file:// breaks PMTiles)
- [ ] Display active port in the UI ("Serving at http://localhost:8000")
- [ ] Add Stop Server button; disable it when server is not running
- [ ] Handle port-in-use error gracefully (try next port or prompt)
- [ ] Open `http://localhost:{port}` in browser once server is confirmed listening
- [ ] Add checkbox "Open in browser after export" to Export tab; persist in settings
- [ ] Stop server on plugin unload / QGIS exit

**Technical Risk:** serve.py runs as a blocking server process. Must use `QProcess` (not `subprocess`) to keep QGIS responsive and to enable clean shutdown. Port conflicts must be caught before the browser opens.

**Estimation:** 6h

---

#### Story 3: Better Error Handling

**As a** user
**I want** clear error messages with actionable guidance
**So that** I can fix issues without guessing

**Tasks:**
- [ ] Add basemap URL/file validation on **focus-out** (not on text change — text change fires on every keystroke and would issue an HTTP request per character)
- [ ] Show QMessageBox for missing pmtiles CLI with install link
- [ ] Track per-layer success/failure in separate-file mode
- [ ] Show summary dialog: "X of Y layers exported successfully"
- [ ] List failed layers with error reasons

**Estimation:** 6h

---

### Phase 2: Polish (Est: 2-3 days)

---

#### Story 4: Collapsible Advanced Options

**As a** user
**I want** a compact Export tab that shows essentials by default
**So that** I can find settings quickly on smaller screens

**Tasks:**
- [ ] Add collapsible "Advanced Options" group using `QToolButton` with arrow toggle
- [ ] Move `chk_style_only` and `chk_save_log` into collapsible section — these are the rarely-used options that create clutter
- [ ] Do NOT move the basemap section — it is already a checkable QGroupBox and handles its own visibility correctly
- [ ] Remember collapsed/expanded state during session
- [ ] Test on 1024x768 and smaller resolutions

**Implementation Note:** Use `QToolButton` with `setCheckable(True)` + `setArrowType()` — NOT QGroupBox which enables/disables, not collapses. Target `chk_style_only` and `chk_save_log` specifically; the basemap group does not need this treatment.

**Estimation:** 4h

---

#### Story 5: Quick Dimension Presets *(Partial — spinboxes done, preset dropdown pending)*

**As a** user
**I want** preset map dimension options
**So that** I don't have to calculate pixel values manually

**Tasks:**
- [x] Width/Height spinboxes added (v0.6.13; 0 = responsive full-window)
- [ ] Add dropdown with presets: "Full window (responsive)", "800x600", "1024x768", "1920x1080", "Custom"
- [ ] "Custom" enables spinboxes; selecting preset fills them
- [ ] Add tooltip explaining the options

**Estimation:** 2h (reduced; spinboxes already exist)

---

#### Story 6: Persist All Settings

**As a** user
**I want** my settings remembered between sessions
**So that** I don't reconfigure everything each time I open QGIS

**Tasks:**
- [ ] Resolve `QSettings` vs `QgsSettings` first — the codebase currently uses `QSettings("MapSplat", "MapSplat")` for `last_output_folder` but the pattern should use `QgsSettings` (respects QGIS profile isolation). Migrate existing `last_output_folder` key before adding new ones.
- [ ] Save/restore: export mode, zoom level, style options, all 7 viewer checkboxes, offline bundling toggle, label placement mode
- [ ] Validate restored settings (e.g., layer still exists in project)

**Estimation:** 4h

---

### Phase 3: Advanced (Est: 2-3 days)

---

#### Story 7: Scale-Dependent Visibility ✅ *Done — v0.6.15/0.6.16*

**As a** user
**I want** my layer visibility scales preserved in the export
**So that** the web map behaves like my QGIS project

**Tasks:**
- [x] Read `scaleDependentVisibility`, `minScale`, `maxScale` from QGIS layers
- [x] Convert to `minzoom`/`maxzoom` — constant corrected to `279541132` (= 559082264 ÷ 2) for MapLibre 512px tiles (v0.6.16)
- [x] Apply to layer definitions in style_converter.py
- [x] Add tests for scale conversion (13 tests added)

**Estimation:** 6h

---

#### Story 8: Keyboard Shortcuts

**As a** power user
**I want** keyboard shortcuts for common actions
**So that** I can work faster without reaching for the mouse

**Tasks:**
- [ ] Ctrl+E: Export
- [ ] Ctrl+Shift+A: Select All layers (`Ctrl+A` conflicts with QGIS "Select All Features" — use `Ctrl+Shift+A` instead)
- [ ] Ctrl+Shift+S: Save Config
- [ ] Ctrl+1 / Ctrl+2 / Ctrl+3 / Ctrl+4: switch to Export / Viewer / Offline / Log tab
- [ ] Add shortcuts to tooltips
- [ ] Audit remaining conflicts with QGIS built-in shortcuts

**Technical Note:** Use `Qt.ShortcutContext.WidgetWithChildrenShortcut` context to ensure shortcuts fire only when the dock has focus (Qt6-scoped enum).

**Estimation:** 3h

---

#### Story 9: Inline Help Tooltips

**As a** new user
**I want** tooltips explaining each control
**So that** I understand options without reading documentation

**Tasks:**
- [ ] Audit existing tooltips first — `spin_max_zoom` and `chk_style_only` already have tooltips; do not duplicate
- [ ] Add tooltip to `combo_export_mode` (single vs separate files)
- [ ] Add tooltip to `combo_extent_layer` (what bounding box is used for)
- [ ] Add tooltip to basemap source inputs (URL format, what pmtiles extract does)
- [ ] Add tooltip to basemap style input (what the style.json is for)
- [ ] Add tooltip to dimension preset dropdown (when implemented)
- [ ] Add tooltips to viewer control checkboxes explaining what each control does in the web map

**Estimation:** 2h

---

---

### Phase 4: High-Value Additions

---

#### Story 10: Zoom Level Tile Count Estimator

**As a** user
**I want** to see an estimated tile count and output size as I configure the export
**So that** I don't accidentally start a multi-hour export at zoom 14

**Tasks:**
- [ ] Add a live label below `spin_max_zoom`: "~N tiles · est. X MB"
- [ ] Recalculate on zoom change and on layer selection change
- [ ] Compute tile count from combined selected-layer bounding box + zoom: `4^zoom × bbox_fraction_of_world`
- [ ] Estimate size as `tile_count × avg_bytes_per_tile` (use a conservative constant, e.g. 3–5 KB/tile)
- [ ] Show "select layers to estimate" when no layers are selected
- [ ] Clamp display to reasonable range (don't show 0 or impossibly large numbers)

**Implementation Note:** All math runs on `QgsRectangle` — no external dependencies. Update is cheap enough to run synchronously on signal.

**Estimation:** 3h

---

#### Story 11: Per-Layer Symbology Warnings

**As a** user
**I want** to see a warning on layers whose symbology won't fully transfer
**So that** I'm not surprised by circles where I expected stars or SVGs

**Tasks:**
- [ ] After layer list is populated, inspect each layer's renderer type via `QgsVectorLayer.renderer()`
- [ ] Add ⚠ icon to `QListWidgetItem` for layers using: categorized/graduated SVG markers, font markers, complex rule-based expressions (AND/OR), heatmap, point displacement
- [ ] Set tooltip on the item explaining the specific limitation (e.g. "SVG markers will render as circles — categorized renderer not supported for sprites")
- [ ] Re-run check when project layers change
- [ ] No warning for fully-supported renderers (single symbol, categorized fill/line/circle, graduated, rule-based with simple filters)

**Estimation:** 4h

---

#### Story 12: Popup Field Customization

**As a** user
**I want** to choose which fields appear in the click-to-identify popup
**So that** the web map shows only relevant attributes to the end user

**Tasks:**
- [ ] Add "Configure Popup Fields..." button or context menu item on layer list items
- [ ] Open dialog showing all fields for the selected layer with checkboxes (default: all checked)
- [ ] Store visible-field selections per layer in config file (new `[popup]` section)
- [ ] Pass visible-field config to `generate_html_viewer()` and filter popup HTML accordingly
- [ ] "Show all / hide all" toggle in dialog
- [ ] Restore selections from config on load

**Estimation:** 6h

---

#### Story 13: Attribution Field

**As a** user
**I want** to set map attribution that appears in the web map viewer
**So that** data sources are properly credited in published maps

**Tasks:**
- [ ] Add "Attribution" text field to Viewer tab
- [ ] Default to any attribution found on exported layers via `QgsMapLayer.attribution()`; join multiple with " | "
- [ ] Pass attribution string to `generate_html_viewer()`
- [ ] Add `maplibregl.AttributionControl({ customAttribution: "..." })` to generated viewer when non-empty
- [ ] Save/restore in config file under `[viewer]`

**Estimation:** 2h

---

## Implementation Dependencies

```
Phase 0 (QGIS4 Conversion) → REQUIRED FIRST — all other work depends on this
Story 1  (Open Folder + Progress)     → Standalone
Story 2a (Embed Copy)                 → Standalone
Story 2b (Auto-Launch Viewer)         → Standalone (but design server lifecycle carefully)
Story 3  (Error Handling)             → Standalone
Story 4  (Collapsible Options)        → Standalone
Story 5  (Dimension Presets)          → Standalone
Story 6  (Persist Settings)           → Resolve QSettings/QgsSettings before starting
Story 7  (Scale Visibility)           → Done ✅
Story 8  (Shortcuts)                  → Standalone
Story 9  (Tooltips)                   → Audit existing tooltips before starting
Story 10 (Zoom Estimator)             → Standalone
Story 11 (Symbology Warnings)         → Standalone
Story 12 (Popup Fields)               → Story 6 first (config file needed for storage)
Story 13 (Attribution)                → Standalone
```

---

## Sprint Breakdown

**Note:** Sprint lengths vary based on workload. Estimates reflect effort, not fixed timeboxes.

### Sprint 0: QGIS4 Conversion (1-2 days)
- Story 0: Remove Qt Shims (2h)
- Story 0b: Qgis.MessageLevel Migration (2h)
- Story 0c: Qt Enum Scoping (2h)
- Story 0d: Recompile Resources + Verify (4h)
- **Total: 10h**

### Sprint 1: Core UX (2-3 days)
- Story 1: Open Folder + Progress (4h)
- Story 2a: Copy Embed Code (2h)
- Story 2b: Auto-Launch Viewer (6h)
- Story 3: Error Handling (6h)
- **Total: 18h**

### Sprint 2: Polish (2-3 days)
- Story 4: Collapsible Options (4h)
- Story 5: Dimension Presets (2h)
- Story 6: Persist Settings (4h)
- Story 9: Tooltips (2h)
- **Total: 12h**

### Sprint 3: Advanced (2-3 days)
- ~~Story 7: Scale Visibility (6h)~~ — Done (v0.6.15/0.6.16)
- Story 8: Keyboard Shortcuts (3h)
- **Total: 3h remaining**

### Phase 4: High-Value Additions (2-3 days)
- Story 10: Zoom Tile Count Estimator (3h)
- Story 11: Per-Layer Symbology Warnings (4h)
- Story 12: Popup Field Customization (6h)
- Story 13: Attribution Field (2h)
- **Total: 15h**

---

## Definition of Done

For each story:
- [ ] Code written and reviewed
- [ ] Unit tests passing (where testable; manual QGIS UI test otherwise)
- [ ] UI tested manually in QGIS4
- [ ] Update `docs/CHANGELOG.md`
- [ ] Bump version if warranted

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| QDesktopServices.openUrl() path handling differs on Windows | Medium | Test on all target platforms |
| serve.py port conflicts on auto-launch | Low | Use random port or prompt user |
| Scale visibility formula edge cases | Medium | Add bounds checking, clamp to [0, 24] |

---

## Technical Notes

### Key Files to Modify

```
mapsplat_dockwidget.py  (UI changes, settings persistence, QGIS4 enum updates)
exporter.py             (progress messages, error tracking, QGIS4 enum updates)
style_converter.py      (scale visibility - Story 7)
config_manager.py        (QGIS4 enum updates)
log_utils.py           (QGIS4 enum updates)
mapsplat.py            (remove Qt5/Qt6 shims)
```

### Existing Patterns to Follow

- Use `qgis.PyQt` for all Qt imports (QGIS4 compatibility)
- Use `QgsSettings` for persistence
- Follow existing code style for UI building
- Use `QToolButton` for collapsible sections (not QGroupBox)

### QGIS4 API Changes

| Old (QGIS3) | New (QGIS4) |
|--------------|--------------|
| `Qgis.Info` | `Qgis.MessageLevel.Info` |
| `Qt.AlignCenter` | `Qt.AlignmentFlag.AlignCenter` |
| `Qt.UserRole` | `Qt.ItemDataRole.UserRole` |
| `Qt.red` | `Qt.GlobalColor.red` |
| `pyrcc5` | `pyrcc6` |

### Resources

Recompile with: `pyrcc6 -o resources.py resources.qrc`
