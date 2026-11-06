# Stage 8 Intermediate Zoom-Out Review: concepts_brief.md

* **Produced by:** `egm:egm-zoom-out` (read-only subagent `a7ffb070937655775`), REVIEW mode. The subagent could not write files, so its report came back as a message. This file holds that message, saved by the orchestrator.
* **Standard:** zoom-out-standard.md (section 0 objective; section 3 weeds).
* **Scope:** full file, lines 1 to 246. Reads Stage 5 (`zoom_out_report.md`), Stage 6 (`comprehension_report.md`) and Stage 7 (`critic_report.md`).
* **Status:** review only. No finding has been applied to `concepts_brief.md`.

## Main finding

The Stage 6 and Stage 7 fixes, applied as written, bring back most of the scope that Stage 5 cut. Stage 6 used the re-implementation standard, which asks for exact values in the brief. The zoom-out standard puts exact values in the task list. The brief should keep decisions, one-line interface names and gates. Exact contracts belong in a slice-1 task file written after you sign off.

## Stage 5 status

Brief text has not changed since Stage 5. Each Stage 5 item is still open unless listed as accepted below.

| Stage 5 item | Status |
|---|---|
| B1 task order and host venv vs D1 | Open. Stage 6 fixes task 4 only. |
| M1 one minute vs 20 to 30 s | Open in text. Stage 6 introduces a new conflicting value. |
| M2 GPU lease in slice 1 | Open. |
| M3 async run id and polling | Open. Stage 6 and 7 add more async detail. |
| M4 stage-gate machinery over-built | Open. Stage 6 adds to it. |
| M5 4b preview and stage 8 gates | Open. |
| M6 schema over-configured | Open. Stage 6 re-adds the fields. |
| M7 reuse target does not exist | Open. Stage 6 and 7 pick different answers. |
| M8 `/tmp/mgen` collision premise | Open. Stage 6 keeps it. |
| N1 `make_score.py mix` reuse missed | Open. |
| N2 whisper-cli already in image | Open. Stage 7 repeats the wrong premise. |
| N3 stale decision text | Open in text. |
| N4 stage lists disagree | Stage 6 B1 proposes a fix. Not applied. |
| N5 citations | Open. `handoff.md:616` does not mention soundfile, HyperFrames or Chrome. |
| N6 tolerance | Stage 6 M2 and Stage 7 D-F11 propose a fix. Not applied. |
| N7 and N8 run folder location, LAYOUT | Open. Stage 6 B10 proposes a conflicting location. |
| N9 implementation detail in brief | Open. Stage 6 adds more. |
| N10 blocker labels inflated | Open. Stage 6 adds ten blockers. |

**Accept as written from Stage 6 and 7:**
* One stage list (Stage 6 B1).
* Stage 0 script approval, one entry (Stage 6 B2, D5).
* Topic input returns an error in slice 1 (Stage 6 M9).
* `out_name_exists` error (Stage 6 M10).
* Tolerance +/-1.0 s marked as a placeholder (Stage 6 M2).
* Superseded decisions rewritten (Stage 6 M1).
* Pins written at the spike (Stage 6 M14).
* Lease removed from slice 1 (Stage 7 C-B1).
* Output contract as one table of values (Stage 6 B8).

## Blockers

* **Z-B1. Host and container split (lines 185-191, 154).** D1 puts Kokoro in the container. Task 3 measures "on this machine". Task 4 builds a Windows host venv. Task 7 says "in the chosen location". Stage 6 B3 fixes task 4 only.
  * Fix: rewrite tasks 3, 4 and 7 to run inside the Mode B image. Add a D1 addendum: the image is built FROM the digest at `docker-compose.yml:27`, plus one Kokoro layer. Add espeak-ng only if the phonemiser needs it. The apt list at `docker/media-generator/Dockerfile:14-16` does not include espeak-ng.
