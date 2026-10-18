# Benchmark harnessfix-verify-2 20261016-120711

n=1, task timeout 150s (bench default)

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 0/1 | 1/1 | 6.8 | 6.8 | ): lowercase, strip, collapse runs of non-alphanumerics into a single '-', no leading or trailing '-'
    ^^^^^^^^^^
SyntaxError: illegal ta |
| fix_bug | 0/1 | 1/1 | 9.0 | 9.0 | Traceback (most recent call last):
  File "<string>", line 2, in <module>
AssertionError
 |
| write_tests | 0/1 | 1/1 | 7.5 | 7.5 | rc=1 tests=0 ttest tests for push, pop and len (at least 3 tests)
             ^^^^^
SyntaxError: invalid syntax
 |
| rename_across_files | 0/1 | 1/1 | 7.4 | 7.4 | def new_name(x):     return x + 1 from a_mod import new_name  print(old_name(1)) |
| find_symbol | 1/1 | 1/1 | 5.8 | 5.8 | - |
| review_sqli | 0/1 | 1/1 | 11.7 | 11.7 | [143a0bfa16] **Vulnerability Class:** File security vulnerability found in the file `/workspace/toke |
| debug_trace | 1/1 | 1/1 | 20.9 | 20.9 | - |
| summarize_readme | 0/1 | 1/1 | 13.0 | 13.0 | [ada5faf35e] The tool error indicates that the request to fetch the README file from the specified U |
| role_analyzer | 1/1 | 1/1 | 10.8 | 10.8 | - |
| role_data | 1/1 | 1/1 | 3.8 | 3.8 | - |
| role_docs | 1/1 | 1/1 | 14.0 | 14.0 | - |
| role_security | 0/1 | 1/1 | 41.4 | 41.4 | [3175641f2c] The tool calls failed due to incorrect file paths or missing necessary parameters. Let' |
| role_designer | 1/1 | 1/1 | 18.0 | 18.0 | - |
| role_browser | 1/1 | 1/1 | 6.6 | 6.6 | - |
| role_tracker | 1/1 | 1/1 | 3.9 | 3.9 | - |
| role_research | 1/1 | 1/1 | 21.0 | 21.0 | - |

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
| CPU % | 0.0 | 27.8 | 61.6 |
| RAM % | 63.9 | 66.3 | 73.9 |
| GPU util % | 0.0 | 7.0 | 98.0 |
| VRAM used MiB | 2474.0 | 2474.0 | 2474.0 |
| GPU temp C | 44.0 | 48.2 | 57.0 |
| GPU power W | 1.7 | 13.0 | 61.0 |

Ollama PROCESSOR split (samples): 100% GPU (x97)

Hardware samples: 97, psutil: True
