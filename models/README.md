# models/

Local model folders, grouped by what they do. Weights, venvs and renders are git-ignored; only scripts are tracked.

| Folder | Holds |
| --- | --- |
| `video_generation/` | LTX-Video, Wan 2.1/2.2, OmniAvatar, SVD weights only. The scripts live in `kalamanch/` at the repo root; fetch with `python kalamanch/preflight.py --fetch` |
| `image_generation/` | FLUX Kontext (`flux_scene.py`, stills and avatars) |
| `image_enhancement/` | face and image enhancement weights |
| `talking_head/` | LivePortrait (photo driven by a driver video) |
| `lipsync/` | MuseTalk (mouth sync to audio) |
| `*.Modelfile`, `trial/` | Ollama builder and thinker model definitions |

## Content pipeline stage models

The seven content stages use three Ollama tags, all already installed as customised builds of the same families (Q4_K_M, tool-capable, GPU-resident at 16k context on an 8 GB card). Nothing needs pulling:

```
ts-qwen3-8b-40960:latest                          # content-outline, content-executive (qwen3 8B, 5.2 GB)
ts-hf-co-bandtor-gemma-4-E4B-it-GGUF-65536:latest # content-draft, content-humanize (gemma 4 E4B, 5.0 GB)
ts-llama3-1-8b-65536:latest                       # content-factcheck, content-critic, content-antislop (llama 3.1 8B, 4.9 GB)
```

Why gemma 4 instead of gemma3:4b: the installed gemma3 4B build (`ts-gemma3-4b-65536`) has no `tools` capability in Ollama, and the gemma3 12B build does not fit in 8 GB of VRAM. The gemma 4 E4B build is the same family, a newer version, and reports `tools`.

`python scripts/doctor.py` lists any of them that is not installed (report only, nothing is pulled).

Sizing: the stages run one after another, so keep one model resident at a time. Set `OLLAMA_MAX_LOADED_MODELS=1` and `OLLAMA_KEEP_ALIVE=5m` before starting Ollama (on Windows, as user environment variables, then restart Ollama). To check a tag: `ollama show <tag>` (look for `tools`) and `ollama ps` (look for `100% GPU`).
