# Concept Brief: Mode B for the media-generator role

**Status:** Brainstorm output. Not approved. Needs user sign-off on the open decisions in section 8 before any task is dispatched.
**Reviewed by:** egm-design, egm-codebase-details, egm-zoom-out, egm-comprehension, egm-implementation-readiness, egm-structural (BRAINSTORM mode).
**Scope of checks:** Read-only review of the repo as of 2026-11-02. Licences and VRAM figures were not verified online and are marked unverified.

---

## 1. Summary

Mode B turns a plain-text brief into a narrated, motion-graphics video of 20 to 30 seconds. It is for promotional and faceless content. Mode A (the captioned 9:16 short from a raw clip, currently named mgen) stays unchanged.

The reviewers agree on the core shape but find that the anchored decisions conflict with the current code in four places:

1. The container is not network-disabled in the real compose service. Only a filesystem sidecar is.
2. The media-generator image already ships HyperFrames 0.8.223, Chromium and ffmpeg. The "host renders because the container cannot" premise is weaker than the brief states.
3. The GPU lease holder list is closed. A Mode B holder cannot take the lease without a code change, and kalamanch already holds the GPU in its own run.
4. The existing mgen tool and role require a Raw clip and have a 900 s timeout. A text brief has no clip, and a one-minute run with voice and render may not fit in 900 s.

**Recommended first slice:** a 20 to 30 second, text-in, single-voice (Kokoro-82M on CPU), one-template video, rendered by HyperFrames, with one optional neutral music bed written for this slice (D10). VoxCPM2, the mood picker, style profiles, topic-to-script writing and the 3D acts are deferred until measured.

---

## 2. Goals and non-goals

**Goals (first slice)**
- Text in (a script the user wrote), MP4 out, about 20 to 30 seconds.
- Neutral visual style with one built-in default palette and font.
- Narration from a local voice engine, with a fixed preset voice.
- Deterministic-enough runs: same inputs produce a manifest that explains any difference.
- Mode A behaviour and tests unchanged.

**Non-goals (first slice)**
- No BusinessNext brand, voice, assets or sting. The businessnext-video-v3 skill is a method reference only.
- No voice cloning.
- No talking avatar.
- No topic-only input (the system writing the script) until the approval step exists.
- No 3D (Three.js) acts.
- No Voicebox.
- No mood dropdown in slice 1.
- No change to the Kalamanch pipeline.

**Deferred (after a measured spike)**
- VoxCPM2 as an opt-in engine.
- Mood picker and music choice.
- Style profile (palette, font, sting).
- Topic-to-script drafting, with a script approval gate.
- Full one-minute target.

---

## 3. Component boundaries

| Component | Where it runs | Responsibility | Crosses boundary as |
| --- | --- | --- | --- |
| Brief intake | Router (tf-roles / new MCP tool) | Validate the brief, create run folder, write run manifest | `brief.json` |
| Narration | Host (decision D1a) | Text to WAV, fixed voice; writes into the mapped media folder | `narration.wav` |
| Music bed | Container (`make_score.py`) for slice 1 | Optional bed, no mood | `bed.wav` |
| Scene build | Container or host (see D1) | HTML/CSS scenes on a timeline | `scenes/*.html` |
| Render | Container (already has HyperFrames and Chromium) or host | Frames to video | `video_raw.mp4` |
| Mux and encode | Container | Mix audio, final encode, captions if used | `Render/<name>.mp4` |
| Verify | Router or container | ffprobe checks, manifest hashes | `manifest.json` |

**Concern:** the brief says "host renders, container does file steps". The image already contains the render stack (see section 5). The team must decide where each step runs and record it (D1).

---

## 4. Interfaces and contracts

**Tool and role.** Mode B should not reuse `mgen`. The reviewers agree on this:
- `mgen` requires the clip to exist in `Raw` (`router/media_generator_mcp.py:63`).
- It finds its output by diffing the Render listing (`:79-80`), so a text run has no clip to name.
- The role `media-generator` has `required_tool: list_raw` and `timeout_s: 900` (`router/tf-roles.yaml:43`). Adding tools also breaks the exact-tool-set assertion in `tests/test_preflight.py:135`.

Proposed: one new MCP tool, `media-briefing`, with the same return convention as `mgen` (`exit=N` or `error: ...`). The tool is `media-briefing`; the role is `media-motion`. Two options for the role (D3):
- **Option 1:** a separate role, `media-motion`, with its own contract and timeout. Mode A is untouched. Recommended by the design and codebase reviewers.
- **Option 2:** a mode of `media-generator` with one new tool and a test update. Cheaper, but it changes the contract that Mode A depends on.

