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

The Part 2 video rubric (100 points, plan section 4) is scored on the rendered films. Its AI-motion and emotional-TTS items are adapted to a HyperFrames render, which has no AI motion or emotional TTS. Before any ranking, the rubric items must be written out in full. The source criteria are recorded in 5.1 below. The scored rubric (Part 1 and Part 2, 100 points each) is `Benchmark/story-test/ratings/VIDEO_RUBRIC.md`.

### 5.1 Source criteria and render mapping (from the owner, 2026-11-04)

The owner's table gives story and video criteria for five destinations. This section covers the video column only. The story column is not re-checked against Part 1 here.

| Destination | Video criterion (source) | Render mapping (HyperFrames, offline) |
|---|---|---|
| YouTube Shorts | Visual change every 2–3 s, no dead air | Feasible: scene cuts timed in `acts.json` |
| YouTube Shorts | High-emotion TTS (panicked, whispering) | Not available: Kokoro has no emotion control. Pace and pauses only. Conflicts with the calm narration in `ai-short-style`. |
| YouTube Shorts | Heavy SFX on every cut | Partial: procedural synthesised ticks only, no sound library |
| YouTube Shorts | Kinetic word-by-word bouncing captions | Feasible in HTML, but needs word timings. Kokoro gives none; whisper.cpp (in the image) would supply them. |
| Instagram / FB Reels | Massive text hook in the first 0–1 s | Feasible |
| Instagram Reels | Trending platform audio at 1–5% under TTS | Not feasible offline: no licensed trending audio. Excluded. |
| Facebook Reels | Hold visual clips 3–4 s | Feasible |
| LinkedIn | Documentary polish, no generic "AI slop" look | Subjective. Scored by the frame review (section 5). |
| LinkedIn | Clean block captions, not bouncing words | Feasible |
| LinkedIn | Calm, documentary-style voice | Feasible with Kokoro at a slow pace |
| Long-form | Shots hold 5–15 s with subtle ambient motion | Feasible: slow push-in and procedural room tone |
| Long-form | Character (`--cref`) and style (`--sref`) references | Not applicable: these are Midjourney parameters and no image model runs in the render. Replace with one fixed palette and character cards in HTML. |
| Long-form | Continuous emotionally mapped score | Partial: procedural bed in five moods |

