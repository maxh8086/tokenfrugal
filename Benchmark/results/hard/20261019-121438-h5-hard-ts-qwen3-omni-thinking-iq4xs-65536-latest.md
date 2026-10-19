# Benchmark h5-hard-ts-qwen3-omni-thinking-iq4xs-65536-latest 20261019-121438

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 0/3 | 0/3 | 226.5 | 227.0 | FAILED (debugger/ts-qwen3-omni-thinking-iq4xs-65536:latest): LoopError: task timed out after 220s. Call resume |
| hard_two_vulns | 2/3 | 2/3 | 59.5 | 64.7 | FAILED (reviewer/ts-qwen3-omni-thinking-iq4xs-65536:latest): LoopError: task timed out after 60s. Call resume_ |
| hard_ambiguous_trace | 3/3 | 3/3 | 60.0 | 76.5 | - |
| hard_long_summary | 3/3 | 3/3 | 56.2 | 56.9 | - |
| hard_compare_functions | 1/3 | 1/3 | 64.6 | 64.6 | FAILED (reviewer/ts-qwen3-omni-thinking-iq4xs-65536:latest): LoopError: task timed out after 60s. Call resume_ |

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
| CPU % | 0.0 | 62.3 | 85.2 |
| RAM % | 49.4 | 91.9 | 96.8 |
| GPU util % | 0.0 | 32.2 | 100.0 |
| VRAM used MiB | 1028.0 | 7051.4 | 7117.0 |
| GPU temp C | 48.0 | 54.5 | 63.0 |
| GPU power W | 1.8 | 18.9 | 67.9 |

Ollama PROCESSOR split (samples): 72%/28% CPU/GPU (x6), 69%/31% CPU/GPU (x348)

Hardware samples: 359, psutil: True
