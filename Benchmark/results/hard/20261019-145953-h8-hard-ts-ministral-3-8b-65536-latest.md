# Benchmark h8-hard-ts-ministral-3-8b-65536-latest 20261019-145953

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 3/3 | 3/3 | 135.1 | 150.5 | - |
| hard_two_vulns | 3/3 | 3/3 | 35.7 | 36.8 | - |
| hard_ambiguous_trace | 0/3 | 3/3 | 51.0 | 51.6 | The script does not crash; it runs successfully and prints `7` (since `3 + 1 = 4`, then `4 * 2 = 8`  | scratch=['trace_cfg.py'] |
| hard_long_summary | 3/3 | 3/3 | 23.1 | 24.4 | - |
| hard_compare_functions | 3/3 | 3/3 | 36.8 | 37.1 | - |

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
| CPU % | 0.0 | 52.7 | 84.0 |
| RAM % | 66.3 | 83.8 | 85.9 |
| GPU util % | 0.0 | 20.3 | 97.0 |
| VRAM used MiB | 889.0 | 6854.0 | 6943.0 |
| GPU temp C | 54.0 | 58.0 | 71.0 |
| GPU power W | 1.7 | 14.6 | 56.0 |

Ollama PROCESSOR split (samples): 26%/74% CPU/GPU (x7), 49%/51% CPU/GPU (x207)

Hardware samples: 216, psutil: True
