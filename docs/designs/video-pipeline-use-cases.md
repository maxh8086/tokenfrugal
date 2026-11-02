# Video pipeline use cases: media-generator and kalamanch

* **Status:** Draft. Based on reading the role, profile and tool files. Test runs are pending, so no output quality is measured yet.
* **Scope:** Defines what each role does, what goes in and out, the steps, the approval gates, and the open routing choice.

## Summary

The two roles do different jobs. Neither one turns plain text into video by itself.

* **media-generator** (widened) has two modes. Mode A takes one raw talking-head clip in `Raw` and makes a captioned 9:16 short in `Render`. Mode B takes a text brief and makes a motion-graphics film in `Render`, using the same method as the businessnext-video-v3 skill: a narration script, Voicebox voice, HTML/CSS scenes on a timeline, Three.js 3D acts, and a deterministic HyperFrames render.
* **kalamanch** makes a talking-avatar video. It takes a narration script and a portrait photo, creates voice audio, animates the portrait to speak, joins audio and video, and upscales to 1080p.

The request was to describe both as text-to-video. Mode B of media-generator now covers text-to-motion-graphics. Kalamanch still animates a photo with a video model. Routing is decided: text-to-motion-graphics goes to media-generator. Kalamanch keeps the scripted avatar path.

## Component facts (from the repo)

### media-generator

* MCP tools: `list_raw`, `list_renders`, `mgen(clip, out_name, no_music, captions)`, `read_file`. Source: `router/media_generator_mcp.py`.
* Input: a bare file name inside the media `Raw` folder. Paths are refused.
* Runs in the `media-generator` Docker service (`docker-compose.yml`, build `./docker/media-generator`), with the media folder mounted at `/work`.
* Output: a file in `Render`. The tool returns the exit line.
* Timeout: 900 seconds.
* Mode B (planned, not built): a new tool would call the businessnext-video-v3 scripts on the host, not inside the container. Reason: Voicebox runs on the host at 127.0.0.1:17493, and the `media-generator` profile has network disabled. Needs Node, ffmpeg, Python with numpy and soundfile, HyperFrames with headless Chrome, and a GPU for 3D acts.
* Voice (checked 2026-11-02): media-generator has no voice component. Its container runs whisper.cpp (speech-to-text for captions) and no speech synthesis or cloning. The only voice path in the repo is kalamanch `run_voice`, which calls the Voicebox REST server (`kalamanch/kalamanch/voice.py`). So Mode B voice means either reusing Voicebox through that path on the host, or adding a new engine. Choosing a new engine needs a licence check; `docs/pixaroma-workflows.md` lists OpenVoice V2, VoxCPM2 and CosyVoice2 as candidates, none tested.
* Background music (required for Mode B): Mode A already mixes a synthesised score under the narration through `make_score.py mix` (ducked by sidechain, video copied). Mode B can use the same script for the bed (`make_score.py score <seconds> <out.wav>`). That script has no mood choice, so mood variety would come from the businessnext-video-v3 `make_music.py --mood` on the host instead. The bed must be recorded in the run's palette/sting note like the other style choices.
* Mode B style rule: no BusinessNext branding. Do not use the BusinessNext logo, logo sting, colour palette, typography or design-system tokens from the businessnext-video-v3 skill. Mode B uses a neutral style profile that the user supplies, or a generic default chosen for the brief. Each run must record the palette, font and sting it uses.
* Profile: `profiles/media-generator.yaml`, server `ts-fs-media-generator`, network disabled, media mounted read-write.
* Role entry: `router/tf-roles.yaml` line 43, model `thinker`, `required_tool: list_raw`.

### kalamanch

* MCP tools: `run_voice(text, profile, out_path)`, `run_animate(portrait, seconds, out_path)`, `run_assemble(video_path, audio_path, out_path)`, `run_upscale(in_path, out_path, scale=2)`. Source: `router/skills/kalamanch/SKILL.md`.
* Stage 1 (the script) is not a tool. The orchestrator writes it and the user approves it.
* Animate runs a 30-second 480p sample first. Longer runs use 30 to 60 second chunks after approval. Memory is capped at 75% (90% worst case).
* Video models: LTX 0.9.8 distilled and OmniAvatar.
* Profile: `profiles/kalamanch.yaml`, image pinned by digest, network enabled, workspace mounted read-write.
* Role entry: `router/tf-roles.yaml` line 37, model `builder`, timeout 450 seconds.
* Uses the ComfyUI GPU lease (`router/gpu_lease.py`).

### Known defect

* `OmniAvatar/utils/io_utils.py:157` runs `cp` through `shell=True`. It fails on Windows and caused the 30 October OmniAvatar output loss. Not fixed. kalamanch's animate stage depends on this path, so this must be fixed or avoided before a full run.

