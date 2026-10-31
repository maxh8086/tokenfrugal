# Video model evaluation for the 8 GB card

Machine: 8 GB VRAM, 31 GB RAM, Windows. Task: talking-avatar and image-to-video, a 20 s clip from one portrait photo (anchored 4 s segments, new seed each, 4-frame cross-fade). Last updated 2026-10-31. Test models were deleted after recording; the three winners and MuseTalk stay on disk.

## Best model

**Wan 2.2 TI2V 5B Turbo (Q4_K_M)** for general image-to-video: 289 s for 20 s, identity kept. **LTX 0.9.8 2B distilled with FP4 T5** is the fastest (105 s for 20 s, near perfect per the user), so use it when speed matters most. **OmniAvatar 1.3B** is the only one with audio-driven lips, so it stays for talking avatars.

## Results

| Model | Time (20 s clip) | Verdict |
|---|---|---|
| LTX 0.9.8 2B distilled, FP4 T5 | 105 s | Near perfect. Fastest. |
| LTX 0.9.8 2B, FP8 T5 / bf16 T5 | 217 s / 242 s | Near perfect, same identity. |
| LTX 0.9.8 2B, GGUF T5 | 427 s | Same quality, slower (dequantised at load). |
| LTX 0.9.6 GGUF (15 s clip) | 179.8 s | Clean; eyes slightly half-closed at 10 s. |
| Wan 2.2 TI2V 5B Turbo Q4_K_M, 4 steps | 289 s | Strong. Identity kept, natural hands. |
| Wan 2.2 TI2V 5B Q4_K_M, 30 steps | about 2000 s | Near perfect, but 7x slower than Turbo. |
| OmniAvatar 1.3B | not re-timed | Near perfect, drives lips from audio. |
| Wan 2.2 Fun 5B InP | 1456.8 s | Rejected: face drift. |
| LTX 0.9.8 13B Q4_K_M | 1889.5 s per 4 s segment | Impractical (spills past 8 GB). |
| HunyuanVideo 1.5 480p | 446 s per step | Impractical (days for 20 s). |
| Kandinsky 6.0 Lite | 559 s per step | Impractical (VRAM spill). |
| CogVideoX1.5 5B I2V | failed | nf4 gave green noise, 8-bit ran 600 s per step. |
| Wan 2.2 I2V A14B Q4_K_S | 30 s per step at 320x576, 33 frames | Impractical at 480x832 (about 5x the tokens). Identity kept in the smoke frame. |
| Wan 2.1 VACE 14B | not run | Skipped: same 14B class as A14B, inferred to spill the same way. |
| anonymous-s2v/s2v-2b-realtime | not run | Blocked: no code or pipeline released. |
| humo-gguf | not run | Excluded: needs more disk than free. |

## Quality pipeline for the LTX clip (2026-10-31)

Best result so far, in this order:

1. **Calm prompt (v3).** The "loud, emphatic" gesture wording caused extra fingers and jittery eyes. Describe relaxed arms, hands low and still, slow natural blinks and a steady gaze. LTX FP4, 20 s clip: 141.7 s.
2. **LivePortrait expression retarget** (humans mode, bundled driver `d9`, source = the LTX clip). Face expression, eyes and head follow the driver; the body and background are unchanged. User verdict: much improved. Needs ffmpeg and ffprobe on PATH, `PYTHONUTF8=1` on Windows, and `onnxruntime-gpu` 1.19.2 (1.18 wants cuDNN 8). Weights about 630 MB.
3. **Optional finishing:** Real-ESRGAN general-x4v3 plus GFPGAN 1.4 at weight 0.5, 373.8 s, output 1024x1408. GFPGAN alters eyes and skin and Real-ESRGAN can leave edge halos, so use a lower weight (about 0.3) or skip it after LivePortrait.

Driver clip: the bundled examples work, but a calm talking clip of the user would be best. The driver's mouth is not tied to the audio.

OmniAvatar 1.3B, 4 s test (TeaCache 0.14, cfg 2.5, 20 steps): good expression, blinks and hands, but 1490 s, so about 2x slower per second of video than the earlier run. Not recommended for 20 s clips.

## Effort to use

- LTX 2B: one pipeline, one model plus T5. FP4 T5 needs encode-once-then-free code.
- Wan 5B GGUF: diffusers `from_single_file` plus a UMT5 encoder; the 8-bit encoder needs the same encode-once step.
- OmniAvatar: its own repo and audio encoder.
- Everything impractical above needed custom loaders or patches and still failed on speed.

## Not decided

MuseTalk (`lipsync/`, about 10 GB) is untested. Deleting earlier-model variants (LTX bf16 T5 shards, Wan bf16 UMT5, older VAE folders) is left to the user.
