# Benchmark full-claude-haiku-5-5+claude-haiku-5-5 20261020-105305

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 3/3 | 3/3 | 12.9 | 14.2 | - |
| fix_bug | 3/3 | 3/3 | 11.1 | 11.4 | - |
| write_tests | 3/3 | 3/3 | 14.7 | 15.2 | - |
| rename_across_files | 3/3 | 3/3 | 15.3 | 15.3 | - |
| find_symbol | 3/3 | 3/3 | 10.6 | 11.6 | - |
| review_sqli | 3/3 | 3/3 | 17.6 | 24.0 | - |
| debug_trace | 3/3 | 3/3 | 46.9 | 50.0 | - |
| summarize_readme | 3/3 | 3/3 | 18.3 | 19.2 | - |
| role_analyzer | 3/3 | 3/3 | 14.2 | 15.5 | - |
| role_data | 3/3 | 3/3 | 8.0 | 8.4 | - |
| role_docs | 3/3 | 3/3 | 17.6 | 18.2 | - |
| role_security | 3/3 | 3/3 | 50.7 | 61.9 | - |
| role_designer | 3/3 | 3/3 | 21.6 | 21.8 | - |
| role_browser | 0/3 | 3/3 | 3.2 | 3.3 | <parameter name="navigate_page">{"url": "http://host.docker.internal:8787/ui/"}</parameter> </invoke | scratch=[] / <parameter name="url">http://host.docker.internal:8787/ui/</parameter> </invoke>  | scratch=[] |
| role_tracker | 3/3 | 3/3 | 7.2 | 7.7 | - |
| role_research | 3/3 | 3/3 | 26.2 | 27.1 | - |

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
| CPU % | 0.0 | 23.6 | 59.0 |
| RAM % | 71.6 | 75.0 | 81.8 |
| GPU util % | 0.0 | 0.0 | 0.0 |
| VRAM used MiB | 0.0 | 0.0 | 0.0 |
| GPU temp C | 38.0 | 47.9 | 54.0 |
| GPU power W | 1.8 | 25.0 | 590.0 |

Ollama PROCESSOR split (samples): -

Hardware samples: 247, psutil: True
