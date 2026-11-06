# Mode B licence note

* **Checked:** 2026-11-02
* **Scope:** licences for the models and tools that Mode B (`media-briefing` tool, `media-motion` role) would use for slice 1.
* **Method:** read from the public registries listed below. Nothing was downloaded or installed for this check.

## Summary

| Item | Where it runs | Licence | Status |
|---|---|---|---|
| Kokoro-82M weights | Voice, slice 1 default (D2) | Apache-2.0 | Checked. Clear for commercial use with the licence notice kept. |
| `kokoro` Python package 0.9.4 | Voice, slice 1 | Apache-2.0 | Checked on PyPI. Pin it at the spike (task 4). |
| espeak-ng | Phonemiser used by Kokoro for words it does not know | GPL-3.0 | Open. Needs a distribution review (D11). |
| VoxCPM2 | Opt-in voice engine only | Apache-2.0 per `docs/designs/video-pipeline-use-cases.md:105` | Model-card licence not yet re-checked. VRAM not measured. Not used in slice 1. |
| HyperFrames 0.8.223 | Renders the picture, in the container | Check before distribution | Not checked in this note. |
| Whisper base.en (whisper.cpp) | Already in the media-generator image | Check before distribution | Not checked in this note. Not new weight. |
| Neutral music bed (task 8) | Written by our own code | Our code | No outside licence if generated from our own code only. |
| Fonts (D12) | Rendered text | Open-licence font required | Font not yet chosen. Record the licence when chosen. |

## Source checks

* **Kokoro-82M.** Hugging Face model card `hexgrad/Kokoro-82M`, licence field `apache-2.0`, at commit `f3ff3571791e39611d31c381e3a41a3af07b4987`, last modified 2025-04-10. Matches `docs/designs/video-pipeline-use-cases.md:108`.
* **kokoro (PyPI).** Latest version 0.9.4, licence Apache License 2.0, requires Python 3.10 or later. Pin the exact version at task 4, and record it in the manifest.
* **espeak-ng.** GitHub repository `espeak-ng/espeak-ng`, licence GPL-3.0. GPL-3.0 applies to the code we would ship or link. Using it as a separate program on the host is different from bundling it in the image. Task 4 must record which one applies.

## Open items

1. **espeak-ng (GPL-3.0).** Decide between: (a) keep it as a separate host program, not bundled in any image we ship, and record that in the design; (b) replace it with a phonemiser under a permissive licence. This is an owner decision under D11 before any image is distributed. Task 4 must also check whether the pinned Kokoro install pulls espeak-ng in as a dependency.
2. **VoxCPM2.** Re-check the model-card licence before any pin. Measure VRAM on this GPU (RTX 4060 Laptop, 8188 MiB total) before any choice. Not in slice 1.
3. **Fonts and the music bed.** Choose the font (D12) and record its licence. The music bed in task 8 is written by our own code, so it has no outside licence.

## Limits

* Licence text was read from registry metadata, not from the full licence files in each package. Check the full files before distribution.
* This note does not give legal advice. It records what the sources say.
