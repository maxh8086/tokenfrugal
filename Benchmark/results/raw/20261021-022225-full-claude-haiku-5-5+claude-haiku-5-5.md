# Benchmark full-claude-haiku-5-5+claude-haiku-5-5 20261021-022225

n=3, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 3/3 | 3/3 | 13.2 | 13.6 | - |
| fix_bug | 3/3 | 3/3 | 11.3 | 13.0 | - |
| write_tests | 3/3 | 3/3 | 14.7 | 15.0 | - |
| rename_across_files | 3/3 | 3/3 | 15.4 | 15.7 | - |
| find_symbol | 3/3 | 3/3 | 10.8 | 11.2 | - |
| review_sqli | 3/3 | 3/3 | 18.5 | 19.8 | - |
| debug_trace | 3/3 | 3/3 | 47.2 | 47.5 | - |
| summarize_readme | 3/3 | 3/3 | 17.2 | 17.6 | - |
| role_analyzer | 3/3 | 3/3 | 14.5 | 17.8 | - |
| role_data | 3/3 | 3/3 | 8.5 | 9.0 | - |
| role_docs | 3/3 | 3/3 | 16.1 | 16.2 | - |
| role_security | 3/3 | 3/3 | 48.3 | 49.1 | - |
| role_designer | 3/3 | 3/3 | 20.3 | 20.7 | - |
| role_browser | 0/3 | 3/3 | 4.9 | 11.5 | **Status: Not completed. No page title obtained.**  **Target:** `http://host.docker.internal:8787/ui | scratch=[] / <invoke name="navigate_page"> <parameter name="url">http://host.docker.internal:8787/ui/</parameter> | scratch=[] / <invoke_tool name="navigate_page"> <parameter name="url">http://host.docker.internal:8787/ui/</param | scratch=[] |
| role_tracker | 3/3 | 3/3 | 7.7 | 9.0 | - |
| role_research | 1/3 | 3/3 | 23.9 | 24.2 | **Result: no page heading found.**  The markdown from https://example.com has no heading element. It | scratch=[] / **Result: no page heading found.** The markdown returned from https://example.com contains no headin | scratch=[] |

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
| CPU % | 0.0 | 22.2 | 46.5 |
| RAM % | 63.8 | 67.5 | 77.9 |
| GPU util % | 0.0 | 0.0 | 0.0 |
| VRAM used MiB | 0.0 | 0.0 | 2.0 |
| GPU temp C | 36.0 | 46.6 | 50.0 |
| GPU power W | 2.2 | 26.5 | 590.0 |

Ollama PROCESSOR split (samples): -

Hardware samples: 275, psutil: True
