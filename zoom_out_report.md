# Stage 5 Zoom-Out Review: concepts_brief.md

* **Produced by:** `egm:egm-zoom-out` (read-only subagent `aa70a9278616b4d06`). The subagent could not write files, so its report came back as a message. This file holds that message text, saved by the orchestrator.
* **Standard:** zoom-out-standard.md
* **Verdict:** Repo facts mostly accurate. Scope is the problem. Slice 1 is over-engineered: the brief still carries the one-minute, GPU, async, multi-gate and resumable-pipeline design that decisions D1, D2, D5, D6 and D7 were meant to remove.

## Verified correct

* `docker-compose.yml:22-33`: no network setting on media-generator. `disableNetwork` is only on the filesystem sidecar (`profiles/media-generator.yaml:23`).
* Dockerfile facts (HyperFrames 0.8.223, chromium and ffmpeg, make_score COPY at :57, Chromium guards). Digest pin at `docker-compose.yml:27`.
* `router/gpu_lease.py`: TTL 30 at :23, 6 GB floor at :35, holders closed at :38, ValueError at :336-337.
* `kalamanch/run.py`: lease taken at :37, released at :54.
* `router/tf-roles.yaml:43`: list_raw and timeout 900. `router/media_generator_mcp.py`: TIMEOUT 900 at :15, MAX_LINES 20 at :16, Raw check at :63, Render diff at :79-80.
* `tests/test_preflight.py:135` asserts the exact native tool set. `store.py`: HEARTBEAT 30, STALE_AFTER 120, sweep_stale. Tool caps (6 recommended, 12 maximum) at `preflight.py:63-64`.
* `make_score.py` has no mood option. The businessnext skill is not in the repo. pyproject requires Python 3.11. The use-cases doc lines 10, 24, 104-109 are correct.

## Blocker

* **B1. Task order and Python setup contradict D1** (lines 154, 187-188, 145). D1 moved render to the container, and the brief says Kokoro also runs there on CPU. Task 3 measures "on this machine". Task 4 creates a Windows host venv. Kokoro and its Python stack must go into the image, which changes the digest-pinned Mode A image, and the goal "Mode A behaviour unchanged" (line 31) is at risk. Section 7 (line 143) leaves this open.
  * Fix: add a D1 addendum that picks one option before task 4. Recommended: a second small image, `FROM` the existing pinned digest plus a Kokoro layer, in its own Dockerfile and compose service. Mode A keeps its pin. Rewrite tasks 3, 4 and 7 to run in that container.

## Major

* **M1. Scope is inconsistent.** Line 11 says "about one minute". Line 81 says "1200 words for a one-minute target". D6 and section 2 say 20 to 30 s. 1200 words is about 8 minutes of speech.
  * Fix: line 11 becomes "20 to 30 seconds (slice 1)". Set max words to 90 for slice 1 (about 150 wpm with margin) and state the words-per-second assumption.
* **M2. The GPU lease (B1, task 5) is not needed for slice 1** (lines 63, 122, 189). Slice 1 uses Kokoro on CPU. The only GPU engine, VoxCPM2, is deferred. Calling `acquire()` would unload the user's Ollama models (`gpu_lease.py:339-359`) and check 6 GB free VRAM (:318), a side effect on shared code for a CPU job. The B1 fix is also wrong: pid-based takeover applies only to kalamanch (`gpu_lease.py:230-231`); other holders use container_id (:233-234).
  * Fix: drop B1 and task 5 from slice 1. Reopen the lease when a GPU engine is enabled, then specify the container_id takeover path.
* **M3. Async run-id, polling, heartbeat and stale-sweep (B3, lines 94-96) are premature** for 20 to 30 s. The role timeout is 900 s (`tf-roles.yaml:43`). The spike (line 177) should decide this.
  * Fix: keep one synchronous call for slice 1. Make async conditional on the spike: only if measured end-to-end time exceeds about 600 s. Remove the run-state draft at line 94.
* **M4. Stage-gate machinery in section 12 is over-built** for one template and 25 s (lines 206-246): 9-stage table, status.json with input hashes, scene-scoped reruns, clip cache (line 234), kill-and-resume tests (line 169). Section 10 (lines 185-192) does not include any of it, so the sections disagree.
  * Fix: for slice 1, one function writes script.json, narration.wav, bed.wav, video_raw.mp4 and the final MP4 in order, plus one manifest with hashes. Add resume only if the spike shows a stage takes minutes. Delete the clip cache and scene-scoped reruns.
