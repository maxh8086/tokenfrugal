"""Quantize the LTX T5-XXL text encoder to 8-bit, then delete the bf16 shards."""
import sys
import os
import shutil
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from _models import require, use_models_dir  # noqa: E402

require("ltx-video-2b-distilled")  # asks before downloading anything missing
use_models_dir()  # model folders below are relative to the models folder
import torch
from transformers import BitsAndBytesConfig, T5EncoderModel

SRC = Path("ltx-video-2b-distilled/text_encoder")
DST = Path("ltx-video-2b-distilled/text_encoder_8bit")

model = T5EncoderModel.from_pretrained(
    SRC,
    quantization_config=BitsAndBytesConfig(load_in_8bit=True),
    torch_dtype=torch.bfloat16,
    device_map="auto",
    low_cpu_mem_usage=True,
)
model.save_pretrained(DST, safe_serialization=True)
print("saved 8-bit encoder to", DST)

# Old unquantized weights go only after the 8-bit copy is on disk.
for shard in SRC.glob("*.safetensors"):
    shard.unlink()
for index in SRC.glob("*.index.json"):
    index.unlink()
print("removed bf16 shards from", SRC)
