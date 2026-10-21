# Benchmark full-claude-haiku-5-5+claude-haiku-5-5 20261021-062524

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 3/3 | 3/3 | 11.3 | 11.4 | - |
| fix_bug | 3/3 | 3/3 | 9.7 | 9.7 | - |
| write_tests | 3/3 | 3/3 | 11.6 | 13.4 | - |
| rename_across_files | 3/3 | 3/3 | 11.4 | 12.2 | - |
| find_symbol | 3/3 | 3/3 | 9.4 | 9.9 | - |
| review_sqli | 3/3 | 3/3 | 16.7 | 18.7 | - |
| debug_trace | 3/3 | 3/3 | 46.9 | 49.6 | - |
| summarize_readme | 3/3 | 3/3 | 17.6 | 18.3 | - |
| role_analyzer | 3/3 | 3/3 | 14.4 | 15.1 | - |
| role_data | 3/3 | 3/3 | 7.7 | 11.0 | - |
| role_docs | 3/3 | 3/3 | 17.9 | 18.1 | - |
| role_security | 3/3 | 3/3 | 55.0 | 56.7 | - |
| role_designer | 3/3 | 3/3 | 23.1 | 24.8 | - |
| role_browser | 3/3 | 3/3 | 11.0 | 14.5 | - |
| role_tracker | 3/3 | 3/3 | 9.4 | 12.1 | - |
| role_research | 3/3 | 3/3 | 25.8 | 27.2 | - |

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
| CPU % | 0.0 | 26.3 | 56.9 |
| RAM % | 71.1 | 75.0 | 83.9 |
| GPU util % | 0.0 | 0.0 | 0.0 |
| VRAM used MiB | 0.0 | 0.0 | 0.0 |
| GPU temp C | 40.0 | 47.4 | 50.0 |
| GPU power W | 2.3 | 27.0 | 590.0 |

Ollama PROCESSOR split (samples): -

Hardware samples: 273, psutil: True
