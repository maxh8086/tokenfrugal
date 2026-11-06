# Implementation readiness review: concepts_brief.md (Stage 9)

**Target:** `concepts_brief.md` (lines 1-246, full file; no Detailed Implementation section, so DetailedRange is N/A)
**Question:** could an engineer build slice 1 from this file alone without making impactful decisions?
**Reviewers:** egm-implementation-readiness, egm-codebase-details, egm-style, plus a direct check of the repo citations by the orchestrator.
**Prior stages:** Stage 5 to 8 findings are not restated. Stage 8's recommendation (move exact contracts to a slice-1 task file written after sign-off) is accepted in principle, with the limits noted in section 3 below.

---

## 1. Verdict: not buildable as written

An engineer would have to make at least six impactful choices before writing code for slice 1, and several more would be guesses. The largest gaps are:

- Where the voice step runs.
- Whether slice 1 has a GPU step at all.
- What sets the video length.
- What the one video template looks like.
- What the tool and role are called, and whether the tool blocks or returns a run id.

The task list in section 10 also does not produce a finished video. Tasks 1 to 8 cover a commit, a licence note, one measurement, a venv, a lease, a schema stub, a silent render and a mux. Nothing builds the script-to-voice step, the timing step, the scene HTML, or the status and resume logic. Task 7 renders scenes that no task creates, and task 8 muxes narration that no task makes (brief lines 185-192).

---

## 2. Findings

### Blockers

**B1. Where the voice step runs contradicts itself.**
The brief says Kokoro runs on CPU (lines 20, 27). D1 (line 154) says render is in the container and assumes the voice step is also in the container. Task 4 (line 188) creates a Python 3.11 venv that is only meaningful on the host. The image installs no voice stack: `docker/media-generator/Dockerfile:15, :18, :26, :54` add ffmpeg, yt-dlp, whisper, Remotion, HyperFrames and Manim, but no TTS package.
*Decision needed:* container or host for voice. If container, the Dockerfile and the image digest change (`docker-compose.yml:27`). If host, the render location in task 7 and the drift risk in line 114 change.

**B2. Slice 1 may need no GPU lease, but the brief requires one.**
Kokoro is CPU-only in the brief's own default (lines 20, 27), yet section 3 says the lease covers "the GPU voice step only" (line 63), B1 requires a holder (line 122), and task 5 builds it (line 189). If there is no GPU step, the 6 GB floor (`router/gpu_lease.py:35`) and the holder work are out of slice 1.
*Decision needed:* does slice 1 take the lease at all. If yes, the lease call must run where the lease file is reachable (see B3).

**B3. A container cannot reach the lease file as the brief assumes.**
Reported by egm-codebase-details, not independently re-read: `lease_dir()` resolves to `router/leases` unless `GPU_LEASE_DIR` or `GATEWAY_DB` is set (`gpu_lease.py:118-125`); the VRAM probe calls `nvidia-smi` (`:305-310`); the image installs no `nvidia-smi` and the compose service has no GPU reservation (`docker-compose.yml:22-33`); and only `/work` is mounted (`:31-32`). A lease call inside the container cannot see the shared `gpu.json`.
*Decision needed:* run the lease step on the host and pass the result in, or add the mount and GPU access (and change the brief).

**B4. The lease takeover rule cannot be applied to a new holder as written.**
Verified. `gpu_lease.py:228-235` applies the pid-based takeover only to `kalamanch` (`:230-231`). Every other holder needs a `container_id` and a stopped container (`:233`). B1 asks for "a pid-based takeover" for a new holder. Adding the name to `HOLDERS` (`:38`) and the check in `acquire()` (`:336-337`) is not enough; `_may_take_over` must change too. Otherwise a crashed Mode B run blocks the GPU until `force_release`.
*Decision needed:* which takeover rule the new holder uses, and whether a container id is recorded.

**B5. The task list does not build slice 1.**
Verified against lines 185-192. No task covers: script to WAV (stages 1-2, lines 214-215), timing (stage 3), scene HTML for the template (stage 4), the preview gate (stage 4b), or status and resume (line 169). Task 2 has no acceptance command, so it cannot be marked done.
*Decision needed:* the owner accepts an amended task list before a slice-1 task file is written.

**B6. Stage 8's recommendation cannot be fully applied at sign-off.**
Stage 8 is right that exact contracts belong in a task file. Three gaps remain:
- Several values come only from the spike (task 3): timeouts, tolerances, words per second, loudness, and VRAM. A task file written at sign-off would carry placeholders.
- Some items are decisions, not values (B1, B2, D3 naming, the template, the music rule). A task file cannot decide them.
- A few values are needed before any task can be written, such as the maximum script length (line 81, "to be set") and the duration rule (B7).
*Decision needed:* the owner closes the decision list in section 4, and the spike numbers are pulled forward or the task file is split into a "decided" part and a "measured" part.

