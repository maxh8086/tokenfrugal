# Media-generator: BusinessNext-style film from a text brief (extension brief)

* **Author:** Vaibhav Pavtekar, drafted by EGM brainstorm
* **Date:** 2026-11-05
* **Status:** Draft for approval, nothing dispatched
* **Extends:** [media-generator-film-brief.md](media-generator-film-brief.md) (2026-11-03, decisions 1 to 12 answered). This file does not replace it. Where a point below re-opens an earlier decision, it says so in the "Re-opens" column of section 4.
* **Related:** story-film-visuals.md, handoff-media-motion.md, mode-b-render-spike.md, mode-b-voice-spike.md, mode-b-template-spike.md, `scripts/story_film.py`, `router/tf-roles.yaml` (lines 43-46, 555-580)

## 1. Overview

**What:** a user gives a text brief. The media-generator container returns a finished 1920x1080 film with narration and a music bed, built from HTML scenes rendered by HyperFrames in headless Chromium. No generative video models. The render makes no network calls.

**For whom:** the repo owner and anyone running tokenfrugal who wants a branded explainer without a video editor.

**Core value:** the skill's rules (narration first at 2.70 words per second, measured synthesis, guard checks, duration check, anonymisation by default) become a repeatable command instead of an interactive Claude session.

**Scope line (added because three documents answer related questions):**
* The earlier film brief is the `mgen` / Mode B path: fixed templates, dry narration.
* `scripts/story_film.py` is a second, existing pipeline: it already narrates, mixes a music bed, renders and checks duration.
* The `businessnext-video` skill is the style authority (brand, safe area, guard rules, verification gates).
* This brief decides how the skill's checks and style reach the container, and whether story_film.py and Mode B become one pipeline. Recommendation: one pipeline, with story_film.py as the base (finding F4).

**"Offline" is split into two meanings (finding F1):**
* **Render-time offline (hard rule, testable):** the container runs with `--network none`, downloads no weights, and every web asset is vendored.
* **Authoring-time offline (separate, stricter mode, not required):** all planning and review model calls are local. Haiku and Sonnet are hosted, so authoring with them is not authoring-time offline. Their output is frozen as files (brief JSON, scene spec, `acts.json`) before the container runs. The container never calls a model.

## 2. Analysis (deduplicated findings)

Severity: Blocker, Major, Nit. Lens names are in brackets. 22 findings kept after deduplication.

### Blockers

* **F1. "Offline" has three meanings** (skill: nothing uploaded; earlier brief: `--network none`; earlier decision 6: no hosted model). Haiku authoring or review conflicts with the third. [design, comprehension, structural]
* **F2. Time limits do not fit a render.** Tool calls are capped at 60 s, tasks at 540 s (`router/config.py:110-111`), but `media-motion` and `media-generator` declare `timeout_s: 900` and a two-minute film takes 5 to 8 minutes. The render must be a start-job / poll-status pattern. This belongs in slice 0. [design, codebase-details, implementation-readiness, structural]
* **F3. The question set silently re-opens earlier decisions** 5 (reuse voice image Kokoro, CPU first), 6 (local Qwen VL only) and 9 (templates only in slice 1). Each must be marked re-opened or kept. [structural]
* **F5. The image cannot run the skill's audio chain.** `make_vo.py` and `measure.py` import `kokoro_onnx`; `check_pronunciation.py` and `try_fix.py` import `faster_whisper`. The media-generator image has whisper.cpp, soundfile and numpy only. Kokoro lives in the voice image (`/opt/venv-kokoro`); faster-whisper is in a different venv there. Replacing it with `whisper-cli` is a behaviour change, not a port. [codebase-details, implementation-readiness]
* **F6. Model weights have no checksum.** The voice Dockerfile fetches `kokoro-v1.0.onnx` from a release tag without sha256 and admits it may 404; the `base.en` whisper model has none either. Offline reproducibility cannot be claimed without a lock file. [implementation-readiness]
* **F7. Anonymisation "on by default" is not enforced.** `guard.config.json` and `guard.mjs` ship `bannedTerms: []`; rule R3 prints "skipped" and the guard still exits 0. The guard scans `scenes/*.js` and `index.html` only, so a name in the narration, `acts.json` or alt text passes. [implementation-readiness, design]
* **F8. A 4B model cannot write the skill's scene HTML/JS.** Scenes are hand-built GSAP modules with strict initial-state and duration rules, and 16-32k context cannot hold references plus a scene file. [implementation-readiness, design, zoom-out, codebase-details]

