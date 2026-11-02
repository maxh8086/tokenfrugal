# Mode B three-scene template (silent render and stills)

* **Date:** 2026-11-02
* **Scope:** D12 template (three scene types) and the D13 point 3 stills gate. Silent video only; no narration or bed.
* **Project:** `docker/media-generator/templates/mode-b` (title 0-8 s, text lines 8-18 s, closing 18-25 s), mounted read-only at `/templates/mode-b` by the `media-generator` service. GSAP is vendored in `vendor/` so the render does not depend on a CDN.
* **Output:** `Render/mode-b-template-spike.run/tpl_silent_25s.mp4` in the media workspace (`OneDrive/Videos/video-editor`), sha256 `ca8e212a22d43a805f65bb918a6879100698c743e01640e47e638e73b0010f87`.
* **Manifest:** `Render/mode-b-template-spike.run/manifest.json`. Stills and contact sheet are in `Render/mode-b-template-spike.run/stills/`.

## Result

| Check | Value | Result |
|---|---|---|
| `hyperframes lint` | 0 errors, 3 warnings | Pass with warnings (see below) |
| Video | h264, 1920x1080, 30/1 fps, 750 frames, 25.000 s | Pass |
| Audio | none | Pass (silent) |
| Stills | one per scene, all three differ and none is blank | Pass (checked by eye) |

## Warnings and open items

* **`nested_structure_needs_subcomposition` (x3).** Each scene is a section with child elements. The fix is one sub-composition file per scene under `compositions/`, mounted with `data-composition-src`. Not done yet; it is the next change if the gate is approved.
* **Font is a placeholder.** The stack names "Template Sans" with `src: local("Arial")`. Arial is not an open licence, and D12 requires a bundled open-licence sans with its licence and hash in the manifest. The render looks like a different sans, so the font actually used is not confirmed. Font choice needs a decision, and the file would need a download, which needs your permission.
* **Palette is a placeholder.** Dark ground `#0e1013`, ink `#f2f2f2`, grey accent `#8a909a`. These follow D12's shape (dark ground, light text, one grey accent) but the values are not approved.
* **Remote 404.** The render log still shows 6 non-blocking 404 responses. The GSAP script is now local, so the source is something else (probably a runtime asset). Not identified yet; the composition does not depend on it visually.

## Stills gate (D13 point 3)

Status: **pending approval**. The stills are `stillsscene_title.png` (4 s), `scene_lines.png` (14 s) and `scene_closing.png` (22 s), with `contact_sheet.png`. These are the first real per-scene stills. The spike stills stay marked `approved_spike_only` and do not count for this gate.

## What this does not cover

Narration mux for this template, the -18 dB bed mix and level gate, the `brief` tool (still a stub), and the full render with music.
