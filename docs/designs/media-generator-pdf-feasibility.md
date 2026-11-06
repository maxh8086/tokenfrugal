# Media generator: feasibility of the PDF's video styles

* **Status:** exploration only. No code written, nothing dispatched, no EGM review run.
* **Source:** `media-generator.pdf` (109 pages, a saved chat with an assistant about "Docker Media Generator Video Workflows"). The PDF has no text layer; the OCR text was used.
* **Date:** 2026-11-05
* **Question:** can offline code in the `docker/media-generator` image produce cinematic or commercial-grade video from the PDF's ideas, rather than plain slides?

## 1. Short answer

- **Yes for motion-graphics explainers.** Architecture diagrams, kinetic type, camera moves across a node graph, data-flow lines, and a clean grade (grain, vignette, rack-focus blur) are all buildable from pinned tools: HyperFrames (GSAP in headless Chromium), Manim, FFmpeg, Piper and whisper.cpp. This is the look the PDF is aiming at.
- **Not yet for "stunning" or photoreal.** The image has no photo, footage, or brand-icon library, no licensed music, and no real sound design. The PDF's SFX and ambient ideas are procedural. Without art direction and assets, output will read as a polished corporate explainer, not a commercial film.
- **The PDF's code cannot be used as written.** It has determinism bugs, an invalid encode flag, a broken SFX condition, and a 1080x1920 vs 1080x1350 mismatch (section 5). Treat it as a list of ideas, not as source.
- **The repo already has a different pipeline.** `docker/media-generator/pipeline.py` turns a talking clip into a 9:16 short (Whisper word captions, sentence cuts, blurred bars). `render-engine/` renders text scenes with hard cuts, Piper narration and a procedural music bed. Neither implements the PDF's architecture engine (JSON manifest, node graph, roving camera, data packets).

## 2. What the image pins and runs (verified in the repo)

| Capability | In image | Evidence |
| --- | --- | --- |
| HTML/GSAP scene render (headless Chromium) | Yes: HyperFrames 0.8.223, `chrome-headless-shell` via `hyperframes browser ensure`, Debian chromium | `Dockerfile` lines 10-72 |
| Remotion 4.0.539 | Installed globally, still present. Licence concern raised in the PDF thread | `Dockerfile` lines 8, 23-34 |
| Manim Community v0.22.1 (commit `16ea443e`) | Yes, own venv `/opt/manim-venv`. No LaTeX, so `Tex`/`MathTex` do not work | `Dockerfile` lines 10-45 |
| Piper TTS 1.8.0, voice en_US-lessac-medium (SHA-pinned) | Yes, `/opt/voice`. Piper is GPL-3.0-or-later; voice terms need checking before commercial use | `Dockerfile` lines 93-109 |
| whisper.cpp v1.7.5, base.en | Yes, `whisper-cli` | `Dockerfile` lines 6-21 |
| tesseract (eng) | Yes | `Dockerfile` line 50 |
| FFmpeg | Yes (Debian) | `Dockerfile` line 14 |
| numpy (unpinned), soundfile 0.14.0 | Yes (story-film workflow) | `Dockerfile` lines 64-67 |
| Pinned reference repos | reelforge 740bf70 (Apache-2.0), hyperframes-motion-library 98c40ca (MIT), hyperframes-student-kit 10511e5 (MIT), product-launch-motion edbfb10 (MIT), animated-diagrams-skill 3de812d (Apache-2.0), design-engineering dbbe43b (MIT) | `Dockerfile` lines 80-90 |
| Fonts | 59 Debian families (`fonts.txt`, `fonts.lock`), CJK excluded on purpose | `docker/media-generator/fonts.txt` |
| Render engine | `POST /render` in `render-engine/server.js`: props to HyperFrames MP4, one render at a time, Piper narration and ffmpeg music, craft checks (read speed, minimum exposure, cut budget, short last scene) | `render-engine/server.js`, `lib/craft-check.js` |
| Talking-clip shorts | `pipeline.py`: whisper word timestamps, OCR check for burned-in subtitles, `compose_intro.py`, `make_score.py` | `pipeline.py` |

