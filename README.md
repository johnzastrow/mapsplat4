# MapSplat

**Export QGIS projects to static web maps using PMTiles and MapLibre GL JS**

![MapSplat](docs/images/logo.svg)

[![QGIS](https://img.shields.io/badge/QGIS-4.0%2B-green.svg)](https://qgis.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-0.6.16-orange.svg)](docs/CHANGELOG.md)

MapSplat is a QGIS plugin that exports (splats) your project layers to self-contained static web map packages. The output can be hosted on any static web server, cloud storage, or run locally — no tile server, no backend, no new stack to learn. Check the [docs/](docs/) directory for design notes, a full changelog, and technical details on the PMTiles + MapLibre GL JS architecture.

**This project targets QGIS 4.X and is 100% written by robots**

---

## Table of Contents

- [Screenshots](#screenshots)
- [Features](#features)
- [Limitations](#limitations)
- [Requirements](#requirements)
- [Installation](#installation)
  - [From ZIP](#from-zip-recommended-for-most-users)
  - [From Source](#from-source-development)
  - [Manual Installation](#manual-installation)
- [Map Production Workflow](#map-production-workflow)
  - [Step 1 — Prepare your QGIS project](#step-1--prepare-your-qgis-project)
  - [Step 2 — Open the MapSplat panel](#step-2--open-the-mapsplat-panel)
  - [Step 3 — Configure the Export tab](#step-3--configure-the-export-tab)
  - [Step 4 — Configure the Viewer tab](#step-4--configure-the-viewer-tab)
  - [Step 5 — Save a config](#step-5--save-a-config-optional-but-recommended)
  - [Step 6 — Export](#step-6--export)
  - [Step 7 — View locally](#step-7--view-locally)
- [Output Structure](#output-structure)
- [Embedding the Map in an Existing Page](#embedding-the-map-in-an-existing-page)
- [Local Viewing](#local-viewing)
- [Deployment](#deployment)
  - [Static hosting (GitHub Pages, Netlify, Vercel, S3)](#static-hosting-github-pages-netlify-vercel-s3)
  - [Linux VPS with serve.py](#linux-vps-with-servepy-low-traffic)
  - [Linux VPS with Caddy](#linux-vps-with-caddy-as-the-server-production)
  - [Linux VPS with Nginx](#linux-vps-with-nginx-production)
  - [CORS configuration](#cors-configuration)
- [Style Editing with Maputnik](#style-editing-with-maputnik)
- [Supported Symbology](#supported-symbology)
  - [Label settings](#label-settings)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)
- [Credits](#credits)

---

## Quick start (5 steps to your first web map)

1. **Install** — download the latest `mapsplat.zip` from [Releases](https://github.com/johnzastrow/mapsplat/releases) and add it in QGIS via **Plugins → Manage and Install Plugins → Install from ZIP**. Put the [pmtiles CLI](https://github.com/protomaps/go-pmtiles/releases) on your PATH (or use the basemap's **Stream from URL** mode, which needs no CLI).
2. **Style your layers in QGIS** as you want them to appear. Zoom/pan to the view your web map should open at.
3. **Open the MapSplat dock** (toolbar icon), and on the **Inputs** tab **tick the layers** to export.
4. *(Optional)* On the **Basemap** section, enable a basemap. Keep **max zoom small** (start at ~13) and the extent tight — your current view extent is a good starting point.
5. **Export.** Click **Export**, then open the output folder and run `python serve.py` — your browser opens the finished map.

> The generated `index.html` has `<!-- BEGIN/END MAPSPLAT -->` comments marking exactly the `<head>` and `<body>` blocks to copy into another page for embedding.

A more detailed walk-through (with pictures) lives in [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md); a shot-by-shot demo script is in [`docs/TUTORIAL_SCRIPT.md`](docs/TUTORIAL_SCRIPT.md). Hit a snag? See [Troubleshooting](#troubleshooting) below.


## Prep Work

This project is based on the work by the folks at Protomaps. They host builds of global map tiles in PMtile format, using data from OpenStreetMap, which you can download here for your basemap. Download the latest build, then use the `pmtiles` CLI tool to trim the global data to your needs, or let mapsplat do it. Mapsplat needs the pmtiles CLI in your path to run. You'll also need a styling JSON to make your basemap look like something - though you can publish a map entirely with your data and Mapsplat will provide the styling. Again, protomaps gives you one to start with, and mapsplat will adapt it to work more standalone.

* [Builds of global map tiles](https://maps.protomaps.com/builds/)
* [More info on basemaps](https://docs.protomaps.com/basemaps/downloads)
* [pmtiles.io blog post about a viewer/tester to preview your tiles](https://protomaps.com/blog/new-pmtiles-io/)
* [Map viewer of the global tiles. Also demos the map viewer you are going to make](https://maps.protomaps.com/#flavorName=light&lang=en&map=4.04/49.02/-100.57)
* [Docs on the pmtile cli](https://docs.protomaps.com/pmtiles/cli)


## Screenshots

1. Starting point: a QGIS project with styled vector layers and labels
     
* <img src="https://github.com/johnzastrow/mapsplat/blob/bb8167982c34b683317029f38f3de6b5ae1b12b4/docs/images/qgis.png" width="600" />
  
2. MapSplat first Inputs tab with layers selected and tool tips configured
    
<img src="https://github.com/johnzastrow/mapsplat4/blob/main/docs/images/ms4_1.png?raw=true" height="400" />

3. MapSplat Options with the export settings configured for a basemap overlay export. 
    
<img src="https://github.com/johnzastrow/mapsplat4/blob/main/docs/images/ms4_2.png?raw=true" height="400" />

1. MapSplat Viewer tab with settings for the online map viewer
    
<img src="https://github.com/johnzastrow/mapsplat4/blob/main/docs/images/ms4_3b.png?raw=true" height="400" />

3. MapSplat baby serve.py dev server running the exported map locally 
  
<img src="https://github.com/johnzastrow/mapsplat/blob/9df47e7286f4095294b265da82bbc4feef290711/docs/images/serve.png" height="300" />

4. Resulting `index.html` with the data layers rendered on top of the Protomaps basemap
    
<img src="https://github.com/johnzastrow/mapsplat/blob/9df47e7286f4095294b265da82bbc4feef290711/docs/images/onlinemap.png" height="400" />


---

## Features

### Core Export
- **Vector layers → PMTiles**: All selected vector layers exported and tiled in one step
- **Single or per-layer PMTiles**: Combine everything in one file or produce one file per layer
- **Auto-reprojection**: All layers re-projected to Web Mercator (EPSG:3857) on export
- **Style conversion**: QGIS Single Symbol, Categorized, Graduated, and Rule-based renderers converted to MapLibre GL Style JSON
- **Label support**: Text field, font, size, color, and halo extracted from QGIS label settings
- **SVG icon sprites**: Point layers using SVG marker symbols export as MapLibre symbol layers backed by a raster sprite sheet
- **Style roundtripping**: Export `style.json`, edit in [Maputnik](https://maputnik.github.io/), re-import

### Basemap Overlay Mode
- **Protomaps basemap**: Overlay your data on a Protomaps-compatible basemap from a local `.pmtiles` file or a remote URL
- **Basemap clipping**: `pmtiles extract` automatically clips the basemap tiles to your data's bounding box at export time
- **Style merging**: Basemap style and your data layers are merged; your layers render on top

### Viewer
- **Self-contained `index.html`**: Interactive web map with click-to-identify popups and layer toggles
- **Configurable controls** (Viewer tab): Scale bar, geolocate, fullscreen, coordinate display, zoom display, reset-view, and north-reset buttons — each individually enabled or disabled before export
- **Embeddable map**: `index.html` contains clearly marked `BEGIN`/`END` copy-paste sections so you can drop the map into an existing HTML page without rebuilding from scratch
- **Built-in dev server**: `serve.py` bundled with every export handles HTTP Range requests required by PMTiles

### Config Save/Load
- **Save Config… / Load Config…**: Persist all export settings (layers, output folder, PMTiles mode, zoom, basemap, viewer controls) to a human-editable TOML file
- **Portable configs**: Layer names (not runtime IDs) are stored, so a config file works across QGIS sessions and machines
- **Hand-editable**: Every key has an inline comment; open the file in any text editor to tweak settings directly

### Compatibility
- **QGIS 4 only**: This fork targets QGIS 4 (Qt6)
- **Static hosting**: No server-side processing — works on GitHub Pages, Netlify, S3, Cloudflare Pages, or any web host

---

## Limitations

- **Vector layers only**: Raster layers (WMS, GeoTIFF, etc.) are not exported
- **No 3D**: Extrusions, terrain, and 3D tiles are not supported
- **Static snapshot**: Layers are not updated after export; re-export to pick up data changes
- **Rule-based renderer**: Simple filter rules are converted; complex nested rules fall back to a default style
- **Heatmap / Point Cluster renderers**: Fall back to a simple default style
- **Zoom range**: Features are only tiled up to the max zoom set at export time (default 6); re-export at a higher zoom for more detail
- **Basemap overlay requires `pmtiles` CLI**: The [Protomaps CLI](https://github.com/protomaps/go-pmtiles/releases) must be on your PATH
- **Basemap from URL requires internet at export time**: The extracted basemap is bundled locally; internet is not needed for viewing
- **Single sprite sheet**: All custom icons share one sprite; icon names must be unique across exported layers
- **No authentication**: The viewer and `serve.py` serve files without access control
- **`python -m http.server` will not work**: The standard Python dev server does not reliably support HTTP Range requests; use the included `serve.py` or a proper web server

### Opacity and transparency

- **Semi-transparent polygon fills are supported** when the transparency is set via the fill **color alpha** (the opacity/alpha slider inside the color picker in QGIS Symbol properties). The alpha value is written to `fill-opacity` in the exported style.
- **Layer-level opacity is not captured.** QGIS offers a second, separate opacity control under *Layer Properties → Rendering → Opacity*. This value is not read by MapSplat — only the color alpha is used. If your polygons appear more opaque in the viewer than they do in QGIS, the transparency was set at the layer level rather than in the color picker. Move it to the fill color alpha to carry it through to the export.

### Unsupported fill and symbol types

Some QGIS fill types cannot be reproduced in MapLibre vector tile styles:

- **Gradient fills** (radial or linear color gradients) — exported as a solid fill. The exported color is the darkest color found among the gradient stops, chosen by perceived luminance. The gradient itself is not preserved.
- **Shape-burst fills** — same as gradient; exported as a solid color approximation.
- **Line pattern and point pattern fills** (hatching, dots) — exported as a semi-transparent solid fill using the pattern's foreground color.
- **Drop shadows, background shapes, and callout lines** on labels — no MapLibre equivalent; silently omitted.

There is no way to represent these effects in the MapLibre GL Style JSON spec, so the output will always differ from the QGIS canvas for these cases. If visual fidelity matters, convert the symbol to a Simple Fill in QGIS before exporting.

---

## Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| QGIS | 4.0+ | This fork targets QGIS 4 only |
| GDAL | 3.8+ | Required for native PMTiles support via `ogr2ogr`; MBTiles driver needed for raster export |
| Python | 3.9+ | Bundled with QGIS |
| pmtiles CLI | Any | Required for basemap **bundle** mode and raster export (not for **Stream** mode) |

---

## Troubleshooting

| Symptom | Cause & fix |
|---|---|
| **"pmtiles CLI not found"** on export | The `pmtiles` binary isn't on QGIS's PATH. Install it from the [go-pmtiles releases](https://github.com/protomaps/go-pmtiles/releases) and restart QGIS — or set the basemap to **Stream from URL** (no CLI needed). |
| **Map is blank / white** | PMTiles need HTTP **Range** requests, which `file://` doesn't provide. Don't open `index.html` directly — run `python serve.py` in the output folder (it serves with Range support) and use the `http://localhost:…` URL. |
| **A layer is missing from the map** | Only layers that tiled successfully are included. Check the **export summary dialog** / the Log tab for the failed layer and its reason. If it was there a moment ago, you may be viewing a **stale server** — stop old `serve.py` processes and re-run. |
| **Markers show as plain circles** | Per-class icons are rendered only for **SVG** markers (single-symbol, categorized, or graduated). Simple-marker (circle/square) symbols map to circles by design. |
| **Basemap doesn't appear** | Check the basemap **source URL/file** and that its **style** is set. In offline bundles, a bad sprite can blank icons — MapSplat now falls back to your local sprite automatically. |
| **Raster layer doesn't export** | Enable **Include raster layers** (Export Options) — it's off by default. It needs GDAL's **MBTiles driver** (`gdal_translate --formats` should list `MBTiles`). Styled single-band rasters (DEMs) aren't supported yet. |
| **🌐-tagged layers are blank** | Vector-tile and online XYZ/WMS layers **stream live** — the exported map needs internet for them. They won't work offline (that's Stage 2/3 offline packaging, coming later). |
| **The measure/draw/export tools aren't on the map** | They're **off by default**. Enable each in the **Viewer** tab before exporting. |
| **Slow re-exports of the same area** | Basemap extracts are cached (by source + extent + zoom). Use **Refresh basemap cache** to force a re-download, or **Clear basemap cache** to free disk. |
| **Embedding into another page shows nothing** | Copy **both** the `<head>` and `<body>` MAPSPLAT blocks, and serve the page over **http with Range support** (see the Caddy/nginx notes in `docs/USER_GUIDE.md`). |

---

## Installation

See [Releases](https://github.com/protomaps/go-pmtiles/releases) for your OS and architecture.

## Docs

See [docs.protomaps.com/pmtiles/cli](https://docs.protomaps.com/pmtiles/cli) for usage.

See [Go package docs](https://pkg.go.dev/github.com/protomaps/go-pmtiles/pmtiles) for API usage.

## Development

Run the program in development:

```sh
go run main.go
```

Run the test suite:

```sh
go test ./pmtiles
```