**Brief schema (draft):**
- `text` (script), required. Max 90 words. Basis: 30 s at 2.5 words per second is 75 words, plus margin. The spike confirms the rate.
- `music`, boolean. `true` adds the bed from `make_score.py`; `false` gives narration only.
- `length_target_s`, default 25. Tolerance: plus or minus 1.0 s (placeholder, set from the spike).
- Constants, not inputs in slice 1: language `en`, engine `kokoro`, one preset voice, style `neutral`. The manifest records them.
- `out_name`, which must pass the existing `_check()` name validation.

**Outputs:** `Render/<out_name>.mp4`, and `Render/<out_name>.manifest.json` beside it.

**Manifest fields:** run id, brief hash, script hash, engine name and version, weight sha256 and source revision, engine seed support (record "seed not supported" if Kokoro has none), HyperFrames version (0.8.223 pinned), Chromium version, ffmpeg version, font file and hash, palette, music source and hash, per-stage timings, output duration, audio stream info, frame count.

**Run state.** Defined by the stage table in section 12 and the run's `status.json`. No separate run-state list here.

**Call shape.** Slice 1 is one synchronous call. The 900 s limit (`router/tf-roles.yaml:43`) must cover a 20 to 30 s run, which the spike checks. Add a run id and polling only if the spike measures a run over about 600 s.

---

## 5. Facts checked against the repo (corrections to the brief)

| Brief says | Repo says | Source |
| --- | --- | --- |
| Container has networking disabled | Compose service `media-generator` sets no network setting. `disableNetwork: true` is only on the filesystem sidecar | `docker-compose.yml:22-33`, `profiles/media-generator.yaml:23` |
| Container is CPU-only, file steps only | Image installs HyperFrames 0.8.223, Node 22, Chromium, ffmpeg, tesseract; `make_score.py` is present | `docker/media-generator/Dockerfile:10, :15, :26, :29-37, :57, :71-72`; `pipeline.py:202` |
| Host lacks ffmpeg, soundfile, HyperFrames, Chrome | Accurate for the host | `handoff.md:616` |
| Image pinned on Docker Hub | Pinned by digest, still named `maxh8086/video-editor` | `docker-compose.yml:27` |
| Lease is taken by the voice step | Holders are closed to `comfyui` and `kalamanch`. Other names raise `ValueError` | `router/gpu_lease.py:38, :336-337` |
| Nothing else holds the GPU for kalamanch | `kalamanch/run.py` takes the lease as `kalamanch` and releases in a finally block | `kalamanch/run.py:37, :54` |
| Mode A is a 9:16 captioned short | Requires a Raw clip; role timeout 900 s | `router/tf-roles.yaml:43`, `router/media_generator_mcp.py:15, :63` |
| Workspace folders exist for Mode B | No Mode B folder; `LAYOUT` is asserted by a test | `router/media_workspace.py:15`, `tests/test_media_workspace.py:63` |
| Business Next skill exists | Not found in the tokenfrugal repo. Mentioned only in `docs/designs/video-pipeline-use-cases.md` | Glob, unconfirmed elsewhere |

**Two HyperFrames copies.** If Mode B renders on the host and Mode A renders in the image, the two versions can drift. This breaks reproducibility. Pick one version and pin it in both places, or use only one.

**Stale design text.** `docs/designs/video-pipeline-use-cases.md` lines 10 and 24 still say Mode B uses Voicebox on the host and renders on the host. Lines 104 to 108 already use VoxCPM2 and Kokoro. The doc needs updating once decisions are made.

---

## 6. Blockers

**B1. Removed for slice 1.** The GPU lease is not used. The slice-1 default voice runs on CPU, so no step takes a lease. The lease returns only when a GPU engine is enabled (VoxCPM2, deferred).

**B2. Voice engine not pinned.** VoxCPM2 licence and peak VRAM are unchecked (`video-pipeline-use-cases.md:105-109`). Kokoro-82M weights are Apache-2.0 per `docs/designs/video-pipeline-use-cases.md:108` (checked 2026-11-02). The Kokoro phonemiser uses espeak-ng (GPL-3.0), installed on the host (D11). Review its obligations before any distribution. Use a fallback rule: if VoxCPM2 fails to load or runs out of VRAM, use Kokoro, and record which engine ran.

**B3. The run must fit one synchronous call.** `mgen` and the role both cap at 900 s. The spike measures a 20 to 30 s run against that cap. Async is added only if it does not fit (section 4).

