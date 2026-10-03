// Regenerate MapSplat's built-in Protomaps basemap styles (basemap_styles/*.json).
//
// Uses the official @protomaps/basemaps package (BSD-3-Clause) to build a complete MapLibre
// style for each named flavor. Run from the repository root:
//
//   npm install --no-save @protomaps/basemaps@5.7.2
//   node scripts/gen_basemap_styles.mjs
//
// The vector source URL is a placeholder: MapSplat's exporter rewrites it at export time to the
// basemap the user chose (streamed build URL, or the clipped local data/basemap.pmtiles).
// Glyphs (fonts) and sprites (icons) load from Protomaps' public assets site.

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const basemaps = require("@protomaps/basemaps");
const pkgDir = path.dirname(require.resolve("@protomaps/basemaps/package.json"));
const pkg = JSON.parse(readFileSync(path.join(pkgDir, "package.json"), "utf8"));

const OUT = "basemap_styles";
const FLAVORS = ["light", "dark", "white", "grayscale", "black"];
mkdirSync(OUT, { recursive: true });

for (const flavor of FLAVORS) {
  const style = {
    version: 8,
    name: `Protomaps ${flavor}`,
    metadata: {
      "mapsplat:generated-by": "scripts/gen_basemap_styles.mjs",
      "mapsplat:source-package": `@protomaps/basemaps@${pkg.version}`,
      "mapsplat:flavor": flavor,
    },
    glyphs: "https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf",
    sprite: `https://protomaps.github.io/basemaps-assets/sprites/v4/${flavor}`,
    sources: {
      protomaps: {
        type: "vector",
        // Placeholder; replaced by the exporter with the chosen basemap source.
        url: "pmtiles://basemap.pmtiles",
        attribution:
          '<a href="https://protomaps.com">Protomaps</a> © <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>',
      },
    },
    layers: basemaps.layers("protomaps", basemaps.namedFlavor(flavor), { lang: "en" }),
  };
  const file = path.join(OUT, `protomaps-${flavor}.json`);
  writeFileSync(file, JSON.stringify(style) + "\n");  // compact: ~60 KB per flavor
  console.log(`${file}: ${style.layers.length} layers`);
}

// BSD-3-Clause requires the licence to travel with redistributed material. The npm package does
// not include it, so fetch the repository's LICENSE.md (BSD-3 code, CC0 design, MIT icons/schema).
const res = await fetch("https://raw.githubusercontent.com/protomaps/basemaps/main/LICENSE.md");
if (!res.ok) throw new Error(`licence download failed: HTTP ${res.status}`);
writeFileSync(path.join(OUT, "LICENSE-protomaps-basemaps.md"), await res.text());
console.log(`licence written for @protomaps/basemaps@${pkg.version}`);
