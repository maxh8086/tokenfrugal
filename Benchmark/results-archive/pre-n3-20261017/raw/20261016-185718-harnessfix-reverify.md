# Benchmark harnessfix-reverify 20261016-185718

n=1, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 1/1 | 1/1 | 35.3 | 35.3 | - |
| fix_bug | 1/1 | 1/1 | 11.8 | 11.8 | - |
| write_tests | 1/1 | 1/1 | 15.9 | 15.9 | - |
| rename_across_files | 1/1 | 1/1 | 25.4 | 25.4 | - |
| find_symbol | 1/1 | 1/1 | 8.6 | 8.6 | - |
| review_sqli | 1/1 | 1/1 | 13.7 | 13.7 | - |
| debug_trace | 1/1 | 1/1 | 25.4 | 25.4 | - |
| summarize_readme | 1/1 | 1/1 | 23.4 | 23.4 | - |
| role_analyzer | 1/1 | 1/1 | 12.6 | 12.6 | - |
| role_data | 1/1 | 1/1 | 7.5 | 7.5 | - |
| role_docs | 1/1 | 1/1 | 16.3 | 16.3 | - |
| role_security | 1/1 | 1/1 | 69.3 | 69.3 | - |
| role_designer | 1/1 | 1/1 | 22.4 | 22.4 | - |
| role_browser | 1/1 | 1/1 | 34.8 | 34.8 | - |
| role_tracker | 1/1 | 1/1 | 13.0 | 13.0 | - |
| role_research | 1/1 | 1/1 | 25.3 | 25.3 | - |

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
| CPU % | 0.0 | 18.9 | 41.3 |
| RAM % | 57.5 | 68.8 | 80.7 |
| GPU util % | 0.0 | 39.8 | 100.0 |
| VRAM used MiB | 93.0 | 5774.0 | 5861.0 |
| GPU temp C | 41.0 | 57.9 | 75.0 |
| GPU power W | 1.6 | 38.2 | 91.5 |

Ollama PROCESSOR split (samples): 100% GPU (x169)

Hardware samples: 172, psutil: True
