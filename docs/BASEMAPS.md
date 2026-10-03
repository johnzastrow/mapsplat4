# Basemaps

MapSplat can publish a map entirely from your own data (it provides the styling), or you can add a
basemap beneath your layers.

## Options

- **No basemap** — publish just your data; MapSplat styles it.
- **Protomaps PMTiles** — overlay your data on a Protomaps basemap (streets, places, water, …).
  **Download & clip** it into the export (clipped to your data's extent with the `pmtiles` CLI;
  **Latest** fills in the newest daily build), or **stream** a PMTiles file you host with CORS.
  Protomaps' daily builds cannot be streamed: browsers on other sites are refused.
  Five Protomaps styles (Light, Dark, White, Grayscale, Black) ship with the plugin; a custom
  `style.json` is optional.
- **XYZ raster** — an online provider (OpenStreetMap, Carto, OpenTopoMap, Esri World Imagery, or a
  custom `{z}/{x}/{y}` URL). Streams live; attribution is added automatically. See
  [Hosting](HOSTING.md) for what "streams live" means for self-hosting.

**Step-by-step guide:** the **?** button beside *Basemap Overlay* opens the bundled
[basemap guide](https://johnzastrow.github.io/mapsplat4/basemaps.html) (`help/basemaps.html`).

## Protomaps basemaps

MapSplat builds on the work of [Protomaps](https://protomaps.com/), who publish a daily planet build
of map tiles in PMTiles format from OpenStreetMap data (about 138 GB). You never download the whole
planet: in **download & clip** mode MapSplat reads only your export area from the build (click
**Latest** for today's URL) and stores it as `data/basemap.pmtiles`; a city at zoom 14 is a few MB.
To clip once and reuse the file, run the command from **Copy extract command** yourself and choose
**Source: Local file**. Download & clip needs the `pmtiles` CLI on your PATH.

Protomaps keeps daily builds for about a week (plus the latest build of each patch version) and
discourages hotlinking them; their servers also refuse browser reads from other sites, so a daily
build cannot be *streamed*. To stream, host a PMTiles file yourself with CORS enabled (see
[Hosting](HOSTING.md#hosting-a-streamable-basemap)).

**Styles.** The built-in styles are generated from the official `@protomaps/basemaps` package
(`scripts/gen_basemap_styles.mjs`); a custom Protomaps-compatible `style.json` also works (for
example from *Get style JSON* on [maps.protomaps.com](https://maps.protomaps.com)). The built-in
styles load fonts and icons from `protomaps.github.io` when the map is viewed, so labels and icons
need internet even when the basemap is clipped.

**Licence.** Protomaps basemap data is an ODbL Produced Work; OpenStreetMap attribution is required
and MapSplat adds it to the map. The styles are BSD-3-Clause (code) and CC0 (design); their licence
ships in `basemap_styles/`.

- [Builds of global map tiles](https://maps.protomaps.com/builds/)
- [More info on basemaps](https://docs.protomaps.com/basemaps/downloads)
- [pmtiles.io — preview/test your tiles](https://protomaps.com/blog/new-pmtiles-io/)
- [Live map viewer of the global tiles](https://maps.protomaps.com/#flavorName=light&lang=en&map=4.04/49.02/-100.57)
- [pmtiles CLI docs](https://docs.protomaps.com/pmtiles/cli)

## Basemap extract cache

Clipped basemap extracts are cached (keyed by source + extent + max zoom), so re-exporting the same
area reuses the previous download. Use **Refresh basemap cache** to force a re-download or **Clear
basemap cache** to free disk space, both under **Advanced Options** on the **Inputs** tab.
