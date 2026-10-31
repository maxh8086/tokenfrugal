"""Image-to-video with LTX-Video 2B distilled 0.9.8 (bf16 transformer, bf16 T5, 0.9.8 VAE).

Usage: python generate_ltx.py <photo> [out.mp4] [prompt]
Default output: video-editor/Render in OneDrive (VIDEO_EDITOR_DIR overrides)/ltx-video-2b-distilled.mp4
"""
import os
import sys
import time

import torch
from diffusers import (AutoencoderKLLTXVideo, FlowMatchEulerDiscreteScheduler,
                       LTXImageToVideoPipeline, LTXVideoTransformer3DModel)
from diffusers.utils import export_to_video, load_image
from PIL import Image
from transformers import T5EncoderModel

# shared helpers live in ../common (flat next to the script inside the container image)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from _models import require, use_models_dir  # noqa: E402

require("ltx-video-2b-distilled")  # asks before downloading anything missing
use_models_dir()  # model folders below are relative to the models folder
from _inputs import photo_path

BASE = "ltx-video-2b-distilled"
WEIGHTS = f"{BASE}/ltxv-2b-0.9.8-distilled.safetensors"
DISTILLED = [1.0, 0.9937, 0.9875, 0.9812, 0.975, 0.9094, 0.725, 0.4219]

photo = photo_path(sys.argv[1] if len(sys.argv) > 1 else None)
from _paths import render_dir
out_dir = str(render_dir())
os.makedirs(out_dir, exist_ok=True)
out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(out_dir, "ltx-video-2b-distilled.mp4")
prompt = sys.argv[3] if len(sys.argv) > 3 else "A person in a dark blazer looks at the camera and slowly nods."

text_encoder = T5EncoderModel.from_pretrained(f"{BASE}/text_encoder", torch_dtype=torch.bfloat16, device_map="cuda")
transformer = LTXVideoTransformer3DModel.from_single_file(WEIGHTS, torch_dtype=torch.bfloat16)
vae = AutoencoderKLLTXVideo.from_pretrained(f"{BASE}/vae_0.9.8", torch_dtype=torch.bfloat16)
pipe = LTXImageToVideoPipeline.from_pretrained(
    BASE, transformer=transformer, vae=vae, text_encoder=None, torch_dtype=torch.bfloat16
)
pipe.text_encoder = text_encoder

# Distilled checkpoint needs its fixed 8-step sigma schedule.
pipe.scheduler = FlowMatchEulerDiscreteScheduler.from_config(
    pipe.scheduler.config, use_dynamic_shifting=False, shift=1.0
)
_orig_set = pipe.scheduler.set_timesteps


def _set(num_inference_steps=None, device=None, sigmas=None, mu=None, **kw):
    return _orig_set(sigmas=DISTILLED, device=device)


pipe.scheduler.set_timesteps = _set
pipe.enable_model_cpu_offload()

# Centre-crop the source to the 512x704 portrait aspect instead of squashing it.
src = load_image(photo)
w, h = src.size
crop_w = int(h * 512 / 704)
left = (w - crop_w) // 2
image = src.crop((left, 0, left + crop_w, h)).resize((512, 704), Image.LANCZOS)

start = time.time()
frames = pipe(
    image=image, prompt=prompt, width=512, height=704, num_frames=65,
    guidance_scale=1.0, decode_timestep=0.05, decode_noise_scale=0.025,
    generator=torch.Generator(device="cuda").manual_seed(42),
).frames[0]
print(f"generation_seconds {time.time() - start:.1f}", flush=True)
export_to_video(frames, out_path, fps=24)
print("wrote", out_path, flush=True)
