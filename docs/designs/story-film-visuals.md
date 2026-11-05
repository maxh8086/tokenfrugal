# Story film visuals: revised draft 2 (2D slice 1, GPU-gated 3D later)

* **Status:** revised draft 2. Not approved. Nothing dispatched. Open question G (GPU exposure) blocks the 3D part, not slice 1.
* **Date:** 2026-11-04
* **Related:** [story-film-visuals-review.md](story-film-visuals-review.md) (six-lens review of draft 1), [story-to-video-workflows.md](story-to-video-workflows.md), `scripts/story_film.py`, `docker/media-generator/Dockerfile`

## 1. Problem

Films from `scripts/story_film.py` show word captions, labels and plain blue chips. Scenes have no picture content, no camera motion, and a narration that opens with the result, so the cause is never shown first.

Target look (creative brief from the user, 2026-11-04): a white clean-room world with black glass screens and soft light. The camera always moves slowly. Pink glowing tubes carry envelopes and light pulses left to right, splitting and merging. Hard cuts carry an envelope or pink line across. An envelope breaks into particles, then becomes a node graph or a grid of numbers. App screens float as glass panels with a pink highlight sweeping their rows. Four 3D scene types from the approved prototype: fibre (sources feeding a gateway), graph (a request bursting into a particle graph with the answer path lit), lanes (routing to gates), stack (layered platform). Light and dark rooms, glow, and three transitions (light sweep, iris, crossfade). Key moments are timed to the narration.

Constraints that stay in force: offline, no generative image or video models, deterministic output, pinned and checksummed third-party files, no hard-coded paths.

## 2. Verified facts (2026-11-04)

| # | Fact | How checked |
|---|---|---|
| V1 | Host GPU is an NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB, driver 592.82. | `nvidia-smi` on host |
| V2 | `docker run --gpus all maxh8086/media-generator:1 nvidia-smi -L` sees the RTX 4060. The container gets the NVIDIA compute libraries. | Run, exit 0 |
| V3 | Headless Chromium 156 in the image gives working WebGL, but the renderer is `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device ...))`, which is CPU software GL. | Probe page dumped with `--dump-dom`, flags `--enable-unsafe-swiftshader` with default, Vulkan and GL-angle settings |
| V4 | With `--gpus all`, `NVIDIA_DRIVER_CAPABILITIES=all`, and the flags above, Chromium still uses SwiftShader. `/etc/vulkan/icd.d` is empty in the image, so no NVIDIA Vulkan driver is visible to Chromium. `--use-gl=egl` gives no WebGL. | Same probe, several flag sets |
| V5 | The image is CPU-only by its own header. `story_film.py` runs `docker run` without `--gpus`. | `Dockerfile` line 2; `_docker_in_work` line 472-474 |
| V6 | Remotion 4.0.539 and HyperFrames 0.8.223 are installed globally and use the same Debian Chromium. Neither has been tested with WebGL here. | Dockerfile lines 8-9, 23-34 |
| V7 | Icon measurement: the 24 topic-4 Tabler SVGs total 12,176 bytes. The full `generic` SVG set is 2,903,284 bytes. The full v3 `icons/` folder is about 19 MB as JSON with metadata. The 60 MB figure in draft 1 had no source and is dropped. | Measured from the v3 `icons/generic.json` |
| V8 | Tabler names for topic 4 (see section 5). | Looked up in `icons/generic.json` |

Consequence of V3 to V5: a 3D path is possible on the CPU (SwiftShader), but the GPU is not used by WebGL in this image. The v3 cost of about 3 s per 1080p frame for software WebGL (`three-d.md` line 85) is a guideline, not measured here. Enabling 3D on the GPU needs the NVIDIA Vulkan/GL driver files exposed to the container, which is not done and not verified.

## 3. Decisions

Status key: **Proposed** needs approval. **Later** is out of slice 1. **Blocked** needs an open question answered first.