**Not in the image:** photos or footage, a brand or vendor icon library, a LUT file (`dark_banking.cube` does not exist), a music library, a 3D engine other than Manim, `ffmpeg` `loudnorm` tuning, and any SRT burn-in or 1080x1350 export path.

## 3. Inventory of the PDF's ideas

Verdict key: **Ready** = pinned tool does it now. **Small code** = a few hours of template or FFmpeg work. **Build** = a new module. **Gap** = needs assets or taste the image lacks.

### 3.1 Scene and camera

| Idea (PDF section) | Tool | Verdict | Notes |
| --- | --- | --- | --- |
| Kinetic keyword blast, word by word, bold, static (sync-driven) | HyperFrames + GSAP | Small code | `render-engine` already does word spans with `textContent`. Needs whisper timestamps and glue-word grouping. |
| Font auto-shrink by character count | GSAP/JS | Small code | Straightforward. |
| Pivot-title minimal text covered by narration | HyperFrames | Ready | Already the render-engine model. |
| Rule of Isolation (dim inactive nodes, grayscale, blur, one glowing node) | CSS filters + GSAP | Small code | Watch GPU cost of `filter: blur` on many nodes. |
| Roving camera pan/zoom to a node (GSAP on world container) | GSAP | Small code | Core of the architecture engine. Needs a manifest schema. |
| Loop transition (flash, reset camera to 0,0) | GSAP | Small code | Cheap. Must loop the first frame's composition, not just flash. |
| Growing node cluster / drill-down on zoom > 1.5 | GSAP + class toggle | Small code | Needs a `resize` listener driven by the timeline, not by wall-clock. |
| 3D perspective CSS grid of data bars (`rotateX`, `translateZ`) | CSS 3D + GSAP stagger | Small code | Works headless. PDF uses `Math.random` for heights: must become seeded. |
| Manim `ThreeDScene` architecture stack | Manim | Build | Real 3D, ambient rotation. Renders are slow; lighting is basic. Good for diagrams, not for product realism. |
| Manim roving camera (`MovingCameraScene`) | Manim | Build | Possible, but mixing two renderers (Manim overlay plus HTML) is fragile. Pick one per scene. |
| Manim `add_fixed_in_frame_mobjects` (2D text over 3D) | Manim | Build | Manim's 2D text is less crisp than HTML text. Prefer HTML overlay. |
| Glass-architecture Manim with transparent PNG overlay | Manim `-t` + FFmpeg `overlay enable=between()` | Ready | Works. Needs the Manim timing mapped to Whisper times. |

### 3.2 Data flow and motion

| Idea | Tool | Verdict | Notes |
| --- | --- | --- | --- |
| Fiber-optic dashes crawling along SVG lines | SVG + CSS `@keyframes` | Small code | **Determinism issue:** CSS infinite keyframes run on the browser clock. Drive `stroke-dashoffset` from the GSAP timeline instead. |
| Data packets along a path (GSAP attr/motionPath) | GSAP | Small code | PDF destroys DOM on complete; fine. Time must come from the timeline. |
| Arrival shockwave ring (scale and opacity) | GSAP | Ready | Simple. |
| Breathing mesh gradient background | CSS radial gradients + keyframes | Small code | Same determinism rule: drive from the timeline. |
| Rolling odometer numbers | GSAP object proxy | Ready | Fine. |
| Chromatic aberration on a fast pan (`drop-shadow` split) | CSS filter | Small code | Cheap, but use sparingly; it can read as a glitch. |
| Config/code terminal cards, telemetry meters | HTML/CSS | Small code | Good for engineering explainers. |
| 3D perspective tilt product cards | CSS 3D | Small code | Needs product images. Gap if none supplied. |

### 3.3 Post-processing (FFmpeg)

