# Talking-avatar model recommendations (8 GB GPU)

Reviewed on 2026-10-30 from the Hugging Face model cards and the linked GitHub READMEs. Nothing here has been run on this machine yet. Every VRAM figure below is the author's claim, not our measurement.

Target: one reference photo plus one voice clip (20.9 s), keep the face in frame and the identity stable, expressive face and hand gestures, output at 30 and 60 fps.

## Summary

| Model | Audio lip-sync | Base model | License | Stated VRAM | Fit on 8 GB | Recommendation |
|---|---|---|---|---|---|---|
| OmniAvatar-1.3B (ours) | Yes | Wan2.1-T2V-1.3B | Not stated on card | Card table covers 14B only | Yes, already runs | Keep as baseline until a replacement is measured |
| AvatarForcing | Yes | Wan2.1-T2V-1.3B | Not stated on card | Not stated | Probably, unverified | Trial next: same base as ours, targets long-form stability |
| MultiTalk | Yes (multi-person) | Wan2.1-I2V-14B-480P | Apache-2.0 | 8 GB only via Wan2GP (community) | Only with heavy offload | Consider, but slow |
| InfiniteTalk | Yes | Wan2.1-I2V-14B-480P | Apache-2.0 | Low-VRAM mode in repo; 8 GB via Wan2GP | Only with heavy offload | Best long-video option, but slow |
| MiniMax H3 | Yes (co-generates speech) | Custom, Qwen3-VL-32B text encoder | Custom; excludes EU, UK, Korea, US | Not stated | Unlikely | Not recommended for us |

## Per model

