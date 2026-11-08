# Media-generator: text brief to narrated explainer film, offline

Author: Claude (orchestrator), from six Goldfish BRAINSTORM reviews
Date: 2026-11-05
Status: Draft for approval. Nothing dispatched.
Extends: docs/designs/media-generator-film-brief.md
Related: docs/designs/media-generator-businessnext-film.md, docs/designs/media-generator-visuals.md

## 1. Goal and non-goals

**Goal.** From a text brief, produce a narrated 16:9 explainer film (about 60 to 120 s) with
scene graphics, a generated music bed and a loudness-matched mix. Rendering runs with no
network. No generative video model is used.

**Non-goals.**
- No new pipeline. `scripts/story_film.py` already does brief to film (section 2).
- No vendor icons, no brand-licensed fonts (open-source fonts only, see section 2).
- No Remotion (licence, see the chat record). HyperFrames only.
- No vision model in the render or review path (policy allows only the builder and thinker).

## 2. Current state

### 2.1 What exists (reuse, do not duplicate)

| Stage | Where | Status |
|---|---|---|
| Sentence selection, narration | `scripts/story_film.py`: `parse_story`, `_select_sentences`, `narrate`, `word_timings` | Built. Kokoro `am_michael` via the voice image |
| Scene HTML | `story_film.py` `build_scene_html`, `write_index_html`; `scripts/story_visuals.py` shot and glyph generators | Built, deterministic |
| Glyphs | `scripts/glyphs/` (30 SVG) | Built |
| Music bed | `make_music_bed` (code-generated, no samples, no model) | Built |
| Mix and mux | `mix_narration` (music gain 0.15), `LOUDNESS_FILTER` (`loudnorm=I=-16:TP=-1.5:LRA=11`) | Built |
| Duration and motion checks | `check_duration`, `check_scene_motion` | Built |
| Job record | `write_job_json`, `assemble_plan` | Built, but see defects in 2.3 |
| Banned-term guard | `tools/guard.mjs` in `Benchmark/video-test-v3/` (per-film copy, R3 with `guard.config.json`) | Not wired into `story_film.py` |
| Role entry | `media-motion` in `router/tf-roles.yaml` (line 44), tools `brief`, `read_file`; `brief` is a stub in `router/media_briefing_mcp.py` | Stub |
| MCP tools | `router/media_generator_mcp.py`: `list_raw`, `list_renders`, `mgen` (Mode A) | Built |

### 2.2 Environment facts (corrected by the codebase review)

- numpy and soundfile are already in the media image (`docker/media-generator/Dockerfile` lines 64-67).
- Kokoro is not in the media image. It lives in the voice image `maxh8086/dhvani:latest` (`docker/voice/Dockerfile` lines 31-48, weights baked at build). The build needs network; running does not.
- Fonts: `fonts.lock` lists 59 open-source packages. Brand-licensed fonts are absent.
- `FORMAT-CHOICE.md` does not exist anywhere in the repo. It is a per-project artifact and has no schema yet.
- Word rate: `WORDS_PER_MINUTE = 162` in `story_film.py` (line 946), which is 2.70 words per second. `tf-roles.yaml` line 563 still says "about 3 words per second". Fix the text.

### 2.3 Defects found in the existing code

1. `story_film.py` writes `render_exit_codes` as literal 0s (around line 1157). `job.json` reports success regardless of the real exit codes.
2. `render_film` truncates stderr to 400 characters (lines 851-855). A failed run cannot be diagnosed from the file.
3. `mux_film` hardcodes the loudnorm literal (lines 876, 909) instead of `LOUDNESS_FILTER`.
4. The banned-term guard is not called. `job.json` says "not run: no guard config in repo". Guard with an empty `bannedTerms` prints "skipped" and exits 0.
5. `mgen` Mode A (clip to captioned short) shares `media_generator_mcp.py` with any new film subcommand. Its argv and output must not change.

### 2.4 Locked (must not change)

- `narrate()` voice and speed; `word_timings()`.
- `LOUDNESS_FILTER`; `make_music_bed()`; `mix_narration()` gain 0.15.
- `check_duration()` output fields; `write_job_json()` field names (add fields only).
- Baseline to match: -16.4 LUFS, about 2.2 words per second in span, 59.9 s for the 60 s topic.
- `mgen` Mode A argv and output.

### 2.5 Decision ledger against the earlier brief

Earlier brief decisions 5, 6 and 9 are re-opened by this design. The earlier brief has not been edited yet. Decisions 5, 6 and 9 are re-decided in section 3 (Q2, Q4, Q5). Decision 1 (HyperFrames) stands.

