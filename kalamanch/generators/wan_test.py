"""Wan2.2 TI2V-5B (Q4_K_M GGUF transformer) image-to-video per spec: 832x480, 81 frames, 16 fps, 30 steps, CFG 6.0."""
import os
import sys
import time

import torch
from diffusers import AutoencoderKLWan, FlowMatchEulerDiscreteScheduler, GGUFQuantizationConfig, WanImageToVideoPipeline, WanTransformer3DModel
from diffusers.utils import export_to_video, load_image
from PIL import Image
from safetensors.torch import load_file

# shared helpers live in ../common (flat next to the script inside the container image)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from _models import require, use_models_dir  # noqa: E402

require("wan2.2-ti2v-5b-q4km")  # asks before downloading anything missing
use_models_dir()  # model folders below are relative to the models folder
from _inputs import photo_path

BASE = "wan2.2-ti2v-5b-q4km"
D = f"{BASE}/diffusers"
GGUF = f"{BASE}/Wan2.2-TI2V-5B-Q4_K_M.gguf"
VAE_FILE = f"{BASE}/VAE/Wan2.2_VAE.safetensors"
W, H, N, FPS = 832, 480, 81, 16

photo = photo_path(sys.argv[1] if len(sys.argv) > 1 else None)
from _paths import render_dir
out_dir = str(render_dir())
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, sys.argv[2])  # written straight to video-editor/Render, no project copy
prompt = sys.argv[3] if len(sys.argv) > 3 else "A man in a dark blazer stands still and looks at the camera."

transformer = WanTransformer3DModel.from_single_file(
    GGUF, config=f"{D}/transformer",
    quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16), torch_dtype=torch.bfloat16,
)
vae = AutoencoderKLWan.from_pretrained(f"{D}/vae", torch_dtype=torch.bfloat16)

pipe = WanImageToVideoPipeline.from_pretrained(D, transformer=transformer, vae=vae, torch_dtype=torch.bfloat16)
pipe.scheduler = FlowMatchEulerDiscreteScheduler.from_config(pipe.scheduler.config, shift=3.0)
pipe.enable_model_cpu_offload()

src = load_image(photo)
w, h = src.size
crop_h = int(w * H / W)
top = (h - crop_h) // 2
image = src.crop((0, top, w, top + crop_h)).resize((W, H), Image.LANCZOS)

start = time.time()
frames = pipe(
    image=image, prompt=prompt, height=H, width=W, num_frames=N,
    num_inference_steps=30, guidance_scale=6.0, max_sequence_length=512,
    generator=torch.Generator(device="cuda").manual_seed(42),
).frames[0]
print(f"generation_seconds {time.time() - start:.1f}", flush=True)
export_to_video(frames, out, fps=FPS)
print("wrote", out, flush=True)
