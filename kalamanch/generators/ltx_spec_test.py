"""LTX-Video 2B distilled 0.9.8 per spec: 704x512, 97 frames, 24 fps, 8 steps, CFG 1.0, strength 0.5."""
import os
import sys
import time

import torch
from diffusers import AutoencoderKLLTXVideo, FlowMatchEulerDiscreteScheduler, LTXConditionPipeline, LTXVideoTransformer3DModel
from diffusers.pipelines.ltx.pipeline_ltx_condition import LTXVideoCondition
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
TIMESTEPS = [1000, 993, 987, 981, 975, 909, 725, 0.03]  # distilled 8-step schedule

photo = photo_path(sys.argv[1] if len(sys.argv) > 1 else None)
from _paths import render_dir
out_dir = str(render_dir())
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, sys.argv[2])  # written straight to video-editor/Render, no project copy
prompt = sys.argv[3] if len(sys.argv) > 3 else "A man in a dark blazer stands still and looks at the camera."
W, H, N = 704, 512, 97

text_encoder = T5EncoderModel.from_pretrained(f"{BASE}/text_encoder", torch_dtype=torch.bfloat16, device_map="cuda")
transformer = LTXVideoTransformer3DModel.from_single_file(WEIGHTS, torch_dtype=torch.bfloat16)
vae = AutoencoderKLLTXVideo.from_pretrained(f"{BASE}/vae_0.9.8", torch_dtype=torch.bfloat16)
pipe = LTXConditionPipeline.from_pretrained(
    BASE, transformer=transformer, vae=vae, text_encoder=None, torch_dtype=torch.bfloat16
)
pipe.text_encoder = text_encoder
pipe.scheduler = FlowMatchEulerDiscreteScheduler.from_config(pipe.scheduler.config, use_dynamic_shifting=False, shift=1.0)
pipe.enable_model_cpu_offload()

src = load_image(photo)
w, h = src.size
crop_w = int(h * W / H)
left = (w - crop_w) // 2
image = src.crop((left, 0, left + crop_w, h)).resize((W, H), Image.LANCZOS)

start = time.time()
frames = pipe(
    conditions=[LTXVideoCondition(image=image, frame_index=0, strength=0.5)],
    prompt=prompt, width=W, height=H, num_frames=N, frame_rate=24,
    timesteps=TIMESTEPS, guidance_scale=1.0,
    decode_timestep=0.05, decode_noise_scale=0.025,
    generator=torch.Generator(device="cuda").manual_seed(42),
).frames[0]
print(f"generation_seconds {time.time() - start:.1f}", flush=True)
export_to_video(frames, out, fps=24)
print("wrote", out, flush=True)
