# Benchmark probe-qwen-tracker-browser 20261017-083713

n=1, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| role_browser | 0/1 | 1/1 | 19.5 | 19.5 | **Page Title:** about:blank  **Findings:** The page navigated to `http://host.docker.internal:8787/u | scratch=[] |
| role_tracker | 1/1 | 1/1 | 12.3 | 12.3 | - |

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
| CPU % | 0.0 | 25.4 | 34.9 |
| RAM % | 80.3 | 83.7 | 85.5 |
| GPU util % | 0.0 | 44.9 | 96.0 |
| VRAM used MiB | 0.0 | 4575.9 | 5861.0 |
| GPU temp C | 53.0 | 62.1 | 73.0 |
| GPU power W | 14.8 | 48.3 | 84.6 |

Ollama PROCESSOR split (samples): 100% GPU (x8)

Hardware samples: 11, psutil: True
