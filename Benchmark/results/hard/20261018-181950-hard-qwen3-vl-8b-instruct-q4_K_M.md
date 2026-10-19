# Benchmark hard-qwen3-vl-8b-instruct-q4_K_M 20261018-181950

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 2/3 | 2/3 | 154.1 | 199.6 | FAILED (debugger/qwen3-vl:8b-instruct-q4_K_M): LoopError: task timed out after 150s. Call resume_task('b492633 |
| hard_two_vulns | 3/3 | 3/3 | 24.6 | 103.4 | - |
| hard_ambiguous_trace | 3/3 | 3/3 | 130.4 | 141.0 | - |
| hard_long_summary | 3/3 | 3/3 | 24.4 | 25.9 | - |
| hard_compare_functions | 3/3 | 3/3 | 36.1 | 36.5 | - |

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
| CPU % | 0.0 | 73.9 | 97.5 |
| RAM % | 74.3 | 88.2 | 92.5 |
| GPU util % | 0.0 | 21.2 | 100.0 |
| VRAM used MiB | 775.0 | 7450.9 | 7510.0 |
| GPU temp C | 54.0 | 57.3 | 71.0 |
| GPU power W | 1.8 | 14.1 | 65.0 |

Ollama PROCESSOR split (samples): 23%/77% CPU/GPU (x6), 52%/48% CPU/GPU (x254)

Hardware samples: 263, psutil: True
