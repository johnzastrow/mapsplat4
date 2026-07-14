# MapSplat

**Export QGIS projects to self-contained static web maps — PMTiles + MapLibre GL JS.**

![MapSplat](docs/images/logo.svg)

[![QGIS](https://img.shields.io/badge/QGIS-4.0%2B-green.svg)](https://qgis.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-0.43.0-orange.svg)](docs/CHANGELOG.md)

MapSplat is a QGIS plugin that "splats" your project layers into a self-contained web map you can host
anywhere static — any web server, cloud storage, or locally. **No tile server, no backend, no new
stack.** Your QGIS styling, labels, and layer order come along for the ride.

> This project targets QGIS 4.x and is written almost entirely by AI.

| Your QGIS project | The exported web map |
|---|---|
| <img src="docs/screenshots/test_in_qgis.png" width="420" /> | <img src="docs/screenshots/output.png" width="420" /> |

---

## Quick start

1. **Install** — download the latest `mapsplat.zip` from [Releases](https://github.com/johnzastrow/mapsplat4/releases)
   and add it in QGIS via **Plugins → Manage and Install Plugins → Install from ZIP**. For offline
   basemaps and raster export, also put the [pmtiles CLI](https://github.com/protomaps/go-pmtiles/releases)
   on your PATH (not needed for basemap **Stream** mode).
2. **Style your layers in QGIS** as you want them online, and zoom to your starting view.
3. **Open the MapSplat dock** and tick the layers to export (**Inputs** tab).
4. *(Optional)* Enable a basemap and keep the max zoom small to start (**Options** tab).
5. **Export**, then open the output folder and run `python serve.py` — your browser opens the map.

Full walk-through with pictures: **[User Guide](docs/USER_GUIDE.md)** · screenshot tour:
**[Gallery](docs/screenshots/README.md)**.

---

## Documentation

| Doc | What's in it |
|---|---|
| 📖 [User Guide](docs/USER_GUIDE.md) | Step-by-step: prepare → export → view → deploy, with Caddy/nginx config |
| ✨ [Features](docs/FEATURES.md) | Everything MapSplat does (export, styling, tools, tiles, basemaps) |
| 🗺️ [Basemaps](docs/BASEMAPS.md) | Protomaps, XYZ providers, and the extract cache |
| 🌐 [Hosting & self-hosting scope](docs/HOSTING.md) | What's bundled (PMTiles) vs streamed (🌐), and how to serve it |
| 🧰 [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and fixes |
| ⚠️ [Limitations](docs/LIMITATIONS.md) | Known gaps and unsupported symbology |
| 🖼️ [Screenshots](docs/screenshots/README.md) | Annotated tour of the plugin and viewer |
| 📝 [Changelog](docs/CHANGELOG.md) | Release history |
| 🎬 [Tutorial script](docs/TUTORIAL_SCRIPT.md) | Storyboard for a demo video |
| 🧭 [Roadmap / backlog](docs/FEATURE_BACKLOG.md) | What's planned next |
| 🗃️ [Design archive](docs/design/README.md) | Historical planning & design notes |

---

## Requirements

| Requirement | Version | Notes |
|---|---|---|
| QGIS | 4.0+ | This project targets QGIS 4 (Qt6) |
| GDAL | 3.8+ | PMTiles via `ogr2ogr`; MBTiles driver needed for raster export |
| Python | 3.9+ | Bundled with QGIS |
| pmtiles CLI | any | Basemap **bundle** mode + raster export (not **Stream** mode) |

## Installation

**From ZIP (recommended):** download `mapsplat.zip` from
[Releases](https://github.com/johnzastrow/mapsplat4/releases) → QGIS **Plugins → Manage and Install
Plugins → Install from ZIP** → restart QGIS.

**From source (development):** clone the repo and copy/symlink the plugin folder into your QGIS
profile's `python/plugins/` directory, then enable it in the Plugin Manager.

---

## Contributing

Issues and PRs welcome. Please keep changes small and focused; the plugin follows a security-first,
QGIS-4-only baseline. See the [roadmap](docs/FEATURE_BACKLOG.md) for planned work.

## License

MIT — see [LICENSE](LICENSE).

## Credits

Built on [Protomaps](https://protomaps.com/) (PMTiles), [MapLibre GL JS](https://maplibre.org/),
[GDAL/OGR](https://gdal.org/), and [QGIS](https://qgis.org/). Basemap tiles © OpenStreetMap
contributors.