**B7. Length source and duration target are undefined.**
Section 1 says "about one minute" (line 11, and `length_target_s` note at line 87). Sections 2, 8 (D6) and 10 say 20 to 30 s for slice 1. The brief does not say whether narration sets the length or whether the video length is fixed and narration is fitted. No words-per-second rate exists, and task 3 measures only VRAM and time (line 187). The stage 1 gate ("word count fits the duration target", line 214) cannot be coded without this.
*Decision needed:* who adapts to whom, and the words-per-second rate (set by the spike).

**B8. The one template is undefined.**
No aspect ratio (Mode A is 9:16; Mode B never says), no palette values, no font file, no scene list, no layout. "Neutral visual style with one built-in default palette and font" (line 28) is a goal, not a spec. The image already has `fonts-dejavu-core` (`Dockerfile:15`), which the owner can accept or reject.
*Decision needed:* aspect ratio, resolution, fps, palette values, font, and the scene list for the one template.

**B9. The tool and role contract is not set.**
- Tool name: `mode_b_brief` "name to confirm" (line 76).
- Role name: `media-motion` is an example only (line 77). D3 (line 156) refers to "the film role" and "the clip role", which appear nowhere else.
- Sync or async: section 4 says Mode B "should" return a run id (line 96) but also reuses `mgen`'s return convention (line 71), which blocks. B3 (line 126) says it "needs" the async pattern. Not a listed decision.
- Error strings, input limits and the maximum script length (line 81) are not set (B4 in the brief).
- The role needs a `tf-roles.yaml` entry (pattern at `:43`), a contracts entry checked by preflight, a teams entry, a skill and a native server (reported by egm-codebase-details; `tests/test_preflight.py:135` asserts the exact tool set).
*Decision needed:* names, sync or async, timeout, error strings, and the role wiring.

**B10. No Mode B container entry point exists.**
Verified. `docker/media-generator/Dockerfile:57-59` copies `pipeline.py` and symlinks only `mgen`. `router/media_generator_mcp.py:67-68` hard-codes `mgen` as the command. A Mode B command, its `COPY` and its argv are unnamed.
*Decision needed:* the Mode B command name and whether it lives in the same image (line 143 leaves this open).

### Major

**M1. Stage list is defined twice, with different contents.**
Section 4 (line 94) lists script, voice, music, scenes, render, mux, verify (7 stages). Section 12 (lines 210-222) lists script, voice, timing, scenes, preview 4b, music, render, mux and verify, review (9 stages). The status keys and resume logic depend on which list is canonical.
*Decision needed:* one canonical stage list.

**M2. The approval points conflict.**
D5 (line 158) says the script is approved "before voice and render". Section 7 (line 140) says approval is "before any GPU stage". Section 12 has no script approval; its only human gate is stills approval at 4b, which comes after voice. No section 10 task covers either.
*Decision needed:* whether script approval is in slice 1, and where stills approval sits relative to voice.

**M3. The existing run-state store does not match the brief's status strings.**
Verified. `router/store.py:47` updates heartbeat only `WHERE status='running'`, and `:75` sweeps only `status='running'` exactly. The brief's states `running:<stage>` and `failed:<stage>` (line 94) would never be beaten or swept. Reusing `store.py` needs a SQL change or exact status values.
*Decision needed:* exact status values, or a change to the SQL.

**M4. The "reuse the Studio record" claim points at nothing built.**
Reported by egm-codebase-details (`docs/designs/studio-and-collector-roles.md:128`, status "Design complete; awaiting egm-review"). No runs table, studio module or `waiting_gpu` state exists in `router/`. The Studio states differ from the brief's states.
*Decision needed:* either build the record in slice 1 (new work, add to task list) or define a new small one.

**M5. The music bed is not neutral.**
Verified. `kalamanch/pipeline/make_score.py:29-37` builds a dark drone (55, 82.5, 110.4, 164.8 Hz), a pink-noise riser, a 48 Hz pulse and echo, with `loudnorm I=-20`. Section 2 asks for a neutral style. The score function is `make_score(ff, seconds, out)` at `:26`; it calls `sys.exit` on ffmpeg failure (`:21-22`), so a Python caller gets `SystemExit`.
Reported by egm-codebase-details: score mode also calls `publish()` (`:61`), which copies the WAV into Render unless `VIDEO_PUBLISH_DIR` is set; the image sets it to `0` (`Dockerfile:73`), so a host run would write into Render.
*Decision needed:* accept the dramatic score, write a neutral bed, or drop music in slice 1 (section 2 says `music: bed` is allowed in slice 1 while music choice is deferred; see M9).

