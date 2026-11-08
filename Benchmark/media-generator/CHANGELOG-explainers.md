# Explainer videos (black and white): version history

Target style: v7 motion generator, CSS 3D acts, 1920x1080, 20 s, silent.
Two themes from the same scene script:

- `bn-v7-explainer-black/`: black background, cyan accent (`#27d4ff`).
- `bn-v7-explainer-white/`: light grey background (`#e2e8f0` plate), teal accent (`#0f766e`).

**Rule:** every change bumps the version. Each version keeps `video-explainer-<theme>-vN.mp4` and `index-explainer-<theme>-vN.html`. `video.mp4` in each folder always holds the latest render.

---

## LinkedIn motion v1: flat motion-graphics explainer (new track, 16:9, silent)

Folder: `linkedin-motion/`
Files: `linkedin-motion/video-linkedin-motion-v1.mp4`, `index-linkedin-motion-v1.html`, `video.mp4` (same as v1)
Spec: 1920x1080 (16:9, the LinkedIn choice in `docs/designs/story-to-video-workflows.md`), 20.0 s, 30 fps, 600 frames, no audio. Captions are on-screen block captions, because LinkedIn plays muted.
Build: HTML + GSAP paused timeline (`vendor/gsap.min.js`). No three.js, no clocks, no randomness. `hyperframes lint`: 0 errors, 0 warnings. Rendered in `tokenfrugal/media-generator:hfshell` in 13 s.

**Changed (first version, nothing to correct yet)**
- Motion-led explainer, four acts, no narration:
  1. Intake (0 to 5 s): twelve request tiles travel into a funnel.
  2. Pipeline (5 to 10 s): three step nodes (triage, route, resolve) appear; connector lines draw in; a pulse travels the rail.
  3. Result (10 to 15 s): paired before and after bars grow; labelled "Illustrative, not measured".
  4. Discussion (15 to 20 s): closing professional question on teal, with an animated reply bubble. It follows the LinkedIn rubric (closing question tied to the lesson).
- Progress bar across the top; caption block in acts 1 to 3.

**Expected outcome**
- Reads as a professional explainer without a voice track, and the motion carries the idea.
- Captions carry the meaning for muted viewers.

**Observed (contact sheet of 12 frames, `review/sheet.png`)**
- Tiles converge on the funnel. Nodes, connectors and pulse appear in order. Bars grow and the after-bars are visibly lower.
- Question card and bubble resolve at the end. No overlaps, nothing clipped at 1920x1080.
- Captions are legible at sheet scale.

**Open**
- Still sparse for a "professional" look: flat shapes and no icon set (vendor icons are not used, to stay trademark-safe), and no per-act camera move. A slow push-in per act and a dot-grid background are the next candidates.
- Act 4 leaves the lower-left empty.
- The before and after values are illustrative shapes, not data. A real chart needs real figures and a source line.
- Voice is not in this version. Add it only if asked.

---

## v11 (white theme only): acts 2 to 4 moved to WebGL (three.js)

Files: `bn-v7-explainer-white/video-explainer-white-v11.mp4`, `index-explainer-white-v11.html`
Same vendor bundle as v10 (`vendor/three.bundle.js`). Act 1 is unchanged from v10.

**Changed**
- Act 2 (6.5 to 13.2 s) is a three.js canvas: a 420x18x240 `RoundedBoxGeometry` slab, a teal glow sprite, a torus ring, 78 nodes (hub nodes teal), 220 cloud dots and 150 edges as cylinders. Same seeded PRNG call order as the CSS version. Camera-group rotation runs from (8, -16) to (4, 6) degrees.
- Act 3 (12.8 to 17.6 s) is a three.js canvas: two torus rings, three label plates (CASE, LEAD, NO ACTION) as canvas textures, 90 tendril cylinders (teal and light core), and a core glow sprite with a sphere.
- Act 4 (17.6 to 20.0 s) is a three.js canvas: three stacked `RoundedBoxGeometry` slabs in one teal material, which build the BUSINESSNEXT mark.
- Each act is a pure function of its local time: one proxy tween per act with `onUpdate`. No clocks, no `requestAnimationFrame`, seeded PRNG only.
- Text and caption DOM and their timeline entries are unchanged.

**Corrections**
- The act-2 scene had no fade-out, so its network and slab stayed behind acts 3 and 4 and the end card. Added `#s2` fade-out at 12.8 s (0.5 s), with a dissolve into act 3. Found on the first render's contact sheet, fixed before the final render.