**B4. No Mode B tool contract.** No signature, input limits, error strings, fps, resolution or timeout is defined yet. Section 4 is a draft.

**B5. Unstable baseline.** `git status` shows an uncommitted `video-editor` to `media-generator` rename, a deleted `role-video-editor` SKILL.md and edits to Mode A tests. Commit or stash this first. Rollback is a revert of the Mode B commit plus the previous digest. Mode A tests must pass before and after.

**B6. One minute on one consumer GPU is unproven.** The design critic estimates VoxCPM2 at about 4 GB of fp16 weights, before activations. The GPU is described as 8 GB in `docs/designs/comfyui-gpu-lease.md:11`, which cannot hold an LLM and a video model together. Nothing has been measured. Start at 20 to 30 seconds. Measure before raising the target.

---

## 7. Major concerns and mitigations

- **Mood picker.** Three reviewers gave different answers (chat prompt, local page, form field). Recommendation: a fixed list of five moods plus "none" in the same brief form, with an optional free-text field that maps to the nearest mood and shows the result. Defer the picker to slice 2 anyway, since slice 1 uses no music choice.
- **Music source.** Decided (D10): slice 1 writes a neutral bed as new code. `make_score.py` is not used because its bed is dramatic. `make_music.py --mood` is a host script from businessnext and outside this repo, so do not copy it unless its licence is cleared.
- **Approval gate.** When only a topic is given, the system writes the narration. Nothing in the concept says the user reviews it before voice and render run. Make an approval step mandatory before any GPU stage. Use an explicit mode toggle ("I have a script" or "write from topic"); do not infer the mode from input length.
- **Observability.** `media_generator_mcp.py:16` keeps only the last 20 lines and returns no stage progress. Each mgen call starts a new container (`router/media_generator_mcp.py:67-68`), so `/tmp` is not shared between runs. Write per-stage timings to the run folder.
- **Shared code.** `docker-compose.yml:25-26` and `Dockerfile:57` pull `compose_intro.py` and `make_score.py` from `kalamanch`. Do not edit those files for Mode B; copy or add new modules to keep Mode A unchanged.
- **Image coupling.** Decided: Mode B uses the same image as Mode A (D9). Any image change gets its own digest and commit, and the Mode A regression gates apply.
- **Naming.** Keep `video-editor` names for now. Rename in a separate change.
- **Python versions.** `pyproject.toml` requires 3.11 or later and the router venv is 3.11.9. CLAUDE.md warns that 3.10.0 breaks pydantic. A dedicated Python 3.11 venv for the voice step satisfies both Kokoro and VoxCPM2 (which accepts 3.10 to 3.12). Do not use the host 3.10 install.
- **Determinism.** Voice sampling and CUDA kernels are not bit-stable. Claim reproducibility only at the level of: same script, same WAV (the saved WAV is the input to render), same render versions. Record the seed where the engine supports one. Verify with ffprobe.
- **Existing verification is weak.** The current check for mgen is "returned the Render path with no error" (`tf-roles.yaml:549`). Mode B needs real checks (section 9).
- **Pins.** Pin the exact Kokoro package version, Hugging Face revision for weights, VoxCPM2 build if used, PyTorch CUDA build, and npm versions. Pin HyperFrames to 0.8.223 to match the image.

---

## 8. Open decisions (need user answer)

