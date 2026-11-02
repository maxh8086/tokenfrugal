import sys
import os
import sys
import numpy as np
import torch
from diffusers import LTXImageToVideoPipeline, LTXVideoTransformer3DModel
from diffusers.utils import export_to_video, load_image
from transformers import T5EncoderModel

# shared helpers live in ../common (flat next to the script inside the container image)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from _models import require, use_models_dir  # noqa: E402

require("ltx-video-2b-distilled")  # asks before downloading anything missing
use_models_dir()  # model folders below are relative to the models folder
from _inputs import photo_path

BASE = "ltx-video-2b-distilled"
WEIGHTS = f"{BASE}/ltxv-2b-0.9.8-distilled-fp8.safetensors"
guid = float(sys.argv[1])
out = sys.argv[2]
photo = photo_path(sys.argv[3] if len(sys.argv) > 3 else None)
prompt = "A man in a dark blazer stands still and looks at the camera."

text_encoder = T5EncoderModel.from_pretrained(f"{BASE}/text_encoder_8bit", torch_dtype=torch.bfloat16, device_map="cuda")
transformer = LTXVideoTransformer3DModel.from_single_file(WEIGHTS, torch_dtype=torch.bfloat16)
pipe = LTXImageToVideoPipeline.from_pretrained(BASE, transformer=transformer, text_encoder=None, torch_dtype=torch.bfloat16)
pipe.text_encoder = text_encoder
from diffusers import FlowMatchEulerDiscreteScheduler
DISTILLED = [1.0, 0.9937, 0.9875, 0.9812, 0.975, 0.9094, 0.725, 0.4219]
pipe.scheduler = FlowMatchEulerDiscreteScheduler.from_config(pipe.scheduler.config, use_dynamic_shifting=False, shift=1.0)
_orig_set = pipe.scheduler.set_timesteps
def _set(num_inference_steps=None, device=None, sigmas=None, mu=None, **kw):
    return _orig_set(sigmas=DISTILLED, device=device)
pipe.scheduler.set_timesteps = _set
pipe.enable_model_cpu_offload()

image = load_image(photo).resize((512, 704))
frames = pipe(image=image, prompt=prompt, width=512, height=704, num_frames=17,
              guidance_scale=guid, generator=torch.manual_seed(42)).frames[0]
arr = np.stack([np.asarray(f, dtype=np.float32) for f in frames])
print("frame_std_per_frame", [round(float(arr[i].std()), 1) for i in range(0, len(arr), 4)], flush=True)
export_to_video(frames, out, fps=24)
print("wrote", out, flush=True)
