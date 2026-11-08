# wireframe-portal-title: licence notice

Status: NOTICE-FOUND (open-source notice present in the item files; see `docs/designs/hyperframes-catalog-licences.md`).
Source: HyperFrames registry item `wireframe-portal-title`, fetched with `hyperframes@0.8.223 add wireframe-portal-title --json --no-clipboard` on 2026-11-07.

Licence and notice files shipped with this item (sha256):
- `compositions/wireframe-portal-title/assets/fonts/Geist-OFL.txt` (930853ee1daa6855)
- `compositions/wireframe-portal-title/vendor/LICENSE-clipper-lib.txt` (c0065d41b422aa17)
- `compositions/wireframe-portal-title/vendor/LICENSE-gsap.txt` (16583f0aeeb2d9d8)
- `compositions/wireframe-portal-title/vendor/three/LICENSE` (bfe119ea4fd413f5)

Vendored (loaded at render time, previously fetched from a CDN):
- `compositions/wireframe-portal-title/vendor/LICENSE-clipper-lib.txt`
- `compositions/wireframe-portal-title/vendor/LICENSE-gsap.txt`
- `compositions/wireframe-portal-title/vendor/clipper.js`
- `compositions/wireframe-portal-title/vendor/gsap.min.js`

Vendored packages: gsap 3.14.2 (npm gsap@3.14.2; licence is GSAP's "Standard no charge" licence, not OSI, flagged for review; see `vendor/LICENSE-gsap.txt`); clipper-lib 6.4.2 (Boost Software License 1.0, see `vendor/LICENSE-clipper-lib.txt`); three.js 0.181.2 (MIT, see `vendor/three/LICENSE`).

## Libraries installed at build time

The vendored copies of the following files were removed from this folder. The image installs them at build time from npm (or the fontsource package), pinned in `docker/media-generator/Dockerfile` and listed in `docker/media-generator/catalogue/LIBS.json`:

- `clipper-lib@6.4.2` (BSL-1.0 (see LICENSE-clipper-lib.txt))
- `gsap@3.14.2` (GSAP standard no-charge licence (see LICENSE-gsap.txt in each item))
- `three@0.181.2` (MIT)

