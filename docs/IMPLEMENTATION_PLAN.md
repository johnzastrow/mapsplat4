# MapSplat4 - Implementation Plan

## Overview

This plan implements usability improvements for MapSplat4 in 3 phases.

**Backlog:** [FEATURE_BACKLOG.md](./FEATURE_BACKLOG.md)

---

## User Stories

### Phase 1: Core UX (Est: 1-2 days)

---

#### Story 1: Open Output Folder + Progress Feedback

**As a** user
**I want** to quickly access my exported files and see what's happening during export
**So that** I can verify the output and understand progress

**Tasks:**
- [ ] Add "Open Folder" button to success dialog using `QDesktopServices.openUrl()`
- [ ] Add status text label showing current operation (layer name, stage)
- [ ] Update progress messages in exporter.py to include layer names
- [ ] Test on Windows (different path handling)

**Estimation:** 4h

---

#### Story 2: Auto-Launch Viewer + Embed Copy

**As a** user
**I want** to preview my export immediately and easily share embed code
**So that** I can iterate on styling without manual steps

**Tasks:**
- [ ] Add checkbox "Open in browser after export" to Export tab
- [ ] On export complete, run `serve.py` or open `index.html` in browser
- [ ] Add "Copy Embed Code" button to Viewer tab
- [ ] Copy BEGIN/END demarcated HTML to clipboard
- [ ] Persist preference in settings

**Estimation:** 4h

---

#### Story 3: Better Error Handling

**As a** user
**I want** clear error messages with actionable guidance
**So that** I can fix issues without guessing

**Tasks:**
- [ ] Add real-time basemap URL validation (on text change)
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
- [ ] Move style_only, save_log, basemap options into collapsible section
- [ ] Remember collapsed/expanded state during session
- [ ] Test on 1024x768 and smaller resolutions

**Implementation Note:** Use `QToolButton` with `setCheckable(True)` + `setArrowType()` — NOT QGroupBox which enables/disables, not collapses.

**Estimation:** 4h

---

#### Story 5: Quick Dimension Presets

**As a** user
**I want** preset map dimension options
**So that** I don't have to calculate pixel values manually

**Tasks:**
- [ ] Add dropdown with presets: "Full window (responsive)", "800x600", "1024x768", "1920x1080", "Custom"
- [ ] "Custom" enables spinboxes; selecting preset fills them
- [ ] Add tooltip explaining the options

**Estimation:** 2h

---

#### Story 6: Persist All Settings

**As a** user
**I want** my settings remembered between sessions
**So that** I don't reconfigure everything each time I open QGIS

**Tasks:**
- [ ] Save/restore: export mode, zoom level, style options, viewer settings
- [ ] Follow existing pattern for `last_output_folder`
- [ ] Validate restored settings (e.g., layer still exists)

**Estimation:** 4h

---

### Phase 3: Advanced (Est: 2-3 days)

---

#### Story 7: Scale-Dependent Visibility

**As a** user
**I want** my layer visibility scales preserved in the export
**So that** the web map behaves like my QGIS project

**Tasks:**
- [ ] Read `scaleDependentVisibility`, `minScale`, `maxScale` from QGIS layers
- [ ] Convert to `minzoom`/`maxzoom` using: `zoom = log2(559082264 / scale_denominator)`
- [ ] Apply to layer definitions in style_converter.py
- [ ] Add tests for scale conversion

**Estimation:** 6h

---

#### Story 8: Keyboard Shortcuts

**As a** power user
**I want** keyboard shortcuts for common actions
**So that** I can work faster without reaching for the mouse

**Tasks:**
- [ ] Ctrl+E: Export
- [ ] Ctrl+A: Select All layers
- [ ] Ctrl+Shift+S: Save Config
- [ ] Add shortcuts to tooltips
- [ ] Audit conflicts with QGIS built-in shortcuts

**Technical Note:** Use `Qt.WidgetWithChildrenShortcut` context to ensure shortcuts work when dock has focus.

**Estimation:** 2h

---

#### Story 9: Inline Help Tooltips

**As a** new user
**I want** tooltips explaining each control
**So that** I understand options without reading documentation

**Tasks:**
- [ ] Add tooltip to combo_export_mode (single vs separate files)
- [ ] Add tooltip to chk_style_only (what it does)
- [ ] Add tooltip to basemap inputs
- [ ] Add tooltip to dimension presets
- [ ] Add tooltip to viewer control checkboxes

**Estimation:** 2h

---

## Implementation Dependencies

```
Story 1 (Open Folder + Progress) → Standalone
Story 2 (Auto-Launch) → Standalone
Story 3 (Error Handling) → Standalone
Story 4 (Collapsible) → Standalone
Story 5 (Dimension Presets) → Standalone
Story 6 (Persist Settings) → Standalone
Story 7 (Scale Visibility) → Standalone
Story 8 (Shortcuts) → Standalone
Story 9 (Tooltips) → Standalone
```

---

## Sprint Breakdown

**Note:** Sprint lengths vary based on workload. Estimates reflect effort, not fixed timeboxes.

### Sprint 1: Core UX (2-3 days)
- Story 1: Open Folder + Progress (4h)
- Story 2: Auto-Launch + Embed Copy (4h)
- Story 3: Error Handling (6h)
- **Total: 14h**

### Sprint 2: Polish (2-3 days)
- Story 4: Collapsible Options (4h)
- Story 5: Dimension Presets (2h)
- Story 6: Persist Settings (4h)
- Story 9: Tooltips (2h)
- **Total: 12h**

### Sprint 3: Advanced (2-3 days)
- Story 7: Scale Visibility (6h)
- Story 8: Keyboard Shortcuts (2h)
- **Total: 8h**

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
mapsplat_dockwidget.py  (UI changes, settings persistence)
exporter.py             (progress messages, error tracking)
style_converter.py      (scale visibility - Story 7)
```

### Existing Patterns to Follow

- Use `qgis.PyQt` for all Qt imports (QGIS4 compatibility)
- Use `QgsSettings` for persistence
- Follow existing code style for UI building
- Use `QToolButton` for collapsible sections (not QGroupBox)

### QGIS4 Compatibility

This plugin targets QGIS 4 only. Remove Qt5/Qt6 compatibility shims from `mapsplat.py`.