**M6. Output location collides with the listing tools.**
Verified. Output goes to `Render` (line 90). `router/media_generator_mcp.py:33-36` and `:49-50` list every file in Render, so `scratch`, `clips/`, `preview/` and `status.json` would appear in `list_renders`. A new `LAYOUT` folder breaks `tests/test_media_workspace.py:63`. The run folder path is never given (section 4 says "create run folder", no path).
*Decision needed:* run-folder location, and whether Mode B output is listed by `list_renders`.

**M7. Weights and download policy are unset.**
D7 keeps the bridge network (line 160). Section 7 pins Hugging Face revisions (line 148), but nothing says whether weights are downloaded at run time or baked at build time. Compose mounts only `/work` (`docker-compose.yml:31-32`), so there is no model cache. A build-time bake changes the Dockerfile and the digest (line 27).
*Decision needed:* run-time download or baked weights; if baked, a separate image or the same image (line 143).

**M8. Voice package and phonemiser are not chosen.**
Task 4 (line 188) says "install pinned Kokoro" but gives no package name, version, voice id, sample rate or weight source. B2 flags espeak-ng (GPL-3.0) without a decision.
*Decision needed:* package and version (from task 2 or 4), voice id, and accept or replace espeak-ng.

**M9. Schema values are unbounded.**
`engine`, `voice`, `language` and `style` have defaults but no allowed values (lines 82-86). `style` clashes with the deferred style profile (line 46). `music: bed` is allowed in slice 1 while music choice is deferred (line 85 vs line 40).
*Decision needed:* allowed values, and whether `music: bed` is in slice 1.

**M10. Pins are incomplete for the manifest.**
Section 4 (line 92) requires Chromium and ffmpeg versions. Verified: `Dockerfile:3` uses a tag, not a digest, for `node:22-bookworm-slim`, and `:15` installs unpinned apt `ffmpeg` and `chromium`. Section 7 pins only HyperFrames. These two values can only be recorded at run time, not pinned.
*Decision needed:* accept run-time recording, or pin by apt version and base digest.

**M11. Gate tolerances are fixed in one place and measured in another.**
Section 4 and section 9 fix ±1.0 s (lines 87, 171). Section 12 (line 240) says tolerances are "set from measured runs ... not guessed". Several gates have no number at all: "within a stated tolerance" (stage 2), "guard rules" and "font sizes" (stage 4), "loudness at the agreed target" (stage 5), and fps and resolution for the frame-count check (stage 6, line 173).
*Decision needed:* a fixed constant or a measured value, and the constants themselves.

**M12. Determinism claim is not testable.**
"Deterministic-enough" (line 30) and the D8 bar (line 161) are open. Section 7 (line 146) claims only "same script, same WAV". The brief does not say what the manifest must prove or what a failing check means.
*Decision needed:* D8 answered.

**M13. Multi-output stages conflict with the one-output principle.**
Section 12 says each stage writes one output file (line 208). Stage 2 writes one WAV per line in `clips/`, stage 4 writes `scenes/*.html`, and 4b writes three stills per scene plus a contact sheet. The brief does not say how hashes and gates are scoped for these.
*Decision needed:* hash and gate scope for multi-file stages.

### Nit

**N1.** Section 8 D1 says "Option A", but Option B is never listed.
**N2.** Section 3 "captions if used" (line 61) has no defined condition.
**N3.** Section 9 says "one audio stream (if music or narration is included)" (line 172). Narration is always included, so the condition misleads.
**N4.** Undefined terms: "slice" (first and second), "act" and "cue" (section 12), "guard rules" (stage 4), "Mode A / Mode B" in some places.
**N5.** B2 (line 124) proposes a VoxCPM2-to-Kokoro fallback. VoxCPM2 is out of slice 1, so the rule has no slice-1 effect.
**N6.** `_check()` is private to `media_generator_mcp.py:25-30`, inside a module that creates a FastMCP instance at import (`:11`). Section 4 (line 90) requires the same name rule without saying where it lives. Decide whether to import or copy.
**N7.** `start_heartbeat` is at `gpu_lease.py:391` (reported). The brief gives no reference.
**N8.** `Dockerfile:57` also copies `common/_publish.py` and `common/_paths.py`. The brief cites only `compose_intro.py` and `make_score.py`.
**N9.** Section 5 says the host "lacks ffmpeg, soundfile, HyperFrames, Chrome" and cites `handoff.md:616`. Reported by egm-codebase-details: that line mentions only ffmpeg and ffprobe. Not verified by the orchestrator.
**N10.** Section 11 and line 112 say `businessnext-video-v3` is mentioned only in `video-pipeline-use-cases.md`. Reported by egm-codebase-details as wrong (the name also appears in other review files). Not verified.
**N11.** Section 2 calls `businessnext-video-v3` a "method reference", but section 5 and section 11 say it was not found in the repo. An implementer cannot consult it. Decide whether it counts as a reference.
**N12.** Section 4 (line 81) has no maximum script length; "1200 words" is an example only.