* **Z-B2. Stage 6 re-implementation fixes add scope (lines 94-96, 206-246).** The brief should carry decisions, one-line interface names and gates. Exact contracts belong in a slice-1 task file written after sign-off.
  * Fix: keep D1-D8 and the gates in the brief. Move schema fields, error strings, timeouts, palette, font, capture times, clip-cache hashing and pins into the slice-1 task file. Do not apply the reversals listed in M-2 to M-6 below.

## Majors

* **Z-M1. Word cap (line 81).** Stage 6 B7 proposes 1 to 300 words. At its own 2.5 words per second, 300 words is 120 s, four times the 30 s ceiling. Stage 5 M1 suggested 90. Stage 7 says 60 to 90.
  * Fix: max 90 words. Basis: 30 s x 2.5 words per second = 75, plus margin. Delete the 1200-word example.
* **Z-M2. Async pattern (lines 94-96).** Stage 6 M11 adds a `mode_motion_runs` table in `router/store.py` with a 10 s heartbeat, 60 s stale time and 5 s poll. `store.py` holds only tasks and templates (Stage 5 M7). The role timeout is 900 s (`router/tf-roles.yaml:43`), and its `max_steps` is 8, so polling every 5 s would use up the steps.
  * Fix: delete the state draft at line 94 and the reuse sentence at line 96. Keep one synchronous call. Use async only if the spike measures a run over about 600 s.
* **Z-M3. Per-stage timeouts (line 126).** Voice 300 s, scenes 60 s, render 600 s and mux 120 s sum to 1080 s. That is above the 900 s role timeout and the 900 s limit in `router/media_generator_mcp.py:15`. Voice also has one retry. The 1800 s whole-run cap is a further number with no basis.
  * Fix: remove the per-stage numbers and the 1800 s cap. Set one budget from the spike.
* **Z-M4. Preview gate and revise call (lines 212-230).** Stage 6 keeps stage 4b, with capture at act start +0.1 s, middle and end -0.1 s. It adds `mode_b_revise(run_id, scene_ids[])`, which reruns scenes. Stage 5 M5 said one contact sheet and no per-scene reruns.
  * Fix: keep D5 only. Drop 4b and the revise call. If a preview is wanted, make one contact sheet with no gate. Stage 8 becomes a manifest note.
* **Z-M5. Schema re-expanded (lines 82-88, 92).** Stage 6 B5, B7, M5 and M6 re-add engine, voice, language, style, music and seed. These are the fields Stage 5 M6 removed, and the error codes are for a single engine.
  * Fix: slice-1 schema is `text`, `length_target_s`, `music` as a boolean, and `out_name`. Kokoro, the preset voice id, English and the neutral style are constants recorded in the manifest. Drop `seed`; record "seed not supported" if Kokoro has none.
* **Z-M6. Weeds in the brief (lines 92, 217, 218).** Stage 6 adds a palette hex, a font path, a minimum font size, a template path, a 0.4 s pad, an act timing rule, a -18 dB bed mix, and `synthesize` and `render` signatures. Zoom-out standard section 3 classes these as weeds.
  * Fix: one line each. For example: "one neutral built-in palette and one bundled font; values in task N." "One scene per line; act length from the voice clip." The rest goes to the task file.
* **Z-M7. Run folder location (lines 56, 61, 223).** Stage 6 B10 proposes `media/mode-motion/runs/<run_id>/`. That path is outside `media_dir()` (`router/media_workspace.py:18-30`) and outside `LAYOUT` (line 15), and it needs a `LAYOUT` test change. Stage 5 N8 found that no change is needed if the run folder sits under Render, which is already in `LAYOUT`.
  * Fix: use `Render/<out_name>.run/`, resolved through `media_dir()`. The mgen Render diff counts files only (`router/media_generator_mcp.py:79`), so a subfolder does not disturb it. Make no `LAYOUT` change.
* **Z-M8. Collision premise is false (line 141).** Each mgen call runs `docker compose ... run --rm -T` (`router/media_generator_mcp.py:67-68`), which starts a new container. `/tmp` is private to each container, so two runs cannot collide there.
  * Fix: delete the collision sentence and drop the Stage 6 M20 test. Keep "run files go in the run folder."
