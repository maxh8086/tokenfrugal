# Mode B HyperFrames render spike (silent)

* **Date:** 2026-11-02
* **Task:** section 10, task 6 (silent HyperFrames render at target length in the media-generator image).
* **Image:** `maxh8086/video-editor:1@sha256:6c222cd6518427127a5fd2fc125e9a5fa2ceb0e27d6f1a7bd4bc79abf90d3e94` (HyperFrames 0.8.223).
* **Project:** `scratchpad/hf_spike/hf_proj` (scaffolded with `hyperframes init --non-interactive --example blank --resolution landscape --skip-skills`, then `index.html` replaced by a 25 s composition: two text elements, one bar, GSAP 3.15.0 from jsdelivr, no audio).
* **Output:** `scratchpad/hf_spike/renders/hf_silent_25s.mp4` (286,975 bytes).

## Result

| Check | Value | Result |
|---|---|---|
| `hyperframes lint .` | 0 errors, 0 warnings | Pass |
| Video stream | h264, 1920x1080, 30/1 fps | Pass |
| Audio streams | 0 | Pass |
| Duration | 25.000000 s (target 25 s, tolerance ±1.0 s) | Pass |
| Frame count | 750 | Pass |
| Wall time | about 21 s, including container start | Recorded |

## Notes

* The render log had a non-blocking 404 resource warning. It did not stop the render. The composition should not depend on a remote asset that can 404 at render time (D12 and the no-network-at-render rule). Find the 404 URL before the full template is built.
* HyperFrames reported that the project pins `hyperframes@0.8.223`, while 0.9.3 is the latest release. The image pins 0.8.223, so no change is needed now. Upgrading is a separate decision.
* The subagent's own exit-code capture failed because of a shell-quoting issue. The file and ffprobe results were re-checked directly by the orchestrator.

## What this means for the brief

Silent render at the target length works in the existing image, with no new image needed. Task 7 (mux narration and bed) can take this file as its video input.

## Task 7: narration mux

* **Output:** `scratchpad/hf_spike/renders/hf_narrated_25s.mp4` (909,735 bytes).
* **sha256:** `ca45092aa0b33da24cac205b98c1580b24ea12e3d61ba92fc8abe591cf9970d8`.
* **Command:** video stream copied; narration `scratchpad/narration_spike.wav` encoded AAC 192k, 48 kHz, stereo; `-shortest`, so the 25.20 s narration is trimmed to the 25.00 s video.
* **Streams:** h264 1920x1080, 30/1, 750 frames; aac 48000 Hz, 2 channels. Format duration 25.067 s.
* **Loudness:** integrated -25.6 LUFS, LRA 2.2 LU, true peak -9.4 dBFS. This is quiet against the usual -16 to -23 LUFS narration range. It is a spike take with one voice, so the level gate (task 8 / D13) is still open.
* **Bed:** not included. The neutral music bed is task 8.

## Task 8: neutral music bed (D10)

* **Generator:** `scratchpad/hf_spike/make_bed.py` (new code; `make_score.py` not used). Run as `.venv-voice\Scripts\python.exe -I scratchpad\hf_spike\make_bed.py 25.0 scratchpad\hf_spike\renders\bed.wav`.
* **Content:** C major pad (C3, E3, G3), low sine partials, 0.1 Hz swell, 2 s fades. No noise, pulse or riser. Deterministic.
* **Output:** `scratchpad/hf_spike/renders/bed.wav`, sha256 `efb5c4e356a16879c893012086301009cdc1b8ce47453208ba9545f3b338b7ba`. 25.000 s, mono, 48 kHz, PCM 24-bit.
* **Loudness (before normalisation):** integrated -22.7 LUFS, true peak -12.0 dBFS, mean -21.8 dB.
* **Manifest:** `scratchpad/hf_spike/manifest.json` lists the bed and the narration source with its sha256.
* **Not done yet:** the bed is not mixed into the narrated file. The mix level (proposed -18 dB under narration) and the level gate are part of task 9 / D13.

## Task 9: stills gate (D13 point 3), spike stills

* **Stills:** `scratchpad/hf_spike/renders/stills/` holds `still_00.png` (0.5 s), `still_01.png` (12.5 s), `still_02.png` (24.5 s) and `contact_sheet.png` (three tiles, 1920x360). Hashes are in `manifest.json` under `stills_gate`.
* **Status:** `approved_spike_only`. The owner approved these spike stills on 2026-11-02. This does not approve the real-template stills gate (D13), which is still open.
* **Finding 1: the first still is blank.** At 0.5 s the title has not animated in yet, so the first tile is only background.
* **Finding 2: stills 12.5 s and 24.5 s are byte-identical.** The title and bar do not move after the intro, so the spike composition has no motion for most of its length. Stills at fixed times cannot show a problem that is not there, so this gate is weak as a check.
* **Limit:** this spike is one scene and not the real three-scene template (D12). The gate for the real film needs one still per scene, as D13 requires. These spike stills only confirm the pipeline produces images.