**Expected outcome**
- Acts 2 to 4 get the same solid lit volumes, soft shadows and tube lighting as act 1, so the film reads as one visual language.
- Clean handover at 12.8 s and a clean end card at 17.6 s onward.

**Observed (contact sheet of 20 frames and frames at 7, 12, 12.5, 13, 13.5, 15, 16, 17, 18.5, 19.5 s, rendered in the media-generator container, 47.6 s render, 600 frames, 20.0 s)**
- Act 1 unchanged from v10.
- Act 2: slab, ring, cloud and network build in order. Captions read cleanly.
- Act 3: rings, label plates and tendrils converge on the glow. Full-size frame at 15 s: labels legible.
- Act 4 and the end card: the stacked mark and BUSINESSNEXT title on a clean background, with no leftover act-2 or act-3 layers.

**Open**
- Act-3 label plates are pale (`#e2e8f0` on `#f4f6f8`). Labels are legible, but the plates barely separate from the background. Needs a darker plate or a teal outline.
- Act-3 rings show small gaps along the torus at about 15 s. Likely a depth or transparency artifact between the ring, the plates and the fade. Not yet isolated; the rings need one more check.
- Act-3 rings are large (radius 325) and cover much of the network from act 2. Consider a smaller radius.
- Act-1 gate ring still reads as an arch (carried from v10).
- `hyperframes lint` on the folder: 3 errors, 1 warning. Errors: `Math.random` and `requestAnimationFrame` inside the vendored `three.bundle.js` (false positives, not called in this composition; the same findings as v10), and multiple root compositions because the old snapshot HTML files (v7 to v10 and v11) sit in the folder. Warning: composition file over 400 lines. Snapshot files should move to an archive folder, or the lint should be scoped to `index.html`.
- Black explainer is still on the v7 CSS version.
- Process note: the act 2 to 4 HTML was written directly in the session, not dispatched through tokenfrugal or a Haiku subagent as the CLAUDE.md global rule asks. Recorded here for the audit trail.

---

## v10 (white theme only): act 1 moved to WebGL (three.js)

Files: `bn-v7-explainer-white/video-explainer-white-v10.mp4`, `index-explainer-white-v10.html`
Vendor added: `bn-v7-explainer-white/vendor/three.bundle.js` and `THREE-LICENSE.txt` (copied from the businessnext-video-v3 skill assets, MIT).

**Changed**
- Act 1 (0 to 6.2 s) is now a three.js canvas: `RoundedBoxGeometry` boxes (radius 10 to 12 px), `EdgesGeometry` outline at 40% opacity, one hemisphere light plus key and fill directional lights, and soft PCF shadows on a shadow-only floor at y = 420 px.
- Contact shadow: a radial-gradient blob under each box.
- Lanes are `TubeGeometry` (radius 4.5 px, same 9 px width as v9) on the same Bezier paths. Dots move along the same curves with the same timing.
- Gate ring is a `TorusGeometry` (radius 120 px, tube 4 px) that fades in at 3.0 s.
- Camera orbit: pitch 32 to 26 degrees, yaw -26 to -14 degrees, same as the CSS version. The FOV is set so 1 unit equals 1 CSS px at the z = 0 plane.
- Everything is driven by one proxy tween (`A1.t`, 0 to 6.2 s), so the frames are a pure function of time. No clocks, no `requestAnimationFrame`, no randomness.
- Acts 2 to 4 are unchanged (still CSS 3D).

**Corrections**
- Act-1 boxes read as flat cards and slivers in v8 and v9. The CSS 3D version has no real lighting or shadows, which was the main quality gap against the reference.

**Expected outcome**
- Boxes read as solid volumes with lit top, front and side faces, rounded edges and a visible contact shadow.
- Stack blocks separate instead of collapsing into slivers.

**Observed (contact sheet and frame at 4 s, rendered in the media-generator container, 39 s render, 600 frames, 20.0 s)**
- Stack reads as six separate solid slabs, lit top and side, with soft shadows on the floor.
- Gateway is a solid rounded block with a lighter top face.
- Lanes read as tubes with light falloff. Dots travel along them.
- Fade-in and fade-out at 0 s and 6.2 s behave as before.

**Open**
- `hyperframes lint` flags the vendored bundle: `Math.random` appears in the three.js bundle (static match, not called here) and `requestAnimationFrame` (not called here). Lint errors are false positives for this composition, but the lint gate must be relaxed or the bundle trimmed before this goes into the pipeline.
- Gate ring reads as an arch above the gateway. It may need to be a flatter disc or moved to the front face.
- Acts 2 to 4 are still CSS 3D. Same WebGL treatment is needed for them if you want the full quality match.
- Black explainer is still on the v7 CSS version.