---

## 3. Stage 8 check

Stage 8's move (exact contracts to a slice-1 task file after sign-off) is sound for error strings, fps, resolution, status-file shape and the manifest field list. It does not cover:

- Decisions (B1, B2, B8, B9 naming, M2, M5, M7, M8), which a task file cannot take.
- Values that only the spike can set (B7, M11, the timeouts in B9), which a task file would have to leave as placeholders.
- Two items that already contradict the repo (B3 lease path, M3 SQL), which need a repo-side change, not a value.

Recommendation: close the decisions in section 4 first, then write the task file, and split it into a "decided" part (written at sign-off) and a "measured" part (written after task 3).

---

## 4. Decisions the owner must make before a slice-1 task file can be written

1. **Voice location:** container or host (B1). If container, accept a Dockerfile and digest change.
2. **GPU in slice 1:** does slice 1 take the lease at all (B2)? If yes, where the lease call runs (B3) and the takeover rule for the new holder (B4).
3. **Length source:** narration sets length, or video length is fixed and narration is fitted (B7). Accept the 20 to 30 s target and the words-per-second value (set by spike).
4. **Template:** aspect ratio, resolution, fps, palette, font (`fonts-dejavu-core` is already in the image), and the scene list (B8).
5. **Voice package:** Kokoro package and version, voice id, sample rate, and whether espeak-ng (GPL-3.0) is accepted or replaced (M8).
6. **Weights:** downloaded at run time or baked at build time, and whether Mode B has its own image (M7, line 143).
7. **Music:** accept the dramatic score in `make_score.py`, write a neutral bed, or drop music in slice 1 (M5, M9).
8. **Approval points:** script approval before voice (D5), and whether stills approval (4b) is in slice 1 (M2).
9. **Tool contract:** tool name, role name, sync or async, timeout, error strings, maximum script length, and the role wiring (B9).
10. **Command and image:** the Mode B container command name and where it lives (B10).
11. **Run folder and listing:** run-folder path, and whether Mode B output appears in `list_renders` (M6).
12. **Status record:** exact status strings and whether the Studio record is built or replaced (M3, M4).
13. **Canonical stage list** (M1), and the hash scope for multi-file stages (M13).
14. **Gate numbers:** tolerances as constants or measured values, plus loudness, fps and the transcript check (M11, section 12 open question).
15. **Determinism bar** (M12, D8).
16. **Manifest pins:** accept run-time recording of Chromium and ffmpeg, or pin them (M10).
17. **Task list:** accept an amended section 10 that covers script, voice, timing, scenes, status and resume (B5).

---

## 5. Method and limits

- Read in full: `concepts_brief.md`, `docker/media-generator/Dockerfile`, `docker-compose.yml:18-37`, `router/gpu_lease.py:220-245` and `:330-340`, `router/media_generator_mcp.py:10-85`, `router/store.py:40-80`, `router/tf-roles.yaml:38-49`, `kalamanch/pipeline/make_score.py:14-63`.
- Confirmed by the orchestrator's own reads: compose `:22-33` and `:27` (no network key; digest pin); Dockerfile `:3, :10, :15, :26, :57-59, :73`; `gpu_lease.py:38, :228-235, :336-337`; `store.py:47, :75`; `media_generator_mcp.py:15, :25-30, :33-36, :49-50, :63-68, :79`; `make_score.py:26, :29-37, :41-49, :61`; `tf-roles.yaml:43`.
- Reported by reviewers and not re-read by the orchestrator: `gpu_lease.py:118-125, :305-310, :391`; `kalamanch/common/_publish.py:13-23`; `studio-and-collector-roles.md:128`; `handoff.md:616`; the businessnext mention count.
- Not checked: licences, VRAM figures, Python version claims, the 6-tool cap, host installs.
- No engine, render or test was run. All figures are as stated in the brief or the repo.
- No files other than this report were changed.