### 1. OmniAvatar-1.3B (baseline)
- **Source:** [OmniAvatar/OmniAvatar-1.3B](https://huggingface.co/OmniAvatar/OmniAvatar-1.3B). Settings we use are in `omniavatar-1.3b/` (`num_steps: 50`, `guidance_scale: 4.5`, `fps: 25`, `overlap_frame: 13`).
- **Memory:** the card's VRAM table covers the 14B model only. There is no 1.3B figure on the card, so our own timing is the reference. Step time was not recorded in this document.
- **Limit we hit:** the 50-step run finished denoising, then lost its output to the Windows `cp` bug. `io_utils.py` now uses `shutil.copyfile`, but the fix has not been verified by a full rerun.

### 2. AvatarForcing
- **Source:** [lycui/AvatarForcing](https://huggingface.co/lycui/AvatarForcing) (paper: arXiv 2603.14331).
- **What it is:** a one-step streaming talking-avatar model. It takes one reference image, speech audio and an optional text prompt, and uses sliding-window denoising with dual-anchor temporal forcing for long-form stability.
- **Setup from the card:** needs `Wan-AI/Wan2.1-T2V-1.3B` as the base, `facebook/wav2vec2-base-960h` as the audio encoder, and the two checkpoints `ode_audio_init.pt` (ODE stage) and `model.pt` (DMD stage).
- **Why it matters:** it uses the same 1.3B base and audio encoder as our OmniAvatar setup, so it may be a drop-in test. The "long-form stability" claim targets the drift we saw.
- **Gaps:** the card gives no VRAM figure, no GPU requirement and no license. The inference code is not in the HF repo, so we would need its GitHub repo. Treat it as unverified until we run it.

### 3. MultiTalk (MeiGen-AI)
- **Source:** [MeiGen-AI/MeiGen-MultiTalk](https://huggingface.co/MeiGen-AI/MeiGen-MultiTalk) and [GitHub](https://github.com/MeiGen-AI/MultiTalk).
- **What it is:** audio-driven, supports single and multi-person conversation, 480p and 720p, up to 15 s. Apache-2.0.
- **Base model:** `Wan-AI/Wan2.1-I2V-14B-480P`. The MultiTalk weights are linked over the base model's files, so the base is required.
- **Memory:** the repo has a `--num_persistent_param_in_dit 0` low-VRAM mode and says it runs 480p on a single RTX 4090. The community project Wan2GP is credited with running it on 8 GB.
- **Best practice:** the repo's low-VRAM flag is the entry point for an 8 GB card. Expect slow generation.

### 4. InfiniteTalk (MeiGen-AI)
- **Source:** [MeiGen-AI/InfiniteTalk](https://github.com/MeiGen-AI/InfiniteTalk) (HF page links the same family).
- **What it is:** audio-driven long-video talking generation with unlimited-length video-to-video and up to 1 minute of image-to-video.
- **Quality notes from the README:**
  - Image-to-video holds up to about 1 minute; colour shift grows beyond that. Our clip is 21 s, well inside that range.
  - The FusionX LoRA worsens colour shift and reduces ID preservation.
  - Image-to-video can be helped by zooming or translating the image; the repo includes `tools/convert_img_to_video.py`.
- **Memory:** `--num_persistent_param_in_dit 0` low-VRAM mode is in the repo. Wan2GP is credited with 8 GB support.
- **License:** Apache-2.0.

### 5. MiniMax H3
- **Source:** [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) (repackaged for ComfyUI) and [MiniMaxAI/MiniMax-H3](https://huggingface.co/MiniMaxAI/MiniMax-H3).
- **Concerns:**
  - **License territory:** the license excludes the EU, UK, Republic of Korea and the United States. Confirm the user's jurisdiction before any use.
  - **Size:** the text encoder is Qwen3-VL-32B, which alone is far larger than 8 GB even when quantized. Heavy offload would be needed, and generation would be slow.
  - **Commercial terms:** a separate MiniMax authorization is needed above US$20M annual revenue.
- **Recommendation:** not for this project.

## Best practices for any Hugging Face model here

1. **Read the card before downloading.** Check the license (some are Apache-2.0, some are custom or territory-limited), whether access is gated, the base model, and any VRAM figures.
2. **Pin the revision.** Download a specific commit hash, not `main`, so an update cannot silently change the output. Record the hash in `fetch_models.py`.
3. **Prefer `.safetensors`.** Avoid repos that need `trust_remote_code` unless you have read the code.
4. **Keep weights out of git.** `fetch_models.py` already does this; the model folders are gitignored.
5. **Memory on 8 GB:** use the repo's low-VRAM flag first (`num_persistent_param_in_dit 0` in the Wan-based repos). Diffusers guidance adds quantization, group offloading, and VAE tiling and slicing. Sequential CPU offload saves the most memory but is slowest.
6. **Judge quality on the whole clip.** Sample frames at 0, 10 and 20 s. The blank NimVideo clip passed a check of only its first seconds.
7. **Measure identity.** Compare face embeddings between the photo and sampled frames over time.

## Recommended next steps (in order)

1. Trial **AvatarForcing** against our OmniAvatar baseline, using the same photo and audio. It needs its GitHub inference code, which we have not reviewed yet. Measure identity and VRAM.
2. If AvatarForcing is not better, trial **InfiniteTalk** in its low-VRAM mode. Expect slow runs, so start with a short clip.
3. Keep **OmniAvatar** as the baseline, and finish its rerun at 25 or 50 steps first.
4. Skip **MiniMax H3** unless the license and VRAM facts change.

## Open questions

- AvatarForcing: VRAM, license and inference code location.
- MultiTalk and InfiniteTalk on 8 GB: real speed at 21 s, measured here.
- Which license applies to OmniAvatar; the card does not state one.
- The user's jurisdiction, for the MiniMax H3 license.

## Sources
- [AvatarForcing model card](https://huggingface.co/lycui/AvatarForcing)
- [OmniAvatar-1.3B model card](https://huggingface.co/OmniAvatar/OmniAvatar-1.3B)
- [MeiGen-MultiTalk model card](https://huggingface.co/MeiGen-AI/MeiGen-MultiTalk)
- [MultiTalk GitHub](https://github.com/MeiGen-AI/MultiTalk)
- [InfiniteTalk GitHub](https://github.com/MeiGen-AI/InfiniteTalk)
- [InfiniteTalk model card](https://huggingface.co/MeiGen-AI/InfiniteTalk)
- [MiniMax H3 ComfyUI repack](https://huggingface.co/Comfy-Org/MiniMax-H3)
- [MiniMax H3 license](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE)
