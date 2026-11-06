# Mediahouse benchmark and end-to-end test plan

* **Status:** draft for approval. Nothing here has been run.
* **Date:** 2026-11-03
* **Scope:** the ten mediahouse roles, one fictional story, and a stitched end-to-end video with narration and music.

## 1. Goal

Test every mediahouse role with recorded results. Then produce one fictional story film, built only from role output, to test the pipeline end to end.

The fictional story is about a product that lets astronauts drink water in space. The product is priced at $1000. Everything in the story is invented: the product, the company, the characters, and the mission. No real brand, person, or product appears.

Each generated clip is between 30 seconds and 2 minutes long.

## 2. Constraints and decisions already set

| Item | Rule | Source |
|---|---|---|
| Tokenfrugal | Suspension applies to general-purpose tasks only, until end of Wednesday 2026-11-04. Routine execution for general-purpose work goes to Haiku subagents until then. Benchmarking tokenfrugal itself (the role benchmark that runs through dispatch_task) is not suspended. | global CLAUDE.md; owner clarification 2026-11-03 |
| Benchmark writes | No write to the real `benchmark.csv` without owner approval. Mediahouse results go to `Benchmark/results/mediahouse.csv` and raw JSON. | `Benchmark/ADDING_ROLES.md` |
| Clip length | Every generated video: 30 s to 120 s. | owner request |
| Reference video | Style only. No frames, script, music, logos, or narrator voice from the reference are reused or cloned. | owner rule, used in earlier analysis |
| Voices | Voices are designed, preset, or consented. No cloning of a real person without consent. | `docs/designs/mode-b-voice-spike.md`, voice-artist skill |
| Model loading | One container or GPU role runs at a time. Claude starts and stops each container in sequence and records the GPU lease before each start. ComfyUI and voice containers never run together. | owner request 2026-11-03 |

## 3. What already exists

| Role | State today | Gap for this plan |
|---|---|---|
| kalamanch | Pipeline image `maxh8086/kalamanch`, stages: voice, animate, assemble, upscale. Needs the GPU lease. | Image-to-video only from an input image. Not benchmarked. Clip length from earlier runs: about 20 s per segment. |
| content-research, content-factcheck, content-writer, content-editor, content-analyst | Script pipeline roles. Need compose services (crawl4ai, searxng, qdrant, postgres). Services are not running. | Need services up before a live run. |
| media-generator | Mode A (one Raw clip to a captioned 9:16 short) works. Mode B is planned, not built. | Mode B is needed for the story film. |
| media-motion | Slice 1 is a stub. Returns "error: not built yet" for a valid brief. | Must be built and passing its tests before Workstream A or F runs. Narration minimum is 90 words, but this is a floor, not an upper limit (see Workstream F item 2). |
| manim-style | Read-only lookup. Profile file exists: `docs/designs/manim-style-profile.md`. | Live test only. |
| voice-artist | Read-only lookup. No profile file exists. | Create `docs/designs/voice-artist-profile.md` before live testing. |

**Voice used for the earlier media-generator video.** Mode A does not generate a voice. It uses the speaker's own audio from the Raw clip. The Mode B voice spike used Kokoro-82M, voice `af_heart`, at 2.94 words per second. Kokoro is the only voice engine measured so far, and the current voice image is CPU-only. A GPU voice image is needed (see Workstream E item 5).

**Offline tests.** `tests/test_mediahouse_roles.py` has 11 checks. They pass, with one expected failure for the missing voice profile.

## 4. Workstreams

### Workstream A: benchmark and test cases (role level)

Each role gets one live task with a deterministic pass check and n = 3 runs. Every run records the metrics listed in section 4A-metrics below. A run that fails for an infrastructure reason is recorded as `infra`, not as a model failure.

| Role | Test task | Pass check | Infra needed |
|---|---|---|---|
| manim-style | Look up `manim-style` and return the settings table. | Every returned setting appears in `manim-style-profile.md`. | none |
| voice-artist | Look up `default`. | Reports the missing path, invents nothing. | none |
| content-research | Outline a fictional product brief, list claims. | `01-research.md` exists with a claims table. | crawl4ai, searxng |
| content-factcheck | Fact-check the fictional brief. | Claims are marked. Fictional product claims are marked "fiction, no source", not "verified". | crawl4ai, searxng |
| content-writer | Write the story script from the outline (60 s). | Script exists, is 150 to 220 words, and has scene headings. | none (reads files) |
| content-editor | Edit the script for pacing and removes slop. | Edited file exists, word count within 10% of the input. | none |
| content-analyst | Summarise trends for "space hydration products" from public data. | Summary exists and has no invented figures. | qdrant, postgres, searxng |
| media-generator | Mode A on one existing Raw clip. | Render file listed by `list_renders`. | `mgen` container |
| media-motion | Brief for a 30 s film. | Render path returned. Stub returns "not built yet" until slice 1 lands. | media-briefing built |
| kalamanch | One `run_animate` stage on a test image. | Output file path returned and exists. | GPU lease free |

