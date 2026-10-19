# Benchmark h7-hard-ts-granite4-micro-65536-latest 20261019-134528

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 3/3 | 3/3 | 31.9 | 37.4 | - |
| hard_two_vulns | 3/3 | 3/3 | 16.8 | 16.8 | - |
| hard_ambiguous_trace | 3/3 | 3/3 | 32.9 | 33.7 | - |
| hard_long_summary | 3/3 | 3/3 | 16.1 | 16.2 | - |
| hard_compare_functions | 3/3 | 3/3 | 17.7 | 17.9 | - |

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
| CPU % | 0.0 | 24.8 | 44.3 |
| RAM % | 66.0 | 67.4 | 71.3 |
| GPU util % | 0.0 | 22.4 | 99.0 |
| VRAM used MiB | 4747.0 | 5783.8 | 5855.0 |
| GPU temp C | 53.0 | 58.5 | 72.0 |
| GPU power W | 1.8 | 23.9 | 82.9 |

Ollama PROCESSOR split (samples): 100% GPU (x108)

Hardware samples: 109, psutil: True
