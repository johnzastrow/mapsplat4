# Basemaps

MapSplat can publish a map entirely from your own data (it provides the styling), or you can add a
basemap beneath your layers.

## Options

- **No basemap** — publish just your data; MapSplat styles it.
- **Protomaps PMTiles** — overlay your data on a Protomaps-compatible basemap (streets, terrain, …),
  from a local `.pmtiles` file or a remote URL. **Stream** it live, or **download & clip** it offline
  (clipped to your data's extent with the `pmtiles` CLI).
- **XYZ raster** — an online provider (OpenStreetMap, Carto, OpenTopoMap, Esri World Imagery, or a
  custom `{z}/{x}/{y}` URL). Streams live; attribution is added automatically. See
  [Hosting](HOSTING.md) for what "streams live" means for self-hosting.

## Protomaps basemaps

MapSplat builds on the work of [Protomaps](https://protomaps.com/), who host builds of global map
tiles in PMTiles format using OpenStreetMap data. Download the latest build, then let MapSplat trim it
to your extent at export time (or trim it yourself with the `pmtiles` CLI). For **download & clip**
mode the `pmtiles` CLI must be on your PATH. You'll also want a basemap style JSON — Protomaps
provides one, and MapSplat adapts it to work more standalone.

- [Builds of global map tiles](https://maps.protomaps.com/builds/)
- [More info on basemaps](https://docs.protomaps.com/basemaps/downloads)
- [pmtiles.io — preview/test your tiles](https://protomaps.com/blog/new-pmtiles-io/)
- [Live map viewer of the global tiles](https://maps.protomaps.com/#flavorName=light&lang=en&map=4.04/49.02/-100.57)
- [pmtiles CLI docs](https://docs.protomaps.com/pmtiles/cli)

## Basemap extract cache

Clipped basemap extracts are cached (keyed by source + extent + max zoom), so re-exporting the same
area reuses the previous download. Use **Refresh basemap cache** to force a re-download or **Clear
basemap cache** to free disk space, both under **Advanced Options**.