## 3. Options and decisions

Each question has one canonical home here. Other sections point back to it.

### Q1. Slice order

**Recommendation:** plan-and-defects first, then new stages. Order: slice 0, 1, 2, 3, 4 (section 4).

- Counter-argument: start with the audio path, which is the largest unknown. Rejected. Fixing the defects in 2.3 is cheaper, and it makes every later render honest.

### Q2. Where TTS, measurement, music and render live

**Recommendation:** split by runtime, with the host orchestrating.
- TTS: the voice image `maxh8086/dhvani:latest`, one-shot job, run from the host. It writes WAV files to a shared volume.
- Measurement, music, mix, scene render, mux, checks: inside `maxh8086/media-generator`, which is already where `assemble_plan` runs.
- Orchestration: host (`story_film.py run`, or the MCP tool later).

- Counter-argument: put Kokoro into the media image so there is one container. Rejected. It duplicates the model and onnxruntime, and the voice image already exists.
- Counter-argument: a host native server for TTS. Rejected. It adds a second runtime and breaks portability.

### Q3. Role split

**Recommendation:** no new role. Keep `media-motion` as the single entry for brief-to-film. Its `brief` tool calls `python -m scripts.story_film run`. Keep `media-generator` with four tools (`list_raw`, `list_renders`, `mgen`, `read_file`). Keep `voice-artist` and `manim-style` as one-tool lookups for now.

- Counter-argument: fold `media-motion` into `media-generator` as subcommands. Deferred. It breaks existing task references. If chosen later, keep an alias for one release.
- The full tool list lives here only. `tf-roles.yaml` is updated in slice 0.

### Q4. Who writes scene HTML

**Recommendation:** deterministic code only. `story_visuals.py` and `story_film.py` generate the HTML. Geometry is fixed (1920x1080, caption zone y760 to 1000, divider y740), and `lint` and `check_scene_motion` depend on it. No model writes HTML in slices 0 to 4.

- Counter-argument: a Sonnet-written scene-spec JSON, later. Deferred to slice 5, open question 3.
- Rejected: the 4B builder writing scenes. Its 16k to 32k context cannot hold the references and the scene file.

### Q5. Frame review

**Recommendation:** deterministic checks are the gate. A contact sheet is the human glance.
- Gate checks: duration, `check_scene_motion`, banned-term guard (wired), OCR with tesseract (in the image), safe area and contrast from pixels.
- Advisory: the orchestrator (Claude) reviews the contact sheet. No vision model.
- Test: seed known defects (a banned term, a caption past y760, a blank frame) into a copy of a passing film. The deterministic checks must flag all of them, with zero false positives on the clean film. If they miss any, the orchestrator review is required for that defect type.
- Policy: `ts-qwen3-vl-8b` needs a CLAUDE.md rule change first. Not in this design.

## 4. Proposed slices

A slice is one shippable step with one acceptance check.

| Slice | Content | Acceptance | Tool-call limit |
|---|---|---|---|
| **0 (first testable)** | Fix `tf-roles.yaml` line 563 to 2.70 words per second. Align `media_briefing_mcp.py` rate and its tests in one commit. Version the rate in the brief schema. | `PYTHONPATH=. python -m unittest discover -s tests -t . -q` exits 0. grep finds no "about 3" in media-motion or media-generator lines. | 8 |
| **1** | Fix defects 2.3 (1) to (4): real exit codes in `job.json`, full stderr log in the out folder, loudnorm from `LOUDNESS_FILTER`. Wire the banned-term guard as a pure-Python word list in `assemble_plan`. Fail closed on an empty term list unless `--allow-no-terms` is passed. Failures write RUN_FAILED. | Unit tests for each. A fixture with a banned term fails the run. An empty term list fails without the flag. | 12 |
| **2** | Measured narration: the host calls the voice image once per line and reads each duration from the output WAV. Add `models.lock` (weights and sha256). | `measure` run on the fixture. Narration rate within 0.1 words per second of 2.70. | 12 |
| **3** | Run `story_film.py run` end to end on one existing story (`Benchmark/video-test/` inputs). Check the job file. Expose the existing path through `media-motion` `brief` (replacing the stub). Keep `mgen` Mode A unchanged, with a regression test. | Duration 59.9 s +/- 0.05. Loudness -16.4 LUFS +/- 0.3 LU. Motion check passes. Mode A regression test passes. | 12 |
| **4** | Deterministic frame gate (2.3 and section 3 Q5): OCR, safe area, contrast, seeded-defect test. Contact sheet for the orchestrator review. | Seeded-defect test: all defects flagged, zero false positives on the clean film. | 12 |
| 5 (later, open) | Scene-spec JSON written by Sonnet, one scene per call. | Open question 3. | - |

