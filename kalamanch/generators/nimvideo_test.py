"""Image-to-video with NimVideo/cogvideox-2b-img2vid (CogVideoX-2B fine-tune, diffusers layout).

Usage: python nimvideo_test.py <photo> <out.mp4> [prompt]
The whole photo is kept: it is letterboxed to the 720x480 frame, not cropped, so the head stays in frame.
"""
import os
import sys
import time

import torch
from diffusers import CogVideoXImageToVideoPipeline
from diffusers.utils import export_to_video, load_image
from PIL import Image

# shared helpers live in ../common (flat next to the script inside the container image)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from _models import require, use_models_dir  # noqa: E402

require("nimvideo-cogvideox-2b-img2vid")  # asks before downloading anything missing
use_models_dir()  # model folders below are relative to the models folder
from _inputs import photo_path

BASE = "nimvideo-cogvideox-2b-img2vid"
W, H, N, FPS = 720, 480, 49, 8

photo = photo_path(sys.argv[1] if len(sys.argv) > 1 else None)
from _paths import render_dir
out = sys.argv[2] if len(sys.argv) > 2 else str(render_dir() / "nimvideo-cogvideox-2b-img2vid.mp4")
prompt = sys.argv[3] if len(sys.argv) > 3 else "A man in a dark blazer stands still and looks at the camera."

pipe = CogVideoXImageToVideoPipeline.from_pretrained(BASE, torch_dtype=torch.float16)
pipe.enable_model_cpu_offload()
pipe.vae.enable_tiling()
pipe.vae.enable_slicing()

src = load_image(photo).convert("RGB")
w, h = src.size
scale = min(W / w, H / h)
new_w, new_h = round(w * scale), round(h * scale)
canvas = Image.new("RGB", (W, H), (0, 0, 0))
canvas.paste(src.resize((new_w, new_h), Image.LANCZOS), ((W - new_w) // 2, (H - new_h) // 2))

start = time.time()
frames = pipe(
    image=canvas, prompt=prompt, height=H, width=W, num_frames=N,
    num_inference_steps=50, guidance_scale=6.0,
    generator=torch.Generator(device="cuda").manual_seed(42),
).frames[0]
print(f"generation_seconds {time.time() - start:.1f}", flush=True)
export_to_video(frames, out, fps=FPS)
print("wrote", out, flush=True)
