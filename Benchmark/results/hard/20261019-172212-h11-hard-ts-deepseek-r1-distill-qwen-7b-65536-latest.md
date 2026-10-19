# Benchmark h11-hard-ts-deepseek-r1-distill-qwen-7b-65536-latest 20261019-172212

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 0/3 | 0/3 | 93.8 | 105.8 | FAILED (debugger/ts-deepseek-r1-distill-qwen-7b-65536:latest): LoopError: you answered without calling any too |
| hard_two_vulns | 0/3 | 0/3 | 55.0 | 65.1 | FAILED (reviewer/ts-deepseek-r1-distill-qwen-7b-65536:latest): LoopError: task timed out after 60s. Call resum / FAILED (reviewer/ts-deepseek-r1-distill-qwen-7b-65536:latest): LoopError: you answered without calling any too |
| hard_ambiguous_trace | 0/3 | 0/3 | 83.8 | 88.8 | FAILED (debugger/ts-deepseek-r1-distill-qwen-7b-65536:latest): LoopError: you answered without calling any too |
| hard_long_summary | 0/3 | 0/3 | 89.1 | 95.6 | FAILED (docs/ts-deepseek-r1-distill-qwen-7b-65536:latest): LoopError: you answered without calling any tool; c |
| hard_compare_functions | 0/3 | 0/3 | 65.2 | 65.9 | FAILED (reviewer/ts-deepseek-r1-distill-qwen-7b-65536:latest): LoopError: task timed out after 60s. Call resum |

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
| CPU % | 0.0 | 59.2 | 83.9 |
| RAM % | 70.7 | 73.2 | 80.7 |
| GPU util % | 0.0 | 51.9 | 100.0 |
| VRAM used MiB | 889.0 | 6844.5 | 6873.0 |
| GPU temp C | 59.0 | 80.6 | 89.0 |
| GPU power W | 1.9 | 57.0 | 78.3 |

Ollama PROCESSOR split (samples): 25%/75% CPU/GPU (x7), 12%/88% CPU/GPU (x296)

Hardware samples: 304, psutil: True
