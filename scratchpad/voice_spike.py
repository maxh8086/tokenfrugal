"""Task 3 spike: time and VRAM for one ~25 s Kokoro narration on this machine."""
import json
import sys
import time

import numpy as np
import soundfile as sf
import torch
from kokoro import KPipeline

TEXT = (
    "Most small teams lose hours each week to the same handoff problem. "
    "A request arrives in one place, the answer lives in another, and the "
    "person who needs it waits. This film shows how one shared intake step "
    "routes each request to the right owner, keeps a record of every decision, "
    "and returns a finished answer the same day. Nothing is copied by hand, "
    "and nothing is lost between the inbox and the report."
)

VOICE = "af_heart"
OUT_WAV = sys.argv[1] if len(sys.argv) > 1 else "narration_spike.wav"

torch.cuda.reset_peak_memory_stats()
device = "cuda" if torch.cuda.is_available() else "cpu"

t_load = time.perf_counter()
pipeline = KPipeline(lang_code="a", device=device)
load_s = time.perf_counter() - t_load

t0 = time.perf_counter()
chunks = []
for _, _, audio in pipeline(TEXT, voice=VOICE, speed=1.0):
    chunks.append(np.asarray(audio, dtype=np.float32))
synth_s = time.perf_counter() - t0

wav = np.concatenate(chunks)
sr = 24000
sf.write(OUT_WAV, wav, sr)

peak_alloc_mib = torch.cuda.max_memory_allocated() / 2**20 if device == "cuda" else 0.0
peak_reserved_mib = torch.cuda.max_memory_reserved() / 2**20 if device == "cuda" else 0.0
words = len(TEXT.split())

result = {
    "device": device,
    "torch": torch.__version__,
    "voice": VOICE,
    "words": words,
    "audio_seconds": round(len(wav) / sr, 2),
    "words_per_second": round(words / (len(wav) / sr), 2),
    "load_seconds": round(load_s, 2),
    "synth_seconds": round(synth_s, 2),
    "realtime_factor": round(synth_s / (len(wav) / sr), 3),
    "peak_cuda_allocated_mib": round(peak_alloc_mib, 1),
    "peak_cuda_reserved_mib": round(peak_reserved_mib, 1),
    "out_wav": OUT_WAV,
}
print(json.dumps(result, indent=2))
