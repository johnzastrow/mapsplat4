# MapSplat — Feature Backlog Analysis

**Date:** 2026-03-22
**Version reviewed:** 0.6.16

This document critiques the existing usability proposals in FEATURE_BACKLOG.md and
IMPLEMENTATION_PLAN.md, and introduces new suggestions. The analysis is grounded in
the current UI code (`mapsplat_dockwidget.py`, `exporter.py`, `style_converter.py`).

---

## Design Premise

The backlog assumes a configure-then-export workflow. The actual workflow is:

> export → see something wrong → tweak → re-export (repeat)

Features that serve **iteration** are worth more than features that serve
first-time setup. This reordering informs the priority stack-rank at the end.

---

## Critique of Existing Proposals

---

### Story 1: Open Output Folder + Progress Feedback

**Open Folder location is wrong.** A modal success dialog is one-shot — once
dismissed, the path is gone. The button should appear persistently in the pinned
footer after a successful export and stay visible until the next export starts.
The infrastructure (export state tracking) already exists; this is a layout
decision, not an architectural one.

**Progress status text is genuinely missing.** The progress bar moves 0→100 but
gives no qualitative information. There is no `QLabel` for current operation
anywhere in the export tab — only `txt_log`, which is on a hidden tab during
export. "Exporting layer 2 of 5: Roads" would cost one label widget and a signal
connection. High value, low effort.

---

### Story 2: Auto-Launch Viewer + Embed Copy

**The auto-launch idea ignores the server lifecycle problem.** PMTiles requires
HTTP Range Requests; `file://index.html` produces a blank map. The plan says
"Run serve.py or open index.html" as if they're equivalent — they are not.
A correct implementation must: start `serve.py` as a managed subprocess, display
the port, provide a Stop button, and handle the case where the port is already
in use. A half-implementation that opens `index.html` directly will confuse
users who see a blank map and don't understand why.

**Recommendation:** Scope this properly. Managed `serve.py` subprocess with port
display and stop button, or defer until the server lifecycle question is resolved.

**Embed copy is straightforward and should be split out.** The demarcation
comments (`<!-- BEGIN MAPSPLAT -->` / `<!-- END MAPSPLAT -->`) already exist in
the generated HTML. A "Copy Embed Code" button reads the output file and puts the
demarcated block on the clipboard. No server dependency. This is the easiest win
in the whole backlog and should not wait on auto-launch.

---

### Story 3: Better Error Handling

**"Real-time basemap URL validation on text change" will fire an HTTP request on
every keystroke.** The correct trigger is focus-out or export start. Implementing
on text change introduces a real bug — this distinction needs to be explicit in
the task.

The pmtiles CLI dialog and export summary ("3 of 5 layers exported successfully")
are both good. The summary surfaces information that currently lives only in the
log tab, which users who don't check logs will never see. Both are worth doing.

---

### Story 4: Collapsible Advanced Options

**The basemap section is already collapsible via its checkable QGroupBox.**
Unchecking it disables the entire section. Adding collapse-on-top-of-disable
adds mechanism without UX value.

**The real clutter problem is in Export Options**, where PMTiles mode, max zoom,
style checkboxes, style-only checkbox, extent combo, and import style button are
packed together with no visual hierarchy. Collapsing `chk_style_only` and
`chk_save_log` (rarely used) would help. The story should target these widgets,
not the basemap section.

---

### Story 6: Persist All Settings

**The code uses `QSettings("MapSplat", "MapSplat")` but the plan and updated
REQUIREMENTS now say `QgsSettings`.** The code and docs disagree. `QgsSettings`
is the correct choice — it respects QGIS profile isolation. Whichever is chosen
must be consistent across the entire plugin; mixing both is worse than either.

**The friction is real.** Max zoom, PMTiles mode, all seven viewer checkboxes,
and offline bundling reset to defaults on every QGIS restart. A user with a
consistent workflow (same team, same data type, always zoom 10, always offline)
re-configures this every session. This is one of the highest-value stories in
the backlog.

---

### Story 8: Keyboard Shortcuts

**`Ctrl+A` conflicts with QGIS's "Select All Features"** — a global canvas
action. `Qt.ShortcutContext.WidgetWithChildrenShortcut` isolates it when the
dock has focus, but users who have internalized `Ctrl+A` as a QGIS action will
be confused. A less conflicted binding: `Ctrl+Shift+A`, or simply rely on the
existing "Select All" button.

**The most useful missing shortcut isn't listed:** tab switching. `Ctrl+1/2/3/4`
for Export/Viewer/Offline/Log would let power users navigate the dock without
touching the mouse. This is absent from both the plan and the backlog.

---

### Story 9: Inline Help Tooltips

**Several targeted widgets already have tooltips.** The max zoom spinbox has one
(lines 176–180 of dockwidget); `chk_style_only` has one (lines 190–194). The
first task of this story must be an audit, not a blanket addition — otherwise
the result is duplicate or conflicting tooltip text.

---

## New Suggestions

---

### S-A: Zoom Level Tile Count Estimator

**The max zoom spinbox is the #1 source of misconfiguration.** At zoom 14 with
a nationwide dataset, users will wait hours and produce gigabytes. The tooltip
warns about this, but tooltips require hovering and are easy to miss.

A live label below the spinbox — updating whenever zoom or layer selection
changes — makes the consequences visible before export:

> `~12,000 tiles at zoom 6 · estimated 45 MB`

