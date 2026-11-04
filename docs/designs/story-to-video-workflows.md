# Story to video: one workflow through media-generation

* **Status:** plan for approval. Nothing here has been built or run.
* **Date:** 2026-11-04
* **Related:** [story-model-test-plan.md](story-model-test-plan.md) (story test), [story-criteria-gap-analysis.md](story-criteria-gap-analysis.md) (destinations, section 10), `Benchmark/story-test/run_stories.py`, `docker/media-generator/Dockerfile`
* **Reference:** the businessnext-video skill (`references/formats.md`, `narration.md`, `audio.md`, `design-system.md`, `architecture.md`, `build-and-verify.md`)

## 1. What stays the same

The story flow is unchanged:

1. A destination is confirmed first (`--destination`: youtube-shorts, instagram-reels, facebook-reels, linkedin, long-form).
2. Each destination gets one topic, in a seeded assignment.
3. Nine models run story, critic, anti-AI and humanizer passes.
4. Stories are rated blind by Haiku and Sonnet and ranked per destination.

The ranked stories are the input to the video step.

## 2. What changes

There is one video workflow, and it runs only inside the media-generation container (`docker/media-generator`). The ComfyUI and Kalamanch workflows from the earlier draft are dropped. The container follows the businessnext-video procedure:

| Step | Businessnext procedure | Media-generator implementation |
|---|---|---|
| Format | `FORMAT-CHOICE.md`: score the film against the last one on eight axes, at least five must differ | Same file, written per job. Stops every video looking the same. |
| Narration first | 2.70 words per second. Word budget = runtime x 2.70 (about 162 words per minute). Measure each line, never estimate. | Word budget from the destination range (story-criteria section 10). Measure with a TTS engine. |
| Narration voice | Kokoro via `audio/measure.py` | Kokoro, run inside the container. Not yet in the image. |
| Music | Procedural bed in one of five moods, or a supplied track, ducked under narration | Same. Deterministic output (fixed seed). |
| Visuals | HTML scenes rendered by HyperFrames in headless Chrome | Same. Chromium and HyperFrames are already in the image. |
| Verify | `guard.mjs` (banned terms, font rules), `hyperframes lint`, frame sheet, duration check | Same gates. Frame review by Haiku multimodal (see section 5). |
| Output | 1920x1080 branded film (16:9) or vertical (9:16) per destination | `Benchmark/video-test/<destination>/<model>/topic-N/` |

The rules from the businessnext skill are kept as written: mono font weight 400 or 700 only, nothing under 18px, no colour tweens, no clocks, randomness or network at render time, and timing set only by `acts.json`.

## 3. Input contract

Each video job takes one ranked story:

* `script.txt`: the story text, one sentence per line.
* `destination`: sets aspect ratio and caption style (9:16 for Shorts, Instagram and Facebook Reels; 16:9 for LinkedIn and long-form, to be confirmed).
* `seed`: fixed per job, so re-runs match.
* `minutes`: target runtime. Word budget = minutes x 162. The one-minute test uses 162 words.
* `format`: the `FORMAT-CHOICE.md` entry chosen for this job.

## 4. Shared rules

* **GPU lease.** Story runs use Ollama on the GPU. `router/gpu_lease.py` already blocks Ollama while ComfyUI holds the lease. This workflow does not use ComfyUI. Run the stories first, then the video jobs. Never run two GPU jobs at once.
* **Each job writes `job.json`** with the destination, model tag (for the story), format name, seed, runtime, scene count, wall-clock time and GPU use. The same metadata goes into the video ranking CSV.
* **Stop rule.** A failed job stops the run and writes `RUN_FAILED-video.md`, as the story runner does.
* **Duration check.** Verify the encoded output against the intended runtime. A render that silently drops scenes must fail the job.
* **Portability.** No hardcoded paths. The container image is pinned. Setup steps are written in section 7 before any build.

## 5. Ranking the videos

The Part 2 video rubric (100 points, plan section 4) is scored on the rendered films. Its AI-motion and emotional-TTS items are adapted to a HyperFrames render, which has no AI motion or emotional TTS. Before any ranking, the rubric items must be written out in full. The current plan lists Part 2 by name only, so the items are not yet defined.

Frame review uses frame sheets of 2 frames per second, reviewed by Haiku multimodal (the `UI/UX Vision` tier in the fleet matrix). A test to choose between Haiku and `ts-qwen3-vl-8b` is a later step, and it needs a rule change to allow the local vision model. Ranking is the mean of the two raters' totals per destination.

## 6. Gaps in the media-generator image

Checked against `docker/media-generator/Dockerfile` on 2026-11-04:

* **Present:** ffmpeg, whisper.cpp, HyperFrames/Remotion, Chromium, Manim, tesseract.
* **Missing:** a TTS engine (Kokoro), numpy and soundfile (for measurement and the procedural music bed), and brand fonts.
* `yt-dlp` was removed from the image on 2026-11-04 and is not rebuilt.

Adding these is a change to the image, so it needs your approval before it is built. Each addition is pinned to a version.

## 7. Decisions (approved 2026-11-04)

1. **Single workflow approved.** Name: **`story-film`**. The ComfyUI and Kalamanch workflows are dropped from this workflow only. They stay in the project.
2. **Aspect ratio approved:** 9:16 for Shorts, Instagram and Facebook Reels; 16:9 for LinkedIn and long-form. Both are needed.
3. **Slice 1 (branch `claude/upbeat-chebyshev-ebfc37`)** is the tracking and PR base for this work. It is not paused.
4. **Image additions approved** (section 6): Kokoro, numpy, soundfile and brand fonts, each pinned. ComfyUI may be used where the existing tools are not enough.
   * **Voice decision (2026-11-04, from the owner):** voice uses the existing voice image, `maxh8086/voice:1` (built from `docker/voice/Dockerfile`, Kokoro-onnx with the model files baked in). Voice is not added to media-generator. This replaces slice-1 D1a (host voice) for the story-film workflow. The container reads `narration.wav` from the shared media folder, as D1a already describes. Media-generator gets only the non-voice packages it still needs: soundfile (numpy is already present) and the brand fonts.
   * **Still open:** the voice image is referenced by tag `:1`, not a digest. Pin it by digest before the first run. The brand font list is not yet named.
5. **Docker repair approved.** Fix the "Inference manager" error so the media-generator image builds.

## 8. Next steps

1. Fix Docker and confirm it runs.
2. Add the approved dependencies to `docker/media-generator`, pinned, and build the image.
3. Write the Part 2 rubric items (section 5).
4. Write the `story-film` setup section and a single-story smoke test. No batch run and no GPU run before approval of the model and topic lists.
