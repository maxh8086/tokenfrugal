#!/usr/bin/env bash
# Fetch the approved low-VRAM ComfyUI model set into the folders the comfyui container maps.
#   T2I  -> models/image_generation/comfy-t2i/        (mounted at /image_models)
#   I2V  -> models/video_generation/                  (mounted at /models)
# Idempotent: curl resumes partial files (-C -) and skips files already complete.
# LTX-2 19B was dropped (about 24 GB for the full workflow, too large for 8 GB).
# Run from the repo root: bash scripts/fetch_comfy_models.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T2I="$ROOT/models/image_generation/comfy-t2i"
I2V="$ROOT/models/video_generation"
mkdir -p "$T2I/diffusion_models" "$T2I/text_encoders" "$T2I/vae" "$I2V/ltx-2b-gguf"

get() {  # get <hf_repo> <path_in_repo> <dest_file>
  local url="https://huggingface.co/$1/resolve/main/$2"
  echo "fetch $1/$2 -> $3"
  curl -fL --retry 5 -C - -o "$3" "$url"
}

# FLUX.2 klein 4B: fp8 transformer and VAE. The text encoder is not fetched here:
# the Qwen3-4B Q4_K_S GGUF comes from maxh8086/tokenfrugal-qwen3-4b-q4ks (see scripts/hf_models.py pull).
get black-forest-labs/FLUX.2-klein-4b-fp8 flux-2-klein-4b-fp8.safetensors "$T2I/diffusion_models/flux-2-klein-4b-fp8.safetensors"
get black-forest-labs/FLUX.2-klein-4B vae/diffusion_pytorch_model.safetensors "$T2I/vae/flux2-vae.safetensors"

# Mage-Flow text encoder: Qwen3-VL-4B FP8 (replaces the bf16 file, which stays until the FP8 run is verified)
get Qwen/Qwen3-VL-4B-Instruct-FP8 model-00001-of-00002.safetensors "$T2I/text_encoders/qwen3vl-4b-fp8-00001.safetensors"
get Qwen/Qwen3-VL-4B-Instruct-FP8 model-00002-of-00002.safetensors "$T2I/text_encoders/qwen3vl-4b-fp8-00002.safetensors"

# SDXL-Turbo GGUF Q8_0 (lightest SDXL option; needs ComfyUI-GGUF, present in the image)
get OlegSkutte/sdxl-turbo-GGUF sd_xl_turbo_1.0.q8_0.gguf "$T2I/diffusion_models/sd_xl_turbo_1.0.q8_0.gguf"

# LTX-Video 2B v0.9 GGUF Q8_0 (best-quality quantized LTX GGUF found; the 0.9.8 transformer stays bf16 until a 0.9.8 GGUF is made)
get city96/LTX-Video-gguf ltx-video-2b-v0.9-Q8_0.gguf "$I2V/ltx-2b-gguf/ltx-video-2b-v0.9-Q8_0.gguf"
get city96/LTX-Video-gguf LTX-Video-VAE-BF16.safetensors "$I2V/ltx-2b-gguf/LTX-Video-VAE-BF16.safetensors"

echo "done"
