# Benchmark harnessfix-verify-3 20261016-121040

n=1, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 0/1 | 1/1 | 7.0 | 7.0 | ): lowercase, strip, collapse runs of non-alphanumerics into a single '-', no leading or trailing '-'
    ^^^^^^^^^^
SyntaxError: illegal ta |
| fix_bug | 0/1 | 1/1 | 7.7 | 7.7 | Traceback (most recent call last):
  File "<string>", line 2, in <module>
AssertionError
 |
| write_tests | 0/1 | 1/1 | 7.7 | 7.7 | rc=1 tests=0 ttest tests for push, pop and len (at least 3 tests)
             ^^^^^
SyntaxError: invalid syntax
 |
| rename_across_files | 0/1 | 1/1 | 7.5 | 7.5 | def new_name(x):     return x + 1 from a_mod import new_name  print(old_name(1)) |
| find_symbol | 1/1 | 1/1 | 6.2 | 6.2 | - |
| review_sqli | 0/1 | 1/1 | 12.0 | 12.0 | [f4c06c1310] The tool calls failed due to incorrect file paths or invalid structures. To fix this, I |
| debug_trace | 1/1 | 1/1 | 21.4 | 21.4 | - |
| summarize_readme | 0/1 | 1/1 | 22.7 | 22.7 | [7463da3226] The project does not exist at the specified URL.   The error indicates a problem with t |
| role_analyzer | 1/1 | 1/1 | 10.1 | 10.1 | - |
| role_data | 1/1 | 1/1 | 4.1 | 4.1 | - |
| role_docs | 1/1 | 1/1 | 13.9 | 13.9 | - |
| role_security | 0/1 | 1/1 | 43.6 | 43.6 | [ed098eb2a5] **Corrected Arguments:**  1. `read_file` with `path` as `/workspace/tokenfrugal/bench/s |
| role_designer | 1/1 | 1/1 | 18.3 | 18.3 | - |
| role_browser | 1/1 | 1/1 | 6.6 | 6.6 | - |
| role_tracker | 1/1 | 1/1 | 4.4 | 4.4 | - |
| role_research | 0/1 | 1/1 | 21.4 | 21.4 | [8e0c500fee] The page heading is "Este dominio está destinado al uso en ejemplos de documentación, s |

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
| CPU % | 0.0 | 28.2 | 62.8 |
| RAM % | 64.0 | 67.1 | 75.5 |
| GPU util % | 0.0 | 10.9 | 99.0 |
| VRAM used MiB | 2474.0 | 2474.0 | 2474.0 |
| GPU temp C | 47.0 | 49.7 | 61.0 |
| GPU power W | 1.7 | 15.8 | 70.8 |

Ollama PROCESSOR split (samples): 100% GPU (x103)

Hardware samples: 103, psutil: True