#### Metrics recorded for every run

- Wall-clock seconds, from request to output file written.
- Peak GPU memory (MB) and peak system RAM (MB), sampled during the run.
- Device used (GPU or CPU) and the container image tag and digest.
- Output checks: file exists (yes or no), duration in seconds versus the target, resolution, frame rate, file size in MB, audio present (yes or no).
- Duration error = output duration minus target duration, in seconds.
- Pass or fail against the pass check in the table, plus a failure class: model, infra, or tool.
- Retries used (count).
- Tool calls made by the role (count), and tokens in and out for role runs.
- For voice runs: speech rate in words per second, measured duration against the word count, and integrated loudness in LUFS.
- For video runs: a 1 to 5 human score for identity consistency with the input image, motion quality, and visible artifacts. Mark it as "human, not automatic".
- For story runs: word count, scene count, and whether the price ($1000) and all three character names appear.
- Output: one row per run in the CSV, with a "run_index" column (1 to 3).

Content-factcheck and content-analyst are included because the plan needs them to test the script pipeline. For the fiction, factcheck is run only to confirm that it marks invented claims as unsourced.

Output: `Benchmark/results/mediahouse.csv` with columns in the same style as `team_results.csv`, plus `infra` and `failure` columns. Raw JSON goes in `bench/` under a new tag, `mediahouse`.

### Workstream B: the story and its product (fiction)

1. Product: a fictional drink system for zero-gravity use. Invented name, invented maker, price fixed at $1000.
2. Story: a short arc with three characters. Two astronauts and one ground engineer.
3. Pipeline: `content-writer` writes, `content-editor` edits. `content-research` and `content-factcheck` are skipped for the fiction and this skip is recorded.
4. Output: `story.md` (about 300 words) and a scene list with timing for 4 to 6 scenes. Total length 60 to 90 s.

### Workstream C: character images (multi-angle)

1. Make three characters, each with front, three-quarter, and side views, plus one close-up. That is 12 images.
2. Generation tool is an open decision. No image role exists in the mediahouse team. Options are listed in section 6.
3. Each character gets one fixed style note so the views match.

### Workstream D: image-to-video with Kalamanch, one model at a time

Run each model separately. Use the same input image and the same prompt for every model.

| Step | Model | Input | Clip length | Check |
|---|---|---|---|---|
| D1 | LTX-Video 0.9.8 distilled | one character front view | 30 s | output exists, fps, duration |
| D2 | Wan 2.2 TI2V 5B (Q4_K_M) | same image | 30 s | same |
| D3 | CogVideoX 2B (nimvideo) | same image | 30 s | same |
| D4 | Best of D1 to D3, extended | same image, anchored | 60 to 120 s | chained segments, no cut at joins |

Models run in order, not in parallel. Each run is logged in `scratchpad/queue/queue.log` or its successor, and each run uses the metrics listed in Workstream A.

Old timings from earlier runs are not used. They came from different images and settings. Every model is measured again on the current input images.

### Workstream E: narration and voice

1. `voice-artist` returns the voice settings for each character from profiles in `docs/designs/voice-artist-<name>.md`. Profiles are created first (open decision 3).
2. Narration is generated per line, measured, then placed on the timeline.
3. The voice is generated per character. Speech rate for each voice is measured before the timeline is set. Kokoro measured 2.94 words per second.
4. Narration length is set by the clip length, not by a word cap. For a 120 s clip at the measured Kokoro rate of 2.94 words per second, the script needs about 350 words. The narration tool must accept that length. The old 90-word figure is a minimum requirement and is not an upper limit.
5. Voice engine on GPU. Build a GPU voice image based on docker/voice/Dockerfile. Use the GPU when one is available, and fall back to CPU only when it is not. The device used is recorded in every run (see metrics). The voice-artist role runs against this image.

### Workstream F: media-generator for the video pieces

