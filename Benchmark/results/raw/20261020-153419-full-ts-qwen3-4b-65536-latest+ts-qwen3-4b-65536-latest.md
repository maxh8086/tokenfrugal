# Benchmark full-ts-qwen3-4b-65536-latest+ts-qwen3-4b-65536-latest 20261020-153419

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 0/3 | 0/3 | 94.4 | 94.7 | FAILED (builder/ts-qwen3-4b-65536:latest) reason=timeout: LoopError: task timed out after 90s. Call resume_tas |
| fix_bug | 1/3 | 1/3 | 94.3 | 95.0 | FAILED (builder/ts-qwen3-4b-65536:latest) reason=timeout: LoopError: task timed out after 90s. Call resume_tas |
| write_tests | 1/3 | 1/3 | 120.0 | 120.0 | EXC TimeoutError:  |
| rename_across_files | 0/3 | 0/3 | 94.6 | 95.2 | FAILED (builder/ts-qwen3-4b-65536:latest) reason=timeout: LoopError: task timed out after 90s. Call resume_tas |
| find_symbol | 3/3 | 3/3 | 36.2 | 65.3 | - |
| review_sqli | 3/3 | 3/3 | 34.7 | 35.5 | - |
| debug_trace | 3/3 | 3/3 | 42.4 | 43.8 | - |
| summarize_readme | 3/3 | 3/3 | 37.1 | 62.6 | - |
| role_analyzer | 3/3 | 3/3 | 37.6 | 37.7 | - |
| role_data | 3/3 | 3/3 | 20.7 | 22.3 | - |
| role_docs | 3/3 | 3/3 | 78.2 | 78.8 | - |
| role_security | 3/3 | 3/3 | 52.8 | 110.3 | - |
| role_designer | 3/3 | 3/3 | 42.5 | 87.4 | - |
| role_browser | 0/3 | 0/3 | 80.2 | 80.6 | FAILED (browser/ts-qwen3-4b-65536:latest) reason=timeout: LoopError: task timed out after 80s. Call resume_tas |
| role_tracker | 0/3 | 0/3 | 60.4 | 60.4 | FAILED (tracker/ts-qwen3-4b-65536:latest) reason=timeout: LoopError: task timed out after 60s. Call resume_tas |
| role_research | 0/3 | 0/3 | 64.0 | 72.5 | FAILED (research/ts-qwen3-4b-65536:latest) reason=timeout: LoopError: task timed out after 60s. Call resume_ta |

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
| CPU % | 0.0 | 57.0 | 93.3 |
| RAM % | 77.1 | 86.8 | 97.8 |
| GPU util % | 0.0 | 30.1 | 100.0 |
| VRAM used MiB | 6914.0 | 6923.8 | 6926.0 |
| GPU temp C | 48.0 | 57.9 | 72.0 |
| GPU power W | 1.8 | 24.5 | 94.1 |

Ollama PROCESSOR split (samples): -

Hardware samples: 949, psutil: True
