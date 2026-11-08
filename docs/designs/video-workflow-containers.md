# Video workflows: container pipeline and run guide

Status: draft for review (2026-11-05). Checked against the code and files in the repo on 2026-11-05. Covers two pipelines that share the media image:

1. **story-film**: a text story becomes a narrated 9:16 or 16:9 film with a procedural music bed (`scripts/story_film.py`).
2. **Halo ad**: a 30 s product ad built from ComfyUI stills and LTX-Video clips, assembled with ffmpeg. Its driver scripts are not in the repo (they sit in `scratchpad/halo_real/`). The finished MP4 is in the repo.

Model downloads are proposals. None of the replacement models in section 5 is approved for download yet.

## 1. Principles

- Numeric, render and media work runs in a container. The host parses text, starts `docker run`, and reads results.
- Each `docker run` uses `--rm`, so the container exits before the next stage starts.
- Story-film outputs go to `Benchmark/video-test/<destination>/<model>/<topic>/`. The Halo MP4 goes to `Benchmark/video-test/halo-tonic/`.
- The render code in `story_film.py` has no clock, no random calls and no network calls. The music is a fixed sine pair. The `docker run` for assembly does not pass `--network none`, so "no network" is not enforced.

## 2. Images

| Image | Used for | Pin and source |
| --- | --- | --- |
| `maxh8086/media-generator:1` | HyperFrames render, ffmpeg and ffprobe, loudnorm, numpy and soundfile for the music bed and mix | Built from `docker/media-generator/Dockerfile`. Adds soundfile 0.14.0 and brand fonts (`fonts.txt`) in commit `fa8dc34` (2026-11-04). HyperFrames 0.8.223. |
| `maxh8086/dhvani:latest` | Kokoro narration over HTTP (`POST /api/kokoro/speak`, port 8080, compose network only), voice `am_michael` | Digest in `docker/dhvani/dhvani.pin` (`follows=latest`). The compose service builds `tokenfrugal/dhvani:local` from `docker/dhvani`. |
| `tokenfrugal/comfyui:1` | Mage-Flow stills and LTX-Video I2V (Halo) | Compose service in `docker-compose.gpu.yml`, project `tokenfrugal-gpu`. ComfyUI v0.43.2 and the ComfyUI-LTXVideo and ComfyUI-GGUF nodes (`docker/pins.yaml`). |

## 3. story-film pipeline

Input: the `story.md` file. The code reads only that file. The LinkedIn rewrite and the anti-ai, critic and humanizer files are not read. `parse_story()` drops lines that are only a bracketed stage direction, strips `*` and leading or trailing quote marks, and splits sentences.

Stages (`scripts/story_film.py`):

1. **Parse (host, text only):** `parse_story()`.
2. **Select (host):** `_select_sentences()` keeps sentences in order until the word count reaches `162 x minutes`. The last sentence can take the count past the target.
3. **Narrate (one `docker run` per sentence, media image on the compose network):** `narrate()` POSTs the text as JSON to dhvani at `DHVANI_SPEAK_URL` (default `http://dhvani:8080/api/kokoro/speak`) with `curl`, and writes the returned WAV bytes to `tmp/s<i>.wav`. The network is `DHVANI_NETWORK` (default `tokenfrugal_default`).
4. **Plan (host):** writes `tmp/plan.json` with the chosen sentences, format, destination, story path, word count and wav list.
5. **Assemble (media image, one `docker run`):** `python3 /app/scripts/story_film.py assemble /work/tmp/plan.json`, with `STORY_FILM_IN_CONTAINER=1`. The repo is mounted read-only at `/app`. Inside the container it:
   - joins the narration wavs with 0.25 s gaps (`GAP_S`) into `tmp/narration.wav`;
   - writes scene HTML (2 or 3 sentences per scene) and a 3 s end card with a tagline from the last sentence;
   - writes `index.html`, copies GSAP from the image to `vendor/`, runs `hyperframes lint`, then `hyperframes render` to `video.mp4`;
   - writes the music bed (110 Hz and 164.81 Hz sine, 2 s fades) and mixes it under the narration at gain 0.15 into `mixed.wav`;
   - muxes with two `loudnorm` passes (I=-16, TP=-1.5, LRA=11), then `alimiter` (limit 0.80), AAC 192k, and `-shortest`, into `film.mp4`;
   - probes the duration with `ffprobe` and checks it is within 5% of the target (narration plus 3 s);
   - writes `job.json`. On any error it writes `RUN_FAILED-video.md` and exits 1.
