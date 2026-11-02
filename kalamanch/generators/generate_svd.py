"""Image-to-video with SVD-XT 1.1 (fp16). Writes video-editor/Render/svd-xt-1.1.mp4 by default from the portrait photo."""
import os
import sys
import torch
from PIL import Image
from diffusers import StableVideoDiffusionPipeline
from diffusers.utils import export_to_video

# shared helpers live in ../common (flat next to the script inside the container image)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from _models import require, use_models_dir  # noqa: E402

require("svd-xt-1.1")  # asks before downloading anything missing
use_models_dir()  # model folders below are relative to the models folder
from _inputs import photo_path
from _paths import render_dir

photo, out_path = photo_path(sys.argv[1] if len(sys.argv) > 1 else None), (sys.argv[2] if len(sys.argv) > 2 else str(render_dir() / "svd-xt-1.1.mp4"))
image = Image.open(photo).convert("RGB")
image.thumbnail((576, 1024))
image = image.resize((576, 1024))

pipe = StableVideoDiffusionPipeline.from_pretrained(
    "svd-xt-1.1", torch_dtype=torch.float16, variant="fp16"
)
pipe.enable_model_cpu_offload()
frames = pipe(image, decode_chunk_size=2, num_frames=25, motion_bucket_id=127, noise_aug_strength=0.02,
              generator=torch.manual_seed(42)).frames[0]
export_to_video(frames, out_path, fps=7)
print("wrote", out_path)