### Majors

* **F4. Duplication with `scripts/story_film.py`.** It already has `narrate` (line 33, `docker run maxh8086/dhvani:latest`), `word_timings` (47), `make_music_bed` (330), `mix_narration` (349), `render_film` (485), `check_duration` (566). Copying the skill's `make_vo.py` and `make_music.py` would build a second pipeline. Note `word_timings` splits by character count, not by measured time; the skill's measurement is better. `_docker_in_work` passes no `--network none`. [codebase-details, zoom-out]
* **F9. "Byte-identical mp4" is not a realistic test.** H.264 encoding is threaded, Chromium frame timing can vary, ONNX float results can change with threads and CPU, and CUDA output can differ from CPU (story-film-visuals V3/V4 shows software versus GPU rendering differs). Auto-enabling CUDA (earlier decision 5) contradicts determinism. [implementation-readiness, comprehension, design]
* **F10. Skill tooling assumes a developer machine.** `model_path.py:10-18` searches `~/.cache/...` and `~/Desktop/*/audio/model` and ignores `KOKORO_MODEL_PATH`. `env.mjs:21-27, 88-105` finds puppeteer-core and the hyperframes CLI by scanning the `_npx` cache, so `hyperframesCli()` throws unless `BNV_HYPERFRAMES` is set. The renderer writes to `~/Desktop/renders/` with a timestamped name. puppeteer-core is not installed explicitly in the image. [codebase-details, implementation-readiness]
* **F11. The earlier brief's acceptance command does not exist.** `mgen` (`pipeline.py:143-147`) takes a clip, `--out`, `--no-music`, `--captions`; there is no `brief` subcommand. `brief` is the separate stub MCP (`router/media_briefing_mcp.py:54-61`, returns "error: not built yet"). Compose sets no `network_mode: none`. Some "slice 0" items are stale: the Dockerfile is clean, digest-pinned (line 4), and `COPY --from=scripts` is served by compose `additional_contexts`. [codebase-details]
* **F12. Word-rate conflict.** Skill 2.70 words/s (`SKILL.md:76`, `retime.mjs:24`); `media_briefing_mcp.py:18-19` uses 3.0; `tf-roles.yaml:563` says "about 3". Moving to 2.70 cuts the 30 s limit from 90 to 81 words, so the docstring, role checklist and tests change together. Earlier decision 10 (per-brief recommender) conflicts with a fixed value in acceptance tests. [codebase-details, design, comprehension]
* **F13. A multi-role split probably does not pay.** Roles run one at a time and cannot chain, so the skill's four sub-agents (art-director, narration-writer, scene-builder, reviewer) mapped to four roles need an orchestrator that does not exist. The deterministic parts (measure, guard, probe, snap, sheet) need no model and should run as one container command. [zoom-out, design]
* **F14. The variation ledger conflicts with templates-only.** The skill's core rule is that two films must differ on at least 5 of 8 axes; fixed templates do the opposite. Port brand, safe area, guard and gates now; defer variation and say so. [zoom-out, comprehension]
* **F16. Brand assets missing.** Skill uses Poppins (woff2 in `templates/project/assets/fonts`) and a mono face (Consolas in guard R1); the image has Inter in `mode-b` and the `fonts.txt` set. Poppins and the mono face need an offline equivalent or guard R1 checks the wrong font. [implementation-readiness, codebase-details]
* **F17. The skill lives in a per-user plugin folder.** The earlier acceptance test greps for `C:\`. The skill must be copied into the repo at a recorded commit/version, not linked. [structural, comprehension]
* **F20. Role and file boundaries are muddled.** `media-generator` (line 43) lists Mode B as "planned"; `media-motion` (line 44) is a stub; decision 2 puts the topic gate in `media-motion`, answer 8 says migrate `media-motion` away. The gate has no home. [structural, comprehension]
* **F22. No stated reason story_film.py output is not enough.** Name concrete deltas (brand fonts and logo, diagram scenes, guard checks) or this may be the wrong problem. [zoom-out]

### Nits

* **F15. Undefined terms:** role, slice (ambiguous across docs), frame review (by eye or by model, gate or advisory), guard R3, seed, "container vs host" (host is the Windows machine running the router), Mode A/B, "third model". [comprehension]
* **F18. Frame review has no baseline.** Run deterministic checks first (guard, tesseract OCR already in the image, pixel safe-area and contrast); a model reviews only what remains. [design, zoom-out]
* **F19. Unpinned inputs.** apt packages (Dockerfile lines 13-14, 42, 50), pip transitive dependencies, and Bonsai/Qwen tags are not hash-pinned, so "a second machine matches" cannot pass. [design, implementation-readiness]
* **F21. Document structure.** The earlier brief already holds glossary, tool table, slice plan and acceptance tests. Extend, do not restate. Add "Extended by" at the top of the earlier brief and "Re-opened by Q#" on affected decisions (an edit to that file, not done here). [structural]

## 3. Options for the five questions

### Q1. Slice order: image additions first, or vendored skill tools first?

* **Recommendation:** vendored skill tools first, with the minimum image change they need. Start with slice 0 (reconcile and fix) so time limits and stale claims do not block later slices.
* **First testable slice (slice 1):** vendor `guard.mjs`, `retime.mjs`, `sheet.mjs`, `snap.mjs`, `env.mjs` (with container paths fixed via `BNV_CHROME`, `BNV_HYPERFRAMES`) at a recorded skill version, then run guard and the duration check on the existing `mode-b` template output under `--network none`. No TTS, no new model. It proves vendoring, the offline path and the empty-banned-terms failure.
* **Strongest counter-argument:** the audio chain (F5) is the biggest unknown, so test it first with `mgen film-plan` (validate brief, write narration and `acts.json`, call the voice image, transcribe back, diff words). Implementation-readiness proposed exactly this.
* **Reason:** vendored tools need only paths and pins, are cheap to test, and fail fast on the largest risk class (dev-machine assumptions, F10). Audio is slice 2, and F5 and F6 must be decided before it starts.

### Q2. Where do TTS, measurement, music and render live?

* **Recommendation:** render, guard, snap, sheet, retime and music stay in the media-generator container. TTS stays in the voice image (`maxh8086/voice`), called as a one-shot `docker run --network none` job that writes a WAV into the shared work volume. Orchestration stays on the host (`scripts/story_film.py` or the MCP). Do not add a new host native server. Do not install Kokoro in media-generator.
* **Strongest counter-argument:** install a pinned Kokoro venv in media-generator so the film is one image and one job. This removes the container-to-container hop, but duplicates a large venv and about 0.4 GB (estimate, not measured) of weights.
* **Reason:** the repo already says "Voice stays in the voice image" (Dockerfile line 57), `story_film.py` already makes that call, and a host server breaks portability and the determinism test. CPU is the baseline; CUDA is opt-in and excluded from hash tests (F9). `docker run` from inside a container is not possible, so orchestration stays on the host.

### Q3. Role split

* **Recommendation:** fold `media-motion` into `media-generator` and keep a thin `media-motion` alias for existing tasks (same pattern as the `video-editor` alias, `tf-roles.yaml` line 106). `media-generator` tools: `list_raw`, `list_renders`, `mgen`, `read_file` (4). Add behaviour as `mgen` subcommands (`film-plan`, `film-build`, `film-status`, `film-sheet`) rather than new tools. `voice-artist` and `manim-style` remain read-only lookups (1 tool each). No new scene-builder or reviewer roles.
* **Strongest counter-argument:** separate roles per skill sub-agent give clearer prompts and per-role model choice. This only pays if roles can chain, and they cannot (F13).
* **Reason:** 4 tools is within the 6-tool recommendation; adding `film_start`, `film_status`, `film_review_sheet` as tools would give 7. A start/poll `mgen` pair answers F2. The topic gate stays a rule list on the host and is deferred with Manim.

### Q4. Who writes scene HTML?

* **Recommendation:** slice 1 to 3: nobody. Templates only, filled from a scene-spec JSON. Later, Sonnet writes the scene-spec JSON (one scene per call, under about 4k tokens) that fills about five parameterised templates (title, bullets, stat, quote, close). Haiku subagents run the pipeline and report results, they do not author free HTML. The builder may emit the JSON for one scene at a time only after a test shows it is reliable. Free-form HTML from any model is a later, optional slice that requires guard to pass before render and the HTML saved as an input artifact.
* **Strongest counter-argument:** Haiku (or a code-class model) is cheap and bounded template-guided HTML is within its range, so let it write scenes constrained to `kit.js` primitives with guard feedback and at most two retries (zoom-out's view).
* **Reason:** free HTML breaks the deterministic render unless saved first, risks guard failures (font weight, minimum size, banned terms, safe area) and, from a 4B model, will fail (F8). A JSON spec keeps the render a pure function of a reviewable file, and keeps earlier decision 9 intact.

### Q5. Frame review: Haiku multimodal or ts-qwen3-vl-8b?

* **Recommendation:** make deterministic checks the gate (guard, OCR, pixel safe-area and contrast, duration). Model review is advisory, on `sheet.mjs` contact sheets, not single frames. Use Haiku on the sheet as an authoring-time step only if the user accepts the F1 definition of offline. Use ts-qwen3-vl-8b only after the rule change is written as its own step (open item from the earlier brief).
* **Strongest counter-argument:** earlier decision 6 chose local Qwen VL because Haiku is hosted. A hosted reviewer is simpler to run and likely stronger; a local 8B model adds a memory cost next to the other local models.
* **Deciding test:** build a labelled set of about 20 frame sheets, half with injected faults (text off the safe area, overlap, wrong font, low contrast, a banned term, clipped text), half clean. Score the guard/OCR baseline, Haiku and ts-qwen3-vl-8b on defect recall and false positives. Adopt a model reviewer only if it catches faults the baseline misses, with recall of at least about 80% and at most 1 false positive on 10 clean sheets. If the baseline already catches the same faults, drop the model reviewer.

## 4. Decision ledger against the earlier brief

| Earlier # | Earlier answer | This brief | Effect |
|---|---|---|---|
| 2 | Gate on host `media-motion` | Gate stays on host; role folded into `media-generator` | Refine (F20) |
| 5 | Reuse voice image Kokoro, CPU first, CUDA if detected | Reuse voice image as a one-shot job; CUDA opt-in only | Refine (F9) |
| 6 | Local Qwen VL only | Deterministic gate plus advisory review; Haiku allowed only if offline is render-time (F1) | Re-opens, user decides |
| 8 | Migrate `media-motion` | Fold into `media-generator`, keep alias | Keep |
| 9 | Templates only in slice 1 | Templates in slices 1-3; scene-spec JSON later; free HTML last | Keep, extend |
| 10 | Per-brief rate recommender | Fixed 2.70 for tests; recommender is its own later slice | Refine (F12) |
| 3, 4, 7, 11, 12 | Manim deferred, texlive, user seed, new tag, cleanup | Unchanged | Keep |

## 5. Proposed slices (in order)

| # | Slice | Requires | First acceptance check |
|---|---|---|---|
| 0 | Reconcile: drop stale claims, set rate 2.70 in `media_briefing_mcp.py`, tf-roles text and tests together; start/poll job pattern replacing 900 s calls; add `--network none` to the compose/run path | none | Offline unit tests pass: `PYTHONPATH=. python -m unittest discover -s tests -t . -q`; a render job returns an id in under 60 s |
| 1 | Vendor skill tools at a recorded version; fix `env.mjs`/`model_path.py` for the container; `models.lock` with sha256 for weights; guard fails when anonymise is on and the term list is empty | 0 | `docker run --rm --network none <image> node tools/guard.mjs` exits 0 on a fixture with terms, and exits non-zero with an empty list; duration check on a `mode-b` render is within 0.1 s |
| 2 | Audio: `mgen film-plan <brief.json>`; schema validation, narration scan by guard, voice-image TTS, measured durations, whisper-cli round trip | 1; F5/F6 decided | Fixture brief gives `PROBLEMS: 0`; `narration.json` and `acts.json` sha256 match `expected.sha256`; `vo.wav` duration within 0.05 s of expected; build runs `sha256sum -c models.lock` |
| 3 | End to end with templates: scene-spec JSON fills ~5 templates, music bed from `story_film.py`, mux, duration check | 2 | 30-second fixture film renders under `--network none`; duration within 5% of narration; intermediate files byte-identical on two runs; five frames hash-equal or SSIM above 0.99 |
| 4 | Frame review test (labelled set) and decision | 3 | Score table for baseline, Haiku, Qwen VL written to `docs/designs/`; no model chosen before it exists |
| 5 | Scene-spec authoring by Sonnet (one scene per call) | 3 | 10 briefs yield valid JSON that passes guard with at most 2 retries |
| 6 | Optional: free HTML authoring, brand variation ledger, Manim path | 4, 5 | Separate brief |

Determinism wording to adopt: byte-identical applies to `acts.json`, `narration.json`, scene HTML and the narration WAV on CPU with `--threads 1` and `OMP_NUM_THREADS=1`. The mp4 is checked by duration and frame hashes.

## 6. Goals and non-goals

**Goals**
* Text brief to a branded 1920x1080 film with narration and music, rendering under `--network none`.
* Skill's guard, measurement and duration checks run in the container from a pinned, repo-local copy.
* Anonymisation enforced, not just configured.
* One pipeline for `mgen`/Mode B and `story_film.py`.

**Non-goals (this brief)**
* Generative video or image models.
* The variation ledger and multiple formats (deferred, stated plainly).
* Manim, texlive, the topic gate.
* Free-form model-written HTML (slice 6, optional).
* 3D / GPU shots (story-film-visuals).
* Authoring-time offline as a requirement.

## 7. Open risks and decisions needed before any dispatch

**Decisions for the user**
1. Define "offline" as render-time only, or require local authoring too (F1). This decides whether Haiku may review frames or author anything.
2. Confirm the single-pipeline direction: `story_film.py` as base, Mode B and the `media-briefing` stub folded in (F4, F20).
3. TTS route: voice-image one-shot job (recommended) or a pinned Kokoro venv in media-generator (F5).
4. Accept the determinism definition in section 5 (F9).
5. Anonymisation: who supplies the banned-term list, and whether a run with an empty list fails or needs an explicit `--allow-no-terms` (F7).
6. Offline equivalents for Poppins and the mono face, or keep Inter and relax guard R1 (F16).
7. Name three concrete deltas over current `story_film.py` output, or reconsider scope (F22).
8. Write the Qwen VL rule change as its own step if Qwen VL is wanted (Q5).

**Risks**
* Chromium frame output may differ across machines; fall back to decoded-frame comparison early.
* Weights URL may 404 (voice Dockerfile admits it); mirror and lock before slice 2.
* Image growth: fonts about 210 MB already; Kokoro adds an estimated 0.4 GB (not measured).
* The earlier brief needs edits ("Extended by", "Re-opened by") that this draft did not make.
* Uncommitted files (`story_film.py`, `model_sync.py`, `video-workflow-containers.md`) may overlap this work.

## 8. Reviewer coverage

| Lens | Result |
|---|---|
| egm-design | Completed. Did not open the skill, Dockerfile or story_film.py; points on them rely on the brief. |
| egm-codebase-details | Completed. Read Dockerfile, compose, story_film.py, MCP files, voice Dockerfile, skill scripts. |
| egm-zoom-out | Completed. Did not open story_film.py or the earlier brief. |
| egm-comprehension | Completed. |
| egm-implementation-readiness | Completed. Did not read pipeline.py or story_film.py in full; two points are marked inference by the lens. |
| egm-structural | Completed. Did not read the skill or story-film-visuals.md. |
| egm-synthesizer | Not run as a subagent; the caller compiled this document directly. |

No lens failed. The skill's `FORMAT-CHOICE.md` is a per-project artifact, not a file in the skill folder (`references/formats.md` holds the ledger), so it was not read as a file.
