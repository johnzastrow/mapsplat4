# MapSplat — Video Tutorial Script & Storyboard

A shot-by-shot script for a ~6-minute screen-capture tutorial taking a viewer from **install** to a
**published, embeddable web map**. Record at 1920×1080, 30 fps. Suggested tools: OBS Studio (capture),
a mic for voice-over, and a simple cursor-highlight. Times are targets, not hard cuts.

> This file is the deliverable for backlog Story 8 (Video Tutorial). The actual recording/hosting
> (YouTube or embedded in the docs) is a manual step — everything the narrator needs is below.

---

## Cold open (0:00–0:15)

**Screen:** A finished MapSplat web map already open in a browser — pan it, toggle a couple of layers,
click a feature to show a popup, click the ruler tool and measure a distance.

**VO:** "This is a live, self-contained web map — vector tiles, your styling, interactive tools —
exported straight from QGIS with the MapSplat plugin. In the next few minutes I'll build one from
scratch."

---

## Scene 1 — Install (0:15–1:00)

**Screen actions:**
1. Browser → the MapSplat **Releases** page; download `mapsplat.zip`.
2. QGIS → **Plugins → Manage and Install Plugins → Install from ZIP** → pick `mapsplat.zip` → Install.
3. Show the MapSplat toolbar icon; click it to open the dock.
4. Terminal: `pmtiles version` to show the CLI is on PATH. (Note: only needed for basemap *bundle*
   mode and raster export.)

**VO:** "Grab the zip from Releases and install it from ZIP — no repository needed. For offline
basemaps you'll also want the `pmtiles` CLI on your PATH; if you skip it, you can still stream a
basemap from a URL."

**Callout card:** *"pmtiles CLI → github.com/protomaps/go-pmtiles/releases"*

---

## Scene 2 — Style your data in QGIS (1:00–2:00)

**Screen actions:**
1. A project with a few vector layers (e.g. parks polygons, a trails line, points of interest).
2. Style them the way you'd want them online: fills, strokes, a categorized SVG marker layer with
   labels, a dashed line.
3. Zoom/pan to the exact view you want the web map to open at.

**VO:** "Style everything in QGIS as you normally would — MapSplat reads your symbology: fills,
strokes, dashed lines, categorized and graduated markers, labels. Whatever view you leave the map
at becomes the web map's starting view."

**Callout card:** *"Tip: SVG markers become real icons; simple circles stay circles."*

---

## Scene 3 — Select layers & options (2:00–3:00)

**Screen actions:**
1. In the dock's **Inputs** tab, tick the layers to export. Point out the type tags: `[Polygon]`,
   `[Line]`, `[Point]`, and a `🌐` online tag if present.
2. **Export Options:** show *Export separate style.json* and *Include raster layers* (mention it's
   off by default and needs GDAL's MBTiles driver).
3. Set **max zoom** modestly (13–14) and note the tile-count estimate updating.

**VO:** "Tick the layers you want. Keep the max zoom small to start — the estimate on the right shows
how many tiles you're about to generate. Raster layers are opt-in under Export Options."

---

## Scene 4 — Basemap (3:00–3:45)

**Screen actions:**
1. Expand **Basemap Overlay**, enable it.
2. Show **Stream from URL** vs **Download & clip offline**; pick Stream for the demo (fast, no CLI).
3. Paste a Protomaps build URL and a basemap style path.
4. Mention the cache: repeat exports of the same area reuse the extract (**Refresh** / **Clear** in
   Advanced Options).

**VO:** "A basemap is optional. Stream it live from a URL, or download-and-clip it offline. MapSplat
caches the clipped basemap, so re-exporting the same area is fast."

---

## Scene 5 — Viewer tools (3:45–4:30)

**Screen actions:**
1. **Viewer** tab: enable **Measure tool**, **Draw/sketch tool**, **Export tool**; set the label
   placement; optionally a custom attribution.
2. Briefly show the units toggle idea and the draw colour picker (these appear in the exported map).

**VO:** "The Viewer tab adds optional on-map tools — measure distance and area, sketch and export
points/lines/polygons to GeoJSON or KML, and save the map as a JPG or PDF. They're off by default;
flip on what you need."

---

## Scene 6 — Export & preview (4:30–5:30)

**Screen actions:**
1. Click **Save Config** (show the TOML) — "so you can iterate."
2. Click **Export**; watch the Log tab stream progress; show the completion dialog (and the
   partial-failure summary format if any layer failed).
3. **Open Folder**; in a terminal run `python serve.py`; the browser opens the map.
4. Interact: toggle layers, click a feature, use the ruler, draw a shape and export GeoJSON, save a
   JPG.

**VO:** "Save your config so you can iterate, then Export. The log shows every step, and you get a
summary of what succeeded. Run `serve.py` — because these tiles need HTTP range requests, don't just
double-click the HTML — and there's your map."

**Callout card:** *"Blank map? Use serve.py, not file://"*

---

## Scene 7 — Embed & wrap (5:30–6:00)

**Screen actions:**
1. Open `index.html` in an editor; highlight the `<!-- BEGIN/END MAPSPLAT -->` head and body blocks.
2. Paste both blocks into a simple host page to show embedding.

**VO:** "To drop the map into an existing site, copy the two marked MAPSPLAT blocks — head and body —
into your page, and serve it with range support. That's MapSplat: your QGIS map, on the web, in
minutes."

**End card:** repo URL + "Docs: README ▸ Quick start ▸ USER_GUIDE.md"

---

## Shot list checklist

- [ ] Cold-open beauty shot of a finished map (with a tool in use)
- [ ] Install-from-ZIP flow
- [ ] `pmtiles version` in a terminal
- [ ] Styled QGIS project + starting view
- [ ] Layer selection with type tags
- [ ] Export options + tile estimate
- [ ] Basemap stream/bundle choice
- [ ] Viewer-tools toggles
- [ ] Export run + Log tab + completion dialog
- [ ] `serve.py` opening the browser
- [ ] Interacting with tools in the live map
- [ ] Embed blocks in an editor

## Production notes

- Keep the cursor movements slow; pause ~1 s after each click so viewers can follow.
- Use a small, real dataset clipped to a tight extent so exports finish in seconds on camera.
- If a step is slow (basemap download, raster tiling), cut/speed-ramp it and narrate over.
- Caption the callout cards for accessibility; add chapter markers matching the scene headings.
