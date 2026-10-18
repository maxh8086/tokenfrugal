# Benchmark browser-longlived 20261017-084227

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| role_browser | 3/3 | 3/3 | 14.8 | 14.9 | - |

## Environment and hardware

| variable | value |
|---|---|
| OLLAMA_MAX_LOADED_MODELS | 1 |
| OLLAMA_NUM_PARALLEL | 1 |
| OLLAMA_KEEP_ALIVE | 30m |
| OLLAMA_FLASH_ATTENTION | 1 |
| OLLAMA_KV_CACHE_TYPE | q8_0 |

Task timeout: 150s (source: bench default)

| metric | min | avg | max |
|---|---|---|---|
| CPU % | 0.0 | 26.7 | 40.2 |
| RAM % | 85.3 | 86.8 | 87.9 |
| GPU util % | 0.0 | 57.6 | 100.0 |
| VRAM used MiB | 5861.0 | 5861.0 | 5861.0 |
| GPU temp C | 46.0 | 62.5 | 72.0 |
| GPU power W | 1.9 | 53.0 | 81.0 |

Ollama PROCESSOR split (samples): 100% GPU (x15)

Hardware samples: 15, psutil: True
