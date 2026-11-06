# Mode B voice spike (Kokoro-82M, host)

* **Date:** 2026-11-02
* **Task:** section 10, task 3 (measure VRAM and time for a 25 s Kokoro narration).
* **Machine:** RTX 4060 Laptop GPU, 8188 MiB total. 775 MiB used before the run.
* **Script:** `scratchpad/voice_spike.py`. Output: `scratchpad/narration_spike.wav`.
* **Venv:** `.venv-voice` (Python 3.11.9). Pinned freeze: `scratchpad/voice-venv-freeze.txt`.

## Pinned versions

| Package | Version | Licence |
|---|---|---|
| kokoro | 0.9.4 | Apache-2.0 |
| misaki | 0.9.4 | see the package metadata before distribution |
| espeakng-loader | 0.2.4 | bundles espeak-ng (GPL-3.0). Open, see the licence note |
| torch | 2.6.0+cu124 | BSD-style |
| en-core-web-sm | 3.8.0 | MIT (installed as a dependency at first run) |
| Kokoro-82M weights | HF commit `f3ff3571791e39611d31c381e3a41a3af07b4987` | Apache-2.0 |

## Measurements

Passage: 74 words, voice `af_heart`, speed 1.0, English.

| Measure | Value |
|---|---|
| Audio length | 25.20 s |
| Words per second | 2.94 |
| Model load | 8.15 s (first run also downloaded weights and spaCy model) |
| Synthesis | 4.00 s |
| Real-time factor | 0.16 |
| Peak GPU memory allocated | 1015 MiB |
| Peak GPU memory reserved | 1218 MiB |
| Peak loudness | -6.4 dBFS |
| RMS loudness | -25.8 dBFS |

## What this means for the brief

* **VRAM.** Kokoro takes about 1.0 to 1.2 GB of GPU memory at this length. That is far below the 6 GB floor in the GPU lease, so the lease is not needed for voice (consistent with removing it from slice 1).
* **Time.** Synthesis is about six times faster than real time. A 30 s narration takes about 5 s, so voice is not a time risk for the 900 s budget.
* **Rate.** Kokoro gives 2.94 words per second. The 90-word cap (about 30 s) holds at this rate.
* **Loudness gate.** The first draft of the gate uses -6 dBFS peak as a ceiling and -26 dBFS RMS as the narration level. These come from one take and one voice, so they are a starting point for the stills and sample gates (D13), not a final standard.
* **Not measured.** Peak system RAM during the run was not recorded. The synthesis wall time above includes CPU work for phonemising. The spike used one voice only.

## Licence notes from this spike

* `espeakng-loader` installs a bundled espeak-ng. Its GPL-3.0 licence applies to distribution, so the review in D11 is still needed.
* `en-core-web-sm` was pulled in automatically by kokoro's install (spaCy model, MIT). Pin it with the rest in task 4.
