# Benchmark h10-hard-ts-hf-co-bandtor-gemma-4-E4B-it-GGUF-65536-latest 20261019-161711

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| hard_multifile_bug | 3/3 | 3/3 | 111.7 | 136.6 | - |
| hard_two_vulns | 3/3 | 3/3 | 23.0 | 23.1 | - |
| hard_ambiguous_trace | 3/3 | 3/3 | 56.1 | 63.3 | - |
| hard_long_summary | 3/3 | 3/3 | 20.1 | 21.8 | - |
| hard_compare_functions | 3/3 | 3/3 | 28.4 | 28.5 | - |

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
| CPU % | 0.0 | 25.0 | 42.9 |
| RAM % | 82.1 | 84.5 | 86.8 |
| GPU util % | 0.0 | 52.9 | 100.0 |
| VRAM used MiB | 3773.0 | 4831.2 | 6503.0 |
| GPU temp C | 56.0 | 73.3 | 86.0 |
| GPU power W | 1.8 | 47.0 | 85.9 |

Ollama PROCESSOR split (samples): 100% GPU (x223)

Hardware samples: 225, psutil: True