| # | Decision | Status |
|---|---|---|
| D1 | Slice 1 vendors the 24 topic-4 Tabler icons (12,176 bytes SVG) with a manifest (path, sha256, upstream version, licence path) and the Tabler MIT licence text. | Proposed |
| D2 | Other vendors (`ai`, `aws`, `azure`, `gcp`, `microsoft`, `oci`, `k8s`, `vmware`, `redhat`, `brand`) wait until a film needs a named vendor. | Later |
| D3 | 3D is GPU-gated, as the user asked. At film render start, a WebGL probe reads the renderer string. A GPU renderer enables 3D shots. A SwiftShader or unknown renderer disables them, and the film uses 2D shots only. Rule recorded now; the probe and its result go in the film's job file. | Proposed; 3D shots are off until G is answered |
| D4 | Three.js pin when 3D is built: v3 `templates/project/assets/vendor/three.bundle.js` with `THREE-LICENSE.txt`. Record version and sha256 at pin time. | Later |
| D5 | Slice 1 scene art: Tabler icon tiles, existing chips, CSS glass panels, SVG pink tubes with an animated light pulse along a path. No stock or generated images. | Proposed |
| D6 | Slice 1 shots: 2D `stack` and `fibre`, placed by hand on sentence timings. Hard cuts between shots. Each shot has a slow camera move for its whole length (the brief's "always moving" rule). Travel is set per shot type and scaled by shot duration, so short and long shots move at the same speed. | Proposed |
| D7 | Slice 1 transitions: hard cut and light sweep. Iris and crossfade are Later. v3's cross-dissolve (0.60 s, `narration.md` line 239) is the crossfade if one is wanted, not a new value. | Proposed |
| D8 | Cause-first script rule moves into slice 1 (see section 6). | Proposed |
| D9 | Sentence timings: the existing character-proportional estimate from `word_timings()`. Stated openly as an estimate. | Proposed |
| D10 | Dark room values: Later, with open question F. Slice 1 uses the light room only, with `CHIP_LIT_BG` (`#2563eb`, `story_film.py` line 87) for lit chips. | Proposed |
| D11 | Remotion versus HyperFrames for the 3D scenes: not decided. Both use the same Chromium, so neither changes the GPU result in V4. Decide by a spike that renders one identical 3D test scene in each (open question H). | Blocked on H |

### 3D determinism rules (apply to any 3D shot, D3)

* Pure function of master-clock time. No `Math.random`, `Date`, or `performance.now`.
* A seeded PRNG if randomness is needed.
* Pinned GL flags and a pinned renderer string. The renderer string is written to the job file. A GPU render and a SwiftShader render give different pixels, so the determinism test runs on one renderer only.
* Test: render the same 3D shot twice and compare per-frame sha256.

## 4. Shots and camera (slice 1)

* Two 2D shot templates, `stack` and `fibre`, written as HTML plus GSAP in the existing `story_film.py` HTML builder (`build_scene_html`, line 238). No new renderer. The shot abstraction is new code.
* Each film file lists, for each shot, the sentence index it covers. Shot start and end come from `word_timings()`.
* Camera: one continuous slow move per shot (push-in and a small lateral drift), with the start and end scale fixed per shot type. The values are new choices of this design. v3 says only "Camera always drifts" (`three-d.md` line 98).
* Frame rate and canvas size come from the existing render settings in `story_film.py`. The implementation task must name them.
* Narration timing: estimated, not measured speech. Whisper.cpp alignment is Later, only if cuts visibly miss speech.

## 5. Icons

* Icon names checked in `icons/generic.json`:

| Topic-4 noun | Icon | Status |
|---|---|---|
| truck | `truck` | Present |
| loaded truck | `truck-loading` | Present |
| delivery truck | `truck-delivery` | Present |
| returning truck | `truck-return` | Present |
| warehouse | `building-warehouse` | Present. `warehouse` does not exist. |
| factory or site | `building-factory-2` | Present |
| box or parcel | `box`, `package`, `packages`, `container` | Present |
| forklift | `forklift` | Present |
| dock door (open) | `door` | Present |
| dock door (exit) | `door-exit` | Present |
| closed dock | none confirmed | **Open.** Candidates `lock` (present) or `door` with a lock overlay. Choose one. |
| pallet | none | Missing. Substitute `packages`. |
| trailer | none | Missing. Substitute `truck`. |
| route, clock, alert, map pin, archive, ship, anchor | `route`, `clock`, `alert-triangle`, `map-pin`, `archive`, `ship`, `anchor` | Present |

Recolouring: only `generic/*` may be recoloured (v3 `icons.md` line 61, reported). Other vendors are not vendored in slice 1.

## 6. Story (slice 1)

* Cause-first rule for the story authoring step. Line 1 names the setup, not the outcome. Each act has one cause, then one consequence.
* "Concrete fact" means one number, name, or dated event per act. Example: "Warehouse dock 4 has three trucks queued" is concrete. "Logistics is hard" is not.
* Place of the rule: `story_film.py` has no narration writer. The v3 equivalent is `sub-agents/narration-writer.md` (reported, not in this repo). The implementation task names the real file after checking.
* Pass criterion: a named reviewer confirms line 1 is a setup, and each act reads cause, then consequence.

## 7. Verification

| Decision | Check | Method |
|---|---|---|
| D1 | Each vendored file matches its manifest sha256; no unlisted icon is referenced | Manifest check script, run before render |
| D1 | Vendored size recorded | Manifest records 12,176 bytes for the 24 icons |
| D3 | Probe reads the renderer; 3D shots are off on SwiftShader | Probe in the job file; unit test with a faked renderer string |
| D3 | 3D determinism | Render one 3D shot twice, compare per-frame sha256 (only once a GPU renderer exists) |
| D5 | No stock or generated image in the film | Every image file is in the manifest |
| D6 | Shots render and the camera moves | Contact sheet every 2nd frame; scale at first and last frame of each shot |
| D6 | Shot timing matches the sentence index | Unit test on the placement function |
| D8 | Cause-first rule | Named reviewer (section 6) |
| All | Offline and deterministic | Render topic 4 twice; compare output sha256 |
| All | Existing tests still pass | `PYTHONPATH=. .venv/Scripts/python.exe -m unittest discover -s tests -t . -q` |

## 8. Open questions

| # | Question | Recommended answer | Blocks |
|---|---|---|---|
| A | Vendor the icons or fetch them? | **Answered:** vendor. 12,176 bytes for the 24 topic-4 icons. | Done |
| E | Exact Tabler names for truck, warehouse, closed dock? | **Mostly answered:** truck family and `building-warehouse` confirmed. Closed dock has no exact name; pick `lock` or `door` with an overlay. | Closed-dock choice only |
| G | How does the container get the NVIDIA GL/Vulkan driver so Chromium uses the RTX 4060? | Spike: add the NVIDIA ICD and EGL files to the image (matched to the host driver), or use the host toolkit's graphics mount. Record the renderer string. If Chromium still picks SwiftShader, 3D stays off (D3). | 3D shots only |
| H | Remotion or HyperFrames for 3D scenes? | Spike both on one identical 3D test scene and compare output and render time. Do not choose before the spike. | 3D shots only |
| B | Are two shot types enough? | Ship slice 1 with two. Decide after one rendered film. | No |
| D | Timing source | Character estimate now. Whisper alignment Later. | No |
| F | Dark room palette | Later. Light room only in slice 1. | No |

## 9. Process

* Before any dispatch: answer the closing choice for E, decide G's spike scope, and approve this slice 1 (D1, D5 to D9). 3D (D3, D4, D11) stays a separate approval.
* Each implementation step gets a task spec with exact paths, one acceptance command, what must not change, and a tool-call limit.
* Haiku subagents do routine execution. Sonnet plans and reviews. Evidence for each task is a git sha or a finished task id.