- **D1. Where does render run? DECIDED 2026-11-02: in the container** (Option A). HyperFrames and Chromium already live there. Option A needs a Mode B service whose network setting is decided under D7.
- **D1a. Where does voice run? DECIDED 2026-11-02: on the host.** The Kokoro step runs on the host and writes `narration.wav` into the media folder. The container reads it from the mapped folder (`docker-compose.yml:32`, mounted at `/work`). The host needs a Python 3.11 venv with Kokoro (task 4), and the container needs no voice layer. The folder path is the existing media workspace folder (`VIDEO_EDITOR_DIR`), unless the owner names another.
- **D2. Default engine. DECIDED 2026-11-02: Kokoro-82M.** VoxCPM2 stays opt-in after a VRAM spike passes. Kokoro licence and espeak-ng check still open (B2).
- **D3. Tool, mode or role? DECIDED 2026-11-02: separate role.** The assistant (orchestrator) picks the role from the request type: text brief goes to the `media-motion` role, raw clip goes to the clip role. The user never sees role names. Reasons: the film run needs its own timeout (the clip role's 900 s limit does not fit), and the router caps each role at 6 recommended tools (12 maximum). The routing rule lives in the assistant's instructions and the role's skill text.
- **D4. Mood picker surface.** Form field with five fixed moods and "none" (recommended), or a chat prompt, or a local page. Deferred to slice 2 either way.
- **D5. Script approval. DECIDED 2026-11-02: mandatory.** The user approves the script before voice and render.
- **D6. Duration target. DECIDED 2026-11-02: 20 to 30 s for slice 1.** The one-minute target stays for a later slice, after the spike measures VRAM, render time and the 900 s limit. An earlier answer said "full one minute now"; the later answer replaces it.
- **D7. Network for the container. DECIDED 2026-11-02: keep the current bridge network.** No separate `network_mode: none` service. The "networking disabled" premise in section 1 is dropped. Reproducibility depends on pinned inputs only.
- **D8. Determinism bar. DECIDED 2026-11-02: no byte-identical requirement.** Fresh runs may differ. Rework and resume reuse every approved stage output, stored in the run folder with its sha256, and regenerate only the stages the user names. Tests check measured properties (duration, frame count, loudness, transcript match), not file bytes. Gate constants (loudness target, transcript tolerance) are set from the spike's measured values (task 3), not guessed. fps is 30 (D12).
- **D10. Music. DECIDED 2026-11-02: write a neutral bed for slice 1.** The dramatic bed in `make_score.py` is not used. The neutral bed is new code, built and tested in the spike, and the `music` field (D5 and section 4) turns it on or off.
- **D13. Approval points. DECIDED 2026-11-02: four user approvals, in order.** (1) Script, before any voice work (extends D5). (2) Narration voice, before scenes and render. (3) Stills of each scene, before the full render. (4) Sample video of 20 to 30 s with background music, before the file is treated as final. This reinstates the stills preview removed as stage 4b in PROPOSE FIX 1, so that fix is reversed.
- **D14. Entry point and error strings. DECIDED 2026-11-02: entry point is assistant routing only.** The user asks for a film in plain words, and the assistant sends the request to `media-motion` through the tool `media-briefing`. There is no separate command. Error strings use the same `error: ...` format as `mgen`, with fixed wording set in the slice-1 task file.
- **D15. Run folder and `list_renders`. DECIDED 2026-11-02: one run folder per job, and only finished films are listed.** Each job writes to `Render/<out_name>.run/`. The folder keeps every stage output and a status file, so a crash or a rework request resumes or redoes from the named stage. `list_renders` shows finished MP4s only, not run folders.
- **D12. Template. DECIDED 2026-11-02: defaults.** 16:9, 1920x1080, 30 fps. One neutral palette: dark background, light text, one grey accent. One open-licence sans-serif font, bundled with its licence and hash recorded in the manifest. Three scene types only: title card, text lines, closing card. The exact colour values and font file are set in the slice-1 task file.
- **D11. Phonemiser. DECIDED 2026-11-02: accept espeak-ng (GPL-3.0).** It installs on the host with the voice step (D1a), not in the image. Before any build is distributed to others, the GPL-3.0 obligations must be reviewed.
- **D9. Image. DECIDED 2026-11-02: same image as Mode A.** Render, scenes, mux and the music bed all use the existing `media-generator` image. Voice runs on the host (D1a), so the image should need no new packages for slice 1. Task 1 confirms this. If the image changes, it gets a new digest at `docker-compose.yml:27`, and the Mode A regression gates in section 9 must pass before and after.

---

## 9. Verification plan (proposed, not yet agreed)

- **Stage tests with fake engines:** a stub voice engine that returns a fixed WAV, a stub renderer, so the state machine and manifest can be tested offline.
- **Kill and resume:** kill the run during voice and during render; confirm resume from the last good stage.
- **Output checks (ffprobe):**
  - Duration within the tolerance for the target (slice 1: target plus or minus 1.0 s).
  - One video stream and one audio stream (if music or narration is included).
  - Frame count equals duration times fps.
  - Narration duration matches the WAV length within 0.1 s.
- **Manifest check:** every input and output has a sha256 and is listed.
- **Mode A regression:** the existing media-workspace and preflight tests pass before and after (`tests/test_media_workspace.py`, `tests/test_preflight.py`), plus `docker compose -f docker-compose.yml config --quiet`.
- **Spike measurements (before any one-minute target):** peak VRAM for each engine, wall-clock time per stage, peak RAM, and the render time for 20 s and 60 s.

Acceptance commands are proposals. They need sign-off with the design.

---

## 10. First-slice task order (proposed, after approval)

1. Commit or stash the current rename and Mode A edits (B5). Acceptance: `git status` clean for the affected paths, and Mode A tests pass.
2. Confirm the Kokoro licence and espeak-ng dependency, and record the VoxCPM2 licence and VRAM as unverified until measured. No acceptance command; a written note in the design doc.
3. Measure VRAM and time for a 25 s Kokoro narration on this machine. Acceptance: a recorded number in the design doc.
4. Create the Python 3.11 voice venv and install pinned Kokoro. Acceptance: `<venv>\Scripts\python.exe -c "import sys, soundfile; assert sys.version_info[:2]==(3,11); print('ok')"`.
5. Add the brief schema and tool stub with validation and error strings. Acceptance: a new unit test file passes.
6. Silent HyperFrames render at the target length, in the chosen location (D1). Acceptance: ffprobe duration within the tolerance.
7. Mux narration and bed, then run the verification checks in section 9. Acceptance: ffprobe lists one video and one audio stream, and the frame count matches.
8. Write the neutral music bed for slice 1 (D10), replacing the dramatic `make_score.py` bed. Acceptance: `bed.wav` exists, its loudness is measured, and the bed is listed in the manifest with its sha256.
9. Stills gate (D13 point 3): render one still per scene and a contact sheet, then record the user's approval or the scene ids they name in the run manifest. Acceptance: `preview/` holds one still per scene, and the approval field is set before the full render runs.

---

## 11. Risks not resolved by this brief

- The licence of each model weight and of the Kokoro phonemiser has not been verified online.
- Voice cloning consent rules are not needed in slice 1, but must be written before cloning is added.
- The businessnext-video-v3 skill was not found in this repo. Its method is described second-hand from the design doc.
- The current git state is dirty. Any Mode B commit must be made after B5.
- The reviewers did not run any render or engine. All time and VRAM figures are estimates.

---

## 12. Stage gates and redo minimisation (added 2026-11-02)

**Principle.** Each stage writes one output file, must pass its gate before the next stage starts, and records the hashes of its inputs. A failed stage reruns alone, and only the stages downstream of a changed input rerun.

**Stage table (slice 1)**

| Stage | Output | Gate (must pass before the next stage) |
| --- | --- | --- |
| 1. Script | `script.json` (lines with cue ids) | Word count fits the duration target; no empty cues; banned-term list empty; user approves the script (D13 point 1) |
| 2. Voice | one WAV per line in `clips/` | Every clip exists; durations measured; the Kokoro transcript of each clip matches its text within a stated tolerance; user approves the narration voice (D13 point 2) |
| 3. Timing | `acts.json` (single writer) | Total length within the tolerance set from measured runs (see Limits below); every cue lands inside its act |
| 4. Scenes | `scenes/*.html` | Lint and the guard rules pass for each scene on its own; font sizes and no colour tweens |
| 4b. Stills | `preview/` stills and one contact sheet | User approves the stills, or names scene ids to change (D13 point 3). Only named scenes rerun |
| 5. Music | `bed.wav` (optional) | Length matches the video; loudness at the agreed target |
| 6. Render | `video_raw.mp4` | Encoded duration matches the plan; frame count equals duration times fps |
| 7. Mux and verify | `Render/<name>.mp4` and manifest | One video and one audio stream; ffprobe duration within tolerance; every input and output has a sha256 |
| 8. Sample approval | the 20 to 30 s sample with background music | User approves the sample before it is treated as final (D13 point 4) |

**Status file.** One `status.json` per run records, for each stage: its input hashes, its output hashes, its gate result and its timing. On rerun, a stage is skipped when its input hashes match and its last gate passed. Mode B keeps its own status file. Studio's runs table is design-only, so it is not a dependency.

**Clip cache.** Voice clips are keyed by the hash of the line text, the voice id, the engine name and version. Editing one line re-synthesises that line only. Voice is the most expensive stage, so this matters most here.

**Failure handling.** A failed gate stops the run at that stage and writes `failed:<stage>` to the status file. A fix changes that stage's inputs. Downstream stages rerun because their input hashes changed. Stages upstream of the failure are not touched.

**Limits.**
- The scripts can check length, format, text match and sizes. They cannot judge whether a scene looks right. Stage 8 remains a look, not a script.
- Gate tolerances (length plus or minus 1.0 s, transcript match, loudness target) are set from measured runs during the spike (section 10, task 3), not guessed.
- The gates only protect what they check. A gate that passes on a wrong voice clip is still a pass.

**Open questions for this section**
- None on stage 8: it is a required user sign-off (D13 point 4).
- Keep the Kokoro transcript check (needs a local ASR model, which adds weight) or check text length and duration only?
