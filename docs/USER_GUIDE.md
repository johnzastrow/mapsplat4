# MapSplat — User Guide

**MapSplat turns the layers in your QGIS project into a self-contained web map** — a folder of
static files (vector tiles in **PMTiles** format + an **HTML viewer** built on **MapLibre GL JS**)
that you can open in any browser or drop on any static web host. No tile server, no backend.

---

## 1. What you need

| Requirement | Why | Notes |
|---|---|---|
| **QGIS 4.0+** | The plugin runs inside QGIS | PyQt6 build |
| **GDAL 3.8+** | Converts your vector layers to PMTiles | Ships with QGIS; nothing to install |
| **`pmtiles` CLI** | **Only** for the optional *Basemap Overlay* | Install from the [releases page](https://github.com/protomaps/go-pmtiles/releases) and put it on your `PATH`. Core export does **not** need it. |

You do **not** need Node, a database, or any web stack.

---

## 2. Quick start (2 required steps)

Open **Plugins ▸ MapSplat** (or the toolbar button) to show the dock, then on the **Inputs** tab:

1. **① Layers** — tick the vector layers you want to publish. Their QGIS **styles and labels are read
   automatically**. (When you open the dock, your currently-visible layers are pre-selected.)
2. **② Output** — set a **Project name** and an **Output folder**. The export is written to
   `<output folder>/<project name>_webmap/`. (These are pre-filled from your project — adjust if needed.)

The **readiness line** above the Export button tells you what's still missing; when it turns green
(*"Ready to export"*) the button enables. Click **Export Web Map**, watch the **Log** tab, then
**Open Folder** to see the result.

That's the whole happy path. Everything below is optional and has sensible defaults.

---

## 3. The dock, tab by tab

- **Inputs** — Layers, Output, and the Export button. A full run lives here.
- **Options** — *Export Options* (PMTiles mode, max zoom, tile-count estimate, style.json, export
  extent) and *Basemap Overlay*. Defaults are fine for most maps.
- **Viewer** — what the generated web map shows: scale bar, geolocate, fullscreen, coordinate/zoom
  readouts, reset/north buttons, label placement, legend, attribution, and map dimensions.
- **Offline** — bundle MapLibre/PMTiles JS + CSS into the export so the viewer works with no internet.
- **Log** — progress, messages, and the **version stamp** (bottom-right) so you can confirm which
  build is loaded.

---

## 4. Key options explained

- **PMTiles mode** — *Single file* merges all layers into one `.pmtiles`; *Separate files* writes one
  per layer (loaded independently in the viewer).
- **Max zoom** — higher = more detail but **exponentially** more tiles/time. 6–10 suits most maps;
  14+ can take a long time on large data. The live estimate under it shows the rough tile count/size.
- **Export extent** — clip the basemap to a chosen layer's extent or the current map view instead of
  the full data extent.
- **Style only** *(Advanced)* — regenerate `style.json` + the viewer without re-tiling the data.

---

## 5. Adding a Protomaps basemap (optional)

On **Options ▸ Basemap Overlay**, enable it and give:
- a **source** — a Protomaps `.pmtiles` archive (a remote build URL, or a local file you've
  downloaded), and
- a **basemap style.json** — a Protomaps-compatible MapLibre style.

MapSplat runs `pmtiles extract` to **clip the basemap to your data's bounding box**, so the offline
map only carries the tiles it needs. This is the one feature that needs the `pmtiles` CLI on your
`PATH`. See [docs.protomaps.com](https://docs.protomaps.com/pmtiles/cli).

---

## 6. Viewing / serving the output

The export folder contains `index.html`, a `data/` folder of `.pmtiles`, and (optionally) a `lib/`
folder of bundled JS/CSS. Because PMTiles uses HTTP **Range** requests, opening `index.html` directly
from disk may not work — serve it over HTTP:

- **Bundled dev server:** run `serve.py` in the export folder (`python serve.py`) and open the printed
  URL.
- **Any static host** that supports range requests: Netlify, Cloudflare Pages, S3/CloudFront,
  GitHub Pages, nginx, etc. Just upload the folder.

---

## 7. Troubleshooting

- **"pmtiles CLI not found"** — only needed for the basemap. Install it and ensure QGIS sees your
  `PATH`. If it works in a terminal but not from the QGIS *Python Console* (`shutil.which("pmtiles")`
  returns `None`), launch QGIS from a terminal so it inherits your full shell `PATH`.
- **Export is huge / slow** — lower **Max zoom**; watch the tile estimate.
- **Blank map in the browser** — you opened `index.html` from disk; serve it over HTTP (§6).
- **The dock looks unchanged after an update** — QGIS caches plugin code; **fully restart QGIS**
  (or use *Plugin Reloader*). Confirm via the **version stamp** on the Log tab.
- **A layer's symbology didn't translate** — a ⚠ icon in the layer list flags renderers/markers
  (heatmap, point cluster, font markers…) that don't map cleanly to MapLibre.

---

*MapSplat is free software (GPL-2.0-or-later). Source, issues, and updates:
<https://github.com/johnzastrow/mapsplat4>.*
