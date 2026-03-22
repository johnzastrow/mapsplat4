# MapSplat

**Export QGIS projects to static web maps using PMTiles and MapLibre GL JS**

![MapSplat](docs/images/logo.svg)

[![QGIS](https://img.shields.io/badge/QGIS-3.40%2B-green.svg)](https://qgis.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-0.6.13-orange.svg)](docs/CHANGELOG.md)

MapSplat is a QGIS plugin that exports (splats) your project layers to self-contained static web map packages. The output can be hosted on any static web server, cloud storage, or run locally — no tile server, no backend, no new stack to learn. Check the [docs/](docs/) directory for design notes, a full changelog, and technical details on the PMTiles + MapLibre GL JS architecture.

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

**Quick start:**
1. Install the plugin (yes, downloading the .zip and manually adding it to QGIS works)
2. Put the [pmtiles CLI](https://github.com/protomaps/go-pmtiles/releases) on your PATH so QGIS can just use it as you
3. Style a point layer in your map with a single point style and labels. Circles and "gray" (special QGIS) SVG icons for markers are working now
4. Download a big set of background tiles (see below. Get a larger area then you need. Mapsplat will trim to your extents) along with some styling (style.json also from below). I like to rename this jason to be basemap.json for clarity`
5. Configure mapsplat by
   * picking your point layer,
  * setting unified or separate layers for the output PMtiles (I like separate), 
1. 


The resulting HTML has comments that can help you copy/paste the map into another HTML page for embedding.


**Prep Work**

This project is based on the work by the folks at Protomaps. They host builds of global map tiles in PMtile format with data from Open Street Map that you can download here for your basemap. Download the latest build, then use the pmtiles CLI tool to trim the glopbal data to your needs, or let mapsplat do it. It wants the pmtiles CLI in your path anyway. You'll also need a styling JSON to make your basemap look like something. Again, protomaps gives you one to start with and mapsplat will adapt it to work in a more stand alone way.

* [Builds of global map tiles](https://maps.protomaps.com/builds/)
* [More info on basemaps](https://docs.protomaps.com/basemaps/downloads)
* [pmtiles.io blog post about a viewer/tester to preview your tiles](https://protomaps.com/blog/new-pmtiles-io/)
* [Map viewer of the global tiles. Also demos the map viewer you are going to make](https://maps.protomaps.com/#flavorName=light&lang=en&map=4.04/49.02/-100.57)
* [Docs on the pmtile cli](https://docs.protomaps.com/pmtiles/cli)


## Screenshots

1. Starting point: a QGIS project with styled vector layers and labels
     
* <img src="https://github.com/johnzastrow/mapsplat/blob/bb8167982c34b683317029f38f3de6b5ae1b12b4/docs/images/qgis.png" width="600" />
  
2. MapSplat Export tab with layers selected and basemap overlay configured
    
<img src="https://github.com/johnzastrow/mapsplat/blob/9df47e7286f4095294b265da82bbc4feef290711/docs/images/mapsplat_config.png" height="400" />

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
- **Qt5 / Qt6**: Works with QGIS 3.x (Qt5) and QGIS 4.x (Qt6)
  *Not really. It works with QGIS 3.44, and it think it works with QGIS 3.99, but not really. I think it can only work with one at a time. So, when 4.0 is released, I'll update the plugin to be compatible with that and drop support for 3.x.*
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
| QGIS | 3.40+ | Also compatible with 4.0 beta |
| GDAL | 3.8+ | Required for native PMTiles support via `ogr2ogr` |
| Python | 3.9+ | Bundled with QGIS |
| pmtiles CLI | Any | Required only for basemap overlay mode |

---

## Installation

### From ZIP (Recommended for most users)

1. Download the latest `mapsplat.zip` from [Releases](https://github.com/johnzastrow/mapsplat/releases)
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**
3. Select the downloaded ZIP and click **Install Plugin**
4. Enable **MapSplat** in the installed plugins list

### From Source (Development)

**Linux / macOS:**
```bash
git clone https://github.com/johnzastrow/mapsplat.git
cd mapsplat
make deploy
```

**Windows (Command Prompt):**
```cmd
git clone https://github.com/johnzastrow/mapsplat.git
cd mapsplat
deploy.bat
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/johnzastrow/mapsplat.git
cd mapsplat
.\deploy.ps1
```

Restart QGIS and enable the plugin in Plugin Manager.

### Manual Installation

Copy the `mapsplat` folder to your QGIS plugins directory:

| OS | Path |
|----|------|
| Linux | `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/` |
| macOS | `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/` |
| Windows | `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\` |

---

## Map Production Workflow

### Step 1 — Prepare your QGIS project

- Load and style the vector layers you want to publish
- Set labels, colors, and symbology in QGIS as usual — MapSplat reads them automatically
- Confirm layer names are meaningful; they become the source-layer names in the PMTiles file and appear in the viewer's layer panel

### Step 2 — Open the MapSplat panel

Click the **MapSplat** toolbar button (or **Web → MapSplat**). The panel docks on the right side of QGIS with three tabs: **Export**, **Viewer**, and **Log**.

### Step 3 — Configure the Export tab

1. **Layers to Export**: Select one or more vector layers from the list. Use *Select All* / *Select None* for convenience.
2. **PMTiles mode**: Choose *Single file* (all layers in one `.pmtiles`) or *Separate files per layer* (one `.pmtiles` per layer). Single file is simpler; separate files let you toggle individual layer sources.
3. **Max zoom** (4–18): Controls the highest zoom level at which tiles are generated. Higher zoom = more detail but exponentially longer processing and larger files.
   - 6: country/region overview (fast, small)
   - 10: city/neighbourhood level (good default for most data)
   - 14+: street-level detail (can take minutes to hours for large datasets)
4. **Export style.json**: Keep checked. Exports a standalone `style.json` alongside the viewer so you can edit styles in Maputnik and reload without re-exporting data.
5. **Style only** (skip data): Re-generate HTML and style without re-converting data. Useful for rapid style iteration when the PMTiles file is already correct.
6. **Import style.json…**: Load a previously edited Maputnik style to merge into the export.
7. **Save export log**: Writes a timestamped `export.log` to `<project_name>_webmap/` for debugging.
8. **Project name**: Used as the output folder name and the map title in the viewer. Defaults to the QGIS project filename.
9. **Output folder**: Parent folder. The full output path is `<output_folder>/<project_name>_webmap/`.

#### Basemap Overlay (optional)

Enable the **Basemap Overlay** group to combine your data with a Protomaps basemap:

1. Choose **Remote URL** (requires internet at export time) or **Local file** (a previously downloaded `.pmtiles` file)
2. Enter or browse to the basemap source
3. Browse to a **basemap style.json** from [protomaps/basemaps releases](https://github.com/protomaps/basemaps/releases)
4. Ensure the `pmtiles` CLI is on your PATH (see [Requirements](#requirements))

### Step 4 — Configure the Viewer tab

Switch to the **Viewer** tab and toggle the map controls that should appear in the exported HTML:

| Control | What it does |
|---------|-------------|
| Scale bar | Distance scale in the bottom-left corner |
| Geolocate | "Show my location" button (uses browser geolocation) |
| Fullscreen | Full-screen toggle button |
| Coordinate display | Live longitude/latitude readout under the mouse cursor |
| Zoom level display | Current zoom level readout |
| Reset view | Button to fit the map back to the data extent |
| North-up reset | Button to snap the map back to north-up / zero pitch |

### Step 5 — Save a config (optional but recommended)

Click **Save Config…** above the Export button. Choose a location and name (e.g. `stations_export.toml`). The config file stores all current settings — layers, output folder, zoom, basemap, viewer controls — in a human-readable TOML file you can share or re-use.

To reload settings in a future session: click **Load Config…** and select the file. All widgets update instantly.

### Step 6 — Export

Click **Export Web Map**. The Log tab opens automatically. Watch progress messages; a typical export takes:
- A few seconds for small datasets at low zoom
- Minutes for large datasets or high zoom levels
- Extra time for basemap extraction (network-dependent if using a URL source)

On completion a dialog shows the full path to `<project_name>_webmap/`.

### Step 7 — View locally

```bash
cd /path/to/output/stations_project4_webmap
python serve.py
```

`serve.py` starts a local HTTP server on port 8000 and opens your browser automatically. It handles HTTP Range requests (required by PMTiles) and CORS headers.

> **Do not use `python -m http.server`** — it does not support Range requests reliably.

---

## Output Structure

Every export writes to `<output_folder>/<project_name>_webmap/`. For a project named `stations_project4` with output folder `C:/Maps`, the result is `C:/Maps/stations_project4_webmap/`:

```
_webmap/
├── index.html              # Interactive map viewer (open this in a browser)
├── style.json              # MapLibre GL Style JSON (if "Export style.json" checked)
├── serve.py                # Local HTTP dev server with Range request support
├── export.log              # Timestamped export log (if "Save export log" checked)
├── README.txt              # Deployment quick-reference
├── data/
│   ├── layers.pmtiles      # Vector tile data — all layers (single-file mode)
│   ├── <layer>.pmtiles     # Per-layer files (separate-files mode)
│   └── basemap.pmtiles     # Basemap tiles clipped to data extent (basemap mode only)
├── lib/                    # Reserved for offline JS/CSS bundles (currently CDN)
└── sprites/                # Icon sprite sheet (present when SVG marker layers exported)
    ├── sprites.png
    └── sprites.json
```

---

## Embedding the Map in an Existing Page

The generated `index.html` contains copy-paste markers so you can embed the map into any existing HTML page:

1. Open `<project_name>_webmap/index.html` in a text editor
2. Find `<!-- <----- BEGIN MAPSPLAT: copy the lines below into your page <head> ----- -->` and copy everything up to the matching `END` comment into your target page's `<head>` (CDN links + styles)
3. Find `<!-- <----- BEGIN MAPSPLAT: copy the lines below into your page <body> ----- -->` and copy everything up to the matching `END` comment into your target page's `<body>` (map divs + initialisation script)
4. Ensure the CDN `<script>` and `<link>` tags from step 2 are present in the target page's `<head>`

The `<div id="map">` is styled `position: absolute; top: 0; bottom: 0; width: 100%` by default — resize or reposition it with CSS to fit your page layout.

---

## Local Viewing

**PMTiles requires HTTP Range requests** — you cannot open `index.html` directly from the filesystem (`file://`).

### Using the included `serve.py` (recommended)

```bash
cd <project_name>_webmap/
python serve.py
# Opens http://localhost:8000 automatically
```

`serve.py` handles Range requests, CORS headers, and CORS preflight — everything needed for PMTiles to work locally. By default it binds to `127.0.0.1` (loopback only). To test from another device on the same network, use `--host 0.0.0.0`.

### Other options

```bash
# Node.js (no install needed)
npx serve <project_name>_webmap/

# PHP
cd <project_name>_webmap/ && php -S localhost:8000
```

---

## Deployment

### Static hosting (GitHub Pages, Netlify, Vercel, S3)

Upload the entire `_webmap/` folder (inside the project subdirectory) to any static host that supports Range requests (all major CDNs do).

**GitHub Pages:**
```bash
cd <project_name>_webmap/
git init && git add . && git commit -m "web map"
git remote add origin https://github.com/username/my-webmap.git
git push -u origin main
# Enable GitHub Pages in repository Settings → Pages
```

**Netlify / Vercel:** Drag and drop the `_webmap/` folder to the dashboard, or connect your repository.

**AWS S3:**
```bash
aws s3 sync <project_name>_webmap/ s3://my-bucket/webmap/ --acl public-read
```

### Linux VPS with `serve.py` (low traffic)

`serve.py` can run as a persistent background service. Suitable for personal or small-team use. This setup serves over plain HTTP; add Nginx or Caddy in front if you need HTTPS.

**1. Create a dedicated service user:**
```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin mapsplat
```

**2. Copy and lock down files:**
```bash
sudo mkdir -p /var/www/myproject
sudo cp -r <project_name>_webmap/. /var/www/myproject/
sudo chown -R root:mapsplat /var/www/myproject
sudo find /var/www/myproject -type f -exec chmod 640 {} +
sudo find /var/www/myproject -type d -exec chmod 750 {} +
```

**3. Create `/etc/systemd/system/mapsplat-myproject.service`:**

`serve.py` defaults to `127.0.0.1` (loopback only). For direct public access without a reverse proxy, pass `--host 0.0.0.0`:

```ini
[Unit]
Description=MapSplat Web Map — My Project
After=network.target

[Service]
Type=simple
User=mapsplat
WorkingDirectory=/var/www/myproject
ExecStart=/usr/bin/python3 /var/www/myproject/serve.py --host 0.0.0.0 --no-browser
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadOnlyPaths=/var/www/myproject
ProtectHome=yes
CapabilityBoundingSet=
RestrictAddressFamilies=AF_INET AF_INET6

[Install]
WantedBy=multi-user.target
```

**4. Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable mapsplat-myproject
sudo systemctl start mapsplat-myproject
sudo systemctl status mapsplat-myproject
```

> For higher traffic, use Nginx (see below).

### Linux VPS with Caddy as the server (production)

Stock Caddy does **not** support HTTP Range requests for static files out of the box — Range request support requires a custom Caddy build with the [Caddy PMTiles module](https://docs.protomaps.com/deploy/server). If you cannot rebuild Caddy, the easiest approach is to run `serve.py` as a background service and let Caddy reverse-proxy to it. `serve.py` handles the Range requests; Caddy handles HTTPS termination and your existing routing.

**1. Create a dedicated service user and copy files** (same as the section above):
```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin mapsplat
sudo mkdir -p /var/www/myproject
sudo cp -r <project_name>_webmap/. /var/www/myproject/
sudo chown -R root:mapsplat /var/www/myproject
sudo find /var/www/myproject -type f -exec chmod 640 {} +
sudo find /var/www/myproject -type d -exec chmod 750 {} +
```

**2. Block the serve.py port from the public internet:**

`serve.py` defaults to binding `127.0.0.1` so external traffic can only reach it through Caddy. Add a firewall rule as belt-and-suspenders protection against misconfiguration:

```bash
sudo ufw deny 8001        # block serve.py port from outside
sudo ufw allow 443
sudo ufw allow 80
sudo ufw enable
```

**3. Create `/etc/systemd/system/mapsplat-myproject.service`:**

`serve.py` flags useful for server deployments:

- `--port PORT` — listen on a specific port (default: `8000`). Use this when running multiple maps on the same host.
- `--no-browser` — don't open a browser tab on startup (essential for headless servers).
- `--host HOST` — address to bind to (default: `127.0.0.1`). No change needed for Caddy deployments — the default is already loopback-only.

```ini
[Unit]
Description=MapSplat Web Map — My Project
After=network.target

[Service]
Type=simple
User=mapsplat
WorkingDirectory=/var/www/myproject
ExecStart=/usr/bin/python3 /var/www/myproject/serve.py --port 8001 --no-browser
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadOnlyPaths=/var/www/myproject
ProtectHome=yes
CapabilityBoundingSet=
RestrictAddressFamilies=AF_INET AF_INET6

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable mapsplat-myproject
sudo systemctl start mapsplat-myproject
```

**4. Add a reverse proxy block with security headers to your `Caddyfile`:**

```caddy
your-domain.com {
    reverse_proxy /myproject/* localhost:8001
    header {
        X-Content-Type-Options    "nosniff"
        X-Frame-Options           "SAMEORIGIN"
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        -Server
    }
}
```

Or if the entire site is just this map:

```caddy
your-domain.com {
    reverse_proxy localhost:8001
    header {
        X-Content-Type-Options    "nosniff"
        X-Frame-Options           "SAMEORIGIN"
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        -Server
    }
}
```

Replace `8001` with whatever port you set in `serve.py`. CORS headers (`Access-Control-Allow-Origin: *`) are already set by `serve.py` and do not need to be added to Caddy.

Caddy automatically provisions and renews a TLS certificate via Let's Encrypt. The Range requests pass through the reverse proxy transparently — `serve.py` handles them, Caddy just forwards.

> For higher traffic or if you want to serve the files directly without `serve.py`, use the [custom Caddy build with PMTiles support](https://docs.protomaps.com/deploy/server) or switch to Nginx (see below).

### Linux VPS with Nginx (production)

Nginx handles Range requests natively and can terminate HTTPS.

```bash
sudo apt install nginx
sudo cp -r <project_name>_webmap/ /var/www/myproject/
```

**`/etc/nginx/sites-available/myproject`:**
```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /var/www/myproject;

    location / {
        try_files $uri $uri/ =404;
    }

    # CORS headers for PMTiles (only needed if served from a different domain)
    location ~* \.pmtiles$ {
        add_header Access-Control-Allow-Origin  "*" always;
        add_header Access-Control-Allow-Methods "GET, HEAD, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Range" always;
        add_header Access-Control-Expose-Headers "Content-Length, Content-Range" always;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/myproject /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
# Add HTTPS:
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### CORS configuration

CORS is only needed when `index.html` and `.pmtiles` files are served from **different origins**. When served from the same domain (the typical case), no CORS configuration is required.

**Apache (.htaccess):**
```apache
<FilesMatch "\.pmtiles$">
    Header set Access-Control-Allow-Origin "*"
    Header set Access-Control-Allow-Methods "GET, HEAD, OPTIONS"
    Header set Access-Control-Allow-Headers "Range"
    Header set Access-Control-Expose-Headers "Content-Length, Content-Range"
</FilesMatch>
```

**AWS S3 CORS policy:**
```json
[{
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["Range"],
    "ExposeHeaders": ["Content-Range", "Content-Length", "ETag"],
    "MaxAgeSeconds": 3600
}]
```

---

## Style Editing with Maputnik

1. Export with **Export style.json** checked
2. Open [Maputnik](https://maputnik.github.io/) → **Open → Upload** and select `style.json`
3. Edit colors, widths, opacity, labels, etc.
4. **Export → Download** to save the edited file
5. In MapSplat, click **Import style.json…** to apply your edits to the next export

---

## Supported Symbology

| QGIS Renderer | Support | Notes |
|---------------|---------|-------|
| Single Symbol | Full | Fill, line, and marker symbol layers |
| Categorized | Full | MapLibre `match` expressions; per-category opacity preserved |
| Graduated | Full | MapLibre `interpolate` expressions for smooth color and size transitions |
| Rule-based | Partial | Simple filter rules converted; complex nested rules fall back to default |
| SVG marker (single symbol) | Full | Rasterised to sprite atlas; exported as MapLibre `symbol` layer |
| Heatmap | Fallback | Rendered as simple circles |
| Point Cluster | Fallback | Rendered as simple circles |
| Labels | Partial | Text field, font, size, color, halo, placement extracted; drop shadows and callouts omitted |

**Fill opacity**: Semi-transparent polygon fills are supported when transparency is set via the fill color's alpha channel. See [Opacity and transparency](#opacity-and-transparency) for the distinction between color alpha and layer-level opacity.

**Unsupported fill types**: Gradient fills, shape-burst fills, and pattern fills are approximated as solid colors. See [Unsupported fill and symbol types](#unsupported-fill-and-symbol-types) for details.

**Unit conversion**: QGIS millimetre sizes are converted to pixels at 96 DPI (1 mm ≈ 3.78 px).

### Label settings

Labels are converted from QGIS *Layer Properties → Labels* to MapLibre `symbol` layers. The following properties are read; everything else is silently omitted.

#### What is exported

| QGIS label property | Where to set it in QGIS | MapLibre property |
|---|---|---|
| Label field | *Labels → Label with* | `text-field` |
| Font family / bold / italic | *Text → Font* | `text-font` (Noto Sans Regular / Medium / Italic — see Font note) |
| Font size | *Text → Size* | `text-size` (converted to px; minimum 8 px enforced) |
| Text color | *Text → Color* | `text-color` |
| Text opacity | *Text → Opacity* | `text-opacity` |
| Capitalization | *Text → Style → Capitalization* | `text-transform` (uppercase / lowercase only; title-case is not available in MapLibre) |
| Line height | *Text → Formatting → Line height* | `text-line-height` |
| Word wrap | *Formatting → Wrap lines to* | `text-max-width` |
| Multiline alignment | *Formatting → Alignment* | `text-justify` (left / center / right) |
| Text buffer (halo) | *Buffer → Draw text buffer* | `text-halo-color`, `text-halo-width` — **see below** |
| Quadrant / anchor (points) | *Placement → Quadrant* | `text-anchor` (exact mode) or `text-variable-anchor` (auto mode) |
| Offset distance (points) | *Placement → Distance* | `text-offset` / `text-radial-offset` |
| X / Y offset (points) | *Placement → Offset X/Y* | combined into `text-offset` |
| Repeat distance (lines) | *Placement → Repeat every* | `symbol-spacing` |
| Curved placement (lines) | *Placement → Placement → Curved* | `symbol-placement: line` + `text-max-angle: 45` |
| Horizontal on line | *Placement → Placement → Horizontal* | `symbol-placement: line-center` |

#### Font note

MapLibre requires fonts to be served from a glyph tile server. MapSplat uses the Protomaps font server, which provides three variants:

| QGIS font style | MapLibre font used |
|---|---|
| Bold (any family) | `Noto Sans Medium` |
| Italic (any family) | `Noto Sans Italic` |
| Regular (any family) | `Noto Sans Regular` |

The font **family** you choose in QGIS is ignored — only bold/italic flags are carried through. If you need a specific typeface, edit `style.json` in Maputnik and point `glyphs` at a font server that hosts your chosen family.

#### Text buffer (halo)

The text buffer in QGIS is the white (or colored) outline around label text that improves legibility against busy backgrounds. In MapLibre this maps to `text-halo-color` and `text-halo-width`.

**How to enable it in QGIS:**

1. Open *Layer Properties → Labels → Buffer* tab
2. Check **Draw text buffer**
3. Set **Size** (e.g. 1 mm is a good starting point; 0.5 mm is subtle, 2 mm is prominent)
4. Set **Color** (white `#ffffff` is the most common choice)
5. Optionally lower **Opacity** for a semi-transparent halo

**What MapSplat reads:**

- **Buffer enabled**: only emitted in the output when *Draw text buffer* is checked. If the buffer is unchecked, no halo appears in the exported map — even if you previously had one.
- **Buffer color**: full color including alpha channel. If you set the color's alpha to less than 100 %, or lower the *Opacity* slider, the exported halo uses `rgba(...)` to preserve transparency.
- **Buffer size**: converted from QGIS units to pixels using the same unit conversion as symbol sizes (1 mm ≈ 3.78 px). A minimum of 1 px is enforced — very small buffers will snap up to 1 px.
- **Buffer opacity**: both the buffer's *Opacity* slider and the color's own alpha channel are read. Either or both can be used.

**Common pitfall**: the buffer is a per-label-format setting, not a layer-level setting. If you copy a style from another layer, check that the buffer is still enabled on the destination layer.

#### Placement modes

The **Viewer tab → Label placement** setting controls how point-layer labels are positioned:

- **Match QGIS (exact)**: reads the *Quadrant* setting and X/Y offset from QGIS. Labels appear in the same relative position as in the QGIS canvas (above-right, below-left, etc.). Overlapping labels are not automatically moved — you may see clutter at small zooms.
- **Auto-place (avoid overlaps)**: ignores the quadrant and instead uses MapLibre's `text-variable-anchor` with all eight positions. MapLibre tries each position in order and picks one that does not overlap other labels. Better for dense datasets; less predictable positioning.

Line labels follow the QGIS placement setting (Curved vs. Horizontal) regardless of the mode switch.
Polygon labels always use centroid placement.

#### What is NOT exported

The following QGIS label options have no equivalent in MapLibre GL Style JSON and are silently omitted:

- **Drop shadows** — no MapLibre equivalent
- **Background shapes** (label bounding box fill/border) — no MapLibre equivalent
- **Callout lines** (leader lines) — no MapLibre equivalent
- **Complex label expressions** — only simple field names are supported; QGIS string concatenation expressions (`'Name: ' || "field"`) are not parsed and will produce no label
- **Scale-based label visibility** — `minzoom` / `maxzoom` are set on both symbol and label layers from the QGIS *Rendering → Scale-based visibility* setting, but the conversion is an approximation (Web Mercator at equator, 96 DPI); results may differ slightly from the QGIS canvas at the exact threshold scale
- **Letter spacing** — not available in MapLibre for vector tile labels
- **Multiple text formats** within one label (e.g. bold first word, regular rest)

---

## Troubleshooting

### Map is blank / tiles don't load

1. Open the browser console (F12 → Console) and look for errors
2. Confirm you are using `serve.py` or a proper web server — not `file://`
3. Verify `data/layers.pmtiles` exists and is not 0 bytes
4. If using basemap overlay, verify `data/basemap.pmtiles` also exists

### "ogr2ogr not found"

GDAL 3.8+ is required:
```bash
ogr2ogr --version
# Ubuntu/Debian:
sudo apt update && sudo apt install gdal-bin
```

### "pmtiles CLI not found" (basemap overlay)

Download from [go-pmtiles releases](https://github.com/protomaps/go-pmtiles/releases) and place on your PATH:
```bash
# Linux x86_64 example
wget https://github.com/protomaps/go-pmtiles/releases/latest/download/go-pmtiles_Linux_x86_64.tar.gz
tar xf go-pmtiles_Linux_x86_64.tar.gz
sudo mv pmtiles /usr/local/bin/
pmtiles --version
```

### Style not applied / wrong colors

Verify that layer names in `style.json` match the `source-layer` names in the PMTiles file. Use the [PMTiles Viewer](https://pmtiles.io/) to inspect your file.

### POI / culvert icons missing in basemap overlay mode

Ensure you are on v0.5.5 or later. Earlier versions passed `style.json` as a URL string, which prevented icon layers from rendering when two PMTiles sources were present.

---

## Development

### Build commands

```bash
cd Plugins/mapsplat

make compile   # Compile Qt resources (run after editing resources.qrc)
make deploy    # Copy to QGIS default profile
make package   # Produce mapsplat.zip for distribution
make test      # Run unit tests
make clean     # Remove compiled/cached files
```

### Project structure

```
mapsplat/
├── __init__.py              # Plugin entry point (classFactory)
├── mapsplat.py              # Plugin lifecycle: toolbar, menu, dockwidget init
├── mapsplat_dockwidget.py   # All UI: settings, validation, export trigger
├── exporter.py              # Export orchestration; generate_html_viewer()
├── style_converter.py       # QGIS renderer → MapLibre Style JSON v8
├── config_manager.py        # TOML config read/write (no external dependencies)
├── log_utils.py             # Timestamped log line formatter
├── metadata.txt             # Plugin metadata (version, changelog)
├── Makefile                 # Build automation
├── docs/
│   ├── CHANGELOG.md         # Full version history
│   ├── PLAN.md              # Design notes and architecture decisions
│   ├── REQUIREMENTS.md      # Technical requirements
│   ├── TODO.md              # Planned features and known issues
│   └── images/              # Logo and screenshots
└── test/                    # Unit tests (pure-Python, no QGIS required)
    ├── test_style_converter.py
    ├── test_config_manager.py
    ├── test_log_writer.py
    └── test_viewer_controls.py
```

### Architecture notes

- Export pipeline: `QgsVectorFileWriter` → GeoPackage → `ogr2ogr` (via `QProcess`) → PMTiles
- `style_converter.py` walks QGIS renderers and builds MapLibre Style JSON v8; unit conversion `MM_TO_PX = 3.78`
- `generate_html_viewer()` in `exporter.py` is a standalone function with no Qt dependencies, enabling unit testing
- The HTML viewer fetches `style.json` at runtime (not as a URL string) so MapLibre correctly resolves `pmtiles://` source URLs
- Basemap overlay uses `pmtiles extract` via `QProcess` with the same polling/cancellation pattern as `ogr2ogr`
- Config files store layer **names**, not runtime QGIS layer IDs, so they are portable across sessions

### Versioning and releases

Bump `__version__` in all seven `.py` modules and `version=` in `metadata.txt` together. Update `docs/CHANGELOG.md`. Releases are created by pushing a version tag — the CI workflow builds `mapsplat.zip` and publishes the GitHub Release automatically:

```bash
git tag v0.6.6
git push origin v0.6.6
```

---

## Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Write tests for new functionality (tests live in `test/`)
4. Bump `__version__` in all seven `.py` files and `metadata.txt`, update `docs/CHANGELOG.md`
5. Push and open a Pull Request

See [TODO.md](docs/TODO.md) for planned features and known issues.

---

## License

MIT — see [LICENSE](../../LICENSE) for details.

## Credits

- [MapLibre GL JS](https://maplibre.org/) — Open-source map rendering library
- [PMTiles](https://protomaps.com/docs/pmtiles) — Single-file tile archive format
- [Protomaps Basemaps](https://github.com/protomaps/basemaps) — Open basemap tiles and styles
- [Maputnik](https://maputnik.github.io/) — Visual MapLibre style editor
- [QGIS](https://qgis.org/) — Geographic Information System

## Links

- **Repository**: https://github.com/johnzastrow/mapsplat
- **Issues**: https://github.com/johnzastrow/mapsplat/issues
- **Releases**: https://github.com/johnzastrow/mapsplat/releases
- **Documentation**: [docs/](docs/)
