# Introduction to po

**We need a better name.**

## Overall Goal

The intent of the project to create a QGIS plugin that can be used to Publish Online (PO) static vector GIS data and styling information to a web server. The publishing format will be a modern, vector file format along with hopefully standards-based style information where each can be usable by existing web mapping libraries and applications. See the review of standards below. We should target the upcoming QGIS 4, based on Qt6 if enough information is possible. Or at least create it in a way to ease migration later this spring.

The plugin will be designed to be easy to use (few controls and sensible defaults) and will allow users to quickly (small number of clicks and publishing steps) publish their GIS data and styling information to the web (initially target a remote, VPS instance running linux where user has root control) without needing to have extensive knowledge of web development or GIS software, or complex styling rules. The plugin will be developed with the goal of making it accessible to a wide range of users, including GIS professionals, students, and hobbyists. We will implement in phases with a simple output suitable for manually publishing as a first step.

The final goal is to provide the easy "Export as.." type function where a user exports a QGIS project with all of its data and styling to a collection of data, code, and configuration files that can be copied to a simple web server to create an interactive web map based on static vector data where the source data are vectors and optionally supported by raster base layers.

## Phase 1

The first phase of the project will focus on developing the core functionality of the plugin, which will include the ability to select layers from a QGIS project, specify styling information for each layer, and publish the data to the local file system. The user will then be left to provide a map server that can read the published data and styling information and upload the newly created files for the map server to use.

## Phase 2

Perhaps be able to publish directly to a web server, along with some basic map server configuration. This would be a stretch goal, but it would be nice to have the option to publish directly to a web server without needing to manually upload the files. The plugin could include options for users to specify their web server credentials and upload the files directly from the plugin.

## Background

### Viable vector formats - MVT is the (old?) standard

Mapbox Vector Tiles (MVT) are a compact, binary format (Google Protobufs) used for transmitting and rendering geographic vector data in map applications. They enable efficient, client-side rendering of interactive, zoomable maps, allowing for customized styling, data interaction, and smaller data transfer sizes compared to raster tiles. MVT is the industry standard for vector data, widely used with mapping tools like MapLibre and OpenLayers.

#### Key Aspects of MVT Tiles

* **Format and Structure**: MVT files are encoded using Google Protobufs and typically use the .mvt file extension.
Performance: While they enable smooth zooming and interaction, rendering MVT on the client side can sometimes be a performance bottleneck, particularly on slower hardware, compared to pre-rendered raster images.
* **Applications**: They are ideal for interactive, dynamic maps, allowing features to be queried, styled, and updated on the fly.
* **Serving and Storage**: MVT tiles can be generated from databases (like PostGIS) and served, or stored in formats like MBTiles or PMTiles for efficient storage and access.
Industry Adoption: The specification is widely supported across various tools and platforms, including OpenLayers, MapLibre, and Deck.gl.

#### Advantages and Disadvantages

* **Pros**: High-quality, client-side styling; reduced bandwidth usage; support for interactivity; smooth zooming.
* **Cons**: Higher client-side computational cost (rendering) compared to raster images; can be complex to implement efficiently.
  

MVT tiles are generally considered the standard for modern, dynamic map visualizations.

#### Alternative File and Storage Formats

* **GeoPackage (GPKG)**: A lightweight, open, and platform-independent format for transferring geospatial information. It can contain large amounts of complex data in a single file and is a good option for offline use or data distribution.
* **MBTiles (.mbtiles)**: This is a specification for storing a collection of map tiles in a single SQLite database file. While the specification originally intended to hold raster tiles, it is commonly used to store Mapbox Vector Tiles (PBF format) as well, which is an efficient way to manage a large number of tiles in a single archive.
* **PMTiles (.pmtiles)**: An "on-demand" single-file archive format for vector or raster tiles. It allows client-side mapping libraries to fetch individual tiles using HTTP Range Requests, eliminating the need for a dedicated tile server to manage millions of individual files and allowing hosting on simple static storage like Amazon S3.
* **Folder with individual PBF files**: The simplest approach involves storing individual vector tile files (in PBF format) in a standard Z/X/Y directory structure on a server.

While the Mapbox Vector Tile (.mvt) format is the industry standard for vector map data, several alternatives exist depending on whether you need a different storage container, a more efficient cloud-native format, or a completely different encoding.

1. **Advanced Container & Transport Formats**
These formats address the limitations of standard .mvt files, such as hosting complexity and large dataset performance.

* **PMTiles**: A single-file archive format for tile pyramids. Unlike thousands of individual .mvt files, a single PMTiles file can be hosted on Amazon S3 and queried via HTTP Range Requests, eliminating the need for a tile server.

* **MBTiles**: An SQLite-based container format that packages tiles into a single database file. It is widely used for offline mobile maps and easier file management.
  
* **GeoArrow**: A high-performance alternative for massive datasets. It avoids the overhead of parsing MVT or GeoJSON by using a memory-efficient columnar format that can be loaded directly onto a GPU.

##### Generating Tiles with ogr2ogr

ogr2ogr can generate several tile-related formats, primarily by utilizing its MVT, MBTiles, and PMTiles drivers. While ogr2ogr is a vector tool, it can also produce some raster tile containers.

1. **Vector Tile Formats**
These formats store map data as geometric features rather than images.
Mapbox Vector Tiles (.mvt / .pbf): Can be output as a standard directory of files (e.g., z/x/y.pbf).

* **MBTiles (.mbtiles)**: A vector tile container stored within an SQLite database. It can be produced by specifying -f MVT and a .mbtiles output extension.
* **PMTiles (.pmtiles)**: A single-file archive for vector tiles. ogr2ogr supports writing to this format as of GDAL version 3.8.

2. **Raster & Hybrid Tile Formats**
   ogr2ogr can write to these containers, though it typically converts vector features into their internal data structures rather than rendering them as images itself.

* **GeoPackage (.gpkg)**: Supports both vector features and raster/terrain tile sets. While ogr2ogr primarily handles the vector layers, it can be used to manage the GeoPackage container which supports tile extensions.
* **MBTiles (Raster)**: While mostly a gdal_translate task, ogr2ogr can read vector data from MBTiles containers and is part of the same GDAL suite used to manage these files.

3. Emerging Cloud-Native Formats

* **Cloud Optimized Point Cloud (COPC)**: While specialized, GDAL/OGR includes drivers that support reading and writing COPC, which uses a clustered/tiled structure for massive point datasets.
* **TileDB**: A multi-dimensional array format that can store vector data in a tiled sparse array for high-performance cloud access.

Summary Table of Output Commands

| Target Format | Example Command |
| --- | --- |
| Directory of .pbf | ogr2ogr -f MVT output_dir input.shp |
| Vector MBTiles | ogr2ogr -f MVT output.mbtiles input.shp -dsco FORMAT=MBTILES |
| PMTiles | ogr2ogr -f PMTiles output.pmtiles input.mbtiles |
| GeoPackage | ogr2ogr -f GPKG output.gpkg input.shp |

To convert a GeoPackage (`.gpkg`) to PMTiles (`.pmtiles`) using `ogr2ogr`, you can use the following command structure. PMTiles are generated in Web Mercator (EPSG:3857) by default. 

Basic Conversion Command



```
ogr2ogr -f "PMTiles" output.pmtiles input.gpkg
```

Recommended Command (with Zoom Levels) 

It is highly recommended to specify minimum and maximum zoom levels to control file size and performance. 



```
ogr2ogr -dsco MINZOOM=0 -dsco MAXZOOM=14 -f "PMTiles" output.pmtiles input.gpkg
```

Key Options

- **`-f "PMTiles"`**: Specifies the output format.
- **`-dsco MINZOOM=n`**: Minimum zoom level.
- **`-dsco MAXZOOM=n`**: Maximum zoom level.
- **`-t_srs EPSG:3857`**: (Optional) Ensures the output is in Web Mercator if the input is in a different projection. 

Handling Multiple Layers 

If your GeoPackage has multiple layers, `ogr2ogr` will include them all by default. You can use `-lco LAYER_NAME=...` to name layers or only convert specific layers by listing them at the end of the command. 

