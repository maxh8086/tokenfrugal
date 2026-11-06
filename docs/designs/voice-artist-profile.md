# Voice artist profile: default narrator

Scope: the default narration voice for the mediahouse pipeline. It is a designed voice from a preset. It is not a copy of any real person, and it has no reference clip.

## Settings

| Setting | Value |
|---|---|
| Engine | Kokoro-82M (ONNX), `kokoro-onnx` 0.6.1 |
| Voice id | `af_heart` |
| Speed | 1.0 |
| Language | English |
| Reference clip | none |
| Consent note | Not needed. Preset voice, no reference clip of a real person. |
| Measured rate | 2.94 words per second (74-word passage, 25.20 s, see [mode-b-voice-spike.md](mode-b-voice-spike.md)) |
| Device | CPU in the current voice image. A GPU voice image is planned (mediahouse plan, Workstream E item 5). |

## Use

- Narration length is set from the measured rate. A 120 s clip needs about 350 words.
- Record the voice id and engine in each clip's sidecar file.
- Character-specific profiles go in `docs/designs/voice-artist-<name>.md`. This file is the fallback when a task names no voice.
