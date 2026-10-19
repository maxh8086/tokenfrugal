# Benchmark h3-hard-ts-qwen3-8-9b-distill-65536-latest 20261019-101450

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 3/3 | 3/3 | 55.4 | 67.7 | - |
| hard_two_vulns | 3/3 | 3/3 | 23.5 | 23.9 | - |
| hard_ambiguous_trace | 0/3 | 3/3 | 151.8 | 188.1 | ## Crash Analysis  **Exception type:** `FileNotFoundError` (Errno 2)  **Root cause:** The file `/wor | scratch=['trace_cfg.py'] / ## Root Cause Analysis  **Exception type:** `FileNotFoundError` (raised by the OS when `subprocess.r | scratch=['trace_cfg.py'] / **Exception type:** `FileNotFoundError`  **Root cause:** The file `/workspace/tokenfrugal/bench/scra | scratch=['trace_cfg.py'] |
| hard_long_summary | 3/3 | 3/3 | 23.5 | 24.1 | - |
| hard_compare_functions | 3/3 | 3/3 | 29.1 | 29.7 | - |

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
| CPU % | 0.0 | 44.5 | 89.0 |
| RAM % | 67.3 | 77.7 | 87.3 |
| GPU util % | 0.0 | 24.5 | 100.0 |
| VRAM used MiB | 1044.0 | 7079.8 | 7699.0 |
| GPU temp C | 51.0 | 62.8 | 81.0 |
| GPU power W | 1.7 | 29.2 | 95.6 |

Ollama PROCESSOR split (samples): 52%/48% CPU/GPU (x6), 15%/85% CPU/GPU (x228)

Hardware samples: 236, psutil: True