Starting slice: **slice 0**. Nothing else starts before the user approves this doc.

## 5. Role split

| Role | Change | Tools |
|---|---|---|
| `media-motion` | Keep. Replace the `brief` stub with a call to `story_film.py run`. | `brief`, `read_file` |
| `media-generator` | Remove the "planned Mode B" wording (`tf-roles.yaml` line 43). | `list_raw`, `list_renders`, `mgen`, `read_file` (4) |
| `voice-artist` | Keep as a one-tool lookup. The pattern `voice-artist-<name>.md` has no files yet, only `voice-artist-profile.md`. | `read_file` (1) |
| `manim-style` | Keep as a one-tool lookup, or drop. Open question 2. | `read_file` (1) |

Policy check: models stay `builder` and `thinker`. Tool counts stay within 6 recommended and 12 maximum.

## 6. Verification

One place for all checks.

- **Unit:** `PYTHONPATH=. python -m unittest discover -s tests -t . -q` exits 0 after every slice.
- **Determinism:** the render is not byte-identical (threaded H.264, Chromium timing). Determinism is checked by hashes: `acts.json`, narration WAVs, scene files, and per-frame hashes of the mp4. Run the render twice on the same image and compare.
- **Duration:** 59.9 s +/- 0.05 s. Check with `ffprobe` on the encoded file.
- **Loudness:** -16.4 LUFS +/- 0.3 LU, measured with `loudnorm=print_format=summary`.
- **Narration rate:** 2.70 words per second, within 0.1, measured from the WAV.
- **Guard:** runs on every render. Empty term list fails the run.
- **Frame gate:** seeded-defect test (section 3 Q5).
- **Container:** render jobs run with `network_mode: none` (`docker compose config` shows it).

## 7. Open questions (user decisions only)

1. **"Entirely offline" scope.** Render time is offline (`--network none`). Authoring time may use hosted Haiku or Sonnet, if their outputs are frozen to files before render. Confirm this reading, or require authoring to be offline too (which rules out hosted models for scene specs).
2. **`manim-style` and `voice-artist`.** Keep as lookups, or drop until a second style or voice exists?
3. **Scene-spec JSON (slice 5).** Write it with Sonnet later, or never?
4. **`FORMAT-CHOICE.md`.** Where does it live (per project, under `docs/` or the film folder) and what is its schema? It does not exist in the repo.
5. **Banned-term source.** Where does `bannedTerms` come from for a film? The repo has no `guard.config.json`.
6. **Skill source.** `guard.mjs`, `retime`, `sheet` and `measure` come from the businessnext-video skill, which is not in this repo. Which version is vendored?
7. **Chromium and TTS weights.** Pin Chromium apt version and add checksums for the Kokoro and whisper weights (needed before slice 2).
8. **Image tag.** `maxh8086/media-generator:1` is mutable and has uncommitted Dockerfile edits. Cut `:2` for the film slices and keep `:1` buildable?
9. **Word-rate change (slice 0).** It cuts the 30 s brief limit from 90 to 81 words. Accept?

## 8. Risks

- **Mode A regression.** `mgen <clip>` shares the MCP file. Mitigated by the regression test in slice 3.
- **Silent failure.** Current `job.json` reports success regardless. Fixed in slice 1.
- **Brief breakage.** Word-rate change breaks existing briefs and tests silently. Mitigated by changing code, role text and tests in one commit, and by versioning the rate.
- **Task timeout.** Tasks are capped at 540 s, and a 2-minute film takes 5 to 8 minutes. Roles declare 900 s. Mitigation: start and poll render jobs, returning an id in under 60 s. The file for this pattern is not yet located.
- **Token cost.** Cost scales with scenes and sheets. Cap retries at 2 per scene and set a sheet budget per film.
- **Byte-identical output is not achievable.** Hashes per section 6 instead.
- **Unpinned dependencies.** Chromium, apt, and the Kokoro and whisper weights. Fixed in slice 2 (`models.lock`) and open question 7.
- **Re-opened decisions.** Earlier brief decisions 5, 6 and 9 (section 2.5). The earlier brief needs an edit after approval.
- **Observability.** No per-stage timing or run id in `job.json`. Add both in slice 1 so a failed film can be triaged from the file alone.
- **Model-free review limits.** Deterministic checks may miss visual problems (layout balance). Covered by the orchestrator contact-sheet review, not by a model.
