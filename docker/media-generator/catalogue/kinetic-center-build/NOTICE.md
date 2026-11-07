# kinetic-center-build: licence notice

Status: NOTICE-FOUND (open-source notice present in the item files; see `docs/designs/hyperframes-catalog-licences.md`).
Source: HyperFrames registry item `kinetic-center-build`, fetched with `hyperframes@0.8.223 add kinetic-center-build --json --no-clipboard` on 2026-11-07.

Licence and notice files shipped with this item (sha256):
- `compositions/components/vendor/LICENSE-gsap.txt` (16583f0aeeb2d9d8)

Vendored (loaded at render time, previously fetched from a CDN):
- `compositions/components/vendor/CustomEase.min.js`
- `compositions/components/vendor/LICENSE-gsap.txt`
- `compositions/components/vendor/geist-1.woff2`
- `compositions/components/vendor/geist-2.woff2`
- `compositions/components/vendor/geist-3.woff2`
- `compositions/components/vendor/geist-4.woff2`
- `compositions/components/vendor/geist-5.woff2`
- `compositions/components/vendor/geist.css`
- `compositions/components/vendor/gsap.min.js`

Vendored packages: gsap 3.14.2 (npm gsap@3.14.2; licence is GSAP's "Standard no charge" licence, not OSI, flagged for review; see `vendor/LICENSE-gsap.txt`); Geist (SIL OFL 1.1, Google Fonts CSS and woff2 files, sha256 in MANIFEST.json).

## Libraries installed at build time

The vendored copies of the following files were removed from this folder. The image installs them at build time from npm (or the fontsource package), pinned in `docker/media-generator/Dockerfile` and listed in `docker/media-generator/catalogue/LIBS.json`:

- `gsap@3.14.2` (GSAP standard no-charge licence (see LICENSE-gsap.txt in each item))