The math is calculable from `QgsRectangle` and zoom level:
`tile_count = 4^zoom × bbox_fraction_of_world`. It runs in milliseconds with no
external dependencies. Complements Story 1's status text and Story 3's
validation; together they form a coherent "set expectations before you commit"
pattern.

---

### S-B: Per-Layer Symbology Warnings in the Layer List

Users discover renderer limitations only after export — or after opening the web
map and noticing circles where they expected stars. `StyleConverter` already knows
which renderers it supports. That knowledge should flow back to the layer list UI
as a `⚠` icon on the list item, with a tooltip explaining the specific limitation:

> `⚠ SVG markers will render as circles (categorized renderer not supported for sprites)`

Surfaces the constraint before export. No new logic required — the converter's
renderer-type checks are already there.

---

### S-C: Popup Field Customization

**Click-to-identify shows all attributes.** Most vector layers have 15–40 fields,
many of which are internal IDs, codes, and foreign keys the end user should never
see. A per-layer "visible fields" checklist — accessible from the Viewer tab or a
dialog triggered from the layer list — controls which attributes appear in the
generated popup. The selection is stored in the config file alongside other layer
settings.

This single change transforms the output from a developer-grade tool into
something deliverable to a client or published audience. It is currently the most
significant gap between "works" and "professional output."

---

### S-D: Attribution Field

**Web maps require attribution.** MapLibre's `AttributionControl` supports custom
text. QGIS layers often have attribution set in Layer Properties → Metadata →
Attribution (`QgsMapLayer.attribution()`). MapSplat currently ignores this
entirely.

A text field in the Viewer tab — "Map attribution (appears bottom-right)" —
defaulting to any QGIS attribution found on the exported layers, with the option
to override, covers the "my client needs to credit the data source" requirement
without extra configuration for users who have already set it in QGIS.

---

### S-E: Export Dry-Run Summary

Before a potentially long export, show a one-line summary:

> `3 layers · zoom 8 · ~22 MB estimated · output: /path/to/project_webmap/`

This appears immediately when Export is clicked, before the process starts. Users
can abort if the estimate looks wrong (e.g., 4 GB at zoom 14 they didn't intend).
Tile count is calculable from bounds + zoom. Size estimation can use
feature count × typical bytes/feature as a rough proxy. Complements S-A;
together they provide before-you-commit feedback at both configuration time and
export time.

---

### S-F: Recent Exports List

A simple list in the Log tab (or a dedicated History tab): timestamp, output
path, layer names, success/fail status. Five entries, persisted in QSettings.
One-click "Open folder" next to each entry.

Solves the common scenario: "I exported three versions of this map this week —
which one is the approved final?" Currently the only record is log text that
resets each session.

---

### S-G: Re-export Changed Layers Only

Style-only export covers the case where no data changed. But if one layer's
data changed, users must re-export everything — even in separate-files-per-layer
mode, which already has the infrastructure for per-layer output.

A smart re-export compares the last-modified time of each layer's source file
against its output PMTiles file and skips layers where the source is not newer.
For large multi-layer projects this can cut iteration time from 10 minutes to
under 30 seconds. The separate-files mode already creates one PMTiles per layer;
the comparison logic is the only missing piece.

---

## Priority Stack-Rank

Combining existing proposals and new suggestions, ordered by user impact:

| Priority | Item | Rationale |
|---|---|---|
| ★★★ | **S-A** Zoom tile count estimator | Prevents the most common serious misconfiguration |
| ★★★ | **Story 6** Persist all settings | Daily friction for every repeat user |
| ★★★ | **S-C** Popup field customization | Gap between working and professional output |
| ★★ | **Story 1** Progress text + persistent open-folder button | Low effort, high visibility |
| ★★ | **S-B** Per-layer symbology warnings | Prevents post-export surprises |
| ★★ | **S-D** Attribution field | Required for most real-world publishing |
| ★★ | **Story 3** Error handling (pmtiles dialog + export summary) | Surfaces silent failures |
| ★ | **Story 2 (embed copy only)** Copy embed code button | Simple, demarcation already exists |
| ★ | **Story 2 (auto-launch)** Managed serve.py subprocess | Needs server lifecycle design first |
| ★ | **S-F** Recent exports list | Nice, not urgent |
| ★ | **Story 4** Collapsible options | Cosmetic; target the right widgets |
| ★ | **Story 9** Tooltips | Audit existing tooltips first |
| ○ | **Story 5** Dimension presets dropdown | Spinboxes exist; dropdown is marginal |
| ○ | **Story 8** Keyboard shortcuts | Useful, low-value in a dock panel |
| ○ | **S-E** Dry-run summary | Good, overlaps with S-A |
| ○ | **S-G** Re-export changed layers | Complex; wait for user request |

---

## Notes for IMPLEMENTATION_PLAN Updates

- Split Story 2 into two stories: embed copy (standalone, 1h) and auto-launch
  (requires server lifecycle design, re-estimate separately).
- Add audit task to Story 9 before any tooltip work begins.
- Story 8: replace `Ctrl+A` with `Ctrl+Shift+A`; add tab-switching shortcuts.
- Story 6: resolve `QSettings` vs `QgsSettings` in code before implementing
  broader persistence (don't persist to the wrong store).
- Story 3: change "on text change" to "on focus-out" for basemap URL validation.
- S-A, S-B, S-C, S-D should be added to FEATURE_BACKLOG.md and assigned story
  numbers (Story 10–13) for tracking.