6. **Report (host):** prints `OK: <path>` or `RUN_FAILED: <path>`.

What the code checks, and what it does not:

- **Checked in code:** duration within 5% of the target (`check_duration()`).
- **Not checked in code:** the 90 s limit. Nothing in `story_film.py` compares the film length with 90 s. The shortlist films were checked against 90 s by reading `job.json`.
- **Not checked in code:** the -16 LUFS result. The filter sets the target, but the output is not measured after the mux. `job.json` records the target, not a measured value.
- **Fixed values in `job.json`:** `render_exit_codes` are written as 0 for every step, and `guard` says "not run". Do not read these as results.

Shortlist (`SHORTLIST` in `scripts/story_film.py`, run by `shortlist`). Durations are from each run's `job.json`:

| Destination | Format | Model | Topic | Final duration |
| --- | --- | --- | --- | --- |
| youtube-shorts | 9x16 | ministral-3-8b | topic-4 | 25.27 s |
| instagram-reels | 9x16 | qwen3-8-9b-distill | topic-5 | 72.77 s |
| facebook-reels | 9x16 | nemotron-3-nano-4b | topic-1 | 39.57 s |
| linkedin | 16x9 | ministral-3-8b | topic-2 | 59.83 s |
| long-form | 16x9 | ministral-3-8b | topic-3 | 74.97 s |

All five are under 90 s in `job.json`. Other runs exist under `Benchmark/video-test/`. They are not in the shortlist.

### Commands

The CLI is `python -m scripts.story_film` with three subcommands: `run`, `shortlist` and `assemble`. Run `run` and `shortlist` from the repo root on the host. `assemble` runs only inside the media image.

```bash
# one story; --format accepts only 9x16 or 16x9; --destination is free text
.venv/Scripts/python.exe -m scripts.story_film run --story <story.md> --destination youtube-shorts --format 9x16 --out Benchmark/video-test/youtube-shorts/ministral-3-8b/topic-4 --minutes 1.0

# the five shortlist jobs, one after another (paths are fixed in SHORTLIST)
.venv/Scripts/python.exe -m scripts.story_film shortlist
```

`--minutes` defaults to 1.0. `--out` can be any path. The code does not limit it to the mapped folder.

### Output tree

```
Benchmark/video-test/<destination>/<model>/<topic>/
  film.mp4          final narrated film (audio and video)
  mixed.wav         narration plus music bed
  video.mp4         rendered picture, no audio
  index.html        HyperFrames composition
  job.json          facts and checks, or RUN_FAILED-video.md on failure
  tmp/              plan.json, s<i>.wav, narration.wav, music.wav, scene_<k>.html
  vendor/           gsap.min.js copied from the image
```

### Five-criteria gate

The brief calls this the five-criteria gate: the four Part 2 categories of the rubric in `Benchmark/story-test/ratings/VIDEO_RUBRIC.md`, plus the 90 s gate. The rubric attaches the 90 s gate to 2.3, so it is listed on that row.

| Rubric | Category | Max | How it is checked | Status |
| --- | --- | --- | --- | --- |
| 2.1 | Visual polish and professionalism | 30 | Frame review (contact sheets). Use the same reviewer for every film in a run. | Needs frame review |
| 2.2 | Muted viewing accessibility | 25 | Frame review. Bold overlays in the first 3 s; captions clean for silent viewing. | Needs frame review |
| 2.3 | Pacing and dwell time. **Hard gate: under 90 s.** | 25 | Automatic: `final_duration_seconds` in `job.json` must be under 90. Not enforced in code yet. The pacing part is judged from frames. | 90 s gate |
| 2.4 | Audio and tone | 20 | Listen to the film. The voiceover should sound calm and clear. | Needs audio review |

Part 1 of the rubric (script, 100 points) is not part of this gate. Score ties by the Part 2 total, then the Part 1 total.

Open point: the brief says five criteria, and the rubric has four categories with the 90 s gate on 2.3. Confirm whether the gate should be its own fifth row.

