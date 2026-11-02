# Stage 6 Comprehension Test: concepts_brief.md

* **Produced by:** `egm:egm-comprehension` (read-only subagent `afe77fb039c73ce9d`). The subagent could not write files, so its report came back as a message. This file holds that message text, saved by the orchestrator.
* **Standard:** re-implementation-standard.md (Zero-Assumption Rule)
* **Scope:** whole file. The Stage 5 report was not read.
* **Verdict:** Fails the re-implementation standard. A builder working only from the brief would have to choose the role name, tool signature, stage list, output format, schemas, validation limits, voice, palette and device.
* **Fixes marked "proposed"** are suggested values. They need your sign-off, as the brief requires (line 3).

## Blockers

* **B1. Three different stage lists.** Line 94 (script, voice, music, scenes, render, mux, verify); lines 56-63 (component table, including GPU lease); lines 214-222 (stages 1 to 8 plus 4b). The state values `running:<stage>` and `failed:<stage>` cannot resolve to one set.
  * Fix: make the section 12 table the only stage list. Give each stage an id. State enum: `queued`, `awaiting_script_approval`, `running:<id>`, `awaiting_preview_approval`, `done`, `failed:<id>`. Remove `waiting_gpu` unless B3 keeps the GPU.
* **B2. Approval, revision, resume and cancel have no states or calls.** D5 requires script approval (line 158), but the stage table has no approval stage. Nothing defines how a user approves, revises, resumes or cancels.
  * Fix: add stage 0 "script approval" with gate "approved script.json sha256 recorded". Define `mode_b_approve(run_id, sha256)`, `mode_b_revise(run_id, scene_ids[])`, `mode_b_cancel(run_id)`, each with its arguments, return text and state transition.
* **B3. Voice device and runtime contradict each other.** D2 and line 155 say Kokoro on CPU. Line 154 says CPU-only in the container. Lines 63 and 122 use a GPU lease for a "GPU voice step". Line 148 pins a CUDA PyTorch build. Line 188 names a host venv path. A builder cannot tell which applies.
  * Fix (proposed): "Slice 1 voice runs CPU-only inside the Mode B container. No GPU lease in slice 1. PyTorch is the CPU wheel at version X." Move the lease to the deferred list. Rewrite task 4 as a container build step with a `docker run ... python -c` acceptance command.
* **B4. Role and tool names are not fixed; the title conflicts with D3.** Line 1 ties Mode B to media-generator. D3 (line 156) says separate role. Line 76 says `mode_b_brief` ("name to confirm"). Line 77 gives `media-motion` as an example. The tf-roles entry and the exact tool-set test (`tests/test_preflight.py:135`) depend on the name.
  * Fix (proposed): role `media-motion`, tool `mode_b_brief`. Write both into D3. Change the line 1 title to "Mode B for a new `media-motion` role". Delete the Option 1 and Option 2 text at lines 76-78.
* **B5. No tool contract.** The return convention "exit=N or error: ..." is defined only by reference to `mgen`. No signature, input limits, error strings, fps, resolution or timeout (line 128 admits this).
  * Fix: add `mode_b_brief(text, language, engine, voice, music, style, length_target_s, out_name) -> "run_id=<id>" | "error: <code> <message>"`. List every error code with its exact message. Add `mode_b_status(run_id)` returning the state enum and stage id. Give a numeric timeout for each call.
* **B6. The transform from brief to video is undefined.** The brief does not say how text is split into lines, what a cue id is, how lines map to acts and scenes, how act duration is computed, or what the template looks like.
  * Fix (proposed): split `text` on blank lines. Each line gets id `c01`, `c02` and so on, and each line is one act. Act duration = voice clip length + 0.4 s pad. Each act renders one scene from `docker/media-motion/templates/default.html`, which shows the line text in one centred block. Name the placeholder fields.
* **B7. Validation rules are missing.** `text` max is "to be set" (line 81). `engine`, `style`, `music`, `length_target_s` and `out_name` have defaults but no allowed values or ranges. `out_name` "must pass the existing `_check()`", whose rules are not in the brief. The example "1200 words for a one-minute target" is roughly 8 minutes of speech at 150 wpm.
  * Fix (proposed): `text` 1 to 300 words, with a duration check at 2.5 words per second. `length_target_s` in [20, 30]. `engine` in {kokoro}, else `error: engine_not_supported`. `style` in {neutral}. `music` in {none, bed}. `out_name` matches `^[a-z0-9_-]{1,64}$`. State each rule in full.