1. Mode A: one Raw clip to a captioned 9:16 short. Used as a control to test the caption and mux path.
2. Mode B: a text brief to a motion-graphics film. Needs `media-motion` slice 1 built and tested before this workstream starts. The narration limit must support clips up to 120 s (about 350 words at Kokoro's rate), per Workstream E item 4.
3. Each Mode B piece is one scene. Scenes are then stitched by the orchestrator (Workstream G).

### Workstream G: media-editor and orchestrator (after this plan is approved)

This is the work the owner asked to finish after the plan. It is listed here so the plan is complete.

1. Input: a scene list with timing, character clips, narration audio, and music choice per scene.
2. Stitch the scene clips in order, with cross-fades at scene joins.
3. Mix narration and background music. Music is chosen per scene: the scene mood sets the track, and the level drops under narration.
4. Output: one film, 2 to 3 minutes, plus a list of all source files used.
5. Checks: duration of the output equals the sum of the scene durations (within 0.5 s), audio is present in every scene, no clip is shorter than 30 s, and no clip is longer than 2 min.
6. Every clip has a sidecar file that records the voice id, voice engine, image tag, model, seed, and the generation command. This is how each clip can be traced to the voice that made it.

### Workstream H: final end-to-end test

1. Run workstreams B to F in order.
2. The orchestrator stitches the output.
3. A human review of the final film against the story: the three characters appear, the narration matches the story, the music changes by scene, and the product price ($1000) is spoken and shown.
4. Record the result in `Benchmark/results/mediahouse-e2e.md`.

## 5. Schedule

**Sequence, back to back**

1. Media-motion slice 1 built and tests passing (gate for Workstream A and F).
2. GPU voice image built. Voice-artist profiles created with designed voices.
3. Workstream A live benchmark, roles run one container at a time.
4. Story and scene list written (Workstream B).
5. Character images generated with ComfyUI (Workstream C), then ComfyUI stopped.
6. Kalamanch D1, then D2, then D3, one model at a time, each followed by the metrics check.
7. Kalamanch D4 extension of the best model.
8. Narration (E) and Mode B scenes (F).
9. Orchestrator and media-editor (G).
10. End-to-end test (H).

Each stage starts when the previous stage passes its checks. There are no waiting periods between stages.

## 6. Open decisions for you

1. **Character image generator.** There is no image role. Options: (a) ComfyUI through the existing comfy bridge, run in the `tokenfrugal-gpu` compose project; (b) a still image tool outside this repo. Recommended: (a), because the GPU lease already covers it.
2. **Narration voice engine.** Kokoro is measured. Use the GPU when available (see Workstream E item 5). Recommended: Kokoro on GPU for the first slice.
3. **Voice-artist profiles.** Create them now with designed voices (no real person), or wait for consented voices. Recommended: designed voices now.
4. **Fiction and factcheck.** Confirm that factcheck is run only to test its behaviour, and that the story skips real-world verification.
5. **Clip length.** 30 to 120 s per clip is set. Confirm that the 30 s floor applies to each Kalamanch clip, and that the final film may be longer than 2 min.

## 7. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Old Wan 2.2 and CogVideoX timings from earlier runs | Not applicable. Those runs used different images and settings. | Measure every model again on the current images. Do not reuse old timings. |
| media-motion is still a stub | Mode B cannot be tested | Build and test slice 1 before Workstream A or F. This is a gate. |
| Narration limit set too low (90 words) | Clips cannot reach 120 s | 90 words is a floor. The tool accepts about 350 words for a 120 s clip. |
| GPU shared between containers and ComfyUI | Out-of-memory or refused runs | One container at a time. Claude starts and stops each container in sequence and checks the GPU lease first. |
| Unclear which voice made which clip | Cannot trace audio to a voice | New voice image and voice-artist role. Each clip has a sidecar file with voice id and engine. |
| Voice image is CPU only | Slow narration | Build a GPU voice image (see Workstream E item 5). Record the device in every run. |

## 8. Done when

* Every mediahouse role has a live result in `Benchmark/results/mediahouse.csv`, or an infra reason.
* One story, one product, and three characters exist as text, images, and narration.
* Each Kalamanch model has one clip, and the three clips are compared.
* One stitched film of 2 to 3 minutes, with narration and music per scene, is produced and reviewed.
* Every number in the results comes from a file or a log, not from memory.
* Every run in the benchmark has the metrics in section 4 recorded, and each clip has a sidecar file.
