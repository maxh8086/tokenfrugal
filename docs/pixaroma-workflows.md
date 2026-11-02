# Pixaroma ComfyUI workflows: local notes

Source: https://workflows.pixaroma.com/ (free ComfyUI workflow files, one set per course episode). Each episode page has a "Download workflows" zip and a "Watch on YouTube" link. Downloaded zips are kept in the scratchpad, not in the repo.

## Episode index (40 episodes, as listed 2026-10-30)

Video, audio and talking-head episodes first. Image-only and node-only episodes are listed at the end.

| Ep | Topic | Type | Workflows | Relevance to KalaManch |
|---|---|---|---|---|
| 35 | MiniMax FastH3, text to video and image to video | Video | 3 | Cloud model (MiniMax), not local |
| 34 | Pixal3D multiview, load and save 3D | 3D | 7 | Not relevant |
| 33 | Image to 3D: Trellis 2 + Pixal3D | 3D | 7 | Not relevant |
| 32 | MiniMax H3 speed LoRA and VRAM monitor | Video | 5 | Speed LoRA idea for video |
| 31 | MiniMax Music 3 and local AI prompt generator | Audio | 5 | Music bed |
| 29 | MiniMax H3: best video generation workflows | Video | 11 | Reference only |
| 23 | Scail 2 video: WiFi nodes, loops | Video | 7 | Multi-character video |
| 19 | Stable Audio 3: AI music and SFX | Audio | 4 | Music and SFX |
| 15 | Images react to music, ACE-Step music | Audio | 2 | Music |
| 10 | Fish Audio S2 text to speech | Audio | 3 | Check licence before commercial use |
| 7 | Qwen3-TTS voice clone and custom voice design | Audio | 8 | Voice clone candidate |
| **6** | **InfiniteTalk + Wan 2.2 + Scail + LTX-2** | **Video** | **17** | **Talking-head lip-sync, long-form extend. Key episode** |
| 5 | Upscale images | Image | 8 | Upscale step |
| 2 | Nunchaku tutorial | Image | 3 | Quantised model loading |
| 1 | ComfyUI course | Basics | 9 | Reference |

Image-only episodes (not for this pipeline): 39, 38, 37, 36, 30, 28, 27, 26, 25, 24, 22, 21, 20, 18, 17, 16, 14, 13, 12, 11, 9, 8, 4, 3.

## Episode 6 in detail (the talking-avatar pipeline)

Zip: `Ep06 Workflows.zip`, 173 KB, 17 workflow JSON files. Downloaded to `scratchpad\pixaroma\ep06_zip\Ep06.zip` on 2026-10-30.

### Wan InfiniteTalk (lip-sync, image plus audio to video)

Five variants by clip length: 4-6 s, 7-9 s, 10-11 s, and two extend workflows.

- **Easy Extend, 3 to 34 s**: 121 nodes, 12 chained `WanInfiniteTalkToVideo` stages, 12 `KSampler` stages, 12 `VHS_VideoCombine` outputs. Each stage makes 81 frames and feeds the next. This is how the long-form case is handled.
- **Manual Extend, 3 to 34 s**: the same chain with the bypass switches exposed by hand.

Models used by the Easy Extend workflow:

| Role | File in workflow | Size class | Local status |
|---|---|---|---|
| Base video model | `wan2.1\Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` | 14B, fp8 | **Not present.** Local models are Wan 2.1 T2V 1.3B, VACE 1.3B, Wan 2.2 TI2V 5B. |
| Speed LoRA | `wan2.2\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` | 4-step distill | Not present; tied to the 14B base |
| Audio patch | `wan2.1_infiniteTalk_single_fp16.safetensors` (ModelPatchLoader) | InfiniteTalk | Not present |
| Audio encoder | `wav2vec2-chinese-base_fp16.safetensors` | wav2vec2 | Not present; OmniAvatar uses `wav2vec2-base-960h` |
| Text encoder | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | UMT5-XXL fp8 | Local copy exists in the Wan 2.2 folder (bf16 shards) |
| VAE | `Wan2_1_VAE_bf16.safetensors` | Wan 2.1 VAE | Local copy exists in the VACE folder |

Sampler settings in the workflow: `KSampler` with 4 steps, cfg 1, `euler`, `normal` scheduler. Resolution 832x480 (16:9) or 480x832 (9:16). Frame count 81 per stage. Output `VHS_VideoCombine` at 25 fps, H.264, CRF 19.

Inputs the workflow expects (these are the "answers" to reproduce):
- `LoadImage`: the still portrait (example file `InfiniteTalkMan.jpg`).
- `VHS_LoadAudioUpload`: the voice track (example `ManVoice42Sec.mp3`, 42 s, start 0, duration 0 = whole file).
- `CLIPTextEncode`: the prompt (example "the character is talking").
- `PrimitiveInt` x2: width and height.

