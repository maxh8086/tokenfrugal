# Benchmark batch-phi4-mini-latest 20261015-230910

n=2, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 0/2 | 0/2 | 8.8 | 20.7 | FAILED (builder/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real  |
| fix_bug | 0/2 | 0/2 | 11.6 | 12.2 | FAILED (builder/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real  |
| write_tests | 0/2 | 0/2 | 16.2 | 25.4 | FAILED (builder/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real  |
| rename_across_files | 0/2 | 0/2 | 10.3 | 14.3 | FAILED (builder/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real  |
| find_symbol | 0/2 | 0/2 | 6.7 | 6.9 | FAILED (builder/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real  |
| review_sqli | 0/2 | 0/2 | 12.5 | 13.1 | FAILED (reviewer/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real |
| debug_trace | 0/2 | 0/2 | 33.6 | 44.5 | FAILED (debugger/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real |
| summarize_readme | 0/2 | 0/2 | 13.6 | 13.7 | FAILED (research/phi4-mini:latest): LoopError: answer contains filler/placeholder text; redo with concrete con |
| role_analyzer | 0/2 | 0/2 | 11.3 | 11.3 | FAILED (analyzer/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real |
| role_data | 0/2 | 0/2 | 5.6 | 6.1 | FAILED (data/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real dat |
| role_docs | 0/2 | 0/2 | 28.1 | 28.8 | FAILED (docs/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real dat |
| role_security | 0/2 | 0/2 | 38.9 | 39.7 | FAILED (security/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real |
| role_designer | 2/2 | 2/2 | 21.8 | 23.4 | - |
| role_browser | 0/2 | 0/2 | 5.0 | 5.4 | FAILED (browser/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real  |
| role_tracker | 0/2 | 0/2 | 15.3 | 150.3 | FAILED (tracker/phi4-mini:latest): LoopError: task timed out after 150s. Call resume_task('285d83842a') to ret / FAILED (tracker/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real  |
| role_research | 0/2 | 0/2 | 16.8 | 72.0 | FAILED (research/phi4-mini:latest): LoopError: you answered without calling any tool; call a tool to read real |

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
| CPU % | 0.0 | 44.4 | 86.3 |
| RAM % | 69.0 | 79.6 | 89.4 |
| GPU util % | 0.0 | 23.4 | 96.0 |
| VRAM used MiB | 1042.0 | 7011.1 | 7062.0 |
| GPU temp C | 53.0 | 63.3 | 73.0 |
| GPU power W | 1.8 | 29.4 | 98.9 |

Ollama PROCESSOR split (samples): 100% GPU (x2), 25%/75% CPU/GPU (x346)

Hardware samples: 351, psutil: True