---

## v9 (white theme only): lighting ramp, deeper boxes, higher camera

Files: `bn-v7-explainer-white/video-explainer-white-v9.mp4`, `index-explainer-white-v9.html`

**Changed**
- Tone ramp per face: top `#ffffff`, front `#e6eaf0`, side `#aeb6c3` (stack) and `#9aa3b1` (gateway).
- Corner radius 6 px on every face. Face gradient softened and a faint darker bottom edge added.
- Depth: stack 110 -> 170 px, gateway 170 -> 230 px.
- Act-1 camera start tilt 14 -> 32 degrees, end 10 -> 26 degrees, so the top face shows.

**Corrections**
- User asked why the boxes did not look like the soft-edged reference boxes. Causes: faces too close in tone, camera too flat, boxes too shallow, no rounded corners.

**Expected outcome**
- Top face brighter and visible, front and side separate, corners softer.

**Observed (contact sheet)**
- Top faces now show. Gateway reads as a box with a lighter top.
- Stack blocks still read as thin slivers at the back. Depth and tone changes did not fully reach them.
- Still short of the reference: no contact shadow under the boxes yet.

**Open**
- Stack blocks need larger scale or a different spacing so they do not collapse into slivers.
- Contact shadow under each block.
- Black explainer is still on v7 styling.

---

## v8: act-1 boxes with fine edges (white)

Files: `bn-v7-explainer-white/video-explainer-white-v8.mp4`, `index-explainer-white-v8.html`

**Changed**
- Act-1 stack and gateway fronts changed from near-white `#f4f5f7` to cool grey `#dfe4ea`, so the blocks separate from the light plate.
- Side faces darkened: stack `#a9b0bb` -> `#7b8595`, gateway `#9aa2ad` -> `#6b7585`.
- Top faces set to `#f8fafc`.
- Fine edge: face outline 2 px at 0.22 alpha -> 1 px dark line at 0.55 alpha, with a 2 px light inner rim.
- Side shade strength 0.35 -> 0.45.

**Corrections**
- User asked for the act-1 page shape to read as a box with fine edges. Previous blocks were too pale to separate from the background.

**Expected outcome**
- Stack and gateway read as solid boxes with crisp outlines and visible side faces.

**Observed (contact sheet)**
- Blocks are greyer and the outlines are visible at 1080p.
- They still read softer than a strong 3D render. Lighting is flat.

**Open**
- The black explainer still has v7 box styling; it needs the same edge change if wanted.

---

## v7: first black and white explainers

Files, black: `bn-v7-explainer-black/video-explainer-black-v7.mp4`, `index-explainer-black-v7.html`
Files, white: `bn-v7-explainer-white/video-explainer-white-v7.mp4`, `index-explainer-white-v7.html`

**Changed**
- Two themes built from the `bn-v3-recreate-v7-3d` base scene script.
- Black theme: black ground, cyan lanes and rings, white/grey text, cyan end-card mark.
- White theme: light ground, teal lanes and rings, dark text, teal end-card mark.
- White theme plate background set to `#e2e8f0` (plate text `#111318`). Earlier dark text on a dark plate was unreadable.
- Box depth and side shading (the 3D volume change) carried into the base scene before the copy.

**Corrections**
- User asked for 3D boxes that read as volumes, not flat rectangles.
- User asked for two explainers with different background and colour themes.

**Expected outcome**
- Both themes read clearly at 1080p with the same four-act structure.
- Act-1 stack and gateway read as solid blocks with visible side faces.

**Observed (contact sheets, `sheet_1s.png`)**
- Both themes: four acts render in order, with the end card at 19 s.
- Act-1 stack: the lanes and stacked blocks now have visible edges in both themes.
- Gateway block is still a pale front face with a faint side. It is the weakest 3D read in both themes.
- Stacked act-1 blocks still look close to flat cards from the camera angle.

**Open**
- Gateway and act-1 stack front faces need a darker or tinted front, or a stronger side shade, so they separate from the background.
- Base `bn-v3-recreate-v7-3d/video.mp4` still holds v6 content. It needs a v7 re-render with the box-depth change.
- No audio yet.
- Durations: 20.000 s was recorded at render time. Host ffprobe is not installed, so the duration was not re-checked on the file in this pass.