The workflow includes a note on matching width and height to the image aspect ratio (9:16 = 480x832, 720x1280; 16:9 = 832x480, 1280x720; 1:1 = 512x512, 640x640, 768x768).

### Other Episode 6 workflows

- **Wan 2.2 Image to Video** and **+ LoRA**: Wan 2.2 14B I2V, not the 5B TI2V model we have locally.
- **Wan 2.2 Animate** (5 variants, 16 and 24 fps, HD): replace the character or the background in an existing video. Needs a driving video. Large graphs (about 100 KB each).
- **Wan Scail** (2 variants): single or multi-character image to video.
- **LTX-2** Image to Video with Audio and with Custom Audio: LTX-2 (not LTX 0.9.8), which carries the audio in the model.
- **Video Upscale SeedVR2**: video upscale.

## Local comparison: what we have against what the workflows need

| Pipeline step in the workflows | Workflow model | Our local equivalent | Gap |
|---|---|---|---|
| Talking-head lip-sync | Wan 2.1 I2V 14B + InfiniteTalk | OmniAvatar 1.3B (Wan 2.1 T2V 1.3B base), MuseTalk (lip-sync only) | 14B does not fit 8 GB. Our lip-sync is OmniAvatar, which is a different model. |
| Long-form extend (3 to 34 s) | 12 chained stages with last-frame conditioning | `kalamanch/pipeline/chain_gen.py` (video only, no audio input) | `chain_gen.py` cannot host OmniAvatar or lip-sync. It needs a new back end that takes audio. Its `hybrid` mode also crashes with wan22: `run()` does not accept `tail=` (`chain_gen.py:98` vs `:70`). |
| 4-step speed | lightx2v LoRA | none | Would need a 1.3B-compatible distill LoRA |
| Audio encoder | wav2vec2 chinese base | wav2vec2-base-960h (OmniAvatar) | Different encoder: outputs will differ |
| Upscale | SeedVR2 | Real-ESRGAN x4plus, GFPGAN (scratchpad face test) | Different upscaler |
| Voice clone | Qwen3-TTS (ep 7) | none yet | Licence check pending: OpenVoice V2 (MIT), VoxCPM2 (Apache-2.0), CosyVoice2 (Apache-2.0 on mirrors) |

Conclusion for the 1:1 reproduction request: the exact Ep 6 InfiniteTalk output needs the 14B Wan 2.1 I2V base plus the InfiniteTalk patch. That is not on this machine and does not fit 8 GB. Any non-ComfyUI reproduction is therefore a substitute model, so the output will match in structure and inputs but not byte for byte.

## Opus review (2026-10-30, hand-back from a subagent)

- Fatal if wrong: lip-sync source. ComfyUI drives the whole frame from audio. Locally that is OmniAvatar 1.3B (end to end) or MuseTalk pasted over a silent video (mouth crop only, so seams and flicker are possible).
- Extend drift: the audio offset per stage must be (frames kept so far) / fps. wan22 runs at 16 fps; ComfyUI and MuseTalk use 25. Check frame counts with ffprobe and a click track.
- Memory: 20 s is about 7 stages of 81 frames. Time one stage per candidate and watch peak VRAM.
- Recommended first test: OmniAvatar 1.3B end to end, 480x832, 25 fps, using the image, audio and prompt from the workflow. Fallback: Wan 2.2 5B `anchor` mode, then MuseTalk v1.5.
- Do not claim "same output". The most we can say is "equivalent by spec", and only after: a reference render exists (none found on disk), same inputs, 25 fps H.264 CRF 19, audio-video offset of 1 frame or less at 0, 10 and 20 s, ArcFace identity above an agreed threshold, LSE-C/D within a margin, and no visible seams.
- InfiniteTalk is trained for 14B (hidden size 5120 vs 1536 for 1.3B). It almost certainly will not load on the 1.3B base [unverified].

## Open questions for brainstorm

1. Can the InfiniteTalk patch be applied to the 1.3B Wan 2.1 base (OmniAvatar's base) without the 14B weights? Needs a check of the patch's input dimensions.
2. Which of the 1.3B models gives the closest lip-sync: OmniAvatar 1.3B or MuseTalk v1.5?
3. The extend chain: is last-frame conditioning from `chain_gen.py` equivalent to the workflow's `ImageFromBatch` plus `BatchImagesNode` chain?
4. Voice: Qwen3-TTS (ep 7) against OpenVoice V2 or VoxCPM2 for a licence-safe clone.