Items marked "Not feasible", "Not available" or "Not applicable" need a decision before scoring: drop them, or replace them with a render-side equivalent. Until that decision, they are not scored.

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
   * **Voice decision (2026-11-04, from the owner):** voice uses the existing voice image, `maxh8086/dhvani:latest` (built from `docker/voice/Dockerfile`, Kokoro-onnx with the model files baked in). Voice is not added to media-generator. This replaces slice-1 D1a (host voice) for the story-film workflow. The container reads `narration.wav` from the shared media folder, as D1a already describes. Media-generator gets only the non-voice packages it still needs: soundfile (numpy is already present) and the brand fonts.
   * **Voice label policy (2026-11-04, from the owner):** the pin follows the `latest` label, not a version number or a fixed digest. Each new voice build gets a version label (`:2`, `:3`, ...) and the `latest` label. `docker/voice/voice.pin` holds `follows=latest` and the digest that `latest` points to. Current state: `maxh8086/dhvani:latest` and `maxh8086/dhvani:latest` both point to digest `86fa8c5b…`; the pin was moved to it with `scripts/update_voice_pin.py --write`. Registry push is not done (needs approval).
   * **Brand fonts (2026-11-04):** the font set is open source Debian packages listed in `docker/media-generator/fonts.txt` (see the file's header for scope and licences). Built into `maxh8086/media-generator:1`: 1135 font files present.
   * **Sound files: none needed.** The media-generator image has no sound library. The music bed is procedural (see section 2), so no sound files are fetched. `docker/media-generator/assets.json` stays empty and `scripts/fetch_media_assets.py` is not used by `story-film`. The only audio files in the image are test samples inside Manim, whisper.cpp and scipy.
5. **Docker repair approved.** Fix the "Inference manager" error so the media-generator image builds.

## 8. Next steps

1. Fix Docker and confirm it runs.
2. Add the approved dependencies to `docker/media-generator`, pinned, and build the image.
3. Write the Part 2 rubric items (section 5).
4. Write the `story-film` setup section and a single-story smoke test. No batch run and no GPU run before approval of the model and topic lists.

## 9. story-film: input, setup and smoke test

### 9.1 Input: the top story per destination

Source: `Benchmark/results/story-ranking-v2-2026-11-04.csv` (rank 1 per destination, `combined` score). Each destination has one topic, so the topic number is fixed by the story test. Story files are at `Benchmark/story-test/outputs-v3/<destination>/<model>/<topic>/story.md`.

| Destination | Format | Rank-1 model | Topic | Combined | Story file |
|---|---|---|---|---|---|
| youtube-shorts | 9:16 | ministral-3-8b | topic-4 | 68.2 | `outputs-v3/youtube-shorts/ministral-3-8b/topic-4/story.md` |
| instagram-reels | 9:16 | qwen3-8-9b-distill | topic-5 | 62.5 | `outputs-v3/instagram-reels/qwen3-8-9b-distill/topic-5/story.md` |
| facebook-reels | 9:16 | nemotron-3-nano-4b | topic-1 | 55.5 | `outputs-v3/facebook-reels/nemotron-3-nano-4b/topic-1/story.md` |
| linkedin | 16:9 | ministral-3-8b | topic-2 | 62.0 | `outputs-v3/linkedin/ministral-3-8b/topic-2/story.md` |
| long-form | 16:9 | ministral-3-8b | topic-3 | 56.2 | `outputs-v3/long-form/ministral-3-8b/topic-3/story.md` |

Each job takes the `story.md` file only, unmodified from the ranking test. The LinkedIn rewrite (hook, business stake, debate question) is not used as input. Any rewrite would be a separate step and a separate ranking. The `anti-ai.md`, `critic.md` and `humanizer.md` files are kept as evidence and are not sent to the video step.

### 9.2 Setup (before any run)

1. Confirm the images: `maxh8086/media-generator:1` (has fonts and soundfile, built 2026-11-04) and `maxh8086/dhvani:latest` (= `:1`, digest `86fa8c5b…`), with `docker/voice/voice.pin` at `follows=latest`.
2. Confirm the offline suite passes: `PYTHONPATH=. .venv/Scripts/python.exe -m unittest discover -s tests -t . -q`.
3. Confirm the GPU lease is free (no ComfyUI running). The story-film step does not use ComfyUI.
4. Put the chosen job list (section 9.1) in the job file for the run. Do not start the run until the user approves the list.

### 9.3 Single-story smoke test

Purpose: prove the chain runs end to end on one story, with no batch.

* **Input:** `youtube-shorts`, `ministral-3-8b`, `topic-4`, `minutes=1` (word budget 162), `format` = the first `FORMAT-CHOICE.md` entry that passes the five-of-eight difference rule against the previous film (none yet, so the first entry).
* **Steps:** measure narration with the voice image and the word budget, build the HTML scenes, run `guard.mjs` and `hyperframes lint`, render at 1080x1920, run the duration check, write `job.json`.
* **Length rule (changed 2026-11-04):** each film narrates the whole story, capped at 60 s of narration (162 words). The duration target is the film's own narration length, not 60 s. A story shorter than 60 s of narration runs as it is. The gate is that the MP4 length is within 5% of the narration length, and the film stays under 90 s (rubric pacing gate). The first smoke run used a 60 s target and came out at 22.3 s because the story has only 52 spoken words; under this rule it passes.
* **Pass:** the output MP4 exists, the duration is within 5% of the narration length and under 90 s, `guard.mjs` reports no banned terms (not run until a guard config exists), and `job.json` lists the seed, format and GPU use.
* **Fail:** stop, write `RUN_FAILED-video.md`, and do not run the other four destinations.
* **Output path:** `Benchmark/video-test/youtube-shorts/ministral-3-8b/topic-4/`.

### 9.4 Open items

* **Part 2 video rubric.** The rubric items are not in this repo. A search of `docs/`, `Benchmark/`, the handoff and the `.claude/plans` folder finds only the references in `story-model-test-plan.md` (section 4) and `story-criteria-gap-analysis.md` (section 10). The user said the rubric was updated with video criteria. The file location must be given before section 5 can be finished.
* **Not yet built:** the story-film scripts and HTML scene templates. This section describes the run, not code that exists.