* **B8. Output format is not specified.** Aspect ratio, resolution, codecs, sample rate, channels and loudness target are all absent. Frame count (line 173) needs an fps that is never given.
  * Fix (proposed): a table: 1920x1080, 16:9, 30 fps, H.264 yuv420p, AAC 48 kHz stereo, integrated loudness -16 LUFS. Mark it for sign-off in section 8.
* **B9. Manifest and status schemas are missing.** Line 92 is a bare field list with no types. Line 224 takes its shape from another document (`docs/designs/studio-and-collector-roles.md:131`). The standard forbids inferring output schemas.
  * Fix: give a JSON skeleton for `manifest.json` and `status.json` with key names and types. Add a per-stage table of hashed inputs. Do not refer the reader to the Studio doc for the shape.
* **B10. Run folder and artifact layout are undefined, and two lines contradict.** Line 56 says "create run folder" with no path. Line 57 has one `narration.wav`; line 215 has one WAV per line in `clips/`. Line 141 leaves `/tmp/mgen` as a fixed path. The mux input name is not given.
  * Fix (proposed): run root `media/mode-motion/runs/<run_id>/`. Files: `script.json`, `clips/<cue-id>.wav`, `narration.wav` (concatenated from clips; the single mux input), `acts.json`, `scenes/<scene-id>.html`, `preview/`, `bed.wav`, `video_raw.mp4`, `status.json`, `manifest.json`. Temp dir `<run root>/tmp/`. Name the test change needed for `LAYOUT`.

## Majors

* **M1. Superseded decisions still read as open.** Lines 14-18, 57, 59, 60, 65, 76-78, 114, 116 and 191 still present decided items as open or as options. A builder could implement a rejected option. Replace each with the decided text; keep history in an appendix.
* **M2. Timing tolerance is stated two ways.** Lines 87, 171 and 216 say plus or minus 1.0 s. Line 240 says tolerances are set from the spike. Write: "slice 1 tolerance is +/-1.0 s; the spike may change it, and any change is written here before build."
* **M3. Gate criteria are undefined.** The banned-term list (line 214) is not given. The transcript check (line 215) has no tolerance and no named ASR model. Line 217 names lint, guard rules, font sizes and colour tweens without values.
  * Fix (proposed): banned terms in `docker/media-motion/banned_terms.txt` (may be empty). Transcript check off in slice 1; replace with a per-clip duration check within 0.1 s of the WAV length. Name the exact lint command. Font minimum 24 px at 1080p. Define "colour tween" or delete it.
* **M4. Open decisions remain at dispatch.** D8 (line 161) is still open. D4 (line 157) is deferred. Lines 244-245 leave the stage 8 sign-off form and the transcript check open.
  * Fix: record defaults. D8: manifest plus ffprobe checks. Stage 8: a manifest note. Transcript check: off in slice 1. D4: not in slice 1.
* **M5. Determinism and seed are vague.** Line 30 says "deterministic-enough". Line 146 says "record the seed where the engine supports one" with no seed value or source.
  * Fix (proposed): add `seed` to the schema with default 0. The manifest records the seed used, or `null` if the engine has no seed support. Define "explains any difference" as a list of changed hashes.
* **M6. Voice is not named.** Lines 29 and 84 say "a fixed preset voice" with no id.
  * Fix: name the Kokoro voice id (for example `af_heart`) as the default. Confirm in the spike (task 3).
* **M7. Palette, font and template have no values.** Line 28 gives no colours. Line 92 has no font file name.
  * Fix (proposed): background `#111827`, text `#F9FAFB`, accent `#2563EB`. Font `docker/media-motion/fonts/Inter-Regular.ttf`. The sha256 is computed at build time and written to the manifest.
* **M8. Music bed invocation is not given.** Line 58 names `make_score.py` but not its arguments, output length rule, or loop/trim behaviour.
  * Fix (proposed): call `make_score.py` with the target duration and output `bed.wav`. Loop if shorter than the video, trim if longer. Mix at -18 dB under narration. Confirm the signature against the script before build.
* **M9. Topic mode conflicts with the schema.** Lines 37 and 47 exclude topic-only input from slice 1. Line 140 requires a mode toggle. Lines 81-88 have no mode field.
  * Fix: slice 1 has no mode field. Topic input returns `error: topic_mode_not_in_slice_1`. The toggle is added in slice 2.
* **M10. Name collision and overwrite are undefined.** No rule for an existing `Render/<out_name>.mp4`.
  * Fix: return `error: out_name_exists`. No overwrite flag in slice 1.
