# Benchmark harnessfix-verify-1 20261016-120151

n=1, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 0/1 | 1/1 | 19.8 | 19.8 | ): lowercase, strip, collapse runs of non-alphanumerics into a single '-', no leading or trailing '-'
    ^^^^^^^^^^
SyntaxError: illegal ta |
| fix_bug | 0/1 | 1/1 | 7.8 | 7.8 | Traceback (most recent call last):
  File "<string>", line 2, in <module>
AssertionError
 |
| write_tests | 0/1 | 1/1 | 7.8 | 7.8 | rc=1 tests=0 ttest tests for push, pop and len (at least 3 tests)
             ^^^^^
SyntaxError: invalid syntax
 |
| rename_across_files | 0/1 | 1/1 | 7.7 | 7.7 | def new_name(x):     return x + 1 from a_mod import new_name  print(old_name(1)) |
| find_symbol | 1/1 | 1/1 | 6.3 | 6.3 | - |
| review_sqli | 0/1 | 1/1 | 11.3 | 11.3 | [c86aa0e202] The tool calls failed due to incorrect file paths or invalid arguments. Let's fix the a |
| debug_trace | 1/1 | 1/1 | 21.3 | 21.3 | - |
| summarize_readme | 0/1 | 1/1 | 12.4 | 12.4 | [e9ce46bd2e] The tool error indicates a problem with the request to `crawl_markdown` for the URL `/w |
| role_analyzer | 1/1 | 1/1 | 10.3 | 10.3 | - |
| role_data | 1/1 | 1/1 | 4.0 | 4.0 | - |
| role_docs | 1/1 | 1/1 | 14.0 | 14.0 | - |
| role_security | 0/1 | 1/1 | 67.9 | 67.9 | [1a5e9f2af6] The tool failed due to incorrect file paths or missing files. The correct file path was |
| role_designer | 1/1 | 1/1 | 16.9 | 16.9 | - |
| role_browser | 1/1 | 1/1 | 7.3 | 7.3 | - |
| role_tracker | 1/1 | 1/1 | 8.3 | 8.3 | - |
| role_research | 0/1 | 1/1 | 21.2 | 21.2 | [875afa7efb] The page heading is "Este dominio está destinado al uso en ejemplos de documentación, s |

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
| CPU % | 0.0 | 29.0 | 68.0 |
| RAM % | 53.5 | 61.8 | 71.7 |
| GPU util % | 0.0 | 13.2 | 95.0 |
| VRAM used MiB | 1029.0 | 2431.5 | 2474.0 |
| GPU temp C | 43.0 | 49.4 | 64.0 |
| GPU power W | 1.7 | 19.2 | 79.4 |

Ollama PROCESSOR split (samples): 100% GPU (x114)

Hardware samples: 117, psutil: True