## 4. Halo ad pipeline (30 s, 1080x1920, 30 fps, silent)

Result: `Benchmark/video-test/halo-tonic/halo_tonic_30s_silent.mp4` (11.2 MB) is in the repo. The run reported 30.034 s, 1080x1920, 30 fps. The length was not measured again in this review (no `ffprobe` on the host).

The stages below ran from scratchpad code. The driver scripts are not in the repo.

| Stage | Where | Notes |
| --- | --- | --- |
| Six Mage-Flow stills, 768x1344, seed 42 | ComfyUI (GPU), via `stills.py` (host, stdlib `urllib`, scratchpad only) | Outputs are `comfy_data/output/halo_s1` to `halo_s6`. Prompts end with "no readable text, no logos". |
| LTX-Video 0.9.8 2B distilled I2V, 97 frames, 512x896 | ComfyUI (GPU), via `ltx_shots.py` (scratchpad only) | 8 sampler sigmas, cfg 1.0. The KEEP suffix keeps the label blank. |
| Clip trim and scale | media image (`assemble.sh`, scratchpad only) | `trim=end_frame=N`, `scale=1080:1920:lanczos`, `fps=30`. |
| Assembly | media image | Concatenates c01 to c09 and c11. Drops c10 (garbled label). |
| End card | media image | Title and tagline with drawtext. Last frame held 3 s with `tpad`. |

Known faults: LTX label drift late in some clips, and a red-tinted hand flash near 13 s.

Open items:

- **Done:** the final MP4 is copied to `Benchmark/video-test/halo-tonic/`.
- **Open:** move `stills.py` and `ltx_shots.py` into `scripts/halo/` in the repo. They are host-side stdlib HTTP clients. Either run them in a small container or keep them as the only host-side code, and say so.
- **Open:** the assembly script (`assemble.sh`) is not in the repo.
- **Open:** add more seeds per shot so clips can be shuffled.
- **Open:** fix or accept the label drift and the 13 s flash.

## 5. Low-VRAM model candidates (8 GB)

Status labels:

- **On disk**: the file is in `models/`. Size checked in this review.
- **In script**: listed in `scripts/fetch_comfy_models.sh`. Not downloaded by this review.
- **Proposal**: not downloaded, not approved, not tested in ComfyUI.

The fetch script header says "approved low-VRAM set". That conflicts with the owner's rule that downloads are not yet approved. Treat the script as a proposal until the owner says otherwise.

Container paths (`docker-compose.gpu.yml`): `models/video_generation` is mounted at `/models`, and `models/image_generation/comfy-t2i` is mounted at `/image_models`. Paths in `docker/comfyui/extra_model_paths.yaml` are relative to these mounts.

### Text to image (`/image_models`, Mage-Flow and FLUX.2)

| Component | File | Size | Status | Decision |
| --- | --- | --- | --- | --- |
| Mage-Flow int8 transformer | `diffusion_models/mage_flow_int8_convrot.safetensors` | 4.16 GB | On disk, in use | Keep |
| Mage-Flow text encoder, bf16 | `text_encoders/qwen3vl_4b_bf16.safetensors` | 8.88 GB | On disk, in use | Replace after test |
| Mage-Flow text encoder, FP8 | `Qwen/Qwen3-VL-4B-Instruct-FP8`, saved as `text_encoders/qwen3vl-4b-fp8-0000{1,2}.safetensors` | about 6.0 GB | In script, not on disk | Proposal. The bf16 file stays until the FP8 run is verified. |
| FLUX.2 klein transformer, fp8 | `diffusion_models/flux-2-klein-4b-fp8.safetensors` | 4.07 GB | On disk, in script | Keep |
| FLUX.2 klein VAE | `vae/flux2-vae.safetensors` | 168 MB | On disk, in script | Keep |
| FLUX.2 klein text encoder, bf16 Qwen3-4B | `text_encoders/flux2-klein-qwen3-4b-00001.safetensors` | 4.79 GB (shard 1 only) | On disk, shard 2 missing | Replace after test |
| Qwen3-4B text encoder (replaces the FP8 encoder) | `maxh8086/tokenfrugal-qwen3-4b-q4ks`, file `text_encoders/qwen3-4b-Q4_K_S.gguf`, loaded by `CLIPLoaderGGUF` | 2.6 GB | Local copy on disk; the FP8 files were removed 2026-11-05 because they do not render in ComfyUI | Done (ComfyUI load not yet re-tested) |
| SDXL-Turbo GGUF Q8_0 | `OlegSkutte/sdxl-turbo-GGUF`, `diffusion_models/sd_xl_turbo_1.0.q8_0.gguf` | about 4.1 GB | In script, not on disk | Candidate. Needs ComfyUI-GGUF (in the image). See the open questions. |