* **M11. Async pattern is not specified.** Line 96 says to reuse the heartbeat and stale-sweep pattern in `router/store.py` but does not say whether to call, copy or extend it. No poll interval, stale time or heartbeat period.
  * Fix (proposed): a `mode_motion_runs` table in `router/store.py`. Heartbeat every 10 s. Stale after 60 s without heartbeat. Poll `mode_b_status` every 5 s.
* **M12. Retries and per-stage timeouts are missing.** Line 126 mentions "a longer timeout with a measured budget" with no number.
  * Fix (proposed): voice 300 s with 1 retry; scenes 60 s, no retry; render 600 s, no retry; mux 120 s, no retry. Whole run cap 1800 s. Mark all as provisional until the spike.
* **M13. Service and image choices are open.** Line 114 offers two options. Line 142 says "copy or add new modules". Line 143 leaves the toolchain choice open. Line 154 names a Mode B service with no name or file.
  * Fix (proposed): new compose service `media-motion` from `docker/media-motion/Dockerfile`. It copies `make_score.py` and `compose_intro.py`. The `media-generator` image digest is unchanged. Record the choice in D1.
* **M14. Pins have no values.** Only HyperFrames 0.8.223 and Python 3.11.9 are given. Kokoro package, Hugging Face revision, PyTorch build and npm versions are missing.
  * Fix: write exact versions into the brief, or make "pin at spike, write into section 10 task 3" an acceptance step. Remove the CUDA pin if B3 is applied.
* **M15. Lease holder name and floor are placeholders.** Applies only if B3 keeps the GPU lease.
  * Fix: if B3 removes the lease, delete this item. Otherwise name the holder `media-motion` and set the floor from the spike.
* **M16. Preview capture is not specified.** Line 218 gives no time offsets. Line 230 says the method is "to be confirmed in the spike".
  * Fix (proposed): capture at act start + 0.1 s, act midpoint, and act end - 0.1 s, using headless Chromium. Remove "to be confirmed".
* **M17. The length target conflicts.** Line 11 says Mode B makes "about one minute". Lines 27 and 158 say 20 to 30 s for slice 1. Line 81 gives a one-minute word example.
  * Fix: line 11 reads "Mode B targets 20 to 30 s in slice 1; one minute is deferred (D6)." Remove the one-minute word example from line 81.
* **M18. Terms the builder must act on are undefined.** Act, cue, cue id, scene id, template, `acts.json` single writer, Raw and Render, MCP, stage 4b, lint, guard rules, colour tween, `_check()`, store.py heartbeat and stale-sweep.
  * Fix: add a glossary at the top of the brief, one line per term, each linked to its file path where one exists.
* **M19. The fake-engine test interface is missing.** Line 167 mentions a stub voice engine and stub renderer. Line 190 names no test file.
  * Fix (proposed): `synthesize(text: str, voice: str, out_wav: Path) -> float` (returns duration in seconds) and `render(scenes_dir: Path, out_mp4: Path) -> None`. Test files `tests/test_mode_motion_intake.py` and `tests/test_mode_motion_stages.py`.
* **M20. Concurrent runs can collide.** Line 141 says `/tmp/mgen` makes runs collide, but section 2 has no requirement against it.
  * Fix: add to section 2: "Each run writes only inside its run root (B10). Two runs with different run ids must not share files." Add a test to section 9.

## Nits

* **N1.** Lines 3-4 list reviewer agent names a fresh reader cannot use. Move them to a footer.
* **N2.** Kalamanch and kalamanch spelled both ways (lines 41, 108, 109, 122, 142). Use one.
* **N3.** "Brief" means three things: the document, the user's plain-text input (line 11), and `brief.json` (line 56). Call the user input "request".
* **N4.** "Render" is a folder (line 90), a stage (lines 60, 220) and a component (line 60). Rename the stage to "frames".
* **N5.** Clip cache hash is undefined (line 234). Use sha256 of `line_text` + newline + `voice_id` + `engine_name` + `engine_version`, stored in `media/mode-motion/cache/clips/`.
* **N6.** Line 112 ("Glob, unconfirmed elsewhere") is a note a reader cannot check. Write: "Not found by a search of the tokenfrugal repo on 2026-11-02."
* **N7.** Line 185 names no paths. List them.
* **N8.** Voicebox (lines 40, 116), "sting" (line 34), GPL-3.0 (line 124) and businessnext-video-v3 (line 200) are not glossed. Add a line each or delete.
* **N9.** "Router or container" (line 62) is an open choice. M13 settles it.
* **N10.** "Option A" (line 154) names no other option. Delete the label.
