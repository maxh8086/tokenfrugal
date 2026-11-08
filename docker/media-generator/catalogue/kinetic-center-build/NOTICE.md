# kinetic-center-build: licence notice

Status: NOTICE-FOUND (open-source notice present in the item files; see `docs/designs/hyperframes-catalog-licences.md`).
Source: HyperFrames registry item `kinetic-center-build`, fetched with `hyperframes@0.8.223 add kinetic-center-build --json --no-clipboard` (pinned in `catalogue/FETCH.json`).

Licence and notice files shipped with this item (committed in this folder):
- `compositions/components/vendor/LICENSE-gsap.txt`

Fetched from the registry item, with exact-text patches recorded in `catalogue/FETCH.json`:
- `compositions/components/kinetic-center-build.html` (2 patched hunks)

Libraries installed at build time (not fetched, not committed): the gsap and CustomEase files that the item loads from `compositions/components/vendor/` are listed in `catalogue/LIBS.json` and copied in by `install-libs.py`.

## Geist font (SIL Open Font Licence 1.1)

The item's original Geist files (`geist-1.woff2` to `geist-5.woff2` and `geist.css`, taken from Google Fonts with no pinned version) are no longer vendored. They are replaced by:

- Source: `@fontsource/geist@5.3.0` (npm), tarball sha256 pinned in `catalogue/FETCH.json`. Each woff2 file's sha256 is pinned there too.
- Weights 500, 600, 700 and 800 (as before), subsets `latin`, `latin-ext` and `cyrillic`.
- `compositions/components/vendor/geist.css` is authored for this repo (`catalogue/overrides/kinetic-center-build-geist.css`): one `@font-face` block per weight and subset, with the unicode-ranges taken from the fontsource CSS.

Effect on rendering: the subsets `cyrillic-ext` and `vietnamese` have no fontsource subset and are dropped. Glyphs that exist only in those two subsets fall back to the next font in the stack. Text in the `latin`, `latin-ext` and `cyrillic` ranges is served from the same Geist design at the same weights; the files are not byte-identical to the former Google Fonts files.

## Libraries installed at build time

- `gsap@3.14.2` (GSAP standard no-charge licence, not OSI; see `LICENSE-gsap.txt`), installed from npm at the version pinned in the Dockerfile and listed in `catalogue/LIBS.json`.