Rejected: `tlwu/sdxl-turbo-onnxruntime`. ComfyUI cannot load ONNX.

Removed from the script: FLUX.1 schnell GGUF and its T5 and CLIP encoders. The earlier draft listed these. They are not current.

### Image to video (`/models`, LTX-Video)

| Component | File | Size | Status | Decision |
| --- | --- | --- | --- | --- |
| LTX-Video 0.9.8 2B distilled transformer | `ltx-video-2b-distilled/ltxv-2b-0.9.8-distilled.safetensors` | 6.34 GB, bf16 | On disk, in use | Needs a quantized replacement. Undecided. |
| LTX-Video 2B v0.9 GGUF Q8_0 | `ltx-2b-gguf/ltx-video-2b-v0.9-Q8_0.gguf` (city96/LTX-Video-gguf) | not stated | In script, folder empty | Candidate only. This is version 0.9, not 0.9.8. Undecided. |
| LTX-2 19B (transformer, Gemma 3 12B encoder, connectors, VAEs) | `ltx-2-gguf/` | about 24 GB total | Dropped. Not on disk. | Remove the entries from `extra_model_paths.yaml`. |

Config mismatch to fix before any GGUF is used: `docker/comfyui/extra_model_paths.yaml` still lists `ltx-2-gguf/` for `text_encoders`, `diffusion_models` and `vae`. It does not list `ltx-2b-gguf/`, where the script puts the v0.9 GGUF and its VAE. Check in ComfyUI whether the GGUF appears in the model lists. Do not describe LTX-2 as current.

## 6. Review checklist

Ticked only where this review checked the item in a file. Unticked items are open.

- [x] The story-film stages in section 3 match `scripts/story_film.py` (parse, select, narrate, plan, assemble, report).
- [x] Every story-film `docker run` uses `--rm`.
- [x] The `run`, `shortlist` and `assemble` commands and flags match the CLI in `story_film.py`.
- [x] The shortlist table matches `SHORTLIST`, and each entry has a `job.json` under 90 s.
- [x] The Halo MP4 is in `Benchmark/video-test/halo-tonic/`.
- [x] The five-criteria gate matches `VIDEO_RUBRIC.md` (2.1 to 2.4, with the 90 s gate on 2.3).
- [x] The image names and pins match `docker-compose.gpu.yml`, `docker/pins.yaml`, `docker/voice/voice.pin` and the media Dockerfile.
- [ ] The 90 s gate is enforced in code. Not yet.
- [ ] The loudness result is measured after the mux. Not yet.
- [ ] Output paths are limited to the mapped folder. The code accepts any `--out`.
- [ ] Host-side Python is limited to docker plumbing and stdlib HTTP. The Halo drivers are not in the repo, so this cannot be checked.
- [ ] The Halo pipeline runs from repo code. Not yet.
- [ ] Any FP8 or GGUF replacement is downloaded and tested in ComfyUI. None is.

## 7. Open questions

1. Approve the downloads in section 5, or keep them as proposals? The fetch script says "approved", and the files for FP8 Qwen3 and the FLUX.2 encoder shard are partly on disk.
2. Should the 90 s gate be added to `story_film.py` as a hard check that fails the run?
3. Should the five criteria be four rows with the gate on 2.3 (as now), or a separate fifth row?
4. Which LTX-Video quantized model should replace the 0.9.8 bf16 transformer? The script's v0.9 GGUF is a different version.
5. Does the SDXL-Turbo GGUF need the SDXL CLIP encoders and VAE? The script does not fetch them.
6. Remove the `ltx-2-gguf/` entries from `extra_model_paths.yaml`, and add `ltx-2b-gguf/` if the GGUF should appear in ComfyUI?