| Idea | Verdict | Notes |
| --- | --- | --- |
| Rack-focus boxblur with `luma_radius` expression over the first 3 s | Ready | Expression is valid FFmpeg syntax, but note the PDF's `max_t` is not defined: pass the duration in. |
| Temporal grain `noise=alls=4:allf=t+u` | Ready | Keep low, 2-4. |
| Vignette `PI/4` | Ready | |
| LUT grade `lut3d=dark_banking.cube` | Gap | No LUT file exists. Build one with a short script, or grade with `eq`/`colorbalance`. |
| `-apad` on final mux | Ready | Use it with `-shortest` off, or the audio is cut at the video length. |
| Top progress bar (GSAP width tween) | Small code | Cheap retention cue for LinkedIn. |
| 1080x1350 (4:5) export | Small code | `render-engine` has fixed 1920x1080 in `composition/index.html`. Needs a size parameter. |
| SRT export and burn-in (`subtitles=` with `force_style`) | Ready | Needs whisper word times turned into SRT cues. |
| 60 fps output | Small code | HyperFrames `--fps` is already passed; check render time at 1080x1350 60 fps. |

### 3.4 Audio

| Idea | Verdict | Notes |
| --- | --- | --- |
| Piper narration per scene, `adelay` placement | Ready | `render-engine/lib/audio-plan.js` already does this, checking clip lengths against scene slots. |
| Whisper word timestamps for timing | Ready | `pipeline.py` uses `whisper-cli -oj -ml 1 -sow`. The PDF invents a `sync.json` schema: map it to the real whisper JSON. |
| Digital "ping"/"swoosh" SFX at keyword times, ducked under narration | Small code | Needs an SFX asset (none in image). The PDF's `build_audio_mix_command` has a bug (`sfx_wav` is not a parameter). |
| Procedural drone bed | Ready | `render-engine` has a deterministic ffmpeg bed. Quality is "background hum", not a score. |
| Ambient industrial / cinematic music | Gap | No licensed music in image. Options: user-supplied tracks (licence checked by user), or a synthesized bed. |
| Loudness target (-16 LUFS) | Small code | Add `loudnorm` in the mix step. |

### 3.5 Pipeline and orchestration

| Idea | Verdict | Notes |
| --- | --- | --- |
| `pipeline.py` batch over a directory of job JSON files | Build | Repo's `pipeline.py` is a different tool (clip to short). A new orchestrator is needed, or `render-engine` extended. |
| Job manifest (nodes, connections, camera cues, tiers, telemetry, code snippets, hotspots) | Build | Schema is sound in principle. Validate with a JSON schema before rendering (the `props.js` validator pattern already exists). |
| Hydrate `index_template.html` with JSON | Small code | `render-engine` already writes `props.js` per job. Same approach. |
| Multi-theme switch (skyline, rain, dawn, vines, searchlight) | Small code | Each theme is a CSS + GSAP block. The PDF's themes are untested. |

## 4. Verdict by style: can offline code reach cinematic or commercial quality?