* **M5. Two extra human gates** beyond the decided approval: preview stage 4b with per-scene stills and scene-id reruns (line 218), and stage 8 review sign-off (line 222). D5 (line 158) decided one mandatory approval: the script.
  * Fix: keep D5 only. Make stage 8 a manifest note, not a gate. If a preview is wanted, one contact sheet with no per-scene approval or rerun.
* **M6. The brief schema is over-configured** (lines 82-87). Slice 1 has one engine, one preset voice, one style and English only, yet the schema exposes engine, voice, language, style and a music enum (YAGNI).
  * Fix: slice 1 schema is text, length_target_s, music as a boolean, out_name. Hard-code Kokoro, the preset voice, neutral style and English; record their values in the manifest (line 92).
* **M7. The reuse target does not exist.** Lines 94 and 96 say to reuse the Studio design's record shape and pattern. Studio status is "Design complete; awaiting egm-review" (`docs/designs/studio-and-collector-roles.md:4`). Its runs table is Piece 2, unbuilt. `router/store.py` creates only tasks and templates (lines 20-27).
  * Fix: remove "reuse" from lines 94 and 96. Define Mode B's own status file in the run folder, or list Studio Piece 2 as an explicit dependency with a go or no-go date.
* **M8. False premise in the observability bullet.** Line 141 says `/tmp/mgen` (`docker/media-generator/pipeline.py:157`) makes two runs collide. Each call uses `docker compose run --rm -T` (`router/media_generator_mcp.py:67-68`), which starts a new container. `/tmp` is private to each container.
  * Fix: delete the collision claim. A per-run temp directory is optional tidying.

## Nit

* **N1.** Mux reuse is missed. `kalamanch/pipeline/make_score.py mix` (lines 41-53) already ducks a bed under narration and encodes the final file. Its bed is dramatic (drone, riser, pulse), which conflicts with the neutral style (line 29). Fix: use mix if that bed is acceptable, or one simple ffmpeg amix line.
* **N2.** The image already ships `whisper-cli` with base.en (`docker/media-generator/Dockerfile:20-24`, WHISPER_MODEL_PATH at :70). Lines 174, 215 and 245 treat a local ASR model as new weight. Fix: use whisper-cli for the transcript check, or drop it for slice 1 and keep the duration check.
* **N3.** Stale text after decisions. Lines 76-78 still present the D3 options after D3 was decided (line 156). Lines 14-17 still list network and render-location conflicts as open, though D7 and D1 resolved them.
* **N4.** Stage lists disagree. Line 94 lists seven run states and stages; lines 212-222 list nine stages plus 4b. Keep one stage table.
* **N5.** Citation issues. Line 106 cites `handoff.md:616` for "host lacks ffmpeg, soundfile, HyperFrames, Chrome"; that line says only ffmpeg and ffprobe are missing. Line 94 cites `studio-and-collector-roles.md:131`; the run record is at :128. Check soundfile, HyperFrames and Chrome directly, or drop them.
* **N6.** Tolerances. Lines 87 and 171 say plus or minus 1.0 s; line 240 says tolerances come from the spike. Mark plus or minus 1.0 s as a placeholder.
* **N7.** The run folder location is undefined (lines 56, 61, 223). Define it, for example `Render/<out_name>.run/` resolved through `router/media_workspace.py media_dir()`.
* **N8.** Line 111 is misleading. `tests/test_media_workspace.py:63` compares against `mw.LAYOUT`, so a run folder under Render needs no new workspace folder.
* **N9.** Implementation detail in a concept brief: the venv and Python version (line 145) and font and colour-tween rules (line 217) belong in the task list (standard section 3).
* **N10.** Blocker labels are inflated. B1 and B3 are conditional on the GPU and on measured time. B4 is partly answered by the section 4 draft. B5 is a precondition, not a design blocker. Re-label as conditions or gates, each tied to a measured outcome.

## Limits

* Host installs (ffmpeg, soundfile, HyperFrames, Chrome) were not checked by running commands.
* Licences (B2, VoxCPM2) were not verified.
* The businessnext skill is absent from the repo, so its method is unverified.
* The image decision (B1) and the slice-1 pipeline size (M3 to M5) matter most before task 1 starts.