* **Z-M9. Second render stack (lines 114, 143, 154).** Stage 6 M13 proposes a new `docker/media-motion/Dockerfile`. It does not say FROM the pinned image, so it would reinstall HyperFrames, Chromium and ffmpeg, which creates the second render stack line 114 warns about.
  * Fix: the Mode B Dockerfile is FROM the digest at `docker-compose.yml:27`, with only the Kokoro layer added. Record this in D1. Delete the line 114 paragraph once D1 is applied.
* **Z-M10. GPU lease still in slice 1 (lines 63, 122, 168, 189).** The Stage 5 M2 fix is not applied in these lines. The B1 text says "pid-based takeover", which applies only to kalamanch (`router/gpu_lease.py:231`). Other holders use `container_id` (`:233`). `acquire()` unloads Ollama (`:359`), so calling it for a CPU job has a side effect.
  * Fix: delete the lease sentence at line 63, B1 at line 122, task 5 at line 189 and the lease test at line 168. Reopen the lease when a GPU engine is enabled, then specify the `container_id` path.
* **Z-M11. Licence status (lines 124, 186, 198).** `docs/designs/video-pipeline-use-cases.md:108` records Kokoro-82M weights as Apache-2.0, checked 2026-11-02. The brief still calls the licence unverified. The open item is now the phonemiser: espeak-ng is GPL-3.0 (line 124) and is not in the image.
  * Fix: line 124 cites use-cases.md:108 for the weights and keeps only the espeak-ng licence and install as open. Narrow task 2 (line 186) to that.
* **Z-M12. Bed and mux duplicate existing code (lines 137-143, 215).** `kalamanch/pipeline/make_score.py` has `make_score(ff, seconds, out)` (line 26), which sets bed length from a duration, and `mix` (lines 41-49), which ducks the bed under narration. Stage 6 M8 specifies a new -18 dB mix with loop and trim, which duplicates both.
  * Fix: call `make_score` for the bed and `mix` for the ducked mux. If the dramatic bed does not suit the neutral style (line 29), use one ffmpeg `amix` line instead. Delete the -18 dB, loop and trim rules.

## Nits

* **Z-N1 (line 11).** The objective is text in and MP4 out, which meets zoom-out section 0. Add one sentence of rationale for "promotional and faceless content". Not a failed review.
* **Z-N2 (lines 215, 245).** The image already ships `whisper-cli` with base.en (`docker/media-generator/Dockerfile:20-24, :70`). The ASR model is not new weight. Correct the premise, or drop the check (Stage 6 M4 sets it to off for slice 1).
* **Z-N3 (section 3 or D1).** Remotion is already installed in the image (`Dockerfile:26`). One line should say why HyperFrames was chosen over it. Do not compare CosyVoice or OpenVoice in slice 1; Kokoro is decided.
* **Z-N4 (section 11).** Chromium `--no-sandbox` is a documented decision (`Dockerfile:66-68`). The OneDrive default is the Mode A default (`router/media_workspace.py:25-30`, `docker-compose.yml:32`). Add one risk line for each. Measure peak RAM in task 3 rather than adding `mem_limit` or a retention policy now. Do not add a security section.
* **Z-N5 (lines 106, 94, 224).** `handoff.md:616` does not support the line 106 claim. The Studio citation at `:131` was not checked. Drop both or check them.
* **Z-N6 (lines 120-132).** Keep the blockers as gates tied to measured outcomes. Only Z-B1 type items are true blockers.
* **Z-N7 (lines 60, 65, 114).** Stale after D1 and D7. Reword or delete.
* **Z-N8 (glossary, Stage 6 M18).** Do not add a glossary. Most terms (act, cue, 4b, colour tween, `_check()`) disappear once the Stage 5 cuts are made.
* **Z-N9 (section 12 placement, Stage 7 S-M16).** Move section 12 before the risks.

## Limits

* No command was run. Verified by reading the brief and the cited repo files only.
* The Studio citation at line 131 was not verified.
* `tests/test_media_workspace.py:63` was not verified.
* Licences were checked against `docs/designs/video-pipeline-use-cases.md` only, not upstream sources.