| Style | Reachable offline? | Main blocker | What "good" looks like |
| --- | --- | --- | --- |
| Architecture explainer with roving camera and isolation | **Yes**, high confidence | Manifest schema and layout work; art direction | Clean, consistent node style, slow camera moves, one idea per shot. Close to commercial explainer quality. |
| Kinetic typography keyword film (TikTok/LinkedIn) | **Yes**, high confidence | Caption timing and glue-word grouping | Fast, legible, bold type synced to narration. Reads as professional social content. |
| TED-style minimal pivot text with narration | **Yes**, high confidence | Type choice and spacing | Restrained, large type with generous space. Depends on taste more than code. |
| Manim 3D glass architecture | **Partly** | Render time; basic lighting; no LaTeX; 3D diagrams look technical, not premium | Acceptable for technical diagrams. Premium look needs better materials and lighting than Manim provides. |
| Procedural backgrounds (mesh gradient, 3D data bars) | **Yes**, medium confidence | Determinism (rewrite the PDF's CSS keyframes to timeline) | Subtle, slow, on-brand. Overdone effects read as cheap. |
| Loop bridge / seamless replay | **Partly** | Needs the last frame to match the first; a flash is not a loop | Requires a deliberate end card that mirrors the opening hook. |
| Product or hardware realism (3D product shots, photo UI) | **No** | No assets, no 3D models, no photos | Would need supplied footage or assets. |
| Music and sound design at commercial level | **No** | No licensed music or SFX library | Would need supplied tracks or sound packs under a known licence. |

**Bottom line:** the offline stack can deliver a convincing motion-graphics explainer in the style of tech keynote diagrams. The gap to "stunning" is asset quality, music, and art direction, not the rendering engine.

## 5. Problems found in the PDF's code (do not copy blindly)

1. **Non-deterministic render.** `Math.random` is used for bar heights, and the PDF's CSS uses infinite `@keyframes` (flow dashes, mesh gradient, pulse). Both break the rule that renders are deterministic and that time comes only from the timeline. Fix: seeded PRNG, and drive every animation from GSAP.
2. **Invalid encode.** `-c:v libx264 ... -pix_fmt yuva420p` is not valid for MP4 (libx264 has no alpha). Use `yuv420p` for the final file.
3. **SFX condition bug.** `has_sfx = sfx_times and os.path.exists(sfx_wav)` refers to `sfx_wav`, which is not a parameter of `build_audio_mix_command`. The mix would fail or silently skip SFX.
4. **Size mismatch.** The architecture prompt says 1080x1920. The LinkedIn prompt says 1080x1350. The 4000x4000 world canvas inside a 1080x1920 viewport is never sized against either.
5. **Undefined variables.** `max_t` in the rack-focus expression is not defined in the sample command.
6. **Remotion contradicts the constraints.** The PDF tells the user to drop Remotion for licence reasons, but the image still installs it (`Dockerfile` line 23). Remove it or document it as unused before the licence review.
7. **Invented schemas.** `sync.json` and the Whisper output fields in the PDF are guesses. The real whisper-cli JSON is what `pipeline.py` reads (`transcription` list); verify field names before building on them.
8. **Unrun code.** None of the PDF's code was executed. Treat every snippet as a sketch.

## 6. Proposed path (for the EGM brainstorm, not yet approved)

Slices, each testable on its own:

1. **Slice A, the explainer template.** One HyperFrames composition for a 3-node architecture with a roving camera, isolation, and one data packet. Fixed 1920x1080. Deterministic (no `Math.random`, no CSS keyframes). Test: render, frame sheet, duration check.
2. **Slice B, timing from narration.** Piper narration per beat, whisper word times, cues that trigger camera moves and packets. Test: cue times match transcript.
3. **Slice C, the grade and size.** FFmpeg post chain (rack focus, grain, vignette, LUT or `eq`) and a size parameter for 1920x1080 and 1080x1350. Test: encoded file probe.
4. **Slice D, captions.** Kinetic keyword captions and SRT burn-in from whisper times. Test: caption times match speech.
5. **Slice E, assets and music.** Only after the user supplies assets or music with a known licence.

Manim 3D scenes and LUT files are optional; add them after slice A works.

## 7. Open questions (from earlier, still unanswered)

1. What is the goal and the audience for these videos (sales, LinkedIn, internal training, product launch)? The answer changes which style is worth building first.
2. Is this the same feature as the BusinessNext-style film brief from earlier, or a separate one? The two overlap in timing and narration, but the BusinessNext skill also covers voice profiles, native vendor icons and 3D acts, which the image does not have.
3. Were any of the PDF's code samples ever run, and should the design rely on the PDF as a source, or only on what this repo has verified?

## 8. Not verified here

- No PDF code was executed. No render was produced. Timings and quality claims above are judgments from the image's pins, not measurements.
- `render-engine` and `pipeline.py` were read, not run, in this pass.
- The three remaining OCR sections (lines 9184-9506, a reference `pipeline.py`) were only partly read.