## Use case A: short from a raw clip (media-generator)

Input: one talking-head clip in `Raw`, about 9:16 or landscape, plus a file name for the output.

Steps:
1. `list_raw` confirms the clip exists.
2. `mgen` crops to 9:16, adds captions (`captions="auto"`), and adds music unless `no_music` is set.
3. Output appears in `Render`. The role returns the exit line and the file name.

Approval gates: none needed. The run is local and writes only to `Render`.

Stop conditions: clip missing, clip name contains a path, or `mgen` exits non-zero. Report the exact error.

Not covered: writing the words, generating motion, or any text input. A raw clip must already exist.

## Use case B: scripted avatar video (kalamanch)

Input: a narration script (plain text) and a portrait image in `Raw`.

Steps:
1. The orchestrator writes the script. The user approves it. Nothing runs before approval.
2. `run_voice` turns the script into audio.
3. `run_animate` makes a 30-second 480p sample from the portrait and audio. The user reviews it.
4. After approval, longer chunks are produced and joined.
5. `run_assemble` joins audio and video.
6. `run_upscale` raises the result to 1080p.

Approval gates: script (before stage 2), 30-second sample (before stage 4). Each full run takes the GPU lease. If the lease is held, the run waits and reports "waiting for GPU".

Stop conditions: lease not granted within the wait limit, memory limit hit, or `cp` failure in OmniAvatar.

Not covered: writing the script from a brief. That stays with the orchestrator and the user.

## Comparison

| Point | media-generator | kalamanch |
| --- | --- | --- |
| Input | Existing raw clip | Script and portrait |
| Writes words | No | No (orchestrator writes the script) |
| Generates motion | No | Yes (LTX or OmniAvatar) |
| Needs GPU | No (container ffmpeg, to confirm in test) | Yes (lease) |
| Approval gates | None | Script, 30-second sample |
| Output | 9:16 captioned short in `Render` | 1080p talking-avatar video |
| Typical duration | Bounded by the input clip | Set by the script length |

## Routing choice

Decided by the user: widen media-generator. Text-to-motion-graphics requests go to media-generator Mode B. Clip-to-short requests stay on Mode A. Scripted avatar videos go to kalamanch.

Rename applied 2026-11-02: the role and tool are now media-generator and mgen (profile, compose service, MCP module, Dockerfile user). Not renamed yet: the OneDrive folder video-editor, the VIDEO_EDITOR_DIR variable, the Docker Hub image name, and the kalamanch repo.

## Open items

* Test run: media-generator on a real raw clip (pending; the first attempt uses a clip name that was not confirmed in `Raw`).
* Test run: kalamanch 30-second sample (needs script and GPU approval).
* Fix or avoid the OmniAvatar `cp` call on Windows.
* Routing rule (user decision).
* README sample: only after the user approves the test video. Nothing is pushed before approval.
* Build Mode B: new host-side tool, profile change, role change in `router/tf-roles.yaml`, skill text. Needs an EGM brainstorm first (feature-sized).
* Mode B voice engine (user chose a new engine, 2026-11-02). Licence check from the repo pages, checked 2026-11-02:
  * VoxCPM2 (OpenBMB/VoxCPM): Apache-2.0 code and weights, 2B, 30 languages, voice design from a text description, controllable cloning from a short clip. Recommended. Requires Python 3.10 to 3.12, PyTorch 2.5+, CUDA 12+. VRAM not measured.
  * CosyVoice / Fun-CosyVoice3-0.5B (FunAudioLLM): repo Apache-2.0. Zero-shot cloning and instruct control. The model-card licence for the Fun-CosyVoice3 weights was not checked.
  * OpenVoice V2 (myshell-ai): MIT code and weights, but it is a tone-colour converter on top of a separate base TTS. It does no voice design, so it covers cloning only.
  * Kokoro-82M (hexgrad, Hugging Face model card, checked 2026-11-02): Apache-2.0 weights, 82M parameters, preset voices only, no cloning. Kept by the user as a second engine. It covers plain narration with fixed voices, and VoxCPM2 covers cloning and voice design.
  * Not yet checked: the VoxCPM2 model-card licence, and VRAM on this GPU. Pin the weights only after both checks.
  * Build still needs an EGM brainstorm first (feature-sized).
* Mode B background music: pick the bed source (`make_score.py` in the container image, or businessnext `make_music.py --mood` on the host). Add to the brainstorm brief.
* Check the media-generator Mode A test run result.
* Confirm the Mode B neutral style profile (palette, font, sting). The businessnext-video-v3 `clean-room` profile has not been checked for neutrality and must not be used by default.
