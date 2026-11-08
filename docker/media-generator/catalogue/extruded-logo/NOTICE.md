# extruded-logo: licence notice

Status: NOTICE-FOUND (open-source notice present in the item files; see `docs/designs/hyperframes-catalog-licences.md`).
Source: HyperFrames registry item `extruded-logo`, fetched with `hyperframes@0.8.223 add extruded-logo --json --no-clipboard` on 2026-11-07.

Licence and notice files shipped with this item (sha256):
- `compositions/assets/fonts/Geist-OFL.txt` (930853ee1daa6855)
- `compositions/vendor/LICENSE-gsap.txt` (16583f0aeeb2d9d8)
- `compositions/vendor/three/LICENSE` (8b378ebe60e2fe50)

Vendored (loaded at render time, previously fetched from a CDN):
- `compositions/vendor/LICENSE-gsap.txt`
- `compositions/vendor/gsap.min.js`
- `compositions/vendor/inter-latin-500-normal.woff2`

Vendored packages: gsap 3.14.2 (npm gsap@3.14.2; licence is GSAP's "Standard no charge" licence, not OSI, flagged for review; see `vendor/LICENSE-gsap.txt`); three.js 0.184.0 (MIT, see `vendor/three/LICENSE`); Inter (SIL OFL 1.1, fontsource; upstream URL unpinned, sha256 in MANIFEST.json).

## Libraries installed at build time

The vendored copies of the following files were removed from this folder. The image installs them at build time from npm (or the fontsource package), pinned in `docker/media-generator/Dockerfile` and listed in `docker/media-generator/catalogue/LIBS.json`:

- `gsap@3.14.2` (GSAP standard no-charge licence (see LICENSE-gsap.txt in each item))
- `@fontsource/inter@5.3.0` (OFL-1.1 (see inter-LICENSE.txt in each item))
- `three@0.184.0` (MIT)