For larger datasets, while `ogr2ogr` works, [Tippecanoe](https://github.com/felt/tippecanoe) is often recommended for more efficient, higher-performance PMTiles generation. 

Free PMTiles files can be downloaded from [Protomaps](https://protomaps.com/blog/pmtiles-v3-whats-new/) and [Source Cooperative](https://source.coop/smartmaps/opencellid), offering OpenStreetMap-based vector tiles and other datasets. The command-line tool `go-pmtiles` is used to manage and extract specific areas from these files, with releases available on [GitHub](https://github.com/protomaps/go-pmtiles/releases). 

**Key Resources to Download PMTiles for Free:**

- **Protomaps Downloads:** Offers daily updated, OpenStreetMap-derived basemap tilesets in V3 format for small-area or larger regions.
- **[Mapterhorn](https://docs.protomaps.com/basemaps/downloads):** Provides elevation data (Terrarium-encoded RGB) in PMTiles format.
- **Source Cooperative:** Provides open-source data, such as OpenCelliD for cell tower locations, in PMTiles format.
- **[PMTiles Viewer](https://pmtiles.io/):** A tool to visualize and inspect .pmtiles files, including examples. 

**Tools to Extract/Create PMTiles:**

- **`go-pmtiles`:** Download the binary from GitHub to extract specific geographical areas from a larger file using commands like `pmtiles extract`.
- **`tippecanoe`:** A tool to create PMTiles from GeoJSON or Shapefiles. 

**Usage Information:**

- **Libraries:** Supported in [Leaflet](https://github.com/protomaps/PMTiles/blob/main/README.md), MapLibre GL JS, and OpenLayers.
- **Serverless:** PMTiles are designed for "serverless" hosting on services like GitHub Pages or S3, eliminating the need for a dedicated tile server. 



# What's new in PMTiles V3

Oct 31, 2022

**PMTiles is a single-file archive format for map tiles**, optimized for the cloud. Think about it like [MBTiles](https://github.com/mapbox/mbtiles-spec), where the database can live on another computer or static storage like S3; or as a minimal alternative to [Cloud Optimized GeoTIFFs](https://www.cogeo.org/) for any tiled data - remote sensing readings, photographs, or vector GIS features.

Why adopt PMTiles? Companies like [Felt, a collaborative mapmaking app, are using PMTiles for user-uploaded datasets](https://felt.com/blog/upload-anything) - eliminating the need to run map tile servers at all.

## Spec version 3

[Read the specification on GitHub](https://github.com/protomaps/PMTiles/blob/master/spec/v3/spec.md)

In its first year of existence, PMTiles focused on being the simplest possible implementation of the [HTTP Byte Range](https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests) read strategy. **PMTiles V3** is a revision that makes the retrieval and storage of tiles not just *simple* but also *efficient*. Minimizing archive size and the number of intermediate requests has a direct effect on the latency of tile requests and ultimately the end user experience of viewing a map on the web.

### File Structure

- **97% smaller overhead** - Spec version 2 would always issue a 512 kilobyte initial request; version 3 reduces this to **16 kilobytes.** What remains the same is that nearly any map tile can be retrieved in at most two additional requests.
- **Unlimited metadata** - version 2 had a hard cap on the amount of JSON metadata of about 300 kilobytes; version 3 removes this limit. This is essential for tools like [tippecanoe](http://github.com/felt/tippecanoe) to store detailed column statistics. Essential archive information, such as tile type and compression methods, are stored in a binary header separate from application metadata.
- **Hilbert tile IDs** - tiles internally are addressed by a single 64-bit Hilbert tile ID instead of Z/X/Y. See the [blog post on Tile IDs for details.](https://protomaps.com/blog/pmtiles-v3-hilbert-tile-ids/)
- **Archive ordering** - An optional `clustered` mode enforces that tile contents are laid out in Tile ID order.
- **Compressed directories and metadata** - Directories used to fetch offsets of tile data consume about 10% the space of those in version 2. See the [blog post on compressed directories](https://protomaps.com/blog/pmtiles-v3-layout-compression) for details.

## JavaScript

- **Compression** - The TypeScript [pmtiles](https://github.com/protomaps/PMTiles/tree/master/js) library now includes a decompressor - [fflate](https://github.com/101arrowz/fflate) - to allow reading compressed vector tile archives directly in the browser. This reduces the size and latency of vector tiles by as much as 70%.
- **Tile Cancellation** - All JavaScript plugins now support *tile cancellation*, meaning quick zooming across many levels will interrupt the loading of tiles that are never shown. This has a significant effect on the perceived user experience, as tiles at the end of a animation will appear earlier.
- **ETag support** - clients can detect when files change on static storage by reading the [ETag](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag) HTTP header. This means that PMTiles-based map applications can update datasets in place at low frequency without running into caching problems.

### Inspector app

[PMTiles on GitHub](https://github.com/protomaps/PMTiles) now hosts an open source inspector for local or remote archives. View an archive hosted on your cloud storage (CORS required) - or drag and drop a file from your computer - no server required.

<video controls="" preload="auto" width="100%" playsinline="" class="html-video" style="box-sizing: border-box; border-width: 0px; border-style: solid; border-color: rgb(229, 231, 235); --tw-border-spacing-x: 0; --tw-border-spacing-y: 0; --tw-translate-x: 0; --tw-translate-y: 0; --tw-rotate: 0; --tw-skew-x: 0; --tw-skew-y: 0; --tw-scale-x: 1; --tw-scale-y: 1; --tw-pan-x: ; --tw-pan-y: ; --tw-pinch-zoom: ; --tw-scroll-snap-strictness: proximity; --tw-gradient-from-position: ; --tw-gradient-via-position: ; --tw-gradient-to-position: ; --tw-ordinal: ; --tw-slashed-zero: ; --tw-numeric-figure: ; --tw-numeric-spacing: ; --tw-numeric-fraction: ; --tw-ring-inset: ; --tw-ring-offset-width: 0px; --tw-ring-offset-color: #fff; --tw-ring-color: rgb(59 130 246 / 0.5); --tw-ring-offset-shadow: 0 0 #0000; --tw-ring-shadow: 0 0 #0000; --tw-shadow: 0 0 #0000; --tw-shadow-colored: 0 0 #0000; --tw-blur: ; --tw-brightness: ; --tw-contrast: ; --tw-grayscale: ; --tw-hue-rotate: ; --tw-invert: ; --tw-saturate: ; --tw-sepia: ; --tw-drop-shadow: ; --tw-backdrop-blur: ; --tw-backdrop-brightness: ; --tw-backdrop-contrast: ; --tw-backdrop-grayscale: ; --tw-backdrop-hue-rotate: ; --tw-backdrop-invert: ; --tw-backdrop-opacity: ; --tw-backdrop-saturate: ; --tw-backdrop-sepia: ; --tw-contain-size: ; --tw-contain-layout: ; --tw-contain-paint: ; --tw-contain-style: ; display: block; vertical-align: middle; max-width: 100%; height: auto; margin-top: 2em; margin-bottom: 2em;"></video>

### Leaflet

For raster tiles, there is first-class support for loading PNG or JPG image archives into Leaflet via the tiny (7 kilobytes!) `PMTiles` library like this:

```js
const p = new pmtiles.PMTiles('example.pmtiles')
pmtiles.leafletRasterLayer(p).addTo(map)
```

For vector tiles, you’ll need to use [protomaps.js](https://github.com/protomaps/protomaps.js), the from-scratch renderer built for vector rendering and labeling using plain Canvas. It’s only about 32 kilobytes - a fraction of the size of an alternative like MapLibre GL JS - and now supports V3 archives.

### MapLibre GL JS

The MapLibre [protocol plugin](https://maplibre.org/maplibre-gl-js-docs/api/properties/#addprotocol) has a new, simpler API; specifying the archive under a source `url` will automatically infer the archive’s `minzoom` and `maxzoom`.

```json
"sources": {
    "example_source": {
        "type": "vector",
        "url": "pmtiles://https://example.com/example.pmtiles",
    }
}
```

## Python

[pmtiles/python on GitHub](https://github.com/protomaps/PMTiles/tree/master/python)

- Python libraries are now modular and can have data sources swapped out. A PMTiles file can be read from disk, or a custom function can be provided to grab byte ranges from AWS via the boto library, Google Cloud, or any other blob data source.
- Python command line utilities have been deprecated as the first-class tooling for creating and working with PMTiles.

## Go

[go-pmtiles on GitHub](http://github.com/protomaps/go-pmtiles)

The greatest obstacle to adopting PMTiles for many users was the need to have a working Python 3 installation on your computer.

The official PMTiles tooling is now a single-file executable you can download at [GitHub Releases](https://github.com/protomaps/go-pmtiles/releases).

Example for converting an MBTiles archive:

```sh
pmtiles convert input.mbtiles output.pmtiles
```

This will spit out some facts on the internals of your archive:

```
tippecanoe ne_10m_admin_1_states_provinces.geojsonseq -o ne_10m_admin_1_states_provinces.mbtiles -z8
pmtiles convert ne_10m_admin_1_states_provinces.mbtiles ne_10m_admin_1_states_provinces.pmtiles
...
# of addressed tiles:  40560
# of tile entries (after RLE):  20733
# of tile contents:  18933
Root dir bytes:  57
Leaves dir bytes:  53570
Num leaf dirs:  6
Total dir bytes:  53627
Average leaf dir bytes:  8928
Average bytes per addressed tile: 1.32
Finished in  444.930625ms
```

The above shows that the sample dataset - [Admin 1 boundaries from Natural Earth](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/) has more than 50% redundant tiles. Although about 40,000 tiles are addresses by the archive, only 19,000 tiles are stored.

On average, only **1.3 bytes or 11 bits** is needed per tile in the directory index after compression!

To upgrade your PMTiles V2 archive to V3:

```sh
pmtiles convert input_v2.pmtiles output_v3.pmtiles
```

Inspect a PMTiles V3 archive:

```sh
pmtiles show file://. output.pmtiles
```

Uploading your archive to cloud storage, once you’ve put your credentials in environment variables:

```sh
pmtiles upload LOCAL.pmtiles "s3://BUCKET_NAME?endpoint=https://example.com&region=region" REMOTE.pmtiles
```

## Ecosystem

- Bringing PMTiles support to [OpenLayers (GitHub issue #3)](https://github.com/protomaps/PMTiles/issues/3).
- Luke Seelenbinder has started a implementation of [PMTiles in Rust](https://github.com/stadiamaps/pmtiles-rs).

## Free Downloads

Finally, you can download OpenStreetMap-derived, up-to-the minute basemap tilesets from [protomaps.com/downloads](https://protomaps.com/downloads), now only delivered in the V3 format. Small-area downloads are perfect for your hyper-local mapping project that will work forever, hosted on storage like GitHub Pages or S3.

[←Serverless Maps - Now Open Source](https://protomaps.com/blog/serverless-maps-now-open-source/)[PMTiles version 3: Disk Layout and Compressed Directories](https://protomaps.com/blog/pmtiles-v3-layout-compression/)



# PMTiles version 3: Disk Layout and Compressed Directories

Aug 12, 2022

[PMTiles](https://github.com/protomaps/PMTiles) is a single-file archive format for pyramids of tiled map data. The [last post](https://protomaps.com/blog/pmtiles-v3-hilbert-tile-ids) described the new `Entry` struct to compact repetitive data in-memory; the next step is to **further shrink directories for storage on disk and transfer over the Internet.**

PMTiles is designed to substitute for APIs like this:

```
https://example.s3-like-storage.com/tileset/{z}/{x}/{y}.pbf
```

One storage pattern is to store each tile as its own object, relying on cloud storage’s filesystem-like paths:

```
                  ┌───┐                   
┌────────┐   ┌───▶│███│ /tileset/1/0/0.pbf
│        │───┘    └───┘                   
│        │        ┌───┐                   
│   S3   │───────▶│███│ /tileset/1/0/1.pbf
│        │        └───┘                   
│        │───┐    ┌───┐                   
└────────┘   └───▶│███│ /tileset/1/1/1.pbf
                  └───┘                         
```

But this approach doesn’t scale up to planet-sized datasets, since millions of unique tiles can take days to upload.

A PMTiles archive is a **single file** upload:

```
https://example.s3-like-storage.com/tileset.pmtiles
```

The information mapping a `Z,X,Y` coordinate to the address of the tile must be stored in the file itself via an embedded `Directory` sector. Making interactive maps fast and affordable means making this directory *as small as possible*.

```
┌────────┐             /tileset.pmtiles   
│        │         ┌─────────────────────┐
│        │         │1,0,0 ┌───┐┌───┐┌───┐│
│   S3   │───────▶ │1,0,1 │███││███││███││
│        │         │1,1,1 └───┘└───┘└───┘│
│        │         └─────────────────────┘
└────────┘                                
```

**PMTiles v2** punts on compression completely; it has a 1:1 relationship between the file layout and in-memory data structures. Waiting for half a megabyte of directory data for every map is slow, but the implementation remains dead simple and has been *good enough* to prove out the design across diverse environments like Cloudflare Workers.

The goal of the next specification version is not just to `gzip` directories and call it a day, but **hand-tune a custom compression codec specific to map datasets.** Projects like [Apache Parquet](https://parquet.apache.org/) combine multiple compression techniques for arbitrary non-tiled data; our approach will look more like the domain-specific compression for [PNG images](https://en.wikipedia.org/wiki/Portable_Network_Graphics#Compression), but tuned to map tiles instead of RGB pixels.

## Disk Layout

PMTiles v2 did not enforce any particular ordering for tile contents in the archive, so it’s easy to generate archives with multi-threaded programs like [Tippecanoe](https://github.com/protomaps/tippecanoe). **v3 adds an optional header field `clustered`**: a boolean indicating the disk layout of tile contents is ordered by Hilbert `TileID`, analogous to [FlatGeobuf’s indexed layout.](https://github.com/flatgeobuf/flatgeobuf) A clustered archive enables optimized clients to batch tile requests for lower latency, inspired by Markus Tremmel’s [COMTiles](https://github.com/mactrem/com-tiles) project.

```
clustered=false        clustered=true 
──────────────▶        ▼ ┌───┐ ┌───┐ ▲
─────▶ ───────▶        └─┘ ┌─┘ └─┐ └─┘
──▶ ──────────▶        ┌─┐ └─┐ ┌─┘ ┌─┐
──────────▶ ──▶        │ └───┘ └───┘ │
──────────────▶        └─┐ ┌─────┐ ┌─┘
───────▶ ─────▶        ┌─┘ └─┐ ┌─┘ └─┐
────▶ ────────▶        │ ┌─┐ │ │ ┌─┐ │
───────▶ ─────▶        └─┘ └─┘ └─┘ └─┘
```

## Test Dataset

Our starting example is a global vector basemap tileset. It addresses 357,913,941 individual tiles, or every tile on every zoom level between 0 and 14. (It includes both an `earth` and `ocean` layer, so there are no holes.) After Hilbert run-length encoding, 40,884,468 `Entry` records remain.

A direct serialization of these records to disk is 40884468 * 24 bytes or **981.2 MB**. Simple gzip compression reduces this to 305.4 MB, but we should be able to do better.

## Varint Encoding

A web-optimized tileset should have individual tiles under a megabyte in size, so 32 bits for `Length` is overkill. We replace the fixed-size records with a stream of unsigned Varints. We also chop off unnecessary high bits used in `TileId`, `RunLength` and `Offset`.

This step reduces the **981.2 MB directory to 526.4 MB, or 53.6% of the original size.**

```
 TileId      RL    Offset     Len
┌───────────┬─────┬──────────┬────┐         ┌─────┬───┬───┬────┐       
│    100    │  1  │    0     │2200│         │ 100 │ 1 │ 0 │2200│       
├───────────┼─────┼──────────┼────┤         ├─────┴┬──┴┬──┴───┬┴───┐   
│    101    │  1  │   2200   │2300│         │ 101  │ 1 │ 2200 │2300│   
├───────────┼─────┼──────────┼────┤ ──────▶ ├──────┼───┼──────┴─┬──┴─┐ 
│    103    │  1  │   4500   │2000│         │ 103  │ 1 │  4500  │2000│ 
├───────────┼─────┼──────────┼────┤         ├──────┴┬──┴┬───────┴┬───┴┐
│    104    │  1  │   6500   │1900│         │  104  │ 1 │  6500  │1900│
└───────────┴─────┴──────────┴────┘         └───────┴───┴────────┴────┘
```

## Delta Encoding of TileID + Offset

Because a directory is sorted by ascending TileID, we can store deltas between consecutive entries instead of large numbers.

In a `clustered` archive, the physical layout of tile data will mostly match `TileID` order. Where tile contents are contiguous, we can keep `Length` while replacing `Offset` with 0, since the `Length` implies the delta to the next `Offset`.

Since this delta encoding makes values small, the varint step above should be even more effective.

These two encodings reduce the **526.4 MB directory to 243.2 MB, or 24.8% of the original size.**

```
┌─────┬───┬───┬────┐                   ┌─────┬───┬───┬────┐
│ 100 │ 1 │ 0 │2200│                   │ 100 │ 1 │ 0 │2200│
├─────┴┬──┴┬──┴───┬┴───┐               ├───┬─┴─┬─┴─┬─┴──┬─┘
│ 101  │ 1 │ 2200 │2300│               │ 1 │ 1 │ 0 │2300│  
├──────┼───┼──────┴─┬──┴─┐     ──────▶ ├───┼───┼───┼────┤  
│ 103  │ 1 │  4500  │2000│             │ 2 │ 1 │ 0 │2000│  
├──────┴┬──┴┬───────┴┬───┴┐            ├───┼───┼───┼────┤  
│  104  │ 1 │  6500  │1900│            │ 1 │ 1 │ 0 │1900│  
└───────┴───┴────────┴────┘            └───┴───┴───┴────┘  
```

## Column transpose

Instead of storing each entry in order, we transpose the values to a columnar layout.

```
┌─────┬───┬───┬────┐           ┌─────┬───┬───┬───┐  
│ 100 │ 1 │ 0 │2200│           │ 100 │ 1 │ 2 │ 1 │  
├───┬─┴─┬─┴─┬─┴──┬─┘           ├───┬─┴─┬─┴─┬─┴─┬─┘  
│ 1 │ 1 │ 0 │2300│             │ 1 │ 1 │ 1 │ 1 │    
├───┼───┼───┼────┤     ──────▶ ├───┼───┼───┼───┤    
│ 2 │ 1 │ 0 │2000│             │ 0 │ 0 │ 0 │ 0 │    
├───┼───┼───┼────┤             ├───┴┬──┴─┬─┴──┬┴───┐
│ 1 │ 1 │ 0 │1900│             │2200│2300│2000│1900│
└───┴───┴───┴────┘             └────┴────┴────┴────┘
```

This step in isolation does not reduce the size of our directory. However, sparse geographic datasets will have repeated deltas of `1`, `RunLength=0` and `Offset` zeroed in the first step, which aids in the next compression step.

## General-purpose compression

Finally, a general purpose compression algorithm like `gzip` is applied to the transposed directory.

This step reduces our **243.2 MB directory size to 91.6 MB, 9.3% of the original size**. Without the column transpose above, the result is 102.0 MB.

Compressors like Brotli and Zstandard improve on `gzip` and are supported by the spec for when they’re widely available in browsers.

## Conclusions + Next Steps

Our real-world, planet-scale dataset can address over 350 million individual tiles in just 91.6 megabytes, **beating generic compression by a factor of 3.**

The finishing touches to header design and directory partitoning are [under discussion on GitHub](https://github.com/protomaps/PMTiles/issues) and will be presented at the [FOSS4G 2022 conference in Firenze, Italy](https://talks.osgeo.org/foss4g-2022/talk/WXJKDM/), along with a richer tool ecosystem for PMTiles.



**Links with more information on PMtiles**

https://protomaps.com/blog/new-pmtiles-io/

https://protomaps.com/blog/pmtiles-more-platforms/

https://github.com/protomaps/PMTiles



**Choosing between MBTiles and PMTiles** depends on whether your priority is offline use (MBTiles) or cloud-native web hosting (PMTiles).

**MBTiles (SQLite-based)**
The MBTiles format is a mature standard that packages tiles into a single SQLite database.

* **Strengths:**

* Offline Performance: Highly optimized for local filesystem access; it is the industry standard for mobile apps and offline GIS workflows.
* Dynamic Updates: Because it is a database, you can update or replace individual tiles incrementally without rewriting the entire file.
* Universal Tooling: Native support in almost all GIS software (QGIS, ArcGIS) and established tile servers like Martin.
**Weaknesses:**
* Requires a Server: Browsers cannot read SQLite directly from a remote URL. You must run a dedicated tile server (e.g., Node.js or Go) to query the database and serve tiles to users.
* Hosting Complexity: Managing a running server process increases operational overhead and infrastructure costs compared to static hosting.





**PMTiles (Cloud-Native)**
PMTiles is a newer, single-file archive format designed specifically for "serverless" web mapping.

##### Strengths

* Serverless Hosting: Uses HTTP Range Requests to fetch only the specific bytes needed for a tile. This allows you to host a 100GB map file on Amazon S3 or Cloudflare R2 for pennies per month without any running server.
* Deduplication: Internal logic automatically deduplicates identical tiles (like solid ocean or land), resulting in file sizes 10-15% smaller than MBTiles.
* Massive Scalability: Designed to handle hundreds of millions of tiles by using a recursive index structure that stays efficient even at a global scale.

##### Weaknesses

* Read-Only/Static: It is not a database; if you need to update one tile, you typically have to regenerate and re-upload the entire file.
* Emerging Tooling: While support is growing (Leaflet, MapLibre), it lacks the deep legacy integration of MBTiles. For example, QGIS support often requires a plugin rather than being native.

##### Comparison Summary

| Feature | MBTiles | PMTiles |
| --- | --- | --- |
|Primary Use Case| Offline mobile/desktop apps |Cloud-native web maps|
|Hosting| Requires a server (e.g., Martin) |Static storage (S3/R2)|
|Internal Engine| SQLite Database |Binary archive + Index|
|Deduplication| Manual (via views) |Automatic|
|Updates| Incremental (Easy) |Full overwrite (Standard)|

### Serving PMtiles

Yes, PMTiles can be served from any standard web server (like Nginx, Apache, or Caddy) as long as it supports HTTP Range Requests. 

Since PMTiles is designed to be "serverless," it does not require a specialized tile server. The web server simply treats the .pmtiles file as a static asset, and the client-side library (like pmtiles.js) fetches only the specific byte ranges it needs. 
Requirements for Your Web Server

To serve PMTiles successfully, your server must meet two criteria:

**Support for Range Requests:** Most modern web servers (Nginx, Apache, Caddy) have this enabled by default. This allows the browser to request just a small slice of your 100GB file rather than downloading the whole thing.

**CORS Configuration:** If your map is hosted on a different domain than your .pmtiles file, you must configure Cross-Origin Resource Sharing to allow GET and HEAD requests and expose the Content-Range header. 

Comparison: S3 vs. Simple Web Server

| Feature | S3 (Cloud Storage) | Simple Web Server (Nginx/Apache) |
| --- | --- | --- |
| Ease of Use | Very high (upload and go) | Requires managing a server or VPS |
| Scalability | Handles massive traffic automatically | Limited by your server's bandwidth/RAM |
| Cost | Extremely low for storage/low traffic | Fixed monthly cost for the server |
| Advanced Use | Limited to standard Range Requests | Can use Caddy plugins for direct tile decoding |
| Why use a server if S3 is "serverless"? |
| Avoid S3 Costs: At extremely high traffic levels, S3 "per-request" fees can add up. A high-bandwidth VPS with Nginx can sometimes be cheaper. |

Privacy: It is easier to set up custom authentication or IP whitelisting on your own Nginx/Apache server than on a public S3 bucket.
Embedded Solutions: Using the Caddy PMTiles plugin allows your web server to act as a tile server natively, serving standard /{z}/{x}/{y}.pbf URLs directly from the PMTiles file. 




#### Configuring CORS for PMTiles

To serve PMTiles from your own server, the configuration must allow the Range header (so the browser can request specific parts of the file) and expose the Content-Range header (so the browser knows how much data is left).
1. **Nginx Configuration**
Add this inside your location block or server block in your Nginx config file (usually /etc/nginx/sites-available/default).
```nginx
location ~* \.pmtiles$ {
    # Allow any origin, or replace * with your domain (e.g., https://example.com)
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, HEAD, OPTIONS' always;
    
    # Critical: Allow the Range header and expose Content-Range
    add_header 'Access-Control-Allow-Headers' 'Range, If-Match, If-Modified-Since, If-None-Match' always;
    add_header 'Access-Control-Expose-Headers' 'Content-Length, Content-Range, ETag' always;

    # Handle preflight OPTIONS requests
    if ($request_method = 'OPTIONS') {
        add_header 'Access-Control-Max-Age' 1728000;
        add_header 'Content-Type' 'text/plain; charset=utf-8';
        add_header 'Content-Length' 0;
        return 204;
    }
}
Use code with caution.
```

After editing, run sudo nginx -t and sudo systemctl reload nginx.
2. **Apache Configuration**
Ensure mod_headers is enabled (sudo a2enmod headers). Add this to your .htaccess file or your VirtualHost config.
```apache
<FilesMatch "\.pmtiles$">
    Header set Access-Control-Allow-Origin "*"
    Header set Access-Control-Allow-Methods "GET, HEAD, OPTIONS"
    Header set Access-Control-Allow-Headers "Range, If-Match, If-Modified-Since, If-None-Match"
    Header set Access-Control-Expose-Headers "Content-Length, Content-Range, ETag"
    
    # Ensure Apache handles Range requests (usually default)
    Header set Accept-Ranges bytes
</FilesMatch>
Use code with caution.
```

After editing, run sudo systemctl restart apache2.
3. **Caddy Configuration**
Caddy is the simplest to configure. Add this to your Caddyfile.
```caddy
example.com {
    root * /var/www/html
    file_server

    @pmtiles path *.pmtiles
    header @pmtiles {
        Access-Control-Allow-Origin "*"
        Access-Control-Allow-Methods "GET, HEAD, OPTIONS"
        Access-Control-Allow-Headers "Range"
        Access-Control-Expose-Headers "Content-Length, Content-Range, ETag"
    }
}
Use code with caution.
```
Run caddy reload to apply.
Pro-Tip: The "Direct" Caddy Plugin
If you want your server to act like a standard tile server (serving .../tiles/z/x/y.pbf URLs from a single PMTiles file), you can use the [Caddy PMTiles Handler](https://www.google.com/url?sa=i&source=web&rct=j&url=https://docs.protomaps.com/deploy/server&ved=2ahUKEwiGrPCW8dGSAxU7EFkFHaTVDPYQy_kOegYIAQgPEAE&opi=89978449&cd&psig=AOvVaw0prY6j9xYVu0fwsAgTBroZ&ust=1770914617538000). This is more efficient for legacy apps that don't support the pmtiles:// protocol.

To verify your setup, you need to confirm that the server acknowledges the Range request and provides the necessary CORS headers.
1. Verifying with curl
Run this command in your terminal. It simulates a browser asking for the first 100 bytes of your map file:
```bash
curl -I -H "Origin: http://localhost:3000" \
     -H "Range: bytes=0-100" \
     https://yourdomain.com
Use code with caution.
```

What to look for in the response:

*HTTP/1.1 206 Partial Content: This confirms your server supports Range Requests. 206 Partial Content (MDN)*
*Access-Control-Allow-Origin: Should match your domain or be *.*
*Access-Control-Expose-Headers: Must include Content-Range. CORS Headers (Protomaps)*

- **The Advanced Caddy Approach**
  While you can serve PMTiles as a static file, Caddy offers a specialized PMTiles Handler. This is the "gold standard" for self-hosting because it makes a single PMTiles file look like a standard Mapbox-style tile server to the rest of the world.
- **Why use the Caddy Handler?**
  Legacy Support: Some apps (like older QGIS versions or closed-source viewers) cannot use the pmtiles:// protocol. The handler translates requests for /tiles/0/0/0.pbf into the correct range request for you.
- URL Masking: It hides your massive .pmtiles filename and serves tiles from a clean URL like https://map.example.com/tiles/{z}/{x}/{y}.mvt.
- Automatic Z/X/Y Routing: It handles the logic of finding the right data inside the archive so your frontend code can be simpler.
- How to Set It Up
  You must use a version of Caddy built with the PMTiles adapter. You can download this via xcaddy or the Caddy download page.
- Sample Caddyfile:

```caddy
{
    order pmtiles before file_server
}

map.example.com {
    # This serves tiles from 'my_map.pmtiles' at the /tiles/ path
    pmtiles /tiles/* {
        path /var/www/maps/my_map.pmtiles
    }

    # Standard CORS headers for the tile endpoint
    header /tiles/* {
        Access-Control-Allow-Origin "*"
        Access-Control-Expose-Headers "Content-Range"
    }

    file_server
}
Use code with caution.
```

How the URLs look after setup:

- Standard Method: `pmtiles://https://example.com/my_map.pmtiles`

- Caddy Handler Method: `https://map.example.com/tiles/{z}/{x}/{y}.mvt`

#### a Custom Caddy Handler for PMTiles

Building a custom Caddy binary is the "pro" way to host maps. It transforms Caddy from a simple file server into a high-performance Tile Server that reads directly from your PMTiles archives.
1. How to Build the Custom Caddy Binary
The easiest way to build Caddy with plugins is using xcaddy, a tool designed specifically for this purpose.
<u>Prerequisites</u>
You need Go installed on your system (v1.21 or newer).
The Build Command
Run this in your terminal to compile a single executable file named caddy that includes the PMTiles handler:
```bash
go install ://github.com

xcaddy build \
    --with ://github.com
Use code with caution.
```

This creates a caddy binary in your current directory. Move it to /usr/bin/ or wherever you keep your executables.

**What does the Plugin actually do?**

Think of the plugin as a translator.

Normally, PMTiles requires the browser to do the work of finding where a tile lives inside the file (using the pmtiles.js library). The Caddy plugin shifts that work to the server.

- Traditional Static Serving: The browser asks for "Bytes 500-600" of map.pmtiles.
- Caddy Plugin Serving: The browser asks for /tiles/5/10/15.mvt. Caddy opens the PMTiles file, finds that specific tile, and sends it back as a standard MVT response.

The 3 Main Benefits:

1. Universal Compatibility: You can use the URL https://yourdomain.com{z}/{x}/{y}.mvt in any software (QGIS, ArcGIS, Mapbox GL JS, OpenLayers) without needing the pmtiles.js library.
2. Performance: Caddy caches the PMTiles internal index in RAM. This makes looking up tiles extremely fast compared to multiple round-trip range requests from a browser.
3. Security/Abstraction: You don't have to expose your massive .pmtiles file paths to the public. You can serve multiple different map files from a single clean URL structure.

Example Caddyfile Configuration
Once you have your custom binary, your Caddyfile looks like this to serve multiple map files:

```caddy
{
    # Required: tell Caddy where to place the pmtiles handler in the internal chain
    order pmtiles before file_server
}

maps.example.com {
    # 1. Serve a specific PMTiles file as a tile endpoint
    pmtiles /world-map/* {
        path /data/maps/planet.pmtiles
    }

    # 2. Serve a different one for city data
    pmtiles /city-data/* {
        path /data/maps/nyc.pmtiles
    }

    # Standard CORS headers for all tile paths
    header /world-map/* Access-Control-Allow-Origin "*"
    header /city-data/* Access-Control-Allow-Origin "*"

    # Optional: Serve your website's HTML/JS from the same server
    root * /var/www/html
    file_server
}
Use code with caution.
```
4. How to use it in your code
Now, instead of the complex pmtiles:// setup, your MapLibre source becomes a simple URL:
```javascript
const map = new maplibregl.Map({
  container: 'map',
  style: {
    version: 8,
    sources: {
      "my-source": {
        "type": "vector",
        "tiles": ["https://maps.example.com/world-map/{z}/{x}/{y}.mvt"],
        "minzoom": 0,
        "maxzoom": 14
      }
    },
    layers: [...]
  }
});
Use code with caution.
```

#### Deploying the map service with Caddy

To run your custom Caddy binary as a background service on Linux (Ubuntu, Debian, CentOS, etc.), you should use Systemd. This ensures the server starts automatically on boot and restarts if it crashes.
1. Place the Binary and Config
Move your custom binary to the standard location:
`sudo mv caddy /usr/bin/caddy`
Give it execution permissions:
`sudo chmod +x /usr/bin/caddy`
Create a directory for your configuration:
`sudo mkdir -p /etc/caddy`
Create your Caddyfile at /etc/caddy/Caddyfile using the Caddy PMTiles Handler configuration discussed previously.
2. Create the Systemd Unit File
Create a new file at /etc/systemd/system/caddy.service:
sudo nano /etc/systemd/system/caddy.service
Paste the following configuration:
```ini
[Unit]
Description=Caddy with PMTiles Plugin
Documentation=https://caddyserver.com
After=network.target network-online.target
Requires=network-online.target

[Service]
Type=notify
User=caddy
Group=caddy
ExecStart=/usr/bin/caddy run --environ --config /etc/caddy/Caddyfile
ExecReload=/usr/bin/caddy reload --config /etc/caddy/Caddyfile --force
TimeoutStopSec=5s
LimitNOFILE=1048576
LimitNPROC=512
PrivateTmp=true
ProtectSystem=full
AmbientCapabilities=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
Use code with caution.
```
3. Set Up Permissions
Caddy should not run as root for security reasons. Create a dedicated user and group:
```bash
# Create the caddy user
sudo groupadd --system caddy
sudo useradd --system \
    --gid caddy \
    --create-home \
    --home-dir /var/lib/caddy \
    --shell /usr/sbin/nologin \
    --comment "Caddy web server" \
    caddy

# Ensure caddy can read your map files
sudo chown -R caddy:caddy /etc/caddy
sudo chown -R caddy:caddy /var/lib/caddy
# Replace /path/to/maps with your actual PMTiles directory
sudo chown -R caddy:caddy /path/to/maps 
Use code with caution.
```

4. Enable and Start
Run these commands to load the service and start your map server:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now caddy
```

5. Management Commands
Check status: `sudo systemctl status caddy`
View logs: `journalctl -u caddy -f` (Crucial for debugging Caddyfile errors)
Reload after config changes: `sudo systemctl reload caddy`


#### Script to build the Caddy binary with PMTiles plugin

This script automates the process of installing Go, building a custom Caddy binary with the PMTiles plugin, setting up the service user, and configuring the Systemd unit.
Deployment Script (deploy-caddy-pmtiles.sh)

```bash
#!/bin/bash

# --- Configuration ---
CADDY_USER="caddy"
MAPS_DIR="/var/www/maps"
CONFIG_DIR="/etc/caddy"
BINARY_PATH="/usr/bin/caddy"

set -e # Exit on error

echo "--- 1. Installing Go and Dependencies ---"
sudo apt-get update
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl git
# Install Go (needed for xcaddy)
if ! command -v go &> /dev/null; then
    sudo apt-get install -y golang-go
fi

echo "--- 2. Building Custom Caddy with PMTiles Plugin ---"
go install ://github.com
~/go/bin/xcaddy build --with ://github.com
sudo mv ./caddy $BINARY_PATH
sudo chmod +x $BINARY_PATH

echo "--- 3. Setting up User and Directories ---"
if ! id -u $CADDY_USER > /dev/null 2>&1; then
    sudo groupadd --system $CADDY_USER
    sudo useradd --system --gid $CADDY_USER --create-home --home-dir /var/lib/caddy --shell /usr/sbin/nologin $CADDY_USER
fi

sudo mkdir -p $CONFIG_DIR
sudo mkdir -p $MAPS_DIR
sudo chown -R $CADDY_USER:$CADDY_USER $CONFIG_DIR
sudo chown -R $CADDY_USER:$CADDY_USER $MAPS_DIR

echo "--- 4. Creating Initial Caddyfile ---"



# Note: Update 'yourdomain.com' and the pmtiles filename below
sudo tee $CONFIG_DIR/Caddyfile > /dev/null <<EOF
{
    order pmtiles before file_server
}

yourdomain.com {
    pmtiles /tiles/* {
        path $MAPS_DIR/my_map.pmtiles
    }
    header /tiles/* Access-Control-Allow-Origin "*"
    file_server
}
EOF

echo "--- 5. Creating Systemd Service ---"
sudo tee /etc/systemd/system/caddy.service > /dev/null <<EOF
[Unit]
Description=Caddy with PMTiles
After=network.target network-online.target
Requires=network-online.target

[Service]
Type=notify
User=$CADDY_USER
Group=$CADDY_USER
ExecStart=$BINARY_PATH run --environ --config $CONFIG_DIR/Caddyfile
ExecReload=$BINARY_PATH reload --config $CONFIG_DIR/Caddyfile --force
TimeoutStopSec=5s
LimitNOFILE=1048576
AmbientCapabilities=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
EOF

echo "--- 6. Starting Service ---"
sudo systemctl daemon-reload
sudo systemctl enable caddy
# Note: This will fail until you place a .pmtiles file in $MAPS_DIR
echo "Setup complete! Place your .pmtiles file in $MAPS_DIR and run: sudo systemctl start caddy"
```

Use code with caution.

**How to use this script:**

1. Save the file: nano deploy-caddy-pmtiles.sh
2. Make it executable: chmod +x deploy-caddy-pmtiles.sh
3. Run it: ./deploy-caddy-pmtiles.sh
4. Finalize:
5. Open /etc/caddy/Caddyfile to update your domain name.
6. Move your .pmtiles file into /var/www/maps/.
7. Run sudo systemctl start caddy.
8. Quick Health Check
9. After starting, check if Caddy is successfully serving your map metadata by visiting:
10. https://yourdomain.com (or your server's IP).


#### Watching for Changes and Auto-Reloading Caddy
To automate the reloading of your PMTiles maps, we will use inotify-tools. This utility monitors the filesystem and triggers a Caddy reload whenever a file in your maps directory is added, moved, or deleted.
1. Install Dependencies
    You need the inotify-tools package:

  ```bash
  sudo apt-get update
  sudo apt-get install -y inotify-tools
  ```

  Use code with caution.

2. Create the Watcher Script
    Create a script at /usr/local/bin/pmtiles-watcher.sh:

  ```bash
  sudo nano /usr/local/bin/pmtiles-watcher.sh
  ```

  Use code with caution.

Paste the following logic (adjusting /var/www/maps if your path is different):
```bash
#!/bin/bash


# Directory to watch
WATCH_DIR="/var/www/maps"

echo "Watching $WATCH_DIR for changes..."

# Monitor for moved, created, or deleted .pmtiles files
inotifywait -m -e close_write -e moved_to -e delete --format '%f' "$WATCH_DIR" | while read FILE
do
    if [[ "$FILE" == *.pmtiles ]]; then
        echo "Change detected in $FILE. Reloading Caddy..."

        # Check config before reloading to prevent downtime
​        if caddy validate --config /etc/caddy/Caddyfile; then
​            systemctl reload caddy
​            echo "Caddy reloaded successfully."
​        else
​            echo "Caddyfile validation failed. Skipping reload."
​        fi
​    fi
done
```
Use code with caution.



Make it executable:
```bash
sudo chmod +x /usr/local/bin/pmtiles-watcher.sh
```

Use code with caution.

3. Create a Systemd Service for the Watcher
To ensure the watcher runs in the background at all times, create /etc/systemd/system/pmtiles-watcher.service:
```ini
[Unit]
Description=PMTiles Directory Watcher
After=caddy.service
Requires=caddy.service

[Service]
Type=simple
ExecStart=/usr/local/bin/pmtiles-watcher.sh
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
```
Use code with caution.

4. Enable and Start
Run these commands to activate your automated workflow:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pmtiles-watcher.service
```
Use code with caution.

**How it works**

1. Zero Downtime: By using systemctl reload caddy, your existing map users won't experience any interruption while the new .pmtiles file is being swapped in the Caddy PMTiles Handler.
2. Validation: The script runs caddy validate first. If your Caddyfile has a syntax error, it won't attempt to reload, keeping your current map online.
3. Persistence: If you restart the server, the watcher starts automatically after Caddy.
4. Monitoring the Logs
5. You can see the watcher in action by tailing the logs while you upload a new map:


`journalctl -u pmtiles-watcher.service -f`

#### A starter index.html file for testing your map server

This single-file index.html uses MapLibre GL JS to automatically render your map.
Since you are using the Caddy PMTiles Plugin, we don't need the pmtiles:// protocol in the frontend; we can point directly to the standard Z/X/Y tile URL provided by your server.
The Previewer (index.html)
Place this file in your Caddy root directory (e.g., /var/www/html/index.html).
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PMTiles Previewer</title>
    <!-- MapLibre GL JS -->
    <script src="https://unpkg.com"></script>
    <link href="https://unpkg.com" rel="stylesheet" />
    <style>
        body { margin: 0; padding: 0; font-family: sans-serif; }
        #map { position: absolute; top: 0; bottom: 0; width: 100%; }
        .overlay {
            position: absolute; top: 10px; left: 10px; z-index: 1;
            background: rgba(255, 255, 255, 0.9); padding: 15px;
            border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
    </style>
</head>
<body>

<div class="overlay">
    <h3 style="margin-top:0">Map Preview</h3>
    <p id="status">Loading tiles from Caddy...</p>
    <small>Zoom: <span id="zoom-level">0</span></small>
</div>

<div id="map"></div>

<script>
    // --- CONFIGURATION ---
    // This matches the path in your Caddyfile: pmtiles /tiles/*
    const TILE_URL = `${window.location.origin}/tiles/{z}/{x}/{y}.mvt`;

    const map = new maplibregl.Map({
        container: 'map',
        style: {
            version: 8,
            sources: {
                "dynamic-pmtiles": {
                    "type": "vector",
                    "tiles": [TILE_URL],
                    "minzoom": 0,
                    "maxzoom": 14
                }
            },
            layers: [
                {
                    "id": "background",
                    "type": "background",
                    "paint": { "background-color": "#f8f9fa" }
                },
                {
                    "id": "all-features",
                    "source": "dynamic-pmtiles",
                    "source-layer": "roads", // Update this to match your actual layer name
                    "type": "line",
                    "paint": {
                        "line-color": "#3388ff",
                        "line-width": 1.5
                    }
                }
            ]
        },
        center: [0, 0],
        zoom: 2
    });
    
    // Update UI on move
    map.on('move', () => {
        document.getElementById('zoom-level').innerText = map.getZoom().toFixed(2);
    });
    
    // Error handling
    map.on('error', (e) => {
        console.error("Map error:", e);
        document.getElementById('status').innerText = "Error loading tiles. Check CORS or layer names.";
        document.getElementById('status').style.color = "red";
    });
    
    map.on('load', () => {
        document.getElementById('status').innerText = "Tiles connected via Caddy Handler";
        document.getElementById('status').style.color = "green";
    });
</script>

</body>
</html>
Use code with caution.
```

**Important Steps to Finish**
* Check Layer Name: In the script above, "source-layer": "roads" must match a layer inside your .pmtiles file. If you see a blank map, use the PMTiles Viewer to confirm your internal layer names.
* Caddyfile Root: Ensure your Caddyfile has a root directive pointing to where you saved this index.html.
* Permissions: Ensure the caddy user has read access to the HTML file:
`sudo chown caddy:caddy /var/www/html/index.html`


**Why this works so well**
By combining the Caddy PMTiles Handler with MapLibre GL JS, you have built a production-grade, self-healing map server that:
* Updates instantly when you drop in a new file (via the Watcher).
* Works on any device (via the HTML index).
* Costs nearly nothing to run on a small VPS.

#### Example configuring a baselayer

To add a professional backdrop to your custom data, you have two options: using free community tiles (like OpenStreetMap) or commercial API keys (like Stadia or MapTiler).
The cleanest way to do this in MapLibre GL JS is to add the basemap as a separate source and layer at the very top of your layers array so your custom PMTiles sit on top of it.

1. Using OpenStreetMap (Raster Tiles)
This is the simplest way to get a map background for free without an API key.
```javascript
// Add this source to your style object
sources: {
    "osm-tiles": {
        "type": "raster",
        "tiles": ["https://tile.openstreetmap.org{z}/{x}/{y}.png"],
        "tileSize": 256,
        "attribution": "© OpenStreetMap contributors"
    },
    "dynamic-pmtiles": { ... } // Your existing PMTiles source
},
layers: [
    {
        "id": "osm-background",
        "type": "raster",
        "source": "osm-tiles",
        "minzoom": 0,
        "maxzoom": 19
    },
    { ... } // Your PMTiles layers go here
]
Use code with caution.
```

2. Using High-Quality Vector Basemaps (Recommended)
If you want a sleek "Dark Mode" or "Satellite" look, use a provider like Stadia Maps or MapTiler. These require a free API key.
Example with Stadia Maps Alidade Smooth:
```javascript
const STADIA_KEY = 'YOUR_API_KEY';
const TILE_URL = `${window.location.origin}/tiles/{z}/{x}/{y}.mvt`;

const map = new maplibregl.Map({
    container: 'map',
    style: {
        version: 8,
        sources: {
            "basemap": {
                "type": "vector",
                "url": `https://tiles.stadiamaps.com{STADIA_KEY}`
            },
            "dynamic-pmtiles": {
                "type": "vector",
                "tiles": [TILE_URL]
            }
        },
        // IMPORTANT: Use the basemap's layers + your custom layer
        layers: [
            // Usually, you fetch the full style from Stadia, but for a simple 
            // implementation, you can just overlay your data on their raster:
            {
                "id": "stadia-raster",
                "type": "raster",
                "source": {
                    "type": "raster",
                    "tiles": [`https://tiles.stadiamaps.com{z}/{x}/{y}.png?api_key=${STADIA_KEY}`]
                }
            },
            {
                "id": "my-data",
                "source": "dynamic-pmtiles",
                "source-layer": "your_layer",
                "type": "circle",
                "paint": { "circle-color": "#ff0000" }
            }
        ]
    }
});
Use code with caution.
```

3. Quick Pro-Tip: "Sandwich" Styling
If you use a Vector Basemap, you can perform a "Sandwich" technique where you place your data underneath the labels of the basemap but above the land and water.

* Find the id of the label layer in the basemap (e.g., place_label).
* Use map.addLayer(myLayer, 'place_label') in your code. This ensures your road lines don't cover up the names of cities.
* Summary of Popular Basemap Providers
  
|Provider|	Best For	|Link|
|---|---|---|
|OpenStreetMap|	Total freedom / No keys |	OSM Tile Info|
|Stadia Maps	|Elegant, clean designs	|Stadia Maps Dashboard|
|MapTiler|	High-perf Vector tiles	|MapTiler Cloud
|Thunderforest|	Outdoors / Topography|	Thunderforest|


####  Example: Adding a Layer Switcher for Basemaps
To create a Layer Switcher for MapLibre, the most robust method is to use a simple HTML control that updates the source and layers of your map.
Since MapLibre "styles" are immutable objects, the standard practice is to use the map.setStyle() method or toggle the visibility property. For switching between completely different basemaps (like Satellite vs. Streets), setStyle is best.

1. Updated HTML & UI
Add a selection box to your index.html overlay:
```html
<div class="overlay">
    <h3 style="margin-top:0">Map Preview</h3>
    <label for="style-select">Basemap:</label>
    <select id="style-select">
        <option value="streets">OpenStreetMap (Streets)</option>
        <option value="satellite">Esri World Imagery (Satellite)</option>
    </select>
    <p id="status">Loading...</p>
</div>
Use code with caution.
```
2. The JavaScript Logic
You need a function that re-defines the style while keeping your PMTiles data on top.
```javascript
const TILE_URL = `${window.location.origin}/tiles/{z}/{x}/{y}.mvt`;

// Define our two styles
const styles = {
    streets: {
        version: 8,
        sources: {
            "base": {
                "type": "raster",
                "tiles": ["https://tile.openstreetmap.org{z}/{x}/{y}.png"],
                "tileSize": 256,
                "attribution": "© OSM"
            }
        },
        layers: [{ "id": "base", "type": "raster", "source": "base" }]
    },
    satellite: {
        version: 8,
        sources: {
            "base": {
                "type": "raster",
                "tiles": ["https://server.arcgisonline.com{z}/{y}/{x}"],
                "tileSize": 256,
                "attribution": "© Esri"
            }
        },
        layers: [{ "id": "base", "type": "raster", "source": "base" }]
    }
};

// Function to inject your PMTiles into any selected style
function getFullStyle(styleKey) {
    const base = JSON.parse(JSON.stringify(styles[styleKey]));
    base.sources["my-data"] = {
        "type": "vector",
        "tiles": [TILE_URL]
    };
    base.layers.push({
        "id": "my-data-layer",
        "source": "my-data",
        "source-layer": "roads", // Update this!
        "type": "line",
        "paint": { 
            "line-color": styleKey === 'satellite' ? "#00ff00" : "#3388ff", // Green on Sat, Blue on Street
            "line-width": 2 
        }
    });
    return base;
}

// Initialize Map
const map = new maplibregl.Map({
    container: 'map',
    style: getFullStyle('streets'),
    center: [0, 0],
    zoom: 2
});

// Event Listener for the Toggle
document.getElementById('style-select').addEventListener('change', (e) => {
    map.setStyle(getFullStyle(e.target.value));
});
Use code with caution.
```

3. Professional Refinement: The Control Plugin
If you prefer a native look, use the MapLibre GL Terrain-RGB compatible plugin maplibre-gl-controls. It adds a standard "stack" icon in the corner.
* Install: `Add <script src="https://unpkg.com"></script>`
* Actionability: Use the MapLibre Official Style Switcher Example to see how to handle complex vector-to-vector transitions.

**Why this works:**
* Persistent Data: The getFullStyle function ensures that no matter which background you pick, your PMTiles layer is immediately re-added to the new style.
* Adaptive Styling: Notice the logic that changes the road color based on the background—this ensures high contrast regardless of whether the map is dark (satellite) or light (streets).


#### Example: Adding a Search Bar (Geocoding) to Your Map
To add a search bar (geocoding) to your map, the most reliable open-source option is the MapLibre GL Geocoder.
Since geocoding requires a massive database of addresses, you typically connect this plugin to a service like maptiler.com, stadiamaps.com, or the free nominatim.openstreetmap.org.
1. Add the Geocoder Dependencies
Include these in the <head> of your index.html:
```html
<!-- MapLibre Geocoder Control -->
<script src="https://unpkg.com"></script>
<link href="https://unpkg.com" rel="stylesheet" />
Use code with caution.
```

2. Implement the Search Logic
Add this script block after your map initialization. This example uses the Nominatim (OpenStreetMap) engine, which is free for low-volume testing.
```javascript
// 1. Define the Geocoder API configuration
const geocoderApi = {
    forwardGeocode: async (config) => {
        const features = [];
        try {
            const request = `https://nominatim.openstreetmap.org{config.query}&format=geojson&addressdetails=1&limit=5`;
            const response = await fetch(request);
            const geojson = await response.json();
            
            for (let feature of geojson.features) {
                let center = [
                    feature.geometry.coordinates[0],
                    feature.geometry.coordinates[1]
                ];
                let point = {
                    type: 'Feature',
                    geometry: feature.geometry,
                    place_name: feature.properties.display_name,
                    properties: feature.properties,
                    text: feature.properties.display_name,
                    place_type: ['place'],
                    center: center
                };
                features.push(point);
            }
        } catch (e) {
            console.error('Failed to forwardGeocode', e);
        }
        return { features };
    }
};

// 2. Add the Geocoder control to the map
const geocoder = new MaplibreGeocoder(geocoderApi, {
    maplibregl: maplibregl,
    placeholder: "Search for an address...",
    zoom: 12
});

map.addControl(geocoder, 'top-right');
Use code with caution.
```

3. Comparison of Geocoding Providers
For a "public website," Nominatim can be slow or blocked if traffic is high. Consider these professional alternatives:


Provider	Pros	Link
Photon	Open-source, fast, No API key needed	Photon by Komoot
MapTiler	Highly accurate, global, built-in plugin support	MapTiler Geocoding
Stadia Maps	Privacy-focused, excellent documentation	Stadia Maps Search


5. Why use a Geocoder with PMTiles?
While your PMTiles file provides the visual data (the roads and buildings), the Geocoder provides the index to find them. When a user selects a result, the geocoder tells MapLibre to flyTo specific coordinates, and your Caddy server instantly pulls the relevant PMTiles for that new location.

To limit geocoding, you essentially "fence" the search results so the user doesn't fly to Paris when your PMTiles only cover New York.
Depending on the provider, you can limit by a Bounding Box (BBOX) or a Country Code.
1. Limiting by Bounding Box (BBOX)
The bounding box is defined by two coordinates: [min_lon, min_lat, max_lon, max_lat]. You pass this into your geocoder request.
Example: Limiting to the United Kingdom
Update your geocoderApi fetch request in the index.html to include the viewbox and bounded parameters:
```javascript
// Define your map's data bounds [West, South, East, North]
const DATA_BOUNDS = "-10.85,49.82,1.76,60.84"; // UK Bounds

const geocoderApi = {
    forwardGeocode: async (config) => {
        // ... (existing code)
        const request = `https://nominatim.openstreetmap.org{config.query}` +
                        `&format=geojson&limit=5` +
                        `&viewbox=${DATA_BOUNDS}&bounded=1`; // Forces results inside bounds
        const response = await fetch(request);
        // ... (rest of the logic)
    }
};
Use code with caution.
```
2. Limiting by Country (Cleanest UI)
If your map covers an entire country, use the countrycodes parameter. This is often more reliable than a box for excluding nearby border results.
```javascript
// Only search within Germany (de) and France (fr)
const request = `https://nominatim.openstreetmap.org{config.query}` +
                `&format=geojson&countrycodes=de,fr`;
Use code with caution.
```
3. Automatic Mapbox-Style "Proximity"
If you don't want to strictly block outside results but want to prioritize the area the user is currently looking at, add a Proximity parameter using the map's current center.
```javascript
const center = map.getCenter();
const request = `https://nominatim.openstreetmap.org{config.query}` +
                `&format=geojson&lat=${center.lat}&lon=${center.lng}`;
Use code with caution.
```
Why this is a "Must-Have" for PMTiles
Since your PMTiles are likely clipped to a specific region (to save space), letting a user search for "Tokyo" when you only host "London" results in them seeing a blank gray screen. Using the Nominatim Search Documentation ensures the search bar and the map data stay in sync.

#### Example, click to identify features in PMTiles

To turn your static PMTiles into an interactive experience, you use the map.on('click') event in MapLibre GL JS. This allows you to "query" the vector data at the exact pixel where the user clicked and pull out the attributes (like name, address, or height) stored inside your tiles.
1. The Interactivity Script
Add this to your index.html after your map initialization. This script listens for clicks, finds the feature in your PMTiles source, and creates a MapLibre Popup.
```javascript
// 1. Create a popup instance (but don't add it yet)
const popup = new maplibregl.Popup({
    closeButton: true,
    closeOnClick: true
});

// 2. Listen for clicks on your specific PMTiles layer
map.on('click', 'my-data-layer', (e) => {
    // Change the cursor to indicate clickability
    map.getCanvas().style.cursor = 'pointer';

    const feature = e.features[0];
    const coordinates = e.lngLat;
    
    // 3. Extract properties (Update 'name' and 'class' to match your data)
    const name = feature.properties.name || "Unnamed Feature";
    const type = feature.properties.class || "Unknown Type";
    
    // 4. Build the HTML content for the popup
    const html = `
        <div style="padding:10px;">
            <strong style="font-size:14px;">${name}</strong><br/>
            <span style="color:#666;">Category: ${type}</span><hr/>
            <small>Lat: ${coordinates.lat.toFixed(4)}, Lon: ${coordinates.lng.toFixed(4)}</small>
        </div>
    `;
    
    // 5. Display the popup
    popup.setLngLat(coordinates)
        .setHTML(html)
        .addTo(map);
});

// 6. Change cursor when hovering over features
map.on('mouseenter', 'my-data-layer', () => {
    map.getCanvas().style.cursor = 'pointer';
});

map.on('mouseleave', 'my-data-layer', () => {
    map.getCanvas().style.cursor = '';
});
Use code with caution.
```
2. How to know your Property Names?
If your popup says "undefined," it's because you haven't used the correct key from your PMTiles attribute table.
The Fix: Use the PMTiles Viewer to click a feature and look at the Properties list. Common keys are name, addr:street, osm_id, or brand.
The Logic: You can access any property using feature.properties['your_key_here'].
3. Advanced: Highlighting the Selected Feature
To make it look professional, you can add a "selection" layer that highlights the building or road the user just clicked.
```javascript
// Add an empty highlight layer to your style
map.on('load', () => {
    map.addLayer({
        "id": "highlight-layer",
        "source": "dynamic-pmtiles",
        "source-layer": "roads",
        "type": "line",
        "paint": { "line-color": "yellow", "line-width": 4 },
        "filter": ["==", ["get", "osm_id"], ""] // Start with an empty filter
    });
});

// Update the filter on click
map.on('click', 'my-data-layer', (e) => {
    const id = e.features[0].properties.osm_id;
    map.setFilter('highlight-layer', ["==", ["get", "osm_id"], id]);
});
Use code with caution.
```
Why this is powerful for Public Maps
Since you are using the Caddy PMTiles Handler, these property lookups happen entirely in the browser using the vector data already downloaded to the user's cache. There is zero lag and zero extra server cost for these identify queries.


#### Example:  adding a legend to your map

To add a Legend to your MapLibre map, you create a custom HTML overlay that stays synced with the colors and filters you defined in your Style JSON.
Since there is no "automatic" legend in MapLibre, you build one using a simple div and CSS.
1. Add the Legend HTML & CSS
Add this structure to your index.html. This creates a floating box in the bottom-right corner.
```html
<style>
    .legend {
        background-color: #fff;
        border-radius: 3px;
        bottom: 30px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        font: 12px/20px 'Helvetica Neue', Arial, Helvetica, sans-serif;
        padding: 10px;
        position: absolute;
        right: 10px;
        z-index: 1;
    }
    .legend h4 { margin: 0 0 10px; }
    .legend div span {
        border-radius: 50%;
        display: inline-block;
        height: 10px;
        margin-right: 5px;
        width: 10px;
    }
</style>

<div id="state-legend" class="legend">
    <h4>Road Types</h4>
    <div><span style="background-color: #ff9900"></span>Major Roads</div>
    <div><span style="background-color: #3388ff"></span>Minor Roads</div>
    <div><span style="background-color: #aaaaaa"></span>Service Paths</div>
</div>
Use code with caution.
```

2. Make it Dynamic (Optional)
If your PMTiles data changes based on zoom level (e.g., layers appearing or disappearing), you can use the map.on('zoom') event to hide or show parts of the legend.
```javascript
map.on('zoom', () => {
    const legend = document.getElementById('state-legend');
    if (map.getZoom() > 12) {
        legend.style.display = 'block';
    } else {
        // You could hide minor road indicators at low zoom
    }
});
Use code with caution.
```
3. Professional Alternative: MapLibre Legend Control
If you want a more "GIS-like" legend that handles complex icons and toggles, use the maplibre-gl-legend plugin. It automatically reads your MapLibre Style Spec and generates the UI for you.
Actionability: Follow the MapLibre Legend Control Documentation to install it via NPM or CDN.
Why this works with PMTiles:
Because your Caddy PMTiles Handler is serving standard vector tiles, the legend only needs to know the Layer ID and Attribute Colors you set in your frontend code. It doesn't need to query the server at all.




### Styling and Rendering on the Web

Styling and rendering for both MBTiles and PMTiles generally rely on the same industry standard: the MapLibre/Mapbox GL Style Specification. Because both formats typically store data as Mapbox Vector Tiles (MVT), the visual configuration—colors, line weights, and zoom-level behavior—remains identical.
The only functional difference lies in how the Style JSON "points" to the data.

1. The Common Styling Engine
Whether you use MBTiles or PMTiles, you will use a Style JSON file. This file acts as the "CSS for maps," defining:
Sources: Where the raw data comes from.
Layers: Which data layers (e.g., roads, buildings) to draw and how to color them.
Zoom Rules: At what zoom level features appear or change size.

2. Styling Differences in Practice
   
|Feature |MBTiles (Server-Dependent)| PMTiles (Serverless/Cloud-Native) |
|---|---|---|
| Source URL | Points to a tile server URL (e.g., <https://api.com{z}/{x}/{y}.pbf>). | Points directly to a hosted file using a custom protocol (e.g., pmtiles://<https://s3.com>). |
| Backend Rendering | A server (like Martin or TileServer-GL) reads the SQLite database and "serves" tiles to the client. | The browser library (via PMTiles.js) reads specific byte ranges of the file directly from cloud storage. |
| Schema Dependency | Styles must match the internal table names of the SQLite file (e.g., OpenMapTiles schema). | Styles must match the layer names defined when the PMTiles file was created (e.g., via Tippecanoe). |

3. Rendering Logic
* Vector Rendering: In both cases, the browser (client-side) does the heavy lifting. It takes the vector coordinates from the tiles and draws them using the GPU (WebGL/WebGPU) based on your Style JSON.
* Raster Rendering: If your MBTiles or PMTiles contain pre-rendered images (PNG/JPG), the browser simply displays them as static images without needing a Style JSON for drawing.
* Pro-Tip: Style Compatibility
You cannot always swap a PMTiles file for an MBTiles file and keep the same style. The Layer Names must match exactly. For example, a style looking for a layer named transportation will fail if your PMTiles file named that same data roads. Always ensure your styling references the correct layer names as defined in your tile generation process.

#### Building a Style JSON for PMTiles

To get started, you need a Style JSON file that defines both where the data is (the Source) and how it looks (the Layer).
Below is a minimal, valid style structure designed for MapLibre GL JS using a PMTiles source.
The Basic Style Structure

```json
{
  "version": 8,
  "name": "My PMTiles Style",
  "metadata": {
    "maputnik:renderer": "mlgljs"
  },
  "sources": {
    "my_data_source": {
      "type": "vector",
      "url": "pmtiles://https://your-bucket.s3.amazonaws.com",
      "attribution": "© My Data Provider"
    }
  },
  "layers": [
    {
      "id": "background-layer",
      "type": "background",
      "paint": {
        "background-color": "#f0f0f0"
      }
    },
    {
      "id": "my-vector-layer",
      "type": "fill",
      "source": "my_data_source",
      "source-layer": "roads", 
      "paint": {
        "fill-color": "#3388ff",
        "fill-opacity": 0.6,
        "fill-outline-color": "#ffffff"
      }
    }
  ]
}
Use code with caution.
```

##### Critical Components Explained

1. sources
This is where you register your PMTiles file.
type: Must be "vector" (or "raster" if your PMTiles contains images).
url: The pmtiles:// prefix is mandatory so the library knows to use the PMTiles protocol instead of a standard tile server.
2. source-layer (The most important part)
A single PMTiles file can contain multiple layers (e.g., roads, water, buildings).
The Problem: If your source-layer name doesn't match exactly what is inside the file, the layer will be invisible.
The Fix: Use the PMTiles CLI (pmtiles show my-map.pmtiles) or the PMTiles Viewer to inspect your file and find the correct internal layer names.
3. layers
This is an array where the order matters. The first layer is drawn on the bottom, and subsequent layers are stacked on top.
id: A unique name for this style layer.
type: Can be fill, line, circle, symbol (for text/icons), or heatmap.
paint: This is where the visual magic happens (colors, widths, opacities).
Quick Tips for Styling
Zoom Levels: Use "minzoom": 0 and "maxzoom": 22 in your layer to control when data appears.
Interpolation: You can make lines get thicker as you zoom in:

```json
"line-width": {
  "stops": [[10, 1], [15, 5]]
}
Use code with caution.
```
Filtering: You can show only specific features from a layer:
```json
"filter": ["==", "class", "highway"]
Use code with caution.
```

#### Style Editors and Tools

To edit MapLibre/Mapbox GL Style JSON files visually without writing raw code, the following tools are the industry standards. They allow you to upload your PMTiles or MBTiles source and tweak colors, fonts, and layers in real-time.

1. Maputnik (Top Recommendation)
Maputnik is the most popular open-source visual editor for the MapLibre/Mapbox style specification. It is entirely browser-based and does not require an account.
Best For: Clean, open-source workflows and editing local style files.
How to use with PMTiles: You can add your PMTiles file as a source by using the pmtiles:// protocol in the "Sources" tab.
Key Feature: The Maputnik CLI allows you to run it locally and "watch" your style file, so every save in the editor updates your local file instantly.
2. MapLibre Style Editor
This is a newer, streamlined editor maintained by the MapLibre community. It is designed to be highly compatible with the latest MapLibre GL JS features.
Best For: Developers who want a modern, fast interface specifically built for the MapLibre ecosystem.
Key Feature: Excellent support for modern MapLibre extensions that might not be supported in older editors.
3. Felt
Felt is a modern web-mapping platform that excels at data upload and rapid styling. While it is a full platform rather than a standalone JSON editor, it is the home of Tippecanoe (the tool used to make PMTiles).
Best For: Users who want the "easiest" possible UI for styling complex datasets.
Caveat: It is more of a "walled garden" than Maputnik, but it is excellent for quickly visualizing how your data looks.
4. Mapbox Studio
The "gold standard" for UI/UX in map design. It is incredibly powerful but proprietary.
Best For: High-end cartography and complex label placement.
Caveat: It is designed to work within the Mapbox ecosystem. While you can export the Style JSON to use with MapLibre, some "Mapbox-only" features (like 3D Globe or certain proprietary fonts) will break when used elsewhere.
Summary Workflow
Open Maputnik.
Go to Sources and add your PMTiles URL (e.g., pmtiles://<https://my-bucket.s3.com>).
Visually adjust your layers.
Click Export to download the style.json file to include in your website code.

For a public website, PMTiles is the superior choice due to its "cloud-native" architecture, which significantly reduces both hosting costs and maintenance effort.

#### Working with Internal Layer Names

To find the internal layer names (the source-layer property) inside your PMTiles or MBTiles file, you can use these three methods ranging from "instant" to "command line."
1. The Instant Way: PMTiles Viewer (Web)
The easiest way is to use the official PMTiles Viewer by Protomaps.
Step 1: Drag and drop your .pmtiles file into the browser (or paste your hosted URL).
Step 2: Click the "Metadata" tab or look at the "Layers" list in the sidebar.
Step 3: You will see a list of IDs. Those are your source-layer names (e.g., water, roads, pois).
2. The Command Line Way: PMTiles CLI
If you prefer working in the terminal, you can use the PMTiles CLI tool.
Command:
```bash
pmtiles show your-file.pmtiles
Use code with caution.
```
Output: Look for the vector_layers section in the JSON output. Each id listed there is a valid source-layer.
```json
"vector_layers": [
  { "id": "buildings", "fields": {...} },
  { "id": "landuse", "fields": {...} }
]
Use code with caution.
```
3. The Developer Way: MapLibre Inspect
If you already have your map running in MapLibre GL JS, you can use the Inspect plugin or a simple console command to see what's under your cursor.
Code Snippet: Add this to your map click event to log layer names to the browser console:
```javascript
map.on('click', (e) => {
    const features = map.queryRenderedFeatures(e.point);
    console.log("Internal Layer Names:", features.map(f => f.layer['source-layer']));
});
Use code with caution.
```
4. For MBTiles: SQLite
Since MBTiles is just an SQLite database, you can query it directly using any SQLite browser.
Query:
```sql
SELECT value FROM metadata WHERE name='json';
Use code with caution.
```
This will return a JSON string containing the vector_layers array, identical to the PMTiles output.

#### Filtering and Styling by Layer

To filter for "Major Roads", your Style JSON needs a filter property within the layer. This filter acts on the attributes (properties) stored inside your vector tiles.
1. Identify Your Attribute Name
First, you must know which attribute identifies road types. Most open-source datasets (like OpenMapTiles or Overture Maps) use a property typically named class, type, or highway.
2. Style JSON Filter Example
In this example, we filter a layer to only show features where the class is either motorway or trunk.

```json
{
  "id": "major-roads-layer",
  "type": "line",
  "source": "my_data_source",
  "source-layer": "transportation", // Change this to your actual layer name
  "filter": [
    "match",
    ["get", "class"],
    ["motorway", "trunk", "primary"],
    true,
    false
  ],
  "paint": {
    "line-color": "#ff9900",
    "line-width": 2
  }
}
Use code with caution.
```

3. Common Filter Syntax Options
The MapLibre/Mapbox GL spec uses Expressions for filtering. Here are the three most common ways to write them:
The "Match" Filter (Best for Lists):
Matches a property against a specific list of values.
["match", ["get", "class"], ["motorway", "primary"], true, false]
The "Equality" Filter (Simple):
Shows only one specific type.
["==", ["get", "class"], "motorway"]
The "In" Filter (Membership):
Checks if a value exists in an array.
["in", ["get", "class"], ["literal", ["motorway", "trunk"]]]
4. How to Find Your Attribute Values
If you aren't sure if your roads are called "motorway" or "highway_major," use the PMTiles Viewer:
Open your file in the viewer.
Click on a road on the map.
Look at the "Properties" or "Attributes" popup. It will show you exactly what strings (like class: "primary") are available to filter.
Pro-Tip: Multi-Level Styling
You can create two separate layers in your Style JSON that point to the same source-layer:
Layer A: Filter for motorway (Style them thick and orange).
Layer B: Filter for service roads (Style them thin and grey).


#### Zoom-Level Styling

To keep your map clean, you use Zoom Expressions. This prevents "visual noise" by hiding minor roads at high altitudes and gradually making major roads thicker as you zoom in.
In the MapLibre Style Spec, this is done using interpolate or step.

1. The "Disappearing" Act (Opacity/Visibility)
This example hides minor roads completely until you reach zoom level 12, then fades them in.

```json
{
  "id": "minor-roads",
  "type": "line",
  "source": "my_source",
  "source-layer": "transportation",
  "filter": ["==", ["get", "class"], "service"], 
  "paint": {
    "line-color": "#aaaaaa",
    "line-opacity": [
      "interpolate", ["linear"], ["zoom"],
      11, 0,  // At zoom 11 or lower, opacity is 0% (hidden)
      13, 1   // By zoom 13, opacity is 100%
    ]
  }
}
Use code with caution.
```

2. The "Dynamic Width" (Scaling)
Major roads should look like thin threads from space but wide boulevards when zoomed in. This uses interpolate to create a smooth transition.
```json
{
  "id": "major-roads-dynamic",
  "type": "line",
  "source": "my_source",
  "source-layer": "transportation",
  "paint": {
    "line-color": "#ff9900",
    "line-width": [
      "interpolate", ["exponential", 1.5], ["zoom"],
      5, 0.5,  // At zoom 5, 0.5px wide
      12, 2,   // At zoom 12, 2px wide
      18, 20   // At zoom 18, 20px wide (street level)
    ]
  }
}
Use code with caution.
```

3. Using step for Discrete Changes
If you want an "on/off" switch rather than a smooth fade (e.g., for labels), use step.
```json
{
    "id": "road-labels",
    "type": "symbol",
    "source": "my_source",
    "source-layer": "transportation_name",
    "layout": {
    "text-field": ["get", "name"],
    "text-size": [
      "step", ["zoom"],
      12, 0,  // Hide text until zoom 12
      13, 10, // Size 10 at zoom 13
      15, 14  // Size 14 at zoom 15+
    ]
    }
}
Use code with caution.
```

Implementation Tips
* Performance: Interpolate is GPU-accelerated and very smooth.
* Testing: Use the Maputnik Editor to slide the zoom bar back and forth while editing these values to see the immediate effect.
* Exponential Base: In the line-width example, ["exponential", 1.5] makes the width grow faster as you zoom in, which feels more natural than a purely linear growth.




#### Why PMTiles Wins for Web Apps

* **Zero-Maintenance Hosting:** You can host a single PMTiles file on Amazon S3, Cloudflare R2, or GitHub Pages as a static asset.
* **Serverless Operation:** Browsers use HTTP Range Requests to fetch only the specific bytes needed for the current view. You do not need to manage a running tile server (like GeoServer or Martin), which eliminates server security patching and uptime monitoring.
* **Massive Cost Savings:** Compared to a Mapbox subscription or a dedicated VPS for MBTiles, static storage typically costs pennies per GB/month.

Most major open-source web mapping libraries can use PMTiles by integrating the official pmtiles JavaScript library. This library provides the necessary "glue" to translate standard map requests into the HTTP Range Requests that PMTiles requires.

1. MapLibre GL JS (Recommended)
MapLibre is considered the premier choice for PMTiles because it supports vector tiles natively with high performance.
Integration: It uses the addProtocol feature to register a pmtiles:// handler.
Benefit: Provides smooth zooming and full support for complex Mapbox-style JSON styling.
2. Leaflet
Leaflet is ideal for lightweight applications or when you only need to overlay specific data layers.
Integration: Uses a dedicated PMTiles Leaflet plugin that treats the archive as a standard tile layer.
Benefit: Extremely simple to set up if you are already familiar with the Leaflet ecosystem.
3. OpenLayers
OpenLayers is the go-to for feature-rich GIS applications.
Integration: Supported via the ol-pmtiles library, which reached version 1.0 in 2024 and includes TypeScript support.
Benefit: Excellent for combining PMTiles with other advanced GIS formats and projections.
4. Specialized & Emerging Libraries
Azure Maps Web SDK: Recently added native support for the pmtiles:// protocol, allowing users to overlay massive datasets like Overture Maps directly within the Azure ecosystem.
Deck.gl: While it doesn't have a built-in PMTiles layer, third-party loaders (like deck.gl-pmtiles) allow it to render PMTiles for high-performance data visualizations.
MapLibre Native (iOS/Android): Now supports PMTiles as a data source for mobile applications, enabling "serverless" maps on mobile devices.
Which of these libraries are you currently using, or would you like a code snippet for a specific one?

### Implementation Guide

To use PMTiles on your website, follow these steps:

1. Prepare the File: Use ogr2ogr or Tippecanoe to convert your data into a .pmtiles file.
2. Upload to Storage: Upload the file to a provider that supports Range Requests and CORS (e.g., Supabase Storage or S3).
3. Client-Side Integration: Use a library like MapLibre GL JS or Leaflet with the pmtiles plugin to render the map.

Example MapLibre Setup:

```javascript
// Register the PMTiles protocol
let protocol = new pmtiles.Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

// Load your map
const map = new maplibregl.Map({
  container: 'map',
  style: {
    version: 8,
    sources: {
      "my-source": {
        type: "vector",
        url: "pmtiles://https://your-bucket.s3.amazonaws.com"
      }
    },
    layers: [...]
  }
});
Use code with caution.
```

To implement PMTiles in your public website, you will need the pmtiles JavaScript library alongside your chosen map client.

1. MapLibre GL JS (Vector Tiles)
This is the standard for high-performance vector maps. It requires registering a custom protocol to handle the pmtiles:// URL prefix.

```html
<!-- Load MapLibre and PMTiles -->
<script src="https://unpkg.com"></script>
<link href="https://unpkg.com" rel="stylesheet" />
<script src="https://unpkg.com"></script>

<div id="map" style="width: 100%; height: 500px;"></div>

<script>
    // 1. Register the PMTiles protocol
    const protocol = new pmtiles.Protocol();
    maplibregl.addProtocol("pmtiles", protocol.tile);

    const PMTILES_URL = "https://your-server.com";

    const map = new maplibregl.Map({
        container: 'map',
        zoom: 2,
        center: [0, 0],
        style: {
            version: 8,
            sources: {
                "my-source": {
                    type: "vector",
                    url: `pmtiles://${PMTILES_URL}`
                }
            },
            layers: [{
                "id": "my-layer",
                "source": "my-source",
                "source-layer": "your_layer_name", // Must match name inside PMTiles
                "type": "circle",
                "paint": { "circle-color": "red" }
            }]
        }
    });
</script>
Use code with caution.
```

1. Leaflet (Raster or Vector)
Leaflet treats PMTiles as a layer. Note that Leaflet is primarily a raster engine, so if you are using vector PMTiles, you often use this to display them as VectorGrid layers.

```html
<!-- Load Leaflet and PMTiles -->
<link rel="stylesheet" href="https://unpkg.com" />
<script src="https://unpkg.com"></script>
<script src="https://unpkg.com"></script>

<div id="leaf-map" style="width: 100%; height: 500px;"></div>

<script>
    const PMTILES_URL = "https://your-server.com";
    const map = L.map('leaf-map').setView([0, 0], 2);

    // 1. Add a base layer (Standard OpenStreetMap)
    L.tileLayer('https://tile.openstreetmap.org{z}/{x}/{y}.png').addTo(map);

    // 2. Add the PMTiles Layer
    // For Raster PMTiles, use pmtiles.leafletRasterLayer
    // For Vector, you typically use a vector provider
    const p = new pmtiles.PMTiles(PMTILES_URL);
    
    // Example for a Raster PMTiles file:
    pmtiles.leafletRasterLayer(p).addTo(map);
</script>
Use code with caution.
```

To serve a PMTiles file from a storage bucket to your public website, you must configure Cross-Origin Resource Sharing (CORS). This tells the storage provider that your website is allowed to request specific "ranges" of the map file.
Choose your provider below for the specific JSON configuration and steps.

1. Amazon S3
Go to the S3 Console, select your bucket, and click the Permissions tab.
Scroll to Cross-origin resource sharing (CORS) and click Edit.
Paste this configuration (replace <https://yourdomain.com> with your actual site URL, or use * for testing):
```json
[
    {
        "AllowedOrigins": ["https://yourdomain.com"],
        "AllowedMethods": ["GET", "HEAD"],
        "AllowedHeaders": ["Range"],
        "ExposeHeaders": ["Content-Range", "Content-Length", "ETag"],
        "MaxAgeSeconds": 3000
    }
]
Use code with caution.
```
2. Cloudflare R2
In the Cloudflare Dashboard, go to R2 > Overview and select your bucket.
Go to Settings > CORS Policy and click Add CORS policy.
Paste the following (Note: R2 uses slightly different keys than S3):
```json
[
    {
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["Range"],
    "ExposeHeaders": ["ETag", "Content-Range"],
    "MaxAgeSeconds": 3600
    }
]
Use code with caution.
```
3. Google Cloud Storage (GCS)
GCS requires the gcloud CLI. Create a cors-config.json file with the following:
```json
[
    {
    "origin": ["*"],
    "method": ["GET", "HEAD"],
    "responseHeader": ["Content-Type", "Range", "ETag"],
    "maxAgeSeconds": 3600
    }
]
Use code with caution.
```
Then run: gcloud storage buckets update gs://YOUR_BUCKET_NAME --cors-file=cors-config.json.
Critical Requirement: Range Headers
PMTiles requires the Range header to function. If you do not include Range in AllowedHeaders and Content-Range in ExposeHeaders, the map will fail to load.

#### Key Differences

* MapLibre GL JS: Better for interactivity, tilting 3D views, and styling specific data features on the fly.
* Leaflet: Easier to set up for simple "pin on a map" apps or when using traditional raster tile backgrounds.

#### When to Stick with MBTiles

* **Legacy Systems:** If you are using older software that cannot be updated to support the PMTiles protocol.
* **Dynamic Data:** If your map data changes every few minutes and you need to update individual tiles inside the database without re-uploading a massive single file.


1. **GIS & Open Standard Alternatives**
For projects requiring high interoperability with traditional GIS software:

* **GeoPackage (.gpkg)**: An OGC standard format based on SQLite. It can store both vector tiles and raw vector data (like Shapefiles), making it more versatile than MVT for cross-platform GIS work.
* **MapLibre Tiles (MLT)**: A specialized encoding used by the MapLibre GL JS ecosystem, designed as a highly optimized, open-source alternative to proprietary formats.
* **Esri Vector Tiles (.pbf)**: While also using the .pbf extension, Esri’s implementation uses its own style specifications and internal structure tailored for the ArcGIS environment.

#### Platforms and Libraries

You can also use entirely different mapping platforms and open-source libraries that provide their own systems for generating, serving, and rendering vector tiles:

* **MapLibre GL JS/Native**: A community-driven, open-source fork of Mapbox GL JS and its native mobile SDKs. It uses the same MVT format and style specification, offering a free and open alternative for rendering GPU-accelerated vector maps on web, iOS, and Android.
* **OpenMapTiles**: A project that provides tools and scripts to generate vector tiles from OpenStreetMap data, which can then be self-hosted and styled.
* **MapTiler**: A commercial provider that offers map tiles, hosting services, and styling tools built on open-source data. It supports both vector and raster tiles and offers a simple pricing structure without vendor lock-in.
* **OpenLayers and Leaflet**: These are popular open-source JavaScript libraries for displaying maps. While Leaflet is more focused on raster tiles, OpenLayers has robust support for rendering vector tiles, allowing for dynamic styling and advanced GIS features.
* **Commercial Alternatives**: Other comprehensive mapping platforms, such as Google Maps Platform (which offers vector maps), ArcGIS Online, HERE Technologies, and Azure Maps, provide robust enterprise-level location services that include their own vector mapping technologies and APIs.



